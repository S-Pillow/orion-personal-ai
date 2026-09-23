# P5-02L — COMPANION Runtime Ingestion Validation

Status: **OWNER AUTHORIZED / FIRST LIVE ATTEMPT SAFE-STOPPED / READ-ONLY DIAGNOSIS PENDING**

Branch:

```text
feature/orion-phase5-p5-02l-runtime-ingestion
```

Depends on:

- P5-02K recovery-root persistence — complete;
- persisted production recovery root:
  `C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery`;
- installed Orion plugin hash:
  `FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA`;
- COMPANION config hash:
  `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- accepted Hermes source commit:
  `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- accepted P4-04A patched API-server hash:
  `ECFD6DD53610C24A81F078650A0B2B3E129478A50FDB5F353313FFF6E12E3888`.

## Owner authorization

Owner explicitly authorized the next runtime-ingestion gate: start COMPANION,
verify that the persisted production recovery-root setting is ingested while
production mutation remains disabled and registered apply remains fail-closed,
then stop COMPANION and return to manual-off.

This authorization covers the minimum Hermes lifecycle required for that gate.

It does not authorize:

- `ORION_P5_MUTATION_MODE=mutation_enabled`;
- any mutation-mode persistence;
- production executor registration;
- real vault/inbox mutation;
- production recovery transaction creation;
- vault/inbox ACL changes;
- Hermes/Ollama/iai upgrades;
- merge/deploy.

P5-02L intentionally controls **Hermes only**. It does not start or stop Ollama.
The separate desired Orion/Ollama lifecycle policy remains a dedicated follow-up.

## Hermes runtime-ingestion source contract

The accepted Hermes source at
`5fc308a70719a83cccdbba4c0e39c23f5a8239d5` establishes the startup contract
used by this gate:

- `hermes -p companion ...` resolves the COMPANION profile before later
  Hermes module imports;
- `hermes_cli.main` calls `load_hermes_dotenv(...)` before subcommand
  dispatch;
- `load_hermes_dotenv()` selects `<HERMES_HOME>\.env`;
- when that file exists it calls the Hermes dotenv loader with
  `override=True`;
- therefore the persisted COMPANION recovery-root assignment is loaded into
  the effective process environment before gateway dispatch.

P5-02L also performs a live read-only verifier while the gateway is healthy.
That verifier uses the same Hermes dotenv loader, requires the effective
recovery-root value to match P5-02J/P5-02K, and confirms:

- production mode resolves to `disabled`;
- `mutation_allowed=false`;
- native production-root validation passes;
- recovery inventory remains empty;
- registered apply remains `apply_plan_placeholder` and fail-closed;
- live authenticated `GET /v1/toolsets` contains exactly one enabled and
  configured `orion_vault` toolset with the expected four tools.

No API key or `.env` contents are printed.

## Prepared operator artifacts

Prepared source pin:

```text
bacd831a9d6935bd619c18cf8f17cbe174b2fd53
scripts/phase5/p5-02l-runtime-ingestion-gate.ps1
scripts/phase5/p5-02l-runtime-ingestion-verify.py
```

The gate requires:

```text
I_AUTHORIZE_P5_02L_RUNTIME_INGESTION
```

The operator script:

1. requires a manual-off baseline;
2. verifies accepted config/plugin/Hermes/P4-04A hashes;
3. verifies exactly one persisted recovery-root assignment and no persisted
   production mutation/disposable flags;
4. verifies the production recovery root is empty;
5. starts only `hermes -p companion gateway start`;
6. waits for gateway health;
7. runs the read-only runtime verifier;
8. stops Hermes in a `finally` path even when verification fails after start;
9. verifies health is down;
10. verifies config, `.env`, plugin, and P4-04A patch bytes are unchanged;
11. verifies no production recovery record appeared.

## Acceptance markers

A successful run must include:

```text
P5_02L_PERSISTED_RECOVERY_ROOT_PRECHECK=PASS
P5_02L_MUTATION_MODE_PERSISTED=false
P5_02L_DISPOSABLE_FLAGS_PERSISTED=false
P5_02L_HERMES_SOURCE_PIN_MATCH=true
P5_02L_P4_04A_PATCH_MATCH=true
P5_02L_GATEWAY_HEALTHY=true
P5_02L_HERMES_DOTENV_LOADED=true
P5_02L_EFFECTIVE_RECOVERY_ROOT_MATCH=true
PRODUCTION_MUTATION_MODE=disabled
PRODUCTION_MUTATION_ALLOWED=false
P5_02L_NATIVE_ROOT_VALIDATION=PASS
P5_02L_RECOVERY_INVENTORY_COUNT=0
P5_02L_RECOVERY_ATTENTION_COUNT=0
P5_02L_REGISTERED_APPLY_FAIL_CLOSED=true
P5_02L_LIVE_ORION_TOOLSET_FOUND=true
P5_02L_LIVE_ORION_TOOL_COUNT=4
P5_02L_RUNTIME_INGESTION=PASS
P5_02L_GATEWAY_STOPPED=true
P5_02L_CONFIG_UNCHANGED=true
P5_02L_ENV_UNCHANGED=true
P5_02L_PLUGIN_UNCHANGED=true
P5_02L_RECOVERY_ROOT_STILL_EMPTY=true
P5_02L_MUTATION_INVOCATION=false
HERMES_MANUAL_OFF=true
P5_02L_RUNTIME_INGESTION_LIFECYCLE=PASS
```

