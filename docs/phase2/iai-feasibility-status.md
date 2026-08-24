# Phase 2 — iai Feasibility and Memory Foundation Status

## Status

Phase 2 is **ACTIVE**.

The iai feasibility branch and the final disposable lifecycle closure are now proven. **PH2-IAI-F6 is PASS / CLOSED.** The next work is Phase 2 memory-product acceptance.

This document records the accepted evidence and remaining Phase 2 work. It does not authorize canonical iai deployment or later phases by itself.

## Pinned baseline

- Canonical Hermes image: `hermes-agent-local:v2026.8.18-ddgs`
- Accepted canonical launcher SHA-256: `c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b`
- iai candidate image: `orion-iai-feas:v3.0.0-f5e`
- iai candidate image ID: `sha256:a537708bc22526990c0c5de98250603bc7ba398d123cf6ee4f090a3a7fe91a6b`
- iai runtime Python: isolated Python 3.12 environment

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
- two complete start/stop lifecycle cycles now pass under the final F6 acceptance harness
- `CAP_KILL` is present and the cross-UID stop path succeeds for the iai service
- socket, daemon-state PID, process, and lock cleanup succeed after stop
- the 32-byte crypto key remains byte-size valid and hash-stable across both cycles
- the iai database remains present and non-empty across both cycles
- offline embed identity remains pinned and healthy across both cycles

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

## Scope boundary

F6 proves the pinned iai candidate's disposable service lifecycle, supervision, persistence, and cleanup behavior. It does **not** mean iai is installed into the canonical Hermes runtime, and it does not by itself satisfy the Phase 2 memory-product acceptance criteria.

## After F6

Proceed to the actual Phase 2 memory-product acceptance work:

- controlled conversation capture
- persistent recall across restart
- correction/deletion semantics
- memory inspection/export
- profile isolation
- backup/restore
- fail-open behavior when iai is unavailable
- confirmation that ordinary Hermes chat continues without memory-service availability

Later phases remain gated until Phase 2 exit criteria are met.
