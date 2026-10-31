# Hermes v0.22.5 isolated gateway smoke v2 operator note

Use `scripts/hermes_upgrade/v0225_isolated_gateway_contract_smoke.py` as the stable entry point. It delegates to the hardened v2 implementation.

Do not execute historical copies of the retired first implementation from older detached tooling worktrees. Refresh the migration tooling worktree to the current PR head before each run.

The hardened smoke is intentionally non-conversational: it tests localhost binding, health, Bearer authentication, capability advertisement, and local validation behavior of the P4 audio routes. It does not call a model, STT provider, TTS provider, or memory system.

The smoke uses a generated minimal scratch profile, forces `gateway.standalone: true`, disables bundled-skill seeding for the scratch profile, and uses a one-run disposable API key. It always attempts exact process-tree cleanup and production/candidate postcondition verification on success or failure.
