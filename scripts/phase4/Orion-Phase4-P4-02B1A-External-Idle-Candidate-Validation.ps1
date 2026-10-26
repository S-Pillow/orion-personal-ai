[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Core = 'orion-iai-m5-c'
$ExpectedCoreId = 'ea9fb7afbe6b394373390310a94bcacb21470388d1310a9305c7ef9e6a97b2d7'
$ExpectedCoreStartedAt = '2026-08-26T08:49:00.989990394Z'
$Image = 'orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix'
$ExpectedImageId = 'sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500'
$IaiRepo = 'E:\Orion-Phase2\iai-personal-memory-engine-source'
$CandidateRef = 'origin/compat/orion-external-idle-signal'
$ExpectedCandidateHead = 'b6d356e67526ed30cc3e7a466597992fc440b800'
$EvidenceRoot = 'E:\Orion-Phase2\P4-02B1A-evidence'
$Stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$EvidenceDir = Join-Path $EvidenceRoot ("p4-02b1a-external-idle-candidate-{0}" -f $Stamp)
$CandidateDir = Join-Path $EvidenceDir 'candidate'
$CandidatePyPath = Join-Path $CandidateDir 'idle_detector.py'
$HostIdlePath = Join-Path $EvidenceDir 'host-idle.json'
$RunOutputPath = Join-Path $EvidenceDir 'candidate-output.txt'

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$NativeArgs,
        [AllowNull()][string]$InputText = $null
    )

    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($null -eq $InputText) {
            $raw = @(& $FilePath @NativeArgs 2>&1)
        }
        else {
            $raw = @($InputText | & $FilePath @NativeArgs 2>&1)
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $saved
    }

    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        Lines = @($raw | ForEach-Object { [string]$_ })
        Text = (@($raw | ForEach-Object { [string]$_ }) -join [Environment]::NewLine)
    }
}

function Require-NativeSuccess {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)]$Result
    )
    if ($Result.ExitCode -ne 0) {
        throw ("{0} failed with exit {1}: {2}" -f $Label, $Result.ExitCode, $Result.Text)
    }
}

function Get-CoreIdentity {
    $r = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @(
        'inspect', $Core, '--format', '{{.Id}}|{{.State.Running}}|{{.State.StartedAt}}'
    )
    Require-NativeSuccess -Label 'docker inspect accepted core' -Result $r
    $line = $r.Text.Trim()
    $parts = $line.Split('|')
    if ($parts.Count -ne 3) {
        throw ("Unexpected accepted-core inspect shape: {0}" -f $line)
    }
    return [pscustomobject]@{
        Id = [string]$parts[0]
        Running = [string]$parts[1]
        StartedAt = [string]$parts[2]
    }
}

Write-Host 'P4-02B1A external idle candidate validation'
Write-Host 'Disposable/read-only with respect to accepted production runtime.'
Write-Host 'No iai state edits, lifecycle controls, restarts, threshold changes, or external network.'
Write-Host ''

foreach ($required in @('docker.exe', 'git.exe')) {
    if ($null -eq (Get-Command $required -ErrorAction SilentlyContinue)) {
        throw ("Required tool not found: {0}" -f $required)
    }
}
if (-not (Test-Path -LiteralPath $IaiRepo -PathType Container)) {
    throw ("iai fork clone not found: {0}" -f $IaiRepo)
}

$pre = Get-CoreIdentity
if ($pre.Id -ne $ExpectedCoreId -or $pre.Running -ne 'true' -or $pre.StartedAt -ne $ExpectedCoreStartedAt) {
    throw 'Accepted core identity/running state drifted; refusing candidate test.'
}
Write-Host 'P4_02B1A_EXTIDLE_CORE_PREFLIGHT=PASS'

$imageResult = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @('image', 'inspect', $Image, '--format', '{{.Id}}')
Require-NativeSuccess -Label 'inspect accepted image' -Result $imageResult
if ($imageResult.Text.Trim() -ne $ExpectedImageId) {
    throw ("Accepted image ID drift: {0}" -f $imageResult.Text.Trim())
}
Write-Host 'P4_02B1A_EXTIDLE_IMAGE_ID=PASS'

