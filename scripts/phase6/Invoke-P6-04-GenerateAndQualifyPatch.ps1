param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04_GENERATE_AND_QUALIFY"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"

if ($AuthorizationToken -ne $ExpectedToken) { throw "STOP: explicit P6-04 generate-and-qualify authorization is required." }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionCron = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\cron"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$P603Probe = Join-Path $PSScriptRoot "p6-03-disposable-corruption-preservation.py"
$P604Probe = Join-Path $PSScriptRoot "p6-04-disposable-run-evidence-qualification.py"
$Transformer = Join-Path $PSScriptRoot "p6-04-build-disposable-source.py"
$P603Patch = Join-Path $RepoRoot "compat\hermes\p6-03-jobs-corruption-preservation.patch"
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
    $Text = [System.IO.File]::ReadAllText($Source)
    $Text = $Text.Replace("`r`n", "`n")
    if ($Text.Contains("`r")) { throw "STOP: patch contains a bare CR byte: $Source" }
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Destination, $Text, $Utf8NoBom)
}
function Init-BaselineRepo([string]$SourceRoot) {
    & git -C $SourceRoot init -q
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to initialize disposable git repository." }
    & git -C $SourceRoot add cron/jobs.py cron/executions.py cron/scheduler.py
    & git -C $SourceRoot -c user.name=Orion-P6-04 -c user.email=orion-p6-04@local commit -q -m "baseline"
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to commit disposable baseline." }
}
function Apply-P603Baseline([string]$SourceRoot, [string]$PatchPath) {
    & git -C $SourceRoot apply --check $PatchPath
    if ($LASTEXITCODE -ne 0) { throw "STOP: P6-03 compatibility patch no longer applies to accepted Hermes pin." }
    & git -C $SourceRoot apply $PatchPath
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to apply P6-03 patch in disposable source." }
    & git -C $SourceRoot add cron/jobs.py
    & git -C $SourceRoot -c user.name=Orion-P6-04 -c user.email=orion-p6-04@local commit -q -m "p6-03-qualified-baseline"
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to establish disposable P6-03 baseline." }
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot
$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusBefore = Get-StatusText $HermesRoot
$CompanionBefore = Get-CronMetadata $CompanionCron

if ($RepoBranch -ne $ExpectedBranch) { throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch" }
if ($RepoStatusBefore) { throw "STOP: Orion worktree must be clean before P6-04 patch generation." }
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

foreach ($Required in @($HermesPython, $P603Probe, $P604Probe, $Transformer, $P603Patch)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "STOP: required P6-04 generation input missing: $Required" }
}

$P603Attr = ((& git -C $RepoRoot check-attr eol -- "compat/hermes/p6-03-jobs-corruption-preservation.patch") -join "")
if ($P603Attr -notmatch "eol: lf$") { throw "STOP: P6-03 patch is not governed by eol=lf." }

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempBase = Join-Path $env:TEMP "orion-p6-04-generate-$Stamp"
$SourceA = Join-Path $TempBase "source-tested"
$SourceB = Join-Path $TempBase "source-roundtrip"
$HomeA = Join-Path $TempBase "home-tested"
$HomeB = Join-Path $TempBase "home-roundtrip"
$HomeP603 = Join-Path $TempBase "home-p603-regression"
$ArchivePath = Join-Path $TempBase "hermes-source.tar"
$P603Normalized = Join-Path $TempBase "p6-03.lf.patch"
$CandidatePatch = Join-Path $TempBase "p6-04-durable-run-evidence.git-generated.patch"

New-Item -ItemType Directory -Path $SourceA -Force | Out-Null
New-Item -ItemType Directory -Path $SourceB -Force | Out-Null
New-Item -ItemType Directory -Path $HomeA -Force | Out-Null
New-Item -ItemType Directory -Path $HomeB -Force | Out-Null
New-Item -ItemType Directory -Path $HomeP603 -Force | Out-Null
Write-LfCopy $P603Patch $P603Normalized

Write-Host "P6_04_GENERATE_REPO_BRANCH=$RepoBranch"
Write-Host "P6_04_GENERATE_REPO_HEAD=$RepoHead"
Write-Host "P6_04_GENERATE_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_GENERATE_INSTALLED_P603_JOBS_SHA256=$InstalledJobsSha"
Write-Host "P6_04_GENERATE_INSTALLED_HERMES_MUTATION_AUTHORIZED=false"
Write-Host "P6_04_GENERATE_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_04_GENERATE_LIVE_JOB_AUTHORIZED=false"

& git -C $HermesRoot archive --format=tar --output=$ArchivePath $ExpectedHermesHead
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to archive pinned Hermes source." }
& tar -xf $ArchivePath -C $SourceA
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to extract tested disposable source." }
& tar -xf $ArchivePath -C $SourceB
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to extract round-trip disposable source." }

Init-BaselineRepo $SourceA
Apply-P603Baseline $SourceA $P603Normalized

& $HermesPython -B $Transformer --source-root $SourceA
if ($LASTEXITCODE -ne 0) { throw "STOP: deterministic P6-04 source transformation failed." }

& git -C $SourceA diff --check
if ($LASTEXITCODE -ne 0) { throw "STOP: transformed P6-04 source contains whitespace errors." }
$ChangedA = @(& git -C $SourceA diff --name-only)
$ChangedA = @($ChangedA | Where-Object { $_ -ne "" } | Sort-Object)
$ExpectedChanged = @("cron/executions.py", "cron/scheduler.py")
if (($ChangedA -join "`n") -ne ($ExpectedChanged -join "`n")) { throw "STOP: transformed source scope drift: $($ChangedA -join ', ')" }
Write-Host "P6_04_GENERATE_TRANSFORM_SCOPE=cron/executions.py,cron/scheduler.py"

& $HermesPython -B $P604Probe --source-root $SourceA --disposable-home $HomeA --prepatched
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04 qualification failed on directly transformed source." }
Write-Host "P6_04_GENERATE_TESTED_SOURCE_QUALIFICATION=PASS"

$ExecShaA = (Get-FileHash -LiteralPath (Join-Path $SourceA "cron\executions.py") -Algorithm SHA256).Hash.ToLowerInvariant()
$SchedShaA = (Get-FileHash -LiteralPath (Join-Path $SourceA "cron\scheduler.py") -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_04_GENERATE_TESTED_EXECUTIONS_SHA256=$ExecShaA"
Write-Host "P6_04_GENERATE_TESTED_SCHEDULER_SHA256=$SchedShaA"

& git -C $SourceA diff --patch --binary --full-index --no-ext-diff --output=$CandidatePatch -- cron/executions.py cron/scheduler.py
if ($LASTEXITCODE -ne 0) { throw "STOP: git failed to generate P6-04 patch." }
if (-not (Test-Path -LiteralPath $CandidatePatch)) { throw "STOP: git-generated P6-04 patch is missing." }
$CandidateBytes = [System.IO.File]::ReadAllBytes($CandidatePatch)
if ($CandidateBytes.Length -eq 0) { throw "STOP: git-generated P6-04 patch is empty." }
$CandidateCrBytes = @($CandidateBytes | Where-Object { $_ -eq 13 }).Count
if ($CandidateCrBytes -ne 0) { throw "STOP: git-generated P6-04 patch contains CR bytes." }
$CandidateSha = (Get-FileHash -LiteralPath $CandidatePatch -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_04_GENERATE_PATCH_METHOD=git_diff_patch"
Write-Host "P6_04_GENERATE_PATCH_SHA256=$CandidateSha"
Write-Host "P6_04_GENERATE_PATCH_CR_BYTES=$CandidateCrBytes"

Init-BaselineRepo $SourceB
Apply-P603Baseline $SourceB $P603Normalized

& git -C $SourceB apply --check $CandidatePatch
if ($LASTEXITCODE -ne 0) { throw "STOP: git-generated P6-04 patch failed fresh-tree apply check." }
Write-Host "P6_04_GENERATE_ROUNDTRIP_APPLY_CHECK=PASS"
& git -C $SourceB apply $CandidatePatch
if ($LASTEXITCODE -ne 0) { throw "STOP: git-generated P6-04 patch failed fresh-tree application." }
& git -C $SourceB diff --check
if ($LASTEXITCODE -ne 0) { throw "STOP: round-trip P6-04 source contains whitespace errors." }

$ChangedB = @(& git -C $SourceB diff --name-only)
$ChangedB = @($ChangedB | Where-Object { $_ -ne "" } | Sort-Object)
if (($ChangedB -join "`n") -ne ($ExpectedChanged -join "`n")) { throw "STOP: round-trip source scope drift: $($ChangedB -join ', ')" }

$ExecShaB = (Get-FileHash -LiteralPath (Join-Path $SourceB "cron\executions.py") -Algorithm SHA256).Hash.ToLowerInvariant()
$SchedShaB = (Get-FileHash -LiteralPath (Join-Path $SourceB "cron\scheduler.py") -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_04_GENERATE_ROUNDTRIP_EXECUTIONS_SHA256=$ExecShaB"
Write-Host "P6_04_GENERATE_ROUNDTRIP_SCHEDULER_SHA256=$SchedShaB"
if ($ExecShaB -ne $ExecShaA -or $SchedShaB -ne $SchedShaA) { throw "STOP: generated patch did not reproduce the exact tested source hashes." }
Write-Host "P6_04_GENERATE_SOURCE_HASH_ROUNDTRIP=PASS"

& $HermesPython -B $P604Probe --source-root $SourceB --disposable-home $HomeB --prepatched
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04 qualification failed after patch round trip." }
Write-Host "P6_04_GENERATE_ROUNDTRIP_P604_QUALIFICATION=PASS"

& $HermesPython -B $P603Probe --source-root $SourceB --disposable-home $HomeP603 --prepatched
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-03 regression qualification failed on combined round-trip source." }
Write-Host "P6_04_GENERATE_P603_REGRESSION=PASS"

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusText $HermesRoot
$CompanionAfter = Get-CronMetadata $CompanionCron

if ($RepoHeadAfter -ne $RepoHead -or $RepoStatusAfter -ne $RepoStatusBefore) { throw "STOP: Orion repository changed during P6-04 generation." }
if ($HermesHeadAfter -ne $HermesHeadBefore -or $HermesStatusAfter -ne $HermesStatusBefore) { throw "STOP: installed Hermes changed during P6-04 generation." }
if (($CompanionAfter -join [Environment]::NewLine) -ne ($CompanionBefore -join [Environment]::NewLine)) { throw "STOP: COMPANION cron metadata changed during P6-04 generation." }

Write-Host "P6_04_GENERATE_ORION_UNCHANGED=true"
Write-Host "P6_04_GENERATE_HERMES_UNCHANGED=true"
Write-Host "P6_04_GENERATE_COMPANION_CRON_UNCHANGED=true"
Write-Host "P6_04_GENERATE_PATCH_FILE=$CandidatePatch"
Write-Host "P6_04_GENERATE_FAILURE_ARTIFACTS_REMOVED=false"
Write-Host "P6_04_GENERATE_AND_QUALIFY=PASS"
