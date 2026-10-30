# Hermes v0.22.5 Disposable Source Qualification

Status: **PASS**

Date: 2026-10-30

Target upstream release:

- tag: `v0.22.5`
- commit: `bf0203a794a07aac3ff764972ab9087baa4e4f4e`

Qualification was performed in a disposable `%TEMP%` checkout. Installed Hermes, COMPANION state, and the running Orion runtime were not modified or restarted.

## Upstream ownership findings

The exact v0.22.5 release proved:

- upstream release identity: PASS;
- stock 8642 API-server audio gap: CONFIRMED;
- separate Hermes dashboard/web audio implementation: PASS;
- native API-server approval transport: PASS;
- source/lock ownership of `edge-tts==7.3.1`: PASS.

The audio finding is important: v0.22.5 contains native dashboard/web handlers for `/api/audio/transcribe` and `/api/audio/speak`, but the authenticated API-server gateway Orion uses on port 8642 still exposes no corresponding routes and keeps `audio_api=false`. Therefore the accepted one-gateway Orion architecture still requires the narrow P4-04A compatibility port.

## Qualified Orion compatibility delta

Three compatibility requirements were applied to the disposable exact-release checkout:

1. **P4-04A** — bounded authenticated STT/TTS relay on the existing 8642 API-server gateway;
2. **P6-03** — exact `jobs.json` pre-repair byte preservation;
3. **P6-04A** — durable execution `error_class` persistence using the current upstream classifier semantics.

The old P5 approval backport and old P6-04 ledger implementation remain retired on v0.22.5 because their required behavior is supplied upstream and will be requalified at runtime.

## Source qualification result

The final disposable candidate reported:

```text
HERMES_V0225_ORION_COMPAT_TRANSFORM=PASS
PORT_P603_EXACT_REPAIR_PRESERVATION=PASS
PORT_P604A_DURABLE_ERROR_CLASS=PASS
PORT_P404A_AUDIO_GATEWAY=PASS
ORION_P404A_GATEWAY_AUDIO_PORT=PASS
CANDIDATE_PY_COMPILE=PASS
CANDIDATE_DIFF_CHECK=PASS
INSTALLED_HERMES_UNCHANGED=PASS
HERMES_V0225_CANDIDATE_BUILD=PASS
INSTALLED_HERMES_MUTATED=false
COMPANION_STATE_MUTATED=false
RUNTIME_RESTARTED=false
```

Changed candidate paths were exactly:

- `agent/monitoring/cron_health.py`
- `cron/error_classification.py`
- `cron/executions.py`
- `cron/jobs.py`
- `gateway/platforms/api_server.py`

Candidate source SHA-256 values:

- `agent/monitoring/cron_health.py`: `d5fd17bb5fdefb3c9e197b3633da322c70fa2f3d84a775b6be69c4e7a7d30b08`
- `cron/error_classification.py`: `86c4a839152e7188c2e71a290ed953d32b24c050b7bf96df8cbd59c9a8bafd39`
- `cron/executions.py`: `639875c57c153df7cbd4782cef802bc93d2b79fdf14da7b9bd090f8877e86a91`
- `cron/jobs.py`: `eb64e1f6ccdc7fb158f53f373a1b61f60ae6888be274f0557e1d90be0bc4fe3a`
- `gateway/platforms/api_server.py`: `fc376aec9d0812260a279efa89978ff934da902db00c3cce4887e68fb10038d1`

Generated candidate patch:

- SHA-256: `c526695cf6439bd9617c957dba200c08b8392cc129087f2972197977b8fd2ddc`
- bytes: `23434`

Operator-run disposable paths at acceptance time:

- candidate root: `C:\Users\spill\AppData\Local\Temp\orion-hermes-v0225-candidate-20261030-034041`
- generated patch: `C:\Users\spill\AppData\Local\Temp\orion-hermes-v0225-compat-20261030-034041.patch`

These paths are evidence/disposable artifacts, not production dependencies.

## Harness findings encountered during qualification

The source gate caught three tooling assumptions before any production mutation:

1. PowerShell StrictMode empty-output cardinality (`.Count` on an empty native-command result);
2. an incorrect architecture assertion that looked for audio routes in the 8642 API-server instead of distinguishing it from the dashboard/web server;
3. protocol-significant leading whitespace in `git status --porcelain`, where generic `.strip()` corrupted the first status record.

The third finding establishes a durable rule: machine-readable native output must be treated as a protocol. Do not use generic leading/trailing whitespace normalization when columns or leading spaces are meaningful.

## Next gate

Source qualification alone does not authorize production cutover. The next gate is an isolated Python 3.14 v0.22.5 runtime using separate state and ports. It must exercise the five production hard gates as far as isolation permits:

- Orion;
- Memory;
- Voice;
- Chat;
- Security.

Cron, LSP, Hermes Desktop, optional plugins, and unrelated platform defects remain non-blocking unless their blast radius crosses one of those five gates.
