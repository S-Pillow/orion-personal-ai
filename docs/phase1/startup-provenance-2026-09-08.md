# Phase 1 startup provenance — 2026-09-08

Status: READ-ONLY DISCOVERY COMPLETE

## Owner lifecycle decision

Current Orion v2.6 intent is manual lifecycle control:

- Windows boot/logon must not automatically start Orion/Hermes.
- Steven starts Orion/Hermes manually when needed and stops it manually when finished.
- The iai vendor daemon Scheduled Task remains installed because it is the accepted on-demand HIBERNATION wake mechanism.

## Restart startup provenance

Read-only process and Scheduled Task inspection after the 2026-09-08 reboot identified the two startup windows:

1. `powershell.exe` PID 10476
   - command: `C:\HermesAgent\bin\Orion-Host-Idle-Bridge.ps1`
   - parent: `svchost.exe`
   - Scheduled Task: `Orion Host Idle Bridge`
   - action writes `C:\HermesAgent\data\orion-runtime\host-idle.json` and `host-idle-bridge.pid`
   - disposition: obsolete Docker-era Orion lifecycle component; not part of current native-Windows v2.6 architecture; candidate for removal after backup/export of task definition.

2. `cmd.exe` PID 7636
   - command: `C:\Users\spill\.iai-mcp\daemon-start.cmd`
   - parent: `svchost.exe`
   - Scheduled Task: `iai-mcp-daemon`
   - disposition: legitimate iai vendor daemon activation path; retain.

Current Hermes task:

- Scheduled Task: `Hermes_Gateway_companion`
- action: `wscript.exe //B //Nologo "C:\Users\spill\AppData\Local\hermes\profiles\companion\gateway-service\Hermes_Gateway_companion.vbs"`
- principal: `spill`, interactive logon
- owner intent requires removal/disablement of its automatic trigger while preserving a supported manual start/stop path.

Startup folders and Run registry entries contained no additional Orion/Hermes startup entries. `Ollama.lnk` is present in the user Startup folder; Docker Desktop is present in HKCU Run, but these were not changed by this discovery.

## Next safe step

Before mutating Scheduled Tasks:

1. inspect the exact triggers on `Hermes_Gateway_companion`, `iai-mcp-daemon`, and `Orion Host Idle Bridge`;
2. export task XML for rollback;
3. remove/disable only the obsolete `Orion Host Idle Bridge`;
4. remove the Hermes automatic startup trigger or otherwise retire the autostart task while preserving supported manual `hermes -p companion gateway start/stop` operation;
5. leave `iai-mcp-daemon` installed and its vendor wake behavior intact;
6. repeat boot/logon acceptance with Hermes stopped by default.

Intent preservation: PRESERVED.