$fetch = Invoke-NativeCapture -FilePath 'git.exe' -NativeArgs @(
    '-C', $IaiRepo, 'fetch', 'origin',
    '+refs/heads/compat/orion-external-idle-signal:refs/remotes/origin/compat/orion-external-idle-signal'
)
Require-NativeSuccess -Label 'fetch iai external-idle branch' -Result $fetch

$head = Invoke-NativeCapture -FilePath 'git.exe' -NativeArgs @('-C', $IaiRepo, 'rev-parse', $CandidateRef)
Require-NativeSuccess -Label 'resolve iai candidate head' -Result $head
$candidateHead = $head.Text.Trim()
if ($candidateHead -ne $ExpectedCandidateHead) {
    throw ("Candidate head mismatch. Expected {0}, got {1}." -f $ExpectedCandidateHead, $candidateHead)
}
Write-Host ("P4_02B1A_EXTIDLE_CANDIDATE_HEAD={0}" -f $candidateHead)

New-Item -ItemType Directory -Force -Path $CandidateDir | Out-Null

$show = Invoke-NativeCapture -FilePath 'git.exe' -NativeArgs @(
    '-C', $IaiRepo, 'show', ("{0}:src/iai_mcp/idle_detector.py" -f $CandidateRef)
)
Require-NativeSuccess -Label 'extract candidate idle_detector.py' -Result $show
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($CandidatePyPath, $show.Text + [Environment]::NewLine, $utf8NoBom)

if ((Get-Item -LiteralPath $CandidatePyPath).Length -lt 5000) {
    throw 'Extracted candidate source is unexpectedly small.'
}
Write-Host 'P4_02B1A_EXTIDLE_CANDIDATE_EXTRACT=PASS'

if ($null -eq ('OrionP4Idle.Native' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace OrionP4Idle
{
    public static class Native
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct LASTINPUTINFO
        {
            public uint cbSize;
            public uint dwTime;
        }

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

        public static uint GetIdleMilliseconds()
        {
            LASTINPUTINFO lii = new LASTINPUTINFO();
            lii.cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO));
            if (!GetLastInputInfo(ref lii))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }
            uint now = unchecked((uint)Environment.TickCount);
            return unchecked(now - lii.dwTime);
        }
    }
}
'@
}

$idleMs = [OrionP4Idle.Native]::GetIdleMilliseconds()
$idleSec = [int64][math]::Floor(([double]$idleMs) / 1000.0)
$observedAt = [DateTimeOffset]::UtcNow.ToString('o')
$hostPayload = [ordered]@{
    schema_version = 1
    idle_sec = $idleSec
    observed_at = $observedAt
    source = 'windows-get-last-input-info'
}
[System.IO.File]::WriteAllText(
    $HostIdlePath,
    ($hostPayload | ConvertTo-Json -Compress),
    $utf8NoBom
)
Write-Host ("P4_02B1A_EXTIDLE_HOST_IDLE_SEC={0}" -f $idleSec)
Write-Host 'P4_02B1A_EXTIDLE_HOST_EVIDENCE=PASS'

$pythonProbe = @'
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

candidate = Path('/candidate/idle_detector.py')
spec = importlib.util.spec_from_file_location('p4_idle_candidate', candidate)
if spec is None or spec.loader is None:
    raise SystemExit('candidate import spec unavailable')
module = importlib.util.module_from_spec(spec)
sys.modules['p4_idle_candidate'] = module
spec.loader.exec_module(module)
IdleDetector = module.IdleDetector

# The mounted Windows observation must be accepted exactly as external idle.
mounted = Path('/evidence/host-idle.json')
raw = json.loads(mounted.read_text(encoding='utf-8'))
os.environ['IAI_MCP_EXTERNAL_IDLE_PATH'] = str(mounted)
value, source = IdleDetector().os_idle_time_sec()
expected = int(raw['idle_sec'])
if source != 'external_idle_file':
    raise SystemExit(f'wrong source: {source!r}')
