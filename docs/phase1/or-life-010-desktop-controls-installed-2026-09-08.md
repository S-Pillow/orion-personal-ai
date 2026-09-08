# OR-LIFE-010 desktop controls — installation checkpoint

Date: 2026-09-08
Status: INSTALLED / FUNCTIONAL ACCEPTANCE PENDING

## Installed operator controls

Source-controlled operator controls from commit `4b96249759a601b95f923c0e5867124ff30e4124` were installed successfully.

Installed scripts:
- `%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1`
- `%LOCALAPPDATA%\Orion\operator\Stop-Orion.ps1`

Desktop shortcuts:
- `%USERPROFILE%\Desktop\Start Orion.lnk`
- `%USERPROFILE%\Desktop\Stop Orion.lnk`

Installer reported: `No background supervisor was installed.`

## Lifecycle context

Manual-off task configuration is already in place:
- `Hermes_Gateway_companion`: task enabled, LogonTrigger disabled.
- `iai-mcp-daemon`: task enabled, LogonTrigger disabled.
- `Orion Host Idle Bridge`: absent.

The next acceptance step is to exercise Start Orion from the desktop, verify Hermes API health and memory availability, then exercise Stop Orion and verify clean shutdown. This checkpoint does not by itself close OR-LIFE-010 or OR-LIFE-005.

Intent Preservation Check: PRESERVED. The desktop controls are one-shot launchers and do not introduce a resident Orion lifecycle supervisor.
