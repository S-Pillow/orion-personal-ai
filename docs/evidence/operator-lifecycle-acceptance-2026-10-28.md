# Orion operator lifecycle acceptance — 2026-10-28

## Outcome

**PASS / CLOSED**

The native Windows manual-off operator lifecycle is accepted on the real Orion workstation after the ROCm backend correction, owned Ollama descendant cleanup hardening, and the final Windows PowerShell empty-collection binding correction.

Accepted code checkpoint before this documentation-only closure:

`3cbc1fa4831966fefce5f2711d82032965080fb2`

## Source chain

- PR #74 — **Fix Orion-started Ollama backend on RX 9070 XT**
  - merge: `6e862102df1e68fd6f707aff3ddb3ced1ea8fa25`
  - selects `rocm_v7_1` only for Orion-started `ollama serve` through the child-process inheritance window;
  - restores the parent PowerShell environment immediately after `Start-Process`;
  - does not rewrite persistent Ollama configuration or user/machine environment state.
- PR #75 — **Clean Orion-owned Ollama descendants on stop**
  - merge: `40f96933e9e429b885c9c7a11cfac781c8b99104`
  - captures and persists the Orion-owned Ollama descendant tree before parent termination;
  - validates creation order to reject stale Windows `ParentProcessId` relationships;
  - revalidates surviving descendants by PID, name, executable path, and creation identity before termination;
  - retains cleanup state on failure and blocks Start until Stop safely reconciles pending identities;
  - never performs a broad process-name kill.
- PR #76 — **Allow empty owned-descendant collections in Stop Orion**
  - merge: `3cbc1fa4831966fefce5f2711d82032965080fb2`
  - adds the Windows PowerShell `[AllowEmptyCollection()]` binding contract for valid first-use/empty descendant lists;
  - preserves the accepted ownership and recovery semantics unchanged.

## Root-cause record

The original Start Orion acceptance failure was not a generic HTTP-health failure.

Observed sequence:

1. Ollama 0.32.15 bound `127.0.0.1:11434` but unrestricted backend discovery stalled while probing unsuitable backends on the Windows AMD workstation.
2. The workstation was initially under severe system-memory pressure, so a clean reboot was used to establish a valid diagnostic baseline.
3. With sufficient free RAM, Vulkan-only Ollama liveness became healthy quickly, proving the loopback API and health probe were not the underlying defect.
4. The actual `qwen3.5-hermes:9b` model then crashed during Vulkan loading.
5. Process-local `OLLAMA_LLM_LIBRARY=rocm_v7_1` successfully started Ollama, detected the AMD Radeon RX 9070 XT, loaded the actual Orion model, and completed inference.
6. The first full lifecycle acceptance then exposed a separate Stop gap: the Orion-owned `ollama.exe` parent exited while its `llama-server.exe` model-runner child remained alive.
7. PR #75 closed that ownership-tree cleanup gap; PR #76 closed the final PowerShell binding edge case found before rerunning live acceptance.

## Final Windows acceptance evidence

The final bounded acceptance run was executed from merged `main` at `3cbc1fa4831966fefce5f2711d82032965080fb2`.

### Source and installation

- local `main` fast-forwarded to the exact accepted code checkpoint;
- installed `Start-Orion.ps1` hash matched repository source;
- installed `Stop-Orion.ps1` hash matched repository source;
- the installed launcher contained the ROCm 7.1 contract, pending-cleanup guard, owned-tree cleanup helpers, creation-order validation, and four `[AllowEmptyCollection()]` markers;
- a rollback backup was created at `%LOCALAPPDATA%\Orion\operator-backups\20261028-095729`.

### Prior orphan reconciliation

The previous acceptance-run orphan PID `10284` was still present. It was terminated only after matching the previously captured `llama-server.exe` identity, executable path, command-line markers, and creation-time window. No broad process-name termination was used.

### Clean stopped baseline

- Hermes stopped through the supported COMPANION gateway path;
- Hermes loopback API was confirmed down;
- Ollama port 11434 was clear;
- the empty-descendant Stop path passed;
- iai remained under the vendor idle/HIBERNATION lifecycle.

### Start and runtime

