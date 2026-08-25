# Phase 2 — iai Feasibility and Memory Foundation Status

## Status

Phase 2 is **ACTIVE**.

The iai feasibility branch and the final disposable lifecycle closure are proven. **PH2-IAI-F6 is PASS / CLOSED.** M5 persistent-memory recall across container recreation is also **PASS / CORE ACCEPTANCE COMPLETE**. Remaining Phase 2 work is correction/deletion, memory inspection/export, profile isolation, backup/restore, and fail-open behavior.

This document records the accepted evidence and remaining Phase 2 work. It does not authorize later phases by itself.

## Pinned baseline

- Canonical Hermes image: `hermes-agent-local:v2026.8.18-ddgs`
- Accepted canonical launcher SHA-256: `c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b`
- F6 iai candidate image: `orion-iai-feas:v3.0.0-f5e`
- F6 iai candidate image ID: `sha256:a537708bc22526990c0c5de98250603bc7ba398d123cf6ee4f090a3a7fe91a6b`
- M5 accepted container: `orion-iai-m5-c`
- M5 accepted image ID: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`
- M5 persistent volume: `orion-iai-m5-data`
- iai runtime Python: isolated Python 3.12 environment
- M5 iai package: `iai-pme 3.0.8`
- Hermes runtime for M5: `v0.20.4 (2026.8.18)`

## Proven feasibility evidence

The disposable iai work has established:

- isolated iai Python runtime is viable without replacing Hermes' runtime
- persistent iai store/database materialization works
- encryption-key identity survives service restart within the bounded test environment
- s6 service materialization works under a private disposable supervision tree
- the generated iai service runs as the `hermes` UID
- authoritative pre-exec environment propagation to the iai daemon was proven
- daemon startup and readiness were observed
- expected local socket creation and ownership were observed
- no external network/model/auth calls were required for the feasibility checks
- canonical launcher/profile state was guarded during disposable work
- two complete start/stop lifecycle cycles pass under the final F6 acceptance harness
- `CAP_KILL` is present and the cross-UID stop path succeeds for the iai service
- socket, daemon-state PID, process, and lock cleanup succeed after stop
- the 32-byte crypto key remains byte-size valid and hash-stable across both cycles
- the iai database remains present and non-empty across both cycles
- offline embed identity remains pinned and healthy across both cycles
- persistent semantic memory survives container destruction/recreation
- automatic first-turn recall works through the real Discord DM gateway path after recreation

## Retired verifier branch

The former post-exec `/proc/<pid>/environ` verifier is retired and must not be used as an acceptance gate.

Reasons established during investigation:

1. iai uses `setproctitle`, which changes process-title/environment visibility behavior after exec.
2. In the pinned image, live Python `os.environ` can retain values while `/proc/self/environ` no longer represents those values after process-title rewriting.
3. Cross-UID reads of another process' `/proc/<pid>/environ` are denied in the hardened container without `CAP_SYS_PTRACE`; container root does not bypass that capability boundary.
4. Therefore a clean `/proc/environ` scan can be falsely reassuring as a secret-exposure check and is not authoritative for the iai daemon.

The accepted environment proof for iai remains the pre-exec boundary evidence plus service/run-script inspection, not post-exec procfs environment inspection.

## Hermes supervision calibration relevant to Phase 2

Hermes' supervision architecture is validated:

- s6-overlay / s6-linux-init infrastructure is present
- s6-rc is installed under `/package`
- per-profile gateway services are dynamically materialized under `/run/service`
- real gateway run scripts intentionally use `s6-setuidgid hermes`
- `main-hermes` is intentionally `exec sleep infinity` under Architecture B
- `CAP_KILL` is the proven narrow capability needed for root s6 supervision to signal the differently owned `hermes` child

F6 used this established minimal-capability pattern including `CAP_KILL`. The accepted run proved that the same cross-UID lifecycle mechanism works for the disposable iai service.

## Hermes credential-boundary findings relevant to future memory/tool integration

Installed-source inspection established:

- Hermes loads profile `.env` values into live `os.environ` via `load_hermes_dotenv()`.
- `DISCORD_BOT_TOKEN` is stripped unconditionally from non-terminal child environments through `_ALWAYS_STRIP_KEYS`.
- terminal / `execute_code` child environments strip `DISCORD_BOT_TOKEN` by default through `_HERMES_PROVIDER_ENV_BLOCKLIST`.
- terminal sanitization honors `tools.env_passthrough`, and the passthrough resolver does not itself prohibit always-strip keys.
- current Orion state is clean: `tools.env_passthrough: []`, `tools.docker_forward_env: []`, no inspected skill passthrough declaration, and no COMPANION override identified.
- cross-profile credential isolation is authoritative at read time through `agent.secret_scope.get_secret`, not through global environment cleanup.

Controls carried forward:

- review `tools.env_passthrough` before configuration changes
- review `tools.docker_forward_env` before configuration changes
- review skill declarations before enablement
- verify DEFAULT/COMPANION secret isolation against the read-time secret-scope mechanism

## PH2-IAI-F6 closure

**Status: PASS / CLOSED**

Accepted run completed at `2026-08-24T04:56:25.1822932Z` against the pinned candidate image.

Required conditions proven:

- networking disabled (`NETWORK=NONE`)
- no external auth/model/API calls required
- candidate image identity pinned before and after
- canonical launcher/profile hashes pinned before and after
- DEFAULT entered and exited `UP` with the same PID (`158`)
- COMPANION entered and exited `DOWN`
- private s6 supervision tree used
- minimal capability set included `CAP_KILL`
- iai service ran as UID `10000` (`hermes`)

Lifecycle evidence proven twice:

1. s6 start request succeeded and service reached `up`.
2. s6 child PID equaled the iai daemon PID.
3. daemon readiness reached `READY=YES`, `FSM_STATE=WAKE`.
4. local socket existed while running and was owned by UID `10000`.
5. stop request succeeded.
6. daemon process, state PID, socket, and lock were absent after stop.
7. the same sequence passed a second time.
8. crypto key remained present, exactly 32 bytes, and SHA-256-stable across both cycles.
9. `brain.sqlite3` remained present and non-empty (`139264` bytes at final check).
10. offline embed identity was healthy and pinned in both cycles.
11. canonical hashes, gateway states, DEFAULT PID, and candidate image identity remained unchanged.
12. disposable cleanup succeeded and the wrapper ended with child exit code `0`.

The retired post-exec `/proc/<iai-pid>/environ` verifier was not reintroduced.

Retained local evidence:

```text
E:\Orion-Phase2\PH2-IAI-F6-20260824-032307Z\
```

Acceptance artifacts include:

- `15-f6-lifecycle-run.txt`
- `20-f6-final-lifecycle.txt`
- `21-f6-final-summary.txt`
- `22-f6-runner-output.txt`

See `docs/phase2/ph2-iai-f6-closure.md` for the detailed closure record and evidence-calibration lessons.

## M5 persistent-memory recall closure

**Status: PASS / CORE ACCEPTANCE COMPLETE**

Accepted on August 25, 2026 in a real fresh Discord DM session.

M5 proves:

- the captured marker `topaz-6842` survived persistent-volume reuse across container destruction/recreation
- iai semantic recall after recreation returned the marker
- the corrected `session_start_payload` exposed the memory
- Hermes' `pre_llm_call` context-injection path accepted the memory
- the serializer/Hermes-wire compatibility fix survived image recreation
- `/new` in the real Discord DM created the fresh-session boundary
- the first vault-code question in that fresh Discord DM returned exactly `topaz-6842`

The accepted end-to-end path is:

**capture → persistent encrypted memory → container destruction/recreation → iai recall → automatic first-turn injection → real fresh-session Discord model recall**

A real upstream iai defect was found during M5: `SessionStartPayload.recent_thread` was populated by assembly but omitted by `_payload_to_json()` in the dispatch serializer. Orion's one-field compatibility fix restored it. The defect was reported upstream as `CodeAbra/iai-personal-memory-engine#156`.

See `docs/phase2/m5-memory-recall-closure.md` for the detailed M5 closure record.

Two apparent failures during diagnosis were invalid acceptance attempts: one was entered directly into Hermes, and one was sent to the wrong Discord channel. A suspected `state.db` persistence defect raised during that investigation is not established and is not carried forward without independent reproduction.

## Scope boundary

F6 proves the pinned iai candidate's disposable service lifecycle, supervision, persistence, and cleanup behavior. M5 additionally proves persistent memory and automatic recall across container recreation through the intended Discord DM path. These results do **not** close the remaining Phase 2 product controls.

## Remaining Phase 2 work

Proceed with:

- correction/deletion semantics
- memory inspection/export
- profile isolation
- backup/restore
- fail-open behavior when iai is unavailable
- confirmation that ordinary Hermes chat continues without memory-service availability

Later phases remain gated until the full Phase 2 exit criteria are met.
