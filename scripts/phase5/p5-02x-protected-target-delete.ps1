param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02X_EXACT_PROTECTED_TARGET_DELETE")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$QualifiedPluginSourceCommit = "211255ff9abfa04101760c7e3358b521a3e530ae"
$ExpectedBranch = "feature/orion-phase5-p5-02x-protected-target-delete"
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

$MoveSource = "C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md"
$MoveTarget = "C:\Personal\Me\_Orion-P5-Move-Canary.md"
$EditCanary = "C:\Personal\Me\_Orion-P5-Canary.md"
$Runner = Join-Path $PSScriptRoot "p5-02x-protected-target-delete.py"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SourceWorktree = Join-Path $env:TEMP "orion-p5-02x-source-$Stamp"

function Test-GatewayListening {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect("127.0.0.1", 8642, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(2000, $false)) { return $false }
        try { $client.EndConnect($connect) } catch { return $false }
        return $client.Connected
    }
    finally { $client.Dispose() }
}

function Get-DirectoryFingerprint {
    param([Parameter(Mandatory = $true)][string]$Path)
    $root = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $rows = @()
    foreach ($item in (Get-ChildItem -LiteralPath $Path -File -Recurse -Force | Sort-Object FullName)) {
        $relative = $item.FullName.Substring($root.Length).TrimStart('\')
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash
        $rows += "$relative|$($item.Length)|$hash"
    }
    return ($rows -join [Environment]::NewLine)
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02X_EXACT_PROTECTED_TARGET_DELETE") {
    throw "STOP: exact P5-02X protected-delete token required."
}

foreach ($file in @(
    $Hermes,$HermesPython,$Config,$EnvFile,$PluginInit,$PluginManifest,
    $MoveSource,$MoveTarget,$EditCanary,$Runner
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}
if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) {
    throw "STOP: production recovery root missing."
}
if (Test-GatewayListening) {
    throw "STOP: port 8642 is listening; P5-02X requires Hermes manual-off baseline."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02X branch is not checked out."
}
& git -C $Repo cat-file -e ($QualifiedPluginSourceCommit + "^{commit}")
if ($LASTEXITCODE -ne 0) {
    throw "STOP: qualified P5-02V plugin source commit unavailable locally."
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

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$EnvBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
$PluginInitBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
$PluginManifestBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash
$MoveSourceBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash
$MoveTargetBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveTarget).Hash
$EditCanaryBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash

if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted baseline."
}
if ($MoveSourceBefore -ne $ExpectedMoveHash -or $MoveTargetBefore -ne $ExpectedMoveHash) {
    throw "STOP: P5-02W move source/target state differs from frozen hash."
}
if ($EditCanaryBefore -ne $ExpectedEditCanaryHash) {
    throw "STOP: unrelated edit canary differs from accepted restored state."
}

$RecoveryEntriesBefore = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryEntriesBefore.Count -ne 4) {
    throw "STOP: expected exactly four accepted recovery records before P5-02X."
}
if (@($RecoveryEntriesBefore | Where-Object { -not $_.PSIsContainer }).Count -ne 0) {
    throw "STOP: unexpected non-directory entry exists in recovery root."
}
$RecoveryIdsBefore = @(
    $RecoveryEntriesBefore | Select-Object -ExpandProperty Name
) | Sort-Object
if (($RecoveryIdsBefore -join "|") -ne (($ExpectedRecoveryIds | Sort-Object) -join "|")) {
    throw "STOP: recovery ID set differs from accepted P5-02U/P5-02W state."
}

$RecoveryFingerprints = @{}
foreach ($recoveryId in $ExpectedRecoveryIds) {
    $recoveryPath = Join-Path $RecoveryRoot $recoveryId
    if (-not (Test-Path -LiteralPath $recoveryPath -PathType Container)) {
        throw "STOP: accepted recovery directory missing: $recoveryId"
    }
    $RecoveryFingerprints[$recoveryId] = Get-DirectoryFingerprint -Path $recoveryPath
}

