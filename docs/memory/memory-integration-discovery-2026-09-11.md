# Orion Memory Integration Discovery Record — 2026-09-11

Status: **NON-NORMATIVE DISCOVERY / FUTURE QUALIFICATION TRACK / NO PRD AMENDMENT AUTHORIZED**

Branch: `docs/orion-memory-integration-discovery`

Base `main` at creation: `8db415a78cf23a99a93c8772cc54a5c357243663`

Controlling specification: **ORION Master PRD v2.8**

## Purpose

Preserve the completed memory-integration review so the findings survive chat/context rollover and can be executed later as a bounded qualification track.

This document does **not** replace the accepted memory architecture, authorize a Hermes or iai upgrade, authorize a new MemoryProvider, or amend OR-MEM-001 / Phase 2 acceptance language.

The currently accepted Orion memory architecture remains the controlling implementation until a replacement passes the qualification gates defined below and the PRD is deliberately amended.

## Executive conclusion

Nothing in this review shows that Orion's accepted memory architecture was built incorrectly.

The accepted Hermes + iai integration is vendor-supported. The review identified a plausible **second-generation integration** that may improve memory freshness and possibly latency while preserving the existing ownership boundary:

- Hermes remains agent/session/tool orchestration authority.
- iai remains persistent-memory authority.
- Orion remains presentation/control and does not become a second memory engine.

The new integration is a candidate only. Its burden of proof is asymmetric:

> **Provider mode may win on speed.**
>
> **Provider mode may win on freshness.**
>
> **Provider mode must never lose on quality, security, or reliability.**

## Accepted current architecture

Accepted baseline at the time of this review:

- Hermes Agent tag `v2026.8.27`, package `0.20.6`.
- iai baseline `iai-pme==3.0.8`.
- COMPANION profile is the accepted Orion Hermes profile.
- Hermes owns the iai MCP wrapper.
- iai owns persistent memory.
- Orion does not duplicate iai storage, ranking, consolidation, forgetting, contradiction, or administration semantics.
- Detailed memory administration remains in supported iai Brain / CLI surfaces.
- The accepted COMPANION iai MCP lifecycle uses the existing persistent stdio-child configuration, including the accepted `idle_timeout_seconds=600` baseline.

### Current Hermes hook path

The accepted vendor integration uses Hermes hooks for ambient recall/capture.

Source review established that the recall adapter invokes a shell/Python/Bash path before the LLM call, while the session-end capture adapter reads Hermes `state.db` and stages deferred captures into iai's deferred-capture spool.

This route is supported. The open question is whether its integration overhead and deferred-capture freshness are materially worse than a MemoryProvider route under Orion's real Windows workload.

### Deferred capture behavior

The deferred path is not equivalent to iai's direct `memory_capture(..., live_turn=True)` dispatch path.

The vendor daemon's WAKE spool sweep is approximately 30 seconds by default. Therefore hook-mode capture-to-recallable latency has a known scheduling component: best case can be a few seconds if a sweep follows immediately; worst case is approximately one sweep interval plus embedding/processing time.

This difference is the main reason a MemoryProvider prototype may be justified even if speed gains are small.

## Low-risk optimization: reduce the model-visible iai tool surface

Hermes `v2026.8.27` supports per-MCP-server `tools.include` / `tools.exclude` filtering.

Rules confirmed in the pinned source:

- `include` takes precedence over `exclude`;
- `include: []` registers no model-visible tools;
- neither filter means register all discovered tools.

The accepted iai 3.0.8 MCP server exposes fourteen tools, while Orion's explicit memory contract only needs the following interactive surface:

- `memory_recall`
- `memory_search`
- `memory_capture`
- `memory_contradict`

Candidate COMPANION configuration shape:

```yaml
mcp_servers:
  <iai-server-name>:
    tools:
      include:
        - memory_recall
        - memory_search
        - memory_capture
        - memory_contradict
```

The actual accepted COMPANION server key must be read from the current profile before any configuration mutation; do not assume the literal key shown in examples.

This is a zero-code optimization candidate and should be characterized before any provider implementation.

## Public Hermes MCP call surface for ambient provider work

