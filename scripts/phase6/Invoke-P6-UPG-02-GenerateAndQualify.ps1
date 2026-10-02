param(
    [string]$CandidateRoot = "C:\Users\spill\AppData\Local\Temp\orion-p6-upg-01-20261001-224934\hermes-v0.21.5",
    [string]$InstalledHermesRoot = "$env:LOCALAPPDATA\hermes\hermes-agent",
    [string]$CompanionHome = "$env:LOCALAPPDATA\hermes\profiles\companion",
    [string]$SystemPython = "C:\Users\spill\AppData\Local\Programs\Python\Python311\python.exe"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ExpectedBranch = "feature/p6-upg-02-v0215-minimal-compat"
$ExpectedCandidateCommit = "f97608f178d1ffeca59860195ab7da295f7c8e5f"
$ExpectedCandidateTag = "v2026.9.24"
$ExpectedInstalledHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedLiveSchema = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error,scheduled_at,delivery_outcome,error_class"

$InstalledHermesPython = Join-Path $InstalledHermesRoot "venv\Scripts\python.exe"
$StateProbe = Join-Path $RepoRoot "scripts\phase6\p6-04-production-state-probe.py"
$Transformer = Join-Path $RepoRoot "scripts\phase6\p6-upg-02-build-v0215-compat.py"
$Qualifier = Join-Path $RepoRoot "scripts\phase6\p6-upg-02-qualify-v0215-compat.py"
$PatchPath = Join-Path $RepoRoot "compat\hermes\v2026.9.24-orion-minimal-compat.patch"

function Get-ProbeValue([string[]]$Output, [string]$Key) {
    $Prefix = $Key + "="
    $Found = @($Output | Where-Object { $_.StartsWith($Prefix) })
    if ($Found.Count -ne 1) {
        throw "STOP: expected exactly one state-probe value for $Key."
    }
    return $Found[0].Substring($Prefix.Length)
}

function Assert-CleanCandidate([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "STOP: candidate root not found: $Root"
    }

    $Head = (git -C $Root rev-parse HEAD).Trim()
    $Tag = (git -C $Root describe --tags --exact-match HEAD).Trim()
    $Status = @(git -C $Root status --porcelain=v1)

    if ($Head -ne $ExpectedCandidateCommit) {
        throw "STOP: candidate commit drift: $Head"
    }
    if ($Tag -ne $ExpectedCandidateTag) {
        throw "STOP: candidate tag drift: $Tag"
    }
    if ($Status.Count -ne 0) {
        throw "STOP: candidate checkout is dirty."
    }
}

Write-Host "P6_UPG_02_BEGIN=true"
Write-Host "P6_UPG_02_INSTALLED_HERMES_MUTATION_AUTHORIZED=false"
Write-Host "P6_UPG_02_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_UPG_02_RESTART_AUTHORIZED=false"
Write-Host "P6_UPG_02_LIVE_REMINDER_AUTHORIZED=false"

Set-Location $RepoRoot

$CurrentBranch = (git branch --show-current).Trim()
if ($CurrentBranch -ne $ExpectedBranch) {
    throw "STOP: expected Orion branch $ExpectedBranch, got $CurrentBranch."
}

if (@(git status --porcelain=v1).Count -ne 0) {
    throw "STOP: Orion worktree must be clean before qualification."
}

foreach ($RequiredPath in @($StateProbe, $Transformer, $Qualifier, $InstalledHermesPython, $SystemPython)) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "STOP: required file missing: $RequiredPath"
    }
}

$InstalledHeadBefore = (git -C $InstalledHermesRoot rev-parse HEAD).Trim()
if ($InstalledHeadBefore -ne $ExpectedInstalledHermesHead) {
    throw "STOP: installed Hermes pin drift."
}

Assert-CleanCandidate $CandidateRoot

$ProdBefore = @(& $InstalledHermesPython -B $StateProbe --companion-home $CompanionHome)
if ($LASTEXITCODE -ne 0) {
    throw "STOP: production state probe failed."
}

$ProdJobsBefore = [int](Get-ProbeValue $ProdBefore "P6_04_PROD_STATE_JOB_COUNT")
$ProdRowsBefore = [int](Get-ProbeValue $ProdBefore "P6_04_PROD_STATE_EXECUTION_ROWS")
$ProdColumnsBefore = Get-ProbeValue $ProdBefore "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$ProdModeBefore = Get-ProbeValue $ProdBefore "P6_04_PROD_STATE_SQLITE_MODE"

