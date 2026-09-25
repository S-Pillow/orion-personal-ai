param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02V_DELETE_SOURCE_QUALIFICATION")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02V source qualification only.
# It compiles/tests/doctors the protected-delete source candidate and proves the
# accepted P5-02U production state is unchanged. It does not install the 0.3.0
# plugin, enable mutation, delete the vault target, or alter recovery evidence.

$ExpectedBranch = "feature/orion-phase5-p5-02v-protected-delete"
$QualifiedInstalledSourceCommit = "faf8b4787d8e6fb668eb5e9d754104910b4b401a"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedMoveHash = "132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132"
$ExpectedEditCanaryHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"
$ExpectedRecoveryIds = @(
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27",
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f",
    "5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175",
    "8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6"
)

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$SourcePlugin = Join-Path $Repo "hermes_plugins\orion-vault-actions"
$SourceInit = Join-Path $SourcePlugin "__init__.py"
$SourceManifest = Join-Path $SourcePlugin "plugin.yaml"
$SourceTests = Join-Path $SourcePlugin "tests"

$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$HermesCheckout = Join-Path $HermesHome "hermes-agent"
$Hermes = Join-Path $HermesCheckout "venv\Scripts\hermes.exe"
$HermesPython = Join-Path $HermesCheckout "venv\Scripts\python.exe"

$Profile = Join-Path $HermesHome "profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$InstalledPlugin = Join-Path $Profile "plugins\orion-vault-actions"
$InstalledInit = Join-Path $InstalledPlugin "__init__.py"
$InstalledManifest = Join-Path $InstalledPlugin "plugin.yaml"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"

$MoveSource = "C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md"
$MoveTarget = "C:\Personal\Me\_Orion-P5-Move-Canary.md"
$EditCanary = "C:\Personal\Me\_Orion-P5-Canary.md"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$InstalledSourceWorktree = Join-Path $env:TEMP "orion-p5-02v-installed-source-$Stamp"

function Test-GatewayListening {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect("127.0.0.1", 8642, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(2000, $false)) {
            return $false
        }
        try {
            $client.EndConnect($connect)
        }
        catch {
            return $false
        }
        return $client.Connected
    }
    finally {
        $client.Dispose()
    }
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02V_DELETE_SOURCE_QUALIFICATION") {
    throw "STOP: exact P5-02V source-qualification token required."
}

foreach ($file in @(
    $Hermes,
    $HermesPython,
    $Config,
    $EnvFile,
    $InstalledInit,
    $InstalledManifest,
    $SourceInit,
    $SourceManifest,
    $MoveSource,
    $MoveTarget,
    $EditCanary
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}
foreach ($dir in @($RecoveryRoot, $SourceTests)) {
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
        throw "STOP: required directory missing: $dir"
    }
}

if (Test-GatewayListening) {
    throw "STOP: port 8642 is listening; P5-02V source qualification requires Hermes manual-off."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02V branch is not checked out."
}

foreach ($name in @(
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
$InstalledInitBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $InstalledInit).Hash
$InstalledManifestBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $InstalledManifest).Hash
$MoveSourceBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash
$MoveTargetBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveTarget).Hash
$EditCanaryBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash

if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted baseline."
}
if ($MoveSourceBefore -ne $ExpectedMoveHash -or $MoveTargetBefore -ne $ExpectedMoveHash) {
    throw "STOP: P5-02U source/target state differs from accepted frozen hash."
}
if ($EditCanaryBefore -ne $ExpectedEditCanaryHash) {
    throw "STOP: unrelated edit canary differs from accepted restored state."
}

$RecoveryEntriesBefore = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryEntriesBefore.Count -ne 4) {
    throw "STOP: production recovery root must contain exactly four accepted records before P5-02V."
}
if (@($RecoveryEntriesBefore | Where-Object { -not $_.PSIsContainer }).Count -ne 0) {
    throw "STOP: unexpected non-directory entry exists in production recovery root."
}
$RecoveryIdsBefore = @(
    $RecoveryEntriesBefore | Select-Object -ExpandProperty Name
) | Sort-Object
if (($RecoveryIdsBefore -join "|") -ne (($ExpectedRecoveryIds | Sort-Object) -join "|")) {
    throw "STOP: recovery inventory differs from accepted P5-02U state."
}

