param(
    [string]$Repo = "D:\Orion\orion-personal-ai"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedBranch = "feature/p6-05-reminder-crud-hud"
$ExpectedHead = "69309e1559428ffee0455ed9f476222600e392a4"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$TestPath = Join-Path $Repo "hud\tests\test_phase3_workspace.py"
$HelperPath = Join-Path $env:TEMP "orion-p6-05-finalize-test-repair.py"
$BackupPath = Join-Path $env:TEMP "orion-p6-05-test_phase3_workspace.before.py"
$ReportPath = Join-Path $env:TEMP "orion-p6-05-finalize-correction-report.txt"

$Allowed = @(
    "hud/orion_hud_bridge.py",
    "hud/reminder_adapter.py",
    "hud/reminder_projection.py",
    "hud/static/app.js",
    "hud/static/index.html",
    "hud/static/target-layout.css",
    "hud/static/workspace-state.js",
    "hud/tests/test_phase3_workspace.py",
    "hud/tests/test_reminder_adapter.py",
    "hud/tests/test_reminder_bridge.py",
    "hud/tests/test_reminder_projection.py",
    "hud/tests/test_reminder_workspace.py"
)

function Assert-P6Scope {
    $status = @(git status --porcelain=v1)
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: git status failed."
    }

    if ($status.Count -ne 12) {
        git status --short
        throw "STOP: expected exactly twelve P6-05 working-tree paths."
    }

    foreach ($line in $status) {
        if ($line.Length -lt 4) {
            throw "STOP: malformed git status line."
        }
        $path = $line.Substring(3)
        if ($path -notin $Allowed) {
            git status --short
            throw "STOP: unexpected P6-05 working-tree path: $path"
        }
    }
}

function Invoke-PythonTest {
    param(
        [string]$Label,
        [string]$Pattern
    )

    Write-Host ""
    Write-Host "=== $Label ==="
    python -m unittest discover -s .\hud\tests -p $Pattern -v
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: $Label failed."
    }
}

Set-Location $Repo

Write-Host "=== P6-05 FINALIZE PRECONDITIONS ==="

$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()

if ($branch -ne $ExpectedBranch) {
    throw "STOP: unexpected Orion branch: $branch"
}
if ($head -ne $ExpectedHead) {
    throw "STOP: unexpected Orion HEAD: $head"
}

Assert-P6Scope

git diff --check
if ($LASTEXITCODE -ne 0) {
    throw "STOP: existing P6-05 diff failed git diff --check."
}

if (-not (Test-Path -LiteralPath $HermesRoot -PathType Container)) {
    throw "STOP: accepted Hermes checkout is unavailable."
}
$hermesHead = (git -C $HermesRoot rev-parse HEAD).Trim()
if ($hermesHead -ne $ExpectedHermesHead) {
    throw "STOP: unexpected Hermes HEAD: $hermesHead"
}

$pyprojectPath = Join-Path $HermesRoot "pyproject.toml"
if (-not (Test-Path -LiteralPath $pyprojectPath -PathType Leaf)) {
    throw "STOP: Hermes pyproject.toml is unavailable."
}
$pyproject = Get-Content -LiteralPath $pyprojectPath -Raw
if ($pyproject -notmatch '(?m)^\s*name\s*=\s*"hermes-agent"\s*$') {
    throw "STOP: Hermes project identity is not the accepted hermes-agent package."
}
if ($pyproject -notmatch '(?m)^\s*version\s*=\s*"0\.20\.6"\s*$') {
    throw "STOP: Hermes project version is not the accepted 0.20.6."
}

Write-Host "P6_05_SCOPE=PASS"
Write-Host "P6_05_HERMES_BASELINE=PASS"

Write-Host ""
Write-Host "=== VERIFY SEMANTIC CORRECTION ALREADY PRESENT ==="

$adapter = Get-Content -LiteralPath (Join-Path $Repo "hud\reminder_adapter.py") -Raw
$app = Get-Content -LiteralPath (Join-Path $Repo "hud\static\app.js") -Raw
$index = Get-Content -LiteralPath (Join-Path $Repo "hud\static\index.html") -Raw

$requiredAdapter = @(
    'EXPECTED_HERMES_VERSION = "0.20.6"',
    'REMINDER_DELIVERY_TARGET = "discord"',
    'version = read_hermes_project_version(root)',
    'deliver=REMINDER_DELIVERY_TARGET'
)
foreach ($token in $requiredAdapter) {
    if (-not $adapter.Contains($token)) {
        throw "STOP: corrected reminder adapter marker missing: $token"
    }
}

