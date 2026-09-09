# OR-LIFE-005 v2.7.4 Gate 3C — Post-Publication Shortcut Failure / Rollback Validation

Date: 2026-09-09
Branch: `feature/orion-start-v272-lifecycle-safety`
Candidate workspace: `C:\Users\spill\Downloads\Orion-v274-gate1-20260908-053419`
Disposition: **PASS**

## Purpose

Validate the candidate installer failure contract after version publication has completed but before shortcut publication finishes.

The required behavior is:

- retain the already-published version;
- remove any shortcuts created by the failed install run;
- clean staging/link scratch artifacts;
- leave the live Orion installation, desktop shortcuts, and runtime untouched.

## Live clean-off precondition

Observed before isolated failure injection:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- live `launcher-session.json`: absent
- live `active-operation.json`: absent

## Isolated failure injection

The real candidate `install.main()` implementation was run against a temporary redirected `LOCALAPPDATA` and temporary Desktop path.

The harness permitted the first shortcut publication step, then injected an `OSError` on the second temporary Desktop shortcut copy.

Observed:

- installer raised: `OSError`
- failure injected: true

## Post-failure sandbox state

Observed after the injected failure:

- published version retained: true
- `Start Orion.lnk`: absent
- `Stop Orion.lnk`: absent
- remaining staging directories: 0
- remaining temporary link directories: 0
- remaining temporary Desktop links: 0

The already-published version was therefore retained, while shortcut publication was rolled back and temporary artifacts were cleaned.

## Live installation verification

The live desktop shortcuts remained unchanged and still referenced the legacy active root:

- Start arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\Users\spill\AppData\Local\Orion\operator\Start-Orion.ps1"`
- Stop arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\Users\spill\AppData\Local\Orion\operator\Stop-Orion.ps1"`

Live final state remained clean-off:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- live launcher session: absent
- live active operation: absent

## Acceptance result

**GATE 3C PASS**

The candidate's documented post-publication failure behavior was validated natively in isolation. A committed version publication was not deleted after shortcut failure; shortcuts created by the failed run were removed; staging and temporary-link artifacts were cleaned; and the live Orion installation/runtime remained untouched.

This validates the installer rollback boundary described in `INSTALL.md` without performing the one-time live legacy transition or installing v2.7.4 into the active Orion path.
