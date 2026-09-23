param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02K_PERSIST_RECOVERY_ROOT")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02K persists exactly one COMPANION environment assignment:
# ORION_P5_PRODUCTION_RECOVERY_ROOT=<accepted P5-02J root>
#
# It does not persist or enable production mutation mode, start Hermes, register
# the production executor, or mutate real vault/inbox content.

$Hermes = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\hermes.exe"
$HermesPython = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\python.exe"
$Profile = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginDest = Join-Path $Profile "plugins\orion-vault-actions"
$PluginInit = Join-Path $PluginDest "__init__.py"
$OrionStateParent = Join-Path $Profile "orion"
$BackupsRoot = Join-Path $OrionStateParent "backups"
$RecoveryRoot = Join-Path $OrionStateParent "production-recovery"
$NativeVerifier = Join-Path $PSScriptRoot "p5-02j-verify-production-recovery-root.py"

$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedPluginInitHash = "FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA"

$RecoveryEnvName = "ORION_P5_PRODUCTION_RECOVERY_ROOT"
$ForbiddenPersistent = @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)
$ForbiddenProcess = @(
    $RecoveryEnvName,
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)

$Utf8Strict = [Text.UTF8Encoding]::new($false, $true)
$Utf8NoBom = [Text.UTF8Encoding]::new($false)

function Test-GatewayHealth {
    $uri = "http" + "://127.0.0.1:8642/health"
    try {
        $null = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
        return $true
    }
    catch {
        return $false
    }
}

function Get-EnvText {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }

    $bytes = [IO.File]::ReadAllBytes($Path)

    # Fail closed on UTF-16/UTF-32 style NUL-bearing dotenv data. Existing
    # COMPANION content is never printed.
    if ($bytes -contains [byte]0) {
        throw "STOP: COMPANION .env encoding is not safe for append-only UTF-8 update."
    }

    return $Utf8Strict.GetString($bytes)
}

function Get-ActiveEnvValues {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $escaped = [regex]::Escape($Name)
    $values = @()

    foreach ($line in ($Text -split "\r?\n")) {
        if ($line -match "^\s*#") {
            continue
        }
        if ($line -match ("^\s*" + $escaped + "\s*=\s*(.*)$")) {
            $values += $Matches[1].Trim()
        }
    }

    return @($values)
}

function Get-OptionalSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Write-Metadata {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][hashtable]$Record
    )

    $json = $Record | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $Utf8NoBom)
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02K_PERSIST_RECOVERY_ROOT") {
    throw "STOP: explicit P5-02K authorization token required."
}

foreach ($required in @($Hermes, $HermesPython, $Config, $PluginInit, $NativeVerifier)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "STOP: required file missing: $required"
    }
}

foreach ($requiredDir in @($OrionStateParent, $BackupsRoot, $RecoveryRoot)) {
    if (-not (Test-Path -LiteralPath $requiredDir -PathType Container)) {
        throw "STOP: required directory missing: $requiredDir"
    }
}

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted baseline."
}

$PluginBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
if ($PluginBefore -ne $ExpectedPluginInitHash) {
    throw "STOP: installed Orion plugin differs from accepted P5-02I baseline."
}

foreach ($name in $ForbiddenProcess) {
    $value = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        throw "STOP: unexpected process setting present: $name"
    }
}

$EnvExistedBefore = Test-Path -LiteralPath $EnvFile -PathType Leaf
$EnvBeforeHash = Get-OptionalSha256 -Path $EnvFile
$EnvBeforeBytes = if ($EnvExistedBefore) {
    [IO.File]::ReadAllBytes($EnvFile)
}
else {
    [byte[]]@()
}

$EnvBeforeText = Get-EnvText -Path $EnvFile

if ((Get-ActiveEnvValues -Text $EnvBeforeText -Name $RecoveryEnvName).Count -ne 0) {
    throw "STOP: persistent production recovery-root setting already exists."
}

