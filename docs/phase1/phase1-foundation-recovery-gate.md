# Phase 1 Foundation Recovery Gate

Status: **PLANNED / REQUIRED BEFORE PHASE 2 HANDOFF**

This gate adds an early recoverability check after Phase 1. It does not replace the full final-system recovery drill planned for Phase 7.

## Purpose

Verify that Orion's preserved source artifacts are sufficient to recreate the accepted Phase 0 + Phase 1 foundation without relying on undocumented machine state.

The check exists to validate the source-preservation requirement, not merely the live runtime.

## Required evidence

The recovery check must demonstrate that the documented/source-controlled materials identify and can recreate the accepted foundation, including:

- pinned Hermes release/tag/package/commit and named profile `companion`;
- pinned `iai-pme` version and native Windows Python environment expectations;
- accepted narrow Windows compatibility fixes/adapters;
- Hermes memory configuration with built-in file memory disabled;
- iai wake-depth and MCP idle-timeout configuration;
- source-pinned Hermes recall/capture adapters and the gateway-restart-after-hook-change rule;
- manual-off Windows lifecycle configuration, including retained vendor Scheduled Tasks with LogonTriggers disabled;
- source-controlled one-shot Start/Stop operator controls once OR-LIFE-005 closes;
- Ollama provider/model/configuration requirements and ownership-aware startup policy;
- persistent iai store location and preservation expectations;
- all required backup/restore or configuration-record locations needed to reproduce the accepted state.

## Acceptance approach

A full destructive rebuild of Steven's primary machine is not required for this early gate. Acceptable evidence may include a clean-room checklist/dry-run plus isolated reconstruction where practical, provided every material dependency, compatibility change, configuration value, and source artifact has a durable source and an explicit restoration step.

Any step that depends on an undocumented manual edit, ephemeral file, forgotten local state, secret copied into source, or unpinned dependency is a failure of this gate and must be corrected before Phase 2 handoff.

The final Phase 7 recovery drill remains responsible for proving end-to-end recovery of the completed Orion system.

Core Intent Preservation: **PRESERVED**.
