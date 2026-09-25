# Orion Vault Actions Hermes Plugin

This directory contains Orion's native Hermes vault-actions plugin source.

## Current accepted state

Phase 5 source qualification is accepted through P5-02N, installed/runtime qualification through P5-02O, and the first bounded production canary edit through P5-02Q.

The plugin is installed and enabled under the COMPANION profile with access limited to the configured `iai-mcp` server. The live runtime has loaded the expected four-tool `orion_vault` toolset.

Production mutation remains disabled:

- `ORION_P5_PRODUCTION_RECOVERY_ROOT` is persisted and runtime-qualified;
- `ORION_P5_MUTATION_MODE` is not persisted and resolves to `disabled`;
- registered `orion_vault_apply_plan` points to `apply_plan_production_guarded`;
- disabled `pre_tool_call` blocks without creating an approval rule;
- disabled public apply returns `production_mutation_not_enabled` without entering the private production executor;
- `_execute_production_plan_candidate()` remains private and unregistered;
- production recovery inventory contains exactly one valid committed P5-02Q record with zero attention state;
- one real production `edit_note` has been accepted against the controlled Phase 5 canary only;
- the canary is now in the frozen after-state with SHA-256 `86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19`;
- mutation mode returned to disabled after the bounded action.

Accepted installed source:

```text
faf8b4787d8e6fb668eb5e9d754104910b4b401a
```

Accepted installed plugin version:

```text
0.2.0
```

P5-02O rollback capture:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\backups\p5-02o-installed-disabled-20260923-040536
```

## P5-02N accepted source

The repository source on `feature/orion-phase5-p5-02n-registered-wrapper` implements and has qualified the P5-02M frozen guarded registration design. Qualified code head: `faf8b4787d8e6fb668eb5e9d754104910b4b401a`. P5-02O subsequently installed and runtime-qualified these exact plugin bytes while mutation remained disabled.

Accepted source behavior:

- manifest version is `0.2.0`;
- registered source handler for `orion_vault_apply_plan` is `apply_plan_production_guarded`;
- the public apply schema exposes only `plan_token` and rejects additional properties;
- missing/blank, `disabled`, and `preview_only` modes refuse as `production_mutation_not_enabled` before any approval request or production-executor call;
- unknown modes refuse as `invalid_production_mutation_mode`;
- only explicit `mutation_enabled` may delegate to the private `_execute_production_plan_candidate()`;
- `pre_tool_call` blocks apply in every non-enabled/invalid mode and returns no approval directive for a valid plan only when mutation mode is explicitly enabled;
- the private executor remains unregistered and continues to own the single fresh Hermes human `ALLOW ONCE` gate and all qualified recovery/staleness safeguards.

P5-02N passed 129/129 Phase 5 tests, Hermes approval 3/3, Hermes dispatcher 2/2, HUD Python 78/78, HUD approval rendering 3/3, and compile checks on the accepted Windows environment. No P5-02N source change installs the plugin, changes COMPANION configuration, starts Hermes, persists/enables mutation mode, or touches production vault/inbox/recovery content. Installed-runtime qualification remains a separate P5-02O authorization unit.

## Registered live surface

- `orion_vault_preview_edit`: read-only edit preview;
- `orion_vault_preview_move_draft`: read-only inbox-to-vault move preview;
- `orion_vault_recommend_destination`: read-only iai-backed destination recommendation;
- `orion_vault_apply_plan`: guarded registered production wrapper, fail-closed unless explicit `mutation_enabled` is present;
- `pre_tool_call`: plan validation plus disabled/preview-only/invalid mode blocking before approval;
- `post_approval_response`: fresh human-once observer used by the qualified private production executor when a later separately authorized mutation gate enables execution.

Hermes doctor accepted the manifest with four tools and two hooks.

## Qualified private source behavior

The source contains private, unregistered candidates for:

- disposable edit and move execution;
- disposable historical edit and move-source restore;
- production-shaped edit, move, and restore execution;
- Windows file-ID and held-handle protection;
- schema-v2 production recovery records and non-authorizing receipts;
- bounded startup recovery inventory;
- fresh handler-owned Hermes `ALLOW ONCE` approval;
- post-approval stale-state refusal;
- replay refusal and restart-safe recovery classification.

These candidates being source-qualified does not register them and does not grant live mutation authority.

## Accepted P5-02I installed-runtime evidence

The installed plugin was qualified against explicit disposable roots only:

- DENY produced no mutation;
- fresh human `ALLOW ONCE` permitted one exact disposable edit or move;
- stale state, mismatched evidence, target races, and replay were refused;
- receipts survived in-memory reset but remained non-authorizing;
- historical restore required a new plan, approval, and recovery transaction;
- pre-mutation and post-mutation failures classified as `prepared_no_effect` and `applied_unfinalized`;
- public apply remained fail-closed throughout;
- real vault and inbox were not touched.

See `docs/phase5/p5-02i-installed-disposable-mutation-qualification.md`.

## Production recovery state

The accepted recovery root is:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery
```

