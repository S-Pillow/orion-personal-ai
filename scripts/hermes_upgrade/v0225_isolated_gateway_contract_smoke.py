#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json, os, secrets, socket, subprocess, tempfile, time
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
import psutil
import yaml

EXPECTED_RELEASE_HEAD = 'bf0203a794a07aac3ff764972ab9087baa4e4f4e'
EXPECTED_CANDIDATE_HASHES = {
    'agent/monitoring/cron_health.py': 'd5fd17bb5fdefb3c9e197b3633da322c70fa2f3d84a775b6be69c4e7a7d30b08',
    'cron/error_classification.py': '86c4a839152e7188c2e71a290ed953d32b24c050b7bf96df8cbd59c9a8bafd39',
    'cron/executions.py': '639875c57c153df7cbd4782cef802bc93d2b79fdf14da7b9bd090f8877e86a91',
    'cron/jobs.py': 'eb64e1f6ccdc7fb158f53f373a1b61f60ae6888be274f0557e1d90be0bc4fe3a',
    'gateway/platforms/api_server.py': 'fc376aec9d0812260a279efa89978ff934da902db00c3cce4887e68fb10038d1',
}
PROFILE = 'companion'
DEFAULT_PORT = 18642
START_TIMEOUT_S = 45.0
HTTP_TIMEOUT_S = 5.0

def sha256(path: Path):
    if not path.is_file(): return None
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def stat_signature(path: Path):
    try: st=path.stat()
    except FileNotFoundError: return (False,None,None)
    return (True,int(st.st_size),int(st.st_mtime_ns))

def git_single(root: Path,*args:str)->str:
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if p.returncode: raise RuntimeError(f"git {' '.join(args)} failed ({p.returncode}): {p.stderr.rstrip()}")
    lines=p.stdout.splitlines()
    if len(lines)!=1 or not lines[0].strip(): raise RuntimeError(f"git {' '.join(args)} expected one non-empty line; observed {len(lines)}")
    return lines[0].strip()

