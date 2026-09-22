# P5-02H Preview-Only COMPANION Installation

Status: **PASS / PREVIEW-ONLY COMPANION INSTALL ACCEPTED / MUTATION STILL PROHIBITED**
Date: 2026-09-22
Authorized source commit: `b8cbb63c3db20c38543220956d3f776bffecf432`
Source branch: `feature/orion-phase5-p5-02g-production-guardrails`

## Authorization boundary

The owner explicitly authorized the preview-only COMPANION installation gate.

This authorization covers only:

- baseline/rollback capture;
- installing the exact approved `orion-vault-actions` plugin source into the COMPANION user-plugin location;
- the narrow plugin configuration required for preview/recommendation behavior, including the existing iai MCP allowlist seam;
- setting/confirming production mutation mode as disabled or preview-only;
- the minimum Hermes lifecycle action needed to load the installed plugin;
- read-only / no-write smoke verification;
- rollback if the install gate fails.

This authorization does **not** cover:

- `mutation_enabled`;
- registering the private production executor;
- creating a production recovery root;
- changing Windows ACLs;
- editing/moving/restoring/deleting any real vault or inbox file;
- upgrading Hermes/SQLite/Ollama/iai;
- merging branches/PRs.

## Pinned source

Install only this exact source commit:

```text
b8cbb63c3db20c38543220956d3f776bffecf432
```

Expected source plugin directory:

```text
D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions
```

Expected COMPANION profile:

```text
%LOCALAPPDATA%\hermes\profiles\companion
```

Expected plugin destination:

```text
%LOCALAPPDATA%\hermes\profiles\companion\plugins\orion-vault-actions
```

## Accepted source evidence before install

- P5 source tests: 116/116 PASS;
- installed-Hermes dispatcher probe: 2/2 PASS;
- source plugin doctor: PASS;
- expected registered surface: 4 tools / 2 hooks;
- `orion_vault_apply_plan` still maps to `apply_plan_placeholder`;
- private production executor is unregistered.

## Gate H0 — read-only baseline capture

Run this before changing any live profile file:

```powershell
$Hermes = "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
$Repo = "D:\Orion\orion-personal-ai"
$Profile = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$PluginRoot = Join-Path $Profile "plugins"
$PluginDest = Join-Path $PluginRoot "orion-vault-actions"

git -C $Repo status --short
git -C $Repo rev-parse --short HEAD

Write-Host "PROFILE=$Profile"
Write-Host "PLUGIN_ROOT_EXISTS=$(Test-Path -LiteralPath $PluginRoot)"
Write-Host "PLUGIN_DEST_EXISTS=$(Test-Path -LiteralPath $PluginDest)"

if (Test-Path -LiteralPath $PluginRoot) {
  Get-ChildItem -LiteralPath $PluginRoot -Force |
    Select-Object Name, Mode, Length, LastWriteTime
}

Get-ChildItem -LiteralPath $Profile -Force |
  Select-Object Name, Mode, Length, LastWriteTime

Get-ChildItem -LiteralPath $Profile -File -Force |
  Where-Object { $_.Extension -in ".yaml", ".yml", ".json", ".toml" } |
  Select-Object FullName, Length, LastWriteTime

& $Hermes -p companion gateway status
& $Hermes -p companion plugins --help
```

Expected repository head:

```text
b8cbb63
```

Do not continue to installation if:

- repository status is unexpectedly dirty;
- HEAD is not the approved commit;
- `PluginDest` already exists unexpectedly;
- an existing plugin/config state would be overwritten without a backup plan;
- COMPANION profile/config files are not where expected;
- the Hermes CLI surface differs materially from the accepted runtime.

Report the H0 output before H1 so exact backup/config commands can be tailored to the observed profile.

## H0 observed baseline — PASS

Operator H0 evidence on 2026-09-22:

