param(
    [ValidateSet("P6-02","P6-03","P6-04","P6-05","P6-06","P6-07")]
    [string]$Ticket = "P6-02"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Phase 6 read-only preflight.
# No service lifecycle, cron mutation, config mutation, git mutation,
# jobs.json body read, or execution-row read is performed.

$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$CompanionCron = Join-Path $CompanionHome "cron"

$env:GIT_PAGER = "cat"
$env:PAGER = "cat"

function Section([string]$Title) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host $Title
    Write-Host "============================================================"
}

function GitText {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [Parameter(ValueFromRemainingArguments=$true)][string[]]$Args
    )
    return ((& git --no-pager -C $Repo @Args) -join [Environment]::NewLine)
}

function Show-PinnedMatches {
    param(
        [Parameter(Mandatory=$true)][string[]]$Patterns,
        [int]$Limit = 80
    )
    foreach ($Pattern in $Patterns) {
        Write-Host ""
        Write-Host "SOURCE_PATTERN=$Pattern"
        $matches = & git --no-pager -C $HermesRoot grep -n -I -e $Pattern $ExpectedHermesHead -- "*.py" "*.md" 2>$null
        if ($LASTEXITCODE -gt 1) {
            throw "git grep failed for pattern: $Pattern"
        }
        if ($matches) {
            $matches | Select-Object -First $Limit
        } else {
            Write-Host "NO_MATCH"
        }
    }
}

Section "Phase 6 / $Ticket — read-only baseline"

$OrionRoot = (& git rev-parse --show-toplevel).Trim()
if (-not $OrionRoot) {
    throw "Run this script from inside the Orion repository."
}

$OrionHeadBefore = (GitText $OrionRoot rev-parse HEAD).Trim()
$OrionStatusBefore = GitText $OrionRoot status --short

Write-Host "ORION_ROOT=$OrionRoot"
Write-Host "ORION_HEAD=$OrionHeadBefore"
Write-Host "ORION_BRANCH=$((GitText $OrionRoot branch --show-current).Trim())"
Write-Host "ORION_STATUS_BEFORE_BEGIN"
if ($OrionStatusBefore) { Write-Host $OrionStatusBefore }
Write-Host "ORION_STATUS_BEFORE_END"

if (-not (Test-Path -LiteralPath $HermesRoot -PathType Container)) {
    throw "Hermes checkout missing: $HermesRoot"
}

$HermesHeadBefore = (GitText $HermesRoot rev-parse HEAD).Trim()
$HermesStatusBefore = GitText $HermesRoot status --short

Write-Host "EXPECTED_HERMES_HEAD=$ExpectedHermesHead"
Write-Host "OBSERVED_HERMES_HEAD=$HermesHeadBefore"
Write-Host "HERMES_HEAD_MATCH=$($HermesHeadBefore -eq $ExpectedHermesHead)"

if ($HermesHeadBefore -ne $ExpectedHermesHead) {
    throw "STOP: installed Hermes HEAD differs from accepted Phase 6 baseline."
}

Write-Host "HERMES_STATUS_BEFORE_BEGIN"
if ($HermesStatusBefore) { Write-Host $HermesStatusBefore }
Write-Host "HERMES_STATUS_BEFORE_END"

Section "Python resolution"

$Python = Get-Command python -ErrorAction SilentlyContinue
$PyLauncher = Get-Command py -ErrorAction SilentlyContinue

Write-Host "PYTHON_COMMAND_PRESENT=$([bool]$Python)"
if ($Python) {
    Write-Host "PYTHON_PATH=$($Python.Source)"
    & python --version
}
Write-Host "PY_LAUNCHER_PRESENT=$([bool]$PyLauncher)"
if ($PyLauncher) {
    Write-Host "PY_LAUNCHER_PATH=$($PyLauncher.Source)"
    & py --version
}

Section "COMPANION cron metadata only"

Write-Host "COMPANION_HOME=$CompanionHome"
Write-Host "COMPANION_HOME_EXISTS=$(Test-Path -LiteralPath $CompanionHome -PathType Container)"
Write-Host "COMPANION_CRON=$CompanionCron"
Write-Host "COMPANION_CRON_EXISTS=$(Test-Path -LiteralPath $CompanionCron -PathType Container)"

$JobsFile = Join-Path $CompanionCron "jobs.json"
$ExecutionDb = Join-Path $CompanionCron "executions.db"

Write-Host "JOBS_JSON_EXISTS=$(Test-Path -LiteralPath $JobsFile -PathType Leaf)"
if (Test-Path -LiteralPath $JobsFile -PathType Leaf) {
    $item = Get-Item -LiteralPath $JobsFile
    Write-Host "JOBS_JSON_LENGTH=$($item.Length)"
    Write-Host "JOBS_JSON_LAST_WRITE=$($item.LastWriteTime.ToString('o'))"
    Write-Host "JOBS_JSON_CONTENT_READ=false"
}

