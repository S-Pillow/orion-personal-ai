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
    def __init__(self, mcp_responses=None):
        self.tools = {}
        self.hooks = {}
        self.mcp_responses = list(mcp_responses or [])
        self.mcp_calls = []

    def register_tool(self, *, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "kwargs": kwargs,
        }

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def call_mcp(self, server, tool, arguments=None, timeout=30):
        self.mcp_calls.append(
            {
                "server": server,
                "tool": tool,
                "arguments": dict(arguments or {}),
                "timeout": timeout,
            }
        )
        if not self.mcp_responses:
            raise AssertionError("unexpected MCP call")
        response = self.mcp_responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


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
                plugin.PREVIEW_DELETE_TOOL,
                plugin.RECOMMEND_TOOL,
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
        self.assertEqual(directive["action"], "block")
        self.assertIn("not enabled", directive["message"])
        self.assertIn(str(note.resolve()), result["plan"]["target_canonical_path"])

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

    def _write_orion_draft(self, name="draft.md", body="draft body"):
        draft = self.inbox / name
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(
            f"---\norion_draft: true\nstatus: draft\n---\n{body}\n",
            encoding="utf-8",
        )
        return draft

    def test_destination_recommendation_uses_iai_order_and_unique_doc_tags(self):
        draft = self._write_orion_draft(body="alpha project notes")
        source_a = self.vault / "AIOS" / "reference.md"
        source_b = self.vault / "Research" / "other.md"
        source_a.parent.mkdir()
        source_b.parent.mkdir()
        source_a.write_text("alpha", encoding="utf-8")
        source_b.write_text("other", encoding="utf-8")

        ctx = FakeContext(
            [
                {
                    "ok": True,
                    "result": {
                        "hits": [
                            {"record_id": "r-aios", "literal_surface": "alpha"},
                            {"record_id": "r-research", "literal_surface": "other"},
                        ]
                    },
                },
                {
                    "ok": True,
                    "result": {
                        "hits": [
                            {
                                "id": "r-aios",
                                "tags": [plugin._doc_tag("AIOS/reference.md")],
                            },
                            {
                                "id": "r-research",
                                "tags": [plugin._doc_tag("Research/other.md")],
                            },
                        ]
                    },
                },
            ]
        )
        plugin.register(ctx)
        handler = ctx.tools[plugin.RECOMMEND_TOOL]["handler"]

        result = json.loads(
            handler({"source_draft": "draft.md", "top": 5})
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(result["native_recall_hit_count"], 2)
        self.assertEqual(result["recommendation_count"], 2)
        self.assertEqual(result["recommendations"][0]["directory"], "AIOS")
        self.assertEqual(
            result["recommendations"][0]["suggested_target_relative_path"],
            "AIOS/draft.md",
        )
        self.assertEqual(
            result["recommendations"][0]["native_recall_rank"],
            1,
        )
        self.assertEqual(result["recommendations"][1]["directory"], "Research")
        self.assertEqual(
            [call["tool"] for call in ctx.mcp_calls],
            [plugin.IAI_RECALL_TOOL, plugin.IAI_TEMPORAL_RECALL_TOOL],
        )
        self.assertEqual(
            [call["server"] for call in ctx.mcp_calls],
            [plugin.IAI_MCP_SERVER, plugin.IAI_MCP_SERVER],
        )
        self.assertEqual(draft.read_text(encoding="utf-8").splitlines()[-1], "alpha project notes")
        self.assertEqual(source_a.read_text(encoding="utf-8"), "alpha")
        self.assertEqual(source_b.read_text(encoding="utf-8"), "other")

    def test_destination_recommendation_skips_ambiguous_lossy_doc_tag(self):
        self._write_orion_draft()
        nested = self.vault / "A" / "B.md"
        flat = self.vault / "A-B.md"
        nested.parent.mkdir()
        nested.write_text("nested", encoding="utf-8")
        flat.write_text("flat", encoding="utf-8")

        collision_tag = plugin._doc_tag("A/B.md")
        self.assertEqual(collision_tag, plugin._doc_tag("A-B.md"))

        ctx = FakeContext(
            [
                {
                    "ok": True,
                    "result": {
                        "hits": [{"record_id": "r1", "literal_surface": "body"}]
                    },
                },
                {
                    "ok": True,
                    "result": {
                        "hits": [{"id": "r1", "tags": [collision_tag]}]
                    },
                },
            ]
        )
        plugin.register(ctx)
        result = json.loads(
            ctx.tools[plugin.RECOMMEND_TOOL]["handler"](
                {"source_draft": "draft.md"}
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["native_recall_hit_count"], 1)
        self.assertEqual(result["recommendation_count"], 0)
        self.assertEqual(result["recommendations"], [])
        self.assertTrue(nested.exists())
        self.assertTrue(flat.exists())

    def test_destination_recommendation_fails_closed_on_iai_error(self):
        draft = self._write_orion_draft()
        before = draft.read_bytes()

        ctx = FakeContext([{"ok": False, "error": "unavailable"}])
        plugin.register(ctx)
        result = json.loads(
            ctx.tools[plugin.RECOMMEND_TOOL]["handler"](
                {"source_draft": "draft.md"}
            )
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "iai_recall_invalid_response")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(draft.read_bytes(), before)

    def test_move_preview_does_not_create_missing_target_directories(self):
        draft = self.inbox / "draft.md"
        draft.write_text(
            "---\norion_draft: true\nstatus: draft\n---\nbody\n",
            encoding="utf-8",
        )

        result = json.loads(
            plugin.preview_move_draft(
                {
                    "source_draft": "draft.md",
                    "target_relative_path": "New/Deep/draft.md",
                }
            )
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["mutation_performed"])
        self.assertFalse((self.vault / "New").exists())
        self.assertTrue(draft.exists())
        self.assertEqual(
            result["plan"]["target_relative_path"],
            "New/Deep/draft.md",
        )

    def test_expired_plan_fails_closed_before_approval(self):
        note = self.vault / "note.md"
        note.write_text("before\n", encoding="utf-8")
        preview = json.loads(
            plugin.preview_edit(
                {
                    "target_relative_path": "note.md",
                    "new_content": "after\n",
                }
            )
        )
        token = preview["plan_token"]
        plugin._PREVIEW_TIMES[token] -= plugin.PREVIEW_TTL_SECONDS + 1

        directive = plugin.pre_tool_call(
            plugin.APPLY_TOOL,
            {"plan_token": token},
        )

        self.assertEqual(directive["action"], "block")
        self.assertIn("expired", directive["message"])
        self.assertEqual(note.read_text(encoding="utf-8"), "before\n")

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

    def test_windows_component_policy_rejects_ads_and_aliases(self):
        bad = [
            "note.md:payload.md", "folder/note.md:payload.md",
            "CON.md", "folder/lpt1.txt.md", "note.md ", "folder. /note.md",
            "folder./note.md", "note?.md", "note\x01.md", "a//note.md",
            "a/./note.md", "a/../note.md",
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(plugin.PathPolicyError):
                    plugin._resolve_under_root(
                        self.vault, value, allow_missing_leaf=True,
                    )

    def test_leading_space_path_is_preserved_not_redirected(self):
        spaced = self.vault / " note.md"
        plain = self.vault / "note.md"
        spaced.write_text("spaced\n", encoding="utf-8")
        plain.write_text("plain\n", encoding="utf-8")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": " note.md", "new_content": "after\n",
        }))
        self.assertEqual(preview["plan"]["target_relative_path"], " note.md")
        self.assertEqual(preview["plan"]["target_canonical_path"], str(spaced.resolve()))
        self.assertEqual(spaced.read_text(encoding="utf-8"), "spaced\n")
        self.assertEqual(plain.read_text(encoding="utf-8"), "plain\n")

    def test_unterminated_diff_lines_are_separate_and_marked(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new",
        }))
        self.assertIn("-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file\n", preview["diff"])
        self.assertEqual(note.read_bytes(), b"old")

        draft = self.inbox / "draft.md"
        # Use explicit CRLF bytes with no final terminator on every platform.
        draft.write_bytes(b"---\r\norion_draft: true\r\nstatus: draft\r\n---\r\nbody")
        move = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md", "target_relative_path": "draft.md",
        }))
        self.assertIn("+body\n\\ No newline at end of file\n", move["diff"])
        self.assertFalse((self.vault / "draft.md").exists())

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
