param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02W_INSTALL_DELETE_DISABLED")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$QualifiedDeleteSourceCommit = "211255ff9abfa04101760c7e3358b521a3e530ae"
$AcceptedInstalledSourceCommit = "faf8b4787d8e6fb668eb5e9d754104910b4b401a"
$ExpectedBranch = "feature/orion-phase5-p5-02w-installed-delete-disabled"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedMoveHash = "132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132"
$ExpectedEditCanaryHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"
$ExpectedHermesCommit = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
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
$PluginRoot = Join-Path $Profile "plugins"
$PluginDest = Join-Path $PluginRoot "orion-vault-actions"
$PluginInit = Join-Path $PluginDest "__init__.py"
$PluginManifest = Join-Path $PluginDest "plugin.yaml"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"
$BackupRoot = Join-Path $Profile "orion\backups"
$RuntimeVerifier = Join-Path $PSScriptRoot "p5-02w-installed-delete-disabled-verify.py"
$MoveSource = "C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md"
$MoveTarget = "C:\Personal\Me\_Orion-P5-Move-Canary.md"
$EditCanary = "C:\Personal\Me\_Orion-P5-Canary.md"

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

function Test-GatewayHealthy {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8642/health" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch { return $false }
}

function Wait-GatewayHealthy {
    param([int]$TimeoutSeconds = 150)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-GatewayHealthy) { return $true }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Wait-GatewayNotListening {
    param([int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Test-GatewayListening)) { return $true }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
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

function Stop-GatewaySafely {
    if (Test-GatewayListening) {
        & $Hermes -p companion gateway stop | Out-Null
        $null = Wait-GatewayNotListening -TimeoutSeconds 30
    }
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02W_INSTALL_DELETE_DISABLED") {
    throw "STOP: exact P5-02W token required."
}

foreach ($file in @($Hermes,$HermesPython,$Config,$EnvFile,$PluginInit,$PluginManifest,$RuntimeVerifier,$MoveSource,$MoveTarget,$EditCanary)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "STOP: required file missing: $file" }
}
if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) { throw "STOP: production recovery root missing." }
if (-not (Test-Path -LiteralPath $BackupRoot -PathType Container)) { New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null }
if (Test-GatewayListening) { throw "STOP: port 8642 is listening; Hermes must be manual-off." }

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) { throw "STOP: Orion repository working tree is not clean." }
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) { throw "STOP: expected P5-02W branch is not checked out." }

foreach ($commit in @($QualifiedDeleteSourceCommit,$AcceptedInstalledSourceCommit)) {
    & git -C $Repo cat-file -e ($commit + "^{commit}")
    if ($LASTEXITCODE -ne 0) { throw "STOP: required source commit unavailable: $commit" }
}

$HermesHead = (& git -C $HermesCheckout rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $HermesHead -ne $ExpectedHermesCommit) { throw "STOP: Hermes checkout differs from accepted runtime." }

foreach ($name in @("ORION_P5_PRODUCTION_RECOVERY_ROOT","ORION_P5_MUTATION_MODE","ORION_P5_ALLOW_DISPOSABLE_MUTATION","ORION_P5_RECOVERY_ROOT")) {
    if (-not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name, "Process"))) {
        throw "STOP: unexpected ambient Phase 5 setting: $name"
    }
}

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$EnvBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
$InstalledInitBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
$InstalledManifestBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash
$MoveSourceBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash
$MoveTargetBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveTarget).Hash
$EditCanaryBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash
$RecoveryFingerprintBefore = Get-DirectoryFingerprint -Path $RecoveryRoot

if ($ConfigBefore -ne $ExpectedConfigHash) { throw "STOP: COMPANION config differs from accepted baseline." }
if ($MoveSourceBefore -ne $ExpectedMoveHash -or $MoveTargetBefore -ne $ExpectedMoveHash) { throw "STOP: accepted P5-02U move state differs from frozen hash." }
if ($EditCanaryBefore -ne $ExpectedEditCanaryHash) { throw "STOP: edit canary differs from accepted state." }

