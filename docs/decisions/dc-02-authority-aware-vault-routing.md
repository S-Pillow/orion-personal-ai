# DC-02 Authority-Aware Vault Routing

Date: 2026-10-25
Status: source correction candidate; runtime acceptance pending

## Observed defect

Natural Retrieval Test C v2 used the ordinary question:

> What did I write about sharing my vault across devices and avoiding sync conflicts?

With 7.65 GiB free system RAM, the accepted model/runtime loaded successfully and Hermes executed for the full test window. The observed tool route was `skill_view -> search_files -> read_file`; `orion_vault_retrieve` was never called. The turn timed out without an assistant answer. This is classified as a routing defect, not a provider/model or RAM blocker.

The accepted Hermes `v2026.8.27` bundled Obsidian skill legitimately claims read/search work in an Obsidian vault and directs the model toward `search_files` and `read_file`. Orion's DC-02 retrieval tool legitimately claims questions about the user's notes/documents/vault. The two capabilities therefore overlap at the natural-language routing layer even though their intended authority roles differ.

## Governing intent

The approved Orion architecture keeps these responsibilities distinct:

- Obsidian Markdown is durable source truth.
- iai owns semantic ranking/recall.
- `orion_vault_retrieve` bridges semantic recall to exact current contained Markdown and returns bounded source content/provenance.
- Hermes remains the orchestrator.
- Generic Obsidian/filesystem tools remain useful for explicit file/path/listing work.
- Read-only retrieval does not grant mutation authority.

Intent status for this correction: **PRESERVED**.

## Decision

Express the authority boundary as a persistent, bounded Orion plugin system-prompt section using Hermes's supported `PluginContext.register_system_prompt_section` extension point.

For read-only questions about the user's durable written knowledge, the policy directs Hermes to use `orion_vault_retrieve` first. Generic Obsidian/file tools are secondary for explicit filesystem work or bounded fallback after authoritative Orion retrieval is unavailable or returns no usable source.

This correction deliberately does **not**:

- disable the bundled Obsidian skill;
- patch or fork Hermes core;
- create a second semantic retriever;
- alter iai ordering or vault source semantics;
- authorize any mutation;
- depend on a growing list of phrase/regex triggers.

## Why this is not the final generalized router

DC-02 needs only the personal-vault authority slice. The longer-term Orion routing architecture should represent capability ownership explicitly across domains (for example: durable vault knowledge, session continuity, semantic memory, filesystem operations, and future targeted capabilities) so overlapping vendor skills cannot silently become competing authorities.

The desired long-term shape is an **authority-aware capability router** with:

1. a stable capability/authority map;
2. supported Hermes prompt or middleware integration rather than Hermes-core patches;
3. deterministic conflict handling where a lower-authority generic tool is attempted for an intent owned by a higher-authority Orion capability;
4. explicit fallback rules rather than silent route substitution;
5. regression coverage using real operator wording plus negative cases.

That generalized router belongs with the later targeted-routing work. DC-02 should not prematurely implement all Phase 7 routing.

## Escalation rule

First qualify the supported persistent policy section because it is the narrowest mechanism that preserves architecture intent. If a clean runtime rerun still chooses generic Obsidian/filesystem search before `orion_vault_retrieve`, treat that as evidence that prompt-level authority policy is insufficient. The next correction should then be a deterministic, narrowly scoped tool-routing guard/middleware for the conflicting path, not additional phrase matching.

## Acceptance impact

Source/unit/CI success is not DC-02 acceptance. Runtime acceptance still requires a high-memory natural-language test showing that the ordinary question routes through `orion_vault_retrieve`, returns authoritative current source content/provenance, names the relevant source note(s), performs no mutation, and restores clean manual-off state.
