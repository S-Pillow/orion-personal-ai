param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02O_INSTALLED_DISABLED")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02O installs the exact accepted P5-02N plugin bytes into COMPANION,
# verifies the registered guarded wrapper while production mutation remains
# disabled, and returns Hermes to manual-off. It never enables mutation and
# never invokes a production mutation path.

$QualifiedSourceCommit = "faf8b4787d8e6fb668eb5e9d754104910b4b401a"
$ExpectedBranch = "feature/orion-phase5-p5-02o-installed-disabled-qualification"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedOldPluginInitHash = "FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA"
$ExpectedHermesCommit = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedApiHash = "ECFD6DD53610C24A81F078650A0B2B3E129478A50FDB5F353313FFF6E12E3888"
$GatewayHealthTimeoutSeconds = 150

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$HermesCheckout = Join-Path $HermesHome "hermes-agent"
$Hermes = Join-Path $HermesCheckout "venv\Scripts\hermes.exe"
$HermesPython = Join-Path $HermesCheckout "venv\Scripts\python.exe"
$HermesPatchedApi = Join-Path $HermesCheckout "gateway\platforms\api_server.py"

$Profile = Join-Path $HermesHome "profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginRoot = Join-Path $Profile "plugins"
$PluginDest = Join-Path $PluginRoot "orion-vault-actions"
$PluginInit = Join-Path $PluginDest "__init__.py"
$PluginManifest = Join-Path $PluginDest "plugin.yaml"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"
$BackupRoot = Join-Path $Profile "orion\backups"
$RuntimeVerifier = Join-Path $PSScriptRoot "p5-02o-installed-disabled-verify.py"

$RecoveryEnvName = "ORION_P5_PRODUCTION_RECOVERY_ROOT"
$ForbiddenNames = @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)

function Test-GatewayHealth {
    $uri = "http" + "://127.0.0.1:8642/health"
    try {
        $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

function Wait-GatewayState {
    param(
        [Parameter(Mandatory = $true)][bool]$ExpectedUp,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ((Test-GatewayHealth) -eq $ExpectedUp) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Get-EnvText {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "STOP: COMPANION .env missing."
    }
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes -contains [byte]0) {
        throw "STOP: COMPANION .env contains NUL bytes."
    }
    $encoding = [Text.UTF8Encoding]::new($false, $true)
    $text = $encoding.GetString($bytes)
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }
    return $text
}

function Get-ActiveEnvValues {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $escaped = [regex]::Escape($Name)
    $values = @()
    foreach ($line in ($Text -split "\r\n|\n|\r")) {
        if ($line -match "^\s*#") {
            continue
        }
        if ($line -match ("^\s*" + $escaped + "\s*=\s*(.*)$")) {
            $values += $Matches[1].Trim()
        }
    }
    return @($values)
}

function Stop-GatewaySafely {
    if (Test-GatewayHealth) {
        & $Hermes -p companion gateway stop
        $null = Wait-GatewayState -ExpectedUp $false -TimeoutSeconds 30
    }
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02O_INSTALLED_DISABLED") {
    throw "STOP: explicit P5-02O authorization token required."
}

foreach ($file in @(
    $Hermes,
    $HermesPython,
    $HermesPatchedApi,
    $Config,
    $EnvFile,
    $PluginInit,
    $PluginManifest,
    $RuntimeVerifier
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}
if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) {
    throw "STOP: accepted production recovery root missing."
}
if (-not (Test-Path -LiteralPath $BackupRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
}
if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway already running; P5-02O requires manual-off baseline."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02O operator branch is not checked out."
}
$CommitObject = $QualifiedSourceCommit + "^{commit}"
& git -C $Repo cat-file -e $CommitObject
if ($LASTEXITCODE -ne 0) {
    throw "STOP: qualified P5-02N source commit is not available locally."
}

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$EnvBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
$PluginBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
$PatchedApiBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $HermesPatchedApi).Hash

if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config hash differs from accepted baseline."
}
if ($PluginBefore -ne $ExpectedOldPluginInitHash) {
    throw "STOP: installed Orion plugin is not the accepted P5-02L baseline."
}
if ($PatchedApiBefore -ne $ExpectedPatchedApiHash) {
    throw "STOP: accepted P4-04A Hermes API patch hash differs."
}
$HermesHead = (& git -C $HermesCheckout rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $HermesHead -ne $ExpectedHermesCommit) {
    throw "STOP: Hermes checkout commit differs from accepted runtime."
}

foreach ($name in @($RecoveryEnvName) + $ForbiddenNames) {
    $value = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        throw "STOP: unexpected ambient process setting present: $name"
    }
}

