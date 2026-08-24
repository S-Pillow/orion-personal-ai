# PH2-IAI-F6 — Final Disposable iai Service Lifecycle Closure

## Disposition

**PASS / CLOSED**

Accepted at `2026-08-24T04:56:25.1822932Z`.

This record closes the final disposable iai service lifecycle acceptance unit. It does not authorize canonical iai installation and does not close Phase 2 as a whole.

## Pinned artifacts

- iai candidate image: `orion-iai-feas:v3.0.0-f5e`
- candidate image ID: `sha256:a537708bc22526990c0c5de98250603bc7ba398d123cf6ee4f090a3a7fe91a6b`
- canonical Hermes container observed during acceptance: `057493d2fcbc`
- accepted canonical launcher SHA-256: `c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b`
- iai runtime: isolated Python 3.12
- lifecycle store: `/opt/data/profiles/companion/.iai-mcp`
- service: private disposable s6 service `iai-companion`

## Retained evidence

Authoritative local evidence directory:

```text
E:\Orion-Phase2\PH2-IAI-F6-20260824-032307Z\
```

Final retained artifacts verified non-empty after cleanup:

- `15-f6-lifecycle-run.txt` — 11394 bytes
- `20-f6-final-lifecycle.txt` — 6470 bytes
- `21-f6-final-summary.txt` — 539 bytes
- `22-f6-runner-output.txt` — 11286 bytes

The summary artifact records `PH2_IAI_F6_FINAL=PASS`, `CYCLES_COMPLETED=2`, `DURABLE_EVIDENCE_RETAINED=PASS`, and the accepted UTC result timestamp above.

## Acceptance result

The accepted run established all of the following:

- Docker network mode `none`
- private s6 PID 1 (`s6-svscan`)
- capability set containing `CAP_KILL` with other capabilities explicitly bounded
- service materialized default-down under the private s6 tree
- executable capability of the service mount proven before lifecycle start
- iai crypto key created as 32 bytes
- iai store/database initialized successfully
- two full start/stop cycles completed
- cycle 1 s6 PID = iai daemon PID = `101`
- cycle 2 s6 PID = iai daemon PID = `216`
- daemon UID = `10000` in both cycles
- readiness = `READY=YES`, FSM = `WAKE` in both cycles
- socket owned by UID `10000` while running
- offline embed identity healthy and pinned in both cycles:
  `BAAI/bge-small-en-v1.5@pinned|pool=cls|dim=384`
- clean stop after both cycles with process absent, daemon-state PID absent, socket absent, and lock absent
- crypto key remained present, 32 bytes, and SHA-256-stable across initial, cycle 1, and cycle 2 checks
- final database remained present and non-empty (`139264` bytes)
- final socket absent
- canonical launcher/profile hashes unchanged from entry to exit
- candidate image ID unchanged from entry to exit
- DEFAULT gateway entered `UP PID=158` and exited `UP PID=158`
- COMPANION gateway entered `DOWN` and exited `DOWN`
- post-cleanup independent verification again showed DEFAULT `up (pid 158 ...)` and COMPANION `down`
- disposable cleanup exit code `0`
- lifecycle wrapper child exit code `0`
- runner end marker `PASS`

## Retired verifier preserved

The post-exec `/proc/<iai-pid>/environ` verifier was not used.

Prior evidence established that iai's `setproctitle` behavior can invalidate `/proc/<pid>/environ` as an authoritative post-exec environment verifier while leaving live in-process environment values intact. Pre-exec boundary proof remains the accepted environment evidence.

## Evidence-calibration lessons from F6

Several failures during harness construction were verifier or execution-envelope defects rather than iai lifecycle failures. They are retained as process lessons, not as product regressions.

### Resolution before absence

A failed lookup is a resolution result, not proof of absence. F6 reinforced the standing rule across filesystem paths, Python module attributes, and locally imported symbols. The iai store root was resolved from installed source before negative persistence conclusions were accepted.

### Upstream evidence review before workaround design

Dependency-shaped failures must trigger upstream evidence review before local workaround iteration. Two examples were material:

- .NET multiline regex handling of CRLF explained the false PID extraction failure; the supported narrow fix is a CRLF-tolerant end anchor such as `\r?$`.
- Docker tmpfs execution policy explained the s6 `Permission denied` on the generated service run script; local capability probing then verified the corrected executable mount behavior.

Upstream evidence does not replace local verification; both were required.

### PowerShell execution discipline

Substantial verification units should use a real `.ps1` file, strict mode, parse-check, a fresh PowerShell child process, durable output capture, and explicit exit markers.

Additional harness rules established by F6:

- do not rely on console-session variables for unit constants
- use `-LiteralPath` for evidence-critical filesystem operations
- do not suppress binding or lookup errors that could masquerade as negative evidence
- avoid function names that collide with commands they invoke
- avoid parameter/assignment names that collide with PowerShell automatic or read-only variables
- structured-return helpers must keep diagnostics off the success pipeline
- extraction of acceptance-critical values must fail closed rather than coerce missing matches to benign defaults
- persistence checks should combine presence, size, and stable identity where practical
- prove executable capability in place; file presence and mode alone are not enough
- write retained evidence before cleanup

## Scope boundary

This closure proves the pinned iai candidate's disposable service lifecycle, cross-UID supervision, socket cleanup, key/database persistence across service restart, offline embed identity, and non-interference with the canonical DEFAULT/COMPANION gateway states.

It does **not** prove:

- iai is installed into the canonical Hermes runtime
- persistence across canonical container recreation
- end-user memory capture/recall behavior
- correction/deletion semantics
- profile-isolated memory behavior
- backup/restore
- fail-open product behavior if iai is unavailable

Those remain Phase 2 memory-product acceptance work.

## Next authorization direction

Proceed to the bounded Phase 2 memory-product acceptance units covering controlled conversation capture, persistent recall across restart, correction/deletion, memory inspection/export, profile isolation, backup/restore, fail-open behavior, and ordinary Hermes chat continuity when iai is unavailable.
