# OR-LIFE-005 Start Launcher Patch Review — 2026-09-08

Status: **v2.7.1 PATCH REJECTED / DO NOT INSTALL**

The static review of the proposed cold-start patch identified material ownership and rollback defects. The patch must not be installed or used for further live acceptance testing.

## Accepted review findings

1. Hermes ownership cannot be inferred from a failed health probe. An unhealthy or still-starting pre-existing gateway must not be claimed as owned by the current Start Orion attempt.
2. `hermes ... gateway start` and rollback `gateway stop` are synchronous and currently unbounded by the readiness timeout. Native command execution needs its own bounded timeout.
3. Rollback outcomes must be checked and recorded; endpoint failure alone is not sufficient proof that a process stopped.
4. Ollama ownership should include stronger identity (PID plus process start time) and distinguish prior-session ownership from processes created by the current attempt.
5. Concurrent Start Orion invocations need a per-user exclusive launch lock.

## Nuance on the missing `.tmp` artifact

The review statement about the patch deleting `launcher-session.json.tmp` is correct for the rejected v2.7.1 patch, but the production incident occurred before that patch was installed. The launcher actually running during the incident did not delete the temporary session file in its catch block. Therefore the observed absence of both `launcher-session.json` and `launcher-session.json.tmp` is evidence that the incident likely occurred before or outside the state-write/rename path, but it is not treated as absolute proof of the exact failure stage.

## Repository disposition

The unaccepted v2.7.1 launcher source was reverted from `main` before installation. The installed operator launcher on Steven's PC was never replaced by v2.7.1.

Future replacement requirements:
- pre-existing Hermes presence/identity check independent of health;
- attempt-scoped ownership only;
- bounded native start/stop command execution;
- verified rollback with recorded outcomes;
- PID + process start-time identity for Ollama;
- exclusive per-user launch lock;
- conservative failure semantics that do not stop unrelated or pre-existing services;
- no supervisor/background monitor.

Core Intent Preservation: **PRESERVED**.