# Phase 2 — iai Feasibility and Memory Foundation Status

## Status

Phase 2 is **ACTIVE**.

The iai feasibility branch is substantially proven. The next authorization unit is:

> **PH2-IAI-F6 — final disposable iai service lifecycle closure**

This document records the accepted evidence and remaining closure work. It does not authorize production deployment or later memory-product phases by itself.

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

## Retired verifier branch

The former post-exec `/proc/<pid>/environ` verifier is retired and must not be used as an acceptance gate.

Reasons established during investigation:

1. iai uses `setproctitle`, which changes process-title/environment visibility behavior after exec.
2. In the pinned image, live Python `os.environ` can retain values while `/proc/self/environ` no longer represents those values after process-title rewriting.
3. Cross-UID reads of another process' `/proc/<pid>/environ` are denied in the hardened container without `CAP_SYS_PTRACE`; container root does not bypass that capability boundary.
4. Therefore a clean `/proc/environ` scan can be falsely reassuring as a secret-exposure check and is not authoritative for the iai daemon.

The accepted environment proof for iai remains the pre-exec boundary evidence plus service/run-script inspection, not post-exec procfs environment inspection.

## Hermes supervision calibration relevant to F6

Hermes' supervision architecture is validated:

- s6-overlay / s6-linux-init infrastructure is present
- s6-rc is installed under `/package`
- per-profile gateway services are dynamically materialized under `/run/service`
- real gateway run scripts intentionally use `s6-setuidgid hermes`
- `main-hermes` is intentionally `exec sleep infinity` under Architecture B
- `CAP_KILL` is the proven narrow capability needed for root s6 supervision to signal the differently owned `hermes` child

F6 may therefore use the established minimal-capability pattern including `CAP_KILL`; this is not a workaround for broken supervision but restoration of the signal capability required by the intended cross-UID design.

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

## PH2-IAI-F6 acceptance scope

F6 should remain disposable and bounded.

Required conditions:

- networking disabled
- no external auth/model/API calls
- candidate image identity pinned before and after
- canonical launcher/profile hashes pinned before and after
- capture actual DEFAULT and COMPANION gateway states at entry and require the exact same states at exit
- private s6 supervision tree
- minimal capabilities, including proven `CAP_KILL`
- iai service runs as `hermes`

Required lifecycle evidence:

1. Start iai service.
2. Confirm s6 desired/actual up state.
3. Confirm daemon PID/UID and local socket readiness.
4. Stop iai service cleanly.
5. Confirm daemon/socket cleanup and service down state.
6. Repeat for a second complete start/stop cycle.
7. Confirm encryption-key hash is unchanged across cycles.
8. Confirm persistent store/database survive the restart cycle.
9. Confirm DEFAULT/COMPANION gateway states are unchanged from their captured entry states.
10. Confirm canonical launcher/profile hashes and candidate image identity are unchanged.

Do not reintroduce the retired post-exec `/proc/environ` verifier.

## After F6

If F6 passes, proceed to the actual Phase 2 memory-product acceptance work:

- controlled conversation capture
- persistent recall across restart
- correction/deletion semantics
- memory inspection/export
- profile isolation
- backup/restore
- fail-open behavior when iai is unavailable
- confirmation that ordinary Hermes chat continues without memory-service availability

Later phases remain gated until Phase 2 exit criteria are met.
