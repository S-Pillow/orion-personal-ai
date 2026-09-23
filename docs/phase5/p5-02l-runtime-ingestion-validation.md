# P5-02L — COMPANION Runtime Ingestion Validation

Status: **OWNER AUTHORIZED / LIVE START-VERIFY-STOP PENDING**

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
5e1db43277b4a408d664fa68fd2ae2b3eccf761a
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
