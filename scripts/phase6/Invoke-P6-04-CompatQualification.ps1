param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04_COMPAT_QUALIFICATION"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"

if ($AuthorizationToken -ne $ExpectedToken) { throw "STOP: explicit P6-04 compatibility qualification authorization is required." }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionCron = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\cron"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$P603Probe = Join-Path $PSScriptRoot "p6-03-disposable-corruption-preservation.py"
$P604Probe = Join-Path $PSScriptRoot "p6-04-disposable-run-evidence-qualification.py"
$P603Patch = Join-Path $RepoRoot "compat\hermes\p6-03-jobs-corruption-preservation.patch"
$P604Patch = Join-Path $RepoRoot "compat\hermes\p6-04-durable-run-evidence.patch"
$InstalledJobs = Join-Path $HermesRoot "cron\jobs.py"

function Get-StatusText([string]$Root) { return ((& git -C $Root status --porcelain=v1) -join [Environment]::NewLine) }
function Get-CronMetadata([string]$CronPath) {
    if (-not (Test-Path -LiteralPath $CronPath)) { return @() }
    return @(Get-ChildItem -LiteralPath $CronPath -Force | Sort-Object Name | ForEach-Object {
        $Type = if ($_.PSIsContainer) { "DIR" } else { "FILE" }
        $Length = if ($_.PSIsContainer) { 0 } else { $_.Length }
        "{0}|{1}|{2}|{3}" -f $_.Name, $Type, $Length, $_.LastWriteTimeUtc.Ticks
    })
}
function Write-LfCopy([string]$Source, [string]$Destination) {
    $Bytes = [System.IO.File]::ReadAllBytes($Source)
    $CrBytes = @($Bytes | Where-Object { $_ -eq 13 }).Count
    $Text = [System.IO.File]::ReadAllText($Source)
    $Text = $Text.Replace("`r`n", "`n")
    if ($Text.Contains("`r")) { throw "STOP: patch contains a bare CR byte: $Source" }
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Destination, $Text, $Utf8NoBom)
    return $CrBytes
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot
$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusBefore = Get-StatusText $HermesRoot
$CompanionBefore = Get-CronMetadata $CompanionCron

