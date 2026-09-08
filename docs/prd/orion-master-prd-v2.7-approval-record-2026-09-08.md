# Orion Master PRD v2.7 — Approval Record

Date: 2026-09-08
Status: APPROVED / CONTROLLING
Supersedes: Orion Master PRD v2.6
Approved artifact: `Orion_Master_PRD_v2_7_AI_Optimized_Approved.docx`
Artifact SHA-256: `d8c3a92f62109b167c61b0950c02d735c8c2d1df40772097b7f6713c7d56480c`

## Approval basis

Steven directly instructed that the controlling PRD be updated now rather than waiting for a separate draft-approval round, and asked the executing AI to perform its own consistency/approval review. v2.7 is therefore the controlling Orion PRD once this review completed.

## Material changes from v2.6

- Default operator lifecycle is now **manual-off** rather than automatic Hermes/iai login startup.
- Hermes and iai Scheduled Tasks remain available, but their LogonTriggers are disabled in default manual mode. The iai task remains enabled for demand wake.
- The obsolete Docker-era `Orion Host Idle Bridge` is outside the v2.7 architecture and is to be removed from startup.
- Orion receives source-controlled one-shot **Start Orion** and **Stop Orion** desktop controls; these are operator launchers, not a resident supervisor.
- Optional persistent/always-on mode remains a reversible explicit owner choice using vendor/Windows persistence rather than a new Orion service.
- Phase 2 HUD work will integrate Start Orion and later expose a confirmed **Stop Orion** control through the same supported shutdown path.
- Native same-Windows-user process placement is explicitly not a sandbox; manual-off is also a least-exposure/resource-control policy for gaming, maintenance, or other periods when Orion is unnecessary.

## Accepted Phase 1 execution evidence incorporated

- Hermes pin: `v2026.8.27`, package `0.20.6`, commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`.
- iai-pme pin: `3.0.8`.
- iai `wake_depth=standard`.
- Hermes built-in persistent memory/user profile disabled so iai remains the sole persistent-memory authority.
- iai MCP `idle_timeout_seconds=600`; OR-LIFE-008 accepted.
- OR-LIFE-003a accepted: daemon-independent recall from true HIBERNATION with canonical pinned provenance `_source="daemon-down-full"`; older `direct-store` wording is only historical shorthand.
- OR-LIFE-003b accepted: fresh-wrapper start from true HIBERNATION reached authenticated daemon-ready in **5.887 seconds** through the Windows `iai-mcp-daemon` Scheduled Task; no `doctor --auto` fallback and no Orion supervisor.
- Accepted HIBERNATION cycles are mapped by requirement ID and must not be rerun merely to reproduce evidence already captured.

## Remaining Phase 1 closure gates

1. Apply the v2.7 manual lifecycle policy with task backups first.
2. Create and source-control the Start Orion / Stop Orion desktop launchers and shortcuts.
3. Run OR-LIFE-005 against the desired manual mode: reboot and separately logoff/logon with Orion remaining off, then manual Start/Stop acceptance plus store/database integrity and memory checks.
4. Record the OR-LIFE-007 owner disposition against the existing 5.887-second result. Current recommendation remains **ACCEPT / no additional wake patch**.
5. Close Phase 1, then begin Phase 2 typed HUD work.

## Self-review / QA

The updated DOCX was rendered to 40 pages and visually reviewed. A final consistency pass caught and corrected two stale execution-era statements: an instruction to rerun informal “Tests A/B,” and wording that still characterized Phase 1 as an exploratory native-install shakeout. The final controlling text instead treats OR-LIFE-003a/003b as accepted evidence and Phase 1 as bounded closure.

This record exists so future Orion chats can recover the controlling v2.7 decisions without relying on conversation context alone.