$RecoveryEntries = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryEntries.Count -ne 4) { throw "STOP: expected exactly four recovery records before P5-02W." }
if (@($RecoveryEntries | Where-Object { -not $_.PSIsContainer }).Count -ne 0) { throw "STOP: unexpected file in production recovery root." }
$RecoveryIds = @($RecoveryEntries | Select-Object -ExpandProperty Name) | Sort-Object
if (($RecoveryIds -join "|") -ne (($ExpectedRecoveryIds | Sort-Object) -join "|")) { throw "STOP: recovery ID set differs from accepted P5-02U state." }

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $BackupRoot "p5-02w-installed-delete-disabled-$Stamp"
$BackupPlugin = Join-Path $BackupDir "plugin.before"
$BackupConfig = Join-Path $BackupDir "config.yaml.before"
$BackupEnv = Join-Path $BackupDir ".env.before"
$OldSourceWorktree = Join-Path $env:TEMP "orion-p5-02w-old-$Stamp"
$NewSourceWorktree = Join-Path $env:TEMP "orion-p5-02w-new-$Stamp"
$StageDest = Join-Path $PluginRoot "orion-vault-actions.p5-02w-stage-$Stamp"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item -LiteralPath $PluginDest -Destination $BackupPlugin -Recurse -Force
Copy-Item -LiteralPath $Config -Destination $BackupConfig -Force
Copy-Item -LiteralPath $EnvFile -Destination $BackupEnv -Force

Write-Host "P5_02W_ROLLBACK_CAPTURED=true"
Write-Host "P5_02W_BACKUP_DIR=$BackupDir"
Write-Host "P5_02W_RECOVERY_COUNT_BEFORE=4"
Write-Host "P5_02W_HERMES_MANUAL_OFF_PREINSTALL=true"

$InstallMutationStarted = $false
$Succeeded = $false

