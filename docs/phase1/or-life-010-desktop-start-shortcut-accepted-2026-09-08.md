# OR-LIFE-010 desktop Start Orion shortcut acceptance

Date: 2026-09-08
Status: ACCEPTED

## Test
The actual desktop `Start Orion` shortcut was invoked from a fully manual-off state after Ollama login startup had been disabled.

Post-launch verification:
- Hermes API `http://127.0.0.1:8642/health`: healthy / HTTP 200
- Ollama API `http://127.0.0.1:11434/api/tags`: healthy / HTTP 200
- Orion launcher session state present
- `ollamaStartedByOrion`: `true`
- tracked Ollama PID: `24876`

This resolves the earlier anomalous shortcut observation. The desktop shortcut successfully launches the same accepted one-shot Start Orion control path.

## Disposition
OR-LIFE-010 desktop Start Orion shortcut path: ACCEPTED.

The Start/Stop operator control pair has now passed:
- desktop install
- Start with pre-existing Ollama
- Stop without claiming external Ollama ownership
- full manual-off state
- Start with Orion-owned Ollama
- ownership persistence
- Stop of Orion-owned Ollama
- actual desktop Start shortcut invocation

Intent Preservation Check: PRESERVED. No resident Orion supervisor was introduced; the launcher acts, verifies readiness, records only session ownership needed for matching shutdown, then exits.
