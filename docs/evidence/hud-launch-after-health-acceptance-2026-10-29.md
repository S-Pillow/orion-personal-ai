# HUD launch-after-health acceptance — 2026-10-29

## Outcome

**PASS / CLOSED**

OR-LIFE-010 HUD launch-after-health integration is accepted on the real Orion Windows workstation.

Accepted implementation checkpoint:

`7465492a7daebb1bf2630f2687668e575177291b`

Merged implementation:

- PR #78 — `Open accepted HUD after Orion runtime health`
- source qualification passed on Windows and Ubuntu;
- final Codex review on the PR head completed with no findings;
- no lifecycle source change was made after the accepted implementation checkpoint during live acceptance.

The earlier ROCm / Ollama ownership lifecycle correction remains accepted separately at its implementation checkpoint `3cbc1fa4831966fefce5f2711d82032965080fb2`. PR #78 extends the one-shot Start/Stop path only with the accepted HUD launch/reuse/ownership behavior and does not reopen that correction.

## Accepted behavior

The live Windows acceptance proved the following behavior on the installed desktop controls:

1. `Start Orion` remains a one-shot launcher and does not become a resident supervisor.
2. Orion-started Ollama uses the accepted process-local `rocm_v7_1` backend behavior.
3. Hermes health is established before the accepted HUD becomes healthy/opened.
4. The installed accepted HUD is the loopback bridge at `http://127.0.0.1:8765/` with the expected `OrionHUD/2A` identity and Orion page title.
5. The HUD visibly opens in the operator's normal browser after runtime health.
6. An Orion-started HUD records durable exact-process ownership in `launcher-session.json`.
7. Re-running `Start Orion` while the Orion-owned HUD is healthy reuses the same bridge process rather than starting a duplicate.
8. `Stop Orion` removes an Orion-owned HUD while preserving the existing Hermes/Ollama ownership and descendant-cleanup guarantees.
9. A verified pre-existing HUD is reused but is not claimed by the launcher.
10. `Stop Orion` leaves that pre-existing unowned HUD running.
11. Browser processes/tabs are never claimed or killed by the lifecycle controls.
12. Final normal Start returns Orion to a healthy running state.

## Source/install evidence

The acceptance run updated local `main` to the accepted implementation checkpoint:

`7465492a7daebb1bf2630f2687668e575177291b`

Installation verification passed:

- installed Start/Stop/HUD-helper files matched source hashes;
- 13 installed HUD static files were verified;
- `Start Orion.lnk` wiring passed;
- `Stop Orion.lnk` wiring passed;
- no background supervisor was installed.

The pre-acceptance HUD listener check found port 8765 clear.

Backup created before installation:

`C:\Users\spill\AppData\Local\Orion\operator-backups\hud-launch-20261029-064508`

## Health-before-HUD proof

The live desktop-shortcut Start run observed:

- Ollama first healthy: `2026-10-29T06:45:32.2690938-04:00`
- Hermes first healthy: `2026-10-29T06:45:46.1890914-04:00`
- HUD first verified healthy: `2026-10-29T06:45:48.4710826-04:00`

Result:

`HEALTH_BEFORE_HUD_LIVE_ORDER=PASS`

The operator separately confirmed that Orion visibly opened in the browser and remained open.

Result:

`VISUAL_BROWSER_CONFIRMATION=PASS`

## Durable owned-HUD proof

A live diagnostic of the first accepted HUD session showed:

- `schemaVersion = 2`
- `ollamaStartedByOrion = True`
- `ollamaLibrary = rocm_v7_1`
- `hudStartedByOrion = True`
- HUD PID `28112`
- HUD process `python.exe`
- executable `C:\Users\spill\AppData\Local\Programs\Python\Python311\python.exe`
- bridge `C:\Users\spill\AppData\Local\Orion\hud\orion_hud_bridge.py`
- exact command line identified the installed bridge on host `127.0.0.1`, port `8765`, Hermes target `http://127.0.0.1:8642`
- exactly one installed Orion HUD bridge process was present;
- no Start/Stop operator PowerShell process was left resident;
- HUD, Hermes, and Ollama loopback endpoints all returned HTTP 200.

The accepted lifecycle run then proved:

`DURABLE_HUD_OWNERSHIP=PASS`

`REPEATED_START_REUSE=PASS`

The repeated Start retained the same owned HUD rather than spawning a second bridge.

## Owned Stop proof

The first acceptance harness used a 60-second combined shutdown wait and timed out before observing full shutdown. A subsequent read-only post-Stop diagnostic showed the actual final state was clean:

