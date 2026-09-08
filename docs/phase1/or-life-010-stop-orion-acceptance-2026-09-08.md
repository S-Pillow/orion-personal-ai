# OR-LIFE-010 Stop Orion acceptance — 2026-09-08

Status: PASS / accepted for current v2.7 operator-control implementation

## Preconditions
- Start Orion desktop control had already passed.
- Current launcher session recorded `ollamaStartedByOrion: false`, so Ollama was not owned by Orion for this session.

## Stop Orion verification
Observed after invoking the desktop `Stop Orion` control:
- Hermes API listening on `127.0.0.1:8642`: false.
- `hermes -p companion gateway status`: Scheduled Task still registered/Ready; no gateway process detected.
- iai MCP wrapper count: 0.
- `%LOCALAPPDATA%\Orion\operator\launcher-session.json`: absent.
- Ollama health remained available: true.

## Interpretation
The desktop Stop Orion control cleanly stopped Hermes/API, allowed the Hermes-owned iai wrapper to disappear, removed the one-shot operator session record, and correctly left Ollama alone because Orion had not started it.

This preserves the v2.7 ownership rule: Stop Orion may stop a local model provider only when that Orion launcher session started it solely for Orion. iai daemon rest/HIBERNATION remains vendor-owned and is not force-killed by the launcher.

Intent Preservation Check: PRESERVED. No resident Orion supervisor or parallel lifecycle mechanism was introduced.
