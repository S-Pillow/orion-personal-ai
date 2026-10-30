$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedInstalledHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedReleaseHead = "bf0203a794a07aac3ff764972ab9087baa4e4f4e"
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$GatewayPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Transformer = Join-Path $PSScriptRoot "v0225_build_orion_compat_runner.py"
$AudioTransformer = Join-Path $PSScriptRoot "v0225_port_p4_audio.py"

$ExpectedStatus = @(
    " M agent/monitoring/cron_health.py",
    " M cron/executions.py",
    " M cron/jobs.py",
    " M cron/scheduler.py",
    " M gateway/platforms/api_server.py",
    "?? cron/error_classification.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
)

$ExpectedCandidatePaths = @(
    "agent/monitoring/cron_health.py",
    "cron/error_classification.py",
    "cron/executions.py",
    "cron/jobs.py",
    "gateway/platforms/api_server.py"
)

function Get-StatusLines([string]$Root) {
    return @(& git -C $Root status --porcelain=v1)
}

function Get-NativeSingleLine(
    [scriptblock]$Command,
    [string]$Label
) {
    $Lines = @(& $Command)
    $Exit = $LASTEXITCODE
    if ($Exit -ne 0) {
        throw "STOP: $Label failed with exit code $Exit."
    }
    if ($Lines.Count -ne 1) {
        throw "STOP: $Label expected exactly one output line; observed $($Lines.Count)."
    }
    $Value = [string]$Lines[0]
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "STOP: $Label returned an empty line."
    }
    return $Value.Trim()
}

function Assert-LinesEqual([string[]]$Actual, [string[]]$Expected, [string]$Label) {
    $A = @($Actual | Sort-Object)
    $E = @($Expected | Sort-Object)
    if (($A -join "`n") -ne ($E -join "`n")) {
        throw "STOP: $Label mismatch. Actual: $($A -join ' || ')"
    }
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

Write-Host "=================================================="
Write-Host "HERMES v0.22.5 DISPOSABLE MIGRATION CANDIDATE BUILD"
Write-Host "INSTALLED HERMES MUTATION AUTHORIZED=false"
Write-Host "=================================================="

foreach ($Required in @($HermesRoot, $GatewayPython, $Transformer, $AudioTransformer)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        throw "STOP: required input missing: $Required"
    }
}

$InstalledHeadBefore = Get-NativeSingleLine {
    & git -C $HermesRoot rev-parse HEAD
} "installed Hermes HEAD"
if ($InstalledHeadBefore -ne $ExpectedInstalledHead) {
    throw "STOP: installed Hermes HEAD drift. Expected $ExpectedInstalledHead; observed $InstalledHeadBefore"
}
$InstalledStatusBefore = @(Get-StatusLines $HermesRoot)
Assert-LinesEqual $InstalledStatusBefore $ExpectedStatus "installed Hermes pre-build status"