try {
    & git -C $Repo worktree add --detach $SourceWorktree $QualifiedPluginSourceCommit
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: could not create qualified-plugin source worktree."
    }

    $SourcePlugin = Join-Path $SourceWorktree "hermes_plugins\orion-vault-actions"
    $SourceInit = Join-Path $SourcePlugin "__init__.py"
    $SourceManifest = Join-Path $SourcePlugin "plugin.yaml"

    if ($PluginInitBefore -ne (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceInit).Hash) {
        throw "STOP: installed plugin code differs from P5-02V-qualified source."
    }
    if ($PluginManifestBefore -ne (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceManifest).Hash) {
        throw "STOP: installed plugin manifest differs from P5-02V-qualified source."
    }

    & $Hermes -p companion plugins doctor $PluginDest --ci
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: installed-location plugin doctor failed."
    }
    & $HermesPython -m py_compile $Runner
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02X runner compile failed."
    }

    Write-Host "P5_02X_PRECHECK=PASS"
    Write-Host "P5_02X_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02X_INSTALLED_PLUGIN_VERSION=0.3.0"
    Write-Host "P5_02X_INSTALLED_PLUGIN_DOCTOR=PASS"
    Write-Host "P5_02X_RUNNER_COMPILE=PASS"
    Write-Host "P5_02X_SOURCE_SHA256=$MoveSourceBefore"
    Write-Host "P5_02X_TARGET_SHA256=$MoveTargetBefore"
    Write-Host "P5_02X_TARGET_STATE_BEFORE=present"
    Write-Host "P5_02X_PRODUCTION_RECOVERY_COUNT_BEFORE=4"
    Write-Host "P5_02X_MUTATION_MODE_PERSISTED=false"
    Write-Host "P5_02X_HERMES_MANUAL_OFF=true"
    Write-Host ""
    Write-Host "The child process will show exactly one Orion protected-delete approval prompt."
    Write-Host "Verify the exact vault target, SHA-256, Windows file ID, and full deletion diff."
    Write-Host "Choose ONCE only. Any other choice must fail closed."
    Write-Host ""

    & $HermesPython $Runner $Profile $PluginDest $RecoveryRoot
    $ChildExit = $LASTEXITCODE

    $SourceHashAfter = if (Test-Path -LiteralPath $MoveSource -PathType Leaf) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash
    } else {
        "MISSING"
    }
    $TargetStateAfter = if (Test-Path -LiteralPath $MoveTarget) {
        "present"
    } else {
        "absent"
    }
    $RecoveryEntriesAfter = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)

    Write-Host "P5_02X_PARENT_CHILD_EXIT=$ChildExit"
    Write-Host "P5_02X_PARENT_SOURCE_SHA256=$SourceHashAfter"
    Write-Host "P5_02X_PARENT_TARGET_STATE=$TargetStateAfter"
    Write-Host "P5_02X_PARENT_RECOVERY_COUNT=$($RecoveryEntriesAfter.Count)"
    Write-Host "P5_02X_PARENT_AUTOMATIC_TARGET_RESTORE=false"
    Write-Host "P5_02X_PARENT_AUTOMATIC_RECOVERY_CLEANUP=false"

    if (Test-GatewayListening) {
        throw "STOP: P5-02X unexpectedly left port 8642 listening."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: P5-02X changed COMPANION config."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: P5-02X changed COMPANION .env."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -ne $PluginInitBefore) {
        throw "STOP: P5-02X changed installed plugin code."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash -ne $PluginManifestBefore) {
        throw "STOP: P5-02X changed installed plugin manifest."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash -ne $EditCanaryBefore) {
        throw "STOP: P5-02X changed unrelated edit canary."
    }
    foreach ($recoveryId in $ExpectedRecoveryIds) {
        $recoveryPath = Join-Path $RecoveryRoot $recoveryId
        if (-not (Test-Path -LiteralPath $recoveryPath -PathType Container)) {
            throw "STOP: P5-02X removed an accepted historical recovery record."
        }
        if ((Get-DirectoryFingerprint -Path $recoveryPath) -ne $RecoveryFingerprints[$recoveryId]) {
            throw "STOP: P5-02X changed historical recovery evidence: $recoveryId"
        }
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
            throw "STOP: P5-02X leaked Phase 5 state into parent process: $name"
        }
    }

    Write-Host "P5_02X_CONFIG_UNCHANGED=true"
    Write-Host "P5_02X_ENV_UNCHANGED=true"
    Write-Host "P5_02X_INSTALLED_PLUGIN_UNCHANGED=true"
    Write-Host "P5_02X_EDIT_CANARY_UNCHANGED=true"
    Write-Host "P5_02X_HISTORICAL_RECOVERY_EVIDENCE_UNCHANGED=true"
    Write-Host "P5_02X_PARENT_MUTATION_MODE_ABSENT=true"
    Write-Host "HERMES_MANUAL_OFF=true"

    if ($ChildExit -ne 0) {
        Write-Host "P5_02X_GATE_RESULT=FAIL_PRESERVE_STATE_AND_RECOVERY_EVIDENCE"
        throw "STOP: P5-02X child reported failure. Do not recreate/delete files or alter recovery records; preserve state for read-only reconciliation."
    }

    if ($SourceHashAfter -ne $ExpectedMoveHash) {
        throw "STOP: P5-02X child succeeded but restored inbox source changed."
    }
    if ($TargetStateAfter -ne "absent") {
        throw "STOP: P5-02X child succeeded but vault target still exists."
    }
    if ($RecoveryEntriesAfter.Count -ne 5) {
        throw "STOP: P5-02X child succeeded but recovery count is not exactly 5."
    }

    Write-Host "P5_02X_PARENT_SOURCE_HASH_MATCH=true"
    Write-Host "P5_02X_PARENT_TARGET_ABSENT=true"
    Write-Host "P5_02X_PARENT_RECOVERY_COUNT_MATCH=true"
    Write-Host "P5_02X_GATE_RESULT=PASS"
}
finally {
    if (Test-Path -LiteralPath $SourceWorktree) {
        & git -C $Repo worktree remove --force $SourceWorktree | Out-Null
    }
}
