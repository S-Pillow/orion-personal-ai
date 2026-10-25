"""Orion authority-aware routing policy for durable personal vault knowledge.

This plugin intentionally owns no retrieval implementation and no mutation path.
It tells Hermes which already-registered capability is authoritative when a user
asks about their own durable written knowledge, while preserving the bundled
Obsidian/filesystem route for explicit file operations and bounded fallback.
"""

from __future__ import annotations

PLUGIN_VERSION = "0.1.0"
ROUTING_SECTION_ID = "orion.vault-authority-routing"
ROUTING_SECTION_MAX_CHARS = 1800

ROUTING_POLICY = """Orion vault authority routing policy:
- For read-only questions asking what the user wrote, what their notes/documents/vault say, or requesting recall, summary, or synthesis of the user's durable written knowledge, use `orion_vault_retrieve` as the primary route. Pass the natural user question as its retrieval cue.
- Do not begin those personal-knowledge retrieval turns with the generic Obsidian skill, `search_files`, `read_file`, or ad-hoc filesystem semantic search. Those mechanisms are secondary: use them for explicit path/file/listing work, or as bounded fallback only after Orion retrieval is unavailable or returns no usable authoritative source.
- Obsidian Markdown remains durable source truth and iai remains the semantic-ranking authority. The routing policy does not create a second semantic retriever.
- When Orion retrieval returns sources, answer from the returned current source content and identify the relevant source note/path. Do not fabricate vault content when retrieval fails or yields no usable source.
- This policy grants no mutation authority. Requests to edit, move, delete, create, or otherwise mutate vault content must follow the existing Orion preview/approval/mutation guardrails rather than being treated as read-only retrieval.
"""


def register(ctx) -> None:
    ctx.register_system_prompt_section(
        ROUTING_SECTION_ID,
        ROUTING_POLICY,
        position="after_memory",
        max_chars=ROUTING_SECTION_MAX_CHARS,
    )
