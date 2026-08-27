Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$CanonicalContainerId = '057493d2fcbc'
$BaseCandidateImage = 'orion-iai-feas:v3.0.0-f5e'
$ExpectedBaseCandidateId = 'sha256:a537708bc22526990c0c5de98250603bc7ba398d123cf6ee4f090a3a7fe91a6b'
$TargetIaiVersion = '3.0.8'
$RefreshedCandidateImage = 'orion-iai-feas:v3.0.8-m2'
$IaiCli = '/opt/iai/venv/bin/iai-mcp'

$CompanionConfigHost = 'C:\HermesAgent\data\profiles\companion\config.yaml'
$ExpectedCompanionConfigHash = '2E4E5A9B139AC68CB67D78FEDC166282451D1C8EA53978EBE94A8126C9FD9280'

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmssZ')
$EvidenceDir = "E:\Orion-Phase2\PH2-IAI-M2-V308-$stamp"
$BuildDir = Join-Path $EvidenceDir 'build'
$ContainerName = "orion-iai-m2-v308-$($stamp.ToLowerInvariant())"

New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

$TranscriptPath = Join-Path $EvidenceDir '00-m2-transcript.txt'
$SummaryPath = Join-Path $EvidenceDir '01-m2-summary.txt'
$DockerfilePath = Join-Path $BuildDir 'Dockerfile'

$TranscriptStarted = $false
$ContainerCreated = $false
$ResultCode = 1
$RollbackClass = 'NOT_REACHED'
$RefreshedImageId = 'NOT_BUILT'

function Invoke-DockerCaptured {
    param(
        [Parameter(Mandatory)][string[]]$DockerArguments
    )

    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = & docker.exe @DockerArguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }

    [pscustomobject]@{
        ExitCode = $exitCode
        Text = (($raw | Out-String).Trim())
    }
}

function Invoke-DockerCapturedStdin {
    param(
        [Parameter(Mandatory)][string[]]$DockerArguments,
        [Parameter(Mandatory)][string]$StdinText
    )

    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = $StdinText | & docker.exe @DockerArguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }

    [pscustomobject]@{
        ExitCode = $exitCode
        Text = (($raw | Out-String).Trim())
    }
}

function Require-Docker {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string[]]$DockerArguments
    )

    $result = Invoke-DockerCaptured -DockerArguments $DockerArguments

    Write-Host "=== $Label ==="
    Write-Host "exit=$($result.ExitCode)"
    if ([string]::IsNullOrWhiteSpace($result.Text)) {
        Write-Host '<no output>'
    }
    else {
        Write-Host $result.Text
    }

    if ($result.ExitCode -ne 0) {
        throw "$Label failed with exit $($result.ExitCode)"
    }

    return $result
}

function Require-DockerStdin {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string[]]$DockerArguments,
        [Parameter(Mandatory)][string]$StdinText
    )

    $result = Invoke-DockerCapturedStdin -DockerArguments $DockerArguments -StdinText $StdinText

    Write-Host "=== $Label ==="
    Write-Host "exit=$($result.ExitCode)"
    if ([string]::IsNullOrWhiteSpace($result.Text)) {
        Write-Host '<no output>'
    }
    else {
        Write-Host $result.Text
    }

    if ($result.ExitCode -ne 0) {
        throw "$Label failed with exit $($result.ExitCode)"
    }

    return $result
}

function Require-HostHash {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Expected,
        [Parameter(Mandatory)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing: $Path"
    }

    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    Write-Host "$Label=$actual"

    if ($actual -ne $Expected) {
        throw "$Label mismatch"
    }

    return $actual
}

function Get-GatewaySemanticState {
    param(
        [Parameter(Mandatory)][string]$ServicePath
    )

    $result = Require-Docker -Label "gateway state $ServicePath" -DockerArguments @(
        'exec',$CanonicalContainerId,'/command/s6-svstat',$ServicePath
    )

    if ($result.Text -match '^up \(pid (\d+) pgid (\d+)\)') {
        return [pscustomobject]@{
            State = 'up'
            ProcId = [int]$Matches[1]
            ProcessGroupId = [int]$Matches[2]
            Raw = $result.Text
        }
    }

    if ($result.Text -match '^down ') {
        return [pscustomobject]@{
            State = 'down'
            ProcId = $null
            ProcessGroupId = $null
            Raw = $result.Text
        }
    }

    throw "Unrecognized gateway state: $($result.Text)"
}

