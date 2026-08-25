# M5 — Persistent Memory Recall Closure

## Status

**PASS / CORE ACCEPTANCE COMPLETE**

Accepted on August 25, 2026 after a real fresh-session Discord DM test returned the persisted marker `topaz-6842` after container destruction/recreation.

## Acceptance scope

M5 proves the required end-to-end path:

**capture → persistent encrypted memory → container destruction/recreation → iai recall → automatic first-turn injection → real fresh-session Discord model recall**

This is the Phase 2 memory-foundation acceptance point for persistence and automatic recall across container recreation. It does not by itself close the remaining Phase 2 work for correction/deletion, export/inspection, backup/restore, profile isolation, or fail-open behavior.

## Pinned runtime

- Container: `orion-iai-m5-c`
- Container ID: `ea9fb7afbe6b394373390310a94bcacb21470388d1310a9305c7ef9e6a97b2d7`
- Image ID: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`
- Persistent volume: `orion-iai-m5-data`
- Persistent mount: `/opt/data`
- Hermes Agent: `v0.20.4 (2026.8.18)`
- Hermes runtime Python: `3.13.5`
- iai distribution: `iai-pme 3.0.8`
- iai isolated runtime: Python 3.12
- Live Hermes-wire recall wrapper SHA-256: `efce3f7be7e5835ca18fcbbb655c9764f83ec48acb28fb307683aa0cc56d4548`

## Evidence chain

The accepted run established all of the following:

1. The marker `topaz-6842` was captured before restart/recreation.
2. The encrypted iai memory store and crypto material remained on the persistent `orion-iai-m5-data` volume.
3. The previous disposable container was removed and container C was created from the corrected image using the same persistent volume.
4. COMPANION configuration, `.env`, SOUL, crypto key, Hermes state, and the Hermes-wire overlay survived container recreation.
5. iai semantic recall after recreation returned `topaz-6842`.
6. The corrected `session_start_payload` contained the memory.
7. Hermes' native `pre_llm_call` contract accepted recalled text through its `context` field.
8. Installed Hermes source confirmed `pre_llm_call` context is composed into the API-bound current user message.
9. The corrected Discord gateway remained connected and stable.
10. A real Discord DM session was reset with `/new`.
11. The first acceptance prompt was: `What is the M5 vault code? Reply with only the code.`
12. Orion replied exactly: `topaz-6842`.

## Serializer defect discovered during M5

A real upstream integration defect was found in `iai-pme 3.0.8`.

`SessionStartPayload.recent_thread` was populated by session assembly but omitted by the core serializer used for `session_start_payload` dispatch. Direct assembly could therefore look correct while the dispatched JSON lost the recent-thread memory needed by ambient Hermes recall.

The Orion compatibility fix added the missing serializer field:

```python
"recent_thread": getattr(payload, "recent_thread", ""),
```

The corrected image passed both serializer-contract checks and the final real Discord acceptance.

Upstream report:

- `CodeAbra/iai-personal-memory-engine#156` — **session_start_payload serializer drops recent_thread**
- https://github.com/CodeAbra/iai-personal-memory-engine/issues/156

The issue was also confirmed against current upstream source at the time of reporting: `_payload_to_json()` still did not serialize `recent_thread`.

## Invalid acceptance attempts during diagnosis

Two apparent failures must not be treated as product failures:

1. One vault-code question was entered directly into Hermes rather than through the intended Discord DM gateway path.
2. A later Discord attempt was sent in `#daily-briefing` instead of the active Hermes DM conversation.

Those attempts triggered unnecessary forensic work but did not exercise the accepted M5 path.

A suspected `state.db` persistence defect raised during that investigation is **not established** and is not carried forward as an Orion defect unless it reproduces independently during valid Discord DM use.

## Closure classification

```text
M5_STATE=PASS
M5_CORE_ACCEPTANCE=COMPLETE
```

## Preservation / cleanup

Until the retained local closure artifact and rollback references are safely preserved:

- do not delete `orion-iai-m5-data`
- do not remove `orion-iai-m5-c`
- do not revert the serializer/Hermes-wire compatibility fix

Cleanup of disposable M5 resources should be a separate explicit unit after evidence retention.
