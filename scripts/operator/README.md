# Orion operator controls

These scripts implement the accepted manual-off operator lifecycle under Orion Master PRD v2.9. They are one-shot Windows operator controls, not a resident supervisor, and they preserve vendor ownership of Hermes and iai lifecycle behavior.

## Files

- `Start-Orion.ps1` — one-shot launcher. Ensures Ollama is available, starts Hermes profile `companion` through the supported Hermes gateway command, waits for direct loopback API health, then verifies/reuses or starts the accepted loopback HUD and opens it in the default browser before exiting.
- `Stop-Orion.ps1` — one-shot shutdown. Stops Hermes profile `companion` through the supported Hermes gateway command, confirms the API is down, stops only an identity-matched HUD bridge that this Orion launcher session started, stops Ollama only when the current Orion launcher session owns the recorded Ollama process, and exits. iai is not killed; it remains under its vendor idle/HIBERNATION lifecycle.
- `Hud-Operator.ps1` — shared operator-only HUD process helper. It verifies the Orion HUD identity on `127.0.0.1:8765`, starts the installed bridge when needed, records exact process identity for owned HUD instances, opens the verified HUD URL, and permits Stop Orion to terminate only the recorded still-matching owned bridge process.
- `Install-Orion-Desktop-Shortcuts.ps1` — installs the one-shot scripts, HUD helper, and accepted HUD runtime under `%LOCALAPPDATA%\Orion`, then creates `Start Orion` / `Stop Orion` desktop shortcuts using `-ExecutionPolicy Bypass` for the launcher process only.

## Current lifecycle behavior

- Orion remains manual-off by default. These controls do not install login persistence or create an Orion lifecycle supervisor.
- Local loopback health checks bypass configured HTTP proxies explicitly. This prevents host proxy settings from turning a healthy `127.0.0.1` Ollama, Hermes, or HUD endpoint into a false failure.
- `Start-Orion.ps1` polls observable health instead of relying on a fixed sleep. The default Ollama health window is 60 seconds, Hermes health window is 30 seconds, and HUD health window is 15 seconds.
- On the current Orion Windows workstation, Orion-started Ollama is launched with the process-local `OLLAMA_LLM_LIBRARY=rocm_v7_1` selection. This bypasses unsuitable backend autodetection for the AMD Radeon RX 9070 XT while leaving the parent PowerShell environment unchanged immediately after `Start-Process` returns.
- The ROCm selection applies only when Orion itself launches `ollama serve`. If Ollama is already healthy before Start Orion, the launcher does not replace, restart, or reconfigure that pre-existing provider.
- The launcher records the known Ollama library in `launcher-session.json` when it launched or inherited a prior Orion-owned session that already recorded the library. This is diagnostic provenance only; it does not transfer ownership.
- When Orion starts `ollama serve`, stdout/stderr are captured under `%LOCALAPPDATA%\Orion\operator\logs`. Startup failures distinguish process exit, port binding without a healthy API, and failure to bind, and include the selected backend when known.
- Ollama ownership remains tied to the process that this launcher started. Listener inspection is diagnostic only and does not transfer ownership to another Ollama process.
- After Hermes/API health is confirmed, Start Orion checks the accepted HUD at `http://127.0.0.1:8765/`. The probe requires both the `OrionHUD/2A` server identity and the accepted Orion page title before the launcher will reuse or open that local endpoint.
- If a verified HUD is already available, Start Orion reuses it. Ownership is carried forward only when `launcher-session.json` still identifies the same PID, executable path, creation time, and bridge command. A pre-existing HUD is never claimed merely because it owns port 8765.
- If no verified HUD is available and port 8765 is clear, Start Orion launches the installed standard-library HUD bridge from `%LOCALAPPDATA%\Orion\hud`, waits for verified readiness, persists exact HUD process identity when Orion owns it, and then opens the verified URL in the default browser.
- HUD Python discovery resolves `sys._base_executable` and launches the real Python base interpreter rather than retaining ownership of a possible Windows virtualenv redirector process. This keeps the recorded HUD PID tied to the process that actually serves the bridge.
- If port 8765 is occupied by an unverified process, Start Orion fails closed rather than replacing, claiming, or opening it as Orion.
- A recoverable launcher state is written after Ollama/Hermes health but before HUD startup/open failure points. If a new Orion-owned HUD starts and its ownership persistence subsequently fails, Start immediately attempts identity-verified rollback of that exact bridge before returning failure. A rollback failure is reported explicitly; Start does not silently convert it to a clean state.
- `Stop-Orion.ps1` verifies the supported Hermes stop path by observing the loopback health endpoint go down. It may stop only an exact recorded Orion-owned HUD bridge and the recorded Orion-owned Ollama process tree; unrelated HUD/Python/Ollama processes are left alone.
- Before stopping an Orion-owned Ollama process, `Stop-Orion.ps1` snapshots its descendant process tree from `Win32_Process`. Candidate parent/child relationships must also pass creation order validation: a child created before its purported parent is treated as a stale `ParentProcessId` relationship and is not claimed or traversed.
- The validated descendant identities are persisted atomically to `launcher-session.json` before the Ollama parent is terminated. A failed descendant cleanup therefore retains enough ownership evidence for a later Stop Orion invocation to retry cleanup even when the parent is already gone.
- After the parent exits, valid descendants are given time to terminate naturally. A surviving descendant is revalidated immediately before termination and is stopped through its verified process handle only when PID, name, executable path, and creation identity still match the persisted pre-stop snapshot. Process-query failures fail Stop instead of being treated as proof of exit.
- `Start-Orion.ps1` refuses to start a new Orion session while persisted Ollama descendant cleanup is pending. The operator must run Stop Orion again so the retained identities can be reconciled safely instead of overwriting them.
- `launcher-session.json` is removed only after Hermes is down, any Orion-owned HUD bridge is handled, the Orion-owned Ollama parent is handled, and all persisted/fresh identity-matched Ollama descendants are confirmed gone.
- The scripts do not directly start or stop `iai-mcp-daemon`; iai demand-wake, idle, and HIBERNATION behavior remain iai/Hermes-owned.

