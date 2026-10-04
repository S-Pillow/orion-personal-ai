param(
    [string]$CandidateRoot = "C:\Users\spill\AppData\Local\Temp\orion-p6-upg-01-20261001-224934\hermes-v0.21.5",
    [string]$InstalledHermesRoot = "$env:LOCALAPPDATA\hermes\hermes-agent",
    [string]$CompanionHome = "$env:LOCALAPPDATA\hermes\profiles\companion",
    [string]$SystemPython = "C:\Users\spill\AppData\Local\Programs\Python\Python311\python.exe"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ExpectedBranch = "feature/p6-upg-03-v0215-full-migration-rehearsal"
$QualifiedBase = "d15f0c3c54236a4aa1b855840dad2b39602244e9"
$ExpectedCandidateCommit = "f97608f178d1ffeca59860195ab7da295f7c8e5f"
$ExpectedCandidateTag = "v2026.9.24"
$ExpectedInstalledHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedLiveSchema = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error,scheduled_at,delivery_outcome,error_class"
$ExpectedCompatHash = "b0f0811f6411dff4d1faa0fbd19a04ad0414dfc3f846f25540dc75b4f8454d9c"

$ExpectedCompatFileHashes = @{
    "cron/jobs.py" = "02a64327b8e0b41c03d6c43ca7f1f7c67a3b1f31e805f22ee30eb90b8d9f1a4a"
    "cron/error_classification.py" = "095a5482791088ab040c04446b5f3bb7d4aa3c5a95f4a1863329530d292f02eb"
    "cron/executions.py" = "990bac66f9d3b30e57cf598ba3099a11004edd893a3ab0f578ef713d7775180e"
    "agent/monitoring/cron_health.py" = "c1f187aa4685fbfafbf1090659fd3185544b9da95bb122c36727b2cb6369ae6a"
}

$InstalledHermesPython = Join-Path $InstalledHermesRoot "venv\Scripts\python.exe"
$StateProbe = Join-Path $RepoRoot "scripts\phase6\p6-04-production-state-probe.py"
$RiskProbe = Join-Path $RepoRoot "scripts\phase6\p6-upg-03-risk-probes.py"
$CompatPatch = Join-Path $RepoRoot "compat\hermes\v2026.9.24-orion-minimal-compat.patch"
$WorkerCompatPatch = Join-Path $RepoRoot "compat\hermes\v2026.9.24-upstream-f57d235-worker-env.patch"

function Get-KeyValue([string[]]$Output, [string]$Key) {
    $Prefix = $Key + "="
    $Found = @($Output | Where-Object { $_.StartsWith($Prefix) })
    if ($Found.Count -ne 1) {
        throw "STOP: expected exactly one value for $Key."
    }
    return $Found[0].Substring($Prefix.Length)
}

function Assert-CleanCandidate([string]$Root) {
    if ((git -C $Root rev-parse HEAD).Trim() -ne $ExpectedCandidateCommit) {
        throw "STOP: candidate commit drift."
    }
    if ((git -C $Root describe --tags --exact-match HEAD).Trim() -ne $ExpectedCandidateTag) {
        throw "STOP: candidate tag drift."
    }
    if (@(git -C $Root status --porcelain=v1).Count -ne 0) {
        throw "STOP: candidate checkout is dirty."
    }
}

Write-Host "P6_UPG_03_BEGIN=true"
Write-Host "P6_UPG_03_PRODUCTION_UPDATE_AUTHORIZED=false"
Write-Host "P6_UPG_03_INSTALLED_HERMES_MUTATION_AUTHORIZED=false"
Write-Host "P6_UPG_03_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_UPG_03_RESTART_AUTHORIZED=false"
Write-Host "P6_UPG_03_LIVE_REMINDER_AUTHORIZED=false"

Set-Location $RepoRoot

if ((git branch --show-current).Trim() -ne $ExpectedBranch) {
    throw "STOP: wrong Orion branch."
}
if (@(git status --porcelain=v1).Count -ne 0) {
    throw "STOP: Orion worktree must be clean."
}

git merge-base --is-ancestor $QualifiedBase HEAD
if ($LASTEXITCODE -ne 0) {
    throw "STOP: P6-UPG-03 branch does not descend from qualified P6-UPG-02."
}

foreach ($Path in @($InstalledHermesPython, $SystemPython, $StateProbe, $RiskProbe, $CompatPatch, $WorkerCompatPatch)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "STOP: required file missing: $Path"
    }
}

if ((git -C $InstalledHermesRoot rev-parse HEAD).Trim() -ne $ExpectedInstalledHermesHead) {
    throw "STOP: installed Hermes pin drift."
}

Assert-CleanCandidate $CandidateRoot

