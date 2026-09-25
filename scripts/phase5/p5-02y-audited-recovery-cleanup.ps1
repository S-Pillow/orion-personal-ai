param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02Y_EXACT_AUDITED_RECOVERY_CLEANUP")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$QualifiedPluginSourceCommit = "211255ff9abfa04101760c7e3358b521a3e530ae"
$ExpectedBranch = "feature/orion-phase5-p5-02y-audited-recovery-cleanup"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedMoveHash = "132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132"
$ExpectedEditCanaryHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"
$ExpectedRecoveryIds = @(
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f",
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27",
    "8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6",
    "5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175",
    "e48123ceecc2be50afb2902511f64397f5dcfa35338ab9fd785cbf7278658b36"
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
$AuditRoot = Join-Path $Profile "orion\recovery-audit"

$MoveSource = "C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md"
$MoveTarget = "C:\Personal\Me\_Orion-P5-Move-Canary.md"
$EditCanary = "C:\Personal\Me\_Orion-P5-Canary.md"
$AuditHelper = Join-Path $PSScriptRoot "p5-02y-recovery-cleanup-audit.py"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$AuditPath = Join-Path $AuditRoot "p5-02y-phase5-canary-recovery-cleanup-$Stamp.json"
$SourceWorktree = Join-Path $env:TEMP "orion-p5-02y-source-$Stamp"

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

function Assert-NoReparseTree {
    param([Parameter(Mandatory = $true)][string]$Path)

    $root = Get-Item -LiteralPath $Path -Force
    if (($root.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "STOP: reparse point rejected: $Path"
    }
    foreach ($item in (Get-ChildItem -LiteralPath $Path -Recurse -Force)) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "STOP: reparse point rejected inside cleanup set: $($item.FullName)"
        }
    }
}

function Emit-FailureState {
    param([Parameter(Mandatory = $true)][string]$Stage)

    Write-Host "P5_02Y_FAILURE_STAGE=$Stage"
    if (Test-Path -LiteralPath $AuditPath -PathType Leaf) {
        Write-Host "P5_02Y_AUDIT_PATH=$AuditPath"
        try {
            Write-Host "P5_02Y_AUDIT_SHA256_OBSERVED=$((Get-FileHash -Algorithm SHA256 -LiteralPath $AuditPath).Hash)"
        }
        catch {
            Write-Host "P5_02Y_AUDIT_HASH_ERROR=$($_.Exception.GetType().Name)"
        }
    }
    $remaining = @(
        Get-ChildItem -LiteralPath $RecoveryRoot -Force -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty Name
    ) | Sort-Object
    Write-Host "P5_02Y_REMAINING_RECOVERY_COUNT=$($remaining.Count)"
    if ($remaining.Count -gt 0) {
        Write-Host "P5_02Y_REMAINING_RECOVERY_IDS=$($remaining -join ',')"
    }
    Write-Host "P5_02Y_AUTOMATIC_RECOVERY_RESTORE=false"
    Write-Host "P5_02Y_AUTOMATIC_ADDITIONAL_DELETE=false"
    Write-Host "P5_02Y_PRESERVE_AUDIT_AND_OBSERVED_STATE=true"
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02Y_EXACT_AUDITED_RECOVERY_CLEANUP") {
    throw "STOP: exact P5-02Y cleanup token required."
}

foreach ($file in @(
    $Hermes,$HermesPython,$Config,$EnvFile,$PluginInit,$PluginManifest,
    $MoveSource,$EditCanary,$AuditHelper
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}
if (Test-Path -LiteralPath $MoveTarget) {
    throw "STOP: P5-02X deleted target has reappeared."
}
if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) {
    throw "STOP: production recovery root missing."
}
if (Test-GatewayListening) {
    throw "STOP: port 8642 is listening; P5-02Y requires Hermes manual-off."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02Y branch is not checked out."
}
& git -C $Repo cat-file -e ($QualifiedPluginSourceCommit + "^{commit}")
if ($LASTEXITCODE -ne 0) {
    throw "STOP: P5-02V-qualified plugin source commit unavailable."
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
$EditCanaryBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash

if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted baseline."
}
if ($MoveSourceBefore -ne $ExpectedMoveHash) {
    throw "STOP: restored move source differs from accepted frozen hash."
}
if ($EditCanaryBefore -ne $ExpectedEditCanaryHash) {
    throw "STOP: edit canary differs from accepted restored hash."
}