if ($ProdJobsBefore -ne 0) {
    throw "STOP: production jobs are not zero."
}
if ($ProdRowsBefore -ne 0) {
    throw "STOP: production execution rows are not zero."
}
if ($ProdColumnsBefore -ne $ExpectedLiveSchema) {
    throw "STOP: production execution schema drift."
}
if ($ProdModeBefore -ne "read_only") {
    throw "STOP: production probe was not read-only."
}

$InstalledPy = (& $InstalledHermesPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
$QualificationPy = (& $SystemPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()

if ($InstalledPy -ne $QualificationPy) {
    throw "STOP: qualification Python $QualificationPy does not match installed Hermes Python $InstalledPy."
}

if (Test-Path -LiteralPath $PatchPath) {
    throw "STOP: generated compatibility patch already exists; inspect it before rerunning."
}

Write-Host "P6_UPG_02_PRODUCTION_PYTHON=$InstalledPy"
Write-Host "P6_UPG_02_PRODUCTION_BASELINE=PASS"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$WorkRoot = Join-Path $env:TEMP "orion-p6-upg-02-$Stamp"
$Worktree = Join-Path $WorkRoot "candidate"
$Roundtrip = Join-Path $WorkRoot "roundtrip"
$Venv = Join-Path $WorkRoot "venv"
$TestHome = Join-Path $WorkRoot "test-home"
$UpstreamHome = Join-Path $WorkRoot "upstream-home"
$UpstreamDb = Join-Path $UpstreamHome "cron\executions.db"
$PycacheRoot = Join-Path $WorkRoot "pycache"

New-Item -ItemType Directory -Force -Path @($WorkRoot, $TestHome, $UpstreamHome, $PycacheRoot) | Out-Null

Write-Host "P6_UPG_02_WORK_ROOT=$WorkRoot"

git -c core.autocrlf=false clone --quiet --no-hardlinks $CandidateRoot $Worktree
if ($LASTEXITCODE -ne 0) {
    throw "STOP: disposable candidate clone failed."
}

git -C $Worktree -c core.autocrlf=false checkout --quiet $ExpectedCandidateCommit
if ($LASTEXITCODE -ne 0) {
    throw "STOP: disposable checkout failed."
}
git -C $Worktree config core.autocrlf false

Assert-CleanCandidate $Worktree

& $SystemPython -m venv $Venv
if ($LASTEXITCODE -ne 0) {
    throw "STOP: disposable venv creation failed."
}

$Python = Join-Path $Venv "Scripts\python.exe"

& $Python -m pip install --disable-pip-version-check --quiet --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "STOP: packaging tool installation failed."
}

& $Python -m pip install --disable-pip-version-check --quiet -e $Worktree
if ($LASTEXITCODE -ne 0) {
    throw "STOP: editable upstream Hermes install failed."
}

& $Python -m pip install --disable-pip-version-check --quiet pytest pytest-asyncio
if ($LASTEXITCODE -ne 0) {
    throw "STOP: pytest dependency installation failed."
}

$Version = (& $Python -c "import hermes_cli; print(hermes_cli.__version__)").Trim()
if ($Version -ne "0.21.5") {
    throw "STOP: disposable runtime is not Hermes 0.21.5."
}

$OldDontWriteBytecode = $env:PYTHONDONTWRITEBYTECODE
$OldPycachePrefix = $env:PYTHONPYCACHEPREFIX
$OldHermesHome = $env:HERMES_HOME
$OldPythonPath = $env:PYTHONPATH

try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $env:PYTHONPYCACHEPREFIX = $PycacheRoot
    $env:HERMES_HOME = $UpstreamHome
    $env:PYTHONPATH = $Worktree

    & $Python -B $Qualifier --mode seed-upstream --home $UpstreamHome --upstream-db $UpstreamDb
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: upstream-native schema seed failed."
    }
}
finally {
    $env:PYTHONDONTWRITEBYTECODE = $OldDontWriteBytecode
    $env:PYTHONPYCACHEPREFIX = $OldPycachePrefix
    $env:HERMES_HOME = $OldHermesHome
    $env:PYTHONPATH = $OldPythonPath
}