$CompatHash = (Get-FileHash -LiteralPath $CompatPatch -Algorithm SHA256).Hash.ToLowerInvariant()
if ($CompatHash -ne $ExpectedCompatHash) {
    throw "STOP: P6-UPG-02 compatibility artifact hash drift."
}

$ProdBefore = @(& $InstalledHermesPython -B $StateProbe --companion-home $CompanionHome)
if ($LASTEXITCODE -ne 0) {
    throw "STOP: production state probe failed."
}

$ProdJobsBefore = [int](Get-KeyValue $ProdBefore "P6_04_PROD_STATE_JOB_COUNT")
$ProdRowsBefore = [int](Get-KeyValue $ProdBefore "P6_04_PROD_STATE_EXECUTION_ROWS")
$ProdColumnsBefore = Get-KeyValue $ProdBefore "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$ProdModeBefore = Get-KeyValue $ProdBefore "P6_04_PROD_STATE_SQLITE_MODE"

if ($ProdJobsBefore -ne 0) {
    throw "STOP: production currently has reminder jobs; this rehearsal expected the accepted zero-job baseline."
}
if ($ProdRowsBefore -ne 0) {
    throw "STOP: production execution ledger is not empty."
}
if ($ProdColumnsBefore -ne $ExpectedLiveSchema) {
    throw "STOP: production execution schema drift."
}
if ($ProdModeBefore -ne "read_only") {
    throw "STOP: production state probe was not read-only."
}

$InstallStateRoot = Join-Path $env:LOCALAPPDATA "hermes\installs"
$PendingMarkers = @()
if (Test-Path -LiteralPath $InstallStateRoot -PathType Container) {
    $PendingMarkers = @(Get-ChildItem -LiteralPath $InstallStateRoot -Filter "source-completion-pending" -File -Recurse -ErrorAction SilentlyContinue)
}
Write-Host "P6_UPG_03_PRODUCTION_SOURCE_COMPLETION_PENDING_COUNT=$($PendingMarkers.Count)"
if ($PendingMarkers.Count -ne 0) {
    throw "STOP: production has source-completion-pending marker(s); diagnose before migration work."
}

$Listeners = @(Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue)
Write-Host "P6_UPG_03_PRODUCTION_GATEWAY_LISTENER_COUNT=$($Listeners.Count)"
if ($Listeners.Count -ne 1) {
    throw "STOP: expected exactly one production gateway listener on 8642."
}

$GatewayPid = [int]$Listeners[0].OwningProcess
$GatewayProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $GatewayPid"
if ($null -eq $GatewayProcess -or -not $GatewayProcess.ExecutablePath) {
    throw "STOP: could not resolve gateway process executable."
}

$GatewayExe = [IO.Path]::GetFullPath([string]$GatewayProcess.ExecutablePath)
$InstalledVenvExe = [IO.Path]::GetFullPath($InstalledHermesPython)
$SystemPythonExe = [IO.Path]::GetFullPath($SystemPython)
$GatewayUsesInstalledVenv = [string]::Equals($GatewayExe, $InstalledVenvExe, [StringComparison]::OrdinalIgnoreCase)
$GatewayUsesSystemPython = [string]::Equals($GatewayExe, $SystemPythonExe, [StringComparison]::OrdinalIgnoreCase)
$InstalledRuntimeSite = Join-Path $InstalledHermesRoot "venv\Lib\site-packages"
$InstalledRuntimeSiteExists = Test-Path -LiteralPath $InstalledRuntimeSite -PathType Container

Write-Host "P6_UPG_03_PRODUCTION_GATEWAY_PID=$GatewayPid"
Write-Host "P6_UPG_03_PRODUCTION_GATEWAY_EXE_NAME=$([IO.Path]::GetFileName($GatewayExe))"
Write-Host "P6_UPG_03_PRODUCTION_GATEWAY_USES_INSTALLED_VENV=$($GatewayUsesInstalledVenv.ToString().ToLowerInvariant())"
Write-Host "P6_UPG_03_PRODUCTION_GATEWAY_USES_SYSTEM_PYTHON=$($GatewayUsesSystemPython.ToString().ToLowerInvariant())"
Write-Host "P6_UPG_03_PRODUCTION_INSTALLED_RUNTIME_SITE_EXISTS=$($InstalledRuntimeSiteExists.ToString().ToLowerInvariant())"
Write-Host "P6_UPG_03_PRODUCTION_BASELINE=PASS"

