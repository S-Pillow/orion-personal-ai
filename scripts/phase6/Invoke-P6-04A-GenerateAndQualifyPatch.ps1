param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04A_GENERATE_AND_QUALIFY"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedP603JobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$ExpectedP604ExecutionsSha256 = "a7a146921af20f97594258f4672c68e0c4955e7c1a1b361e857be8b4e470d208"
$ExpectedP604SchedulerSha256 = "6c0a43c175aab8e7d2a0107f6b067bcfa42f9a55650ab8cc761824c37fb02bfe"
$ExpectedP604Columns = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error,scheduled_at,delivery_outcome"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-04A generate-and-qualify authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"

$P603Patch = Join-Path $RepoRoot "compat\hermes\p6-03-jobs-corruption-preservation.patch"
$P604Patch = Join-Path $RepoRoot "compat\hermes\p6-04-durable-run-evidence.patch"
$Transformer = Join-Path $PSScriptRoot "p6-04a-build-disposable-source.py"
$P604AProbe = Join-Path $PSScriptRoot "p6-04a-disposable-error-classification-qualification.py"
$P604Probe = Join-Path $PSScriptRoot "p6-04-disposable-run-evidence-qualification.py"
$P603Probe = Join-Path $PSScriptRoot "p6-03-disposable-corruption-preservation.py"
$StateProbe = Join-Path $PSScriptRoot "p6-04-production-state-probe.py"

$InstalledJobs = Join-Path $HermesRoot "cron\jobs.py"
$InstalledExecutions = Join-Path $HermesRoot "cron\executions.py"
$InstalledScheduler = Join-Path $HermesRoot "cron\scheduler.py"

function Get-StatusText([string]$Root) {
    return ((& git -C $Root status --porcelain=v1) -join [Environment]::NewLine)
}

function Get-CronMetadata([string]$CronPath) {
    if (-not (Test-Path -LiteralPath $CronPath)) { return @() }
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

function Write-LfCopy([string]$Source, [string]$Destination) {
    $Text = [System.IO.File]::ReadAllText($Source)
    $Text = $Text.Replace("`r`n", "`n")
    if ($Text.Contains("`r")) {
        throw "STOP: patch contains a bare CR byte: $Source"
    }
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Destination, $Text, $Utf8NoBom)
}

function Init-Repo([string]$SourceRoot) {
    & git -C $SourceRoot init -q
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to initialize disposable git repository." }
    & git -C $SourceRoot add .
    & git -C $SourceRoot -c user.name=Orion-P6-04A -c user.email=orion-p6-04a@local commit -q -m "accepted-hermes-pin"
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to commit accepted Hermes baseline." }
}

