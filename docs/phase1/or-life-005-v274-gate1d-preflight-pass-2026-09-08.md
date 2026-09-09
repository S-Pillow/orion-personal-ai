# OR-LIFE-005 v2.7.4 Candidate Gate 1D Preflight PASS — 2026-09-08

Status: **PASS — native primitive and source/pin preflight gate complete**

Candidate: `Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`
Candidate SHA-256: `fd2268aa79883dae2f0fa2b3371de022c3e54be72c85a566be01c893f79d54be`

Accepted evidence:
- Intended Hermes Python: `C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`, Python 3.11.3.
- Offline candidate safety suite: 27/27 tests passed.
- Native Windows primitive checks passed: original-handle retention, mismatch refusal, exact-handle termination, and cross-process canonical-lock exclusion.
- Boot identifier available: `6172837424080388543625888134913610437` for this boot.
- Exact local configuration created for Hermes source/home/Ollama paths and pinned commit.
- Initial preflight correctly blocked on `HERMES_CHECKOUT_NOT_CLEAN`.
- Read-only classification showed exact HEAD pin `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`, no tracked/staged changes, and only one untracked historical Discord backup file.
- Backup `plugins/platforms/discord/adapter.py.orion-pre-17157-20260829-224911.bak` was copied outside the Hermes checkout to `C:\Users\spill\Documents\Orion-Hermes-Backups\20260908-055031\adapter.py.orion-pre-17157-20260829-224911.bak`; source and destination SHA-256 both `6E7EB8E0C3C5640028E8117A406BB7DB8DE2C5CEE0FAF019A5371DC5F629FCCB`.
- After verified backup relocation, Hermes checkout was clean at the exact pin.
- Preflight rerun passed and reported package `2.7.4-candidate1`, exact pin, exact Hermes Python/source, existing COMPANION profile, and available boot identity.
- Preflight explicitly performed source/path checks only; no Hermes imports, runtime starts, or health calls.

No Orion/Hermes/Ollama runtime was started by this gate. No Scheduled Task, login trigger, memory configuration, or installed Orion control was changed.

Next gate: candidate worker ready/go/result handshake and pinned vendor `status` binding validation only, before any installation or lifecycle start/stop action.

Core Intent Preservation: **PRESERVED**.