def candidate_status_paths(root: Path):
    p=subprocess.run(['git','-C',str(root),'status','--porcelain=v1'],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if p.returncode: raise RuntimeError(f'candidate git status failed ({p.returncode})')
    paths=[]
    for line in p.stdout.splitlines():
        if len(line)<4: raise RuntimeError(f'malformed porcelain record: {line!r}')
        paths.append(line[3:])
    return sorted(paths)

def snapshot_production(root: Path, profile_home: Path):
    hashed=[root/'config.yaml',root/'.env',root/'active_profile',profile_home/'config.yaml',profile_home/'.env']
    runtime=[root/'state.db',root/'gateway_state.json',root/'gateway.pid',profile_home/'state.db',profile_home/'gateway_state.json',profile_home/'gateway.pid']
    return {'hashes':{str(p):sha256(p) for p in hashed},'runtime':{str(p):stat_signature(p) for p in runtime}}

def listener_rows(port:int):
    rows=[]
    for c in psutil.net_connections(kind='tcp'):
        if c.status==psutil.CONN_LISTEN and c.laddr and int(c.laddr.port)==port:
            rows.append((c.pid,str(c.laddr.ip),int(c.laddr.port)))
    return sorted(rows,key=lambda r:((r[0] or -1),r[1],r[2]))

def require_single_listener(port:int,expected_host=None):
    rows=listener_rows(port)
    if len(rows)!=1: raise RuntimeError(f'expected exactly one listener on {port}; observed {rows}')
    row=rows[0]
    if expected_host is not None and row[1]!=expected_host: raise RuntimeError(f'listener on {port} bound to {row[1]!r}, expected {expected_host!r}')
    return row

def tcp_port_free(host:str,port:int):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        try: s.bind((host,port))
        except OSError: return False
    return True

def http_json(method,url,token=None,payload=None):
    headers={'Accept':'application/json'}; body=None
    if token is not None: headers['Authorization']=f'Bearer {token}'
    if payload is not None:
        body=json.dumps(payload).encode(); headers['Content-Type']='application/json'
    req=urlrequest.Request(url,data=body,headers=headers,method=method)
    try:
        with urlrequest.urlopen(req,timeout=HTTP_TIMEOUT_S) as r: raw=r.read(); code=int(r.status)
    except urlerror.HTTPError as e: code=int(e.code); raw=e.read()
    except (urlerror.URLError,TimeoutError,OSError) as e: raise RuntimeError(f'HTTP request failed for {method} {url}: {e}') from e
    if not raw: return code,None
    try: return code,json.loads(raw.decode())
    except Exception: return code,None

def safe_log_tail(path:Path,key:str,lines=60):
    try: text=path.read_text(encoding='utf-8',errors='replace')
    except OSError: return '<log unavailable>'
    return '\n'.join(text.splitlines()[-lines:]).replace(key,'<redacted-ephemeral-api-key>')

def scrubbed_child_env(scratch_profile:Path,key:str,port:int):
    allow=('SystemRoot','WINDIR','COMSPEC','PATH','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA','PROGRAMDATA','PROCESSOR_ARCHITECTURE','PROCESSOR_ARCHITEW6432','NUMBER_OF_PROCESSORS','USERNAME')
    env={n:os.environ[n] for n in allow if n in os.environ}
    env.update({'HERMES_HOME':str(scratch_profile),'API_SERVER_ENABLED':'true','API_SERVER_KEY':key,'API_SERVER_HOST':'127.0.0.1','API_SERVER_PORT':str(port),'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1','NO_COLOR':'1'})
    return env

def prepare_scratch_config(source:Path,dest:Path,port:int):
    data=yaml.safe_load(source.read_text(encoding='utf-8-sig')) or {}
    if not isinstance(data,dict): raise RuntimeError('production config root is not a mapping')
    cfg=copy.deepcopy(data)
    gateway=cfg.get('gateway')
    if gateway is None: gateway={}; cfg['gateway']=gateway
    if not isinstance(gateway,dict): raise RuntimeError('gateway config is not a mapping')
    gateway['standalone']=True; gateway['on_all_adapters_down']='stay_alive'; gateway['profile_routes']=[]; gateway.pop('relay_url',None); cfg.pop('relay_url',None)
    cfg['platforms']={'api_server':{'enabled':True,'host':'127.0.0.1','port':port}}
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True),encoding='utf-8',newline='\n')

def descendants(proc):
    try: root=psutil.Process(proc.pid)
    except psutil.Error: return []
    try: return [root,*root.children(recursive=True)]
    except psutil.Error: return [root]

