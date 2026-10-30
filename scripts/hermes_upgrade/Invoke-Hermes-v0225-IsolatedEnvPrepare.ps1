[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$CandidateRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedReleaseHead = "bf0203a794a07aac3ff764972ab9087baa4e4f4e"
$ExpectedInstalledHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"

$ExpectedCandidateHashes = [ordered]@{
    "agent/monitoring/cron_health.py" = "d5fd17bb5fdefb3c9e197b3633da322c70fa2f3d84a775b6be69c4e7a7d30b08"
    "cron/error_classification.py" = "86c4a839152e7188c2e71a290ed953d32b24c050b7bf96df8cbd59c9a8bafd39"
    "cron/executions.py" = "639875c57c153df7cbd4782cef802bc93d2b79fdf14da7b9bd090f8877e86a91"
    "cron/jobs.py" = "eb64e1f6ccdc7fb158f53f373a1b61f60ae6888be274f0557e1d90be0bc4fe3a"
    "gateway/platforms/api_server.py" = "fc376aec9d0812260a279efa89978ff934da902db00c3cce4887e68fb10038d1"
}

$ExpectedInstalledStatus = @(
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

function Get-NativeSingleLine {
    param(
        [Parameter(Mandatory=$true)][scriptblock]$Command,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $Lines = @(& $Command)
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "STOP: $Label failed with exit code $ExitCode."
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

function Get-GitStatusLines {
    param([Parameter(Mandatory=$true)][string]$Root)

    $Lines = @(& git -C $Root status --porcelain=v1)
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "STOP: git status failed for $Root with exit code $ExitCode."
    }
    return $Lines
}

function Assert-LinesEqual {
    param(
        [Parameter(Mandatory=$true)][string[]]$Actual,
        [Parameter(Mandatory=$true)][string[]]$Expected,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $ActualSorted = @($Actual | Sort-Object)
    $ExpectedSorted = @($Expected | Sort-Object)
    if (($ActualSorted -join "`n") -ne ($ExpectedSorted -join "`n")) {
        throw "STOP: $Label mismatch. Actual: $($ActualSorted -join ' || ')"
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory=$true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-FileHash {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Expected,
        [Parameter(Mandatory=$true)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "STOP: $Label file missing: $Path"
    }
    $Observed = Get-Sha256 $Path
    if ($Observed -ne $Expected) {
        throw "STOP: $Label SHA-256 mismatch. Expected $Expected; observed $Observed"
    }
}

Write-Host "=================================================="
Write-Host "HERMES v0.22.5 ISOLATED PYTHON 3.14 ENV PREP"
Write-Host "PRODUCTION MUTATION AUTHORIZED=false"
Write-Host "=================================================="

$CandidateRoot = (Resolve-Path -LiteralPath $CandidateRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $CandidateRoot ".git"))) {
    throw "STOP: candidate root is not a Git checkout: $CandidateRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $HermesRoot ".git"))) {
    throw "STOP: installed Hermes checkout missing: $HermesRoot"
}

Write-Host ""
Write-Host "=== VERIFY QUALIFIED SOURCE CANDIDATE ==="
$CandidateHead = Get-NativeSingleLine -Label "candidate HEAD" -Command {
    & git -C $CandidateRoot rev-parse HEAD
}
if ($CandidateHead -ne $ExpectedReleaseHead) {
    throw "STOP: candidate HEAD drift. Expected $ExpectedReleaseHead; observed $CandidateHead"
}

$CandidateStatusBefore = @(Get-GitStatusLines $CandidateRoot)
$CandidatePaths = @(
    $CandidateStatusBefore |
    ForEach-Object {
        $Line = [string]$_
        if ($Line.Length -lt 4) {
            throw "STOP: malformed candidate porcelain record: $Line"
        }
        $Line.Substring(3)
    } |
    Sort-Object
)
$ExpectedPaths = @($ExpectedCandidateHashes.Keys | Sort-Object)
Assert-LinesEqual -Actual $CandidatePaths -Expected $ExpectedPaths -Label "candidate changed path scope"

foreach ($Rel in $ExpectedCandidateHashes.Keys) {
    Assert-FileHash `
        -Path (Join-Path $CandidateRoot $Rel) `
        -Expected $ExpectedCandidateHashes[$Rel] `
        -Label "candidate $Rel"
}
Write-Host "QUALIFIED_CANDIDATE_IDENTITY=PASS"

Write-Host ""
Write-Host "=== VERIFY INSTALLED HERMES BASELINE ==="
$InstalledHeadBefore = Get-NativeSingleLine -Label "installed Hermes HEAD" -Command {
    & git -C $HermesRoot rev-parse HEAD
}
if ($InstalledHeadBefore -ne $ExpectedInstalledHead) {
    throw "STOP: installed Hermes HEAD drift. Expected $ExpectedInstalledHead; observed $InstalledHeadBefore"
}
$InstalledStatusBefore = @(Get-GitStatusLines $HermesRoot)
Assert-LinesEqual -Actual $InstalledStatusBefore -Expected $ExpectedInstalledStatus -Label "installed Hermes status"
Write-Host "INSTALLED_HERMES_BASELINE=PASS"

$Arch = if ($env:PROCESSOR_ARCHITEW6432) {
    [string]$env:PROCESSOR_ARCHITEW6432
}
else {
    [string]$env:PROCESSOR_ARCHITECTURE
}
$Arch = $Arch.ToUpperInvariant()

switch ($Arch) {
    "AMD64" {
        $PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.14.9+20261021-x86_64-pc-windows-msvc-install_only.tar.gz"
        $PythonSha = "60739023ce2d9dee1dfde665c73bc61735cd8ecc5e0277345f1dc0ba6c0fc9ba"
        $UvUrl = "https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-pc-windows-msvc.zip"
        $UvSha = "a38b8d1902b7cfbc76b423ba1bb456f623f42064cdc72628b6075b89afd1019a"
    }
    "ARM64" {
        $PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.14.9+20261021-aarch64-pc-windows-msvc-install_only.tar.gz"
        $PythonSha = "b7af5a4655fcf919f00ef9426f9737637de73062bf9953cc0c13e50e516f282a"
        $UvUrl = "https://github.com/astral-sh/uv/releases/download/0.13.5/uv-aarch64-pc-windows-msvc.zip"
        $UvSha = "09f47edf90726084a70f9426f6e3ca4f46e9bf7cbf23b1716ec64d60b055fae3"
    }
    default {
        throw "STOP: unsupported Windows architecture for this gate: $Arch"
    }
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RuntimeRoot = Join-Path $env:TEMP "orion-hermes-v0225-runtime-$Stamp"
$Downloads = Join-Path $RuntimeRoot "downloads"
$PythonExtract = Join-Path $RuntimeRoot "python-dist"
$UvExtract = Join-Path $RuntimeRoot "uv-dist"
$VenvRoot = Join-Path $RuntimeRoot "venv"
$UvCache = Join-Path $RuntimeRoot "uv-cache"

New-Item -ItemType Directory -Path $Downloads -Force | Out-Null
New-Item -ItemType Directory -Path $PythonExtract -Force | Out-Null
New-Item -ItemType Directory -Path $UvExtract -Force | Out-Null
New-Item -ItemType Directory -Path $UvCache -Force | Out-Null

$PythonArchive = Join-Path $Downloads "python-3.14.9-install_only.tar.gz"
$UvArchive = Join-Path $Downloads "uv-0.13.5.zip"

Write-Host ""
Write-Host "=== DOWNLOAD EXACT RELEASE-LOCKED TOOLCHAIN ==="
Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonArchive
Assert-FileHash -Path $PythonArchive -Expected $PythonSha -Label "Python 3.14.9 artifact"
Invoke-WebRequest -Uri $UvUrl -OutFile $UvArchive
Assert-FileHash -Path $UvArchive -Expected $UvSha -Label "uv 0.13.5 artifact"
Write-Host "PYTHON_ARTIFACT_SHA256=PASS"
Write-Host "UV_ARTIFACT_SHA256=PASS"

$Tar = Get-Command "tar.exe" -CommandType Application -ErrorAction SilentlyContinue
if ($null -eq $Tar) {
    throw "STOP: Windows tar.exe is required to extract the release-locked Python artifact."
}

Write-Host ""
Write-Host "=== EXTRACT ISOLATED TOOLCHAIN ==="
& $Tar.Source -xf $PythonArchive -C $PythonExtract
$TarExit = $LASTEXITCODE
if ($TarExit -ne 0) {
    throw "STOP: Python artifact extraction failed with exit code $TarExit."
}
Expand-Archive -LiteralPath $UvArchive -DestinationPath $UvExtract -Force

$PythonCandidates = @(
    Get-ChildItem -LiteralPath $PythonExtract -Filter python.exe -File -Recurse -ErrorAction Stop
)
if ($PythonCandidates.Count -ne 1) {
    throw "STOP: expected exactly one extracted python.exe; observed $($PythonCandidates.Count)."
}
$BootstrapPython = $PythonCandidates[0].FullName

$UvCandidates = @(
    Get-ChildItem -LiteralPath $UvExtract -Filter uv.exe -File -Recurse -ErrorAction Stop
)
if ($UvCandidates.Count -ne 1) {
    throw "STOP: expected exactly one extracted uv.exe; observed $($UvCandidates.Count)."
}
$UvExe = $UvCandidates[0].FullName

$PythonVersion = Get-NativeSingleLine -Label "isolated Python version" -Command {
    & $BootstrapPython -c "import platform; print(platform.python_version())"
}
if ($PythonVersion -ne "3.14.9") {
    throw "STOP: isolated Python version mismatch. Expected 3.14.9; observed $PythonVersion"
}
$UvVersionLine = Get-NativeSingleLine -Label "isolated uv version" -Command {
    & $UvExe --version
}
if ($UvVersionLine -notmatch '^uv 0\.13\.5(?:\s|$)') {
    throw "STOP: isolated uv version mismatch: $UvVersionLine"
}
Write-Host "ISOLATED_PYTHON_VERSION=3.14.9"
Write-Host "ISOLATED_UV_VERSION=0.13.5"

Write-Host ""
Write-Host "=== SYNC v0.22.5 ISOLATED DEPENDENCY ENVIRONMENT ==="
$SavedProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT
$SavedCacheDir = $env:UV_CACHE_DIR
$SavedPythonInstallDir = $env:UV_PYTHON_INSTALL_DIR
try {
    $env:UV_PROJECT_ENVIRONMENT = $VenvRoot
    $env:UV_CACHE_DIR = $UvCache
    $env:UV_PYTHON_INSTALL_DIR = (Join-Path $RuntimeRoot "uv-python-unused")

    & $UvExe sync `
        --project $CandidateRoot `
        --locked `
        --python $BootstrapPython `
        --extra all `
        --extra edge-tts `
        --extra voice
    $SyncExit = $LASTEXITCODE
    if ($SyncExit -ne 0) {
        throw "STOP: isolated uv sync failed with exit code $SyncExit."
    }
}
finally {
    $env:UV_PROJECT_ENVIRONMENT = $SavedProjectEnvironment
    $env:UV_CACHE_DIR = $SavedCacheDir
    $env:UV_PYTHON_INSTALL_DIR = $SavedPythonInstallDir
}

$RuntimePython = Join-Path $VenvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $RuntimePython -PathType Leaf)) {
    throw "STOP: isolated runtime Python missing after uv sync: $RuntimePython"
}

Write-Host ""
Write-Host "=== ISOLATED DEPENDENCY / IMPORT QUALIFICATION ==="
$RuntimeVersion = Get-NativeSingleLine -Label "runtime Python version" -Command {
    & $RuntimePython -c "import platform; print(platform.python_version())"
}
if ($RuntimeVersion -ne "3.14.9") {
    throw "STOP: runtime Python drift. Expected 3.14.9; observed $RuntimeVersion"
}

$EdgeVersion = Get-NativeSingleLine -Label "edge-tts version" -Command {
    & $RuntimePython -c "import edge_tts; print(edge_tts.__version__)"
}
if ($EdgeVersion -ne "7.3.1") {
    throw "STOP: edge-tts version mismatch. Expected 7.3.1; observed $EdgeVersion"
}

$ImportLines = @(& $RuntimePython -c "import aiohttp; import gateway.platforms.api_server; import hermes_cli.web_routers.audio; import cron.executions; import cron.jobs; print('IMPORT_SET=PASS')")
$ImportExit = $LASTEXITCODE
if ($ImportExit -ne 0 -or $ImportLines.Count -ne 1 -or ([string]$ImportLines[0]) -ne "IMPORT_SET=PASS") {
    throw "STOP: isolated Hermes import qualification failed."
}

& $UvExe pip check --python $RuntimePython
$PipCheckExit = $LASTEXITCODE
if ($PipCheckExit -ne 0) {
    throw "STOP: isolated dependency consistency check failed."
}

Write-Host "RUNTIME_PYTHON_VERSION=3.14.9"
Write-Host "RUNTIME_EDGE_TTS_VERSION=7.3.1"
Write-Host "RUNTIME_IMPORT_SET=PASS"
Write-Host "RUNTIME_DEPENDENCY_CHECK=PASS"

Write-Host ""
Write-Host "=== PROVE SOURCE / PRODUCTION UNCHANGED ==="
$CandidateStatusAfter = @(Get-GitStatusLines $CandidateRoot)
Assert-LinesEqual -Actual $CandidateStatusAfter -Expected $CandidateStatusBefore -Label "candidate source post-sync status"
foreach ($Rel in $ExpectedCandidateHashes.Keys) {
    Assert-FileHash `
        -Path (Join-Path $CandidateRoot $Rel) `
        -Expected $ExpectedCandidateHashes[$Rel] `
        -Label "candidate post-sync $Rel"
}

$InstalledHeadAfter = Get-NativeSingleLine -Label "installed Hermes post-prep HEAD" -Command {
    & git -C $HermesRoot rev-parse HEAD
}
$InstalledStatusAfter = @(Get-GitStatusLines $HermesRoot)
if ($InstalledHeadAfter -ne $InstalledHeadBefore) {
    throw "STOP: installed Hermes HEAD changed during isolated environment preparation."
}
Assert-LinesEqual -Actual $InstalledStatusAfter -Expected $InstalledStatusBefore -Label "installed Hermes post-prep status"

Write-Host "CANDIDATE_SOURCE_UNCHANGED=PASS"
Write-Host "INSTALLED_HERMES_UNCHANGED=PASS"

Write-Host ""
Write-Host "=================================================="
Write-Host "HERMES_V0225_ISOLATED_ENV_PREP=PASS"
Write-Host "PRODUCTION_HERMES_MUTATED=false"
Write-Host "COMPANION_STATE_MUTATED=false"
Write-Host "RUNTIME_RESTARTED=false"
Write-Host "ISOLATED_RUNTIME_ROOT=$RuntimeRoot"
Write-Host "ISOLATED_RUNTIME_PYTHON=$RuntimePython"
Write-Host "QUALIFIED_CANDIDATE_ROOT=$CandidateRoot"
Write-Host "NEXT=ISOLATED_PROFILE_AND_GATEWAY_QUALIFICATION"
Write-Host "=================================================="
