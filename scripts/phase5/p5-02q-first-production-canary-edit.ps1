param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02Q_EXACT_CANARY_EDIT")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02Q performs exactly one authorized production mutation:
# edit C:\Personal\Me\_Orion-P5-Canary.md from the frozen "before" bytes to
# the frozen "after" bytes through the installed registered Orion apply tool.
#
# The mutation mode exists only inside the child Python process, immediately
# around the one registered apply dispatch. This wrapper never persists it,
# never starts the Hermes gateway, and never auto-restores/deletes recovery
# evidence on failure.

$QualifiedSourceCommit = "faf8b4787d8e6fb668eb5e9d754104910b4b401a"
$ExpectedBranch = "feature/orion-phase5-p5-02q-first-production-canary-edit"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedBeforeHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"
$ExpectedAfterHash = "86E94184EF6FF2A80F5CDFA04749C42328079E029D153D3A23D42EAB05059E19"

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
$Target = "C:\Personal\Me\_Orion-P5-Canary.md"
$Runner = Join-Path $PSScriptRoot "p5-02q-first-production-canary-edit.py"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SourceWorktree = Join-Path $env:TEMP "orion-p5-02q-source-$Stamp"

function Test-GatewayHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8642/health" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02Q_EXACT_CANARY_EDIT") {
    throw "STOP: exact P5-02Q authorization token required."
}

foreach ($file in @(
    $Hermes,
    $HermesPython,
    $Config,
    $EnvFile,
    $PluginInit,
    $PluginManifest,
    $Target,
    $Runner
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}
if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) {
    throw "STOP: production recovery root missing."
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; P5-02Q requires manual-off baseline."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02Q branch is not checked out."
}

$CommitObject = $QualifiedSourceCommit + "^{commit}"
& git -C $Repo cat-file -e $CommitObject
if ($LASTEXITCODE -ne 0) {
    throw "STOP: exact P5-02N qualified source commit is unavailable locally."
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
        throw "STOP: unexpected ambient Phase 5 process setting present: $name"
    }
}

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$EnvBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
$PluginInitBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
$PluginManifestBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash
$CanaryBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash
$RecoveryCountBefore = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count

if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted P5-02O baseline."
}
if ($CanaryBefore -ne $ExpectedBeforeHash) {
    throw "STOP: production canary before hash differs from frozen P5-02Q contract."
}
if ($RecoveryCountBefore -ne 0) {
    throw "STOP: production recovery inventory is not empty before P5-02Q."
}

try {
    & git -C $Repo worktree add --detach $SourceWorktree $QualifiedSourceCommit
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: could not create exact qualified-source worktree."
    }

    $SourcePlugin = Join-Path $SourceWorktree "hermes_plugins\orion-vault-actions"
    $SourceInit = Join-Path $SourcePlugin "__init__.py"
    $SourceManifest = Join-Path $SourcePlugin "plugin.yaml"

    if (
        $PluginInitBefore -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceInit).Hash
    ) {
        throw "STOP: installed Orion plugin code differs from qualified P5-02N source."
    }
    if (
        $PluginManifestBefore -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceManifest).Hash
    ) {
        throw "STOP: installed Orion plugin manifest differs from qualified P5-02N source."
    }

    & $Hermes -p companion plugins doctor $PluginDest --ci
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: installed-location plugin doctor failed."
    }

    & $HermesPython -m py_compile $Runner
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02Q runner compile check failed."
    }

    Write-Host "P5_02Q_PRECHECK=PASS"
    Write-Host "P5_02Q_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02Q_INSTALLED_PLUGIN_DOCTOR=PASS"
    Write-Host "P5_02Q_RUNNER_COMPILE=PASS"
    Write-Host "P5_02Q_CANARY_BEFORE_SHA256=$CanaryBefore"
    Write-Host "P5_02Q_PRODUCTION_RECOVERY_COUNT_BEFORE=0"
    Write-Host "P5_02Q_MUTATION_MODE_PERSISTED=false"
    Write-Host "P5_02Q_HERMES_MANUAL_OFF=true"
    Write-Host ""
    Write-Host "The child process will show exactly one Orion production approval prompt."
    Write-Host "Verify the target/diff and choose ONCE only."
    Write-Host "Any other choice must fail closed."
    Write-Host ""

    & $HermesPython $Runner $Profile $PluginDest $RecoveryRoot
    $ChildExit = $LASTEXITCODE

    $CanaryAfterObserved = if (Test-Path -LiteralPath $Target -PathType Leaf) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash
    } else {
        "MISSING"
    }
    $RecoveryCountAfterObserved = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count

    Write-Host "P5_02Q_PARENT_CHILD_EXIT=$ChildExit"
    Write-Host "P5_02Q_PARENT_CANARY_SHA256=$CanaryAfterObserved"
    Write-Host "P5_02Q_PARENT_RECOVERY_COUNT=$RecoveryCountAfterObserved"
    Write-Host "P5_02Q_PARENT_AUTOMATIC_RESTORE=false"

    if (Test-GatewayHealth) {
        throw "STOP: P5-02Q unexpectedly started Hermes gateway."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: P5-02Q changed COMPANION config."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: P5-02Q changed COMPANION .env."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -ne $PluginInitBefore) {
        throw "STOP: P5-02Q changed installed plugin code."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash -ne $PluginManifestBefore) {
        throw "STOP: P5-02Q changed installed plugin manifest."
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
            throw "STOP: P5-02Q leaked a Phase 5 setting into the parent process: $name"
        }
    }

    Write-Host "P5_02Q_CONFIG_UNCHANGED=true"
    Write-Host "P5_02Q_ENV_UNCHANGED=true"
    Write-Host "P5_02Q_INSTALLED_PLUGIN_UNCHANGED=true"
    Write-Host "P5_02Q_PARENT_MUTATION_MODE_ABSENT=true"
    Write-Host "HERMES_MANUAL_OFF=true"

    if ($ChildExit -ne 0) {
        Write-Host "P5_02Q_GATE_RESULT=FAIL_PRESERVE_RECOVERY_EVIDENCE"
        throw "STOP: P5-02Q child reported failure. Do not edit/delete the canary or recovery directory; preserve state for inspection."
    }

    if ($CanaryAfterObserved -ne $ExpectedAfterHash) {
        throw "STOP: P5-02Q child succeeded but parent after-hash verification failed."
    }
    if ($RecoveryCountAfterObserved -ne 1) {
        throw "STOP: P5-02Q child succeeded but parent recovery count is not exactly 1."
    }

    Write-Host "P5_02Q_PARENT_AFTER_HASH_MATCH=true"
    Write-Host "P5_02Q_PARENT_RECOVERY_COUNT_MATCH=true"
    Write-Host "P5_02Q_GATE_RESULT=PASS"
}
finally {
    if (Test-Path -LiteralPath $SourceWorktree) {
        & git -C $Repo worktree remove --force $SourceWorktree | Out-Null
    }
}
