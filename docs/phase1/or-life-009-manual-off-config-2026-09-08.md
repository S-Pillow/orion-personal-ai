# OR-LIFE-009 manual-off configuration — accepted

Date: 2026-09-08
Status: PASS / CONFIGURATION ACCEPTED

## Governing requirement
Orion Master PRD v2.7 OR-LIFE-009 and §22 step 2.

## Final verified state

### Hermes_Gateway_companion
- Scheduled Task remains registered.
- Task enabled: True.
- Task state: Ready.
- Trigger type: MSFT_TaskLogonTrigger.
- LogonTrigger enabled: False.

### iai-mcp-daemon
- Scheduled Task remains registered.
- Task enabled: True.
- Task state: Ready.
- Trigger type: MSFT_TaskLogonTrigger.
- LogonTrigger enabled: False.
- This preserves the installed vendor task for on-demand activation while preventing login startup in default manual mode.

### Obsolete Docker-era task
- `Orion Host Idle Bridge` Scheduled Task: absent.
- The historical script source was not deleted as part of this configuration change.

### Hermes persistence fallback
- Prior verification found zero Hermes Gateway items in the Windows Startup folder.

### Runtime state during configuration
- Hermes COMPANION was stopped through `hermes -p companion gateway stop` and drained cleanly.
- Hermes API `127.0.0.1:8642` was confirmed not listening afterward.

## Recovery evidence
Before task mutations, XML backups were created under:
`C:\Users\spill\Documents\Orion-Task-Backups\20260908-020211`

Backed-up task definitions:
- Hermes_Gateway_companion
- iai-mcp-daemon
- Orion Host Idle Bridge

## Execution note
The first non-elevated attempt could remove the obsolete Host Idle Bridge but could not modify the two retained tasks (`0x80070005 Access is denied`). The trigger edits were then repeated from an elevated PowerShell session and verified successfully.

## Disposition
The PRD v2.7 manual-off persistence policy is now configured. Do not treat this configuration alone as full OR-LIFE-005 acceptance; restart and separate logoff/logon validation plus manual Start Orion / Stop Orion acceptance remain.

Intent Preservation Check: PRESERVED. Vendor Scheduled Tasks/lifecycle mechanisms remain authoritative; Orion only changes whether login triggers are active in the owner-selected manual mode.
