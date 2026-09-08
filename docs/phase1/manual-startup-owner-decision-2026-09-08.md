# Orion manual startup owner decision — 2026-09-08

Status: **OWNER DECISION — ACCEPTED**

Steven clarified the desired native-Windows lifecycle for Orion/COMPANION:

- Orion/Hermes must **not** auto-start on Windows reboot or user logon.
- Steven wants to start and stop Orion/Hermes manually when needed.
- The supported manual Hermes lifecycle should remain available.
- The `iai-mcp-daemon` Scheduled Task must remain installed because it is the vendor wake mechanism used on demand by the iai MCP wrapper from HIBERNATION. It must not be removed merely to prevent Hermes auto-start.
- Legacy Docker-era startup artifacts, including the `Orion Host Idle Bridge` task, are not part of the current v2.6 native-Windows architecture and should be removed after evidence/backup of their definitions.

## Revised desired boot state

After Windows boot/logon, before Steven manually starts Orion:

- Hermes COMPANION gateway: stopped
- Hermes API on `127.0.0.1:8642`: not listening
- iai MCP wrapper: absent
- iai daemon: may remain parked/absent unless independently required by its vendor lifecycle; it should not be forced awake by Orion/Hermes at login
- no legacy Orion Host Idle Bridge process/window

After Steven manually starts Orion/Hermes:

- COMPANION gateway starts through the supported Hermes lifecycle
- Hermes API becomes available
- Hermes owns the iai stdio wrapper
- iai may wake on demand through the retained `iai-mcp-daemon` Scheduled Task

## OR-LIFE-005 implication

The 2026-09-08 restart integrity run remains valid evidence that the store, gateway task, API, iai daemon, and memory survived a real Windows restart without corruption. However, unattended Hermes auto-start is **not** the desired final product behavior and therefore is not accepted as the target boot configuration.

OR-LIFE-005 should close only after the startup configuration is corrected and a subsequent reboot/logoff-logon confirms:

1. Orion/Hermes remains stopped until manually started.
2. No obsolete Docker-era startup bridge launches.
3. Manual Orion/Hermes start still works.
4. iai on-demand wake still works with the vendor Scheduled Task retained.
5. Store integrity and recall remain correct.

Intent preservation: **PRESERVED** — Hermes remains the conversation/gateway owner; iai remains memory/lifecycle authority; no Orion supervisor is introduced.
