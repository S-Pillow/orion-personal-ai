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

## Gate H1 — rollback capture

H1 is intentionally deferred until H0 output identifies the live config filename(s) and current plugin inventory.

Before any copy/config mutation, H1 must capture:

- exact source commit;
- existing plugin destination state;
- relevant COMPANION config file(s);
- gateway state;
- backup directory path;
- file hashes for every config/plugin artifact that will be changed.

No secret values should be printed into evidence.

## Gate H2 — preview-only install

After H1 is accepted:

- copy only the approved `orion-vault-actions` source directory to the exact COMPANION plugin destination;
- configure only the required plugin entry / `mcp_allowlist: ["iai-mcp"]` seam;
- set or preserve production mutation mode as `disabled` or `preview_only`;
- do not configure `ORION_P5_PRODUCTION_RECOVERY_ROOT`;
- do not register the private production executor.

## Gate H3 — lifecycle/load

Use only the accepted manual-off Hermes lifecycle.

Do not enable login startup.

Any gateway stop/start needed solely to load the plugin is covered by this install authorization, but must happen only after rollback artifacts exist.

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