if ($RepoBranch -ne $ExpectedBranch) { throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch" }
if ($RepoStatusBefore) { throw "STOP: Orion worktree must be clean before P6-04 compatibility qualification." }
if ($HermesHeadBefore -ne $ExpectedHermesHead) { throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore" }

$ExpectedHermesStatus = @(
    " M cron/jobs.py",
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
) -join [Environment]::NewLine
if ($HermesStatusBefore -ne $ExpectedHermesStatus) { throw "STOP: installed Hermes worktree differs from the accepted P6-03 compatibility state." }

$InstalledJobsSha = (Get-FileHash -LiteralPath $InstalledJobs -Algorithm SHA256).Hash.ToLowerInvariant()
if ($InstalledJobsSha -ne $ExpectedPatchedJobsSha256) { throw "STOP: installed P6-03 jobs.py hash drift." }

foreach ($Required in @($HermesPython, $P603Probe, $P604Probe, $P603Patch, $P604Patch)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "STOP: required P6-04 qualification input missing: $Required" }
}

$P603Attr = ((& git -C $RepoRoot check-attr eol -- "compat/hermes/p6-03-jobs-corruption-preservation.patch") -join "")
$P604Attr = ((& git -C $RepoRoot check-attr eol -- "compat/hermes/p6-04-durable-run-evidence.patch") -join "")
if ($P603Attr -notmatch "eol: lf$") { throw "STOP: P6-03 patch is not governed by eol=lf." }
if ($P604Attr -notmatch "eol: lf$") { throw "STOP: P6-04 patch is not governed by eol=lf." }

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempBase = Join-Path $env:TEMP "orion-p6-04-compat-$Stamp"
$SourceRoot = Join-Path $TempBase "hermes-source"
$P603Home = Join-Path $TempBase "p6-03-home"
$P604Home = Join-Path $TempBase "p6-04-home"
$ArchivePath = Join-Path $TempBase "hermes-source.tar"
$P603Normalized = Join-Path $TempBase "p6-03.lf.patch"
$P604Normalized = Join-Path $TempBase "p6-04.lf.patch"

New-Item -ItemType Directory -Path $SourceRoot -Force | Out-Null
New-Item -ItemType Directory -Path $P603Home -Force | Out-Null
New-Item -ItemType Directory -Path $P604Home -Force | Out-Null

$P603Cr = Write-LfCopy $P603Patch $P603Normalized
$P604Cr = Write-LfCopy $P604Patch $P604Normalized

Write-Host "P6_04_COMPAT_REPO_BRANCH=$RepoBranch"
Write-Host "P6_04_COMPAT_REPO_HEAD=$RepoHead"
Write-Host "P6_04_COMPAT_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_COMPAT_INSTALLED_P603_JOBS_SHA256=$InstalledJobsSha"
Write-Host "P6_04_COMPAT_P603_PATCH_CR_BYTES=$P603Cr"
Write-Host "P6_04_COMPAT_P604_PATCH_CR_BYTES=$P604Cr"
Write-Host "P6_04_COMPAT_INSTALLED_HERMES_MUTATION_AUTHORIZED=false"
Write-Host "P6_04_COMPAT_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_04_COMPAT_LIVE_JOB_AUTHORIZED=false"

& git -C $HermesRoot archive --format=tar --output=$ArchivePath $ExpectedHermesHead
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to archive pinned Hermes source." }
& tar -xf $ArchivePath -C $SourceRoot
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to extract disposable Hermes source archive." }

& git -C $SourceRoot init -q
& git -C $SourceRoot add cron/jobs.py cron/executions.py cron/scheduler.py
& git -C $SourceRoot -c user.name=Orion-P6-04 -c user.email=orion-p6-04@local commit -q -m "baseline"
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to commit disposable baseline." }

& git -C $SourceRoot apply --check $P603Normalized
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-03 compatibility patch no longer applies to accepted Hermes pin." }
& git -C $SourceRoot apply $P603Normalized
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to apply P6-03 patch in disposable source." }
& git -C $SourceRoot add cron/jobs.py
& git -C $SourceRoot -c user.name=Orion-P6-04 -c user.email=orion-p6-04@local commit -q -m "p6-03-qualified-baseline"
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to establish disposable P6-03 baseline." }

& git -C $SourceRoot apply --check $P604Normalized
if ($LASTEXITCODE -ne 0) { throw "STOP: source-controlled P6-04 patch does not apply cleanly after P6-03." }
Write-Host "P6_04_COMPAT_GIT_APPLY_CHECK=PASS"
& git -C $SourceRoot apply $P604Normalized
if ($LASTEXITCODE -ne 0) { throw "STOP: source-controlled P6-04 patch apply failed." }

& git -C $SourceRoot diff --check
if ($LASTEXITCODE -ne 0) { throw "STOP: source-controlled P6-04 patch introduced whitespace errors." }
Write-Host "P6_04_COMPAT_DIFF_CHECK=PASS"

$Changed = @(& git -C $SourceRoot diff --name-only)
$Changed = @($Changed | Where-Object { $_ -ne "" } | Sort-Object)
$ExpectedChanged = @("cron/executions.py", "cron/scheduler.py")
if (($Changed -join "`n") -ne ($ExpectedChanged -join "`n")) { throw "STOP: P6-04 patch scope drift: $($Changed -join ', ')" }
Write-Host "P6_04_COMPAT_CHANGED_FILES=cron/executions.py,cron/scheduler.py"

$P604Exit = 1
$P603Exit = 1
try {
    & $HermesPython -B $P604Probe --source-root $SourceRoot --disposable-home $P604Home --prepatched
    $P604Exit = $LASTEXITCODE
    if ($P604Exit -ne 0) { throw "STOP: P6-04 disposable qualification failed." }

    & $HermesPython -B $P603Probe --source-root $SourceRoot --disposable-home $P603Home --prepatched
    $P603Exit = $LASTEXITCODE
    if ($P603Exit -ne 0) { throw "STOP: P6-03 regression qualification failed on combined source." }
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

    Write-Host "P6_04_COMPAT_P604_EXIT_CODE=$P604Exit"
    Write-Host "P6_04_COMPAT_P603_REGRESSION_EXIT_CODE=$P603Exit"
    Write-Host "P6_04_COMPAT_ORION_HEAD_UNCHANGED=$RepoHeadUnchanged"
    Write-Host "P6_04_COMPAT_ORION_WORKTREE_UNCHANGED=$RepoWorktreeUnchanged"
    Write-Host "P6_04_COMPAT_HERMES_HEAD_UNCHANGED=$HermesHeadUnchanged"
    Write-Host "P6_04_COMPAT_HERMES_WORKTREE_UNCHANGED=$HermesWorktreeUnchanged"
    Write-Host "P6_04_COMPAT_COMPANION_CRON_UNCHANGED=$CompanionUnchanged"

    if ($P604Exit -eq 0 -and $P603Exit -eq 0 -and $RepoHeadUnchanged -and $RepoWorktreeUnchanged -and $HermesHeadUnchanged -and $HermesWorktreeUnchanged -and $CompanionUnchanged) {
        Remove-Item -LiteralPath $TempBase -Recurse -Force
        Write-Host "P6_04_COMPAT_DISPOSABLE_ARTIFACTS_REMOVED=true"
        Write-Host "P6_04_COMPAT_QUALIFICATION=PASS"
    } else {
        Write-Host "P6_04_COMPAT_FAILURE_EVIDENCE_PRESERVED=$TempBase"
    }
}

if ($P604Exit -ne 0 -or $P603Exit -ne 0) { throw "STOP: P6-04 compatibility qualification failed." }
