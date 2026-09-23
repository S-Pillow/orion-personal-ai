# P5-02N Guarded Registered Apply Wrapper

Status: **SOURCE CANDIDATE / RUNTIME UNCHANGED / VERIFICATION IN PROGRESS**

Date: 2026-09-23

Branch: `feature/orion-phase5-p5-02n-registered-wrapper`

Base: P5-02M design-freeze head `5e2967d1c7e63a312d082ae8cece737c5154000f`

## Purpose

P5-02N implements the source-side registered apply wrapper frozen by P5-02M. It changes repository source and tests only.

This gate does not install or replace the COMPANION plugin, change COMPANION configuration or `.env`, start Hermes, enable production mutation, or touch production vault, inbox, or recovery records.

## Owner authorization

The owner explicitly authorized P5-02N source wiring after the P5-02M design freeze.

Authorized work:

- implement the named guarded public wrapper;
- wire the public apply registration to that wrapper;
- keep the public schema limited to `plan_token`;
- block disabled, preview-only, missing, and invalid mutation modes before approval or executor delegation;
- keep `_execute_production_plan_candidate()` private and unregistered;
- bump the plugin manifest to `0.2.0`;
- add and update source regressions;
- prepare source-control review material.

Not authorized:

- live plugin installation or replacement;
- COMPANION config or environment changes;
- Hermes/Ollama/iai lifecycle changes;
- persisting or enabling `ORION_P5_MUTATION_MODE`;
- production vault/inbox mutation;
- production recovery-root or ACL mutation;
- dependency upgrades.

## Implemented source contract

The registered apply handler is:

```text
apply_plan_production_guarded(params: Dict[str, Any], **_: Any) -> str
```

The public schema exposes only:

```json
{"plan_token": "string"}
```

and declares additional properties invalid.

Mode behavior is fail closed on every invocation:

- missing or blank mode -> `production_mutation_not_enabled`;
- `disabled` -> `production_mutation_not_enabled`;
- `preview_only` -> `production_mutation_not_enabled`;
- unknown mode -> `invalid_production_mutation_mode`;
- `mutation_enabled` -> delegate only the normalized `plan_token` to the private production executor.

Caller-supplied approval callbacks, redactors, probes, roots, proposed bytes, or failure hooks are not forwarded by the registered wrapper.

## Approval ownership

`pre_tool_call` remains the fail-closed plan-validation hook.

- For invalid or non-enabled production mode it blocks apply and produces no approval directive.
- For explicit `mutation_enabled` and a valid plan it returns no approval directive.
- The private production executor remains the only owner of the fresh Hermes generic approval request.
- Mutation still requires both an approved gate result and a matching fresh, non-coalesced human `choice=once` observer event.
- Existing stale-state, replay, recovery-inventory, receipt, filesystem identity, atomic-operation, and postcondition safeguards remain inside the private executor.

The private executor is not registered as any public tool.

## Source changes

- `hermes_plugins/orion-vault-actions/__init__.py`
  - adds and registers `apply_plan_production_guarded`;
  - changes non-enabled/invalid `pre_tool_call` behavior from approval request to block;
  - keeps `_execute_production_plan_candidate()` private;
  - keeps four tools and two hooks.
- `hermes_plugins/orion-vault-actions/plugin.yaml`
  - version `0.2.0`;
  - guarded-apply description.
- Existing P5 source tests are updated where they intentionally asserted the pre-P5-02N placeholder registration or preview-only approval prompt.
- `test_p5_02n_registered_wrapper.py` adds direct registration, schema, mode, delegation, and injection-boundary tests.
- Repository and plugin READMEs distinguish the new source candidate from the unchanged installed P5-02L runtime.

## Verification plan

Required source verification:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  -m unittest discover `
  -s "hermes_plugins\orion-vault-actions\tests" `
  -p "test_p5*.py" `
  -v
```

HUD approval-rendering regressions remain part of the P5-02N acceptance set:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  -m unittest discover -s "hud\tests" -p "test_*.py" -v

node "hud\tests\test_approval_rendering.cjs"
```

Python compile checks should cover the plugin and affected Python tests.

The accepted Windows-specific file-identity, ACL, fixed-local-volume, `ReplaceFileW`, held-handle, and delete-pending regressions must pass on the accepted Windows machine. P5-02N does not reopen the accepted production recovery root or lifecycle state merely to recreate old evidence.

## Current verification state

Repository/source inspection confirms:

- the branch descends directly from the P5-02M head;
- public registration points to `apply_plan_production_guarded`;
- `_execute_production_plan_candidate()` remains unregistered;
- the apply schema exposes only `plan_token` and rejects additional properties;
- invalid/non-enabled modes block in `pre_tool_call`;
- the wrapper cannot forward caller-supplied callbacks, roots, probes, bytes, or failure hooks;
- manifest version is `0.2.0`;
- installed/runtime state has not been changed by this source work.

The full executable regression set has not yet been claimed as passing in this record. Record exact counts only after it is actually run.

## Acceptance boundary

P5-02N may be accepted only after the required executable source/HUD regressions and applicable Windows-specific checks pass and the N-only diff is reviewed.

P5-02N acceptance does **not** authorize installation.

The next separate unit is P5-02O: install the accepted source with rollback captured while production mutation remains absent/disabled, verify the live registered wrapper refuses without a human approval prompt, then restore manual-off.

Any real production edit, move, restore, or later delete requires another owner authorization beyond P5-02O.