if value is None or abs(int(value) - expected) > 5:
    raise SystemExit(f'idle value mismatch: candidate={value}, host={expected}')
print(f'P4PROBE_EXTERNAL_SOURCE={source}')
print(f'P4PROBE_EXTERNAL_IDLE_SEC={value}')

# The native 30-minute eligibility threshold must remain unchanged.
if IdleDetector().sleep_eligible(False, os_idle_sec=1799):
    raise SystemExit('sleep eligibility became true below native 1800s threshold')
if not IdleDetector().sleep_eligible(False, os_idle_sec=1800):
    raise SystemExit('native 1800s eligibility threshold no longer accepted')
print('P4PROBE_NATIVE_1800_THRESHOLD=PASS')

# Validate fail-closed parsing/freshness semantics in an isolated temp dir.
def write(path: Path, idle, when=None, schema=1):
    payload = {
        'schema_version': schema,
        'idle_sec': idle,
        'observed_at': when or datetime.now(timezone.utc).isoformat(),
        'source': 'candidate-test',
    }
    path.write_text(json.dumps(payload), encoding='utf-8')

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / 'idle.json'
    os.environ['IAI_MCP_EXTERNAL_IDLE_PATH'] = str(p)

    write(p, 1834)
    if IdleDetector()._external_idle_time_sec() != 1834:
        raise SystemExit('fresh external idle rejected')

    write(p, 0)
    if IdleDetector()._external_idle_time_sec() != 0:
        raise SystemExit('zero active evidence rejected')

    write(p, 7200, (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat())
    if IdleDetector()._external_idle_time_sec() is not None:
        raise SystemExit('stale evidence accepted')

    write(p, 7200, (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat())
    if IdleDetector()._external_idle_time_sec() is not None:
        raise SystemExit('future-invalid evidence accepted')

    for bad in (-1, True, '1800', float('nan'), float('inf')):
        write(p, bad)
        if IdleDetector()._external_idle_time_sec() is not None:
            raise SystemExit(f'invalid idle accepted: {bad!r}')

    write(p, 1800, schema=2)
    if IdleDetector()._external_idle_time_sec() is not None:
        raise SystemExit('wrong schema accepted')

    p.write_text('{not-json', encoding='utf-8')
    if IdleDetector()._external_idle_time_sec() is not None:
        raise SystemExit('malformed JSON accepted')

print('P4PROBE_FAIL_CLOSED_CASES=PASS')
print('P4PROBE_EXTERNAL_IDLE_CANDIDATE=PASS')
'@

$mountCandidate = "type=bind,source=$CandidateDir,target=/candidate,readonly"
$mountEvidence = "type=bind,source=$EvidenceDir,target=/evidence,readonly"
$dockerArgs = @(
    'run', '--rm', '-i', '--network', 'none',
    '--mount', $mountCandidate,
    '--mount', $mountEvidence,
    '--entrypoint', '/opt/iai/venv/bin/python',
    $Image,
    '-'
)
$probe = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs $dockerArgs -InputText $pythonProbe
[System.IO.File]::WriteAllText($RunOutputPath, $probe.Text, $utf8NoBom)
Require-NativeSuccess -Label 'disposable external-idle candidate probe' -Result $probe

if ($probe.Text -notmatch '(?m)^P4PROBE_EXTERNAL_IDLE_CANDIDATE=PASS\r?$') {
    throw 'Disposable candidate probe did not emit PASS sentinel.'
}
$probe.Lines | ForEach-Object { Write-Host $_ }

$post = Get-CoreIdentity
if ($post.Id -ne $pre.Id -or $post.Running -ne 'true' -or $post.StartedAt -ne $pre.StartedAt) {
    throw 'Accepted core changed during disposable candidate validation.'
}
Write-Host 'P4_02B1A_EXTIDLE_CORE_UNCHANGED=PASS'
Write-Host ("P4_02B1A_EXTIDLE_EVIDENCE={0}" -f $EvidenceDir)
Write-Host 'P4_02B1A_EXTIDLE_DISPOSABLE_VALIDATION=PASS'
Write-Host 'P4_02B1A_EXTIDLE=PASS'
