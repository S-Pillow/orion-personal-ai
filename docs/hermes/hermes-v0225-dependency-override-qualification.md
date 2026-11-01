# Hermes v0.22.5 Dependency Override Qualification

Status: **IN PROGRESS — isolated runtime environment**

Date: 2026-10-30

## Observed result

The exact v0.22.5 isolated Windows environment was successfully created with the release-pinned toolchain and lock:

- CPython `3.14.9` from the exact `pm/lock.json` artifact;
- uv `0.13.5` from the exact `pm/lock.json` artifact;
- `uv sync --locked` completed successfully;
- 130 packages installed;
- `edge-tts==7.3.1` installed;
- initial Hermes import qualification passed.

A raw `uv pip check` then returned one incompatibility:

- `browser-harness==0.1.13` declares `pillow==12.3.0`;
- the v0.22.5 environment installs `Pillow==13.0.0`.

The environment gate stopped before any isolated gateway launch. Production Hermes, COMPANION state, and Orion runtime were not changed.

## Upstream disposition

This mismatch is deliberate in Hermes v0.22.5 rather than accidental lock drift.

The exact release `pyproject.toml` records that `browser-harness==0.1.13` still pins Pillow 12.3.0, while Hermes intentionally overrides that requirement to `Pillow==13.0.0` because Pillow 13 is the security-fixed line for the advisory set cited by upstream. The release explicitly states that PM's install-time validation must interpret the resulting raw metadata mismatch through `uv.lock`'s `[manifest] overrides` rather than treating the raw `uv pip check` exit code as failure.

The exact v0.22.5 implementation in `pm/pip_check.py` and `pm/environment.py` provides that lock-aware behavior: an incompatibility is accepted only when the lock records the dependency as overridden and the installed version equals a locked override version; any unexplained mismatch remains a hard dependency-validation failure.

Therefore Orion must **not** downgrade Pillow to 12.3.0 merely to make raw `uv pip check` return zero. Doing so would undo a deliberate upstream security decision and violate Orion's Security hard gate.

## Orion qualification rule

For exact Hermes v0.22.5 dependency qualification:

1. raw `uv pip check` output is still collected as evidence;
2. the report is evaluated with the exact release's `pm.pip_check.unexpected_incompatibilities()` against the candidate `uv.lock`;
3. qualification passes only when the unexpected incompatibility set is empty;
4. the current candidate additionally requires the sole raw mismatch to be the reviewed `browser-harness` / Pillow override;
5. `Pillow==13.0.0`, `browser-harness==0.1.13`, and `edge-tts==7.3.1` identities must be proven;
6. imports and a bounded Pillow API smoke must pass;
7. any additional raw mismatch, parse ambiguity, version drift, or import/API failure is a stop condition.

This keeps the Security hard gate intact while matching the dependency semantics Hermes v0.22.5 itself is designed to use.

## Related upstream reports

- Hermes issue #143313 documents the raw metadata conflict and confirms lock-based uv installs are the supported path.
- Hermes issue #144110 reports a PM override-validation failure on a carried v0.21.5 environment. Exact v0.22.5 contains the lock-aware checker described above, so Orion will qualify that exact implementation directly rather than infer applicability from the older carried environment.

No production cutover is authorized by this finding.
