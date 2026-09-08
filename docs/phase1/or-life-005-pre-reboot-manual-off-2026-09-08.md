# OR-LIFE-005 pre-reboot manual-off checkpoint

Date: 2026-09-08
Status: PASS / READY FOR REBOOT ACCEPTANCE

## Runtime state before reboot
- Hermes API listening: False
- iai MCP wrapper count: 0
- Ollama API available: False
- Ollama process count: 0
- Orion launcher session exists: False
- Ollama login Startup shortcut present: False
- Hermes gateway process absent (`hermes -p companion gateway status` reported no gateway process detected)

## Scheduled-task state
### Hermes_Gateway_companion
- Task enabled: True
- Task state: Ready
- Trigger: MSFT_TaskLogonTrigger
- Trigger enabled: False

### iai-mcp-daemon
- Task enabled: True
- Task state: Running
- Trigger: MSFT_TaskLogonTrigger
- Trigger enabled: False

The iai task being Running at this checkpoint is not a blocker: this is the already-running vendor daemon instance from the prior Orion session. Stop Orion intentionally leaves iai under its own idle/HIBERNATION lifecycle. The decisive OR-LIFE-005 reboot acceptance condition is that after Windows restart/login, with the LogonTrigger disabled, the iai daemon does not auto-start.

## Legacy bridge
- Orion Host Idle Bridge task present: False

## Disposition
Manual-off pre-reboot state is accepted. Proceed to a real Windows restart. After login, do not click Start Orion before collecting post-reboot evidence.

Intent Preservation Check: PRESERVED.