$InstalledHashesBefore = [ordered]@{}
foreach ($Rel in @(
    "agent/monitoring/cron_health.py",
    "cron/executions.py",
    "cron/jobs.py",
    "cron/scheduler.py",
    "gateway/platforms/api_server.py",
    "cron/error_classification.py"
)) {
    $InstalledHashesBefore[$Rel] = Get-Sha256 (Join-Path $HermesRoot $Rel)
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$CandidateRoot = Join-Path $env:TEMP "orion-hermes-v0225-candidate-$Stamp"
$PatchPath = Join-Path $env:TEMP "orion-hermes-v0225-compat-$Stamp.patch"

if (Test-Path -LiteralPath $CandidateRoot) {
    throw "STOP: candidate path already exists: $CandidateRoot"
}

Write-Host ""
Write-Host "=== CLONE EXACT UPSTREAM RELEASE ==="
& git -c core.autocrlf=false clone --quiet --no-checkout `
    "https://github.com/NousResearch/hermes-agent.git" $CandidateRoot
if ($LASTEXITCODE -ne 0) {
    throw "STOP: Hermes disposable clone failed."
}

& git -C $CandidateRoot config core.autocrlf false
if ($LASTEXITCODE -ne 0) {
    throw "STOP: candidate core.autocrlf configuration failed."
}
& git -C $CandidateRoot config core.eol lf
if ($LASTEXITCODE -ne 0) {
    throw "STOP: candidate core.eol configuration failed."
}
& git -C $CandidateRoot checkout --quiet --detach $ExpectedReleaseHead
if ($LASTEXITCODE -ne 0) {
    throw "STOP: exact v0.22.5 release checkout failed."
}

$CandidateHead = Get-NativeSingleLine {
    & git -C $CandidateRoot rev-parse HEAD
} "candidate Hermes HEAD"
if ($CandidateHead -ne $ExpectedReleaseHead) {
    throw "STOP: candidate checkout identity mismatch."
}
if (@(Get-StatusLines $CandidateRoot).Count -ne 0) {
    throw "STOP: exact upstream candidate is not clean before transform."
}

$Tags = @(& git -C $CandidateRoot tag --points-at HEAD)
if ($LASTEXITCODE -ne 0) {
    throw "STOP: candidate tag query failed."
}
if ($Tags -notcontains "v0.22.5") {
    throw "STOP: exact release commit is not tagged v0.22.5 in the clone."
}

Write-Host "UPSTREAM_RELEASE_COMMIT=$CandidateHead"
Write-Host "UPSTREAM_RELEASE_TAG=v0.22.5"
Write-Host "UPSTREAM_RELEASE_IDENTITY=PASS"

Write-Host ""
Write-Host "=== UPSTREAM CAPABILITY OWNERSHIP CHECK ==="
$ApiServerPath = Join-Path $CandidateRoot "gateway\platforms\api_server.py"
$DashboardAudioPath = Join-Path $CandidateRoot "hermes_cli\web_routers\audio.py"
$RunServerPath = Join-Path $CandidateRoot "gateway\platforms\api_server_runs.py"
$PyprojectPath = Join-Path $CandidateRoot "pyproject.toml"
$UvLockPath = Join-Path $CandidateRoot "uv.lock"

foreach ($Path in @($ApiServerPath, $DashboardAudioPath, $RunServerPath, $PyprojectPath, $UvLockPath)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "STOP: required upstream capability source missing: $Path"
    }
}

$ApiServer = Get-Content -LiteralPath $ApiServerPath -Raw
$DashboardAudio = Get-Content -LiteralPath $DashboardAudioPath -Raw
$RunServer = Get-Content -LiteralPath $RunServerPath -Raw
$Pyproject = Get-Content -LiteralPath $PyprojectPath -Raw
$UvLock = Get-Content -LiteralPath $UvLockPath -Raw

if (-not $ApiServer.Contains('"skills_api": True, "audio_api": False, "realtime_voice": False,')) {
    throw "STOP: stock v0.22.5 API-server audio capability ownership changed."
}
foreach ($Marker in @('/api/audio/transcribe', '/api/audio/speak')) {
    if ($ApiServer.Contains($Marker)) {
        throw "STOP: stock v0.22.5 API server unexpectedly exposes audio route marker: $Marker"
    }
    if (-not $DashboardAudio.Contains($Marker)) {
        throw "STOP: stock v0.22.5 dashboard audio implementation missing marker: $Marker"
    }
}
if (-not $ApiServer.Contains('"waiting_for_approval"') -or -not $ApiServer.Contains('"approval.request"')) {
    throw "STOP: upstream API-server approval transport markers missing."
}
if (-not $RunServer.Contains("register_gateway_notify")) {
    throw "STOP: upstream run-scoped approval registration marker missing."
}
if ($Pyproject -notmatch 'edge-tts\s*=\s*\["edge-tts==7\.3\.1"\]') {
    throw "STOP: v0.22.5 pyproject does not pin edge-tts 7.3.1."
}
if ($UvLock -notmatch 'name = "edge-tts"\s+version = "7\.3\.1"') {
    throw "STOP: v0.22.5 lock does not resolve edge-tts 7.3.1."
}
Write-Host "UPSTREAM_API_SERVER_AUDIO_GAP=CONFIRMED"
Write-Host "UPSTREAM_DASHBOARD_AUDIO_IMPLEMENTATION=PASS"
Write-Host "UPSTREAM_NATIVE_APPROVAL_TRANSPORT=PASS"
Write-Host "UPSTREAM_EDGE_TTS_7_3_1=PASS"

Write-Host ""
Write-Host "=== APPLY ORION SURVIVING COMPATIBILITY PORTS ==="
$P6Output = @(& $GatewayPython -B $Transformer --source-root $CandidateRoot)
$P6Exit = $LASTEXITCODE
if ($P6Exit -ne 0) {
    throw "STOP: Orion P6 v0.22.5 compatibility transform failed with exit code $P6Exit."
}
foreach ($Line in $P6Output) {
    if ([string]$Line -ne "RETIRED_P4_AUDIO_PATCH=true") {
        Write-Host $Line
    }
}

$AudioOutput = @(& $GatewayPython -B $AudioTransformer --source-root $CandidateRoot)
$AudioExit = $LASTEXITCODE
if ($AudioExit -ne 0) {
    throw "STOP: Orion P4-04A v0.22.5 audio transform failed with exit code $AudioExit."
}
foreach ($Line in $AudioOutput) {
    Write-Host $Line
}

$CandidateStatus = @(Get-StatusLines $CandidateRoot)
$CandidatePaths = @(
    $CandidateStatus |
    ForEach-Object {
        if ([string]::IsNullOrWhiteSpace([string]$_) -or ([string]$_).Length -lt 4) {
            throw "STOP: malformed candidate git status line: $_"
        }
        ([string]$_).Substring(3)
    } |
    Sort-Object
)
Assert-LinesEqual $CandidatePaths $ExpectedCandidatePaths "candidate changed path scope"

$PatchedApiServer = Get-Content -LiteralPath $ApiServerPath -Raw
foreach ($Marker in @(
    'ORION-HERMES-V0225-P4-04A-AUDIO-GATEWAY-v1',
    '"audio_api": True',
    '("POST", "/api/audio/transcribe", self._handle_audio_transcribe)',
    '("POST", "/api/audio/speak", self._handle_audio_speak)'
)) {
    if (-not $PatchedApiServer.Contains($Marker)) {
        throw "STOP: post-transform API-server audio verification missing: $Marker"
    }
}
Write-Host "ORION_P404A_GATEWAY_AUDIO_PORT=PASS"

Write-Host ""
Write-Host "=== SOURCE COMPILE / DIFF QUALIFICATION ==="
$CompileRoot = Join-Path $CandidateRoot ".orion-compile"
New-Item -ItemType Directory -Path $CompileRoot -Force | Out-Null
try {
    foreach ($Rel in $ExpectedCandidatePaths) {
        $Source = Join-Path $CandidateRoot $Rel
        $Pyc = Join-Path $CompileRoot (($Rel -replace '[\\/]', '_') + ".pyc")
        & $GatewayPython -I -c "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)" $Source $Pyc
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Pyc)) {
            throw "STOP: py_compile failed for $Rel"
        }
    }
}
finally {
    Remove-Item -LiteralPath $CompileRoot -Recurse -Force -ErrorAction SilentlyContinue
}

& git -C $CandidateRoot diff --check
if ($LASTEXITCODE -ne 0) {
    throw "STOP: candidate diff contains whitespace errors."
}

& git -C $CandidateRoot diff --binary --full-index --output=$PatchPath -- `
    agent/monitoring/cron_health.py `
    cron/error_classification.py `
    cron/executions.py `
    cron/jobs.py `
    gateway/platforms/api_server.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $PatchPath)) {
    throw "STOP: failed to generate candidate compatibility patch."
}