if (-not $index.Contains('placeholder="30m or every 30m"')) {
    throw "STOP: corrected schedule examples are missing."
}
if ($index.Contains("tomorrow at 9am") -or $index.Contains("every weekday at 8am")) {
    throw "STOP: unsupported schedule prose remains in the reminder form."
}
if (-not $app.Contains("await refreshReminders();")) {
    throw "STOP: independent reminder refresh marker is missing."
}
if (-not $app.Contains("scheduler inactive")) {
    throw "STOP: scheduler-liveness presentation marker is missing."
}
if ($app.Contains("Hermes offline // reminder authority unavailable")) {
    throw "STOP: false offline reminder-authority statement remains."
}

$refreshStart = $app.IndexOf("async function refreshStatus")
$refreshEnd = $app.IndexOf("function parseSSEFrame", $refreshStart)
if ($refreshStart -lt 0 -or $refreshEnd -lt 0) {
    throw "STOP: refreshStatus source boundary is unavailable."
}
$refreshBlock = $app.Substring($refreshStart, $refreshEnd - $refreshStart)
$reminderIndex = $refreshBlock.IndexOf("await refreshReminders();")
$onlineIndex = $refreshBlock.IndexOf("if (online) {")
if ($reminderIndex -lt 0 -or $onlineIndex -lt 0 -or $reminderIndex -ge $onlineIndex) {
    throw "STOP: reminder refresh is not independent of the conversation online branch."
}

Write-Host "P6_05_SEMANTIC_CORRECTION_PRESENT=PASS"

Write-Host ""
Write-Host "=== REPAIR ONLY THE STALE PHASE 3 STATIC ASSERTION ==="

$testText = Get-Content -LiteralPath $TestPath -Raw
$orderingMarker = 'refresh.index("if (online) {")'

if ($testText.Contains($orderingMarker)) {
    Write-Host "P6_05_PHASE3_TEST_REPAIR=ALREADY_PRESENT"
} else {
    Copy-Item -LiteralPath $TestPath -Destination $BackupPath -Force

    $helper = @'
from __future__ import annotations

import ast
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1]).resolve()
source = path.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(path))

target = None
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "Phase3AdaptiveWorkspaceContractTests":
        for child in node.body:
            if (
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == "test_status_observations_sync_before_online_branch"
            ):
                target = child
                break
        break

if target is None:
    raise SystemExit("STOP: target Phase 3 test function was not found")
if target.end_lineno is None:
    raise SystemExit("STOP: Python AST did not provide end_lineno")

newline = "\r\n" if "\r\n" in source else "\n"
normalized = source.replace("\r\n", "\n")
lines = normalized.splitlines(keepends=True)

replacement = '''    def test_status_observations_sync_before_online_branch(self):
        start = APP.index("async function refreshStatus")
        end = APP.index("function parseSSEFrame", start)
        refresh = APP[start:end]

        bridge = (
            'ui.bridgeValue.textContent = '
            'payload?.bridge?.status || "online";'
        )
        credential = (
            "ui.credentialValue.textContent = "
            'payload?.hermes?.credentials_available ? "available" : "missing";'
        )
        sync = "syncSystemWorkspace();"
        reminder_refresh = "await refreshReminders();"
        online_branch = "if (online) {"

        for token in (
            bridge,
            credential,
            sync,
            reminder_refresh,
            online_branch,
        ):
            with self.subTest(token=token):
                self.assertIn(token, refresh)

        self.assertLess(refresh.index(bridge), refresh.index(credential))
        self.assertLess(refresh.index(credential), refresh.index(sync))
        self.assertLess(
            refresh.index(sync),
            refresh.index(reminder_refresh),
        )
        self.assertLess(
            refresh.index(reminder_refresh),
            refresh.index(online_branch),
        )
'''

start = target.lineno - 1
end = target.end_lineno
candidate_lines = lines[:start] + replacement.splitlines(keepends=True) + lines[end:]
candidate = "".join(candidate_lines)

compile(candidate, str(path), "exec")

if candidate.count("def test_status_observations_sync_before_online_branch") != 1:
    raise SystemExit("STOP: candidate contains an unexpected target-test count")
if 'refresh.index("if (online) {")' not in candidate:
    raise SystemExit("STOP: candidate is missing the ordering-based online-branch assertion")
if "await refreshReminders();" not in candidate:
    raise SystemExit("STOP: candidate is missing reminder-refresh ordering coverage")

candidate = candidate.replace("\n", newline)

fd, tmp_name = tempfile.mkstemp(
    prefix=path.name + ".",
    suffix=".tmp",
    dir=str(path.parent),
)
try:
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        handle.write(candidate)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_name, path)
except Exception:
    try:
        os.unlink(tmp_name)
    except OSError:
        pass
    raise

