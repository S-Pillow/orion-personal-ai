# OR-LIFE-005 v2.7.4 Candidate — End-of-Session Clean-Off Checkpoint

Date: 2026-09-08
Candidate validation branch: `feature/orion-start-v272-lifecycle-safety`
Candidate: `Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`
Hermes pin: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## Purpose

Record the safe stopping point after native Windows candidate validation through Gate 2F. This is documentation only; it does not merge or install the candidate implementation.

## Final runtime state

Gate 2F ended in clean-off state:

- Hermes API: off
- Ollama API: off
- Ollama process count: 0
- candidate `launcher-session.json`: absent
- candidate `active-operation.json`: absent
- independent test Ollama: terminated only after exact PID/image/start-time identity verification
- Hermes source checkout remained clean at the approved pin

Persistence policy remains the approved manual-off configuration:

- `Hermes_Gateway_companion`: registered/enabled, LogonTrigger disabled
- `iai-mcp-daemon`: registered/enabled, LogonTrigger disabled
- `Orion Host Idle Bridge`: absent
- Ollama Startup shortcut: removed

iai remains vendor-managed and is intentionally not force-stopped by Orion Stop.

## Candidate validation accepted so far

- Static review: ACCEPT FOR NATIVE WINDOWS VALIDATION
- Gate 1A: Windows PowerShell 5.1 parse PASS
- Gate 1B: read-only discovery PASS
- Gate 1C: installed Hermes/Ollama provenance resolved
- Gate 1D: Python 3.11.3, 27 offline tests PASS, native Windows primitives PASS, clean exact-pin preflight PASS
- Gate 2A: real worker handshake + pinned vendor status binding PASS; missing-task start/install veto PASS
- Gate 2B: controlled cold Start PASS
- Gate 2C: session ownership identity PASS; corrected resource interpretation
- Gate 2D: first real model inference + Discord `/new` roundtrip + ambient iai marker recall PASS; severe prior slowdown did not reproduce; corrected telemetry stayed healthy
- Gate 2E: candidate Stop PASS; Orion-owned Ollama stopped; wrapper absent after Stop
- Gate 2F: independent-runtime ownership PASS; independent Ollama was not claimed or stopped by Orion

## Important correction

The initial Gate 2B CSV observer produced invalid numeric column interpretation because formatted numbers containing commas were written without CSV quoting. The apparent `264 MB free RAM` result is rejected as telemetry evidence.

Corrected Gate 2D telemetry during real first inference showed approximately:

- minimum free RAM: 4.55 GB
- maximum pagefile usage: 88 MB
- maximum GPU used: 2.65 GiB
- minimum GPU free: 5.36 GiB

The earlier severe post-reboot slowdown remains unexplained, but it did not reproduce under the v2.7.4 controlled start + first-inference path.

## Not yet accepted / not installed

The v2.7.4 candidate is **not installed, merged to main, or deployment-accepted**. This main-branch document records validation status only.

Remaining acceptance work includes selected native fault/race/recovery cases, installation/publication validation, then post-install OR-LIFE-005 recovery Start/Stop and a separate real logoff/logon manual-off durability test.

Do not rerun already accepted HIBERNATION cycles or Gates 1 / 2A–2F without contradictory evidence.

## Resume point

Resume from the remaining Gate 2 fault/recovery coverage using isolated/native harnesses where possible. Avoid destabilizing the accepted production Hermes installation merely to satisfy fault injection.

After Gate 2 is sufficiently complete, proceed to Gate 3 installation/workflow validation. Only after installation acceptance should the final post-reboot recovery Start/Stop and separate real logoff/logon close OR-LIFE-005.

OR-LIFE-007 owner disposition remains pending final Phase 1 closure; current recommendation is ACCEPT the observed 5.887 s vendor wake path with no additional iai patch.

Core Intent Preservation: **PRESERVED**.
