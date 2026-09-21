# Orion Vault Actions Hermes Plugin

This directory contains the source-controlled native Hermes plugin planned for Orion Phase 5.

## Current status

P5-01 only. The plugin is **not installed or enabled** in the live COMPANION profile by this ticket.

The current implementation exposes:

- `orion_vault_preview_edit` — read-only edit preview;
- `orion_vault_preview_move_draft` — read-only inbox-to-vault move preview;
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