if (@(git -C $Worktree status --porcelain=v1).Count -ne 0) {
    Write-Host "P6_UPG_02_PRETRANSFORM_DIRTY_BEGIN"
    git -C $Worktree status --short
    Write-Host "P6_UPG_02_PRETRANSFORM_DIRTY_END"
    throw "STOP: unmodified candidate became dirty during disposable setup."
}

Write-Host "P6_UPG_02_REAL_UPSTREAM_FIXTURE=PASS"

& $Python -B $Transformer --candidate-root $Worktree
if ($LASTEXITCODE -ne 0) {
    throw "STOP: compatibility transform failed."
}

$ExpectedPaths = @("agent/monitoring/cron_health.py", "cron/error_classification.py", "cron/executions.py", "cron/jobs.py") | Sort-Object
$ActualPaths = @(git -C $Worktree status --porcelain=v1 | ForEach-Object { $_.Substring(3).Replace("\","/") } | Sort-Object)

if (($ActualPaths -join [Environment]::NewLine) -ne ($ExpectedPaths -join [Environment]::NewLine)) {
    Write-Host "P6_UPG_02_CHANGED_PATHS_BEGIN"
    $ActualPaths
    Write-Host "P6_UPG_02_CHANGED_PATHS_END"
    throw "STOP: transformed source scope differs from the expected four paths."
}

Write-Host "P6_UPG_02_SOURCE_SCOPE=PASS"

& $Python -B $Qualifier --mode syntax --candidate-root $Worktree
if ($LASTEXITCODE -ne 0) {
    throw "STOP: transformed syntax validation failed."
}

try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $env:PYTHONPYCACHEPREFIX = $PycacheRoot
    $env:HERMES_HOME = $TestHome
    $env:PYTHONPATH = $Worktree

    & $Python -B $Qualifier --mode qualify --home $TestHome --upstream-db $UpstreamDb
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: custom P6-UPG-02 qualification failed."
    }

    Push-Location $Worktree
    try {
        & $Python -B -m pytest tests/cron/test_jobs.py tests/cron/test_scheduled_occurrence.py tests/cron/test_claim_job_for_fire.py tests/cron/test_upgrade_module_skew.py -q -p no:cacheprovider
        $PytestExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($PytestExit -ne 0) {
        throw "STOP: focused upstream regression failed."
    }
}
finally {
    $env:PYTHONDONTWRITEBYTECODE = $OldDontWriteBytecode
    $env:PYTHONPYCACHEPREFIX = $OldPycachePrefix
    $env:HERMES_HOME = $OldHermesHome
    $env:PYTHONPATH = $OldPythonPath
}

$PostTestPaths = @(git -C $Worktree status --porcelain=v1 | ForEach-Object { $_.Substring(3).Replace("\","/") } | Sort-Object)

if (($PostTestPaths -join [Environment]::NewLine) -ne ($ExpectedPaths -join [Environment]::NewLine)) {
    Write-Host "P6_UPG_02_POSTTEST_DIRTY_BEGIN"
    git -C $Worktree status --short
    Write-Host "P6_UPG_02_POSTTEST_DIRTY_END"
    throw "STOP: qualification created unexpected candidate-tree artifacts."
}

Write-Host "P6_UPG_02_FOCUSED_REGRESSION=PASS"

$GitPaths = @("cron/jobs.py", "cron/error_classification.py", "cron/executions.py", "agent/monitoring/cron_health.py")

git -C $Worktree add -- $GitPaths
if ($LASTEXITCODE -ne 0) {
    throw "STOP: exact-path staging failed."
}

$Staged = @(git -C $Worktree diff --cached --name-only | Sort-Object)
if (($Staged -join [Environment]::NewLine) -ne ($ExpectedPaths -join [Environment]::NewLine)) {
    throw "STOP: staged scope differs from expected four files."
}

git -C $Worktree diff --cached --check
if ($LASTEXITCODE -ne 0) {
    throw "STOP: staged compatibility diff failed git diff --check."
}

git -C $Worktree diff --cached --binary --full-index --output="$PatchPath" -- $GitPaths
if ($LASTEXITCODE -ne 0) {
    throw "STOP: Git-native patch generation failed."
}

if (-not (Test-Path -LiteralPath $PatchPath -PathType Leaf)) {
    throw "STOP: generated compatibility patch is missing."
}
if ((Get-Item -LiteralPath $PatchPath).Length -eq 0) {
    throw "STOP: generated compatibility patch is empty."
}

$PatchHash = (Get-FileHash -LiteralPath $PatchPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_UPG_02_PATCH_SHA256=$PatchHash"

git -c core.autocrlf=false clone --quiet --no-hardlinks $CandidateRoot $Roundtrip
if ($LASTEXITCODE -ne 0) {
    throw "STOP: roundtrip clone failed."
}

git -C $Roundtrip -c core.autocrlf=false checkout --quiet $ExpectedCandidateCommit
if ($LASTEXITCODE -ne 0) {
    throw "STOP: roundtrip checkout failed."
}
git -C $Roundtrip config core.autocrlf false

Assert-CleanCandidate $Roundtrip

git -C $Roundtrip apply --check $PatchPath
if ($LASTEXITCODE -ne 0) {
    throw "STOP: generated patch fails git apply --check."
}

git -C $Roundtrip apply $PatchPath
if ($LASTEXITCODE -ne 0) {
    throw "STOP: generated patch fails roundtrip apply."
}

foreach ($Relative in $GitPaths) {
    $WorkHash = (Get-FileHash -LiteralPath (Join-Path $Worktree $Relative) -Algorithm SHA256).Hash.ToLowerInvariant()
    $RoundtripHash = (Get-FileHash -LiteralPath (Join-Path $Roundtrip $Relative) -Algorithm SHA256).Hash.ToLowerInvariant()

    if ($WorkHash -ne $RoundtripHash) {
        throw "STOP: roundtrip hash mismatch for $Relative."
    }

    Write-Host "P6_UPG_02_HASH_$($Relative.Replace('/','_'))=$WorkHash"
}

Write-Host "P6_UPG_02_PATCH_ROUNDTRIP=PASS"
Write-Host "P6_UPG_02_DISPOSABLE_QUALIFICATION=PASS"

$ProdAfter = @(& $InstalledHermesPython -B $StateProbe --companion-home $CompanionHome)
if ($LASTEXITCODE -ne 0) {
    throw "STOP: final production state probe failed."
}

$ProdJobsAfter = [int](Get-ProbeValue $ProdAfter "P6_04_PROD_STATE_JOB_COUNT")
$ProdRowsAfter = [int](Get-ProbeValue $ProdAfter "P6_04_PROD_STATE_EXECUTION_ROWS")
$ProdColumnsAfter = Get-ProbeValue $ProdAfter "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$ProdModeAfter = Get-ProbeValue $ProdAfter "P6_04_PROD_STATE_SQLITE_MODE"

if ($ProdJobsAfter -ne $ProdJobsBefore) {
    throw "STOP: production job count changed."
}
if ($ProdRowsAfter -ne $ProdRowsBefore) {
    throw "STOP: production execution-row count changed."
}
if ($ProdColumnsAfter -ne $ProdColumnsBefore) {
    throw "STOP: production execution schema changed."
}
if ($ProdModeAfter -ne "read_only") {
    throw "STOP: final production probe was not read-only."
}
if ((git -C $InstalledHermesRoot rev-parse HEAD).Trim() -ne $InstalledHeadBefore) {
    throw "STOP: installed Hermes HEAD changed."
}

Write-Host "P6_UPG_02_PRODUCTION_JOB_COUNT_AFTER=$ProdJobsAfter"
Write-Host "P6_UPG_02_PRODUCTION_EXECUTION_ROWS_AFTER=$ProdRowsAfter"
Write-Host "P6_UPG_02_PRODUCTION_SCHEMA_AFTER=$ProdColumnsAfter"
Write-Host "P6_UPG_02_COMPANION_CRON_LOGICAL_STATE_UNCHANGED=true"
Write-Host "P6_UPG_02_INSTALLED_HERMES_UNCHANGED=true"
Write-Host "P6_UPG_02_GATEWAY_RESTARTED=false"
Write-Host "P6_UPG_02_LIVE_REMINDER_RUN=false"

Write-Host "P6_UPG_02_ORION_STATUS_BEGIN"
git status --short
Write-Host "P6_UPG_02_ORION_STATUS_END"

Write-Host "P6_UPG_02_IMPLEMENTATION_AND_QUALIFICATION=PASS"