- repository working tree: clean;
- repository HEAD: `cb602e3` (approved P5-02G source);
- COMPANION profile: `C:\Users\spill\AppData\Local\hermes\profiles\companion`;
- plugin root exists;
- plugin root inventory: empty;
- `orion-vault-actions` destination does not exist;
- live profile config: `config.yaml`, 3828 bytes, last modified 2026-09-12 20:14:13 local;
- managed task `Hermes_Gateway_companion`: registered / Ready;
- no gateway process detected;
- Hermes plugin CLI exposes install/search/update/remove/list/enable/disable/capabilities/doctor/pack/show.

H0 is accepted. No live profile file was changed and no gateway process was started.

Before H1/H2, perform one additional read-only CLI/config-shape check so installation uses Hermes-native plugin management where supported and the config backup/edit is targeted rather than guessed.

## H0.5 plugin/config shape — PASS

Additional operator evidence:

- `hermes plugins list` reports plugins are opt-in and supports compact user-plugin listing;
- install supports immutable `--ref COMMIT_SHA`, but the CLI exposes no repository-subdirectory selector;
- enable supports `--no-allow-tool-override`;
- `plugins show <name>` is available;
- the current live `config.yaml` contains no `plugins:` block;
- the observed config SHA-256 begins `13C7CBA5...` (full value will be captured locally in H1 metadata).

Because `orion-vault-actions` is a subdirectory of the Orion monorepo, P5-02H will not use the Git-repository installer against the monorepo root. The authorized install method is a rollback-backed copy of only the pinned source plugin directory into the COMPANION user-plugin directory, followed by Hermes-native doctor/show/enable operations.

The first mutating step will still keep the plugin disabled while installed-location doctor/show/capability checks run.

## Gate H1 — rollback capture

H1 now has a concrete rollback target:

- live config: `%LOCALAPPDATA%\hermes\profiles\companion\config.yaml`;
- plugin destination absent before install;
- gateway already stopped.

Create a timestamped backup below the existing COMPANION `orion\backups` directory. Record the full config SHA-256, source pin, plugin inventory, and gateway status without copying or printing `.env` contents.

Before any install mutation, fail closed if either `ORION_P5_MUTATION_MODE` or `ORION_P5_PRODUCTION_RECOVERY_ROOT` is already set in the current process or declared in the profile `.env`. For this preview-only gate the desired state is to leave both absent, which makes source mutation mode default to `disabled`.

## H2 first staging attempt — SAFE FAILURE

Observed operator result:

- rollback backup created at `C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\backups\p5-02h-preview-20260922-014521`;
- captured live config SHA-256: `13C7CBA513A260659A2859A6F60289483C657DDBC0686E9E1EB2EEBF156A504D`;
- temporary worktree creation failed because the local Git object database had not fetched pinned commit `b8cbb63c3db20c38543220956d3f776bffecf432`;
- cleanup left `PLUGIN_STAGED=False`;
- installed-location doctor correctly reported plugin path not found;
- compact user-plugin list remained empty;
- `plugins show orion-vault-actions` reported not found;
- managed gateway remained stopped.

No COMPANION config change, plugin enablement, or vault/inbox mutation occurred.

The standalone `finally` parse error was an interactive PowerShell statement-boundary issue after the failed `try/catch`; there was no staging directory to remove and no live-state consequence.

Remediation: fetch the exact branch/commit first, verify the 40-character SHA resolves, then perform staging with cleanup expressed without a detached interactive `finally` block.

## Gate H2 — install exact pinned plugin while disabled

Do not use `hermes plugins install` against the Orion monorepo because the accepted plugin is a repository subdirectory and the observed installer exposes no subdirectory selector.

Create a temporary detached Git worktree at the exact approved commit:

```text
b8cbb63c3db20c38543220956d3f776bffecf432
```

Copy only:

```text
hermes_plugins\orion-vault-actions
```

into:

```text
%LOCALAPPDATA%\hermes\profiles\companion\plugins\orion-vault-actions
```

Then, before enablement:

- run installed-location plugin doctor;
- run compact user-plugin list;
- run `plugins show orion-vault-actions`;
- run `plugins capabilities orion-vault-actions`;
- confirm the gateway remains stopped.