The preferred ambient invocation primitive is **`PluginContext.call_mcp(server, tool, arguments, timeout)`** at the pinned Hermes tag.

Important properties from the pinned source:

- synchronous and documented as safe for plugin hooks/tools;
- reuses Hermes' **existing native MCP client machinery**;
- does not create a second MCP client or connection;
- internally reuses the same MCP handler path, including trust gate, circuit breaker, reconnect behavior, and result rendering;
- does **not** depend on the model-visible registry registration of the requested MCP tool;
- uses a per-plugin default-deny `mcp_allowlist`;
- timeout is clamped to 1–600 seconds;
- returned result is bounded to approximately 64 KB;
- future Hermes source contains a migration note toward finer per-tool / expiry / read-write grants.

Candidate security boundary:

```yaml
plugins:
  entries:
    <orion-iai-ambient-plugin-id>:
      mcp_allowlist:
        - <iai-server-name>
```

The ambient adapter should never receive authority over unrelated MCP servers.

### Important separation of knobs

Model visibility and ambient invocation are independent:

- `mcp_servers.<iai>.tools.include` controls which iai schemas the **model sees**;
- `PluginContext.call_mcp()` allows an authorized plugin to invoke an iai MCP tool over the **resident MCP connection** even when that tool is not model-visible.

Therefore a future ambient provider can use additional iai operations internally without exposing their schemas to the 9B model.

## MemoryProvider capability-injection limitation

The transport choice is closed. The remaining implementation detail is how an exclusive Hermes `MemoryProvider` receives access to `PluginContext.call_mcp()` without touching private framework state.

Hermes' pinned memory-provider loader passes provider `register(ctx)` functions a `_ProviderCollector`.

`_ProviderCollector.__getattr__` deliberately forwards only names beginning with `register_`. Accessing `ctx.call_mcp` from a memory-provider `register(ctx)` therefore raises `AttributeError` by design.

Do **not** solve this by reaching into:

- `_ProviderCollector._plugin_context()`;
- `tools.mcp_tool._servers`;
- `_mcp_loop`;
- other private Hermes globals.

Those shortcuts would replace a public vendor integration with private coupling.

### Single-plugin shortcut is also closed

A normal Hermes plugin cannot simply register the MemoryProvider and retain a normal `PluginContext`.

Pinned Hermes plugin discovery classifies modules containing `register_memory_provider` or `MemoryProvider` as the exclusive memory-provider category and routes them through the memory-provider loader rather than the general plugin manager.

The general `PluginContext.register_memory_provider` path is not a supported escape hatch for intentionally combining both roles.

## Candidate capability-injection design: two-plugin handshake

This remains a **candidate to prove**, not an accepted design.

Shape:

1. A small generic Hermes plugin contains no `MemoryProvider` / `register_memory_provider` markers, receives a real `PluginContext`, and retains a bounded facade around `ctx.call_mcp`.
2. It publishes that facade through a plain Python adapter module.
3. The exclusive iai MemoryProvider resolves that facade at initialization/runtime and uses it for ambient MCP operations.
4. The MCP allowlist belongs to the generic bridge plugin's plugin id and grants only the iai server.

Mandatory properties before this design can be accepted:

- **profile-scoped** — no cross-profile handle reuse;
- **lifecycle-scoped** — tied to the current PluginManager/plugin generation;
- **revocable** — unload/reload invalidates the published handle;
- missing bridge plugin yields a clean degraded state;
- no search through private Hermes objects as fallback;
- deterministic load-order behavior;
- no stale function reference survives plugin reload;
- no second MCP connection;
- default-deny MCP allowlist remains effective.

A single unscoped process-global function reference is not acceptable.

## Provider/hook exclusivity

Provider mode and the existing iai Hermes hooks must be **mutually exclusive configurations**.

Never run both active capture/injection paths simultaneously.

Risks of co-activation include:

- duplicate capture;
- duplicate ambient context;
- conflicting freshness semantics;
- harder rollback/attribution;
- misleading benchmark results.

Rollback means switching the profile back to the accepted hook configuration, not keeping both paths live.

## Ambient-provider responsibilities