- Hermes health: down;
- Ollama health: down;
- HUD health: down;
- `launcher-session.json`: absent.

The following clean-off acceptance step confirmed:

`OWNED_HUD_STOP_CLEANUP=PASS`

`CLEAN_OFF_BASELINE=PASS`

No source change was required; the earlier failure was an acceptance-wait timing issue rather than a lifecycle failure.

## Pre-existing HUD ownership-boundary proof

An initial hand-built fixture proved unsuitable for acceptance because it could remain alive without reaching a usable listener state. That fixture was exact-identity cleaned up and port teardown was confirmed before retrying.

The accepted pre-existing-HUD fixture was then started through the installed product HUD helper itself. It reached verified readiness as PID `10836` without creating `launcher-session.json`.

Result:

`PREEXISTING_HUD_FIXTURE=PASS`

From that controlled state, the final ownership acceptance proved:

- pre-existing HUD baseline verified;
- Start Orion brought up the core runtime while reusing the existing HUD;
- launcher state kept `hudStartedByOrion = false`;
- no duplicate HUD bridge was created;
- Stop Orion shut down the owned core runtime but preserved the pre-existing HUD;
- the exact controlled fixture was then identity-checked and cleaned up;
- a final normal Start created a normal Orion-owned HUD again.

Results:

`PREEXISTING_HUD_BASELINE=PASS`

`PREEXISTING_HUD_NOT_CLAIMED=PASS`

`PREEXISTING_HUD_REUSED=PASS`

`PREEXISTING_HUD_PRESERVED_BY_STOP=PASS`

`CONTROLLED_FIXTURE_CLEANUP=PASS`

## Acceptance-harness findings

Several acceptance-only issues were encountered and resolved without changing product source:

1. A `Get-NetTCPConnection` listener-count assertion returned zero even while the verified HUD endpoint returned HTTP 200 and the exact owned bridge process was alive. Listener enumeration was therefore removed as an acceptance truth source; endpoint identity plus exact process identity remained authoritative.
2. One continuation attempted to dot-source the installed HUD helper from a PowerShell session subject to the machine execution policy. The attempt failed before lifecycle work ran. Installed shortcuts already use process-scoped `-ExecutionPolicy Bypass`; later acceptance did not depend on dot-sourcing in the caller shell.
3. The first owned-Stop harness used a 60-second combined core shutdown wait. Post-failure read-only diagnostics proved Hermes, Ollama, and HUD were all down and session state removed. Later acceptance used a wider observation window.
4. A direct hand-built pre-existing HUD fixture was not used as final evidence. Final fixture qualification used the real installed `Start-OrionHudBridge` helper.

These were test-harness corrections only. They do not change the accepted runtime implementation checkpoint.

## Final accepted state

Final acceptance output:

- `DURABLE_HUD_OWNERSHIP=PASS`
- `REPEATED_START_REUSE=PASS`
- `OWNED_HUD_STOP_CLEANUP=PASS`
- `PREEXISTING_HUD_NOT_CLAIMED=PASS`
- `PREEXISTING_HUD_REUSED=PASS`
- `PREEXISTING_HUD_PRESERVED_BY_STOP=PASS`
- `CONTROLLED_FIXTURE_CLEANUP=PASS`
- `VISUAL_BROWSER_CONFIRMATION=PASS`
- `WINDOWS_HUD_ACCEPTANCE=PASS`
- `ORION_FINAL_STATE=RUNNING`

Final observed process IDs at closure:

- HUD PID `1360`
- Ollama PID `28084`

Process IDs are runtime evidence only and are not durable identity beyond this acceptance session.

## Accepted invariants

- Manual-off remains the lifecycle default.
- Start Orion and Stop Orion remain one-shot operator controls, not supervisors.
- Start establishes Ollama/Hermes health before opening the accepted HUD.
- HUD identity must be verified before reuse/open.
- Orion may stop only a HUD bridge that the current launcher session owns and can identity-match.
- A verified pre-existing HUD is reused without ownership transfer and survives Stop Orion.
- Browser processes/tabs are not lifecycle-owned.
- Existing ROCm 7.1, Ollama ownership, descendant cleanup, iai vendor lifecycle, and no-login-persistence boundaries remain unchanged.
- No Hermes/iai configuration, Scheduled Task, watcher, service, or second lifecycle subsystem was introduced by this outcome.

## Disposition

**OR-LIFE-010 HUD launch-after-health: ACCEPT / CLOSED.**

Do not reopen this integration based on acceptance-harness artifacts alone. Re-verification is appropriate only when a material lifecycle dependency, HUD entry point, process-ownership contract, or accepted runtime behavior changes.
