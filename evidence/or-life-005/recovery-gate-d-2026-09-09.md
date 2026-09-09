# OR-LIFE-005 Changed-Boot Recovery Acceptance

Date: 2026-09-09
Branch: feature/orion-start-v272-lifecycle-safety
Installed version: 2.7.4-candidate1

## Result

RECOVERY GATE D PASS.

Observed evidence:

- Recorded boot identity before restart: `134334129385000000`
- Current boot identity after real Windows Restart: `134334145095000000`
- Boot changed: `True`
- Boot comparison exit: `0`
- Post-restart precondition remained manual-off:
  - Hermes healthy: `False`
  - Ollama healthy: `False`
  - Ollama process count: `0`
  - Session exists: `False`
  - Active operation exists: `True`
- Supported installed recovery output: `Previous-boot records archived. No processes stopped.`
- Recovery exit: `0`
- Post-recovery:
  - Active operation exists: `False`
  - Session exists: `False`
  - Hermes healthy: `False`
  - Ollama healthy: `False`
  - Ollama process count: `0`

## Interpretation

The fixed boot identity based on Windows kernel BootTime changed across a real Windows Restart. The supported recovery path accepted and archived the previous-boot recovery journal without starting or stopping runtime processes. Changed-boot recovery behavior is accepted.

## Defect discovered during acceptance

The original `win_process.boot_id()` implementation used `NtQuerySystemInformation(90)` and returned a value that remained unchanged across a genuine Windows Restart, causing recovery to fail closed with `RECOVERY_REQUIRES_WINDOWS_RESTART` even after a real restart.

A bounded installed hotfix replaced the boot identity source with `SystemTimeOfDayInformation` (`NtQuerySystemInformation(3)`) `BootTime`. Proof showed kernel BootTime exactly matched Windows `LastBootUpTime` for the active boot. A fresh recovery record created using the fixed identity then changed across the next real restart and recovered successfully.

Original installed `win_process.py` backup retained at:
`C:\Users\spill\Documents\Orion-BootId-Hotfix-20260909-035126\win_process.py`

Original installed SHA-256:
`80D4E0BC57DC81977206B7E78837E0765F213112F2FE556CD57993665EAB3ED3`

Patched installed SHA-256:
`E0E176790E482FEF8D8EF58D52C4C35F9182E5C2D47C51D4DDB44499761433E6`

Source-control closure of the BootTime hotfix remains required before Phase 1 closure.
