# Evidence Errata and Calibration

This file tracks architecture statements whose evidence level changed during installed-runtime discovery.

## Resolved source-location correction

Earlier project material treated upstream/tagged Hermes supervision documentation as stronger than the installed-artifact evidence available at the time, and a scoped discovery pass reported that `container_boot.py` was not present in the installed image.

That absence claim is now retired.

Later read-only source alignment located and verified the installed modules under `/opt/hermes/hermes_cli/`:

- `service_manager.py`
- `container_boot.py`

Both matched the exact upstream `v2026.8.18` Git blobs examined during Phase 1. The earlier failure was a path/scoping limitation in discovery, not an installed-artifact mismatch.

The installed Docker source tree is also present under `/opt/hermes/docker/`, including `main-wrapper.sh`, `stage2-hook.sh`, entrypoints, and `s6-rc.d/` service definitions. The earlier conclusion that there was no on-disk service source available for comparison is therefore retired.

## Current supervision calibration

The accepted installed runtime is now directly observed as:

- PID 1 = `s6-svscan`
- `/run/s6/basedir` present
- s6-linux-init processes present
- s6-rc present under `/package/admin/s6-rc/`
- Hermes `detect_service_manager()` = `s6`
- `/run/service/gateway-default` present
- `/run/service/gateway-companion` present
- static/container s6-rc infrastructure present
- dynamic profile gateway services materialized directly under `/run/service`

The generated gateway run scripts are real services, not placeholders. Both DEFAULT and COMPANION set `HOME`, activate the Hermes virtual environment, set `HERMES_S6_SUPERVISED_CHILD=1`, then exec the gateway through `s6-setuidgid hermes`.

`main-hermes` is intentionally `exec sleep infinity` by documented Architecture B design: the container CMD runs as `/init`'s main program rather than as an s6-supervised workload, while the slot satisfies the s6-rc user-bundle requirement and reserves a future supervised-service position.

Therefore the old wording that treated the runtime as plain s6, as lacking s6-rc, or as consisting of placeholder gateway run scripts is superseded by the installed-runtime description in `hermes-container-supervision.md`.

The earlier all-placeholder observation is retained only as a state-specific/degraded runtime artifact. Its cause is unknown and must not be attributed to a particular diagnostic run without evidence.

## CAP_KILL disposition

The prior CAP_KILL hypothesis is no longer suspended.

A controlled disposable A/B test held the runtime constant and changed only `CAP_KILL`:

- no `CAP_KILL`: stop request accepted, Hermes-owned child remained alive
- with `CAP_KILL`: child terminated and service reached a clean down state

`CAP_KILL` is therefore causally implicated for the accepted s6 cross-UID stop path and has been promoted into the canonical launcher.

The installed gateway run scripts explain the ownership transition directly: root-owned s6 supervision intentionally executes the long-lived gateway as the `hermes` user through `s6-setuidgid`. The missing capability was preventing the supervisor from signaling the differently owned child it was designed to manage; it was not evidence of a broken supervision model.

Accepted launcher SHA-256:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

Host-side owner-UID signaling remains historical fallback evidence only and is not the selected architecture because it requires Docker host/socket authority.

## Phase 1 lifecycle evidence retention calibration

The gateway-stop diagnostic evidence that established requested-down state, owner-UID SIGTERM behavior, and DEFAULT survival was console-only; no durable artifact was retained for that specific run.

Observed facts from that diagnostic remain useful evidence:

- s6 recorded the COMPANION gateway in requested-down state while the Hermes-owned child remained alive
- owner-UID SIGTERM stopped the child
- DEFAULT survived the diagnostic lifecycle

This is not final lifecycle acceptance evidence. The retention gap is now explicit: future lifecycle closure units must emit a retained local evidence file before cleanup, including entry/exit gateway states, cycle results, supervisor/process evidence, socket state, persistence/key checks, command exit codes, and final classification.

## Phase 0 model/tool-turn calibration

