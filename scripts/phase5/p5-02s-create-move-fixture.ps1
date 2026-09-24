param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02S_MOVE_FIXTURE_CREATE")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02S-A creates one controlled Orion draft fixture in the dedicated inbox.
# This is NOT the move itself. Hermes stays manual-off, production mutation
# mode remains absent/disabled, the vault target must be absent, and existing
# production recovery evidence is untouched.

$ExpectedVaultRoot = "C:\Personal\Me"
$ExpectedInboxRoot = "C:\Personal\Orion-Inbox"
$SourceName = "_Orion-P5-Move-Canary.md"
$TargetName = "_Orion-P5-Move-Canary.md"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedFixtureHash = "132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132"
$ExpectedEditCanaryHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"
$ExpectedRecoveryIds = @(
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27",
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"
)

$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$Profile = Join-Path $HermesHome "profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginManifest = Join-Path $Profile "plugins\orion-vault-actions\plugin.yaml"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"
$Source = Join-Path $ExpectedInboxRoot $SourceName
$Target = Join-Path $ExpectedVaultRoot $TargetName
$EditCanary = Join-Path $ExpectedVaultRoot "_Orion-P5-Canary.md"

$FixtureLines = @(
    "---",
    "orion_draft: true",
    "status: draft",
    "date: 2026-09-24",
    "origin: p5-02s-controlled-fixture",
    "---",
    "# Orion Phase 5 Move Canary",
    "state: inbox",
    "gate: first-production-move",
    ""
)
$FixtureText = $FixtureLines -join [char]10
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$FixtureBytes = $Utf8NoBom.GetBytes($FixtureText)

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

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02S_MOVE_FIXTURE_CREATE") {
    throw "STOP: explicit P5-02S-A fixture authorization required."
}

foreach ($dir in @($ExpectedVaultRoot, $ExpectedInboxRoot, $RecoveryRoot)) {
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
        throw "STOP: required directory missing: $dir"
    }
}
foreach ($file in @($Config, $EnvFile, $PluginManifest, $EditCanary)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required baseline file missing: $file"
    }
}
if ([IO.File]::ReadAllText($PluginManifest) -notmatch '(?m)^version:\s*"0\.2\.0"\s*
if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; fixture setup requires manual-off."
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted baseline."
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash -ne $ExpectedEditCanaryHash) {
    throw "STOP: edit canary differs from accepted P5-02R restored state."
}

$ForbiddenNames = @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)
foreach ($name in @("ORION_P5_PRODUCTION_RECOVERY_ROOT") + $ForbiddenNames) {
    if (-not [string]::IsNullOrWhiteSpace(
        [Environment]::GetEnvironmentVariable($name, "Process")
    )) {
        throw "STOP: unexpected ambient Phase 5 process setting present: $name"
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

$RecoveryEntries = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryEntries.Count -ne 2) {
    throw "STOP: production recovery root must contain exactly two accepted entries."
}
if (@($RecoveryEntries | Where-Object { -not $_.PSIsContainer }).Count -ne 0) {
    throw "STOP: unexpected non-directory entry exists in production recovery root."
}
$RecoveryIds = @($RecoveryEntries | Select-Object -ExpandProperty Name) | Sort-Object
if (($RecoveryIds -join "|") -ne (($ExpectedRecoveryIds | Sort-Object) -join "|")) {
    throw "STOP: production recovery inventory differs from accepted P5-02R state."
}

if (Test-Path -LiteralPath $Source) {
    throw "STOP: proposed move source fixture already exists; do not overwrite it."
}
if (Test-Path -LiteralPath $Target) {
    throw "STOP: proposed move vault target already exists."
}

$fixtureHash = Get-Sha256Bytes -Bytes $FixtureBytes
if ($fixtureHash -ne $ExpectedFixtureHash) {
    throw "STOP: local fixture bytes differ from the frozen fixture hash."
}

$stream = [IO.File]::Open(
    $Source,
    [IO.FileMode]::CreateNew,
    [IO.FileAccess]::Write,
    [IO.FileShare]::None
)
try {
    $stream.Write($FixtureBytes, 0, $FixtureBytes.Length)
    $stream.Flush($true)
}
finally {
    $stream.Dispose()
}

$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Source).Hash
if ($actualHash -ne $ExpectedFixtureHash) {
    throw "STOP: move source fixture post-create hash mismatch; leave it in place for inspection."
}
if (Test-Path -LiteralPath $Target) {
    throw "STOP: vault target appeared during fixture creation; preserve state for inspection."
}