The candidate provider should expose **no additional model tool schemas**:

```text
get_tool_schemas() == []
```

The four explicit model-callable memory tools remain provided once through the existing iai MCP wrapper.

Ambient responsibilities only:

- `queue_prefetch` / background recall;
- `sync_turn` / completed-turn capture;
- bounded status/degraded reporting as supported by the MemoryProvider contract;
- lifecycle integration needed to keep those operations safe and observable.

## Failure semantics

Prefetch and capture have different consequences and must not share one generic fail-open policy.

### Prefetch

Desired prototype behavior:

- background only;
- short bounded timeout, initial candidate approximately 1 second;
- fail open;
- no retry on the critical user-turn path;
- a miss costs one turn of ambient context, not conversation availability.

Exact timeout is empirical, not fixed by this document.

### Capture

A dropped capture can permanently lose a memory when hook mode is disabled.

Therefore candidate provider capture must have stronger delivery semantics:

- bounded initial call;
- bounded background retry;
- duplicate-safe/idempotent behavior where supported;
- visible degraded-memory state after retry exhaustion;
- no silent permanent loss.

If a durable fallback is required, prefer an **iai-supported deferred-capture mechanism** rather than creating an Orion memory database or plaintext durable queue.

An adapter may maintain bounded transport/retry state; it must not become a second memory authority.

## Concurrency matrix for provider qualification

At minimum, test:

1. provider prefetch only;
2. model explicit iai memory-tool call only;
3. provider prefetch + explicit memory-tool call overlapping;
4. capture + next-turn prefetch overlapping;
5. iai slow/unavailable during overlap.

Measure:

- queueing/contention;
- timeouts;
- time-to-first-token impact;
- explicit memory-tool correctness;
- failure isolation;
- whether ambient traffic can degrade a user-requested memory operation;
- recovery/reconnect behavior.

The fact that Hermes' MCP machinery is designed for concurrent use is not itself Orion acceptance evidence.

## iai 3.2.1 qualification

The review promoted iai 3.2.1 from an interesting future version to a serious qualification candidate, but **no upgrade is authorized** by this document.

Qualification must follow PRD upgrade rules against a copied/rollback-safe store and include at minimum:

- memory correctness;
- encrypted-store / crypto compatibility;
- Windows lifecycle and HIBERNATION behavior;
- capture/recall behavior;
- daemon-down recall behavior;
- Brain/admin compatibility;
- provenance/availability/degraded-state behavior;
- rollback safety.

### Important non-expectation

Source review found that the iai 3.2.1 Hermes hook path retains the same shell/deferred integration shape as the accepted 3.0.8 route.

Therefore upgrading iai is **not expected to eliminate the MemoryProvider question**.

Build any provider prototype only against whichever iai version wins qualification so the provider is implemented once.

## Vendor benchmark evidence: how to use it

Vendor benchmark numbers are useful reference evidence, **not Orion measurements or Orion pass/fail thresholds**.

The published figures were measured on vendor hardware/workloads (including Apple M2 Max and synthetic corpora) and isolate the iai retrieval layer rather than the complete Orion/Hermes/Windows/model path.

They support vendor due diligence: iai's retrieval engine is credible.

They do not prove Orion's:

- time-to-first-token;
- Windows latency;
- hook-chain cost;
- MCP/provider overhead;
- capture freshness;
- model prompt cost;
- end-to-end memory quality.

### Reference lines relevant to interpretation

The review identified these vendor figures as useful order-of-magnitude reference lines:

- recall p95 approximately 77 ms at 100 records;
- recall p95 approximately 105 ms at 1,000 records;
- recall p95 approximately 368 ms at 10,000 records, which the vendor notes misses its own internal target;
- session-start pack approximately 1,629 tokens at `wake_depth=minimal` versus approximately 2,993 at `standard`;
- ambient/foresight pack approximately 350 tokens versus approximately 2,850 tokens for a larger reactive agent search on the vendor's test store.

Do not compare Orion absolute results directly to those numbers as hardware-independent thresholds.

Instead use them to interpret decomposition. For example, if iai retrieval is near ~100 ms while Orion's `pre_llm_call` memory path consumes far more time, the integration layer is the likely dominant source of overhead.

