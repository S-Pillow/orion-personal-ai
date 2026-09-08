# OR-LIFE-010 Start Orion acceptance — 2026-09-08

Status: PASS for Start Orion path; Stop Orion still pending.

## Preconditions
- Orion v2.7 manual-off task policy had been applied.
- `Hermes_Gateway_companion` Scheduled Task retained/enabled with LogonTrigger disabled.
- `iai-mcp-daemon` Scheduled Task retained/enabled with LogonTrigger disabled.
- Obsolete `Orion Host Idle Bridge` Scheduled Task removed.
- One-shot Start/Stop Orion operator controls installed under `%LOCALAPPDATA%\Orion\operator` with desktop shortcuts.

## Start Orion acceptance evidence
After launching **Start Orion** from the desktop:

Hermes:
- `http://127.0.0.1:8642/health` returned HTTP 200.
- `hermes -p companion gateway status` reported Scheduled Task registered and gateway process running.
- Gateway PID observed: 21312.

iai:
- daemon process rows: 2 (known single logical venv/base-Python chain pattern from earlier accepted evidence; not treated as duplicate daemons).
- MCP wrapper count: 1.

Memory:
- canonical marker queried: `ORION_CAPTURE_FRESH_GATEWAY_20260829`.
- recall JSON parsed successfully.
- recall source: `daemon`.
- recall count: 5.
- known marker found: true.

Operator session state:
- `%LOCALAPPDATA%\Orion\operator\launcher-session.json` exists.
- `ollamaStartedByOrion=false`.
- tracked Ollama PID empty/null.

Interpretation: Ollama was already available before Start Orion, so the ownership rule correctly did not claim it. Stop Orion must therefore leave Ollama running for this session.

## Disposition
OR-LIFE-010 Start path: PASS.
Remaining paired acceptance: execute desktop **Stop Orion**, then verify Hermes/API are down, wrapper is absent, session state is cleared/updated as designed, and Ollama remains available because Orion did not start it.

Intent Preservation Check: PRESERVED. Start uses the supported Hermes lifecycle and iai remains demand-wake managed; no resident Orion supervisor was introduced.
