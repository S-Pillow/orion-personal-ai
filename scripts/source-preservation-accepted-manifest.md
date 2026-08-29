# Source Preservation Manifest

Updated 2026-08-29 for **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**.

This manifest now distinguishes the current native-Windows baseline from preserved historical Docker-era artifacts.

## Current native-Windows accepted source

| Repository path | Status | SHA-256 |
| --- | --- | --- |
| `scripts/phase0/Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1` | **CURRENT / ACCEPTED PHASE 0** | `e64cdfc471754547671259e8ae09d0167dc9e8dbcf359b1effb6a1da09086e85` |

The Phase 0 script contains no API keys, Discord tokens, or iai encryption keys. It preserves Configure / Verify / Rollback logic for the accepted native Hermes baseline and never runs `hermes update`.

## Historical Docker-era accepted source

The following scripts were accepted under the previous container architecture. They remain preserved for provenance and legacy recovery, but are **not current v2.6 acceptance** unless separately revalidated.

| Repository path | Historical SHA-256 |
| --- | --- |
| `scripts/phase2/accepted/Orion-Phase2-Erase-Isolation-Closeout.ps1` | `e6d8eebcd2cecfcdbf0fc725ca047aa2a54a46e6e1e3c4607a739f90c14da77c` |
| `scripts/phase3/accepted/Orion-Phase3-Create-Vault-Retrieval-Sidecar-v2.ps1` | `b8ae39ce8c4fe9543c2e7c6f46e0cd3a9608d759d35bf9e585ceb36aa90768a1` |
| `scripts/phase3/accepted/Orion-Phase3-P3-02A-Native-Iai-Vault-Watch.ps1` | `2cc30442a6b1ed9edc914a958a46ddac6a35a76937e40d847b3246ef4c26fd69` |
| `scripts/phase3/accepted/Orion-Phase3-P3-02B-Exact-Vault-Resolver.ps1` | `96943c9c3f2b68dc59045ad554a76eba8b36d22a4fe3593c8755125dcc00f930` |
| `scripts/phase3/accepted/Orion-Phase3-P3-03-Vault-Memory-Acceptance.ps1` | `29734741bc762cdbecad1c46fdd058fcac2222f48edfe19c36e6358c712eab1a` |
| `scripts/phase3/accepted/Orion-Phase3-P3-04-Create-Inbox-Draft.ps1` | `5abbd20c4582d482ae9ce2608b833b30a9dd8cabe64e61f2b5518089bb0e94f3` |
| `scripts/phase3/accepted/Orion-Phase3-P3-04-Provision-Dedicated-Inbox-v3.ps1` | `7c5641287725feb825dab2cbef3e0609e101192b18162dbb52a2209f44515dae` |
| `scripts/phase3/accepted/Orion-Phase3-P3-05-Controlled-Vault-Broker-v2.ps1` | `cb37b0b4991ac3e3a0fe3d20b507a43d772edcaee80dba0ab2a187ad5c789582` |
| `scripts/phase3/accepted/Orion-Phase3-P3-05-Provision-And-Accept-Controlled-Broker-v3.ps1` | `a8fae507cc53d26d20cdecd16a6f217acbe5b57767302345d99d34dd444c4c1d` |
| `scripts/phase3/accepted/Orion-Phase3-P3-06-Vault-Destination-Recommender.ps1` | `96fa3b6030100e1592a9f7ae60a08acaf2545ebc3e6fb138637a43a5cae0fdbb` |
| `scripts/phase3/accepted/Orion-Phase3-P3-06-Vault-Destination-Recommender-Acceptance.ps1` | `e16bd6e3aaf4f0aed352521a161215316c656c03407fb55d347d1f5b7ad9cf2a` |

## Phase 1 source status

No Orion Phase 1 compatibility patch is accepted yet.

Current stock `iai-pme==3.0.8` Windows daemon startup is blocked by an unguarded `signal.SIGHUP` reference. If Orion authorizes and accepts a compatibility patch, the patch must be preserved in `S-Pillow/iai-personal-memory-engine`, and any Orion-owned setup/verification/rollback script must be added here before Phase 1 closure.

This manifest preserves source identity only. Secrets, vault content, memory data, `.env` contents, iai encryption keys, and private runtime state are not stored in the repository.