Any mismatch stops the gate and rolls back the copied plugin directory.

## H2 observed result — PASS

Operator H2 evidence:

- exact pin resolved: `b8cbb63c3db20c38543220956d3f776bffecf432`;
- detached staging worktree HEAD matched the exact approved pin;
- plugin staged successfully at the COMPANION user-plugin destination;
- installed-location plugin doctor: PASS;
- installed-location registrations: **4 tools / 2 hooks**;
- compact user-plugin list: `orion-vault-actions` 0.1.0, user source, **not enabled**;
- `plugins show`: status **not enabled**, source user;
- live `config.yaml` SHA-256 remained exactly `13C7CBA513A260659A2859A6F60289483C657DDBC0686E9E1EB2EEBF156A504D`;
- managed gateway remained stopped.

H2 is accepted. No plugin enablement, config mutation, gateway start, production recovery-root creation, or vault/inbox mutation occurred.

## Gate H3 — enable with gateway still stopped

If H2 passes, enable through Hermes with:

```text
--no-allow-tool-override
```

Do not start the gateway yet.

After enablement, inspect only the resulting `plugins:` section of `config.yaml` plus `plugins show` / `plugins capabilities`.

This observation determines the exact live plugin-entry schema before adding the `mcp_allowlist: ["iai-mcp"]` seam. Do not guess or hand-edit that structure before Hermes has written its native enablement shape.

A second config SHA-256 is captured after enablement.

## H3 observed result — PASS

Operator H3 evidence:

- Hermes enable succeeded with `--no-allow-tool-override`;
- plugin status: **enabled**;
- source: user;
- declared capabilities: none;
- live config SHA-256 after Hermes-native enable: `1104B781D7CAF7F2B9B88616ACB13901DFB7ECE4E912BA588D6A3238AC2BA83A`;
- Hermes wrote the native plugin config shape:

```yaml
plugins:
  enabled:
    - orion-vault-actions
  disabled: []
  entries:
    orion-vault-actions:
      allow_tool_override: false
```

- gateway remained stopped / no process detected.

H3 is accepted. No plugin code executed inside a live gateway session yet.

## Gate H3.5 — MCP allowlist config

Only after H3 reveals Hermes's native plugin-entry shape may the existing source-documented iai seam be added:

```yaml
mcp_allowlist: ["iai-mcp"]
```

No other plugin capability is authorized.

## H3.5 observed result — PASS

Operator H3.5 evidence:

- mutation-related Phase 5 environment settings remained absent;
- exact manual config edit succeeded with `MCP_ALLOWLIST_ADDED=true`;
- live config SHA-256 after allowlist edit: `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- plugin remains enabled as a user plugin;
- declared capabilities remain none;
- installed-location doctor remains PASS at **4 tools / 2 hooks**;
- live plugin config is now:

```yaml
plugins:
  enabled:
    - orion-vault-actions
  disabled: []
  entries:
    orion-vault-actions:
      allow_tool_override: false
      mcp_allowlist: ["iai-mcp"]
```

- managed gateway remained stopped / no process detected.

H3.5 is accepted. The next step is the first lifecycle/load gate. No real vault/inbox mutation has occurred.

## H4 first lifecycle attempt — SAFE FAILURE

Observed operator result:

- the old unversioned launcher path `%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1` is absent;
- installed plugin doctor still passed at **4 tools / 2 hooks**;
- live config SHA-256 remained `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- plugin remained enabled;
- gateway remained stopped / no process detected;
- health endpoint remained unreachable, as expected because Start never occurred.

Accepted Phase 1 transition evidence identifies the current lifecycle publication at:

```text
%LOCALAPPDATA%\Orion\operator\versions\2.7.4-candidate1
```

and records that the installed desktop shortcuts target that versioned publication.

Disposition: procedural path mismatch only; no runtime/plugin failure and no vault/inbox mutation.

Before retrying H4, read the actual `Start Orion.lnk` target, arguments, and working directory and confirm the versioned publication files exist. Do not reinstall operator controls.