function Apply-QualifiedBaseline([string]$SourceRoot, [string]$P603, [string]$P604) {
    & git -C $SourceRoot apply --check $P603
    if ($LASTEXITCODE -ne 0) { throw "STOP: P6-03 patch no longer applies to accepted Hermes pin." }
    & git -C $SourceRoot apply $P603
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to apply P6-03 baseline patch." }

    & git -C $SourceRoot apply --check $P604
    if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04 patch no longer applies after P6-03 baseline." }
    & git -C $SourceRoot apply $P604
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to apply P6-04 baseline patch." }

    & git -C $SourceRoot add .
    & git -C $SourceRoot -c user.name=Orion-P6-04A -c user.email=orion-p6-04a@local commit -q -m "accepted-p6-03-p6-04-baseline"
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to commit P6-03/P6-04 disposable baseline." }
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot
$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusBefore = Get-StatusText $HermesRoot
$CompanionBefore = Get-CronMetadata $CompanionCron

if ($RepoBranch -ne $ExpectedBranch) { throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch" }
if ($RepoStatusBefore) { throw "STOP: Orion worktree must be clean before P6-04A generation." }
if ($HermesHeadBefore -ne $ExpectedHermesHead) { throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore" }

$ExpectedHermesStatus = @(
    " M cron/executions.py",
    " M cron/jobs.py",
    " M cron/scheduler.py",
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
) -join [Environment]::NewLine

if ($HermesStatusBefore -ne $ExpectedHermesStatus) {
    throw "STOP: installed Hermes worktree differs from accepted P6-04 live state."
}

$InstalledJobsSha = (Get-FileHash -LiteralPath $InstalledJobs -Algorithm SHA256).Hash.ToLowerInvariant()
$InstalledExecutionsSha = (Get-FileHash -LiteralPath $InstalledExecutions -Algorithm SHA256).Hash.ToLowerInvariant()
$InstalledSchedulerSha = (Get-FileHash -LiteralPath $InstalledScheduler -Algorithm SHA256).Hash.ToLowerInvariant()

if ($InstalledJobsSha -ne $ExpectedP603JobsSha256) { throw "STOP: installed P6-03 jobs.py hash drift." }
if ($InstalledExecutionsSha -ne $ExpectedP604ExecutionsSha256) { throw "STOP: installed P6-04 executions.py hash drift." }
if ($InstalledSchedulerSha -ne $ExpectedP604SchedulerSha256) { throw "STOP: installed P6-04 scheduler.py hash drift." }

foreach ($Required in @($HermesPython, $P603Patch, $P604Patch, $Transformer, $P604AProbe, $P604Probe, $P603Probe)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        throw "STOP: required P6-04A generation input missing: $Required"
    }
}

foreach ($PatchRel in @(
    "compat/hermes/p6-03-jobs-corruption-preservation.patch",
    "compat/hermes/p6-04-durable-run-evidence.patch"
)) {
    $Attr = ((& git -C $RepoRoot check-attr eol -- $PatchRel) -join "")
    if ($Attr -notmatch "eol: lf$") {
        throw "STOP: qualified baseline patch is not governed by eol=lf: $PatchRel"
    }
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempBase = Join-Path $env:TEMP "orion-p6-04a-generate-$Stamp"
$SourceA = Join-Path $TempBase "source-tested"
$SourceB = Join-Path $TempBase "source-roundtrip"
$HomeA = Join-Path $TempBase "home-p604a-tested"
$HomeB = Join-Path $TempBase "home-p604a-roundtrip"
$HomeP604 = Join-Path $TempBase "home-p604-regression"
$HomeP603 = Join-Path $TempBase "home-p603-regression"
$ArchivePath = Join-Path $TempBase "hermes-source.tar"
$P603Normalized = Join-Path $TempBase "p6-03.lf.patch"
$P604Normalized = Join-Path $TempBase "p6-04.lf.patch"
$CandidatePatch = Join-Path $TempBase "p6-04a-durable-error-classification.git-generated.patch"

New-Item -ItemType Directory -Path $SourceA -Force | Out-Null
New-Item -ItemType Directory -Path $SourceB -Force | Out-Null
New-Item -ItemType Directory -Path $HomeA -Force | Out-Null
New-Item -ItemType Directory -Path $HomeB -Force | Out-Null
New-Item -ItemType Directory -Path $HomeP604 -Force | Out-Null
New-Item -ItemType Directory -Path $HomeP603 -Force | Out-Null

Write-LfCopy $P603Patch $P603Normalized
Write-LfCopy $P604Patch $P604Normalized

Write-Host "P6_04A_GENERATE_REPO_BRANCH=$RepoBranch"
Write-Host "P6_04A_GENERATE_REPO_HEAD=$RepoHead"
Write-Host "P6_04A_GENERATE_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04A_GENERATE_INSTALLED_P603_JOBS_SHA256=$InstalledJobsSha"
Write-Host "P6_04A_GENERATE_INSTALLED_P604_EXECUTIONS_SHA256=$InstalledExecutionsSha"
Write-Host "P6_04A_GENERATE_INSTALLED_P604_SCHEDULER_SHA256=$InstalledSchedulerSha"
Write-Host "P6_04A_GENERATE_INSTALLED_HERMES_MUTATION_AUTHORIZED=false"
Write-Host "P6_04A_GENERATE_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_04A_GENERATE_LIVE_JOB_AUTHORIZED=false"

& git -C $HermesRoot archive --format=tar --output=$ArchivePath $ExpectedHermesHead
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to archive pinned Hermes source." }
& tar -xf $ArchivePath -C $SourceA
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to extract tested disposable source." }
& tar -xf $ArchivePath -C $SourceB
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to extract round-trip disposable source." }

Init-Repo $SourceA
Apply-QualifiedBaseline $SourceA $P603Normalized $P604Normalized

& $HermesPython -B $Transformer --source-root $SourceA
if ($LASTEXITCODE -ne 0) { throw "STOP: deterministic P6-04A source transformation failed." }

& git -C $SourceA diff --check
if ($LASTEXITCODE -ne 0) { throw "STOP: transformed P6-04A source contains whitespace errors." }

$ChangedNamesA = @(
    & git -C $SourceA status --porcelain=v1 |
        ForEach-Object { $_.Substring(3) } |
        Sort-Object
)
$ExpectedChanged = @(
    "agent/monitoring/cron_health.py",
    "cron/error_classification.py",
    "cron/executions.py"
)
if (($ChangedNamesA -join [Environment]::NewLine) -ne ($ExpectedChanged -join [Environment]::NewLine)) {
    throw "STOP: transformed P6-04A source scope drift: $($ChangedNamesA -join ', ')"
}
Write-Host "P6_04A_GENERATE_TRANSFORM_SCOPE=agent/monitoring/cron_health.py,cron/error_classification.py,cron/executions.py"

& $HermesPython -B $P604AProbe --source-root $SourceA --disposable-home $HomeA --prepatched
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04A qualification failed on directly transformed source." }
Write-Host "P6_04A_GENERATE_TESTED_SOURCE_QUALIFICATION=PASS"

$HealthShaA = (Get-FileHash -LiteralPath (Join-Path $SourceA "agent\monitoring\cron_health.py") -Algorithm SHA256).Hash.ToLowerInvariant()
$ClassifierShaA = (Get-FileHash -LiteralPath (Join-Path $SourceA "cron\error_classification.py") -Algorithm SHA256).Hash.ToLowerInvariant()
$ExecShaA = (Get-FileHash -LiteralPath (Join-Path $SourceA "cron\executions.py") -Algorithm SHA256).Hash.ToLowerInvariant()

Write-Host "P6_04A_GENERATE_TESTED_CRON_HEALTH_SHA256=$HealthShaA"
Write-Host "P6_04A_GENERATE_TESTED_CLASSIFIER_SHA256=$ClassifierShaA"
Write-Host "P6_04A_GENERATE_TESTED_EXECUTIONS_SHA256=$ExecShaA"

# Mark the new classifier as intent-to-add so git diff includes it in the generated patch.
& git -C $SourceA add -N -- cron/error_classification.py
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to mark new classifier for patch generation." }

$DiffArgs = @(
    "-C", $SourceA,
    "diff", "--patch", "--binary", "--full-index", "--no-ext-diff",
    "--output=$CandidatePatch", "--",
    "agent/monitoring/cron_health.py",
    "cron/error_classification.py",
    "cron/executions.py"
)
& git @DiffArgs
if ($LASTEXITCODE -ne 0) { throw "STOP: git failed to generate P6-04A patch." }
if (-not (Test-Path -LiteralPath $CandidatePatch)) { throw "STOP: git-generated P6-04A patch is missing." }

$CandidateBytes = [System.IO.File]::ReadAllBytes($CandidatePatch)
if ($CandidateBytes.Length -eq 0) { throw "STOP: git-generated P6-04A patch is empty." }
$CandidateCrBytes = @($CandidateBytes | Where-Object { $_ -eq 13 }).Count
if ($CandidateCrBytes -ne 0) { throw "STOP: git-generated P6-04A patch contains CR bytes." }

$CandidateSha = (Get-FileHash -LiteralPath $CandidatePatch -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_04A_GENERATE_PATCH_METHOD=git_diff_patch"
Write-Host "P6_04A_GENERATE_PATCH_SHA256=$CandidateSha"
Write-Host "P6_04A_GENERATE_PATCH_CR_BYTES=$CandidateCrBytes"

Init-Repo $SourceB
Apply-QualifiedBaseline $SourceB $P603Normalized $P604Normalized

& git -C $SourceB apply --check $CandidatePatch
if ($LASTEXITCODE -ne 0) { throw "STOP: git-generated P6-04A patch failed fresh-tree apply check." }
Write-Host "P6_04A_GENERATE_ROUNDTRIP_APPLY_CHECK=PASS"

& git -C $SourceB apply $CandidatePatch
if ($LASTEXITCODE -ne 0) { throw "STOP: git-generated P6-04A patch failed fresh-tree application." }

& git -C $SourceB diff --check
if ($LASTEXITCODE -ne 0) { throw "STOP: round-trip P6-04A source contains whitespace errors." }

$ChangedNamesB = @(
    & git -C $SourceB status --porcelain=v1 |
        ForEach-Object { $_.Substring(3) } |
        Sort-Object
)
if (($ChangedNamesB -join [Environment]::NewLine) -ne ($ExpectedChanged -join [Environment]::NewLine)) {
    throw "STOP: round-trip P6-04A source scope drift: $($ChangedNamesB -join ', ')"
}

$HealthShaB = (Get-FileHash -LiteralPath (Join-Path $SourceB "agent\monitoring\cron_health.py") -Algorithm SHA256).Hash.ToLowerInvariant()
$ClassifierShaB = (Get-FileHash -LiteralPath (Join-Path $SourceB "cron\error_classification.py") -Algorithm SHA256).Hash.ToLowerInvariant()
$ExecShaB = (Get-FileHash -LiteralPath (Join-Path $SourceB "cron\executions.py") -Algorithm SHA256).Hash.ToLowerInvariant()

Write-Host "P6_04A_GENERATE_ROUNDTRIP_CRON_HEALTH_SHA256=$HealthShaB"
Write-Host "P6_04A_GENERATE_ROUNDTRIP_CLASSIFIER_SHA256=$ClassifierShaB"
Write-Host "P6_04A_GENERATE_ROUNDTRIP_EXECUTIONS_SHA256=$ExecShaB"

if ($HealthShaB -ne $HealthShaA -or $ClassifierShaB -ne $ClassifierShaA -or $ExecShaB -ne $ExecShaA) {
    throw "STOP: generated P6-04A patch did not reproduce exact tested source hashes."
}
Write-Host "P6_04A_GENERATE_SOURCE_HASH_ROUNDTRIP=PASS"

& $HermesPython -B $P604AProbe --source-root $SourceB --disposable-home $HomeB --prepatched
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04A qualification failed after patch round trip." }
Write-Host "P6_04A_GENERATE_ROUNDTRIP_P604A_QUALIFICATION=PASS"

& $HermesPython -B $P604Probe --source-root $SourceB --disposable-home $HomeP604 --prepatched
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04 regression qualification failed on P6-04A combined source." }
Write-Host "P6_04A_GENERATE_P604_REGRESSION=PASS"

& $HermesPython -B $P603Probe --source-root $SourceB --disposable-home $HomeP603 --prepatched
if ($LASTEXITCODE -ne 0) { throw "STOP: P6-03 regression qualification failed on P6-04A combined source." }
Write-Host "P6_04A_GENERATE_P603_REGRESSION=PASS"

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusText $HermesRoot
$CompanionAfter = Get-CronMetadata $CompanionCron

if ($RepoHeadAfter -ne $RepoHead -or $RepoStatusAfter -ne $RepoStatusBefore) {
    throw "STOP: Orion repository changed during P6-04A generation."
}
if ($HermesHeadAfter -ne $HermesHeadBefore -or $HermesStatusAfter -ne $HermesStatusBefore) {
    throw "STOP: installed Hermes changed during P6-04A generation."
}
if (($CompanionAfter -join [Environment]::NewLine) -ne ($CompanionBefore -join [Environment]::NewLine)) {
    throw "STOP: COMPANION cron metadata changed during P6-04A generation."
}

Write-Host "P6_04A_GENERATE_ORION_UNCHANGED=true"
Write-Host "P6_04A_GENERATE_HERMES_UNCHANGED=true"
Write-Host "P6_04A_GENERATE_COMPANION_CRON_UNCHANGED=true"
Write-Host "P6_04A_GENERATE_PATCH_FILE=$CandidatePatch"
Write-Host "P6_04A_GENERATE_FAILURE_ARTIFACTS_REMOVED=false"
Write-Host "P6_04A_GENERATE_AND_QUALIFY=PASS"
