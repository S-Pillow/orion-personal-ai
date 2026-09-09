# Orion v2.7.4 candidate — Hermes clean pin checkpoint

Date: 2026-09-08
Branch: feature/orion-start-v272-lifecycle-safety

Status: PASS for Hermes source cleanliness/pin classification.

Observed on Windows host before rerunning candidate preflight:

- Hermes source root: `C:\Users\spill\AppData\Local\hermes\hermes-agent`
- HEAD: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- HEAD matches approved pin: yes
- `git status --short --branch`: `## HEAD (no branch)` with no tracked/staged/untracked entries after cleanup
- No tracked modifications
- No staged modifications
- The only prior dirty item was the untracked backup `plugins/platforms/discord/adapter.py.orion-pre-17157-20260829-224911.bak`
- That backup was copied to `C:\Users\spill\Documents\Orion-Hermes-Backups\20260908-055031\adapter.py.orion-pre-17157-20260829-224911.bak`
- Source and relocated backup SHA-256 matched: `6E7EB8E0C3C5640028E8117A406BB7DB8DE2C5CEE0FAF019A5371DC5F629FCCB`
- Original untracked backup was then removed from the Hermes checkout.

No Hermes tracked source was reset, restored, cleaned, checked out, or modified. No Orion/Hermes/Ollama runtime was started by this classification/cleanup step.

Next step: rerun only `Test-Orion-Preflight.ps1` using the already-created exact local `orion-config.json`; do not rerun the 27 offline tests or Windows primitive tests unless another premise changes.