## Consolidation expectation

Do not describe iai as becoming smarter merely because a nightly consolidation cycle runs.

More accurate model:

> useful source records → correct capture → fresh availability → strong retrieval → useful reinforcement → durable consolidation

The vendor's sleep/consolidation ablation evidence indicates that a consolidation cycle can preserve recall without automatically improving it.

More records broaden available evidence; reinforcement can improve selection; consolidation primarily protects/organizes memory over time.

## Reusable vendor benchmark harnesses

Prefer vendor-provided harnesses over writing replacement synthetic tests when they cover the needed property.

Candidate 3.2.1 qualification harnesses on disposable/copied stores:

- `personal_fact_drift`
- `contradiction_longitudinal`
- recall-accuracy harness/tests, including `tests/test_recall_accuracy_gate.py` family

Candidate context-cost A/B harnesses:

- token/session-cost tooling for `wake_depth=minimal` versus `standard`

Candidate provider/hook decomposition tools:

- pipeline-stage timing harnesses;
- full-recall latency probes.

All vendor harnesses must run against disposable/copied stores, never the canonical memory store unless a specific test is explicitly authorized and designed for it.

## Step-2 characterization artifact

Before writing a provider prototype, create a characterization table for the accepted 3.0.8 system.

### Section A — current baseline

Measure current state rather than relying on historical checkpoints:

- current record count / store scale;
- current model-visible iai schema count;
- current daemon/store health;
- `pre_llm_call` memory wall time;
- actual iai retrieval time;
- capture-to-recallable delay;
- submit → first-token latency;
- turn completion latency;
- current session-start/context pack token contribution where measurable.

### Section B — four-tool include A/B

Apply only the supported four-tool include configuration in a controlled profile/test.

Verify:

- model-visible iai schemas decrease from the actual baseline to four;
- explicit recall/search/capture/contradict operations still function;
- ambient hook recall/capture remain intact;
- prompt/tool-schema burden changes as expected;
- first-token/turn latency change is measured, not assumed.

If accepted, this optimization may remain even if no MemoryProvider is later adopted.

### Section C — wake-depth A/B

Compare accepted `standard` with `minimal`.

Measure both:

- token/context savings;
- actual answer/context quality on fixed Orion prompts.

Do not accept `minimal` merely because it uses fewer tokens. It must preserve enough relevant context for Orion's real tasks.

### Section D — architecture comparison

Only if still justified after low-risk optimizations, compare hook mode versus provider mode.

Separate:

- speed;
- freshness;
- quality/security/reliability.

Do not collapse these into one score.

## Precommitted freshness acceptance criteria

Define success before running the provider experiment.

### Test 1 — novel fact → new session retrieval

Scenario:

1. tell Orion a genuinely novel fact;
2. allow the turn to complete;
3. start/probe from a new session according to the controlled test design;
4. measure completion → fact-recallable elapsed time.

Provider-mode target:

> **Fact becomes retrievable within 5 seconds in at least 95% of trials.**

Hook mode is measured unchanged as the control distribution.

Record at minimum:

- p50;
- p90;
- p95;
- maximum;
- failures/timeouts.

Use enough trials for the distribution to be meaningful; approximately 40–50 trials across multiple sessions is a suitable starting design unless a better statistical plan is justified before execution.

Randomize probe delay enough to avoid accidentally synchronizing every hook-mode trial to the daemon sweep cadence.

Use facts that cannot be guessed from model/world knowledge or existing memory.

### Test 2 — same-session ambient foresight

Scenario:

1. tell Orion a novel fact;
2. continue normal conversation without explicitly requesting a memory search;
3. within the next two turns, create a semantically relevant situation where that fact should inform context;
4. inspect whether the ambient/foresight context surfaced it appropriately.

Provider-mode target:

> **The relevant fact is available through ambient context within the next two turns when semantically applicable.**

This is primarily a functional yes/no freshness test. Hook mode need not provide an equivalent mechanism in order for provider mode to demonstrate user-visible value.

The test must distinguish actual retrieved/ambient memory evidence from the model merely retaining the fact in active conversation context.

