# P6-UPG-04 — Controlled Production Hermes v0.21.5 Upgrade Review

Status: **PREPARED — CURRENTLY NO-GO ON OPEN VENDOR P1 #131145**

Production mutation, pin change, gateway stop/restart, and live reminder remain
unauthorized.

## Accepted candidate from P6-UPG-03

Hermes target:

- tag: `v2026.9.24`
- package: `0.21.5`
- commit: `f97608f178d1ffeca59860195ab7da295f7c8e5f`

Qualified Orion candidate:

- exact Hermes v0.21.5 target;
- P6-UPG-02 Orion compatibility patch;
- upstream `f57d2357485f1cc234e438b813e75c241a09c9e7` external-worker
  dependency fix;
- combined artifact:
  `compat/hermes/v2026.9.24-orion-qualified-combined.patch`;
- combined SHA-256:
  `21edb9cf49eb6e2724852dc090f755cf38564db5026ab4d0b3814f34c0b355e4`.

P6-UPG-03 acceptance:

- exact upstream worker-fix regression set: 5 passed;
- Orion-relevant focused set: 56 passed, 15 skipped;
- SQLite integrity selftest: PASS;
- production cron logical state unchanged;
- installed Hermes unchanged;
- no gateway restart or live reminder.

## Evidence policy for this ticket

Documented upstream defects and vendor fixes are decision inputs. P6-UPG-04 does
not independently re-prove a vendor defect merely to confirm that upstream is
telling the truth. Extra local reproduction is required only when Orion is
materially different or when the result would change the production decision.

That rule is why the worker dependency defect uses the accepted upstream
`f57d235` backport directly.

## 2026-10-04 upstream release and risk review

### Latest stable release

GitHub Releases still lists `v2026.9.24 / 0.21.5` as the latest stable Hermes
release. There is no later stable tag available to choose instead today.

### Blocking P1: #131145 boot warm-up / first-turn wedge

Issue #131145 remains open and is labelled P1. Its reported environment is
Hermes 0.21.5 on Windows 11. The failure signature is material to Orion:

- boot turn-machinery warm-up does not complete;
- the target's bounded startup wait expires;
- the inbound gate opens anyway;
- the first inbound turn can wedge before any provider request;
- gateway status may still report healthy;
- only a gateway restart clears the observed wedge.

The exact v0.21.5 source contains this behavior:

- default warm-up timeout: 20 seconds;
- `HERMES_STARTUP_WARMUP_TIMEOUT` controls the bound;
- on timeout the code explicitly opens the inbound gate while warm-up continues
  in the background.

This is new relative to Orion's accepted production v0.20.6 line.

PR #131148 attempted to keep the gate closed during warm-up. It was closed
unmerged. Maintainer review found the unbounded version could instead hold the
gateway closed forever; the author restored the bounded behavior, leaving no
net fix, and the maintainer explicitly stated that the underlying hang remains
tracked in #131145.

Draft PR #132700 only raises late warm-up failures from DEBUG to WARNING. Its
own description calls it a partial visibility fix and says the wedge root cause
still requires follow-up.

**Decision:** do not backport PR #131148, do not invent an Orion-specific
warm-up workaround, and do not proceed to production while the qualified
candidate lacks a vendor-proven resolution to #131145.

The execution packet therefore requires a committed
`docs/phase6/p6-upg-04-warmup-clearance.json` bound to the candidate artifact.
That file intentionally does not exist today. The mutation script cannot cross
the source-replacement boundary without it.

### Other open production risks

The current upstream review also reconfirmed:

- #129171 (P2): Windows update can report success while the gateway remains
  stopped.
- #129947 (P1): update can interrupt active cron work because updater drain
  bounds do not necessarily cover a running job.
- #129990 (P2): abrupt termination can leave cron tick ownership stalled on
  Windows.
- #110007 (P2): update-time state.db verification ordering does not prove the
  database is still healthy after the restarted gateway is live.
- #127284 (P2): source-completion-pending can strand newer PM-managed update
  completion state.

The exact v0.21.5 target predates the later PM/source-completion implementation,
so #127284 is retained only as a defensive marker check; no PM-era code is being
backported into this pre-PM target.

## Production strategy

P6-UPG-04 deliberately does **not** use `hermes update`.

Instead, after all gates pass and the owner explicitly authorizes execution, it
uses the exact v0.21.5 official Windows installer in stage mode and a preserved
rollback copy:

1. Run the read-only production preflight.
2. Download the exact target `scripts/install.ps1` by commit and verify it
   before stopping anything.
