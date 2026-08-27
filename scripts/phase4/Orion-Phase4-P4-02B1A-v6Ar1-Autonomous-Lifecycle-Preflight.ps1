[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$CoreContainer = "orion-iai-m5-c"
$DashboardContainer = "orion-iai-dashboard"
$ExpectedCoreId = "ea9fb7afbe6b394373390310a94bcacb21470388d1310a9305c7ef9e6a97b2d7"
$ExpectedCoreStartedAt = "2026-08-26T08:49:00.989990394Z"
$ExpectedDashboardId = "b163bfd69177b03d7104d57a38c4be819e181e98cd540229ecdc912026465da0"
$EvidenceRoot = "E:\Orion-Phase2\P4-02B1A-evidence"
$ProbePrefix = "P4PROBE_JSON="

function Invoke-NativeText {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $FilePath @ArgumentList 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $saved
    }

    $text = @($raw | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    if ($code -ne 0) {
        throw ("Native command failed with exit {0}: {1} {2}{3}{4}" -f
            $code, $FilePath, ($ArgumentList -join " "),
            [Environment]::NewLine, $text)
    }
    return [string]$text
}

function Get-ContainerState {
    param([Parameter(Mandatory = $true)][string]$Name)

    $line = (Invoke-NativeText -FilePath "docker.exe" -ArgumentList @(
        "inspect", "-f",
        "{{.Id}}|{{.State.StartedAt}}|{{.State.Running}}",
        $Name
    )).Trim()

    if ([string]::IsNullOrWhiteSpace($line)) {
        throw ("docker inspect returned no output for {0}." -f $Name)
    }

    $parts = $line -split '\|', 3
    if ($parts.Count -ne 3) {
        throw ("Unexpected docker inspect output for {0}: {1}" -f $Name, $line)
    }

    [pscustomobject]@{
        Id        = $parts[0]
        StartedAt = $parts[1]
        Running   = [System.Convert]::ToBoolean($parts[2])
    }
}

Write-Host "P4-02B1A v6Ar1 - read-only autonomous lifecycle preflight"
Write-Host "Python probe is delivered over stdin to avoid Windows PowerShell 5.1 native argv quoting."
Write-Host "No Brain controls, iai state edits, threshold changes, or container restarts."
Write-Host ""

if (-not (Get-Command "docker.exe" -ErrorAction SilentlyContinue)) {
    throw "Required tool not found: docker.exe"
}
Write-Host "P4_02B1A_V6AR1_TOOLS=PASS"

$core = Get-ContainerState -Name $CoreContainer
$dash = Get-ContainerState -Name $DashboardContainer

if (-not $core.Running -or -not $dash.Running) {
    throw "Accepted core or Brain dashboard container is not running."
}
if ($core.Id -ne $ExpectedCoreId -or $core.StartedAt -ne $ExpectedCoreStartedAt) {
    throw "Accepted core container identity/StartedAt changed since manual-control acceptance."
}
if ($dash.Id -ne $ExpectedDashboardId) {
    throw "Brain dashboard container identity changed since deployment acceptance."
}

Write-Host ("P4_02B1A_V6AR1_ACCEPTED_CONTAINER_ID={0}" -f $core.Id)
Write-Host ("P4_02B1A_V6AR1_ACCEPTED_STARTED_AT={0}" -f $core.StartedAt)
Write-Host ("P4_02B1A_V6AR1_DASHBOARD_CONTAINER_ID={0}" -f $dash.Id)
Write-Host "P4_02B1A_V6AR1_RUNTIME_PREFLIGHT=PASS"

$python = @'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from iai_mcp.daemon_state import load_state as load_daemon_state
from iai_mcp.heartbeat_scanner import HeartbeatScanner
from iai_mcp.idle_detector import IdleDetector
from iai_mcp.lifecycle_state import lifecycle_state_path, load_state as load_lifecycle_state
from iai_mcp.quiet_window import (
    BUCKET_COUNT,
    BUCKET_MINUTES,
    effective_consolidation_window,
    within_window,
)

root_env = os.environ.get("IAI_MCP_STORE")
root = Path(root_env) if root_env else Path.home() / ".iai-mcp"

lc = load_lifecycle_state(lifecycle_state_path(root_env if root_env else None))
ds = load_daemon_state()

window = effective_consolidation_window(
    ds.get("quiet_window"),
    manual=ds.get("quiet_window_manual_override"),
)
start_bucket, duration_buckets = window
now_local = datetime.now().astimezone()
in_window = within_window(window, now_local, now_local.tzinfo)

def hhmm(bucket):
    mins = (int(bucket) % BUCKET_COUNT) * BUCKET_MINUTES
    return f"{mins // 60:02d}:{mins % 60:02d}"

end_bucket = (start_bucket + duration_buckets) % BUCKET_COUNT
now_seconds = now_local.hour * 3600 + now_local.minute * 60 + now_local.second
start_seconds = start_bucket * BUCKET_MINUTES * 60
seconds_until_window = 0 if in_window else (start_seconds - now_seconds) % 86400

if os.environ.get("IAI_MCP_CONSOLIDATION_WINDOW"):
    window_source = "env"
elif isinstance(ds.get("quiet_window_manual_override"), (list, tuple)):
    window_source = "manual"
elif isinstance(ds.get("quiet_window"), (list, tuple)):
    window_source = "learned"
else:
    window_source = "default"

scanner = HeartbeatScanner(root / "wrappers")
fresh_count = scanner.fresh_count()
heartbeat_idle = fresh_count == 0

idle = IdleDetector()
try:
    os_idle_sec, os_idle_source = idle.os_idle_time_sec()
except Exception:
    os_idle_sec, os_idle_source = None, None

try:
    sleep_eligible = bool(idle.sleep_eligible(heartbeat_idle, os_idle_sec))
except Exception:
    sleep_eligible = False

def request_view(key):
    raw = ds.get(key)
    if not isinstance(raw, dict):
        raw = {}
    return {
        "pending": bool(raw.get("pending")),
        "honored_at": raw.get("honored_at"),
    }

transitions = []
logs_dir = root / "logs"
for path in sorted(logs_dir.glob("lifecycle-events-*.jsonl"))[-2:]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        continue
    for line in lines[-500:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("event") != "state_transition":
            continue
        transitions.append({
            "ts": row.get("ts"),
            "from": row.get("from"),
            "to": row.get("to"),
            "trigger": row.get("trigger"),
        })

out = {
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "lifecycle": {
        "current_state": lc.get("current_state"),
        "since_ts": lc.get("since_ts"),
        "last_activity_ts": lc.get("last_activity_ts"),
        "wrapper_event_seq": lc.get("wrapper_event_seq"),
        "shadow_run": lc.get("shadow_run"),
        "crisis_mode": lc.get("crisis_mode"),
    },
    "thresholds": {
        "drowsy_after_sec": float(os.environ.get("LIFECYCLE_DROWSY_AFTER_SEC", "300")),
        "sleep_heartbeat_idle_sec": float(os.environ.get("LIFECYCLE_SLEEP_HEARTBEAT_IDLE_SEC", "1800")),
        "sleep_cycle_cooldown_sec": float(os.environ.get("IAI_MCP_SLEEP_CYCLE_COOLDOWN_SEC", "14400")),
        "lifecycle_tick_sec": 30.0,
    },
    "window": {
        "source": window_source,
        "start": hhmm(start_bucket),
        "end": hhmm(end_bucket),
        "duration_buckets": duration_buckets,
        "in_window_now": bool(in_window),
        "seconds_until_window": int(seconds_until_window),
        "container_local_time": now_local.isoformat(),
        "container_tz": str(now_local.tzinfo),
    },
    "scheduler_paused": bool(ds.get("scheduler_paused")),
    "last_clean_cycle_at": ds.get("last_clean_cycle_at"),
    "requests": {
        "force_rem": request_view("force_rem_request"),
        "user_sleep": request_view("user_sleep_request"),
        "force_wake": request_view("force_wake_request"),
    },
    "idle_inputs": {
        "fresh_wrapper_count": int(fresh_count),
        "heartbeat_idle": bool(heartbeat_idle),
        "os_idle_sec": os_idle_sec,
        "os_idle_source": os_idle_source,
        "sleep_eligible": bool(sleep_eligible),
    },
    "recent_state_transitions": transitions[-12:],
}

print("P4PROBE_JSON=" + json.dumps(out, separators=(",", ":")))
'@

# Feed Python over stdin. Do not pass multiline source through python -c as a
# Windows PowerShell 5.1 native argv element.
$savedPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $rawProbe = $python | & docker.exe exec -i $CoreContainer /opt/iai/venv/bin/python - 2>&1
    $probeExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $savedPreference
}

$probeLines = @($rawProbe | ForEach-Object { [string]$_ })
$probeCombined = $probeLines -join [Environment]::NewLine

if ($probeExit -ne 0) {
    throw ("Python stdin probe failed with exit {0}:{1}{2}" -f
        $probeExit, [Environment]::NewLine, $probeCombined)
}

$probeJsonLine = @(
    $probeLines | Where-Object { $_.StartsWith($ProbePrefix, [System.StringComparison]::Ordinal) }
) | Select-Object -Last 1

if ($null -eq $probeJsonLine -or [string]::IsNullOrWhiteSpace([string]$probeJsonLine)) {
    throw ("Python stdin probe returned no {0} record. Output:{1}{2}" -f
        $ProbePrefix, [Environment]::NewLine, $probeCombined)
}

$probeText = ([string]$probeJsonLine).Substring($ProbePrefix.Length)

try {
    $probe = $probeText | ConvertFrom-Json
}
catch {
    throw ("Could not parse lifecycle probe JSON: {0}" -f $probeText)
}

Write-Host "P4_02B1A_V6AR1_PYTHON_STDIN=PASS"
Write-Host ("P4_02B1A_V6AR1_LIFECYCLE={0}" -f $probe.lifecycle.current_state)
Write-Host ("P4_02B1A_V6AR1_DROWSY_AFTER_SEC={0}" -f $probe.thresholds.drowsy_after_sec)
Write-Host ("P4_02B1A_V6AR1_SLEEP_IDLE_SEC={0}" -f $probe.thresholds.sleep_heartbeat_idle_sec)
Write-Host ("P4_02B1A_V6AR1_SLEEP_COOLDOWN_SEC={0}" -f $probe.thresholds.sleep_cycle_cooldown_sec)
Write-Host ("P4_02B1A_V6AR1_WINDOW_SOURCE={0}" -f $probe.window.source)
Write-Host ("P4_02B1A_V6AR1_WINDOW={0}-{1}" -f $probe.window.start, $probe.window.end)
Write-Host ("P4_02B1A_V6AR1_WINDOW_IN_NOW={0}" -f $probe.window.in_window_now)
Write-Host ("P4_02B1A_V6AR1_SECONDS_UNTIL_WINDOW={0}" -f $probe.window.seconds_until_window)
Write-Host ("P4_02B1A_V6AR1_CONTAINER_LOCAL_TIME={0}" -f $probe.window.container_local_time)
Write-Host ("P4_02B1A_V6AR1_SCHEDULER_PAUSED={0}" -f $probe.scheduler_paused)
Write-Host ("P4_02B1A_V6AR1_LAST_CLEAN_CYCLE_AT={0}" -f $probe.last_clean_cycle_at)
Write-Host ("P4_02B1A_V6AR1_FORCE_REM_PENDING={0}" -f $probe.requests.force_rem.pending)
Write-Host ("P4_02B1A_V6AR1_FORCE_REM_HONORED_AT={0}" -f $probe.requests.force_rem.honored_at)
Write-Host ("P4_02B1A_V6AR1_USER_SLEEP_PENDING={0}" -f $probe.requests.user_sleep.pending)
Write-Host ("P4_02B1A_V6AR1_USER_SLEEP_HONORED_AT={0}" -f $probe.requests.user_sleep.honored_at)
Write-Host ("P4_02B1A_V6AR1_FORCE_WAKE_PENDING={0}" -f $probe.requests.force_wake.pending)
Write-Host ("P4_02B1A_V6AR1_FORCE_WAKE_HONORED_AT={0}" -f $probe.requests.force_wake.honored_at)
Write-Host ("P4_02B1A_V6AR1_FRESH_WRAPPER_COUNT={0}" -f $probe.idle_inputs.fresh_wrapper_count)
Write-Host ("P4_02B1A_V6AR1_HEARTBEAT_IDLE={0}" -f $probe.idle_inputs.heartbeat_idle)
Write-Host ("P4_02B1A_V6AR1_OS_IDLE_SOURCE={0}" -f $probe.idle_inputs.os_idle_source)
Write-Host ("P4_02B1A_V6AR1_OS_IDLE_SEC={0}" -f $probe.idle_inputs.os_idle_sec)
Write-Host ("P4_02B1A_V6AR1_SLEEP_ELIGIBLE={0}" -f $probe.idle_inputs.sleep_eligible)

Write-Host "P4_02B1A_V6AR1_RECENT_TRANSITIONS_BEGIN"
foreach ($t in @($probe.recent_state_transitions)) {
    Write-Host ("P4_02B1A_V6AR1_TRANSITION={0}|{1}->{2}|{3}" -f
        $t.ts, $t.from, $t.to, $t.trigger)
}
Write-Host "P4_02B1A_V6AR1_RECENT_TRANSITIONS_END"

if ([double]$probe.thresholds.drowsy_after_sec -ne 300.0) {
    throw "Production DROWSY threshold is not the accepted 300 seconds; stopping without changing it."
}
if ([double]$probe.thresholds.sleep_heartbeat_idle_sec -ne 1800.0) {
    throw "Production SLEEP idle threshold is not the accepted 1800 seconds; stopping without changing it."
}
if ($probe.scheduler_paused -eq $true) {
    throw "Scheduler is paused; autonomous lifecycle acceptance cannot proceed without an explicit operator decision."
}

if (-not (Test-Path -LiteralPath $EvidenceRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null
}
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$evidencePath = Join-Path $EvidenceRoot ("p4-02b1a-v6ar1-autonomous-preflight-{0}.json" -f $stamp)
$probe | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $evidencePath -Encoding UTF8

Write-Host ("P4_02B1A_V6AR1_EVIDENCE={0}" -f $evidencePath)
Write-Host "P4_02B1A_V6AR1_READ_ONLY=PASS"
Write-Host "P4_02B1A_V6AR1=PASS"