$EnvText = Get-EnvText -Path $EnvFile
$RecoveryValues = @(Get-ActiveEnvValues -Text $EnvText -Name $RecoveryEnvName)
if ($RecoveryValues.Count -ne 1) {
    throw "STOP: expected exactly one persisted production recovery-root assignment."
}
if ($RecoveryValues[0] -ne $RecoveryRoot) {
    throw "STOP: persisted production recovery-root value mismatch."
}
foreach ($name in $ForbiddenNames) {
    if (@(Get-ActiveEnvValues -Text $EnvText -Name $name).Count -ne 0) {
        throw "STOP: forbidden persistent mutation/disposable setting present: $name"
    }
}
if (@(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count -ne 0) {
    throw "STOP: production recovery root is not empty before installation."
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $BackupRoot "p5-02o-installed-disabled-$Stamp"
$BackupPlugin = Join-Path $BackupDir "plugin.before"
$BackupConfig = Join-Path $BackupDir "config.yaml.before"
$BackupEnv = Join-Path $BackupDir ".env.before"
$Metadata = Join-Path $BackupDir "metadata.json"
$SourceWorktree = Join-Path $env:TEMP "orion-p5-02o-source-$Stamp"
$StageDest = Join-Path $PluginRoot "orion-vault-actions.p5-02o-stage-$Stamp"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item -LiteralPath $Config -Destination $BackupConfig -Force
Copy-Item -LiteralPath $EnvFile -Destination $BackupEnv -Force
Copy-Item -LiteralPath $PluginDest -Destination $BackupPlugin -Recurse -Force

[ordered]@{
    gate = "P5-02O"
    created_local = (Get-Date).ToString("o")
    qualified_source_commit = $QualifiedSourceCommit
    config_sha256_before = $ConfigBefore
    env_sha256_before = $EnvBefore
    installed_plugin_init_sha256_before = $PluginBefore
    hermes_commit = $HermesHead
    hermes_patched_api_sha256 = $PatchedApiBefore
    recovery_root = $RecoveryRoot
} | ConvertTo-Json | Set-Content -LiteralPath $Metadata -Encoding UTF8

Write-Host "P5_02O_ROLLBACK_CAPTURED=true"
Write-Host "P5_02O_BACKUP_DIR=$BackupDir"
Write-Host "P5_02O_MUTATION_MODE_PERSISTED=false"
Write-Host "P5_02O_DISPOSABLE_FLAGS_PERSISTED=false"
Write-Host "P5_02O_RECOVERY_INVENTORY_COUNT=0"
Write-Host "P5_02O_HERMES_MANUAL_OFF_PREINSTALL=true"

$InstallMutationStarted = $false
$Installed = $false
$GatewayStartIssued = $false
$Validated = $false
$Stopped = $false
$Succeeded = $false

try {
    & git -C $Repo worktree add --detach $SourceWorktree $QualifiedSourceCommit
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: could not create exact qualified-source worktree."
    }

    $SourcePlugin = Join-Path $SourceWorktree "hermes_plugins\orion-vault-actions"
    $SourceInit = Join-Path $SourcePlugin "__init__.py"
    $SourceManifest = Join-Path $SourcePlugin "plugin.yaml"
    foreach ($file in @($SourceInit, $SourceManifest)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "STOP: qualified source plugin file missing: $file"
        }
    }

    $SourceManifestText = [IO.File]::ReadAllText($SourceManifest)
    if ($SourceManifestText -notmatch '(?m)^version:\s*"0\.2\.0"\s*$') {
        throw "STOP: qualified source manifest is not plugin version 0.2.0."
    }
    $SourceInitHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceInit).Hash
    $SourceManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceManifest).Hash

    & $Hermes -p companion plugins doctor $SourcePlugin --ci
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: qualified source plugin doctor failed."
    }
    Write-Host "P5_02O_SOURCE_DOCTOR=PASS"

    if (Test-Path -LiteralPath $StageDest) {
        Remove-Item -LiteralPath $StageDest -Recurse -Force
    }
    Copy-Item -LiteralPath $SourcePlugin -Destination $StageDest -Recurse -Force

    $InstallMutationStarted = $true
    Remove-Item -LiteralPath $PluginDest -Recurse -Force
    Move-Item -LiteralPath $StageDest -Destination $PluginDest
    $Installed = $true

    $PluginAfterInstall = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
    $ManifestAfterInstall = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash
    if ($PluginAfterInstall -ne $SourceInitHash) {
        throw "STOP: installed plugin __init__.py does not match qualified source."
    }
    if ($ManifestAfterInstall -ne $SourceManifestHash) {
        throw "STOP: installed plugin manifest does not match qualified source."
    }

    & $Hermes -p companion plugins doctor $PluginDest --ci
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: installed-location plugin doctor failed."
    }
    Write-Host "P5_02O_INSTALLED_DOCTOR=PASS"
    Write-Host "P5_02O_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02O_INSTALLED_PLUGIN_VERSION=0.2.0"

    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: COMPANION config changed during install."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: COMPANION .env changed during install."
    }
    if (@(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count -ne 0) {
        throw "STOP: installation created unexpected production recovery records."
    }

    Write-Host ""
    Write-Host "=== P5-02O START COMPANION ==="
    & $Hermes -p companion gateway start
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: Hermes COMPANION gateway start failed."
    }
    $GatewayStartIssued = $true
    Write-Host "P5_02O_GATEWAY_HEALTH_TIMEOUT_SECONDS=$GatewayHealthTimeoutSeconds"

    if (-not (Wait-GatewayState -ExpectedUp $true -TimeoutSeconds $GatewayHealthTimeoutSeconds)) {
        throw "STOP: Hermes gateway did not become healthy within $GatewayHealthTimeoutSeconds seconds."
    }
    Write-Host "P5_02O_GATEWAY_HEALTHY=true"

    & $HermesPython $RuntimeVerifier $Profile $PluginDest $RecoveryRoot
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02O installed-runtime verifier failed."
    }
    $Validated = $true

    Write-Host ""
    Write-Host "=== P5-02O STOP COMPANION ==="
    & $Hermes -p companion gateway stop
    $StopExit = $LASTEXITCODE
    if (-not (Wait-GatewayState -ExpectedUp $false -TimeoutSeconds 30)) {
        throw "STOP: Hermes gateway remained reachable after stop."
    }
    if ($StopExit -ne 0) {
        Write-Host "P5_02O_GATEWAY_STOP_NONZERO_BUT_DOWN=true"
    }
    $Stopped = $true
    Write-Host "P5_02O_GATEWAY_STOPPED=true"

    if (-not $Validated -or -not $Stopped) {
        throw "STOP: installed-disabled qualification did not complete."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: COMPANION config changed during P5-02O."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: COMPANION .env changed during P5-02O."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -ne $SourceInitHash) {
        throw "STOP: installed plugin changed during P5-02O."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $HermesPatchedApi).Hash -ne $PatchedApiBefore) {
        throw "STOP: accepted P4-04A Hermes patch changed during P5-02O."
    }
    if (Test-GatewayHealth) {
        throw "STOP: Hermes gateway unexpectedly reachable after manual-off restoration."
    }
    if (@(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count -ne 0) {
        throw "STOP: P5-02O created unexpected production recovery records."
    }

    $Succeeded = $true
    Write-Host "P5_02O_CONFIG_UNCHANGED=true"
    Write-Host "P5_02O_ENV_UNCHANGED=true"
    Write-Host "P5_02O_RECOVERY_ROOT_STILL_EMPTY=true"
    Write-Host "P5_02O_MUTATION_INVOCATION=false"
    Write-Host "HERMES_MANUAL_OFF=true"
    Write-Host "P5_02O_INSTALLED_DISABLED_QUALIFICATION=PASS"
}
catch {
    $Failure = $_
    try {
        if ($GatewayStartIssued -or (Test-GatewayHealth)) {
            & $Hermes -p companion gateway stop
            $null = Wait-GatewayState -ExpectedUp $false -TimeoutSeconds 30
        }
    }
    catch {
        Write-Host "P5_02O_ROLLBACK_GATEWAY_STOP=ERROR"
    }

    if ($InstallMutationStarted -and (Test-Path -LiteralPath $BackupPlugin -PathType Container)) {
        if (Test-Path -LiteralPath $PluginDest) {
            Remove-Item -LiteralPath $PluginDest -Recurse -Force
        }
        Copy-Item -LiteralPath $BackupPlugin -Destination $PluginDest -Recurse -Force
    }
    if (Test-Path -LiteralPath $BackupConfig -PathType Leaf) {
        Copy-Item -LiteralPath $BackupConfig -Destination $Config -Force
    }
    if (Test-Path -LiteralPath $BackupEnv -PathType Leaf) {
        Copy-Item -LiteralPath $BackupEnv -Destination $EnvFile -Force
    }

    if (
        (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -eq $ConfigBefore -and
        (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -eq $EnvBefore -and
        (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -eq $PluginBefore
    ) {
        Write-Host "P5_02O_ROLLBACK_RESTORED=true"
    }
    else {
        Write-Host "P5_02O_ROLLBACK_RESTORED=false"
    }
    Write-Host "P5_02O_RECOVERY_EVIDENCE_PRESERVED=true"
    throw $Failure
}
finally {
    if (Test-Path -LiteralPath $StageDest) {
        Remove-Item -LiteralPath $StageDest -Recurse -Force
    }
    if (Test-Path -LiteralPath $SourceWorktree) {
        & git -C $Repo worktree remove --force $SourceWorktree | Out-Null
    }
    if (-not $Succeeded -and ($GatewayStartIssued -or (Test-GatewayHealth))) {
        try {
            & $Hermes -p companion gateway stop
            $null = Wait-GatewayState -ExpectedUp $false -TimeoutSeconds 30
        }
        catch {}
    }
}