Write-Host "EXECUTIONS_DB_EXISTS=$(Test-Path -LiteralPath $ExecutionDb -PathType Leaf)"
if (Test-Path -LiteralPath $ExecutionDb -PathType Leaf) {
    $item = Get-Item -LiteralPath $ExecutionDb
    Write-Host "EXECUTIONS_DB_LENGTH=$($item.Length)"
    Write-Host "EXECUTIONS_DB_LAST_WRITE=$($item.LastWriteTime.ToString('o'))"
}

if (Test-Path -LiteralPath $CompanionCron -PathType Container) {
    Write-Host "CRON_ARTIFACTS_BEGIN"
    Get-ChildItem -LiteralPath $CompanionCron -Force |
        Sort-Object Name |
        ForEach-Object {
            Write-Host (
                "name={0};type={1};length={2};last_write={3:o}" -f
                $_.Name,
                $(if ($_.PSIsContainer) { "DIR" } else { "FILE" }),
                $(if ($_.PSIsContainer) { 0 } else { $_.Length }),
                $_.LastWriteTime
            )
        }
    Write-Host "CRON_ARTIFACTS_END"
}

Section "Execution DB schema only"

if ((Test-Path -LiteralPath $ExecutionDb -PathType Leaf) -and $Python) {
    $SchemaProbe = @'
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1]).resolve()
conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
try:
    print("SQLITE_MODE=read_only")
    for table in ("executions", "cron_incidents"):
        found = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        print(f"TABLE={table};present={bool(found)}")
        if found:
            for row in conn.execute(f"PRAGMA table_info({table})"):
                print(
                    f"SCHEMA={table};name={row[1]};type={row[2]};"
                    f"notnull={row[3]};pk={row[5]}"
                )
finally:
    conn.close()
'@
    $SchemaProbe | python - $ExecutionDb
    if ($LASTEXITCODE -ne 0) {
        throw "Read-only SQLite schema probe failed."
    }
} else {
    Write-Host "SCHEMA_PROBE_SKIPPED=true"
}

Section "Mutation-enabling environment guard"

$MutationNames = @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_PRODUCTION_MUTATION",
    "ORION_REMINDER_TEST_MUTATION"
)

foreach ($Name in $MutationNames) {
    $Value = [Environment]::GetEnvironmentVariable($Name)
    Write-Host ("{0}_PRESENT={1}" -f $Name, [bool]$Value)
}

Section "Pinned Hermes capability evidence for $Ticket"

switch ($Ticket) {
    "P6-02" {
        Show-PinnedMatches @(
            "def cronjob",
            "def _cron_api",
            "/api/cron/jobs",
            "cron_subparsers.add_parser",
            "def list_jobs"
        ) 50
    }
    "P6-03" {
        Show-PinnedMatches @(
            "def _parse_jobs_file",
            "def load_jobs",
            "Auto-repaired jobs.json",
            "def atomic_replace",
            "create_quick_snapshot"
        ) 50
    }
    "P6-04" {
        Show-PinnedMatches @(
            "CREATE TABLE IF NOT EXISTS executions",
            "delivery_outcome",
            "def create_execution",
            "def finish_execution",
            "scheduled"
        ) 60
    }
    "P6-05" {
        Show-PinnedMatches @(
            "/api/cron/jobs",
            "def cronjob",
            "def list_executions",
            "last_delivery_error"
        ) 60
    }
    "P6-06" {
        Show-PinnedMatches @(
            "ONESHOT_GRACE_SECONDS",
            "claim_dispatch",
            "fire fence",
            "recover_interrupted_executions",
            "record_catch_up_occurrence"
        ) 60
    }
    "P6-07" {
        Show-PinnedMatches @(
            "no_agent",
            "monitor_script",
            "monitor_url",
            "_validate_cron_script_path",
            "scripts_dir"
        ) 60
    }
}

Section "Final non-mutation proof"

$OrionHeadAfter = (GitText $OrionRoot rev-parse HEAD).Trim()
$HermesHeadAfter = (GitText $HermesRoot rev-parse HEAD).Trim()
$OrionStatusAfter = GitText $OrionRoot status --short
$HermesStatusAfter = GitText $HermesRoot status --short

Write-Host "ORION_HEAD_UNCHANGED=$($OrionHeadAfter -eq $OrionHeadBefore)"
Write-Host "HERMES_HEAD_UNCHANGED=$($HermesHeadAfter -eq $HermesHeadBefore)"
Write-Host "ORION_WORKTREE_UNCHANGED=$($OrionStatusAfter -eq $OrionStatusBefore)"
Write-Host "HERMES_WORKTREE_UNCHANGED=$($HermesStatusAfter -eq $HermesStatusBefore)"

if (
    $OrionHeadAfter -ne $OrionHeadBefore -or
    $HermesHeadAfter -ne $HermesHeadBefore -or
    $OrionStatusAfter -ne $OrionStatusBefore -or
    $HermesStatusAfter -ne $HermesStatusBefore
) {
    throw "STOP: preflight observed repository mutation."
}

Write-Host ""
Write-Host "PHASE6_READONLY_PREFLIGHT=PASS"
Write-Host "TICKET=$Ticket"