## ROCm 7.1 correction evidence

The operator correction was selected from real workstation evidence rather than generic hardware assumptions:

- unrestricted Ollama 0.32.15 discovery bound `127.0.0.1:11434` but repeatedly timed out while probing unsuitable backends;
- Vulkan-only server liveness succeeded, but `qwen3.5-hermes:9b` crashed during Vulkan model loading;
- process-local `rocm_v7_1` server startup succeeded and the actual `qwen3.5-hermes:9b` model completed an `/api/generate` request on the AMD Radeon RX 9070 XT;
- the temporary diagnostic processes were cleaned up and no persistent Ollama environment or global configuration was changed.

The operator script therefore uses the same process-local ROCm selection only for Orion-owned Ollama startup. It does not rewrite user-level or machine-level Ollama environment variables or configuration.

## Owned Ollama tree cleanup evidence

The first full ROCm operator acceptance run proved Start, direct health, session ownership, environment restoration, ROCm runtime selection, and actual model inference, but it also exposed a shutdown gap: after the recorded Orion-owned `ollama.exe` PID exited, its `llama-server.exe` model runner could remain alive. The API was already down, so parent-only shutdown evidence was insufficient.

Stop Orion now treats the pre-stop descendant snapshot as part of the same Orion-owned lifecycle boundary. Creation order validation rejects stale parent links caused by Windows PID reuse. Valid descendants are persisted before parent termination, receive a grace period after the parent exits, and any survivor is revalidated and force-stopped through a verified process handle only when its identity still matches the captured snapshot. If cleanup fails, the state is retained for retry and Start Orion will not overwrite that pending cleanup state. Unrelated `llama-server.exe` or other processes are not selected by name and remain untouched.

## Final Windows lifecycle acceptance — PASS (2026-10-28)

The ROCm/owned-Ollama-tree operator correction is accepted on the real Orion workstation.

Accepted source chain:

- PR #74 / merge `6e862102df1e68fd6f707aff3ddb3ced1ea8fa25` — process-local ROCm 7.1 startup for Orion-owned Ollama;
- PR #75 / merge `40f96933e9e429b885c9c7a11cfac781c8b99104` — durable, identity-checked cleanup of Orion-owned Ollama descendants;
- PR #76 / merge `3cbc1fa4831966fefce5f2711d82032965080fb2` — Windows PowerShell empty-descendant binding correction.

