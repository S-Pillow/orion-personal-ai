# P6-UPG-02 — Hermes v0.21.5 Minimal Orion Compatibility

Status: **prepared for next-session disposable implementation/qualification; not yet locally executed**

Prepared: 2026-10-02

Target upstream:

- Hermes tag: `v2026.9.24`
- package: `0.21.5`
- commit: `f97608f178d1ffeca59860195ab7da295f7c8e5f`

Orion source baseline for this branch:

- `69309e1559428ffee0455ed9f476222600e392a4`

Production Hermes remains pinned to:

- tag `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

No production update, COMPANION mutation, gateway restart, or live reminder is authorized by this preparation.

## Why P6-UPG-02 exists

P6-UPG-01 showed that Hermes v0.21.5 has absorbed much of the scheduler behavior Orion had been adding locally. The target architecture therefore moves toward upstream ownership of:

- `scheduled_instant`;
- `pending_slot` recovery;
- completed-occurrence deduplication;
- missed-run/catch-up policy;
- handoff ownership;
- scheduler locking;
- `delivery_outcome`.

Orion should not carry forward superseded P6-04 scheduler logic.

The minimal compatibility layer retains only requirements upstream still does not provide:

1. P6-03 exact-byte preservation before automatic `jobs.json` repair rewrites.
2. P6-04A durable nullable `executions.error_class`.

Historical `scheduled_at` remains readable when already present, but new v0.21.5 scheduled executions use upstream `scheduled_instant`.

## P6-03 design

Before Hermes automatically rewrites a repairable `jobs.json`, preserve the exact source bytes under `cron/recovery/`.

Covered upstream repair transitions:

- invalid-control-character fallback;
- bare-list to canonical object;
- ID-keyed jobs map to canonical list.

Requirements:

- preserve exact bytes before the rewrite;
- fail closed if evidence preservation fails;
- do not create artifacts for canonical reads;
- deduplicate identical evidence by source digest;
- use short Windows-safe filenames;
- retain at most 32 recovery artifacts per cron store;
- re-read under Hermes' existing jobs-store lock before preserving/replacing so an unlocked parse cannot archive stale bytes after a sibling writer wins.

## P6-04A design

The v0.21.5 classifier remains the classification grammar.

The exact reviewed upstream classifier block in
`agent/monitoring/cron_health.py` has SHA-256:

`9e153106740ca017fa8140c1b5a82a1cf530056fc157fd28f357b4983047cddc`

The transformer must refuse to extract a different block.

The rules are moved into dependency-light `cron/error_classification.py`. The tiny upstream-equivalent `_contains_any` helper is local to that module so `cron` does not depend upward on `agent.monitoring.gateway_health`.

Both monitoring and the durable execution ledger consume the same classifier implementation.

Durability rules:

- failed terminal rows persist their derived class in the same transaction as terminal status/error;
- successful rows retain `error_class = NULL`;
- historical rows are not backfilled;
- owner-gone and live-but-wedged recovery write the factual class `interrupted` directly instead of re-inferring it from human-readable text.

## Qualification design

The next-session wrapper performs these stages:

1. fail-closed local/production/candidate guards;
2. clone exact v0.21.5 with `core.autocrlf=false`;
3. create a disposable venv matching production Hermes' Python major/minor;
4. install the **unmodified** candidate first and let upstream code create a real native `executions.db`;
5. transform exactly four candidate source files;
6. syntax-check the transformed Python without writing pycache into the checkout;
7. qualify exact-byte preservation, dedup, retention, fail-closed repair, classifier parity, real upstream-schema migration, current-Orion-schema migration, terminal immutability, and interruption classification;
8. run focused upstream cron regressions;
9. require the candidate checkout to contain only the four expected source changes;
10. stage exactly those four paths;
11. let Git write the binary/full-index patch directly with `--output`;
12. apply that patch to a second LF-normalized exact-tag clone and require per-file SHA-256 parity;
13. repeat read-only production logical-state probes and confirm installed Hermes stayed at the accepted pin.

Expected candidate source delta:

- `cron/jobs.py`
- `cron/error_classification.py`
- `cron/executions.py`
- `agent/monitoring/cron_health.py`

The generated compatibility artifact will be:

- `compat/hermes/v2026.9.24-orion-minimal-compat.patch`

## Known upstream risks carried into P6-UPG-03

The current Hermes issue sweep identified risks worth testing against Orion's **actual** Windows installation topology rather than patching speculatively:

- restart-safe cron external workers can lose runtime venv dependencies on managed installs (open P1 family including #122529 / #129235);
- an update can interrupt an in-flight cron execution (#129947);
- Windows update flows can leave a gateway stopped (#129171);
- interrupted source-update completion can leave a sticky `source-completion-pending` marker (#127284);
- abrupt termination can leave cron blocked behind a stale `.tick.lock` (#129990);
- two Windows scheduler owners can duplicate deliveries (#57191);
- post-update `state.db` integrity verification has a restart-order gap (#110007).

P6-UPG-02 does **not** patch these areas. P6-UPG-03 reproduces the real upgraded topology and patches only defects that affect Orion.

## Community research note

A Reddit sweep did not surface a more authoritative reproduction of Orion's exact v0.21.5 Windows worker case than the Hermes GitHub issues. It did surface two useful operating patterns:

- Hermes users explicitly monitor upstream commits before investing in local workarounds, because the repository moves quickly and a workaround can be obsoleted rapidly.
- Users doing significant customization report that building/qualifying outside the live Hermes tree is substantially easier to control than developing directly inside a dirty runtime checkout.

These support Orion's current approach: exact-tag pinning, issue-led testing, disposable compatibility construction, and promotion only after qualification.

References:

- https://www.reddit.com/r/hermesagent/comments/1t9gz2f/the_cron_job_every_serious_hermes_agent_user/
- https://www.reddit.com/r/hermesagent/comments/1u8w9bw/insource_build_my_painful_revelation/
- https://www.reddit.com/r/hermesagent/comments/1w7az9t/4_hermes_agent_prs_merged_in_the_last_24_hours/

## Current stopping point

The previous operator block failed at PowerShell parse time because a here-string was nested inside another here-string. PowerShell parses the full scriptblock before execution, so that attempt performed no branch creation, file write, production probe, or runtime mutation.

The replacement implementation keeps the transformer, qualifier, PowerShell runner, and documentation as standalone repository files. No nested here-strings are required at runtime.

## Next-session execution order

1. Fetch and switch to `feature/p6-upg-02-v0215-minimal-compat`.
2. Confirm local tree clean and branch head matches GitHub.
3. Run `scripts/phase6/Invoke-P6-UPG-02-GenerateAndQualify.ps1`.
4. Review all PASS/STOP evidence and the generated patch hash.
5. If qualified, commit the generated compatibility patch and qualification evidence.
6. Push exact tested head and run CI.
7. Begin P6-UPG-03 disposable full migration rehearsal.
8. Production Hermes remains unchanged until a separately authorized production migration ticket.
