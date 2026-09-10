# Phase 2A Fake-Hermes Test Gate — 2026-09-10

Status: PASS WITH PRE-LIVE HARDENING NOTE

Tested branch head: `5f888150504cc7d45ed1fc38083e424171ebf4bd`

Observed on Windows:

- isolated checkout created at `C:\Users\spill\Documents\Orion-Phase2A-PR9`
- exact branch head matched expected commit
- required Phase 2A HUD files present
- `hud/orion_hud_bridge.py` compiled successfully under Python 3.11.3
- 14 fake-Hermes unit/integration tests passed in 9.390 seconds
- real Hermes remained offline
- real Ollama remained offline with zero Ollama processes
- HUD port 8765 had zero listeners after tests
- no model call was made
- no lifecycle or Scheduled Task state was changed

## Pre-live hardening note

Two rejection-path tests emitted follow-on parser noise after the intended response:

- `Bad request syntax ('{}')`
- `Bad HTTP/0.9 request type ('{"title":')`

The intended rejection responses themselves passed and no authorization boundary was bypassed. The noise indicates that rejected POST request bodies can remain unread on an HTTP/1.1 keep-alive connection and then be interpreted as another request by `BaseHTTPRequestHandler`.

Before any live Hermes proof, harden the bridge so POST connections close after the response (or otherwise consume rejected request bodies safely), then rerun the fake-Hermes gate. This is a pre-live quality/security hardening item, not a failure of the Phase 2A architecture.
