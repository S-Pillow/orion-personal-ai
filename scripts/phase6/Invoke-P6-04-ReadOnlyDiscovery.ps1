param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04_READ_ONLY_DISCOVERY"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"

if ($AuthorizationToken -ne $ExpectedToken) { throw "STOP: explicit P6-04 read-only discovery authorization is required." }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Helper = Join-Path $PSScriptRoot "p6-04-readonly-discovery.py"
$JobsTarget = Join-Path $HermesRoot "cron\jobs.py"

function Get-StatusLines([string]$Root) { return @(& git -C $Root status --porcelain=v1) }
function Get-StatusText([string]$Root) { return ((Get-StatusLines $Root) -join [Environment]::NewLine) }
function Assert-StatusEquals([string[]]$Actual, [string[]]$Expected, [string]$Label) {
    $ActualSorted = @($Actual | Sort-Object)
    $ExpectedSorted = @($Expected | Sort-Object)
    if (($ActualSorted -join "`n") -ne ($ExpectedSorted -join "`n")) { throw "STOP: $Label status mismatch. Actual: $($ActualSorted -join ' || ')" }
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHeadBefore = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot
if ($RepoBranch -ne $ExpectedBranch) { throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch" }
if ($RepoStatusBefore) { throw "STOP: Orion worktree must be clean before P6-04 read-only discovery." }
if (-not (Test-Path -LiteralPath $HermesRoot)) { throw "STOP: installed Hermes root not found: $HermesRoot" }
if (-not (Test-Path -LiteralPath $CompanionHome)) { throw "STOP: COMPANION profile home not found: $CompanionHome" }
if (-not (Test-Path -LiteralPath $HermesPython)) { throw "STOP: Hermes venv Python not found: $HermesPython" }
if (-not (Test-Path -LiteralPath $Helper)) { throw "STOP: P6-04 discovery helper not found: $Helper" }

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHeadBefore -ne $ExpectedHermesHead) { throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore" }

$ExpectedHermesStatus = @(
    " M cron/jobs.py",
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
)
$HermesStatusBefore = Get-StatusLines $HermesRoot
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatus "installed Hermes"

$PatchedJobsSha256 = (Get-FileHash -LiteralPath $JobsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
if ($PatchedJobsSha256 -ne $ExpectedPatchedJobsSha256) { throw "STOP: installed P6-03 cron/jobs.py hash drift. Expected $ExpectedPatchedJobsSha256; observed $PatchedJobsSha256" }

$CompanionCron = Join-Path $CompanionHome "cron"
$CronMetadataBefore = @()
if (Test-Path -LiteralPath $CompanionCron) {
    $CronMetadataBefore = @(Get-ChildItem -LiteralPath $CompanionCron -Force | Sort-Object Name | ForEach-Object {
        $Type = if ($_.PSIsContainer) { "DIR" } else { "FILE" }
        $Length = if ($_.PSIsContainer) { 0 } else { $_.Length }
        "{0}|{1}|{2}|{3}" -f $_.Name, $Type, $Length, $_.LastWriteTimeUtc.Ticks
    })
}

Write-Host "P6_04_DISCOVERY_REPO_BRANCH=$RepoBranch"
Write-Host "P6_04_DISCOVERY_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_04_DISCOVERY_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_DISCOVERY_PATCHED_JOBS_SHA256=$PatchedJobsSha256"
Write-Host "P6_04_DISCOVERY_COMPANION_HOME=$CompanionHome"
Write-Host "P6_04_DISCOVERY_MUTATION_AUTHORIZED=false"
Write-Host "P6_04_DISCOVERY_REMINDER_CREATION_AUTHORIZED=false"
Write-Host "P6_04_DISCOVERY_GATEWAY_RESTART_AUTHORIZED=false"

& $HermesPython -B $Helper --hermes-root $HermesRoot --hermes-ref $ExpectedHermesHead --companion-home $CompanionHome
$HelperExit = $LASTEXITCODE
if ($HelperExit -ne 0) { throw "STOP: P6-04 read-only discovery helper failed with exit code $HelperExit." }

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusLines $HermesRoot

$CronMetadataAfter = @()
if (Test-Path -LiteralPath $CompanionCron) {
    $CronMetadataAfter = @(Get-ChildItem -LiteralPath $CompanionCron -Force | Sort-Object Name | ForEach-Object {
        $Type = if ($_.PSIsContainer) { "DIR" } else { "FILE" }
        $Length = if ($_.PSIsContainer) { 0 } else { $_.Length }
        "{0}|{1}|{2}|{3}" -f $_.Name, $Type, $Length, $_.LastWriteTimeUtc.Ticks
    })
}

if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) { throw "STOP: Orion repository changed during P6-04 read-only discovery." }
if ($HermesHeadAfter -ne $HermesHeadBefore) { throw "STOP: Hermes HEAD changed during P6-04 read-only discovery." }
Assert-StatusEquals $HermesStatusAfter $ExpectedHermesStatus "post-discovery Hermes"
if (($CronMetadataAfter -join [Environment]::NewLine) -ne ($CronMetadataBefore -join [Environment]::NewLine)) { throw "STOP: COMPANION cron metadata changed during P6-04 read-only discovery." }

Write-Host "P6_04_DISCOVERY_ORION_UNCHANGED=true"
Write-Host "P6_04_DISCOVERY_HERMES_UNCHANGED=true"
Write-Host "P6_04_DISCOVERY_COMPANION_CRON_UNCHANGED=true"
Write-Host "P6_04_READ_ONLY_DISCOVERY=PASS"
