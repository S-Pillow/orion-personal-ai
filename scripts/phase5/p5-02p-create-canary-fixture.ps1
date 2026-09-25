param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02P_CANARY_CREATE")]
    [string]$AuthorizationToken,

    [ValidateSet("_Orion-P5-Canary.md")]
    [string]$TargetRelativePath = "_Orion-P5-Canary.md"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02P-A creates one permanent, non-sensitive Phase 5 canary note while
# Hermes is manual-off and production mutation mode remains absent/disabled.
# It does NOT start Hermes, enable mutation, call the Orion plugin, or delete
# anything. The canary is intentionally retained for later edit/restore gates.

$ExpectedVaultRoot = "C:\Personal\Me"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"

$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$Profile = Join-Path $HermesHome "profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginDest = Join-Path $Profile "plugins\orion-vault-actions"
$PluginManifest = Join-Path $PluginDest "plugin.yaml"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"
$Target = Join-Path $ExpectedVaultRoot $TargetRelativePath

$BeforeLines = @(
    "# Orion Phase 5 Canary",
    "state: before",
    "gate: first-production-edit",
    ""
)
$BeforeText = $BeforeLines -join [char]10
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$BeforeBytes = $Utf8NoBom.GetBytes($BeforeText)
$ExpectedBeforeHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"

function Get-Sha256Bytes {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace("-", "")
    }
    finally {
        $sha.Dispose()
    }
}

function Test-GatewayHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8642/health" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
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

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02P_CANARY_CREATE") {
    throw "STOP: explicit P5-02P-A canary creation authorization required."
}

foreach ($path in @($ExpectedVaultRoot, $RecoveryRoot, $PluginDest)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "STOP: required directory missing: $path"
    }
}
foreach ($path in @($Config, $EnvFile, $PluginManifest)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "STOP: required file missing: $path"
    }
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; canary setup requires manual-off."
}

if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config hash differs from P5-02O accepted baseline."
}

$manifestText = [IO.File]::ReadAllText($PluginManifest)
if ($manifestText -notmatch '(?m)^version:\s*"0\.2\.0"\s*$') {
    throw "STOP: installed Orion plugin is not version 0.2.0."
}

$ForbiddenNames = @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)
foreach ($name in $ForbiddenNames) {
    if (-not [string]::IsNullOrWhiteSpace(
        [Environment]::GetEnvironmentVariable($name, "Process")
    )) {
        throw "STOP: unexpected ambient process setting present: $name"
    }
}

$EnvText = Get-EnvText -Path $EnvFile
foreach ($name in $ForbiddenNames) {
    if (@(Get-ActiveEnvValues -Text $EnvText -Name $name).Count -ne 0) {
        throw "STOP: forbidden persistent mutation/disposable setting present: $name"
    }
}

$RecoveryValues = @(
    Get-ActiveEnvValues -Text $EnvText -Name "ORION_P5_PRODUCTION_RECOVERY_ROOT"
)
if ($RecoveryValues.Count -ne 1 -or $RecoveryValues[0] -ne $RecoveryRoot) {
    throw "STOP: persisted production recovery-root assignment mismatch."
}

if (@(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count -ne 0) {
    throw "STOP: production recovery inventory is not empty."
}

$vaultReal = (Resolve-Path -LiteralPath $ExpectedVaultRoot).Path
$targetParentReal = (Resolve-Path -LiteralPath (Split-Path -Parent $Target)).Path
if ($targetParentReal -ne $vaultReal) {
    throw "STOP: canary target parent is not the accepted vault root."
}
if (Test-Path -LiteralPath $Target) {
    throw "STOP: proposed canary already exists; do not overwrite it."
}

$expectedBeforeHash = Get-Sha256Bytes -Bytes $BeforeBytes
if ($expectedBeforeHash -ne $ExpectedBeforeHash) {
    throw "STOP: local canary bytes differ from the frozen before hash."
}
$stream = [IO.File]::Open($Target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $stream.Write($BeforeBytes, 0, $BeforeBytes.Length)
    $stream.Flush($true)
}
finally {
    $stream.Dispose()
}

$actualBytes = [IO.File]::ReadAllBytes($Target)
$actualHash = Get-Sha256Bytes -Bytes $actualBytes
if ($actualHash -ne $expectedBeforeHash) {
    throw "STOP: canary post-create hash mismatch. Leave file in place for inspection."
}

Write-Host "P5_02P_CANARY_CREATE=PASS"
Write-Host "P5_02P_CANARY_RELATIVE_PATH=$TargetRelativePath"
Write-Host "P5_02P_CANARY_CANONICAL_PATH=$Target"
Write-Host "P5_02P_CANARY_BEFORE_SHA256=$actualHash"
Write-Host "P5_02P_CANARY_UTF8_NO_BOM=true"
Write-Host "P5_02P_CANARY_NEWLINES=LF"
Write-Host "PRODUCTION_MUTATION_MODE=disabled"
Write-Host "P5_02P_RECOVERY_INVENTORY_COUNT=0"
Write-Host "HERMES_MANUAL_OFF=true"
Write-Host "P5_02P_CANARY_RETAIN_FOR_FUTURE_GATES=true"