## H4 launcher resolution — PASS

Read-only operator inspection confirmed:

- versioned publication exists at `C:\Users\spill\AppData\Local\Orion\operator\versions\2.7.4-candidate1`;
- `Start-Orion.ps1` is present;
- desktop shortcut target is `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`;
- desktop shortcut arguments are exactly:

```text
-NoProfile -ExecutionPolicy Bypass -File "C:\Users\spill\AppData\Local\Orion\operator\versions\2.7.4-candidate1\Start-Orion.ps1"
```

- shortcut working directory is the same versioned publication directory.

Therefore the corrected H4 retry must mirror this exact installed invocation contract. No operator reinstall or lifecycle-script modification is required.

## H4 second lifecycle attempt — SAFE FAILURE

Observed operator result:

- exact versioned Start shortcut invocation was mirrored;
- installed `Start-Orion.ps1` failed during parameter binding before any runtime start;
- failure:
  `Join-Path : Cannot bind argument to parameter 'Path' because it is an empty string.`
- failing expression is the wrapper's default `ConfigPath` construction using `$PSScriptRoot`;
- Start returned exit code 1;
- Hermes health remained unavailable;
- gateway remained stopped;
- Orion plugin remained enabled;
- installed plugin doctor remained PASS at **4 tools / 2 hooks**;
- live config SHA-256 remained exactly `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`.

Disposition: safe invocation-contract failure before lifecycle start. Do not patch/reinstall the accepted operator package. Read the installed `Start-Orion.ps1` and `Invoke-Orion.ps1` parameter/forwarding contract, then retry only with an invocation directly supported by those installed scripts.

## H4 launcher contract correction

The installed `Start-Orion.ps1` wrapper accepts an explicit `-ConfigPath` and forwards it unchanged to `Invoke-Orion.ps1 -Action start`:

```powershell
[CmdletBinding()]
param([string]$ConfigPath = (Join-Path $PSScriptRoot 'orion-config.json'))
& (Join-Path $PSScriptRoot 'Invoke-Orion.ps1') -Action start -ConfigPath $ConfigPath
exit $LASTEXITCODE
```

`Invoke-Orion.ps1` likewise accepts `-ConfigPath` and resolves the configured Hermes Python before invoking `orion.py start --config <resolved>`.

The earlier failure came from the default parameter expression evaluating `Join-Path $PSScriptRoot ...` before `$PSScriptRoot` was usable in that invocation context. No source/runtime patch is needed. The H4 retry must pass the installed `orion-config.json` explicitly.

## H4 third lifecycle attempt — SAFE FAILURE / ACCEPTED LIFECYCLE DRIFT IDENTIFIED

Observed operator result:

- versioned v2.7.4 launcher was invoked with explicit installed `orion-config.json`;
- launcher refused before runtime start with `HERMES_CHECKOUT_NOT_CLEAN`;
- Hermes health remained unavailable;
- gateway remained stopped;
- Orion plugin remained enabled;
- installed plugin doctor remained PASS at **4 tools / 2 hooks**;
- live config SHA-256 remained exactly `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`.

Repository evidence explains a likely accepted incompatibility:

- Phase 1 v2.7.4 lifecycle package enforces a clean Hermes checkout at pinned commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- accepted P4-04A later applies a bounded source patch to that pinned Hermes checkout at `gateway/platforms/api_server.py`;
- P4-04A leaves deterministic sidecars `api_server.py.orion-p4-04a.bak` and `api_server.py.orion-p4-04a.json`;
- P4-04A runtime acceptance explicitly records a successful normal restart through repository `scripts/operator/Start-Orion.ps1` after the patch was applied.

Therefore do not reset/clean/stash/rollback Hermes merely to satisfy the older v2.7.4 clean-checkout invariant. First classify the current Hermes checkout read-only and verify that any dirtiness is exactly the accepted P4-04A patch state.

## H4 Hermes checkout classification — ACCEPTED P4-04A STATE