$RecoveryEntriesBefore = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryEntriesBefore.Count -ne 5) {
    throw "STOP: exact cleanup policy requires five recovery records."
}
if (@($RecoveryEntriesBefore | Where-Object { -not $_.PSIsContainer }).Count -ne 0) {
    throw "STOP: unexpected non-directory entry exists in recovery root."
}
$RecoveryIdsBefore = @(
    $RecoveryEntriesBefore | Select-Object -ExpandProperty Name
) | Sort-Object
if (($RecoveryIdsBefore -join "|") -ne (($ExpectedRecoveryIds | Sort-Object) -join "|")) {
    throw "STOP: recovery ID set differs from approved cleanup set."
}
foreach ($recoveryId in $ExpectedRecoveryIds) {
    Assert-NoReparseTree -Path (Join-Path $RecoveryRoot $recoveryId)
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
        throw "STOP: installed plugin doctor failed."
    }
    & $HermesPython -m py_compile $AuditHelper
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02Y audit helper compile failed."
    }

    if (-not (Test-Path -LiteralPath $AuditRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $AuditRoot | Out-Null
    }
    $auditRootItem = Get-Item -LiteralPath $AuditRoot -Force
    if (($auditRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "STOP: audit root is a reparse point."
    }
    if (Test-Path -LiteralPath $AuditPath) {
        throw "STOP: chosen P5-02Y audit path already exists."
    }

    Write-Host "P5_02Y_PRECHECK=PASS"
    Write-Host "P5_02Y_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02Y_INSTALLED_PLUGIN_VERSION=0.3.0"
    Write-Host "P5_02Y_INSTALLED_PLUGIN_DOCTOR=PASS"
    Write-Host "P5_02Y_AUDIT_HELPER_COMPILE=PASS"
    Write-Host "P5_02Y_POLICY_KIND=exact_count_exact_id"
    Write-Host "P5_02Y_APPROVED_RECOVERY_COUNT=5"
    Write-Host "P5_02Y_TARGET_STATE_BEFORE=absent"
    Write-Host "P5_02Y_SOURCE_SHA256=$MoveSourceBefore"
    Write-Host "P5_02Y_HERMES_MANUAL_OFF=true"

    & $HermesPython $AuditHelper prepare $Profile $PluginDest $RecoveryRoot $AuditPath
    if ($LASTEXITCODE -ne 0) {
        Emit-FailureState -Stage "audit_prepare"
        throw "STOP: P5-02Y audit preparation failed; no recovery records were deleted."
    }

    if (-not (Test-Path -LiteralPath $AuditPath -PathType Leaf)) {
        Emit-FailureState -Stage "audit_missing_after_prepare"
        throw "STOP: prepared audit file missing."
    }

    # After the audit is durable, delete only the explicitly approved IDs.
    foreach ($recoveryId in $ExpectedRecoveryIds) {
        $recoveryPath = Join-Path $RecoveryRoot $recoveryId
        if (-not (Test-Path -LiteralPath $recoveryPath -PathType Container)) {
            Emit-FailureState -Stage "approved_record_missing_before_delete"
            throw "STOP: approved recovery record disappeared before its cleanup step."
        }
        Assert-NoReparseTree -Path $recoveryPath

        Remove-Item -LiteralPath $recoveryPath -Recurse -Force
        if (Test-Path -LiteralPath $recoveryPath) {
            Emit-FailureState -Stage "recovery_directory_delete_failed"
            throw "STOP: recovery directory still exists after explicit delete."
        }

        & $HermesPython $AuditHelper record $AuditPath $recoveryId
        if ($LASTEXITCODE -ne 0) {
            Emit-FailureState -Stage "audit_progress_journal_failed"
            throw "STOP: removal occurred but audit journaling failed. Do not delete any additional recovery records."
        }
    }

    & $HermesPython $AuditHelper finalize $Profile $PluginDest $RecoveryRoot $AuditPath
    if ($LASTEXITCODE -ne 0) {
        Emit-FailureState -Stage "audit_finalize"
        throw "STOP: all exact removals completed but audit finalization failed. Preserve audit and observed state."
    }

    if (@(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count -ne 0) {
        Emit-FailureState -Stage "recovery_root_not_empty"
        throw "STOP: production recovery root is not empty after exact cleanup."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: P5-02Y changed COMPANION config."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: P5-02Y changed COMPANION .env."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -ne $PluginInitBefore) {
        throw "STOP: P5-02Y changed installed plugin code."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash -ne $PluginManifestBefore) {
        throw "STOP: P5-02Y changed installed plugin manifest."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash -ne $MoveSourceBefore) {
        throw "STOP: P5-02Y changed restored move source."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash -ne $EditCanaryBefore) {
        throw "STOP: P5-02Y changed edit canary."
    }
    if (Test-Path -LiteralPath $MoveTarget) {
        throw "STOP: P5-02Y unexpectedly recreated the deleted target."
    }
    if (Test-GatewayListening) {
        throw "STOP: P5-02Y unexpectedly left port 8642 listening."
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
            throw "STOP: P5-02Y leaked Phase 5 state into parent process: $name"
        }
    }

    $AuditHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $AuditPath).Hash
    Write-Host "P5_02Y_RECOVERY_CLEANUP=PASS"
    Write-Host "P5_02Y_REMOVED_RECOVERY_COUNT=5"
    Write-Host "P5_02Y_PRODUCTION_RECOVERY_COUNT_AFTER=0"
    Write-Host "P5_02Y_PRODUCTION_RECOVERY_ROOT_EMPTY=true"
    Write-Host "P5_02Y_AUDIT_STATUS=committed"
    Write-Host "P5_02Y_AUDIT_PATH=$AuditPath"
    Write-Host "P5_02Y_AUDIT_SHA256=$AuditHash"
    Write-Host "P5_02Y_SOURCE_UNCHANGED=true"
    Write-Host "P5_02Y_TARGET_REMAINS_ABSENT=true"
    Write-Host "P5_02Y_EDIT_CANARY_UNCHANGED=true"
    Write-Host "P5_02Y_CONFIG_UNCHANGED=true"
    Write-Host "P5_02Y_ENV_UNCHANGED=true"
    Write-Host "P5_02Y_INSTALLED_PLUGIN_UNCHANGED=true"
    Write-Host "P5_02Y_MUTATION_MODE_PERSISTED=false"
    Write-Host "P5_02Y_AUTOMATIC_RECOVERY_RESTORE=false"
    Write-Host "HERMES_MANUAL_OFF=true"
    Write-Host "P5_02Y_GATE_RESULT=PASS"
}
finally {
    if (Test-Path -LiteralPath $SourceWorktree) {
        & git -C $Repo worktree remove --force $SourceWorktree | Out-Null
    }
}
