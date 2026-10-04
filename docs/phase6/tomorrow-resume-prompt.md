# Resume Prompt — Orion P6-UPG-04

We are resuming the Orion Personal AI project.

Repository: `S-Pillow/orion-personal-ai`

Use native Windows PowerShell + Git/GitHub. There is no Builder Agent.

Start by reconciling GitHub, current upstream Hermes release/issue state, and
the installed production Hermes state. Do not guess from memory.

## Durable checkpoint

Accepted production Hermes remains unchanged:

- tag `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

P6-03, P6-04, and P6-04A production compatibility work are already live on
that accepted production install. Do not reset, clean, or revert the accepted
production Hermes dirty set.

P6-UPG-03 is accepted and closed.

Qualified upgrade target:

- Hermes tag `v2026.9.24`
- package `0.21.5`
- exact target commit `f97608f178d1ffeca59860195ab7da295f7c8e5f`
- P6-UPG-02 Orion compatibility
- upstream external-worker fix
  `f57d2357485f1cc234e438b813e75c241a09c9e7`
- combined artifact
  `compat/hermes/v2026.9.24-orion-qualified-combined.patch`
- combined SHA-256
  `21edb9cf49eb6e2724852dc090f755cf38564db5026ab4d0b3814f34c0b355e4`

P6-UPG-03 acceptance:

- upstream worker-fix tests: 5 passed
- Orion-relevant focused tests: 56 passed, 15 skipped
- SQLite guard selftest: PASS
- production logical state unchanged
- installed Hermes unchanged
- no restart/live reminder

## Current branch

`feature/p6-upg-04-controlled-production-upgrade`

Read first:

1. `docs/phase6/p6-upg-04-controlled-production-upgrade-review.md`
2. `scripts/phase6/Test-P6-UPG-04-Packet.ps1`
3. `scripts/phase6/Invoke-P6-UPG-04-Preflight.ps1`
4. `scripts/phase6/Invoke-P6-UPG-04-ControlledUpgrade.ps1`
5. `scripts/phase6/p6-upg-04-state-guard.py`

## Current production decision: NO-GO until upstream changes

As of 2026-10-04, latest stable Hermes remains `v2026.9.24 / 0.21.5`.

Upstream #131145 remains OPEN / P1 on Hermes 0.21.5 + Windows 11. It documents
an incomplete boot warm-up that can let the inbound gate open and leave the
first turn wedged before any provider call while gateway status still looks
healthy.

PR #131148 is closed unmerged. Maintainer closure says its first unbounded wait
created a larger availability problem; after restoring the bounded behavior
the PR had no net change, and the underlying hang remains tracked in #131145.

PR #132700 is still a draft partial visibility fix only; its own description
says the wedge root cause remains follow-up work.

Therefore do not execute the production upgrade merely because the prepared
packet exists.

## Evidence policy

Do not independently re-prove documented vendor defects when the target source
and upstream evidence already establish them. Treat upstream issue/fix evidence
as a decision input unless Orion is materially different or local testing would
change the decision.

## Tomorrow's sequence

1. Re-check the latest stable Hermes release and #131145 first.
2. If #131145 is still unresolved for the candidate, keep production on
   accepted v0.20.6. Do not run the mutation packet.
3. Synchronize the P6-UPG-04 branch and run
   `scripts/phase6/Test-P6-UPG-04-Packet.ps1`.
4. Run `scripts/phase6/Invoke-P6-UPG-04-Preflight.ps1` with its default
   `OPEN_UNRESOLVED` disposition. The expected safe result while the vendor
   blocker remains is `P6_UPG_04_VERDICT=NO_GO_VENDOR_P1_WARMUP`.
5. If upstream has shipped a proven merged fix or newer stable release,
   reconcile only that concrete upstream change, update the candidate and
   hashes, requalify it, and create
   `docs/phase6/p6-upg-04-warmup-clearance.json` with vendor provenance +
   Orion qualification evidence.
6. Re-run packet self-check and read-only preflight.
7. Only then request explicit owner authorization for the production mutation
   and one controlled gateway restart.

## Prepared execution strategy after clearance + authorization

The controlled packet does not use `hermes update`.

It:

- verifies the exact installed production head/dirty set and idle state;
- verifies one gateway owner/listener and zero active work;
- verifies the qualified artifact and exact target installer hashes;
- downloads the exact target installer by commit;
- gracefully stops the old gateway and requires the old process to exit;
- runs fresh offline SQLite integrity across root + all profile state DBs;
- creates verified SQLite backups outside `HERMES_HOME`;
- preserves the complete old install and Hermes launcher directory;
- stages exact v0.21.5 using the vendor installer's official stage protocol;
- applies the single qualified combined compatibility artifact;
- verifies exact patched source hashes;
- builds the target venv/dependencies via official installer stages;
- starts the gateway once using the vendor CLI;
- verifies one new gateway owner/listener, fresh SQLite integrity, cron schema,
  ticker heartbeat advancement, and positive warm-up completion;
- rolls back the old install on critical activation failure.

State-integrity anomalies fail closed: the packet does not restart a gateway
against unverified state.

Rollback does not force-kill by default. The optional
`-AllowEmergencyForceStop` path is a separate emergency authorization and
will only target a listener owner that is verified as a Hermes gateway.

## Authorization boundary

No production Hermes mutation, pin change, gateway stop/restart, live reminder,
state repair, or emergency force-stop is authorized by this preparation.

Do not invent a workaround for #131145. Prefer the safe documented upstream
path: vendor fix/new stable, bounded requalification, then controlled upgrade.
