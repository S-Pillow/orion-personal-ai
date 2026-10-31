# Hermes v0.22.5 Isolated Runtime Environment Finding — 2026-10-30

Status: **QUALIFICATION FINDING RECORDED; lock-aware validation pending**

## Exact environment created

The disposable v0.22.5 Windows environment was successfully built from the exact release-pinned toolchain:

- Hermes source candidate: `bf0203a794a07aac3ff764972ab9087baa4e4f4e` plus the qualified Orion compatibility delta;
- CPython: `3.14.9`;
- uv: `0.13.5`;
- `uv sync --locked --extra all --extra edge-tts --extra voice`: completed successfully;
- packages installed: 130;
- `edge-tts==7.3.1` installed;
- initial imports passed before dependency validation.

## Raw dependency-check stop

Raw `uv pip check` returned one incompatibility:

`browser-harness==0.1.13` declares `pillow==12.3.0`, while the locked environment contains `Pillow==13.0.0`.

The gate stopped at that point. No isolated Hermes gateway was started. Production Hermes, COMPANION state, memory, HUD, Ollama, and Orion runtime were not changed or restarted.

## Interpretation

This raw mismatch is expected by the exact v0.22.5 project configuration. The release intentionally overrides browser-harness's stale Pillow pin to Pillow 13.0.0 because Pillow 13 is the security-fixed line. Hermes' own `pm.pip_check` / `PythonEnvironment.check(lock)` implementation exists specifically to distinguish lock-explained override mismatches from unexpected dependency drift.

Therefore raw `uv pip check` exit code alone is not the correct acceptance criterion for this release. Orion will validate the existing isolated environment with the exact v0.22.5 lock-aware checker. Qualification remains fail-closed: only the reviewed browser-harness/Pillow override may be accepted, and any other incompatibility remains a stop condition.

## Security disposition

Do not downgrade Pillow to 12.3.0 solely to make raw metadata validation return zero. That would reverse an upstream security hardening and would violate Orion's Security hard gate.

Production cutover remains unauthorized.
