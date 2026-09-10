# Phase 2A Windows Read-Only Preflight — 2026-09-10

Status: PASS

Scope: read-only validation before running the Phase 2A HUD branch on Windows. No runtime, task, config, lifecycle, dependency, or model-call state was changed.

Observed results:

- Accepted operator install exists at version `2.7.4-candidate1`.
- `launcher-session.json` absent.
- `active-operation.json` absent.
- Hermes health endpoint not running.
- Ollama API not running and Ollama process count `0`.
- `Hermes_Gateway_companion`: exactly one task, state `Ready`, exactly one LogonTrigger, enabled LogonTriggers `0`.
- `iai-mcp-daemon`: exactly one task, state `Ready`, exactly one LogonTrigger, enabled LogonTriggers `0`.
- `Orion Host Idle Bridge` absent.
- Startup-folder Orion/Hermes/iai entries: `0`.
- COMPANION `.env` exists and contains an `API_SERVER_KEY` entry; credential value was not printed.
- Hermes Python exists and reports Python `3.11.3`, exit `0`.
- Ollama executable found at the installed local Programs path; client version reports `0.32.15`, exit `0`; warning confirmed no running Ollama instance.
- HUD TCP port `8765` has `0` listeners.

Acceptance interpretation:

The machine remains in the accepted manual-off lifecycle state, scheduled-task login policy remains disabled, the HUD credential prerequisite is present without disclosure, the existing Python runtime is available, and port 8765 is free. Phase 2A may proceed to branch checkout/worktree plus fake-Hermes unit testing only. Starting Hermes, Ollama, iai, or the real HUD remains out of scope for this gate.
