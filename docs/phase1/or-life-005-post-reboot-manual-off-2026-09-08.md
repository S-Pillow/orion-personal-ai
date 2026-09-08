# OR-LIFE-005 Post-Reboot Manual-Off Evidence — 2026-09-08

Status: **POST-REBOOT MANUAL-OFF PASS / OR-LIFE-005 STILL OPEN**

Controlling intent: Orion/Hermes must remain stopped after Windows boot/login in the default manual-off operator mode. Existing Hermes and iai Scheduled Tasks remain registered and enabled, but their LogonTriggers are disabled. Ollama login startup is disabled. Orion is started and stopped explicitly by the operator through one-shot controls.

## Reboot observation

- Windows boot time: `2026-09-08 02:53:49` local.
- Operator waited after login and did **not** invoke Start Orion before verification.

## Manual-off runtime verification

Observed after reboot/login:

- Hermes API listening on `127.0.0.1:8642`: **False**
- iai MCP wrapper count: **0**
- iai daemon process rows: **0**
- Ollama API available on `127.0.0.1:11434`: **False**
- Ollama process count: **0**
- legacy `Orion-Host-Idle-Bridge` process count: **0**
- Orion launcher session file present: **False**

This is the desired default manual-off runtime state.

## Persistence / registration verification

- `%USERPROFILE%\.iai-mcp` store root exists: **True**
- Ollama Startup shortcut present: **False**
- `Hermes_Gateway_companion` task: enabled **True**, state `Ready`, LogonTrigger enabled **False**
- `iai-mcp-daemon` task: enabled **True**, state `Ready`, LogonTrigger enabled **False**
- `Orion Host Idle Bridge` task present: **False**

This preserves supported on-demand registrations while preventing automatic Orion/Hermes/iai startup at login.

## Hermes status verification

The final informational command completed after a short delay:

`hermes -p companion gateway status`

Observed:

- Scheduled Task registered: `Hermes_Gateway_companion`
- Status: `Ready`
- Last Run Time: `9/8/2026 12:50:37 AM`
- Last Run Result: `0`
- `No gateway process detected`

Therefore there is no CLI-status hang to track from this acceptance step.

## Disposition

The **post-reboot manual-off half of OR-LIFE-005 passes**. OR-LIFE-005 itself remains open pending the required post-reboot Start Orion health/memory/Discord verification, Stop Orion return-to-off verification, and separate logoff/logon durability check.

Core Intent Preservation: **PRESERVED**.
