# P4-02B1A v3r1 — Brain dashboard chmod deployment failure

Date: 2026-08-27

Status: **DEPLOYMENT HARNESS FAILURE — P4-02B1A REMAINS IN PROGRESS**

## Progress reached

The repaired v3r1 continuation passed the earlier CRLF-sensitive import guard and then successfully completed:

- parser/hash gates
- runtime preflight
- bounded continuation-state validation
- fork sync
- source patch/assertions
- target Brain-container Python compile
- diff check
- source commit and push
- Brain dashboard path validation
- Brain dashboard backup

The accepted upstream-compatible iai compatibility source is now committed and pushed as:

`55a8c32ece1f2af32002b3e0e542bead7290bdf1` — `fix: make BrainView controls container-safe`

The commit changes exactly the intended Brain control-plane compatibility surfaces:

- `src/iai_mcp/brainview.py`
- `src/iai_mcp/_deploy/brainview/index.html`

It adds the required `reason` for `user_initiated_sleep`, returns `external_manager` for Linux container lifecycle control instead of trying `systemctl --user`, and adds the matching dashboard status copy.

## Failure boundary

The run then stopped after the dashboard backup at a deployment-only permission step:

`docker exec orion-iai-dashboard chmod 644 ...`

Both package paths returned:

`Operation not permitted`

Backup directory reported by the run:

`E:\Orion-Phase2\P4-02B1A-backups\20260827-211216`

No manual Brain control smoke was reached.

## Diagnosis

This is not an iai memory-semantics defect and does not invalidate the pushed compatibility commit. The failure is in the deployment harness requiring an unnecessary in-container `chmod` after the file copy. The dashboard runtime only needs the deployed package files to be readable; normalizing the mode from the container's default exec user is not itself an acceptance requirement.

The next continuation should:

1. treat commit `55a8c32...` as the accepted source candidate and require a clean fork at that exact commit;
2. inspect whether the failed attempt left candidate files in place or rolled them back;
3. if needed, back up and copy the two committed files again;
4. verify exact deployed hashes and verify that the dashboard runtime user can read both files;
5. skip the redundant `chmod` rather than broaden container privileges;
6. restart only `orion-iai-dashboard`;
7. verify Brain HTTP health and the new externally-managed UI copy;
8. verify `orion-iai-m5-c` ID and StartedAt remain unchanged;
9. only then proceed to manual Brain control smoke.

## Safety disposition

Do not reset or clean the iai fork. Do not recreate/restart the accepted core Hermes/iai container. Do not add capabilities or Docker-socket authority merely to satisfy the failed chmod step.