## Latency acceptance principle

Provider mode does not automatically need to be faster if low-risk configuration changes already eliminate the perceived latency problem.

Interpretation:

- if four-tool filtering / wake-depth tuning leaves meaningful memory-path latency, provider speed becomes a stronger justification;
- if accepted hook-mode memory overhead is already near the actual iai retrieval cost, provider speed justification largely disappears;
- provider freshness may independently justify adoption if it produces a meaningful user-visible improvement.

## Quality / security / reliability gate

This axis is non-negotiable.

Provider mode must not regress:

- recall accuracy;
- contradiction behavior;
- explicit memory-search behavior;
- persistent-store ownership;
- encrypted-store handling;
- privacy/local-first behavior;
- daemon-down behavior;
- HIBERNATION/lifecycle behavior;
- duplicate prevention;
- capture correctness;
- provenance/source correctness;
- failure isolation;
- rollback simplicity;
- model-visible authority boundaries.

A speed or freshness win cannot compensate for regression on this axis.

## Feedback controls: future only

Do not add generic thumbs-up/down answer feedback to memory ranking.

Any future Memory Lens reinforcement UI must bind feedback to the **specific retrieved memory record/event** that influenced context, for example:

- Helpful
- Incorrect / outdated

Only add this after Orion can truthfully expose the relevant memory provenance.

## Vault ingestion

Increasing useful memory volume remains desirable, but ingestion must preserve the PRD's source-of-truth hierarchy and privacy boundaries.

- Obsidian/written vault remains durable written truth where the PRD says it does.
- iai may ingest supported vault material through vendor-native ingestion paths.
- do not blindly bulk-import sensitive or excluded material.
- preserve provenance/source identity.
- inspect current store population before claiming memory is sparse.

## REM / external reflection

Optional cloud/subscription reflection over personal memory remains **rejected for the current Orion architecture** under the stronger privacy/local-first requirement.

Do not enable it as part of this track.

## Model-size changes are out of scope

Do not change the accepted 9B model merely because a smaller model might be faster.

Memory reduces recall burden; it does not replace reasoning, tool selection, planning, ambiguity handling, or judgment.

Any future 4B/9B comparison requires its own benchmark on representative Orion tasks after memory-path latency is decomposed.

## Future PRD amendment trigger

No PRD amendment is authorized by this document.

If provider mode passes qualification and is chosen for promotion, then deliberately update the relevant normative language at the same time as architecture promotion, including as applicable:

- OR-MEM-001;
- §16 memory acceptance language;
- accepted iai/Hermes integration baseline;
- lifecycle/failure semantics;
- any configuration ownership needed for the provider/bridge pair.

Do not silently drift the implementation away from the PRD first and document it later.

## Sequence after P3-04

This track stays behind the current P3-04 provenance/origin/authority work.

Recommended order:

1. Close P3-04 independently.
2. Produce the accepted-3.0.8 characterization table.
3. Run the four-tool include before/after characterization.
4. Run `wake_depth=minimal` versus `standard` A/B if justified.
5. Qualify iai 3.2.1 against a copied store.
6. Resolve/prove the clean capability-injection adapter for `MemoryProvider → PluginContext.call_mcp`.
7. Prototype provider mode against whichever iai version wins qualification.
8. Run concurrency, latency, freshness, quality, security, lifecycle, and rollback gates.
9. Promote only if the precommitted decision rule is satisfied.
10. Amend the PRD deliberately if and only if the architecture is promoted.

## Hard stop conditions

Stop and report rather than widening scope if implementation would require:

- private Hermes `_servers`, `_mcp_loop`, `_ProviderCollector._plugin_context()`, or equivalent internals;
- a second persistent MCP client/connection when `PluginContext.call_mcp()` should suffice;
- provider and hook capture active simultaneously;
- an Orion-owned persistent memory database;
- silent loss of captures;
- cloud reflection of personal memory without a separate explicit privacy decision;
- weakening iai as the memory authority;
- changing the accepted model merely to make provider metrics look better;
- changing the PRD before qualification evidence exists.

Core Intent Preservation: **PRESERVED**.
