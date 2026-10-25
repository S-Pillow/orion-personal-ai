from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[2] / "hermes_plugins" / "orion-vault-routing"
SPEC = importlib.util.spec_from_file_location("orion_vault_routing_dc02", PLUGIN_DIR / "__init__.py")
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class FakeContext:
    def __init__(self):
        self.sections = []

    def register_system_prompt_section(self, section_id, content, **kwargs):
        self.sections.append((section_id, content, kwargs))


class DC02VaultRoutingPolicyTests(unittest.TestCase):
    def test_registers_one_bounded_authority_policy_section(self):
        ctx = FakeContext()
        plugin.register(ctx)
        self.assertEqual(len(ctx.sections), 1)
        section_id, content, kwargs = ctx.sections[0]
        self.assertEqual(section_id, plugin.ROUTING_SECTION_ID)
        self.assertEqual(content, plugin.ROUTING_POLICY)
        self.assertEqual(kwargs["position"], "after_memory")
        self.assertEqual(kwargs["max_chars"], plugin.ROUTING_SECTION_MAX_CHARS)
        self.assertLessEqual(len(content), plugin.ROUTING_SECTION_MAX_CHARS)

    def test_personal_durable_knowledge_prefers_orion_retrieval(self):
        policy = plugin.ROUTING_POLICY
        self.assertIn("what the user wrote", policy)
        self.assertIn("durable written knowledge", policy)
        self.assertIn("`orion_vault_retrieve` as the primary route", policy)
        self.assertIn("Pass the natural user question as its retrieval cue", policy)
        self.assertIn("identify the relevant source note/path", policy)
        self.assertIn("Do not fabricate vault content", policy)

    def test_generic_obsidian_and_filesystem_are_secondary_not_disabled(self):
        policy = plugin.ROUTING_POLICY
        self.assertIn("generic Obsidian skill", policy)
        self.assertIn("`search_files`", policy)
        self.assertIn("`read_file`", policy)
        self.assertIn("explicit path/file/listing work", policy)
        self.assertIn("bounded fallback", policy)
        self.assertNotIn("disable the Obsidian", policy)

    def test_policy_preserves_authority_and_mutation_boundaries(self):
        policy = plugin.ROUTING_POLICY
        self.assertIn("Obsidian Markdown remains durable source truth", policy)
        self.assertIn("iai remains the semantic-ranking authority", policy)
        self.assertIn("does not create a second semantic retriever", policy)
        self.assertIn("grants no mutation authority", policy)
        for verb in ("edit", "move", "delete", "create"):
            self.assertIn(verb, policy)
        self.assertIn("preview/approval/mutation guardrails", policy)


if __name__ == "__main__":
    unittest.main()
