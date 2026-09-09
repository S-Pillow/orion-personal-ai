# OR-LIFE-005 Final Acceptance — 2026-09-09

Status: PASS

Installed version under acceptance: `2.7.4-candidate1`

## Accepted restart path

- Real Windows restart observed by changed boot identity.
- Installed publication survived restart.
- All 10 published runtime/config files retained identical SHA-256 hashes.
- Desktop Start/Stop shortcut contract survived unchanged.
- `Hermes_Gateway_companion` and `iai-mcp-daemon` task registrations survived with LogonTriggers disabled.
- Post-login state remained manual-off: Hermes unhealthy/off, Ollama unhealthy/off, no Ollama process, no launcher session, no active operation.
- Installed Start after restart returned `ORION READY`, Hermes healthy, Ollama healthy, one Ollama process, launcher session present, no active operation.
- Installed Stop after restart returned `Owned Ollama: stopped` and `ORION STOPPED; iai remains vendor-managed.`
- Final state after Stop returned to clean-off with no lifecycle metadata.

## Accepted logoff/logon path

- Pure Windows sign-out/sign-in observed with boot identity unchanged.
- Installed publication survived logoff/logon.
- All 10 published runtime/config files retained identical SHA-256 hashes.
- Desktop Start/Stop shortcuts survived unchanged.
- Task registrations survived with LogonTriggers disabled.
- Post-logon state remained manual-off.
- Installed Start after logon returned `ORION READY`, Hermes healthy, Ollama healthy, one Ollama process, launcher session present, no active operation.
- Installed Stop after logon returned `Owned Ollama: stopped` and `ORION STOPPED; iai remains vendor-managed.`
- Final clean-off verified with Hermes off, Ollama off, zero Ollama processes, no session, no active operation.

## Conclusion

OR-LIFE-005 is fully accepted for both restart and logoff/logon persistence and lifecycle behavior. Installed publication and manual-off lifecycle are accepted.

No HUD/UI work was started by this acceptance action.
