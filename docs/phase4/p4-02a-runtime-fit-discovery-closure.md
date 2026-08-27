# P4-02A — Runtime-Fit Discovery Closure

**Status: PASS / CLOSED — August 27, 2026**

## Purpose

Determine the real Hermes API/dashboard network state before changing the accepted Windows + Docker runtime.

## Accepted evidence

The corrected v2 discovery run verified:

- Orion HUD workspace: `E:\Orion-Phase2\Orion-HUD`
- HUD branch: `orion-mvp`
- HUD HEAD: `aeb0643f8119a4d4f8b78a950194e9778eea4af2`
- HUD working tree: clean
- accepted Hermes/iai container: `orion-iai-m5-c`
- image: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- published Docker ports: none
- observed bridge network address during acceptance: `172.17.0.3`
- container `8642`: CLOSED
- container `9119`: CLOSED
- Windows localhost `8642`: CLOSED
- Windows localhost `9119`: CLOSED
- Windows localhost native iai Brain `4477`: OPEN
- host Python: `3.11.3`
- resolved Hermes API route: `not-listening`
- Orion HUD source layout: present

Safety markers passed:

- no config write
- no container change
- no secret output
- read-only discovery

## Interpretation

The upstream Orion HUD cannot currently reach Hermes through port `8642` because the problem is earlier than Docker port publication: Hermes API service behavior is not currently listening inside the accepted container.

Therefore P4-02B must enable/configure the Hermes API service first and only then expose the smallest safe local/container route needed by the HUD. Native iai Brain on `4477` is already independently reachable and should remain the authoritative detailed memory-management surface.

## Revision note

The first P4-02A script revision failed only in its diagnostic probe because Windows PowerShell -> Docker -> Python `-c` argument handling stripped quotes from an embedded Python string. The failure occurred in read-only diagnostics after successful Git/container checks and caused no runtime/configuration mutation.

The accepted v2 removed nested Python execution and inspected `/proc/net/tcp` and `/proc/net/tcp6` directly for Linux LISTEN state.

Canonical accepted implementation: `scripts/phase4/p4-02a-runtime-fit-discovery-v2.ps1`.

## Next

Before P4-02B modifies the accepted runtime, complete the source-preservation pass in `docs/rebuild/reproducibility-inventory.md`, especially the custom Hermes+iai image build recipe and accepted Phase 2/3 operational scripts.
