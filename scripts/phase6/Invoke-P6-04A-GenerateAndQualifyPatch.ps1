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

function Invoke-StateProbe {
    $Output = @(& $HermesPython -B $StateProbe --companion-home $CompanionHome)
    if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04 production state probe failed." }
    return $Output
}

function Get-ProbeValue([string[]]$Output, [string]$Key) {
    $Prefix = $Key + "="
    $Line = @($Output | Where-Object { $_.StartsWith($Prefix) })
    if ($Line.Count -ne 1) { throw "STOP: expected exactly one $Key line from state probe." }
    return $Line[0].Substring($Prefix.Length)
}

function Get-CompanionLogicalState([string[]]$ProbeOutput, [string]$Label) {
    $JobCount = [int](Get-ProbeValue $ProbeOutput "P6_04_PROD_STATE_JOB_COUNT")
    $DbPresent = Get-ProbeValue $ProbeOutput "P6_04_PROD_STATE_EXECUTIONS_DB_PRESENT"
    $Rows = [int](Get-ProbeValue $ProbeOutput "P6_04_PROD_STATE_EXECUTION_ROWS")
    $Columns = Get-ProbeValue $ProbeOutput "P6_04_PROD_STATE_EXECUTION_COLUMNS"
    $Mode = Get-ProbeValue $ProbeOutput "P6_04_PROD_STATE_SQLITE_MODE"
    if ($JobCount -ne 0) { throw "STOP: $Label COMPANION job count is $JobCount; expected 0." }
    if ($DbPresent -ne "true") { throw "STOP: $Label COMPANION executions.db is missing." }
    if ($Rows -ne 0) { throw "STOP: $Label COMPANION execution row count is $Rows; expected 0." }
    if ($Columns -ne $ExpectedP604Columns) { throw "STOP: $Label COMPANION execution schema drift." }
    if ($Mode -ne "read_only") { throw "STOP: $Label state probe was not read-only." }
    return @{ JobCount = $JobCount; Rows = $Rows; Columns = $Columns; Mode = $Mode }
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

function Clone-AcceptedHermes([string]$Destination) {
    & git -c core.autocrlf=false clone --quiet --no-hardlinks $HermesRoot $Destination
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to create disposable local Hermes clone." }
    & git -C $Destination config core.autocrlf false
    & git -C $Destination config core.eol lf
    & git -C $Destination config user.name "Orion-P6-04A"
    & git -C $Destination config user.email "orion-p6-04a@local"
    & git -C $Destination checkout --quiet --detach $ExpectedHermesHead
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to check out accepted Hermes pin in disposable clone." }
    if ((& git -C $Destination rev-parse HEAD).Trim() -ne $ExpectedHermesHead) { throw "STOP: disposable clone did not resolve to accepted Hermes pin." }
    if (Get-StatusText $Destination) { throw "STOP: disposable accepted Hermes clone is not clean." }
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

    $BaselineChanged = @(& git -C $SourceRoot status --porcelain=v1 | ForEach-Object { $_.Substring(3) } | Sort-Object)
    $ExpectedBaselineChanged = @("cron/executions.py", "cron/jobs.py", "cron/scheduler.py")
    if (($BaselineChanged -join "`n") -ne ($ExpectedBaselineChanged -join "`n")) {
        throw "STOP: disposable P6-03/P6-04 baseline scope drift: $($BaselineChanged -join ', ')"
    }
    & git -C $SourceRoot add -- cron/jobs.py cron/executions.py cron/scheduler.py
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to stage disposable P6-03/P6-04 baseline." }
    & git -C $SourceRoot commit --quiet -m "accepted-p6-03-p6-04-baseline"
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed to commit P6-03/P6-04 disposable baseline." }
    return (& git -C $SourceRoot rev-parse HEAD).Trim()
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot
$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusBefore = Get-StatusText $HermesRoot

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

foreach ($Required in @($HermesPython, $P603Patch, $P604Patch, $Transformer, $P604AProbe, $P604Probe, $P603Probe, $StateProbe)) {
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

$StateBeforeOutput = Invoke-StateProbe
$StateBefore = Get-CompanionLogicalState $StateBeforeOutput "pre-generation"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempBase = Join-Path $env:TEMP "orion-p6-04a-generate-$Stamp"
$SourceA = Join-Path $TempBase "candidate"
$SourceB = Join-Path $TempBase "roundtrip"
$HomeA = Join-Path $TempBase "home-p604a-tested"
$HomeB = Join-Path $TempBase "home-p604a-roundtrip"
$HomeP604 = Join-Path $TempBase "home-p604-regression"
$HomeP603 = Join-Path $TempBase "home-p603-regression"
$P603Normalized = Join-Path $TempBase "p6-03.lf.patch"
$P604Normalized = Join-Path $TempBase "p6-04.lf.patch"
$CandidatePatch = Join-Path $TempBase "p6-04a-durable-error-classification.git-generated.patch"

New-Item -ItemType Directory -Path $TempBase -Force | Out-Null
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
Write-Host "P6_04A_GENERATE_COMPANION_JOB_COUNT_BEFORE=$($StateBefore.JobCount)"
Write-Host "P6_04A_GENERATE_COMPANION_EXECUTION_ROWS_BEFORE=$($StateBefore.Rows)"
Write-Host "P6_04A_GENERATE_COMPANION_EXECUTION_COLUMNS_BEFORE=$($StateBefore.Columns)"
Write-Host "P6_04A_GENERATE_INSTALLED_HERMES_MUTATION_AUTHORIZED=false"
Write-Host "P6_04A_GENERATE_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_04A_GENERATE_LIVE_JOB_AUTHORIZED=false"

Clone-AcceptedHermes $SourceA
$BaselineCommit = Apply-QualifiedBaseline $SourceA $P603Normalized $P604Normalized
Write-Host "P6_04A_GENERATE_BASELINE_COMMIT=$BaselineCommit"

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

& git -C $SourceA add -- agent/monitoring/cron_health.py cron/error_classification.py cron/executions.py
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to stage exact P6-04A candidate scope." }
$StagedNames = @(& git -C $SourceA diff --cached --name-only | Sort-Object)
if (($StagedNames -join "`n") -ne ($ExpectedChanged -join "`n")) {
    throw "STOP: staged P6-04A candidate scope drift: $($StagedNames -join ', ')"
}
& git -C $SourceA commit --quiet -m "candidate-p6-04a-durable-error-classification"
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to commit disposable P6-04A candidate." }
$CandidateCommit = (& git -C $SourceA rev-parse HEAD).Trim()
Write-Host "P6_04A_GENERATE_CANDIDATE_COMMIT=$CandidateCommit"
if (Get-StatusText $SourceA) { throw "STOP: disposable candidate clone is not clean after candidate commit." }

$DiffArgs = @(
    "-C", $SourceA,
    "diff", "--patch", "--binary", "--full-index", "--no-ext-diff",
    "--output=$CandidatePatch",
    $BaselineCommit,
    $CandidateCommit,
    "--",
    "agent/monitoring/cron_health.py",
    "cron/error_classification.py",
    "cron/executions.py"
)
& git @DiffArgs
if ($LASTEXITCODE -ne 0) { throw "STOP: git failed to generate commit-to-commit P6-04A patch." }
if (-not (Test-Path -LiteralPath $CandidatePatch)) { throw "STOP: commit-to-commit P6-04A patch is missing." }

$CandidateBytes = [System.IO.File]::ReadAllBytes($CandidatePatch)
if ($CandidateBytes.Length -eq 0) { throw "STOP: git-generated P6-04A patch is empty." }
$CandidateCrBytes = @($CandidateBytes | Where-Object { $_ -eq 13 }).Count
if ($CandidateCrBytes -ne 0) { throw "STOP: git-generated P6-04A patch contains CR bytes." }

$CandidateSha = (Get-FileHash -LiteralPath $CandidatePatch -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_04A_GENERATE_PATCH_METHOD=git_diff_commit_to_commit"
Write-Host "P6_04A_GENERATE_PATCH_SHA256=$CandidateSha"
Write-Host "P6_04A_GENERATE_PATCH_CR_BYTES=$CandidateCrBytes"

& git -c core.autocrlf=false clone --quiet --no-hardlinks $SourceA $SourceB
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to clone disposable candidate history for round-trip qualification." }
& git -C $SourceB config core.autocrlf false
& git -C $SourceB config core.eol lf
& git -C $SourceB checkout --quiet --detach $BaselineCommit
if ($LASTEXITCODE -ne 0) { throw "STOP: failed to check out disposable baseline commit for round-trip qualification." }
if (Get-StatusText $SourceB) { throw "STOP: round-trip baseline clone is not clean before patch application." }

& git -C $SourceB apply --check $CandidatePatch
if ($LASTEXITCODE -ne 0) { throw "STOP: commit-to-commit P6-04A patch failed fresh-baseline apply check." }
Write-Host "P6_04A_GENERATE_ROUNDTRIP_APPLY_CHECK=PASS"

& git -C $SourceB apply $CandidatePatch
if ($LASTEXITCODE -ne 0) { throw "STOP: commit-to-commit P6-04A patch failed fresh-baseline application." }

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
    throw "STOP: commit-to-commit P6-04A patch did not reproduce exact tested source hashes."
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
$StateAfterOutput = Invoke-StateProbe
$StateAfter = Get-CompanionLogicalState $StateAfterOutput "post-generation"

if ($RepoHeadAfter -ne $RepoHead -or $RepoStatusAfter -ne $RepoStatusBefore) {
    throw "STOP: Orion repository changed during P6-04A generation."
}
if ($HermesHeadAfter -ne $HermesHeadBefore) { throw "STOP: installed Hermes HEAD changed during P6-04A generation." }
Assert-StatusEquals (Get-StatusLines $HermesRoot) $ExpectedHermesStatus "post-generation Hermes"
if ((Get-FileHash -LiteralPath $InstalledJobs -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InstalledJobsSha) { throw "STOP: installed P6-03 jobs.py changed during P6-04A generation." }
if ((Get-FileHash -LiteralPath $InstalledExecutions -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InstalledExecutionsSha) { throw "STOP: installed P6-04 executions.py changed during P6-04A generation." }
if ((Get-FileHash -LiteralPath $InstalledScheduler -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InstalledSchedulerSha) { throw "STOP: installed P6-04 scheduler.py changed during P6-04A generation." }
if ($StateAfter.JobCount -ne $StateBefore.JobCount) { throw "STOP: COMPANION logical job count changed during P6-04A generation." }
if ($StateAfter.Rows -ne $StateBefore.Rows) { throw "STOP: COMPANION logical execution row count changed during P6-04A generation." }
if ($StateAfter.Columns -ne $StateBefore.Columns) { throw "STOP: COMPANION logical execution schema changed during P6-04A generation." }

Write-Host "P6_04A_GENERATE_COMPANION_JOB_COUNT_AFTER=$($StateAfter.JobCount)"
Write-Host "P6_04A_GENERATE_COMPANION_EXECUTION_ROWS_AFTER=$($StateAfter.Rows)"
Write-Host "P6_04A_GENERATE_COMPANION_EXECUTION_COLUMNS_AFTER=$($StateAfter.Columns)"
Write-Host "P6_04A_GENERATE_ORION_UNCHANGED=true"
Write-Host "P6_04A_GENERATE_HERMES_UNCHANGED=true"
Write-Host "P6_04A_GENERATE_COMPANION_LOGICAL_STATE_UNCHANGED=true"
Write-Host "P6_04A_GENERATE_PATCH_FILE=$CandidatePatch"
Write-Host "P6_04A_GENERATE_AND_QUALIFY=PASS"
