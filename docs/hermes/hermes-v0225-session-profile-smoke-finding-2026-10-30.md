# Hermes v0.22.5 session/profile smoke finding — 2026-10-30

Status: **HARNESS PRE-FLIGHT METHOD FAILURE — CANDIDATE NOT LAUNCHED**

## Observed result

The first isolated session/profile contract attempt stopped before starting Hermes. The failure occurred inside the reused v5 `probe_scratch_identity()` helper. Its single child Python process had a fixed 20-second timeout while importing/resolving all of the following in one opaque probe:

- `get_hermes_home()` / `profile_name_for_home()`;
- `profile_is_standalone()`;
- Windows `get_task_name()`.

The child process exceeded the 20-second deadline and `subprocess.TimeoutExpired` propagated out of preflight.

No gateway process was launched by this attempt, no session API request ran, and no model, memory, STT, or TTS provider call was made. The attempt therefore provides no evidence for or against the Hermes v0.22.5 session-resource contract.

## Why this is classified as a harness failure

The same composite identity probe had already passed during the accepted v6 standalone gateway smoke against the same exact candidate commit, runtime environment, scratch profile name, and standalone topology. v6 established:

- scratch profile `orion_v0225_qual`;
- `gateway.standalone=true`;
- Windows task identity `Hermes_Gateway_orion_v0225_qual`;
- no collision with the production COMPANION Scheduled Task;
- stable isolated HTTP readiness and authenticated API behavior.

The failed session/profile attempt never reached candidate launch, so attributing the timeout to Hermes runtime/session behavior would be unsupported. The composite probe also provides no phase-level timing, so the evidence does not identify which import/resolution step consumed the timeout.

## Observer correction

`v0225_isolated_session_profile_contract_smoke_v2.py` changes only the observation method, not the session acceptance contract:

1. verify `HERMES_HOME` points to the generated `profiles/orion_v0225_qual` scratch profile;
2. read scratch `config.yaml` directly and require `gateway.standalone: true`;
3. reuse the exact Windows task identity already proven by v6 for this immutable candidate/profile combination, while still querying `schtasks` to fail closed if that task exists;
4. retain the existing HTTP health/process-stability checks before session-resource requests;
5. retain authenticated create/get/patch/list/delete session checks;
6. after gateway cleanup, verify the scratch `state.db` directly with Python stdlib `sqlite3` opened in read-only mode;
7. require the persisted session row to contain the updated title and pinned flag and require the deleted session row to be absent;
8. retain production watched-state, production 8642 health, candidate-source, isolated-port cleanup, and secret-redaction postconditions.

The v2 observer does not send a chat turn and does not invoke model, memory, STT, or TTS providers.

## Disposition

- Session/profile gate: **UNRESOLVED** until v2 runs.
- Hermes v0.22.5 candidate: **not failed by this attempt**.
- Production Hermes: **no authorized mutation or cutover**.
- Next bounded action: run the observer-hardened v2 session/profile smoke once and review its complete output before moving to another runtime gate.