foreach ($name in $ForbiddenPersistent) {
    if ((Get-ActiveEnvValues -Text $EnvBeforeText -Name $name).Count -ne 0) {
        throw "STOP: forbidden persistent mutation/disposable setting exists: $name"
    }
}

& $Hermes -p companion gateway status
if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; P5-02K requires manual-off."
}

# Revalidate the accepted P5-02J root before persisting its path.
& $HermesPython $NativeVerifier $PluginDest $RecoveryRoot
if ($LASTEXITCODE -ne 0) {
    throw "STOP: accepted production recovery root failed native validation."
}

$ExistingRecoveryChildren = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($ExistingRecoveryChildren.Count -ne 0) {
    throw "STOP: production recovery root is no longer empty."
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $BackupsRoot "p5-02k-env-$Stamp"
$BackupEnv = Join-Path $BackupDir ".env.before"
$MetadataPath = Join-Path $BackupDir "metadata.json"

New-Item -ItemType Directory -Path $BackupDir -ErrorAction Stop | Out-Null

if ($EnvExistedBefore) {
    Copy-Item -LiteralPath $EnvFile -Destination $BackupEnv -Force
    $BackupHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BackupEnv).Hash
    if ($BackupHash -ne $EnvBeforeHash) {
        throw "STOP: byte-for-byte .env rollback capture failed."
    }
}

$metadata = @{
    schema_version = 1
    gate = "P5-02K"
    created_at = (Get-Date).ToString("o")
    env_existed_before = $EnvExistedBefore
    env_sha256_before = $EnvBeforeHash
    config_sha256 = $ConfigBefore
    plugin_init_sha256 = $PluginBefore
    production_recovery_root = $RecoveryRoot
    env_sha256_after = $null
    result = "prepared"
}
Write-Metadata -Path $MetadataPath -Record $metadata

Write-Host "P5_02K_BACKUP_DIR=$BackupDir"
Write-Host "P5_02K_ROLLBACK_CAPTURED=true"

$EnvMutated = $false
$Passed = $false

