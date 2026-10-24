from __future__ import annotations
import hashlib, importlib.util, json, os, sys, tempfile, unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('orion_vault_actions_dc02', PLUGIN_DIR / '__init__.py')
plugin = importlib.util.module_from_spec(SPEC); assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin; SPEC.loader.exec_module(plugin)

class FakeContext:
    def __init__(self, responses=()):
        self.tools, self.hooks = {}, {}; self.responses=list(responses); self.mcp_calls=[]
    def register_tool(self, *, name, toolset, schema, handler, **kwargs):
        self.tools[name]={'toolset':toolset,'schema':schema,'handler':handler,'kwargs':kwargs}
    def register_hook(self, name, callback): self.hooks[name]=callback
    def call_mcp(self, server, tool, arguments=None, timeout=30):
        self.mcp_calls.append((server,tool,dict(arguments or {}),timeout))
        if not self.responses: raise AssertionError('unexpected MCP call')
        value=self.responses.pop(0)
        if isinstance(value, BaseException): raise value
        return value

class DC02RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.vault=self.root/'vault'; self.inbox=self.root/'inbox'; self.vault.mkdir(); self.inbox.mkdir()
        self.old_v=os.environ.get('ORION_VAULT_ROOT'); self.old_i=os.environ.get('ORION_INBOX_ROOT')
        os.environ['ORION_VAULT_ROOT']=str(self.vault); os.environ['ORION_INBOX_ROOT']=str(self.inbox)
    def tearDown(self):
        if self.old_v is None: os.environ.pop('ORION_VAULT_ROOT',None)
        else: os.environ['ORION_VAULT_ROOT']=self.old_v
        if self.old_i is None: os.environ.pop('ORION_INBOX_ROOT',None)
        else: os.environ['ORION_INBOX_ROOT']=self.old_i
        self.tmp.cleanup()
    def note(self, rel, text):
        p=self.vault/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8'); return p
    def handler(self, responses):
        ctx=FakeContext(responses); plugin.register(ctx); return ctx,ctx.tools[plugin.RETRIEVE_TOOL]['handler']

    def test_registers_read_only_retrieval_tool_contract(self):
        ctx=FakeContext(); plugin.register(ctx); reg=ctx.tools[plugin.RETRIEVE_TOOL]
        self.assertEqual(reg['toolset'],'orion_vault'); self.assertEqual(reg['schema']['name'],plugin.RETRIEVE_TOOL)
        self.assertEqual(reg['schema']['parameters']['required'],['cue']); self.assertFalse(reg['schema']['parameters']['additionalProperties'])
        self.assertIn('Read-only',reg['schema']['description']); self.assertIn('no vault or memory mutation',reg['schema']['description'])

    def test_retrieval_uses_iai_order_and_current_source_provenance_without_mutation(self):
        a=self.note('Projects/alpha.md','alpha current source\n'); b=self.note('Research/beta.md','beta current source\n')
        before={a:a.read_bytes(),b:b.read_bytes()}
        ctx,h=self.handler([
          {'ok':True,'result':{'hits':[{'record_id':'r-alpha'},{'record_id':'r-beta'}]}},
          {'ok':True,'result':{'hits':[{'id':'r-alpha','tags':[plugin._doc_tag('Projects/alpha.md')]},{'id':'r-beta','tags':[plugin._doc_tag('Research/beta.md')]}]}}
        ])
        r=json.loads(h({'cue':'What do my notes say about alpha?'}))
        self.assertTrue(r['success']); self.assertFalse(r['mutation_performed']); self.assertEqual(r['retrieval_count'],2)
        self.assertEqual([x['source_relative_path'] for x in r['sources']],['Projects/alpha.md','Research/beta.md'])
        self.assertEqual([x['native_recall_rank'] for x in r['sources']],[1,2]); self.assertEqual(r['sources'][0]['content'],before[a].decode('utf-8'))
        self.assertEqual(r['sources'][0]['source_sha256'],hashlib.sha256(before[a]).hexdigest())
        self.assertEqual([x[1] for x in ctx.mcp_calls],[plugin.IAI_RECALL_TOOL,plugin.IAI_TEMPORAL_RECALL_TOOL])
        self.assertEqual(a.read_bytes(),before[a]); self.assertEqual(b.read_bytes(),before[b])

    def test_ambiguous_doc_tag_is_omitted(self):
        a=self.note('A/B.md','nested\n'); b=self.note('A-B.md','flat\n'); tag=plugin._doc_tag('A/B.md'); self.assertEqual(tag,plugin._doc_tag('A-B.md'))
        _,h=self.handler([{'ok':True,'result':{'hits':[{'record_id':'r1'}]}},{'ok':True,'result':{'hits':[{'id':'r1','tags':[tag]}]}}])
        r=json.loads(h({'cue':'collision'})); self.assertTrue(r['success']); self.assertEqual(r['retrieval_count'],0); self.assertEqual(r['sources'],[])
        self.assertEqual(a.read_text(),'nested\n'); self.assertEqual(b.read_text(),'flat\n')

    def test_zero_hits_and_iai_failures_fail_closed(self):
        ctx,h=self.handler([{'ok':True,'result':{'hits':[]}}]); r=json.loads(h({'cue':'none'}))
        self.assertTrue(r['success']); self.assertEqual(r['sources'],[]); self.assertEqual(len(ctx.mcp_calls),1)
        cases=[([{'ok':False}], 'iai_recall_invalid_response'),([RuntimeError('offline')],'iai_recall_unavailable'),([
          {'ok':True,'result':{'hits':[{'record_id':'r1'}]}},{'ok':False}], 'iai_metadata_invalid_response')]
        for responses,err in cases:
            with self.subTest(err=err):
                _,h=self.handler(responses); r=json.loads(h({'cue':'x'})); self.assertFalse(r['success']); self.assertEqual(r['error'],err); self.assertFalse(r['mutation_performed'])

    def test_top_and_excerpt_limits_are_bounded(self):
        hits=[]; meta=[]; paths=[]
        for i in range(6):
            rel=f'Set/note-{i}.md'; p=self.note(rel,f'content-{i}-long'); paths.append(p); rid=f'r{i}'; hits.append({'record_id':rid}); meta.append({'id':rid,'tags':[plugin._doc_tag(rel)]})
        before=[p.read_bytes() for p in paths]; _,h=self.handler([{'ok':True,'result':{'hits':hits}},{'ok':True,'result':{'hits':meta}}])
        r=json.loads(h({'cue':'many','top':999,'max_chars_per_source':3})); self.assertEqual(r['retrieval_count'],5); self.assertEqual([x['content'] for x in r['sources']],['con']*5)
        self.assertTrue(all(x['content_truncated'] for x in r['sources'])); self.assertEqual([p.read_bytes() for p in paths],before)

    def test_empty_cue_rejected_before_mcp(self):
        ctx,h=self.handler([]); r=json.loads(h({'cue':'   '})); self.assertFalse(r['success']); self.assertEqual(r['error'],'cue_required'); self.assertFalse(r['mutation_performed']); self.assertEqual(ctx.mcp_calls,[])

if __name__ == '__main__': unittest.main()