try {
    Start-Transcript -LiteralPath $TranscriptPath -Force | Out-Null
    $TranscriptStarted = $true

    Write-Host 'PH2_IAI_M2_V308_START=YES'
    Write-Host "EVIDENCE_DIR=$EvidenceDir"
    Write-Host "TARGET_IAI_VERSION=$TargetIaiVersion"
    Write-Host 'PLAN=REFRESH_PINNED_CANDIDATE_THEN_TEST_UPSTREAM_HERMES_WIRING'
    Write-Host 'CANONICAL_MUTATION=NONE'

    $configEntryHash = Require-HostHash `
        -Path $CompanionConfigHost `
        -Expected $ExpectedCompanionConfigHash `
        -Label 'COMPANION_CONFIG_ENTRY_SHA256'

    $baseIdentity = Require-Docker -Label 'base candidate identity' -DockerArguments @(
        'image','inspect',$BaseCandidateImage,'--format','{{.Id}}'
    )
    if ($baseIdentity.Text.Trim() -ne $ExpectedBaseCandidateId) {
        throw "Base candidate identity mismatch: $($baseIdentity.Text.Trim())"
    }
    Write-Host 'BASE_CANDIDATE_IDENTITY=PASS'

    $defaultEntry = Get-GatewaySemanticState -ServicePath '/run/service/gateway-default'
    $companionEntry = Get-GatewaySemanticState -ServicePath '/run/service/gateway-companion'

    $baseUserProbe = Require-Docker -Label 'base candidate configured user' -DockerArguments @(
        'image','inspect',$BaseCandidateImage,'--format','{{.Config.User}}'
    )
    $baseUser = $baseUserProbe.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($baseUser)) {
        $baseUser = 'root'
    }
    Write-Host "BASE_CONFIG_USER=$baseUser"

    $dockerfileLines = @(
        "FROM $BaseCandidateImage",
        'USER root',
        'ENV PIP_DISABLE_PIP_VERSION_CHECK=1',
        "RUN /opt/iai/venv/bin/python -m pip install --no-cache-dir --upgrade --only-binary=:all: iai-pme==$TargetIaiVersion"
    )
    if ($baseUser -ne 'root' -and $baseUser -ne '0') {
        $dockerfileLines += "USER $baseUser"
    }

    $dockerfileLines | Set-Content -LiteralPath $DockerfilePath -Encoding ASCII
    Write-Host "DOCKERFILE=$DockerfilePath"

    $build = Require-Docker -Label 'build refreshed iai 3.0.8 candidate' -DockerArguments @(
        'build',
        '--file',$DockerfilePath,
        '--tag',$RefreshedCandidateImage,
        $BuildDir
    )
    Write-Host 'REFRESHED_CANDIDATE_BUILD=PASS'
    Write-Host 'BUILD_NETWORK=USED_FOR_PYPI_PACKAGE_RESOLUTION'

    $newIdentity = Require-Docker -Label 'refreshed candidate identity' -DockerArguments @(
        'image','inspect',$RefreshedCandidateImage,'--format','{{.Id}}'
    )
    $RefreshedImageId = $newIdentity.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($RefreshedImageId)) {
        throw 'Refreshed candidate image id was empty'
    }
    if ($RefreshedImageId -eq $ExpectedBaseCandidateId) {
        throw 'Refreshed candidate unexpectedly has the same image id as the 3.0.0 base'
    }
    Write-Host "REFRESHED_CANDIDATE_ID=$RefreshedImageId"

    $versionProbeCode = [string]::Join("`n", @(
        'import importlib.metadata as md',
        'from importlib import resources',
        'import iai_mcp',
        "print('IAI_DIST_VERSION=' + md.version('iai-pme'))",
        "print('IAI_IMPORT_PATH=' + str(iai_mcp.__file__))",
        "hooks=resources.files('iai_mcp') / '_deploy' / 'hooks'",
        "names=('iai-mcp-session-recall.sh','iai-mcp-per-turn-recall.sh','iai-mcp-hermes-recall.sh','iai-mcp-hermes-capture.sh')",
        'for name in names:',
        "    print('HOOK_TEMPLATE_' + name.upper().replace('-','_').replace('.','_') + '=' + ('PRESENT' if (hooks/name).is_file() else 'MISSING'))"
    ))

    $versionProbe = Require-DockerStdin -Label 'verify refreshed package version and Hermes templates' -DockerArguments @(
        'run','--rm','--network','none','-i',
        '--entrypoint','/opt/iai/venv/bin/python',
        $RefreshedCandidateImage,'-'
    ) -StdinText $versionProbeCode

    if ($versionProbe.Text -notmatch '(?m)^IAI_DIST_VERSION=3\.0\.8\r?$') {
        throw 'Refreshed candidate does not report iai-pme 3.0.8'
    }
    if ($versionProbe.Text -match '(?m)^HOOK_TEMPLATE_.+=MISSING\r?$') {
        throw 'Refreshed candidate is missing one or more Hermes hook templates'
    }
    Write-Host 'REFRESHED_PACKAGE_IDENTITY=PASS'

    $pipCheck = Require-Docker -Label 'pip dependency check in refreshed candidate' -DockerArguments @(
        'run','--rm','--network','none',
        '--entrypoint','/opt/iai/venv/bin/python',
        $RefreshedCandidateImage,
        '-m','pip','check'
    )
    Write-Host 'REFRESHED_PIP_CHECK=PASS'

    $helpProbe = Require-Docker -Label 'refreshed capture-hooks Hermes target' -DockerArguments @(
        'run','--rm','--network','none',
        '--entrypoint',$IaiCli,
        $RefreshedCandidateImage,
        'capture-hooks','install','--help'
    )
    if ($helpProbe.Text -notmatch '(?i)hermes') {
        throw 'Refreshed candidate capture-hooks install help does not expose Hermes'
    }
    Write-Host 'REFRESHED_HERMES_TARGET=PASS'

    $create = Require-Docker -Label 'create disposable M2 container' -DockerArguments @(
        'run','-d',
        '--network','none',
        '--name',$ContainerName,
        '--entrypoint','/bin/sh',
        $RefreshedCandidateImage,
        '-c','while :; do sleep 3600; done'
    )
    $ContainerCreated = $true
    Write-Host "M2_CONTAINER_ID=$($create.Text.Trim())"

    $networkProbe = Require-Docker -Label 'verify disposable runtime network' -DockerArguments @(
        'inspect',$ContainerName,'--format','{{.HostConfig.NetworkMode}}'
    )
    if ($networkProbe.Text.Trim() -ne 'none') {
        throw "Disposable M2 runtime network is not none: $($networkProbe.Text.Trim())"
    }
    Write-Host 'TEST_RUNTIME_NETWORK=NONE'

    Require-Docker -Label 'prepare disposable directories' -DockerArguments @(
        'exec',$ContainerName,'mkdir','-p','/tmp/hermes','/tmp/iai-home'
    ) | Out-Null

    Require-Docker -Label 'copy exact COMPANION config into disposable container' -DockerArguments @(
        'cp',$CompanionConfigHost,"${ContainerName}:/tmp/hermes/config.yaml"
    ) | Out-Null

    Require-Docker -Label 'save disposable config rollback baseline' -DockerArguments @(
        'exec',$ContainerName,'cp','/tmp/hermes/config.yaml','/tmp/hermes/config.before'
    ) | Out-Null

    $copyHash = Require-Docker -Label 'disposable config initial hash' -DockerArguments @(
        'exec',$ContainerName,'sha256sum','/tmp/hermes/config.yaml'
    )
    $disposableInitialHash = ($copyHash.Text -split '\s+')[0].ToUpperInvariant()
    if ($disposableInitialHash -ne $ExpectedCompanionConfigHash) {
        throw "Disposable config copy hash mismatch: $disposableInitialHash"
    }
    Write-Host 'DISPOSABLE_CONFIG_COPY=PASS'

    $dbCode = [string]::Join("`n", @(
        'from pathlib import Path',
        'import sqlite3',
        "p=Path('/tmp/hermes/state.db')",
        'conn=sqlite3.connect(p)',
        'conn.execute("CREATE TABLE messages (id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp TEXT)")',
        'conn.execute("INSERT INTO messages VALUES (?,?,?,?,?)", ("1","m2-synthetic","user","M2 synthetic memory fact: the lantern code is cobalt-47.","2026-08-24T05:30:00Z"))',
        'conn.execute("INSERT INTO messages VALUES (?,?,?,?,?)", ("2","m2-synthetic","assistant","Acknowledged the synthetic M2 memory fact.","2026-08-24T05:30:01Z"))',
        'conn.commit()',
        'count=conn.execute("SELECT COUNT(*) FROM messages WHERE session_id=?", ("m2-synthetic",)).fetchone()[0]',
        'conn.close()',
        'print("SYNTHETIC_ROWS=" + str(count))'
    ))

    $dbCreate = Require-DockerStdin -Label 'create synthetic Hermes state.db' -DockerArguments @(
        'exec','-i',$ContainerName,'/usr/bin/python3','-'
    ) -StdinText $dbCode
    if ($dbCreate.Text -notmatch '(?m)^SYNTHETIC_ROWS=2\r?$') {
        throw 'Synthetic Hermes state.db did not contain exactly two rows'
    }
    Write-Host 'SYNTHETIC_STATE_DB=PASS'

    $install1 = Require-Docker -Label 'upstream iai Hermes hook install' -DockerArguments @(
        'exec',$ContainerName,
        'env',
        'HOME=/tmp/iai-home',
        'IAI_MCP_HERMES_HOME=/tmp/hermes',
        $IaiCli,
        'capture-hooks','install','--target','hermes'
    )
    Write-Host 'UPSTREAM_INSTALL=PASS'

    $status = Require-Docker -Label 'upstream iai Hermes hook status' -DockerArguments @(
        'exec',$ContainerName,
        'env',
        'HOME=/tmp/iai-home',
        'IAI_MCP_HERMES_HOME=/tmp/hermes',
        $IaiCli,
        'capture-hooks','status','--target','hermes'
    )
    if ($status.Text -notmatch '(?i)status:\s+ACTIVE') {
        throw 'Upstream Hermes hook status was not ACTIVE after install'
    }
    Write-Host 'UPSTREAM_STATUS_ACTIVE=PASS'

    $install2 = Require-Docker -Label 'upstream iai Hermes hook install idempotence' -DockerArguments @(
        'exec',$ContainerName,
        'env',
        'HOME=/tmp/iai-home',
        'IAI_MCP_HERMES_HOME=/tmp/hermes',
        $IaiCli,
        'capture-hooks','install','--target','hermes'
    )
    Write-Host 'UPSTREAM_INSTALL_IDEMPOTENCE_CALL=PASS'

    $wireCode = [string]::Join("`n", @(
        'from pathlib import Path',
        'import re',
        "p=Path('/tmp/hermes/config.yaml')",
        "t=p.read_text(encoding='utf-8')",
        "print('TOP_LEVEL_HOOKS_COUNT=' + str(len(re.findall(r'(?m)^hooks\s*:', t))))",
        "print('PRE_LLM_CALL_PRESENT=' + ('YES' if 'pre_llm_call' in t else 'NO'))",
        "print('ON_SESSION_END_PRESENT=' + ('YES' if 'on_session_end' in t else 'NO'))",
        "print('HERMES_RECALL_COMMAND_PRESENT=' + ('YES' if 'iai-mcp-hermes-recall.sh' in t else 'NO'))",
        "print('HERMES_CAPTURE_COMMAND_PRESENT=' + ('YES' if 'iai-mcp-hermes-capture.sh' in t else 'NO'))",
        "hooks=Path('/tmp/hermes/agent-hooks')",
        "names=('iai-mcp-session-recall.sh','iai-mcp-per-turn-recall.sh','iai-mcp-hermes-recall.sh','iai-mcp-hermes-capture.sh')",
        'for name in names:',
        "    q=hooks/name",
        "    print('HOOK_' + name.upper().replace('-','_').replace('.','_') + '=' + ('PRESENT' if q.is_file() else 'MISSING'))"
    ))

    $wire = Require-DockerStdin -Label 'verify upstream wiring contract' -DockerArguments @(
        'exec','-i',$ContainerName,'/usr/bin/python3','-'
    ) -StdinText $wireCode

    $wireRequirements = @(
        'TOP_LEVEL_HOOKS_COUNT=1',
        'PRE_LLM_CALL_PRESENT=YES',
        'ON_SESSION_END_PRESENT=YES',
        'HERMES_RECALL_COMMAND_PRESENT=YES',
        'HERMES_CAPTURE_COMMAND_PRESENT=YES'
    )

    foreach ($requirement in $wireRequirements) {
        if ($wire.Text -notmatch "(?m)^$([regex]::Escape($requirement))\r?$") {
            throw "Upstream wiring requirement missing: $requirement"
        }
    }

    if ($wire.Text -match '(?m)^HOOK_.+=MISSING\r?$') {
        throw 'One or more upstream Hermes hook scripts are missing after install'
    }

    Write-Host 'UPSTREAM_WIRING_CONTRACT=PASS'
    Write-Host 'UPSTREAM_INSTALL_IDEMPOTENCE=PASS'

    $recallPayload = @{
        session_id = 'm2-recall-daemon-absent'
        is_first_turn = $true
        cwd = '/tmp'
        user_message = 'M2 synthetic recall probe'
    } | ConvertTo-Json -Compress

    $recallResult = Invoke-DockerCapturedStdin -DockerArguments @(
        'exec','-i',$ContainerName,
        'env',
        'HOME=/tmp/iai-home',
        'IAI_MCP_HERMES_HOME=/tmp/hermes',
        "IAI_MCP_SESSION_RECALL_CLI=$IaiCli",
        'IAI_MCP_RECALL_HOOK_TIMEOUT=2',
        '/bin/bash',
        '/tmp/hermes/agent-hooks/iai-mcp-hermes-recall.sh'
    ) -StdinText $recallPayload

    Write-Host '=== fail-safe recall with daemon absent ==='
    Write-Host "exit=$($recallResult.ExitCode)"
    Write-Host "stdout_chars=$($recallResult.Text.Length)"

    if ($recallResult.ExitCode -ne 0) {
        throw "Recall fail-safe hook returned nonzero exit $($recallResult.ExitCode)"
    }
    if (-not [string]::IsNullOrWhiteSpace($recallResult.Text)) {
        throw 'Recall fail-safe hook emitted context while daemon/cache were absent'
    }
    Write-Host 'RECALL_DAEMON_ABSENT_FAILSAFE=PASS'

    $capturePayload = @{
        session_id = 'm2-synthetic'
        cwd = '/tmp'
    } | ConvertTo-Json -Compress

    $captureFirst = Invoke-DockerCapturedStdin -DockerArguments @(
        'exec','-i',$ContainerName,
        'env',
        'HOME=/tmp/iai-home',
        'IAI_MCP_HERMES_HOME=/tmp/hermes',
        '/bin/bash',
        '/tmp/hermes/agent-hooks/iai-mcp-hermes-capture.sh'
    ) -StdinText $capturePayload

    Write-Host '=== first synthetic Hermes capture ==='
    Write-Host "exit=$($captureFirst.ExitCode)"
    Write-Host "stdout_chars=$($captureFirst.Text.Length)"

    if ($captureFirst.ExitCode -ne 0) {
        throw "First capture hook returned nonzero exit $($captureFirst.ExitCode)"
    }

    $captureInspectCode = [string]::Join("`n", @(
        'from pathlib import Path',
        'import json, stat',
        "root=Path('/tmp/iai-home/.iai-mcp')",
        "deferred=root/'.deferred-captures'",
        "files=sorted(deferred.glob('m2-synthetic.live-*.jsonl')) if deferred.is_dir() else []",
        "print('DEFERRED_FILE_COUNT=' + str(len(files)))",
        'if len(files) != 1: raise SystemExit(3)',
        'p=files[0]',
        "lines=p.read_text(encoding='utf-8').splitlines()",
        "print('DEFERRED_LINE_COUNT=' + str(len(lines)))",
        "print('DEFERRED_BYTES=' + str(p.stat().st_size))",
        "print('DEFERRED_MODE=' + oct(stat.S_IMODE(p.stat().st_mode)))",
        'docs=[json.loads(line) for line in lines]',
        "print('HEADER_KEYS=' + ','.join(sorted(docs[0].keys())))",
        "print('EVENT_COUNT=' + str(len(docs)-1))",
        "event_keys=sorted(set().union(*(d.keys() for d in docs[1:]))) if len(docs)>1 else []",
        "print('EVENT_KEYS=' + ','.join(event_keys))",
        "wm=root/'.capture-state'/'hermes-m2-synthetic.watermark'",
        "print('WATERMARK_PRESENT=' + ('YES' if wm.is_file() else 'NO'))"
    ))

    $captureInspect = Require-DockerStdin -Label 'inspect first capture metadata only' -DockerArguments @(
        'exec','-i',$ContainerName,'/usr/bin/python3','-'
    ) -StdinText $captureInspectCode

    $captureRequirements = @(
        'DEFERRED_FILE_COUNT=1',
        'DEFERRED_LINE_COUNT=3',
        'DEFERRED_MODE=0o600',
        'EVENT_COUNT=2',
        'WATERMARK_PRESENT=YES'
    )

    foreach ($requirement in $captureRequirements) {
        if ($captureInspect.Text -notmatch "(?m)^$([regex]::Escape($requirement))\r?$") {
            throw "Capture metadata requirement missing: $requirement"
        }
    }

    Write-Host 'SYNTHETIC_HERMES_CAPTURE=PASS'

    $captureSecond = Invoke-DockerCapturedStdin -DockerArguments @(
        'exec','-i',$ContainerName,
        'env',
        'HOME=/tmp/iai-home',
        'IAI_MCP_HERMES_HOME=/tmp/hermes',
        '/bin/bash',
        '/tmp/hermes/agent-hooks/iai-mcp-hermes-capture.sh'
    ) -StdinText $capturePayload

    if ($captureSecond.ExitCode -ne 0) {
        throw "Second capture hook returned nonzero exit $($captureSecond.ExitCode)"
    }

    $dedupe = Require-Docker -Label 'verify capture watermark idempotence' -DockerArguments @(
        'exec',$ContainerName,'/bin/sh','-lc',
        'find /tmp/iai-home/.iai-mcp/.deferred-captures -maxdepth 1 -type f -name "m2-synthetic.live-*.jsonl" | wc -l'
    )
    if ($dedupe.Text.Trim() -ne '1') {
        throw "Capture rerun produced duplicate deferred files: $($dedupe.Text.Trim())"
    }
    Write-Host 'CAPTURE_WATERMARK_IDEMPOTENCE=PASS'

    $uninstall = Require-Docker -Label 'upstream iai Hermes hook uninstall' -DockerArguments @(
        'exec',$ContainerName,
        'env',
        'HOME=/tmp/iai-home',
        'IAI_MCP_HERMES_HOME=/tmp/hermes',
        $IaiCli,
        'capture-hooks','uninstall','--target','hermes'
    )
    Write-Host 'UPSTREAM_UNINSTALL=PASS'

    $rollbackProbeCode = [string]::Join("`n", @(
        'from pathlib import Path',
        'import hashlib, re',
        "before=Path('/tmp/hermes/config.before').read_bytes()",
        "after=Path('/tmp/hermes/config.yaml').read_bytes()",
        "print('ROLLBACK_BEFORE_SHA256=' + hashlib.sha256(before).hexdigest())",
        "print('ROLLBACK_AFTER_SHA256=' + hashlib.sha256(after).hexdigest())",
        "if before == after:",
        "    print('ROLLBACK_CLASS=EXACT')",
        "elif before.rstrip(b'\r\n') == after.rstrip(b'\r\n'):",
        "    print('ROLLBACK_CLASS=TRAILING_NEWLINE_ONLY')",
        'else:',
        "    print('ROLLBACK_CLASS=CONTENT_DRIFT')",
        "text=after.decode('utf-8', errors='replace')",
        "print('POST_UNINSTALL_TOP_LEVEL_HOOKS_COUNT=' + str(len(re.findall(r'(?m)^hooks\s*:', text))))",
        "hooks=Path('/tmp/hermes/agent-hooks')",
        "names=('iai-mcp-session-recall.sh','iai-mcp-per-turn-recall.sh','iai-mcp-hermes-recall.sh','iai-mcp-hermes-capture.sh')",
        'for name in names:',
        "    print('POST_UNINSTALL_' + name.upper().replace('-','_').replace('.','_') + '=' + ('PRESENT' if (hooks/name).exists() else 'ABSENT'))"
    ))

    $rollbackProbe = Require-DockerStdin -Label 'verify upstream uninstall rollback' -DockerArguments @(
        'exec','-i',$ContainerName,'/usr/bin/python3','-'
    ) -StdinText $rollbackProbeCode

    $rollbackMatch = [regex]::Match($rollbackProbe.Text,'(?m)^ROLLBACK_CLASS=(.+)\r?$')
    if (-not $rollbackMatch.Success) {
        throw 'Could not extract rollback class'
    }
    $RollbackClass = $rollbackMatch.Groups[1].Value.Trim()

    if ($RollbackClass -eq 'CONTENT_DRIFT') {
        throw 'Upstream uninstall changed disposable config beyond trailing-newline normalization'
    }
    if ($rollbackProbe.Text -notmatch '(?m)^POST_UNINSTALL_TOP_LEVEL_HOOKS_COUNT=0\r?$') {
        throw 'Top-level hooks block remained after upstream uninstall'
    }
    if ($rollbackProbe.Text -match '(?m)^POST_UNINSTALL_.+=PRESENT\r?$') {
        throw 'One or more upstream Hermes hook scripts remained after uninstall'
    }

    Write-Host "DISPOSABLE_CONFIG_ROLLBACK_CLASS=$RollbackClass"
    Write-Host 'UPSTREAM_UNINSTALL_CLEANUP=PASS'

    $configExitHash = Require-HostHash `
        -Path $CompanionConfigHost `
        -Expected $ExpectedCompanionConfigHash `
        -Label 'COMPANION_CONFIG_EXIT_SHA256'

    $baseIdentityExit = Require-Docker -Label 'base candidate identity exit' -DockerArguments @(
        'image','inspect',$BaseCandidateImage,'--format','{{.Id}}'
    )
    if ($baseIdentityExit.Text.Trim() -ne $ExpectedBaseCandidateId) {
        throw 'Base candidate image identity changed'
    }

    $newIdentityExit = Require-Docker -Label 'refreshed candidate identity exit' -DockerArguments @(
        'image','inspect',$RefreshedCandidateImage,'--format','{{.Id}}'
    )
    if ($newIdentityExit.Text.Trim() -ne $RefreshedImageId) {
        throw 'Refreshed candidate image identity changed during M2'
    }

    $defaultExit = Get-GatewaySemanticState -ServicePath '/run/service/gateway-default'
    $companionExit = Get-GatewaySemanticState -ServicePath '/run/service/gateway-companion'

    if ($defaultEntry.State -ne $defaultExit.State) {
        throw 'DEFAULT gateway state changed'
    }
    if ($defaultEntry.State -eq 'up' -and $defaultEntry.ProcId -ne $defaultExit.ProcId) {
        throw "DEFAULT gateway PID changed: entry=$($defaultEntry.ProcId) exit=$($defaultExit.ProcId)"
    }
    if ($companionEntry.State -ne $companionExit.State) {
        throw 'COMPANION gateway state changed'
    }

    $summary = @(
        'PH2_IAI_M2_V308=PASS',
        "IAI_VERSION=$TargetIaiVersion",
        "REFRESHED_CANDIDATE_IMAGE=$RefreshedCandidateImage",
        "REFRESHED_CANDIDATE_ID=$RefreshedImageId",
        'REFRESHED_CANDIDATE_BUILD=PASS',
        'REFRESHED_PACKAGE_IDENTITY=PASS',
        'REFRESHED_PIP_CHECK=PASS',
        'UPSTREAM_IAI_HERMES_INSTALL=PASS',
        'UPSTREAM_STATUS_ACTIVE=PASS',
        'UPSTREAM_INSTALL_IDEMPOTENCE=PASS',
        'UPSTREAM_WIRING_CONTRACT=PASS',
        'RECALL_DAEMON_ABSENT_FAILSAFE=PASS',
        'SYNTHETIC_HERMES_CAPTURE=PASS',
        'CAPTURE_WATERMARK_IDEMPOTENCE=PASS',
        'UPSTREAM_UNINSTALL=PASS',
        'UPSTREAM_UNINSTALL_CLEANUP=PASS',
        "DISPOSABLE_CONFIG_ROLLBACK_CLASS=$RollbackClass",
        'CANONICAL_CONFIG_PRESERVED=PASS',
        'DEFAULT_STATE_AND_PID_PRESERVED=PASS',
        'COMPANION_STATE_PRESERVED=PASS',
        'BASE_CANDIDATE_ID_PRESERVED=PASS',
        'REFRESHED_CANDIDATE_ID_PRESERVED=PASS',
        'BUILD_NETWORK=USED_FOR_PYPI_PACKAGE_RESOLUTION',
        'TEST_RUNTIME_NETWORK=NONE',
        'MODEL_CALLS=NONE',
        'CANONICAL_MUTATION=NONE',
        'REFRESHED_CANDIDATE_RETAINED_FOR_M3=YES',
        "EVIDENCE_DIR=$EvidenceDir",
        ('UTC_RESULT=' + (Get-Date).ToUniversalTime().ToString('o'))
    )

    $summary | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
    $summary | ForEach-Object { Write-Host $_ }

    Write-Host 'PH2_IAI_M2_V308_END=PASS'
    $ResultCode = 0
}
catch {
    $fatal = $_.Exception.Message

    Write-Host 'PH2_IAI_M2_V308=FAIL'
    Write-Host "FATAL=$fatal"

    @(
        'PH2_IAI_M2_V308=FAIL',
        "FATAL=$fatal",
        "REFRESHED_CANDIDATE_ID=$RefreshedImageId",
        "DISPOSABLE_CONFIG_ROLLBACK_CLASS=$RollbackClass",
        'CANONICAL_MUTATION=NONE',
        'MODEL_CALLS=NONE',
        "EVIDENCE_DIR=$EvidenceDir",
        ('UTC_RESULT=' + (Get-Date).ToUniversalTime().ToString('o'))
    ) | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

    $ResultCode = 1
}
finally {
    if ($ContainerCreated) {
        $cleanup = Invoke-DockerCaptured -DockerArguments @('rm','-f',$ContainerName)

        Write-Host '=== disposable cleanup ==='
        Write-Host "exit=$($cleanup.ExitCode)"
        if (-not [string]::IsNullOrWhiteSpace($cleanup.Text)) {
            Write-Host $cleanup.Text
        }

        if ($cleanup.ExitCode -eq 0) {
            Add-Content -LiteralPath $SummaryPath -Value 'DISPOSABLE_CONTAINER_CLEANUP=PASS' -Encoding UTF8
        }
        else {
            Add-Content -LiteralPath $SummaryPath -Value 'DISPOSABLE_CONTAINER_CLEANUP=FAIL' -Encoding UTF8
            $ResultCode = 1
        }
    }

    if ($TranscriptStarted) {
        Stop-Transcript | Out-Null
    }
}

exit $ResultCode

