from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "orion_vault_actions",
    PLUGIN_DIR / "__init__.py",
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class EnvRoots:
    def __init__(self, vault: Path, inbox: Path):
        self.vault = vault
        self.inbox = inbox
        self.old_vault = os.environ.get("ORION_VAULT_ROOT")
        self.old_inbox = os.environ.get("ORION_INBOX_ROOT")

    def __enter__(self):
        os.environ["ORION_VAULT_ROOT"] = str(self.vault)
        os.environ["ORION_INBOX_ROOT"] = str(self.inbox)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.old_vault is None:
            os.environ.pop("ORION_VAULT_ROOT", None)
        else:
            os.environ["ORION_VAULT_ROOT"] = self.old_vault

        if self.old_inbox is None:
            os.environ.pop("ORION_INBOX_ROOT", None)
        else:
            os.environ["ORION_INBOX_ROOT"] = self.old_inbox


class FakeContext:
    def __init__(self):
        self.tools = {}
        self.hooks = {}

    def register_tool(self, *, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "kwargs": kwargs,
        }

    def register_hook(self, name, callback):
        self.hooks[name] = callback


class P501VaultContractTests(unittest.TestCase):
    def setUp(self):
        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.inbox = self.root / "inbox"
        self.outside = self.root / "outside"
        self.vault.mkdir()
        self.inbox.mkdir()
        self.outside.mkdir()
        self.env = EnvRoots(self.vault, self.inbox)
        self.env.__enter__()

    def tearDown(self):
        self.env.__exit__(None, None, None)
        self.tmp.cleanup()

    def test_registers_expected_tools_and_approval_hook(self):
        ctx = FakeContext()
        plugin.register(ctx)

        self.assertEqual(
            set(ctx.tools),
            {
                plugin.PREVIEW_EDIT_TOOL,
                plugin.PREVIEW_MOVE_TOOL,
                plugin.APPLY_TOOL,
            },
        )
        self.assertIn("pre_tool_call", ctx.hooks)

    def test_edit_preview_is_side_effect_free_and_plan_scoped(self):
        note = self.vault / "Notes" / "example.md"
        note.parent.mkdir()
        original = "alpha\nbeta\n"
        note.write_text(original, encoding="utf-8")

        result = json.loads(
            plugin.preview_edit(
                {
                    "target_relative_path": "Notes/example.md",
                    "new_content": "alpha\ngamma\n",
                }
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "preview")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_text(encoding="utf-8"), original)
        self.assertIn("-beta", result["diff"])
        self.assertIn("+gamma", result["diff"])
        self.assertEqual(len(result["plan_token"]), 64)

        directive = plugin.pre_tool_call(
            plugin.APPLY_TOOL,
            {"plan_token": result["plan_token"]},
        )
        self.assertEqual(directive["action"], "approve")
        self.assertEqual(
            directive["rule_key"],
            f"orion_vault_plan:{result['plan_token']}",
        )
        self.assertIn(str(note.resolve()), directive["message"])

    def test_move_preview_is_side_effect_free(self):
        draft = self.inbox / "draft.md"
        source = (
            "---\n"
            "orion_draft: true\n"
            "status: draft\n"
            "---\n"
            "draft body\n"
        )
        draft.write_text(source, encoding="utf-8")

        target_dir = self.vault / "Projects"
        target_dir.mkdir()

        result = json.loads(
            plugin.preview_move_draft(
                {
                    "source_draft": "draft.md",
                    "target_relative_path": "Projects/draft.md",
                }
            )
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["mutation_performed"])
        self.assertTrue(draft.exists())
        self.assertFalse((target_dir / "draft.md").exists())
        self.assertIn("+draft body", result["diff"])

    def test_unknown_plan_blocks_before_placeholder_handler(self):
        directive = plugin.pre_tool_call(
            plugin.APPLY_TOOL,
            {"plan_token": "0" * 64},
        )
        self.assertEqual(directive["action"], "block")
        self.assertIn("unknown", directive["message"])

        result = json.loads(
            plugin.apply_plan_placeholder({"plan_token": "0" * 64})
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "p5_01_mutation_not_authorized")
        self.assertFalse(result["mutation_performed"])

    def test_placeholder_apply_never_mutates_known_edit_plan(self):
        note = self.vault / "note.md"
        original = "before\n"
        note.write_text(original, encoding="utf-8")

        preview = json.loads(
            plugin.preview_edit(
                {
                    "target_relative_path": "note.md",
                    "new_content": "after\n",
                }
            )
        )
        result = json.loads(
            plugin.apply_plan_placeholder(
                {"plan_token": preview["plan_token"]}
            )
        )

        self.assertTrue(result["plan_known"])
        self.assertFalse(result["success"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_text(encoding="utf-8"), original)

    def test_relative_path_policy_rejects_absolute_and_traversal(self):
        bad = [
            "../escape.md",
            "folder/../escape.md",
            r"C:\escape.md",
            r"\\server\share\escape.md",
            "/escape.md",
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(plugin.PathPolicyError):
                    plugin._resolve_under_root(
                        self.vault,
                        value,
                        allow_missing_leaf=True,
                    )

    def test_non_markdown_target_is_rejected(self):
        note = self.vault / "note.txt"
        note.write_text("text", encoding="utf-8")

        with self.assertRaises(plugin.PathPolicyError):
            result = json.loads(
                plugin.preview_edit(
                    {
                        "target_relative_path": "note.txt",
                        "new_content": "new",
                    }
                )
            )
            self.fail(result)

    def test_reparse_or_symlink_escape_is_rejected_when_platform_supports_it(self):
        outside_file = self.outside / "outside.md"
        outside_file.write_text("outside", encoding="utf-8")
        link = self.vault / "escape"

        created = False
        try:
            os.symlink(self.outside, link, target_is_directory=True)
            created = True
        except (OSError, NotImplementedError):
            if os.name == "nt":
                proc = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(self.outside)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
                created = proc.returncode == 0

        if not created:
            self.skipTest("Platform did not permit a temporary symlink/junction fixture")

        with self.assertRaises(plugin.PathPolicyError) as ctx:
            plugin._resolve_under_root(
                self.vault,
                "escape/outside.md",
                must_exist=True,
            )
        self.assertIn(
            str(ctx.exception),
            {"reparse_point_rejected", "resolved_path_outside_root"},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