$PatchBytes = (Get-Item -LiteralPath $PatchPath).Length
if ($PatchBytes -le 0) {
    throw "STOP: generated compatibility patch is empty."
}

Write-Host "CANDIDATE_PY_COMPILE=PASS"
Write-Host "CANDIDATE_DIFF_CHECK=PASS"
Write-Host "CANDIDATE_CHANGED_SCOPE=$($ExpectedCandidatePaths -join ',')"
Write-Host "CANDIDATE_PATCH_SHA256=$(Get-Sha256 $PatchPath)"
Write-Host "CANDIDATE_PATCH_BYTES=$PatchBytes"

Write-Host ""
Write-Host "=== CANDIDATE SOURCE HASHES ==="
foreach ($Rel in $ExpectedCandidatePaths) {
    Write-Host "CANDIDATE_SHA256=$Rel|$(Get-Sha256 (Join-Path $CandidateRoot $Rel))"
}

Write-Host ""
Write-Host "=== PROVE INSTALLED HERMES UNCHANGED ==="
$InstalledHeadAfter = Get-NativeSingleLine {
    & git -C $HermesRoot rev-parse HEAD
} "installed Hermes post-build HEAD"
$InstalledStatusAfter = @(Get-StatusLines $HermesRoot)
if ($InstalledHeadAfter -ne $InstalledHeadBefore) {
    throw "STOP: installed Hermes HEAD changed during disposable build."
}
Assert-LinesEqual $InstalledStatusAfter $InstalledStatusBefore "installed Hermes post-build status"
foreach ($Rel in $InstalledHashesBefore.Keys) {
    $After = Get-Sha256 (Join-Path $HermesRoot $Rel)
    if ($After -ne $InstalledHashesBefore[$Rel]) {
        throw "STOP: installed Hermes source changed during disposable build: $Rel"
    }
}
Write-Host "INSTALLED_HERMES_UNCHANGED=PASS"

Write-Host ""
Write-Host "=================================================="
Write-Host "HERMES_V0225_CANDIDATE_BUILD=PASS"
Write-Host "PORT_P404A_AUDIO_GATEWAY=PASS"
Write-Host "INSTALLED_HERMES_MUTATED=false"
Write-Host "COMPANION_STATE_MUTATED=false"
Write-Host "RUNTIME_RESTARTED=false"
Write-Host "CANDIDATE_ROOT=$CandidateRoot"
Write-Host "CANDIDATE_PATCH=$PatchPath"
Write-Host "UPSTREAM_RELEASE_COMMIT=$ExpectedReleaseHead"
Write-Host "=================================================="