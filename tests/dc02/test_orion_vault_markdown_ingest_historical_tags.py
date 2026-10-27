from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dc02"
    / "orion_vault_markdown_ingest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "orion_vault_markdown_ingest_historical_tag_tests",
    MODULE_PATH,
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class CrossGenerationOwnershipTests(unittest.TestCase):
    def _state(self, path: str, tag: str):
        return {
            "files": {
                path: {
                    "size": 1,
                    "mtime_ns": 1,
                    "sha256": "a" * 64,
                    "doc_tag": tag,
                }
            }
        }

    def test_vanished_path_colliding_with_new_current_path_is_refused(self):
        state = self._state("old/path.md", "doc:shared-owner")
        current = {"new/path.md": "doc:shared-owner"}

        def doc_tag(name: str) -> str:
            if name in {"old/path.md", "new/path.md"}:
                return "doc:shared-owner"
            return f"doc:{name}"

        with self.assertRaisesRegex(mod.AdapterError, "historical_doc_tag_collision"):
            mod.validate_cross_generation_doc_tags(state, current, doc_tag)

    def test_case_only_cross_generation_collision_is_refused(self):
        state = self._state("Notes/Alpha.md", "doc:notes-alpha.md")
        current = {"notes/alpha.md": "doc:notes-alpha.md"}

        def doc_tag(_name: str) -> str:
            return "doc:notes-alpha.md"

        with self.assertRaisesRegex(mod.AdapterError, "historical_doc_tag_collision"):
            mod.validate_cross_generation_doc_tags(state, current, doc_tag)

    def test_persisted_tag_must_still_match_pinned_vendor_function(self):
        state = self._state("old.md", "doc:tampered")
        current = {}

        with self.assertRaisesRegex(mod.AdapterError, "state_doc_tag_vendor_mismatch"):
            mod.validate_cross_generation_doc_tags(
                state,
                current,
                lambda name: f"doc:{name}",
            )

    def test_same_path_same_tag_is_not_a_cross_generation_collision(self):
        state = self._state("same.md", "doc:same.md")
        current = {"same.md": "doc:same.md"}
        mod.validate_cross_generation_doc_tags(
            state,
            current,
            lambda name: f"doc:{name}",
        )

    def test_distinct_historical_and_current_tags_are_allowed(self):
        state = self._state("gone.md", "doc:gone.md")
        current = {"current.md": "doc:current.md"}
        mod.validate_cross_generation_doc_tags(
            state,
            current,
            lambda name: f"doc:{name}",
        )


if __name__ == "__main__":
    unittest.main()
