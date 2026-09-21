# Orion Vault Actions Hermes Plugin

This directory contains the source-controlled native Hermes plugin planned for Orion Phase 5.

## Current status

P5-01 only. The plugin is **not installed or enabled** in the live COMPANION profile by this ticket.

The current implementation exposes:

- `orion_vault_preview_edit` — read-only edit preview;
- `orion_vault_preview_move_draft` — read-only inbox-to-vault move preview;
- `orion_vault_recommend_destination` — read-only iai-backed destination recommendation;
- `orion_vault_apply_plan` — fail-closed placeholder used only to prove Hermes approval interception.

The apply handler always returns `p5_01_mutation_not_authorized`. No protected filesystem mutation is implemented in P5-01.

## Intended runtime location

The accepted COMPANION Hermes home is:

```text
%LOCALAPPDATA%\hermes\profiles\companion
```

If a later owner-approved P5-02 ticket authorizes installation, the intended plugin destination is:

```text
%LOCALAPPDATA%\hermes\profiles\companion\plugins\orion-vault-actions
```

Do not copy or enable this plugin there as part of P5-01.

## Configuration seam

The source defaults to the currently accepted Orion roots:

```text
ORION_VAULT_ROOT=C:\Personal\Me
ORION_INBOX_ROOT=C:\Personal\Orion-Inbox
```

Tests override these values with disposable temporary directories.

## Approval seam

A valid preview is cached in process memory for a bounded interval and identified by an immutable SHA-256 plan token.

A later call to `orion_vault_apply_plan` is intercepted by the plugin's `pre_tool_call` hook:

- missing/unknown/expired token -> `action=block`;
- valid token -> `action=approve`;
- `rule_key` is scoped to the exact plan token.

Hermes, not Orion, owns the human approval decision. The current apply handler still refuses mutation even after approval because P5-01 is source-contract work only.

## Source verification

From the Orion repository root, run:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  "D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions\tests\test_p5_01.py"
```

The suite uses temporary directories only. It must not touch the live vault or inbox.

Current Windows verification evidence (2026-09-21):

- `test_p5_01.py`: 13/13 passed in 0.133 s;
- Hermes `plugins doctor <source-dir> --ci`: PASS;
- runtime discovery, manifest parsing, import, and registration passed;
- doctor observed 4 tools and 1 hook with no warnings;
- COMPANION user-plugin baseline was `[]`, so no pre-existing user plugin was displaced;
- destination recommendation coverage passed for native iai ordering, ambiguous lossy `doc:` tag omission, and fail-closed iai errors.

## iai destination-recommendation seam

The COMPANION profile already has `iai-mcp` enabled. Phase 5 destination recommendation should therefore call the existing native iai recall/search authority rather than recreate the historical Docker recommender or add an Orion-side semantic ranker.

The implemented P5-01 recommendation behavior is read-only against the Orion inbox/vault:

- call `iai-mcp.memory_recall` for native semantic ordering;
- call `iai-mcp.memory_temporal_recall` only for the recalled records' document tags;
- compute iai-compatible `doc:` tags for current contained Markdown files in the vault;
- accept a source only when one document tag maps to exactly one current file;
- preserve native recall order and deduplicate only by destination directory;
- omit ambiguous/missing mappings rather than guessing;
- never mutate the draft or vault.

The source deliberately does not open the iai store directly.

A future live install must explicitly grant this plugin access only to the configured iai server:

```yaml
plugins:
  entries:
    orion-vault-actions:
      mcp_allowlist: ["iai-mcp"]
```

P5-01 does **not** apply that live configuration.

## Future P5-02 installation gate

A later installation ticket must, at minimum:

1. verify the source commit and changed-path set;
2. confirm the COMPANION user-plugin baseline immediately before install;
3. install only from the approved repository commit into the exact COMPANION plugin directory;
4. validate Hermes plugin discovery before enablement;
5. enable the plugin only after source/tests pass;
6. restart Hermes only through the accepted Orion lifecycle path;
7. prove preview-only behavior before authorizing any mutation implementation;
8. record rollback instructions and evidence.

Rollback for an installed version must disable the plugin first, return Hermes to the prior accepted configuration, and remove only the explicitly installed Orion plugin artifact under a separately authorized mutation step.