$InstalledPy = (& $InstalledHermesPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
$SystemPy = (& $SystemPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($InstalledPy -ne $SystemPy) {
    throw "STOP: disposable Python major/minor does not match production."
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$WorkRoot = Join-Path $env:TEMP "orion-p6-upg-03-$Stamp"
$Target = Join-Path $WorkRoot "target"
$RuntimeVenv = Join-Path $Target "venv"
$TestHome = Join-Path $WorkRoot "test-home"

New-Item -ItemType Directory -Force -Path @($WorkRoot, $TestHome) | Out-Null
Write-Host "P6_UPG_03_WORK_ROOT=$WorkRoot"

git -c advice.detachedHead=false -c core.autocrlf=false clone --quiet --no-hardlinks $CandidateRoot $Target
if ($LASTEXITCODE -ne 0) {
    throw "STOP: disposable target clone failed."
}

git -C $Target -c core.autocrlf=false -c advice.detachedHead=false checkout --quiet $ExpectedCandidateCommit
if ($LASTEXITCODE -ne 0) {
    throw "STOP: disposable target checkout failed."
}
git -C $Target config core.autocrlf false

Assert-CleanCandidate $Target

git -C $Target apply --check $CompatPatch
if ($LASTEXITCODE -ne 0) {
    throw "STOP: qualified compatibility patch no longer applies to exact target."
}
git -C $Target apply $CompatPatch
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to apply qualified compatibility patch."
}

foreach ($Relative in $ExpectedCompatFileHashes.Keys) {
    $Actual = (Get-FileHash -LiteralPath (Join-Path $Target $Relative) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $ExpectedCompatFileHashes[$Relative]) {
        throw "STOP: qualified compatibility file hash mismatch: $Relative"
    }
}
Write-Host "P6_UPG_03_QUALIFIED_COMPAT_REPRODUCED=PASS"

git -C $Target apply --check $WorkerCompatPatch
if ($LASTEXITCODE -ne 0) {
    throw "STOP: reviewed upstream f57d235 worker-env backport does not apply cleanly."
}
git -C $Target apply $WorkerCompatPatch
if ($LASTEXITCODE -ne 0) {
    throw "STOP: failed to apply reviewed upstream f57d235 worker-env backport."
}
Write-Host "P6_UPG_03_UPSTREAM_F57D235_BACKPORT_APPLIED=PASS"

& $SystemPython -m venv $RuntimeVenv
if ($LASTEXITCODE -ne 0) {
    throw "STOP: runtime venv creation failed."
}
$RuntimePython = Join-Path $RuntimeVenv "Scripts\python.exe"

& $RuntimePython -m pip install --disable-pip-version-check --quiet --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "STOP: runtime packaging tools install failed."
}
& $RuntimePython -m pip install --disable-pip-version-check --quiet -e $Target
if ($LASTEXITCODE -ne 0) {
    throw "STOP: target editable install failed."
}
& $RuntimePython -m pip install --disable-pip-version-check --quiet pytest pytest-asyncio
if ($LASTEXITCODE -ne 0) {
    throw "STOP: target test dependencies failed."
}

$RuntimeSite = (& $RuntimePython -c "import site; print(site.getsitepackages()[0])").Trim()
if (-not (Test-Path -LiteralPath $RuntimeSite -PathType Container)) {
    throw "STOP: runtime site-packages path not found."
}

$Static = @(& $RuntimePython -B $RiskProbe --mode static --repo-root $Target 2>&1)
$Static | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
    throw "STOP: static target-risk probe failed."
}

& $RuntimePython -B $RiskProbe --mode integrity --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) {
    throw "STOP: SQLite integrity-guard selftest failed."
}

$OldHome = $env:HERMES_HOME
$OldPythonPath = $env:PYTHONPATH
$OldDontWrite = $env:PYTHONDONTWRITEBYTECODE

$UpstreamWorkerFixTests = @(
    "tests/cron/test_restart_safe_worker.py::test_launch_external_worker_pin_extends_the_sanitized_env_not_os_environ",
    "tests/cron/test_restart_safe_worker.py::test_pin_restores_activated_dependency_site_packages",
    "tests/cron/test_restart_safe_worker.py::test_activated_dependency_site_packages_derives_from_sys_path",
    "tests/cron/test_restart_safe_worker.py::test_activated_dependency_site_packages_excludes_own_purelib",
    "tests/cron/test_restart_safe_worker.py::test_activated_dependency_site_packages_requires_real_venv"
)