Final live acceptance proved all of the following in one bounded run:

- installed Start/Stop controls matched the accepted source hashes;
- no process-, user-, or machine-level persistent `OLLAMA_LLM_LIBRARY` mutation was introduced;
- Orion-started Ollama used `rocm_v7_1` and both Ollama and Hermes became healthy;
- the actual `qwen3.5-hermes:9b` model completed an `/api/generate` request with HTTP 200;
- the owned descendant tree was observed, including the live `llama-server.exe` model runner;
- Stop Orion persisted the owned descendant identities before parent termination, stopped the recorded Ollama parent, identity-checked and force-stopped the surviving owned model runner, and left unrelated processes untouched;
- Hermes and Ollama APIs were down after Stop, port 11434 was clear, and launcher session state was removed;
- a final Start returned Orion to a healthy running state on `rocm_v7_1` with zero pending descendant cleanup identities.

The durable acceptance record is `docs/evidence/operator-lifecycle-acceptance-2026-10-28.md`.

## HUD launch-after-health Windows acceptance — PASS / CLOSED (2026-10-29)

OR-LIFE-010 HUD launch-after-health is accepted on the real Orion Windows workstation at implementation checkpoint:

`7465492a7daebb1bf2630f2687668e575177291b`

Merged implementation:

- PR #78 — `Open accepted HUD after Orion runtime health`.

Live Windows acceptance proved:

- installed operator/HUD files matched source and both desktop shortcuts were wired correctly;
- Ollama became healthy first, Hermes became healthy second, and the verified Orion HUD became healthy only afterward;
- the accepted HUD visibly opened in the operator's normal browser;
- Orion-started HUD ownership was durably recorded with exact PID/process/executable/creation/bridge identity;
- repeated Start reused the same owned HUD instead of spawning a duplicate;
- owned Stop removed the Orion-owned HUD and returned Hermes/Ollama/HUD to clean-off with launcher state removed;
- a verified pre-existing HUD launched through the installed product HUD helper was reused without ownership transfer;
- Stop Orion preserved that unowned pre-existing HUD;
- the controlled pre-existing fixture was identity-checked and cleaned up;
- final normal Start returned Orion to a healthy running state with an Orion-owned HUD;
- no background supervisor, login persistence, browser-process ownership, Hermes/iai configuration change, or second lifecycle authority was introduced.

The durable acceptance record is:

`docs/evidence/hud-launch-after-health-acceptance-2026-10-29.md`

Acceptance-harness artifacts encountered during qualification—including unreliable `Get-NetTCPConnection` listener enumeration, caller-shell execution-policy blocking, an initially too-short combined Stop observation window, and an unsuitable direct fixture launch—were isolated from product behavior and did not require a source change after the accepted implementation checkpoint.

## Invariants

- No resident Orion supervisor is created.
- No Scheduled Task definitions or login persistence are changed.
- No Hermes or iai configuration is rewritten by these controls.
- The process-local ROCm library selection does not rewrite persistent Ollama configuration or user/machine environment state.
- HUD launch happens only after Hermes/API health; the HUD bridge itself remains a loopback presentation/control client with no Hermes/Ollama/iai lifecycle authority.
- HUD identity is verified before reuse/open. Port ownership alone never grants Orion ownership.
- If Start Orion created the HUD bridge, Stop Orion may terminate only the persisted, still identity-matching HUD process. Pre-existing HUD/Python processes are left alone.
- Browser processes/tabs are never killed or claimed by Orion operator controls.
- Ollama ownership is session-scoped: if Ollama was already healthy before Start Orion, Stop Orion leaves it alone. If Start Orion launched `ollama serve`, Stop Orion may terminate only the recorded, still-matching Ollama process and identity-checked descendants captured from that owned process tree before shutdown.
- Stop Orion never performs a broad process-name kill for `python.exe`, `ollama.exe`, or `llama-server.exe`.
- Pending cleanup identities are durable across failed Stop attempts and block unsafe ownership transfer.
- Success output follows observable component health/HUD/shutdown evidence; a command exit alone is not treated as component health.
- Changes to lifecycle-affecting dependencies or integration invalidate the relevant operator-lifecycle regression evidence and require focused re-verification.