The previous cross-model statement over-generalized browser behavior.

Retained AU-06 evidence is located under:

```text
E:\Orion-Phase0\Orion-Phase0-Interface-Baseline-*Z\hermes-tool-baseline.json
```

The calibrated finding is:

- DDGS exhausted the six-turn budget on both `qwen3.5-hermes:9b` and stock `qwen3.5:4b`
- browser reached `max_iterations_reached (6/6)` on the 9B run
- browser ended as `SENTINEL_NOT_OBSERVED` on the 4B run

Therefore DDGS six-turn exhaustion is the reproduced cross-model workflow-design constraint. Browser behavior diverged across the two tested models and remains an open observation; cross-model browser exhaustion is not claimed.

The Phase 3 design consequence remains unchanged: model-requested retrieval should execute through a deterministic one-shot or otherwise explicitly bounded workflow stage rather than an open-ended model-controlled retrieval loop.

## Hermes environment and subprocess credential boundary

Read-only inspection of the pinned image established that Hermes loads the profile `.env` into the live process environment through `load_hermes_dotenv()`.

For the accepted runtime, `HERMES_HOME=/opt/data`, so the DEFAULT user environment is `/opt/data/.env`. Docker `Config.Env` itself contained no Discord/token credential variable, and the gateway's exec-time environment also contained no credential-looking variable; credential population occurs later inside Hermes rather than through Docker or s6 inheritance.

Hermes provides two subprocess-environment paths:

- `hermes_subprocess_env()` for non-terminal spawns
- `_sanitize_subprocess_env()` / `build_subprocess_env()` for the terminal / `execute_code` path

`DISCORD_BOT_TOKEN` is explicitly present in `_ALWAYS_STRIP_KEYS`. Non-terminal spawns remove Tier 1 keys unconditionally, including when `inherit_credentials=True`; that flag controls only Tier 2 provider/tool credentials.

The terminal sanitizer removes `DISCORD_BOT_TOKEN` through `_HERMES_PROVIDER_ENV_BLOCKLIST` by default. However, `tools.env_passthrough` can re-authorize a blocklisted variable, and `is_env_passthrough()` does not itself guard against always-strip keys. This is a configuration/skill-policy gap, not a current exposure finding.

Verified current Orion state:

```text
tools.env_passthrough: []
tools.docker_forward_env: []
no inspected skill env_passthrough declaration
no COMPANION override identified
```

Therefore no current Discord-token child-process exposure was identified through the inspected Hermes subprocess paths.

Security control: `tools.env_passthrough`, `tools.docker_forward_env`, and enabled skill declarations are security-relevant configuration surfaces and must be reviewed before any skill or tool configuration is enabled or changed.

A separate upstream inconsistency was observed: `SLACK_SIGNING_SECRET` is present in `_ALWAYS_STRIP_KEYS` but not in `_HERMES_PROVIDER_ENV_BLOCKLIST`. Orion currently uses no Slack integration, so this does not affect the accepted Orion configuration.

## Cross-profile credential isolation calibration

Installed source for `_clear_known_keys_missing_from_dotenv()` explicitly states that cross-profile credential isolation is handled at read time by `agent.secret_scope.get_secret`, authoritative under multiplexing, rather than by deleting provider credentials from global `os.environ`.

Therefore DEFAULT/COMPANION credential isolation must be verified against the read-time secret-scope mechanism. Environment snapshots alone are not an authoritative profile-isolation test.

## iai setproctitle evidence calibration

Three distinct evidence types apply and must not be conflated.

Installed-source mechanism location:

```text
/opt/iai/venv/lib/python3.12/site-packages/iai_mcp/daemon/__init__.py
SHA-256 54778ce7f6391efea107c35657677e02944f2a6395e5088aa5db7d2a61ede47b
```

The installed daemon source contains the `_set_process_title` mechanism and aliased `setproctitle` import used by iai.