try {
    $env:HERMES_HOME = $TestHome
    $env:PYTHONPATH = $Target
    $env:PYTHONDONTWRITEBYTECODE = "1"

    Push-Location $Target
    try {
        & $RuntimePython -B -m pytest $UpstreamWorkerFixTests -q -p no:cacheprovider
        $UpstreamWorkerFixExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    $env:HERMES_HOME = $OldHome
    $env:PYTHONPATH = $OldPythonPath
    $env:PYTHONDONTWRITEBYTECODE = $OldDontWrite
}

if ($UpstreamWorkerFixExit -ne 0) {
    throw "STOP: upstream f57d235 regression tests failed."
}

Write-Host "P6_UPG_03_UPSTREAM_F57D235_BACKPORT_PROOF=PASS"

$FocusedTests = @(
    "tests/tools/test_local_env_blocklist.py::TestActiveVenvMarkerStripping::test_virtualenv_marker_stripped_end_to_end",
    "tests/tools/test_local_env_blocklist.py::TestActiveVenvMarkerStripping::test_sanitize_subprocess_env_strips_markers",
    "tests/tools/test_local_env_blocklist.py::TestPythonpathSelectiveStrip::test_owned_entries_stripped_matrix",
    "tests/tools/test_local_env_blocklist.py::TestPythonpathSelectiveStrip::test_windows_hermes_owned_paths_stripped",
    "tests/tools/test_local_env_blocklist.py::TestPythonpathSelectiveStrip::test_base_python_sanitizer_uses_validated_separate_runtime_venv",
    "tests/tools/test_local_env_blocklist.py::TestPythonpathSelectiveStrip::test_builders_strip_hermes_venv_pythonpath",
    "tests/cron/test_cron_multiplex_tick_ownership.py",
    "tests/cron/test_cron_multiplex_desktop_ticker_scope.py",
    "tests/cron/test_ticker_stall.py",
    "tests/cron/test_cron_emfile_stall.py",
    "tests/gateway/test_restart_resume_pending.py",
    "tests/gateway/test_cron_active_work_drain.py"
)

foreach ($Relative in $FocusedTests) {
    $RelativeFile = ($Relative -split "::", 2)[0]
    if (-not (Test-Path -LiteralPath (Join-Path $Target $RelativeFile) -PathType Leaf)) {
        throw "STOP: expected focused target test file missing: $RelativeFile"
    }
}

$OldHome = $env:HERMES_HOME
$OldPythonPath = $env:PYTHONPATH
$OldDontWrite = $env:PYTHONDONTWRITEBYTECODE

try {
    $env:HERMES_HOME = $TestHome
    $env:PYTHONPATH = $Target
    $env:PYTHONDONTWRITEBYTECODE = "1"

    Push-Location $Target
    try {
        & $RuntimePython -B -m pytest $FocusedTests -q -p no:cacheprovider
        $FocusedExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    $env:HERMES_HOME = $OldHome
    $env:PYTHONPATH = $OldPythonPath
    $env:PYTHONDONTWRITEBYTECODE = $OldDontWrite
}

if ($FocusedExit -ne 0) {
    throw "STOP: focused P6-UPG-03 upstream risk regressions failed."
}

Write-Host "P6_UPG_03_FOCUSED_UPSTREAM_RISK_REGRESSION=PASS"

$ProdAfter = @(& $InstalledHermesPython -B $StateProbe --companion-home $CompanionHome)
if ($LASTEXITCODE -ne 0) {
    throw "STOP: final production state probe failed."
}

$ProdJobsAfter = [int](Get-KeyValue $ProdAfter "P6_04_PROD_STATE_JOB_COUNT")
$ProdRowsAfter = [int](Get-KeyValue $ProdAfter "P6_04_PROD_STATE_EXECUTION_ROWS")
$ProdColumnsAfter = Get-KeyValue $ProdAfter "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$ProdModeAfter = Get-KeyValue $ProdAfter "P6_04_PROD_STATE_SQLITE_MODE"

if ($ProdJobsAfter -ne $ProdJobsBefore -or $ProdRowsAfter -ne $ProdRowsBefore) {
    throw "STOP: production cron logical counts changed."
}
if ($ProdColumnsAfter -ne $ProdColumnsBefore -or $ProdModeAfter -ne "read_only") {
    throw "STOP: production execution state changed or was not read-only."
}
if ((git -C $InstalledHermesRoot rev-parse HEAD).Trim() -ne $ExpectedInstalledHermesHead) {
    throw "STOP: installed Hermes HEAD changed."
}
if (@(git status --porcelain=v1).Count -ne 0) {
    throw "STOP: Orion worktree changed during disposable rehearsal."
}

Write-Host "P6_UPG_03_PRODUCTION_CRON_LOGICAL_STATE_UNCHANGED=true"
Write-Host "P6_UPG_03_INSTALLED_HERMES_UNCHANGED=true"
Write-Host "P6_UPG_03_GATEWAY_RESTARTED=false"
Write-Host "P6_UPG_03_LIVE_REMINDER_RUN=false"

Write-Host "P6_UPG_03_VERDICT=PASS"
Write-Host "P6_UPG_03_CANDIDATE=V0215_PLUS_ORION_COMPAT_PLUS_UPSTREAM_F57D235"
Write-Host "P6_UPG_03_NEXT=prepare_combined_immutable_compat_artifact_for_p6_upg_04_review"
