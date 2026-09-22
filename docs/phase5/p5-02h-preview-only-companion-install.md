# P5-02H Preview-Only COMPANION Installation

Status: **OWNER AUTHORIZED / BASELINE CAPTURE FIRST / NO MUTATION ENABLEMENT**
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