Read-only operator classification after `HERMES_CHECKOUT_NOT_CLEAN` showed:

- Hermes HEAD: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- tracked changes: only `gateway/platforms/api_server.py`;
- tracked diff stat: 242 insertions / 1 deletion;
- untracked files: only:
  - `gateway/platforms/api_server.py.orion-p4-04a.bak`
  - `gateway/platforms/api_server.py.orion-p4-04a.json`;
- patched target SHA-256: `ECFD6DD53610C24A81F078650A0B2B3E129478A50FDB5F353313FFF6E12E3888`;
- backup SHA-256: `8D87036DD488CB811DBABB7048102D0C28FBF54E0E658C464683000118537EC3`;
- manifest patch id: `ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1`;
- manifest accepted Hermes commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- manifest pre Git blob: `980659c9343d2975040f304e05bf97fa95f6a046`;
- manifest pre/post SHA-256 values exactly match the accepted P4-04A evidence.

The PowerShell verification wrapper itself did not run because local PowerShell execution policy blocks script execution. This is not a patch-state mismatch. Perform the same read-only verification by invoking the source-controlled Python patcher directly with the accepted Hermes Python.

Disposition: the Hermes checkout dirtiness is fully accounted for by the accepted P4-04A compatibility patch. **Do not clean/reset/stash/rollback this checkout.**

## H4 P4-04A verification — PASS

Operator ran the underlying source-controlled Python verifier directly because local PowerShell execution policy blocked the wrapper.

Observed:

```text
P4-04A VERIFY PASS
Target=C:\Users\spill\AppData\Local\hermes\hermes-agent\gateway\platforms\api_server.py
Sha256=ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888
```

This closes the checkout-classification question: the dirty Hermes checkout is the accepted P4-04A runtime state, not unexpected drift.

Repository cross-check also confirmed that `scripts/operator/Start-Orion.ps1` at local Orion HEAD `cb602e3` is byte-identical to the current P5-02G branch copy. This is the same repo operator lifecycle path referenced by P4-04A runtime acceptance after the compatibility patch was installed.

H4 should therefore use the repository operator Start script rather than the stale versioned v2.7.4 wrapper that enforces a clean Hermes checkout.

## H4.5 installed-runtime no-write smoke — PASS

The first H4.5A attempt exposed two PowerShell response-shape issues in the operator probe, not runtime failures:

1. pinned Hermes `GET /v1/toolsets` returns a wrapper object with rows under `.data`;
2. after filtering to exactly one matching `PSCustomObject`, PowerShell unwraps the single pipeline result to a scalar, so using `$OrionToolset.Count -ne 1` was not a reliable cardinality assertion.

The corrected read-only query produced the actual live runtime object:

- toolset name: `orion_vault`;
- `enabled: True`;
- `configured: True`;
- resolved tools:
  - `orion_vault_apply_plan`
  - `orion_vault_preview_edit`
  - `orion_vault_preview_move_draft`
  - `orion_vault_recommend_destination`;
- live tool count: 4;
- gateway health after toolset inspection: HTTP 200.

The separately executed H4.5B installed registration probe also passed:

- 4 registered tools;
- 2 registered hooks;
- registered apply handler is exactly `apply_plan_placeholder`;
- unknown plan token returns `p5_01_mutation_not_authorized`;
- `plan_known=false`;
- `mutation_performed=false`;
- gateway remained healthy with HTTP 200.

H4.5 is accepted. This proves the running COMPANION gateway exposes the enabled Orion vault toolset while the installed registered apply surface remains fail-closed and no protected filesystem mutation occurs.


Observed:

- H4.5A authenticated `GET /v1/toolsets` request itself succeeded, but the operator probe incorrectly treated the response as a bare array;
- pinned Hermes returns a wrapper object with `object`, `platform`, and `data`; toolset rows live under `data`;
- therefore the H4.5A Orion-toolset assertion is invalid and must be rerun against `$Toolsets.data`;
- any subsequent `LIVE_ORION_TOOLSET_FOUND=true` / tool-count lines from that failed block are not acceptance evidence because PowerShell execution continued after the thrown assertion;
- H4.5B installed registration probe **PASS**:
  - 4 registered tools;
  - 2 registered hooks;
  - registered apply handler is `apply_plan_placeholder`;
  - unknown plan token returns `p5_01_mutation_not_authorized`;
  - `plan_known=false`;
  - `mutation_performed=false`;
- gateway remained healthy after the probe with HTTP 200.

Disposition: H4.5 is not closed until the corrected read-only live-toolset query confirms whether `orion_vault` is present and enabled for the `api_server` platform.

## H4 observed result — PASS

Operator H4 evidence:

- repository operator `scripts/operator/Start-Orion.ps1` started Orion successfully;
- output included `ORION READY`;
- Hermes API health returned HTTP 200;
- gateway process detected running (PID 14616);
- `orion-vault-actions` remained enabled as a user plugin;
- installed-location plugin doctor remained PASS at **4 tools / 2 hooks**;
- live COMPANION config SHA-256 remained exactly `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- P4-04A compatibility patch remained verified and intact;
- no production recovery root was created and no real vault/inbox mutation was intentionally performed by the lifecycle step.

H4 lifecycle/load is accepted.

## Gate H4 — lifecycle/load

Use the accepted installed one-shot Orion operator lifecycle:

```text
%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1
```

The accepted source behavior:

- ensures Ollama is available;
- starts Hermes profile `companion` using `hermes -p companion gateway start`;
- waits for `http://127.0.0.1:8642/health`;
- records Orion launcher ownership for Ollama;
- exits after the gateway is ready;
- does not change Scheduled Task definitions or login startup;
- leaves iai under Hermes/iai demand-wake ownership.

Before starting:

- require live config SHA-256 `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- require `ORION_P5_MUTATION_MODE` absent from process/profile env;
- require `ORION_P5_PRODUCTION_RECOVERY_ROOT` absent from process/profile env;
- require installed plugin doctor PASS at 4 tools / 2 hooks;
- require gateway currently stopped.

H4 lifecycle PASS criteria:

- Start Orion exits successfully;
- Hermes health endpoint returns HTTP 200;
- `hermes -p companion gateway status` reports a running gateway process;
- Orion plugin remains enabled;
- installed-location doctor remains 4 tools / 2 hooks;
- live config SHA-256 remains unchanged from the H3.5 value;
- no production recovery root appears;
- no real vault/inbox content is intentionally mutated by this lifecycle step.

Do not perform an apply-tool invocation in the lifecycle/load sub-step. First establish that the enabled plugin loads into the accepted runtime without destabilizing the gateway. The no-write registered-tool smoke follows as a separate H4.5 step.

Do not enable login startup.


Use only the accepted manual-off Hermes lifecycle.

Do not enable login startup.

Any gateway start needed solely to load the preview-only plugin is covered by this install authorization, but must happen only after rollback artifacts exist and H3/H3.5 configuration is accepted.

## Gate H4 — no-write acceptance

Required installed-runtime checks:

- plugin doctor/discovery succeeds from the installed location;
- registered surface remains 4 tools / 2 hooks;
- preview edit is side-effect-free;
- preview move is side-effect-free;
- destination recommendation remains read-only;
- apply returns `p5_01_mutation_not_authorized`;
- mutation mode is disabled/preview-only;
- no production recovery root is created;
- no real vault/inbox content changes;
- no unexpected extra approval/mutation path appears.

## Post-H4.5 manual-off restoration — PASS

Operator shutdown through the accepted repository Stop Orion path completed successfully:

- Hermes gateway drained and stopped cleanly;
- `hermes -p companion gateway status` reports no gateway process;
- `http://127.0.0.1:8642/health` is unreachable;
- COMPANION config SHA-256 remains exactly `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- `orion-vault-actions` remains enabled;
- installed-location doctor remains PASS at **4 tools / 2 hooks**;
- operator marker `P5_02H_MANUAL_OFF_RESTORED=true` was emitted.

Stop Orion also reported `Ollama: stopping Orion-owned server PID 42040`. This is compatible with the repository launcher ownership model when a prior launcher session already owns the recorded Ollama PID; it is recorded as observed lifecycle behavior rather than inferred from the H4 “already available” line.

The preview-only install remains in place while runtime is returned to manual-off.

One acceptance item remains before closing P5-02H: exercise installed preview-edit, preview-move, and destination-recommendation handlers against disposable temporary roots and verify byte-for-byte fixture stability plus known-plan apply refusal. No live vault/inbox paths may be used.

## Final disposable-root no-write acceptance — PASS

Operator final probe against the **installed** plugin completed successfully with Hermes stopped and only temporary disposable roots in use.

Observed:

- `PRODUCTION_MUTATION_MODE=disabled`;
- preview edit succeeded with `mutation_performed=false`;
- preview move succeeded with `mutation_performed=false`;
- destination recommendation succeeded with `mutation_performed=false`;
- deterministic fixture recommendation count: 1;
- recommended target: `Projects/draft.md`;
- known-plan apply returned `p5_01_mutation_not_authorized`;
- known-plan apply reported `plan_known=true`;
- known-plan apply reported `mutation_performed=false`;
- fixture file hashes were unchanged before/after;
- preview move created no target file;
- only disposable roots were used;
- final marker: `P5_02H_FINAL_NO_WRITE_PROBE=PASS`.

### P5-02H disposition

**PASS / PREVIEW-ONLY COMPANION INSTALL ACCEPTED**

Accepted installed state:

- user plugin `orion-vault-actions` installed and enabled;
- `allow_tool_override: false`;
- `mcp_allowlist: ["iai-mcp"]`;
- live config SHA-256: `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- installed plugin doctor: **4 tools / 2 hooks**;
- live gateway exposure verified for enabled/configured `orion_vault` toolset with all 4 expected tools;
- registered apply surface remains `apply_plan_placeholder` and fail-closed;
- mutation mode remains disabled;
- no production recovery root was created;
- no real vault/inbox mutation occurred;
- runtime returned to accepted manual-off state after smoke.

