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

## Non-blocking observation

The final informational command:

`hermes -p companion gateway status`

hung after printing no output. The operator was instructed to cancel it with Ctrl+C and not rerun it during this acceptance step. This does not invalidate the manual-off boot-state evidence above because direct HTTP, process, task-trigger, persistence, and legacy-bridge checks had already completed successfully before the hung command.

Treat the CLI-status hang as a separate follow-up observation unless it reproduces during normal supported start/stop behavior.

## Disposition

The **post-reboot manual-off half of OR-LIFE-005 passes**. OR-LIFE-005 itself remains open pending the required post-reboot Start Orion health/memory/Discord verification, Stop Orion return-to-off verification, and separate logoff/logon durability check.

Core Intent Preservation: **PRESERVED**.
