param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_COMPAT_PATCH_REVIEW"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 compatibility patch review authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionCron = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\cron"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Probe = Join-Path $PSScriptRoot "p6-03-disposable-corruption-preservation.py"
$Patch = Join-Path $RepoRoot "compat\hermes\p6-03-jobs-corruption-preservation.patch"

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
    throw "STOP: Orion worktree must be clean before P6-03 compatibility patch review."
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
if (-not (Test-Path -LiteralPath $Patch)) {
    throw "STOP: P6-03 compatibility patch not found: $Patch"
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempBase = Join-Path $env:TEMP "orion-p6-03-compat-$Stamp"
$SourceRoot = Join-Path $TempBase "hermes-source"
$DisposableHome = Join-Path $TempBase "hermes-home"
$ArchivePath = Join-Path $TempBase "hermes-source.tar"

New-Item -ItemType Directory -Path $SourceRoot -Force | Out-Null
New-Item -ItemType Directory -Path $DisposableHome -Force | Out-Null

Write-Host "P6_03_COMPAT_REPO_BRANCH=$RepoBranch"
Write-Host "P6_03_COMPAT_REPO_HEAD=$RepoHead"
Write-Host "P6_03_COMPAT_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_03_COMPAT_PATCH=$Patch"
Write-Host "P6_03_COMPAT_INSTALLED_HERMES_MUTATION_AUTHORIZED=false"
Write-Host "P6_03_COMPAT_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_03_COMPAT_DISPOSABLE_SOURCE=$SourceRoot"
Write-Host "P6_03_COMPAT_DISPOSABLE_HOME=$DisposableHome"

& git -C $HermesRoot archive --format=tar --output=$ArchivePath $ExpectedHermesHead
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to archive pinned Hermes source."
}
& tar -xf $ArchivePath -C $SourceRoot
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to extract disposable Hermes source archive."
}

& git -C $SourceRoot init -q
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to initialize disposable review repository."
}
& git -C $SourceRoot add cron/jobs.py
& git -C $SourceRoot -c user.name=Orion-P6-03 -c user.email=orion-p6-03@local commit -q -m "baseline"
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to commit disposable baseline."
}

& git -C $SourceRoot apply --check $Patch
if ($LASTEXITCODE -ne 0) {
    throw "STOP: source-controlled P6-03 patch does not apply cleanly to accepted Hermes pin."
}
Write-Host "P6_03_COMPAT_GIT_APPLY_CHECK=PASS"

& git -C $SourceRoot apply $Patch
if ($LASTEXITCODE -ne 0) {
    throw "STOP: source-controlled P6-03 patch apply failed."
}

& git -C $SourceRoot diff --check
if ($LASTEXITCODE -ne 0) {
    throw "STOP: source-controlled P6-03 patch introduced whitespace errors."
}
Write-Host "P6_03_COMPAT_DIFF_CHECK=PASS"

$Changed = @(& git -C $SourceRoot diff --name-only)
if ($LASTEXITCODE -ne 0) {
    throw "STOP: could not inspect compatibility patch scope."
}
$Changed = @($Changed | Where-Object { $_ -ne "" })
if ($Changed.Count -ne 1 -or $Changed[0] -ne "cron/jobs.py") {
    throw "STOP: compatibility patch scope drift: $($Changed -join ', ')"
}
Write-Host "P6_03_COMPAT_CHANGED_FILES=cron/jobs.py"

$PythonExit = 1
try {
    & $HermesPython $Probe --source-root $SourceRoot --disposable-home $DisposableHome --prepatched
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

    Write-Host "P6_03_COMPAT_PYTHON_EXIT_CODE=$PythonExit"
    Write-Host "P6_03_COMPAT_ORION_HEAD_UNCHANGED=$RepoHeadUnchanged"
    Write-Host "P6_03_COMPAT_ORION_WORKTREE_UNCHANGED=$RepoWorktreeUnchanged"
    Write-Host "P6_03_COMPAT_HERMES_HEAD_UNCHANGED=$HermesHeadUnchanged"
    Write-Host "P6_03_COMPAT_HERMES_WORKTREE_UNCHANGED=$HermesWorktreeUnchanged"
    Write-Host "P6_03_COMPAT_COMPANION_CRON_UNCHANGED=$CompanionUnchanged"

    if ($PythonExit -eq 0 -and $RepoHeadUnchanged -and $RepoWorktreeUnchanged -and $HermesHeadUnchanged -and $HermesWorktreeUnchanged -and $CompanionUnchanged) {
        Remove-Item -LiteralPath $TempBase -Recurse -Force
        Write-Host "P6_03_COMPAT_DISPOSABLE_ARTIFACTS_REMOVED=true"
        Write-Host "P6_03_COMPAT_PATCH_REVIEW=PASS"
    }
    else {
        Write-Host "P6_03_COMPAT_FAILURE_EVIDENCE_PRESERVED=$TempBase"
    }
}

if ($PythonExit -ne 0) {
    throw "STOP: P6-03 source-controlled compatibility patch qualification failed."
}
