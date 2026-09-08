# OR-LIFE-005 manual-off configuration — partial execution

Date: 2026-09-08
Status: PARTIAL / NOT CLOSED

## Intended v2.7 target
- Hermes_Gateway_companion task retained/enabled; LogonTrigger disabled.
- iai-mcp-daemon task retained/enabled; LogonTrigger disabled so demand-start remains available.
- Obsolete Orion Host Idle Bridge task removed.
- No Hermes Startup-folder fallback.
- Hermes gateway/API off after manual stop.

## Execution result
Backup directory created before changes:
`C:\Users\spill\Documents\Orion-Task-Backups\20260908-020211`

Backups created for:
- Hermes_Gateway_companion
- iai-mcp-daemon
- Orion Host Idle Bridge

Hermes stopped cleanly through supported lifecycle:
- `hermes -p companion gateway stop`
- result: `Gateway stopped (drained cleanly)`
- gateway process absent afterward
- API `127.0.0.1:8642` not listening afterward

Obsolete Docker-era task:
- `Orion Host Idle Bridge` unregistered successfully
- verification: task absent

Startup fallback:
- Hermes Startup-folder items: 0

## Blocker
Attempts to disable the LogonTriggers for both retained tasks failed with Windows Task Scheduler access denied (`0x80070005`) through `Set-ScheduledTask`.

Post-attempt verification confirmed both triggers remained enabled:
- Hermes_Gateway_companion: task enabled, Ready, LogonTrigger enabled=True
- iai-mcp-daemon: task enabled, Ready, LogonTrigger enabled=True

Because commands were pasted interactively, later commands continued after the two trigger-edit failures even though `$ErrorActionPreference='Stop'`; therefore the final printed `MANUAL-OFF CONFIGURATION COMPLETE` banner is not evidence of completion.

## Disposition
Manual-off configuration is only partially applied. Do not reboot/logoff for OR-LIFE-005 acceptance until the two LogonTriggers are successfully disabled from an elevated Task Scheduler context and re-verified.

Intent Preservation Check: PRESERVED. No vendor lifecycle replacement was introduced.