$ManifestText = [IO.File]::ReadAllText($SourceManifest)
if ($ManifestText -notmatch 'version:\s*"0\.3\.0"') {
    throw "STOP: P5-02V source manifest is not version 0.3.0."
}
if ($ManifestText -notmatch 'orion_vault_preview_delete') {
    throw "STOP: P5-02V source manifest does not expose delete preview."
}

try {
    & git -C $Repo worktree add --detach $InstalledSourceWorktree $QualifiedInstalledSourceCommit
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: could not create exact installed-source comparison worktree."
    }

    $ExpectedInstalledPlugin = Join-Path $InstalledSourceWorktree "hermes_plugins\orion-vault-actions"
    $ExpectedInstalledInit = Join-Path $ExpectedInstalledPlugin "__init__.py"
    $ExpectedInstalledManifest = Join-Path $ExpectedInstalledPlugin "plugin.yaml"

    if (
        $InstalledInitBefore -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $ExpectedInstalledInit).Hash
    ) {
        throw "STOP: live installed plugin code no longer matches accepted P5-02N source."
    }
    if (
        $InstalledManifestBefore -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $ExpectedInstalledManifest).Hash
    ) {
        throw "STOP: live installed plugin manifest no longer matches accepted P5-02N source."
    }

    & $HermesPython -m py_compile $SourceInit
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02V plugin compile failed."
    }

    & $HermesPython -m unittest discover -s $SourceTests -p "test_p5*.py"
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02V Phase 5 source regression suite failed."
    }

    & $Hermes -p companion plugins doctor $SourcePlugin --ci
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02V source plugin doctor failed."
    }

    if (Test-GatewayListening) {
        throw "STOP: source qualification unexpectedly left port 8642 listening."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: source qualification changed COMPANION config."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: source qualification changed COMPANION .env."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $InstalledInit).Hash -ne $InstalledInitBefore) {
        throw "STOP: source qualification changed installed plugin code."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $InstalledManifest).Hash -ne $InstalledManifestBefore) {
        throw "STOP: source qualification changed installed plugin manifest."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash -ne $MoveSourceBefore) {
        throw "STOP: source qualification changed restored move source."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $MoveTarget).Hash -ne $MoveTargetBefore) {
        throw "STOP: source qualification changed retained vault target."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash -ne $EditCanaryBefore) {
        throw "STOP: source qualification changed unrelated edit canary."
    }

    $RecoveryIdsAfter = @(
        Get-ChildItem -LiteralPath $RecoveryRoot -Force | Select-Object -ExpandProperty Name
    ) | Sort-Object
    if (($RecoveryIdsAfter -join "|") -ne ($RecoveryIdsBefore -join "|")) {
        throw "STOP: source qualification changed production recovery inventory."
    }

    Write-Host "P5_02V_SOURCE_QUALIFICATION=PASS"
    Write-Host "P5_02V_SOURCE_PLUGIN_VERSION=0.3.0"
    Write-Host "P5_02V_DELETE_PREVIEW_REGISTERED_IN_SOURCE=true"
    Write-Host "P5_02V_PLUGIN_COMPILE=PASS"
    Write-Host "P5_02V_PHASE5_TESTS=PASS"
    Write-Host "P5_02V_SOURCE_PLUGIN_DOCTOR=PASS"
    Write-Host "P5_02V_LIVE_INSTALLED_PLUGIN_UNCHANGED=true"
    Write-Host "P5_02V_CONFIG_UNCHANGED=true"
    Write-Host "P5_02V_ENV_UNCHANGED=true"
    Write-Host "P5_02V_MOVE_SOURCE_UNCHANGED=true"
    Write-Host "P5_02V_MOVE_TARGET_UNCHANGED=true"
    Write-Host "P5_02V_EDIT_CANARY_UNCHANGED=true"
    Write-Host "P5_02V_PRODUCTION_RECOVERY_COUNT=4"
    Write-Host "P5_02V_MUTATION_INVOCATION=false"
    Write-Host "P5_02V_LIVE_INSTALL_PERFORMED=false"
    Write-Host "HERMES_MANUAL_OFF=true"
}
finally {
    if (Test-Path -LiteralPath $InstalledSourceWorktree) {
        & git -C $Repo worktree remove --force $InstalledSourceWorktree | Out-Null
    }
}
