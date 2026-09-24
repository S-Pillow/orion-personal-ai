param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02R_EXACT_CANARY_RESTORE")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02R restores exactly one accepted P5-02Q canary edit from its committed
# production recovery record. The mutation mode exists only inside the child
# Python process around the one registered apply dispatch.
#
# This wrapper never persists mutation mode, never starts Hermes gateway, and
# never performs an automatic second mutation on failure.

$QualifiedSourceCommit = "faf8b4787d8e6fb668eb5e9d754104910b4b401a"
$ExpectedBranch = "feature/orion-phase5-p5-02r-production-canary-restore"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedCurrentHash = "86E94184EF6FF2A80F5CDFA04749C42328079E029D153D3A23D42EAB05059E19"
$ExpectedRestoredHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"
$OriginRecoveryId = "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"

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
$OriginRecoveryDir = Join-Path $RecoveryRoot $OriginRecoveryId
$Target = "C:\Personal\Me\_Orion-P5-Canary.md"
$Runner = Join-Path $PSScriptRoot "p5-02r-production-canary-restore.py"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SourceWorktree = Join-Path $env:TEMP "orion-p5-02r-source-$Stamp"

function Test-GatewayHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8642/health" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02R_EXACT_CANARY_RESTORE") {
    throw "STOP: exact P5-02R authorization token required."
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
foreach ($dir in @($RecoveryRoot, $OriginRecoveryDir)) {
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
        throw "STOP: required directory missing: $dir"
    }
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; P5-02R requires manual-off baseline."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02R branch is not checked out."
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
    throw "STOP: COMPANION config differs from accepted baseline."
}
if ($CanaryBefore -ne $ExpectedCurrentHash) {
    throw "STOP: canary current hash differs from accepted P5-02Q post-state."
}
if ($RecoveryCountBefore -ne 1) {
    throw "STOP: production recovery inventory must contain exactly the P5-02Q record."
}

$OriginNames = @(
    Get-ChildItem -LiteralPath $OriginRecoveryDir -Force | Select-Object -ExpandProperty Name
) | Sort-Object
if (($OriginNames -join "|") -ne "manifest.json|original.bin|receipt.json") {
    throw "STOP: P5-02Q origin recovery directory entries differ from accepted state."
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
        throw "STOP: P5-02R runner compile check failed."
    }

    Write-Host "P5_02R_PRECHECK=PASS"
    Write-Host "P5_02R_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02R_INSTALLED_PLUGIN_DOCTOR=PASS"
    Write-Host "P5_02R_RUNNER_COMPILE=PASS"
    Write-Host "P5_02R_ORIGIN_RECOVERY_ID=$OriginRecoveryId"
    Write-Host "P5_02R_CANARY_CURRENT_SHA256=$CanaryBefore"
    Write-Host "P5_02R_PRODUCTION_RECOVERY_COUNT_BEFORE=1"
    Write-Host "P5_02R_MUTATION_MODE_PERSISTED=false"
    Write-Host "P5_02R_HERMES_MANUAL_OFF=true"
    Write-Host ""
    Write-Host "The child process will show exactly one Orion production restore approval prompt."
    Write-Host "Verify the recovery id, target, hashes, and reverse diff. Choose ONCE only."
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

    Write-Host "P5_02R_PARENT_CHILD_EXIT=$ChildExit"
    Write-Host "P5_02R_PARENT_CANARY_SHA256=$CanaryAfterObserved"
    Write-Host "P5_02R_PARENT_RECOVERY_COUNT=$RecoveryCountAfterObserved"
    Write-Host "P5_02R_PARENT_AUTOMATIC_FOLLOWUP_MUTATION=false"

    if (Test-GatewayHealth) {
        throw "STOP: P5-02R unexpectedly started Hermes gateway."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: P5-02R changed COMPANION config."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: P5-02R changed COMPANION .env."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -ne $PluginInitBefore) {
        throw "STOP: P5-02R changed installed plugin code."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash -ne $PluginManifestBefore) {
        throw "STOP: P5-02R changed installed plugin manifest."
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
            throw "STOP: P5-02R leaked a Phase 5 setting into the parent process: $name"
        }
    }

    Write-Host "P5_02R_CONFIG_UNCHANGED=true"
    Write-Host "P5_02R_ENV_UNCHANGED=true"
    Write-Host "P5_02R_INSTALLED_PLUGIN_UNCHANGED=true"
    Write-Host "P5_02R_PARENT_MUTATION_MODE_ABSENT=true"
    Write-Host "HERMES_MANUAL_OFF=true"

    if ($ChildExit -ne 0) {
        Write-Host "P5_02R_GATE_RESULT=FAIL_PRESERVE_RECOVERY_EVIDENCE"
        throw "STOP: P5-02R child reported failure. Do not edit/delete the canary or recovery directories; preserve state for inspection."
    }

    if ($CanaryAfterObserved -ne $ExpectedRestoredHash) {
        throw "STOP: P5-02R child succeeded but parent restored-hash verification failed."
    }
    if ($RecoveryCountAfterObserved -ne 2) {
        throw "STOP: P5-02R child succeeded but parent recovery count is not exactly 2."
    }

    Write-Host "P5_02R_PARENT_RESTORED_HASH_MATCH=true"
    Write-Host "P5_02R_PARENT_RECOVERY_COUNT_MATCH=true"
    Write-Host "P5_02R_GATE_RESULT=PASS"
}
finally {
    if (Test-Path -LiteralPath $SourceWorktree) {
        & git -C $Repo worktree remove --force $SourceWorktree | Out-Null
    }
}
