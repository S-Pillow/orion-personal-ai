# P6-UPG-02 Next-Session Runbook

Use this runbook to resume immediately from the prepared GitHub branch.

Production Hermes remains unchanged. This run is disposable qualification plus generation of an Orion compatibility patch only.

## 1. Synchronize the prepared branch

Run from native Windows PowerShell:

    Set-Location D:\Orion\orion-personal-ai
    $ErrorActionPreference = "Stop"

    if (@(git status --porcelain=v1).Count -ne 0) {
        throw "STOP: local Orion worktree is not clean."
    }

    git fetch origin feature/p6-upg-02-v0215-minimal-compat
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: fetch failed."
    }

    git show-ref --verify --quiet refs/heads/feature/p6-upg-02-v0215-minimal-compat
    if ($LASTEXITCODE -eq 0) {
        git switch feature/p6-upg-02-v0215-minimal-compat
    }
    else {
        git switch --track origin/feature/p6-upg-02-v0215-minimal-compat
    }

    if ($LASTEXITCODE -ne 0) {
        throw "STOP: branch switch failed."
    }

    git pull --ff-only origin feature/p6-upg-02-v0215-minimal-compat
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: branch fast-forward failed."
    }

    git status --short
    git rev-parse HEAD

Expected result: clean worktree on the prepared P6-UPG-02 feature branch.

Do not reset, clean, stash, or overwrite local work if the guard fails.

## 2. Run disposable implementation qualification

    $Log = Join-Path $env:TEMP ("p6-upg-02-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase6\Invoke-P6-UPG-02-GenerateAndQualify.ps1 2>&1 |
        Tee-Object -FilePath $Log

    Write-Host "P6_UPG_02_LOG=$Log"

Return the complete output for review.

The runner is fail-closed and is expected to stop on:

- branch/worktree drift;
- installed Hermes pin drift;
- candidate commit/tag/status drift;
- production reminder-state drift;
- Python major/minor mismatch;
- upstream classifier-block drift;
- unexpected transformed paths;
- syntax or qualification failure;
- focused upstream regression failure;
- unexpected test artifacts in the candidate checkout;
- patch serialization/apply failure;
- round-trip source-hash mismatch;
- final production logical-state drift.

## 3. Expected successful end state

A successful run prints:

- `P6_UPG_02_CUSTOM_QUALIFICATION=PASS`
- `P6_UPG_02_FOCUSED_REGRESSION=PASS`
- `P6_UPG_02_PATCH_ROUNDTRIP=PASS`
- `P6_UPG_02_DISPOSABLE_QUALIFICATION=PASS`
- `P6_UPG_02_COMPANION_CRON_LOGICAL_STATE_UNCHANGED=true`
- `P6_UPG_02_INSTALLED_HERMES_UNCHANGED=true`
- `P6_UPG_02_IMPLEMENTATION_AND_QUALIFICATION=PASS`

It also creates exactly one intended Orion artifact:

- `compat/hermes/v2026.9.24-orion-minimal-compat.patch`

The Orion worktree is therefore expected to be dirty **only because that generated patch is new**.

Do not commit the generated patch until its output, hash, exact source delta, and regression results have been reviewed.

## 4. After P6-UPG-02 passes

Next actions:

1. review the generated four-file Hermes delta and patch SHA-256;
2. commit the exact tested patch plus qualification evidence on this feature branch;
3. push and verify CI against that exact head;
4. start P6-UPG-03 disposable full migration rehearsal;
5. specifically probe the known Windows restart-safe-worker dependency issue, single scheduler ownership, update-with-no-active-jobs rule, gateway return verification, sticky update markers, ticker progress, and post-restart SQLite integrity;
6. prepare a separate production-upgrade ticket only after the disposable migration rehearsal passes.

No production Hermes pin change or gateway restart is implied by P6-UPG-02.