Write-Host "P5_02S_MOVE_FIXTURE_CREATE=PASS"
Write-Host "P5_02S_SOURCE_CANONICAL_PATH=$Source"
Write-Host "P5_02S_TARGET_CANONICAL_PATH=$Target"
Write-Host "P5_02S_SOURCE_SHA256=$actualHash"
Write-Host "P5_02S_TARGET_STATE=absent"
Write-Host "P5_02S_FIXTURE_UTF8_NO_BOM=true"
Write-Host "P5_02S_FIXTURE_NEWLINES=LF"
Write-Host "P5_02S_PRODUCTION_RECOVERY_COUNT=2"
Write-Host "PRODUCTION_MUTATION_MODE=disabled"
Write-Host "HERMES_MANUAL_OFF=true"
Write-Host "P5_02S_MOVE_NOT_EXECUTED=true"
) {
    throw "STOP: installed Orion plugin is not version 0.2.0."
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; fixture setup requires manual-off."
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted baseline."
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash -ne $ExpectedEditCanaryHash) {
    throw "STOP: edit canary differs from accepted P5-02R restored state."
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

$RecoveryIds = @(
    Get-ChildItem -LiteralPath $RecoveryRoot -Force -Directory |
        Select-Object -ExpandProperty Name
) | Sort-Object
if (($RecoveryIds -join "|") -ne (($ExpectedRecoveryIds | Sort-Object) -join "|")) {
    throw "STOP: production recovery inventory differs from accepted P5-02R state."
}

if (Test-Path -LiteralPath $Source) {
    throw "STOP: proposed move source fixture already exists; do not overwrite it."
}
if (Test-Path -LiteralPath $Target) {
    throw "STOP: proposed move vault target already exists."
}

$fixtureHash = Get-Sha256Bytes -Bytes $FixtureBytes
if ($fixtureHash -ne $ExpectedFixtureHash) {
    throw "STOP: local fixture bytes differ from the frozen fixture hash."
}

$stream = [IO.File]::Open(
    $Source,
    [IO.FileMode]::CreateNew,
    [IO.FileAccess]::Write,
    [IO.FileShare]::None
)
try {
    $stream.Write($FixtureBytes, 0, $FixtureBytes.Length)
    $stream.Flush($true)
}
finally {
    $stream.Dispose()
}

$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Source).Hash
if ($actualHash -ne $ExpectedFixtureHash) {
    throw "STOP: move source fixture post-create hash mismatch; leave it in place for inspection."
}
if (Test-Path -LiteralPath $Target) {
    throw "STOP: vault target appeared during fixture creation; preserve state for inspection."
}

Write-Host "P5_02S_MOVE_FIXTURE_CREATE=PASS"
Write-Host "P5_02S_SOURCE_CANONICAL_PATH=$Source"
Write-Host "P5_02S_TARGET_CANONICAL_PATH=$Target"
Write-Host "P5_02S_SOURCE_SHA256=$actualHash"
Write-Host "P5_02S_TARGET_STATE=absent"
Write-Host "P5_02S_FIXTURE_UTF8_NO_BOM=true"
Write-Host "P5_02S_FIXTURE_NEWLINES=LF"
Write-Host "P5_02S_PRODUCTION_RECOVERY_COUNT=2"
Write-Host "PRODUCTION_MUTATION_MODE=disabled"
Write-Host "HERMES_MANUAL_OFF=true"
Write-Host "P5_02S_MOVE_NOT_EXECUTED=true"
