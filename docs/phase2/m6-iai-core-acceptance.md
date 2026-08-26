# Phase 2 — M6 iai Core MVP Acceptance

## Status

**PASS — iai core MVP implementation accepted on August 26, 2026.**

This closure records setup-specific acceptance of the pinned iai runtime in Orion. It does not claim that Orion reimplemented or independently revalidated iai internals. The governing implementation rule remains: use iai as the canonical MVP memory system and preserve its native semantics.

## Accepted runtime

- Container: `orion-iai-m5-c`
- Hermes: v0.20.4 / 2026.8.18
- iai: `iai-pme 3.0.8`
- iai runtime: isolated Python 3.12
- COMPANION home: `/opt/data/profiles/companion`
- Persistent iai store: `/opt/data/profiles/companion/.iai-mcp`

## Evidence accepted

### Installation and Hermes integration

`iai-mcp doctor`, executed as the actual Hermes/iai UID 10000, returned **All checks passed / exit 0**. Relevant passing checks included daemon process, socket, store lock, daemon state, Hippo readability, valid crypto key at mode `0600`, database health, embedder health, capture-state hygiene, deferred-capture backlog, RSS plateau, and AVX2 support.

The Hermes-target hook status reported all four required hooks installed and the Hermes config wired:

- `iai-mcp-session-recall.sh`
- `iai-mcp-per-turn-recall.sh`
- `iai-mcp-hermes-recall.sh`
- `iai-mcp-hermes-capture.sh`

Result: `status: ACTIVE — Hermes hooks installed and wired`.

### Persistence and recall

M5 remains controlling evidence for capture → encrypted persistent memory → container destruction/recreation → recall → automatic first-turn injection → real Discord model recall.

### Native correction

Direct iai MCP acceptance previously proved native `memory_contradict`: old record preserved, current corrector inserted, `contradicts` edge present, stale temporal validity closed, and current corrector ranked first. This establishes iai-native correction behavior in Orion without custom correction semantics.

Natural-language correction routing through Hermes is **not** part of this core iai acceptance and is deferred as Orion UX/integration work. No custom SOUL-based correction-routing layer was adopted.

### Native forgetting and rescue

One disposable memory was captured and exercised through iai-native forgetting and rescue:

- record id: `53f1bfb2-a1e7-49df-bd31-1f66d35e07a7`
- forget result: `status=queued_for_forgetting`
- rescue result: `status=rescued`
- result: `M6_FADE_RESCUE=PASS`

This accepts iai's native fade/forget-hint and rescue semantics without a custom deletion lifecycle.

### Fail-open behavior

The exact installed Hermes recall wrapper was staged without its sibling core recall script. The wrapper returned:

- `FAIL_OPEN_RC=0`
- `FAIL_OPEN_STDOUT_BYTES=0`
- `M6_FAIL_OPEN=PASS`

This matches iai's host-wrapper fail-safe contract: memory-hook failure degrades to silence rather than blocking the host model call.

### Backup and restore

The installed iai backup/restore implementation created an archive and restored it into a disposable store. The restored copy opened successfully and contained 10 records.

Accepted results:

- `RESTORED_KEY_MODE=0o600`
- `RESTORED_RECORD_COUNT=10`
- `M6_BACKUP_RESTORE=PASS`
- `IAI_CORE_ACCEPTANCE=PASS`
- `FINAL_IAI_MVP_ACCEPTANCE=PASS`

Retained host backup:

`E:\Orion-Phase2\iai-backups\brain-backup-20260826T071352Z.tar.gz`

- bytes: `55536`
- SHA-256: `cf674ce7ce9ede3975fa96ce2cdbf4b0e1af9f8e82a345c37058c440a0dea39c`

Important: iai's native backup archive includes `.crypto.key` with the memory store. This retained test artifact is therefore sensitive and is not, by itself, the final Orion production backup-policy design; Orion's separate-key backup requirement remains a higher-level security control.

### Native Brain dashboard / memory inspection

The native `iai brain` dashboard is now running for Orion and reachable from the Windows host at:

`http://127.0.0.1:4477/`

The dashboard is the upstream iai Brain surface, not an Orion replacement. It exposes the live iai store for inspection and control, including memory search, graph view, time/conversation folders, contradiction visibility, pin/fade/rescue, lifecycle state, event feed, and token-economy information.

The Docker-side bridge is transport-only so the upstream dashboard can remain loopback-bound inside its container while the Windows host reaches it through localhost. No second store or alternate memory semantics were introduced.

Result: **native iai Brain inspection surface accepted for MVP**.

### Native JSONL export

The installed iai `export_jsonl` implementation was exercised against a disposable restored snapshot of the live store so export did not contend with the running daemon/store.

Accepted results:

- `EXPORT_RECORD_COUNT=10`
- `M6_JSONL_EXPORT=PASS`
- `FINAL_MEMORY_EXPORT=PASS`

Retained host export:

`E:\Orion-Phase2\iai-exports\memory-export-20260826T081024Z.jsonl`

- bytes: `4427`
- records: `10`
- SHA-256: `16c21effa35884eeb6d444320107f36a24c33e0ef8fa518882a0a1235a7cbeb2`

This closes the MVP inspection/export acceptance item using iai-native surfaces.

## Acceptance conclusion

The Orion environment can run the pinned iai release successfully with:

- encrypted local persistent memory
- Hermes ambient capture and recall hooks
- container-recreation persistence
- native contradiction/correction
- native forgetting/fading and rescue
- fail-open host-hook behavior
- successful backup and disposable restore
- native Brain dashboard inspection
- native JSONL export

No parallel Orion memory store, custom ranking model, custom correction model, custom forgetting lifecycle, or substitute consolidation/decay system is required.

**M6 iai core MVP implementation is accepted.**

## Carry-forward items outside core iai acceptance

These remain Orion product/integration controls rather than reasons to continue re-testing iai internals:

- natural-language convenience routing for memory-control commands
- visible degraded-memory status in Orion UI/status surfaces
- supported whole-store administrative erasure workflow
- any remaining profile-isolation acceptance required by the PRD
- production backup policy that keeps encryption/recovery material separate from encrypted backup data

The project should now stop treating iai as an experimental memory candidate and proceed with Orion MVP development around the accepted iai foundation.