3. Gracefully stop the current gateway and require port 8642 to be released.
4. With the gateway offline, run fresh read-only SQLite integrity checks.
5. Preserve the entire accepted v0.20.6 install directory by moving it to a
   timestamped sibling backup outside `HERMES_HOME`; copy the Hermes launcher
   bin directory for rollback.
6. Use the official installer `repository` stage to create the exact
   v0.21.5 checkout at the normal install path.
7. Apply the single qualified combined Orion artifact and verify the exact
   runtime file hashes.
8. Use official installer stages for `python`, `venv`, `dependencies`,
   `node-deps`, profile-aware `platform-sdks`, `path`, and
   `bootstrap-marker`.
9. Intentionally skip `config-templates`, `configure`, and automatic
   `gateway` stages so the upgrade does not rewrite user configuration,
   synchronize skills, or hide the restart boundary.
10. Start the gateway once with the vendor CLI and perform post-start
    acceptance.
11. On any critical post-activation failure, stop the new gateway, preserve the
    failed new install, restore the old install + launchers, and return the old
    gateway before doing diagnosis.

No runtime database is hand-edited and the old install backup is never
automatically deleted after a successful upgrade.

## Exact vendor installer pin

The exact v0.21.5 `scripts/install.ps1` reviewed for the packet is:

- Git blob: `ca17df8fcf63d2dc0072f0e248c3635aed2fcf97`
- SHA-256:
  `0a80dfeb7434229933bac32e73140d10086dff81bd84b156e71be9abc87cddf2`

The controlled packet downloads the script from the exact target commit and
refuses to continue if this hash differs.

The target installer natively supports the stage protocol, explicit
`-Commit`, `-ForceCommit`, `-HermesHome`, `-InstallDir`, and
`-NonInteractive`. Its dependency stage uses the locked project environment
before fallback behavior. These are vendor mechanisms, not an Orion-created
installer.

## Prepared code

The P6-UPG-04 branch contains:

- `scripts/phase6/Invoke-P6-UPG-04-Preflight.ps1` — read-only production
  baseline and no-go/readiness verdict.
- `scripts/phase6/p6-upg-04-state-guard.py` — read-only active-cron and SQLite
  integrity probes.
- `scripts/phase6/Invoke-P6-UPG-04-ControlledUpgrade.ps1` — guarded production
  execution + rollback packet. Without `-Execute` it is preview-only.
- `scripts/phase6/Test-P6-UPG-04-Packet.ps1` — PowerShell parser checks,
  Python syntax check, artifact hash check, static safety checks, and
  no-mutation preview validation.

The controlled script additionally requires the exact authorization token
`P6-UPG-04-PRODUCTION-UPGRADE`. That token alone is insufficient: the
warm-up clearance artifact must also exist and bind a qualified vendor fix to
the candidate hash.

## Same-day preflight — all must pass

Before any mutation:

1. Orion is on the P6-UPG-04 branch with a clean worktree.
2. Combined compatibility artifact hash matches the accepted value.
3. Installed Hermes still matches production commit
   `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`.
4. The installed Hermes dirty set exactly matches the accepted production set.
5. Production cron remains at the accepted zero-job / zero-execution baseline.
6. No claimed/running/handoff execution exists.
7. No source-completion marker exists.
8. Exactly one gateway listener owns port 8642.
9. Gateway process shape matches the accepted Windows topology.
10. Required vendor prerequisites (`git`, `node`, `npm`, `uv`) are
    available.
11. Vendor P1 #131145 has a vendor-proven resolution incorporated into and
    requalified with the candidate.

Any mismatch is a STOP.

## Mandatory post-start acceptance

A successful installer message is not acceptance. The packet requires:

- exact target HEAD and exact qualified dirty set;
- exact patched runtime hashes;
- required runtime imports;
- one new gateway process/listener and healthy gateway status;
- no stranded source-completion marker;
- fresh-connection SQLite integrity checks after the new gateway is live;
- preserved cron logical counts and required execution schema columns;
- ticker heartbeat advancement within the bounded acceptance window;
- positive `Turn machinery warmed in ...` evidence from only the newly
  appended gateway logs;
- no `opening inbound gate anyway` warm-up timeout signature;
- no duplicate gateway ownership.

A live reminder is not part of P6-UPG-04 and remains separately authorized.

## Tomorrow's first decision

Before running any production mutation tomorrow, re-check upstream #131145 and
the latest stable release.

- If #131145 remains unresolved for the candidate: **NO-GO; stay on accepted
  v0.20.6.**
- If upstream ships a proven fix or a newer stable release: reconcile only that
  concrete vendor change, update/requalify the candidate as needed, create the
  bound warm-up clearance artifact, run the packet self-check and read-only
  preflight, then request explicit production authorization.

This is a production safety gate, not a request for more exploratory testing.
