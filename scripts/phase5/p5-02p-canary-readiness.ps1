param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02P_READINESS")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02P-B is read-only with respect to vault, inbox, recovery, COMPANION
# configuration, and mutation mode. It verifies that the installed P5-02O
# runtime still matches the exact P5-02N-qualified plugin and freezes the
# canary target/hash/file-id/diff contract for a later separately authorized
# production edit.

$QualifiedSourceCommit = "faf8b4787d8e6fb668eb5e9d754104910b4b401a"
$ExpectedBranch = "feature/orion-phase5-p5-02p-production-canary-readiness"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$HermesCheckout = Join-Path $HermesHome "hermes-agent"
$Hermes = Join-Path $HermesCheckout "venv\Scripts\hermes.exe"
$HermesPython = Join-Path $HermesCheckout "venv\Scripts\python.exe"
$Profile = Join-Path $HermesHome "profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginDest = Join-Path $Profile "plugins\orion-vault-actions"
$PluginInit = Join-Path $PluginDest "__init__.py"
$PluginManifest = Join-Path $PluginDest "plugin.yaml"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"
$Verifier = Join-Path $PSScriptRoot "p5-02p-canary-readiness.py"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SourceWorktree = Join-Path $env:TEMP "orion-p5-02p-readiness-$Stamp"

function Test-GatewayHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8642/health" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02P_READINESS") {
    throw "STOP: explicit P5-02P-B readiness authorization token required."
}

foreach ($file in @(
    $Hermes,
    $HermesPython,
    $Config,
    $EnvFile,
    $PluginInit,
    $PluginManifest,
    $Verifier
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}
if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) {
    throw "STOP: accepted production recovery root missing."
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; P5-02P-B requires manual-off."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02P readiness branch is not checked out."
}

$CommitObject = $QualifiedSourceCommit + "^{commit}"
& git -C $Repo cat-file -e $CommitObject
if ($LASTEXITCODE -ne 0) {
    throw "STOP: exact P5-02N qualified source commit is unavailable locally."
}

if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config hash differs from P5-02O accepted baseline."
}

foreach ($name in @(
    "ORION_P5_PRODUCTION_RECOVERY_ROOT",
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)) {
    if (-not [string]::IsNullOrWhiteSpace(
        [Environment]::GetEnvironmentVariable($name, "Process")
    )) {
        throw "STOP: unexpected ambient Phase 5 setting present: $name"
    }
}

try {
    & git -C $Repo worktree add --detach $SourceWorktree $QualifiedSourceCommit
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: could not create exact qualified-source worktree."
    }

    $SourcePlugin = Join-Path $SourceWorktree "hermes_plugins\orion-vault-actions"
    $SourceInit = Join-Path $SourcePlugin "__init__.py"
    $SourceManifest = Join-Path $SourcePlugin "plugin.yaml"

    $InstalledInitHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
    $SourceInitHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceInit).Hash
    if ($InstalledInitHash -ne $SourceInitHash) {
        throw "STOP: installed Orion plugin code differs from qualified P5-02N source."
    }

    $InstalledManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash
    $SourceManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceManifest).Hash
    if ($InstalledManifestHash -ne $SourceManifestHash) {
        throw "STOP: installed Orion plugin manifest differs from qualified P5-02N source."
    }

    & $Hermes -p companion plugins doctor $PluginDest --ci
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: installed-location plugin doctor failed."
    }

    Write-Host "P5_02P_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02P_INSTALLED_PLUGIN_DOCTOR=PASS"
    Write-Host "P5_02P_HERMES_MANUAL_OFF=true"

    & $HermesPython $Verifier $Profile $PluginDest $RecoveryRoot
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02P canary readiness verifier failed."
    }

    if (Test-GatewayHealth) {
        throw "STOP: P5-02P-B unexpectedly started Hermes."
    }

    Write-Host "P5_02P_READINESS_WRAPPER=PASS"
    Write-Host "P5_02P_MUTATION_INVOCATION=false"
    Write-Host "HERMES_MANUAL_OFF=true"
}
finally {
    if (Test-Path -LiteralPath $SourceWorktree) {
        & git -C $Repo worktree remove --force $SourceWorktree | Out-Null
    }
}