This acceptance does **not** authorize disposable mutation mode, production mutation mode, production recovery-root creation/configuration, or any real vault/inbox edit/move/restore/delete.

The next mutation step is a separate installed-runtime disposable-mutation qualification gate and requires explicit owner authorization.


## Lifecycle follow-up — dedicated Ollama shutdown policy

Owner clarified after P5-02H acceptance that Ollama is dedicated to Orion and is not used by other applications. Desired future lifecycle policy:

- Start Orion should ensure/start Ollama and start Hermes/COMPANION.
- Stop Orion should stop Hermes/COMPANION and then stop the local Ollama runtime, rather than preserving an already-running Ollama solely because the current launcher session did not originally start it.
- iai remains under the existing vendor-managed idle/HIBERNATION lifecycle.
- Manual-off login behavior remains unchanged.

This is a separate lifecycle follow-up. It was not implemented as part of P5-02H and does not change the accepted preview-only plugin result.

## Gate H5 — rollback

Rollback triggers include:

- plugin discovery/registration mismatch;
- config parse failure;
- gateway fails to return to accepted state;
- apply does not fail closed;
- unexpected write/mutation;
- unexpected plugin/config conflict.

Rollback must:

1. stop the gateway if required to safely restore profile files;
2. restore backed-up COMPANION config exactly;
3. restore/remove only the Orion plugin destination introduced by this gate;
4. preserve unrelated plugins/config;
5. restart only if required to restore the prior accepted runtime state;
6. re-run status/doctor;
7. record final state.

No recovery data exists or should be removed in this preview-only gate.

## Stop point after preview-only PASS

A preview-only PASS does not authorize mutation activation.

The next gate is installed-runtime **disposable mutation qualification**, under a separate explicit authorization, using disposable roots and a deliberately enabled mutation mode. Real-vault mutation remains later.