## First live attempt — SAFE STARTUP-READINESS STOP

The first authorized live P5-02L invocation passed all pre-start checks and
spawned a COMPANION gateway process, but the health endpoint did not become
reachable within the 30-second gate window.

Observed:

```text
P5_02L_PERSISTED_RECOVERY_ROOT_PRECHECK=PASS
P5_02L_MUTATION_MODE_PERSISTED=false
P5_02L_DISPOSABLE_FLAGS_PERSISTED=false
P5_02L_HERMES_SOURCE_PIN_MATCH=true
P5_02L_P4_04A_PATCH_MATCH=true
Gateway started via direct spawn
P5_02L_GATEWAY_STOPPED=true
P5_02L_CHILD_EXIT_CODE=1
```

The runtime-ingestion verifier was never reached. Therefore this result does
**not** establish that the persisted recovery-root setting failed ingestion.
It establishes only that the direct Hermes-only lifecycle used by this gate did
not reach the accepted HTTP health surface in time.

The `finally` shutdown path ran and Hermes reported the gateway stopped. No
mutation invocation occurred.

The temporary operator worktree was subsequently removed by the operator even
though the failure wrapper requested preservation.

Before any retry, classify the existing startup evidence read-only.

Prepared read-only diagnostic:

```text
42d96757e2bb8be48bafc0a51ee1049f8b5249a8
scripts/phase5/p5-02l-readonly-failure-diagnostics.py
```

The diagnostic:

- does not start or stop Hermes;
- does not mutate COMPANION files;
- compares the current `.env` hash to the P5-02K accepted post-write hash;
- confirms recovery-root assignment cardinality/value without printing the
  full `.env`;
- confirms forbidden mutation/disposable settings remain absent;
- confirms the recovery root is still empty;
- prints config/plugin hashes;
- emits only recent log lines matching startup/error-related terms;
- redacts bearer tokens and common key/token/secret/password assignments before
  printing.

A retry is blocked until the read-only evidence explains or narrows the health
failure.

## Read-only diagnosis — STARTUP LATENCY CLASSIFIED

The read-only diagnostic completed successfully and preserved the accepted
P5-02K state.

Observed persistent state:

- current COMPANION `.env` SHA-256 exactly matched the accepted P5-02K
  post-write SHA-256;
- exactly one production recovery-root assignment existed;
- the persisted recovery-root value matched the accepted P5-02J path;
- no forbidden production-mutation/disposable settings were persisted;
- the production recovery root remained empty;
- accepted config and installed-plugin hashes remained unchanged.

Observed startup timing:

- detached gateway process start was recorded at approximately 00:39:24 local;
- control pipe was listening by approximately 00:39:25;
- Hermes did not log `Starting Hermes Gateway...` until approximately
  00:40:28;
- immediately before that transition, MCP startup logged a failed connection to
  `iai-mcp` with `CancelledError`;
- the API server began listening on `127.0.0.1:8642` at approximately
  00:40:28.5.

Therefore the first P5-02L gate's 30-second HTTP-health timeout expired while
Hermes was still in pre-platform startup. The gateway later reached the API
listen point after roughly 64 seconds of process lifetime.

Classification:

```text
P5_02L_FIRST_ATTEMPT=SAFE_FALSE_TIMEOUT
P5_02L_PERSISTED_STATE_INTACT=true
P5_02L_RUNTIME_INGESTION_RESULT=NOT_YET_REACHED
```

The evidence does not implicate Ollama. The API server reached its listen point
without P5-02L starting Ollama.

Source correction:

```text
bacd831a9d6935bd619c18cf8f17cbe174b2fd53
```

The correction changes only the bounded gateway-health readiness window:

- previous: 30 seconds;
- corrected: 150 seconds.

The wider window remains bounded and is intended to cover the accepted Hermes
runtime's MCP-delayed startup path. No authorization scope is widened and no
mutation behavior changes.

The existing P5-02L lifecycle authorization remains applicable to retry this
same start-verify-stop gate against the corrected source.

## Stop conditions

Stop/fail closed if:

- Hermes is already running before the gate;
- persisted recovery-root assignment is missing, duplicated, or mismatched;
- mutation/disposable settings are persisted or ambient;
- recovery root is non-empty;
- accepted hashes/source pin do not match;
- gateway fails to start or become healthy;
- Hermes dotenv loader does not report COMPANION `.env` loaded;
- effective recovery root differs from the accepted path;
- production mode is anything except disabled;
- native root/inventory validation fails;
- live Orion toolset is missing/misconfigured;
- public apply no longer fails closed;
- any persistent file changes during start/stop;
- recovery data appears unexpectedly;
- gateway cannot be returned to manual-off.

No mutation call is permitted as a diagnostic.

## Next gate

If P5-02L passes, recovery-root persistence will be runtime-qualified while
production mutation remains disabled.

Any later step that enables production mutation or wires the private production
executor into the registered apply surface is a separate, higher-risk
authorization unit.
