# P6-UPG-03 Operator Runbook

This runbook starts from the accepted P6-UPG-02 compatibility commit
`d15f0c3c54236a4aa1b855840dad2b39602244e9`.

P6-UPG-03 is disposable only. It does not update installed Hermes, mutate
COMPANION, restart the gateway, run a live reminder, or change the production
pin.

## 1. Synchronize the prepared branch

From native Windows PowerShell:

    Set-Location D:\Orion\orion-personal-ai
    $ErrorActionPreference = "Stop"

    if (@(git status --porcelain=v1).Count -ne 0) {
        throw "STOP: Orion worktree is not clean."
    }

    git fetch origin feature/p6-upg-03-v0215-full-migration-rehearsal
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: fetch failed."
    }

    git show-ref --verify --quiet refs/heads/feature/p6-upg-03-v0215-full-migration-rehearsal
    if ($LASTEXITCODE -eq 0) {
        git switch feature/p6-upg-03-v0215-full-migration-rehearsal
    }
    else {
        git switch --track origin/feature/p6-upg-03-v0215-full-migration-rehearsal
    }

    if ($LASTEXITCODE -ne 0) {
        throw "STOP: branch switch failed."
    }

    git pull --ff-only origin feature/p6-upg-03-v0215-full-migration-rehearsal
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: fast-forward failed."
    }

    git status --short
    git rev-parse HEAD

Do not reset, clean, stash, or overwrite local work if a guard fails.

## 2. Cheap parser preflight

    $Python = "C:\Users\spill\AppData\Local\Programs\Python\Python311\python.exe"

    foreach ($File in @(
        ".\scripts\phase6\p6-upg-03-risk-probes.py",
        ".\scripts\phase6\p6-upg-03-apply-worker-env-fix.py"
    )) {
        & $Python -B -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec'); print('PY_PARSE_PASS=' + str(p))" $File
        if ($LASTEXITCODE -ne 0) {
            throw "STOP: Python parse failed: $File"
        }
    }

    $Wrapper = ".\scripts\phase6\Invoke-P6-UPG-03-FullMigrationRehearsal.ps1"
    $Tokens = $null
    $Errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path $Wrapper).Path,
        [ref]$Tokens,
        [ref]$Errors
    )

    if ($Errors.Count -ne 0) {
        $Errors | ForEach-Object { Write-Host $_.Message }
        throw "STOP: P6-UPG-03 PowerShell runner does not parse."
    }

    Write-Host "P6_UPG_03_PREFLIGHT=PASS"

## 3. Run the disposable rehearsal

    $Log = Join-Path $env:TEMP ("p6-upg-03-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase6\Invoke-P6-UPG-03-FullMigrationRehearsal.ps1 2>&1 |
        Tee-Object -FilePath $Log

    Write-Host "P6_UPG_03_LOG=$Log"

Return the complete output.

## Expected result classes

### PASS

No new compatibility blocker reproduced. Focused upstream risk regressions passed
and production remained unchanged.

### BLOCKED_WORKER_ENV

The exact v0.21.5 target reproduced the managed external-worker dependency-path
defect described in upstream P1 reports #122529/#129235, while the narrow
disposable repair proved the same topology green.

This is useful evidence. It means the next step is to promote that one additional
compatibility delta and requalify it before any production upgrade.

### STOP

An unexpected source/state/test invariant failed. Stop at that point and inspect
the returned evidence; do not continue manually around the guard.

## Production acceptance intentionally deferred

The following require the real controlled production migration ticket rather than
an offline disposable simulation:

- independent gateway return/listener verification after update (#129171);
- ticker heartbeat advancing after the restarted process owns scheduling
  (#129990);
- no active cron execution at update start (#129947);
- no `source-completion-pending` marker before/after update (#127284);
- fresh-connection post-restart `PRAGMA integrity_check` (#110007);
- gateway turn-machinery warm-up completion or bounded first-turn acceptance
  before considering the gateway fully ready (#131145).
