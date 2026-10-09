param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_DISPOSABLE_CORRUPTION_PRESERVATION"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 disposable authorization token is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionCron = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\cron"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Probe = Join-Path $PSScriptRoot "p6-03-disposable-corruption-preservation.py"

function Get-StatusText([string]$Root) {
    return ((& git -C $Root status --porcelain=v1) -join [Environment]::NewLine)
}

function Get-CronMetadata([string]$CronPath) {
    if (-not (Test-Path -LiteralPath $CronPath)) {
        return @()
    }
    return @(
        Get-ChildItem -LiteralPath $CronPath -Force |
            Sort-Object Name |
            ForEach-Object {
                $Type = if ($_.PSIsContainer) { "DIR" } else { "FILE" }
                $Length = if ($_.PSIsContainer) { 0 } else { $_.Length }
                "{0}|{1}|{2}|{3}" -f $_.Name, $Type, $Length, $_.LastWriteTimeUtc.Ticks
            }
    )
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot
$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusBefore = Get-StatusText $HermesRoot
$CompanionBefore = Get-CronMetadata $CompanionCron

if ($RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch"
}
if ($RepoStatusBefore) {
    throw "STOP: Orion worktree must be clean before P6-03 disposable qualification."
}
if ($HermesHeadBefore -ne $ExpectedHermesHead) {
    throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore"
}

$ExpectedHermesStatus = @(
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
) -join [Environment]::NewLine

if ($HermesStatusBefore -ne $ExpectedHermesStatus) {
    throw "STOP: Hermes worktree differs from the accepted compatibility-artifact state."
}
if (-not (Test-Path -LiteralPath $HermesPython)) {
    throw "STOP: Hermes venv Python not found: $HermesPython"
}
if (-not (Test-Path -LiteralPath $Probe)) {
    throw "STOP: P6-03 Python qualifier not found: $Probe"
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempBase = Join-Path $env:TEMP "orion-p6-03-$Stamp"
$SourceRoot = Join-Path $TempBase "hermes-source"
$DisposableHome = Join-Path $TempBase "hermes-home"
$ArchivePath = Join-Path $TempBase "hermes-source.tar"

New-Item -ItemType Directory -Path $SourceRoot -Force | Out-Null
New-Item -ItemType Directory -Path $DisposableHome -Force | Out-Null

Write-Host "P6_03_REPO_BRANCH=$RepoBranch"
Write-Host "P6_03_REPO_HEAD=$RepoHead"
Write-Host "P6_03_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_03_COMPANION_CRON_METADATA_CAPTURED=true"
Write-Host "P6_03_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_03_INSTALLED_HERMES_SOURCE_MUTATION_AUTHORIZED=false"
Write-Host "P6_03_DISPOSABLE_SOURCE=$SourceRoot"
Write-Host "P6_03_DISPOSABLE_HOME=$DisposableHome"

& git -C $HermesRoot archive --format=tar --output=$ArchivePath $ExpectedHermesHead
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to archive pinned Hermes source."
}

& tar -xf $ArchivePath -C $SourceRoot
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to extract disposable Hermes source archive."
}

$PythonExit = 1
try {
    & $HermesPython $Probe --source-root $SourceRoot --disposable-home $DisposableHome
    $PythonExit = $LASTEXITCODE
}
finally {
    $RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $RepoStatusAfter = Get-StatusText $RepoRoot
    $HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
    $HermesStatusAfter = Get-StatusText $HermesRoot
    $CompanionAfter = Get-CronMetadata $CompanionCron

    $RepoHeadUnchanged = ($RepoHeadAfter -eq $RepoHead)
    $RepoWorktreeUnchanged = ($RepoStatusAfter -eq $RepoStatusBefore)
    $HermesHeadUnchanged = ($HermesHeadAfter -eq $HermesHeadBefore)
    $HermesWorktreeUnchanged = ($HermesStatusAfter -eq $HermesStatusBefore)
    $CompanionUnchanged = (($CompanionAfter -join [Environment]::NewLine) -eq ($CompanionBefore -join [Environment]::NewLine))

    Write-Host "P6_03_PYTHON_EXIT_CODE=$PythonExit"
    Write-Host "P6_03_ORION_HEAD_UNCHANGED=$RepoHeadUnchanged"
    Write-Host "P6_03_ORION_WORKTREE_UNCHANGED=$RepoWorktreeUnchanged"
    Write-Host "P6_03_HERMES_HEAD_UNCHANGED=$HermesHeadUnchanged"
    Write-Host "P6_03_HERMES_WORKTREE_UNCHANGED=$HermesWorktreeUnchanged"
    Write-Host "P6_03_COMPANION_CRON_UNCHANGED=$CompanionUnchanged"

    if ($PythonExit -eq 0 -and $RepoHeadUnchanged -and $RepoWorktreeUnchanged -and $HermesHeadUnchanged -and $HermesWorktreeUnchanged -and $CompanionUnchanged) {
        Remove-Item -LiteralPath $TempBase -Recurse -Force
        Write-Host "P6_03_DISPOSABLE_ARTIFACTS_REMOVED=true"
        Write-Host "P6_03_DISPOSABLE_IMPLEMENTATION_QUALIFICATION=PASS"
    }
    else {
        Write-Host "P6_03_FAILURE_EVIDENCE_PRESERVED=$TempBase"
    }
}

if ($PythonExit -ne 0) {
    throw "STOP: P6-03 disposable corruption-preservation probe failed."
}

if ((& git -C $RepoRoot rev-parse HEAD).Trim() -ne $RepoHead) {
    throw "STOP: Orion HEAD changed during P6-03 qualification."
}
if ((Get-StatusText $RepoRoot) -ne $RepoStatusBefore) {
    throw "STOP: Orion worktree changed during P6-03 qualification."
}
if ((& git -C $HermesRoot rev-parse HEAD).Trim() -ne $HermesHeadBefore) {
    throw "STOP: installed Hermes HEAD changed during P6-03 qualification."
}
if ((Get-StatusText $HermesRoot) -ne $HermesStatusBefore) {
    throw "STOP: installed Hermes worktree changed during P6-03 qualification."
}
if (((Get-CronMetadata $CompanionCron) -join [Environment]::NewLine) -ne ($CompanionBefore -join [Environment]::NewLine)) {
    throw "STOP: COMPANION cron metadata changed during P6-03 qualification."
}