P5-02J accepted its location and ACL. P5-02K persisted the exact path in COMPANION `.env` without persisting mutation mode. P5-02L proved the live runtime ingests it while mutation remains disabled. The inventory remained empty through P5-02P. P5-02Q then created exactly one valid committed production recovery record for the accepted canary edit: `33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f`.

## Configuration contract

Accepted data roots:

```text
ORION_VAULT_ROOT=C:\Personal\Me
ORION_INBOX_ROOT=C:\Personal\Orion-Inbox
ORION_P5_PRODUCTION_RECOVERY_ROOT=C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery
```

Production mutation mode:

```text
ORION_P5_MUTATION_MODE=disabled | preview_only | mutation_enabled
```

Missing or blank mode resolves to `disabled`. Unknown values fail closed. `mutation_enabled` makes mutation only eligible; all root, recovery, plan, approval, stale-state, receipt, and postcondition guards still apply.

The browser/HUD has no path that can widen this mode.

## iai destination recommendation

Destination recommendation remains advisory and read-only:

- use native `iai-mcp.memory_recall` ordering;
- use `memory_temporal_recall` only to recover document tags;
- map a document tag only when it resolves to exactly one current contained Markdown file;
- omit missing or ambiguous mappings;
- add no Orion semantic reranking or second memory store;
- perform no vault/inbox mutation.

COMPANION configuration grants only:

```yaml
plugins:
  entries:
    orion-vault-actions:
      mcp_allowlist: ["iai-mcp"]
```

## P5-02M registration design freeze

P5-02M does not change plugin code or the installed runtime. It freezes the required shape of a later registered production apply wrapper:

1. The manifest and schema continue exposing only `plan_token` for apply.
2. The registered handler accepts ordinary Hermes handler arguments only. Test callbacks, root probes, approval functions, and failure hooks are never tool arguments.
3. Missing, invalid, disabled, or preview-only production mode refuses without calling a production executor.
4. Unknown, expired, malformed, or consumed plans fail before human approval.
5. In `mutation_enabled` mode, `pre_tool_call` validates the plan but does not own approval.
6. The final handler requests exactly one fresh Hermes generic approval and accepts only a matching human `choice=once` observer event plus `approved=true`.
7. Session, always, yolo, cached, cron, single-query, missing, late, denied, timed-out, or mismatched approval cannot authorize mutation.
8. The handler revalidates plan state and recovery inventory after approval and immediately before the protected filesystem primitive.
9. Durable recovery and receipt preparation precedes the protected side effect.
10. The handler returns the production candidate result as bounded JSON without leaking secrets or recovery bytes.
11. The plugin version and description must change when the registered behavior changes.
12. Source wiring, live installation while disabled, mutation enablement, and the first real mutation are separate authorization units.

See `docs/phase5/p5-02m-repository-integration-and-registration-design-freeze.md`.

## Verification

From the repository root:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  -m unittest discover `
  -s "hermes_plugins\orion-vault-actions\tests" `
  -p "test_p5*.py" `
  -v
```

Windows-only file identity, ACL, local-volume, and handle semantics remain required P5-02N acceptance regressions on the accepted Windows machine; the source branch does not substitute Linux/source checks for that evidence.

## Safety boundary

Do not treat this README, a source test, a plugin registration, an approval card, a persisted receipt, or a visual authority label as mutation authorization.

Production mutation remains separately authorization-gated per action. P5-02Q accepted exactly one bounded canary edit through the guarded P5-02N wrapper; afterward `ORION_P5_MUTATION_MODE` is absent/disabled and Hermes remains manual-off. The next restore or any other edit/move/delete requires a new explicit gate.