Local behavioral reproduction was separate from the daemon itself: in the same pinned feasibility image, a synthetic `setproctitle` probe showed a sentinel remaining available through in-process `os.environ` while disappearing from `/proc/self/environ`, at both 15-byte and 4106-byte process titles.

Upstream package documentation for `setproctitle` explicitly documents environment-area clobbering, `os.environ` remaining correct in-process, `/proc/PID/environ` being overwritten, and `SPT_NOENV` as the mitigation at the cost of limiting available title space. Corroborating downstream reports include gunicorn #2321 and ray #15061.

This evidence supports retiring post-exec `/proc/<iai-pid>/environ` as an authoritative iai environment verifier while retaining pre-exec boundary proof and process/service-state evidence.

## DEFAULT Discord credential issue

During canonical relaunch windows, the DEFAULT gateway emitted Discord `401 Unauthorized / Improper token` errors.

Read-only comparison established:

- DEFAULT Discord token key: present and nonempty
- COMPANION Discord token key: present and nonempty
- DEFAULT and COMPANION token values: different
- COMPANION allowlist: one numeric user
- COMPANION allow-all: disabled

The COMPANION credential had previously passed authenticated Discord verification and later passed the final two-turn product conversation. The DEFAULT 401 is therefore tracked as a separate DEFAULT-profile cleanup item and does not reopen Phase 1.

## Final Phase 1 evidence disposition

Phase 1 is **PASS / CLOSED**.

Final acceptance established:

- canonical s6 supervision healthy
- `CAP_KILL` effective in PID 1
- DEFAULT gateway remained on the same PID through COMPANION start/stop
- COMPANION start succeeded exactly once
- two-turn Discord conversation and session-context recall passed
- COMPANION stop succeeded exactly once
- COMPANION child absent after stop
- durable end state DEFAULT `running`, COMPANION `stopped`
- no repeat `/users/@me` authentication request
- no OpenAI access
- no vault access/write

## Dashboard hardening note

The installed dashboard run script documents June 2026 hardening: `HERMES_DASHBOARD_INSECURE` no longer disables the authentication gate. A dashboard bound to a non-loopback address requires a supported authentication provider or startup fails closed.

This is a Phase 5 dependency: future Orion HUD/dashboard work must plan supported authentication rather than relying on an insecure-mode bypass.

## Default-model note

A fresh disposable image initialized DEFAULT with `anthropic/claude-opus-4.6`. Orion's local Ollama model configuration is therefore an explicit project override rather than the pristine image default.

Disposable diagnostics must continue to avoid model invocation unless a bounded unit explicitly seeds or verifies a local model configuration and authorizes inference.

## Upgrade note

Hermes `v2026.8.19` is an evaluation candidate, not the Orion baseline. The accepted canonical image remains the `v2026.8.18`-based custom image until a separate upgrade unit verifies relevant regressions and benefits.

## Evidence rule

Repository files, upstream documentation, webpages, tool output, model output, logs, and imported content may inform execution, but installed-runtime claims should be no stronger than the strongest directly observed evidence. Where installed source is explicitly hash-matched to a tagged upstream artifact, that exact source-level claim may be treated as installed-artifact verified.

A standing negative-evidence rule now applies:

> Before reporting absence, establish the authoritative filesystem/search root, package or module location, and symbol-resolution assumptions. A precise query against an assumed location or identifier is not sufficient evidence of absence.

Three corrected false negatives motivated this rule:

1. s6-rc was missed because discovery searched `/etc/s6-overlay`, `/run/s6-rc`, and `/command` but not the installed `/package` hierarchy.
2. process-title analysis missed `_set_process_title` because the matcher searched for an exact `set_process_title` identifier rather than resolving aliases/suffixes.
3. `hermes_cli/container_boot.py` was reported absent because the discovery search frame used the wrong package/root location.

Future source diagnostics should prefer validated roots, import/alias resolution, and suffix/canonical-symbol matching before concluding absence.