def terminate_owned_tree(proc):
    owned=descendants(proc); ids=[]
    for p in owned:
        try: ids.append((p.pid,p.create_time()))
        except psutil.Error: pass
    if proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=8)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)
    for pid,created in reversed(ids):
        if pid==proc.pid: continue
        try:
            p=psutil.Process(pid)
            if abs(p.create_time()-created)<=0.001: p.terminate()
        except psutil.Error: pass
    deadline=time.time()+5
    while time.time()<deadline:
        alive=[]
        for pid,created in ids:
            try:
                p=psutil.Process(pid)
                if abs(p.create_time()-created)<=0.001 and p.is_running(): alive.append(p)
            except psutil.Error: pass
        if not alive: return
        time.sleep(.1)
    for p in alive:
        try: p.kill()
        except psutil.Error: pass

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--production-hermes-root',required=True); ap.add_argument('--candidate-root',required=True); ap.add_argument('--runtime-python',required=True); ap.add_argument('--port',type=int,default=DEFAULT_PORT); args=ap.parse_args()
    prod_root=Path(args.production_hermes_root).resolve(); prod_profile=prod_root/'profiles'/PROFILE; candidate=Path(args.candidate_root).resolve(); runtime_python=Path(args.runtime_python).resolve(); port=int(args.port)
    if not prod_root.is_dir() or not prod_profile.is_dir(): raise RuntimeError('production Hermes root or COMPANION profile is missing')
    if not (prod_profile/'config.yaml').is_file(): raise RuntimeError('production COMPANION config.yaml is missing')
    if not candidate.is_dir() or not (candidate/'.git').exists(): raise RuntimeError('candidate root is not a Git checkout')
    if not runtime_python.is_file(): raise RuntimeError('isolated runtime Python is missing')
    if not tcp_port_free('127.0.0.1',port): raise RuntimeError(f'isolated port {port} is not free')
    head=git_single(candidate,'rev-parse','HEAD')
    if head!=EXPECTED_RELEASE_HEAD: raise RuntimeError(f'candidate HEAD drift: {head}')
    expected_paths=sorted(EXPECTED_CANDIDATE_HASHES); actual_paths=candidate_status_paths(candidate)
    if actual_paths!=expected_paths: raise RuntimeError(f'candidate changed scope mismatch: expected {expected_paths}, observed {actual_paths}')
    for rel,expected in EXPECTED_CANDIDATE_HASHES.items():
        observed=sha256(candidate/rel)
        if observed!=expected: raise RuntimeError(f'candidate hash mismatch for {rel}: expected {expected}, observed {observed}')
    prod_before=snapshot_production(prod_root,prod_profile); prod_listener_before=require_single_listener(8642); prod_pid_before=prod_listener_before[0]
    stamp=time.strftime('%Y%m%d-%H%M%S'); scratch_root=Path(tempfile.gettempdir())/f'orion-hermes-v0225-gateway-{stamp}'; scratch_profile=scratch_root/'profiles'/PROFILE; scratch_profile.mkdir(parents=True,exist_ok=False)
    prepare_scratch_config(prod_profile/'config.yaml',scratch_profile/'config.yaml',port)
    key=secrets.token_urlsafe(36)
    (scratch_profile/'.env').write_text(f'# Disposable qualification only.\nAPI_SERVER_ENABLED=true\nAPI_SERVER_KEY={key}\nAPI_SERVER_HOST=127.0.0.1\nAPI_SERVER_PORT={port}\n',encoding='utf-8',newline='\n')
    log_path=scratch_root/'gateway.log'; env=scrubbed_child_env(scratch_profile,key,port); cmd=[str(runtime_python),'-B','-m','hermes_cli.main','gateway','run','--force']
    print(f'CANDIDATE_HEAD={head}'); print('SCRATCH_PROFILE_LAYOUT=profiles/companion'); print('SCRATCH_GATEWAY_STANDALONE=true'); print('SCRATCH_EXTERNAL_PLATFORM_COUNT=0'); print('SCRATCH_PRODUCTION_CREDENTIALS_COPIED=false'); print(f'ISOLATED_BIND_TARGET=127.0.0.1:{port}')
    proc=None
    try:
        with log_path.open('wb') as log:
            proc=subprocess.Popen(cmd,cwd=str(candidate),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
            deadline=time.time()+START_TIMEOUT_S
            while time.time()<deadline:
                if proc.poll() is not None: raise RuntimeError('isolated gateway exited before readiness\n'+safe_log_tail(log_path,key))
                if listener_rows(port): break
                time.sleep(.25)
            else: raise RuntimeError('isolated gateway did not bind before timeout\n'+safe_log_tail(log_path,key))
        child_listener=require_single_listener(port,expected_host='127.0.0.1'); owned_pids={p.pid for p in descendants(proc)}
        if child_listener[0] not in owned_pids: raise RuntimeError(f'isolated listener PID {child_listener[0]} not owned by candidate tree {sorted(owned_pids)}')
        base=f'http://127.0.0.1:{port}'
        if http_json('GET',base+'/health')[0]!=200: raise RuntimeError('GET /health did not return 200')
        if http_json('GET',base+'/v1/capabilities')[0]!=401: raise RuntimeError('unauthenticated capabilities did not return 401')
        if http_json('GET',base+'/v1/capabilities',token='orion-wrong-disposable-token')[0]!=401: raise RuntimeError('wrong-token capabilities did not return 401')
        cap_code,caps=http_json('GET',base+'/v1/capabilities',token=key)
        if cap_code!=200 or not isinstance(caps,dict): raise RuntimeError(f'authorized capabilities expected JSON 200; observed {cap_code}')
        features=caps.get('features'); endpoints=caps.get('endpoints')
        if not isinstance(features,dict) or not isinstance(endpoints,dict): raise RuntimeError('capabilities missing features/endpoints maps')
        required={'audio_api':True,'realtime_voice':False,'session_chat':True,'session_chat_streaming':True,'run_stop':True,'run_steer':True,'run_approval_response':True,'approval_events':True}
        bad={k:(features.get(k),v) for k,v in required.items() if features.get(k) is not v}
        if bad: raise RuntimeError(f'capability feature mismatch: {bad}')
        for name,method,path in [('audio_transcribe','POST','/api/audio/transcribe'),('audio_speak','POST','/api/audio/speak')]:
            row=endpoints.get(name)
            if not isinstance(row,dict) or row.get('method')!=method or row.get('path')!=path: raise RuntimeError(f'capability endpoint mismatch for {name}: {row!r}')
        if http_json('POST',base+'/api/audio/speak',payload={})[0]!=401: raise RuntimeError('unauthenticated audio speak did not return 401')
        if http_json('POST',base+'/api/audio/speak',token=key,payload={})[0]!=400: raise RuntimeError('authorized empty audio speak did not return local 400 validation')
        if http_json('POST',base+'/api/audio/transcribe',token=key,payload={})[0]!=400: raise RuntimeError('authorized empty audio transcribe did not return local 400 validation')
        print('ISOLATED_GATEWAY_HEALTH=PASS'); print('ISOLATED_BIND_LOCALHOST_ONLY=PASS'); print('API_BEARER_AUTH=PASS'); print('CAPABILITY_CONTRACT=PASS'); print('P404A_AUDIO_ROUTE_AUTH=PASS'); print('P404A_AUDIO_ROUTE_LOCAL_VALIDATION=PASS'); print('MODEL_PROVIDER_CALLS=0'); print('STT_PROVIDER_CALLS=0'); print('TTS_PROVIDER_CALLS=0'); print('MEMORY_CALLS=0')
    finally:
        if proc is not None: terminate_owned_tree(proc)
    if listener_rows(port): raise RuntimeError(f'isolated listener {port} remained after exact candidate cleanup')
    if snapshot_production(prod_root,prod_profile)!=prod_before: raise RuntimeError('production watched artifacts changed during isolated gateway smoke')
    prod_listener_after=require_single_listener(8642)
    if prod_listener_after[0]!=prod_pid_before: raise RuntimeError(f'production 8642 owner PID changed: before {prod_pid_before}, after {prod_listener_after[0]}')
    if candidate_status_paths(candidate)!=expected_paths: raise RuntimeError('candidate Git status changed during isolated gateway smoke')
    for rel,expected in EXPECTED_CANDIDATE_HASHES.items():
        if sha256(candidate/rel)!=expected: raise RuntimeError(f'candidate source changed during smoke: {rel}')
    print('ISOLATED_GATEWAY_CLEANUP=PASS'); print('PRODUCTION_8642_OWNER_UNCHANGED=PASS'); print('PRODUCTION_WATCHED_STATE_UNCHANGED=PASS'); print('CANDIDATE_SOURCE_UNCHANGED=PASS'); print(f'SCRATCH_ROOT={scratch_root}'); print(f'SCRATCH_LOG={log_path}'); print('ISOLATED_STANDALONE_GATEWAY_CONTRACT=PASS'); print('PRODUCTION_HERMES_MUTATED=false'); print('COMPANION_STATE_MUTATED=false'); print('PRODUCTION_RUNTIME_RESTARTED=false')
    return 0
if __name__=='__main__': raise SystemExit(main())