try {
    & git -C $Repo worktree add --detach $OldSourceWorktree $AcceptedInstalledSourceCommit
    if ($LASTEXITCODE -ne 0) { throw "STOP: could not create accepted old-source worktree." }
    & git -C $Repo worktree add --detach $NewSourceWorktree $QualifiedDeleteSourceCommit
    if ($LASTEXITCODE -ne 0) { throw "STOP: could not create qualified new-source worktree." }

    $OldSourcePlugin = Join-Path $OldSourceWorktree "hermes_plugins\orion-vault-actions"
    $NewSourcePlugin = Join-Path $NewSourceWorktree "hermes_plugins\orion-vault-actions"
    $OldSourceInit = Join-Path $OldSourcePlugin "__init__.py"
    $OldSourceManifest = Join-Path $OldSourcePlugin "plugin.yaml"
    $NewSourceInit = Join-Path $NewSourcePlugin "__init__.py"
    $NewSourceManifest = Join-Path $NewSourcePlugin "plugin.yaml"

    if ($InstalledInitBefore -ne (Get-FileHash -Algorithm SHA256 -LiteralPath $OldSourceInit).Hash) { throw "STOP: installed code differs from accepted P5-02N source." }
    if ($InstalledManifestBefore -ne (Get-FileHash -Algorithm SHA256 -LiteralPath $OldSourceManifest).Hash) { throw "STOP: installed manifest differs from accepted P5-02N source." }

    $NewManifestText = [IO.File]::ReadAllText($NewSourceManifest)
    if ($NewManifestText -notmatch '(?m)^version:\s*"0\.3\.0"\s*$') { throw "STOP: new source manifest is not 0.3.0." }
    if ($NewManifestText -notmatch 'orion_vault_preview_delete') { throw "STOP: new source manifest lacks delete preview." }

    $NewInitHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $NewSourceInit).Hash
    $NewManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $NewSourceManifest).Hash

    & $Hermes -p companion plugins doctor $NewSourcePlugin --ci
    if ($LASTEXITCODE -ne 0) { throw "STOP: qualified source doctor failed." }
    Write-Host "P5_02W_SOURCE_DOCTOR=PASS"

    Copy-Item -LiteralPath $NewSourcePlugin -Destination $StageDest -Recurse -Force
    $InstallMutationStarted = $true
    Remove-Item -LiteralPath $PluginDest -Recurse -Force
    Move-Item -LiteralPath $StageDest -Destination $PluginDest

    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -ne $NewInitHash) { throw "STOP: installed code does not match qualified source." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash -ne $NewManifestHash) { throw "STOP: installed manifest does not match qualified source." }

    & $Hermes -p companion plugins doctor $PluginDest --ci
    if ($LASTEXITCODE -ne 0) { throw "STOP: installed plugin doctor failed." }
    Write-Host "P5_02W_INSTALLED_DOCTOR=PASS"
    Write-Host "P5_02W_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02W_INSTALLED_PLUGIN_VERSION=0.3.0"

    if ((Get-DirectoryFingerprint -Path $RecoveryRoot) -ne $RecoveryFingerprintBefore) { throw "STOP: installation changed recovery evidence." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash -ne $MoveSourceBefore) { throw "STOP: installation changed move source." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $MoveTarget).Hash -ne $MoveTargetBefore) { throw "STOP: installation changed move target." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) { throw "STOP: installation changed config." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) { throw "STOP: installation changed .env." }

    & $Hermes -p companion gateway start
    if ($LASTEXITCODE -ne 0) { throw "STOP: Hermes gateway start failed." }
    if (-not (Wait-GatewayHealthy -TimeoutSeconds 150)) { throw "STOP: Hermes gateway did not become healthy." }
    Write-Host "P5_02W_GATEWAY_HEALTHY=true"

    & $HermesPython $RuntimeVerifier $Profile $PluginDest $RecoveryRoot
    if ($LASTEXITCODE -ne 0) { throw "STOP: installed-disabled runtime verifier failed." }

    & $Hermes -p companion gateway stop
    $StopExit = $LASTEXITCODE
    if (-not (Wait-GatewayNotListening -TimeoutSeconds 30)) { throw "STOP: port 8642 remained listening after stop." }
    if ($StopExit -ne 0) { Write-Host "P5_02W_GATEWAY_STOP_NONZERO_BUT_DOWN=true" }

    if ((Get-DirectoryFingerprint -Path $RecoveryRoot) -ne $RecoveryFingerprintBefore) { throw "STOP: P5-02W changed recovery evidence." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash -ne $MoveSourceBefore) { throw "STOP: P5-02W changed move source." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $MoveTarget).Hash -ne $MoveTargetBefore) { throw "STOP: P5-02W changed move target." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash -ne $EditCanaryBefore) { throw "STOP: P5-02W changed edit canary." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) { throw "STOP: P5-02W changed config." }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) { throw "STOP: P5-02W changed .env." }
    if (Test-GatewayListening) { throw "STOP: Hermes is not manual-off after P5-02W." }

    $Succeeded = $true
    Write-Host "P5_02W_CONFIG_UNCHANGED=true"
    Write-Host "P5_02W_ENV_UNCHANGED=true"
    Write-Host "P5_02W_PRODUCTION_RECOVERY_UNCHANGED=true"
    Write-Host "P5_02W_MOVE_SOURCE_UNCHANGED=true"
    Write-Host "P5_02W_MOVE_TARGET_UNCHANGED=true"
    Write-Host "P5_02W_EDIT_CANARY_UNCHANGED=true"
    Write-Host "P5_02W_MUTATION_INVOCATION=false"
    Write-Host "P5_02W_MUTATION_MODE_PERSISTED=false"
    Write-Host "HERMES_MANUAL_OFF=true"
    Write-Host "P5_02W_INSTALLED_DISABLED_QUALIFICATION=PASS"
}
catch {
    $Failure = $_
    try { Stop-GatewaySafely } catch { Write-Host "P5_02W_ROLLBACK_GATEWAY_STOP=ERROR" }

    if ($InstallMutationStarted -and (Test-Path -LiteralPath $BackupPlugin -PathType Container)) {
        if (Test-Path -LiteralPath $PluginDest) { Remove-Item -LiteralPath $PluginDest -Recurse -Force }
        Copy-Item -LiteralPath $BackupPlugin -Destination $PluginDest -Recurse -Force
    }
    if (Test-Path -LiteralPath $BackupConfig -PathType Leaf) { Copy-Item -LiteralPath $BackupConfig -Destination $Config -Force }
    if (Test-Path -LiteralPath $BackupEnv -PathType Leaf) { Copy-Item -LiteralPath $BackupEnv -Destination $EnvFile -Force }

    $RollbackPluginOk = ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -eq $InstalledInitBefore -and (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash -eq $InstalledManifestBefore)
    $RollbackStateOk = ((Get-DirectoryFingerprint -Path $RecoveryRoot) -eq $RecoveryFingerprintBefore -and (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveSource).Hash -eq $MoveSourceBefore -and (Get-FileHash -Algorithm SHA256 -LiteralPath $MoveTarget).Hash -eq $MoveTargetBefore)
    Write-Host "P5_02W_ROLLBACK_PLUGIN_RESTORED=$($RollbackPluginOk.ToString().ToLowerInvariant())"
    Write-Host "P5_02W_ROLLBACK_STATE_RESTORED=$($RollbackStateOk.ToString().ToLowerInvariant())"
    Write-Host "P5_02W_RECOVERY_EVIDENCE_PRESERVED=true"
    throw $Failure
}
finally {
    if (Test-Path -LiteralPath $StageDest) { Remove-Item -LiteralPath $StageDest -Recurse -Force }
    foreach ($worktree in @($OldSourceWorktree,$NewSourceWorktree)) {
        if (Test-Path -LiteralPath $worktree) { & git -C $Repo worktree remove --force $worktree | Out-Null }
    }
    if (-not $Succeeded) { try { Stop-GatewaySafely } catch {} }
}