- Orion-started Ollama launched with backend `rocm_v7_1`;
- Ollama API health passed;
- Hermes API health passed;
- `launcher-session.json` recorded Orion ownership of the Ollama PID and backend `rocm_v7_1`;
- initial pending descendant count was zero;
- no process-, user-, or machine-level persistent `OLLAMA_LLM_LIBRARY` mutation occurred.

### Actual model inference

The real Orion model `qwen3.5-hermes:9b` completed a non-streaming `/api/generate` request:

- HTTP success: true;
- HTTP status: 200;
- request completed in approximately 12.44 seconds;
- `done=true`;
- the short diagnostic request ended with `done_reason=length`, which is expected for the deliberately bounded token count;
- runtime logs proved `OLLAMA_LLM_LIBRARY=rocm_v7_1`, `library=ROCm`, and successful model load.

### Owned descendant proof

Before Stop, the acceptance harness observed three descendants of the recorded Orion-owned Ollama process:

- `conhost.exe`;
- `llama-server.exe`;
- `conhost.exe`.

Exactly one owned `llama-server.exe` model runner was present.

### Stop acceptance

Stop Orion:

- stopped Hermes and confirmed its API down;
- persisted all three owned descendant identities before terminating the Ollama parent;
- stopped the recorded Orion-owned Ollama parent;
- observed the surviving owned `llama-server.exe` runner and force-stopped it through the identity-checked owned-descendant path;
- confirmed all captured owned descendants were gone;
- confirmed Ollama API down;
- confirmed port 11434 clear;
- removed launcher session state only after cleanup succeeded;
- introduced no persistent Ollama environment mutation.

### Final operational state

A final Start Orion succeeded and intentionally left Orion running:

- Ollama healthy: true;
- Hermes healthy: true;
- backend: `rocm_v7_1`;
- pending descendant cleanup identities: zero.

## Accepted invariants

- Orion remains manual-off.
- Start/Stop remain one-shot controls, not resident supervisors.
- A pre-existing healthy Ollama process is not restarted, replaced, or claimed by Orion.
- Orion-started Ollama uses process-local ROCm 7.1 selection on the accepted workstation without persistent environment mutation.
- Stop may terminate only the recorded Orion-owned Ollama process and identity-checked descendants captured from that owned tree.
- No broad `ollama.exe` or `llama-server.exe` name-based kill is permitted.
- Failed descendant cleanup retains durable evidence for safe retry and blocks Start from overwriting that state.
- Hermes remains the gateway/runtime authority.
- iai remains the persistent-memory and vendor lifecycle authority.

## Remaining separate gap

The operator lifecycle hardening itself is closed. The remaining PRD lifecycle/presentation gap is separate:

> After Ollama and Hermes are healthy, Start Orion should open the accepted Orion HUD.

The current launcher does not yet perform that step.

## Next coherent outcome when work resumes

Do not reopen the ROCm or owned-tree correction unless a dependency or runtime change invalidates its evidence.

The next lifecycle outcome should be **Start Orion -> healthy runtime -> accepted HUD opens** as one coherent bounded integration:

1. **Read-only discovery first**
   - identify the accepted HUD entry point and current launch command;
   - confirm single-instance/reconnect behavior;
   - determine whether the HUD can be opened safely after Hermes health without introducing a supervisor or duplicate runtime;
   - identify the observable success/failure signal for launch acceptance.
2. **Bounded implementation**
   - add the HUD-open action only after Ollama and Hermes health succeed;
   - preserve one-shot Start semantics;
   - do not change Stop semantics unless the accepted HUD itself requires an explicitly justified close behavior;
   - do not add login startup, Scheduled Tasks, watchers, or a second lifecycle owner.
3. **Focused verification**
   - source regression for ordering: health before HUD open;
   - failure diagnostics when the accepted HUD entry point cannot launch;
   - real Windows desktop-shortcut smoke proving Start -> health -> HUD visible/reconnected and Stop -> runtime down with existing ownership guarantees preserved.
4. **Closure**
   - update this evidence chain and the main README only after live Windows acceptance;
   - then return to the broader Orion roadmap from the current repository state rather than treating this lifecycle work as still open.

## Resume note

Before resuming unrelated Phase 4 or Phase 6 work, refresh the live GitHub state for their active PRs/issues. The lifecycle closure above is current as of 2026-10-28; older roadmap text elsewhere in the repository may describe earlier checkpoints and should not be assumed to reflect later PR status without verification.