try {
    $assignment = $RecoveryEnvName + "=" + $RecoveryRoot
    $prefix = ""

    if ($EnvBeforeBytes.Length -gt 0) {
        $last = $EnvBeforeBytes[$EnvBeforeBytes.Length - 1]
        if ($last -ne 10 -and $last -ne 13) {
            $prefix = [Environment]::NewLine
        }
    }

    $appendText = $prefix + $assignment + [Environment]::NewLine
    $appendBytes = $Utf8NoBom.GetBytes($appendText)

    if ($EnvExistedBefore) {
        $stream = [IO.File]::Open(
            $EnvFile,
            [IO.FileMode]::Append,
            [IO.FileAccess]::Write,
            [IO.FileShare]::Read
        )
        try {
            $stream.Write($appendBytes, 0, $appendBytes.Length)
            $stream.Flush($true)
        }
        finally {
            $stream.Dispose()
        }
    }
    else {
        $stream = [IO.File]::Open(
            $EnvFile,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::Read
        )
        try {
            $stream.Write($appendBytes, 0, $appendBytes.Length)
            $stream.Flush($true)
        }
        finally {
            $stream.Dispose()
        }
    }

    $EnvMutated = $true

    $EnvAfterBytes = [IO.File]::ReadAllBytes($EnvFile)

    if ($EnvExistedBefore) {
        if ($EnvAfterBytes.Length -ne ($EnvBeforeBytes.Length + $appendBytes.Length)) {
            throw "STOP: .env length does not match append-only expectation."
        }

        for ($i = 0; $i -lt $EnvBeforeBytes.Length; $i++) {
            if ($EnvAfterBytes[$i] -ne $EnvBeforeBytes[$i]) {
                throw "STOP: pre-existing .env bytes changed; append-only contract violated."
            }
        }
    }
    else {
        if ($EnvAfterBytes.Length -ne $appendBytes.Length) {
            throw "STOP: newly created .env bytes do not match expected single assignment."
        }
    }

    $EnvAfterText = Get-EnvText -Path $EnvFile
    $rootValues = @(Get-ActiveEnvValues -Text $EnvAfterText -Name $RecoveryEnvName)

    Write-Host "P5_02K_RECOVERY_ROOT_ASSIGNMENT_COUNT=$($rootValues.Count)"

    if ($rootValues.Count -ne 1) {
        throw "STOP: expected exactly one production recovery-root assignment."
    }
    if ($rootValues[0] -ne $RecoveryRoot) {
        throw "STOP: persisted production recovery-root value mismatch."
    }

    foreach ($name in $ForbiddenPersistent) {
        if ((Get-ActiveEnvValues -Text $EnvAfterText -Name $name).Count -ne 0) {
            throw "STOP: forbidden mutation/disposable setting appeared: $name"
        }
    }

    Write-Host "P5_02K_ENV_APPEND_ONLY=true"
    Write-Host "P5_02K_RECOVERY_ROOT_VALUE_MATCH=true"
    Write-Host "P5_02K_MUTATION_MODE_PERSISTED=false"
    Write-Host "P5_02K_DISPOSABLE_FLAGS_PERSISTED=false"

    # Native validation remains process-scoped for this no-restart gate.
    & $HermesPython $NativeVerifier $PluginDest $RecoveryRoot
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: post-persistence native recovery-root validation failed."
    }

    Write-Host "P5_02K_NATIVE_ROOT_VALIDATION=PASS"
    Write-Host "PRODUCTION_MUTATION_MODE=disabled"
    Write-Host "PRODUCTION_MUTATION_ALLOWED=false"
    Write-Host "P5_02K_RECOVERY_INVENTORY_COUNT=0"

    $ConfigAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
    if ($ConfigAfter -ne $ConfigBefore) {
        throw "STOP: COMPANION config changed during P5-02K."
    }

    $PluginAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
    if ($PluginAfter -ne $PluginBefore) {
        throw "STOP: installed plugin changed during P5-02K."
    }

    if (Test-GatewayHealth) {
        throw "STOP: Hermes gateway unexpectedly started during P5-02K."
    }

    foreach ($name in $ForbiddenProcess) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            throw "STOP: process setting leaked into operator process: $name"
        }
    }

    $EnvAfterHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
    $metadata.env_sha256_after = $EnvAfterHash
    $metadata.result = "pass"
    Write-Metadata -Path $MetadataPath -Record $metadata

    Write-Host "P5_02K_CONFIG_UNCHANGED=true"
    Write-Host "P5_02K_PLUGIN_UNCHANGED=true"
    Write-Host "HERMES_MANUAL_OFF=true"
    Write-Host "P5_02K_PERSIST_RECOVERY_ROOT=PASS"

    $Passed = $true
}
catch {
    Write-Host ""
    Write-Host "P5-02K FAILED."

    if ($EnvMutated) {
        if ($EnvExistedBefore) {
            Copy-Item -LiteralPath $BackupEnv -Destination $EnvFile -Force
            $RestoredHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
            if ($RestoredHash -ne $EnvBeforeHash) {
                Write-Host "P5_02K_ROLLBACK_VERIFY_FAILED=true"
            }
            else {
                Write-Host "P5_02K_ENV_ROLLED_BACK=true"
            }
        }
        else {
            if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
                Remove-Item -LiteralPath $EnvFile -Force
            }
            Write-Host "P5_02K_NEW_ENV_REMOVED=true"
        }
    }

    $metadata.result = "failed"
    try {
        Write-Metadata -Path $MetadataPath -Record $metadata
    }
    catch {}

    throw
}
finally {
    if (-not $Passed) {
        Write-Host "P5_02K_PERSIST_RECOVERY_ROOT=FAIL"
    }
}