print("P6_05_PHASE3_TEST_REPAIR=PASS")
'@

    [IO.File]::WriteAllText(
        $HelperPath,
        $helper,
        [Text.UTF8Encoding]::new($false)
    )

    try {
        python $HelperPath $TestPath
        if ($LASTEXITCODE -ne 0) {
            throw "STOP: AST-scoped Phase 3 test repair failed."
        }

        python -m py_compile $TestPath
        if ($LASTEXITCODE -ne 0) {
            throw "STOP: repaired Phase 3 test does not compile."
        }

        python -m unittest discover -s .\hud\tests -p "test_phase3_workspace.py" -v
        if ($LASTEXITCODE -ne 0) {
            Copy-Item -LiteralPath $BackupPath -Destination $TestPath -Force
            throw "STOP: targeted Phase 3 test failed; test file was restored."
        }
    }
    finally {
        Remove-Item -LiteralPath $HelperPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "=== PYTHON COMPILE ==="
python -m py_compile `
    .\hud\reminder_adapter.py `
    .\hud\reminder_projection.py `
    .\hud\orion_hud_bridge.py `
    .\hud\tests\test_phase3_workspace.py
if ($LASTEXITCODE -ne 0) {
    throw "STOP: Python compile gate failed."
}

Invoke-PythonTest "FRONTEND HARDENING" "test_frontend_hardening.py"
Invoke-PythonTest "REMINDER SUITE" "test_reminder_*.py"
Invoke-PythonTest "PHASE 3 WORKSPACE" "test_phase3_workspace.py"
Invoke-PythonTest "UI CONVERGENCE" "test_ui_convergence_contract.py"
Invoke-PythonTest "BRIDGE REGRESSION" "test_bridge.py"
Invoke-PythonTest "POST CONNECTION CLOSE" "test_post_connection_close.py"

Write-Host ""
Write-Host "P6_05_FOCUSED_EXPECTED_TESTS=98"
Write-Host "P6_05_FOCUSED_REGRESSION_GATE=PASS"

Write-Host ""
Write-Host "=== FULL HUD PYTHON DISCOVERY ==="
python -m unittest discover -s .\hud\tests -p "test_*.py" -v
if ($LASTEXITCODE -ne 0) {
    throw "STOP: full HUD Python discovery failed."
}
Write-Host "P6_05_FULL_HUD_TEST_GATE=PASS"

Write-Host ""
Write-Host "=== FINAL DIFF AND SCOPE CHECK ==="
git diff --check
if ($LASTEXITCODE -ne 0) {
    throw "STOP: final git diff --check failed."
}

Assert-P6Scope

$finalTest = Get-Content -LiteralPath $TestPath -Raw
if (-not $finalTest.Contains($orderingMarker)) {
    throw "STOP: final Phase 3 ordering assertion is missing."
}

$forbidden = @(
    "tomorrow at 9am",
    "every weekday at 8am",
    "Hermes offline // reminder authority unavailable"
)
foreach ($token in $forbidden) {
    $match = Select-String `
        -Path (Join-Path $Repo "hud\static\app.js"), (Join-Path $Repo "hud\static\index.html") `
        -Pattern $token `
        -SimpleMatch `
        -ErrorAction SilentlyContinue
    if ($match) {
        throw "STOP: forbidden stale P6-05 token remains: $token"
    }
}

$report = @(
    "ORION P6-05 FINALIZE CORRECTION REPORT",
    "generated=$([DateTimeOffset]::Now.ToString('o'))",
    "repo=$Repo",
    "branch=$branch",
    "head=$head",
    "hermes_head=$hermesHead",
    "hermes_version=0.20.6",
    "semantic_correction=PASS",
    "phase3_test_repair=PASS",
    "focused_regression_gate=PASS",
    "focused_expected_tests=98",
    "full_hud_test_gate=PASS",
    "git_diff_check=PASS",
    "working_tree_paths=12",
    "production_reminder_created=NO",
    "hermes_run_invoked=NO",
    "hermes_restart=NO",
    "companion_config_changed=NO",
    "commit_push_merge_deploy=NO",
    "p6_05_status=READY_FOR_FINAL_DIFF_REVIEW_NOT_COMMITTED"
)

[IO.File]::WriteAllLines(
    $ReportPath,
    $report,
    [Text.UTF8Encoding]::new($false)
)

Write-Host "P6_05_REPORT=$ReportPath"
Write-Host ""
git status --short --branch
Write-Host ""
Write-Host "P6_05_FINAL_CORRECTION_GATE=PASS"
