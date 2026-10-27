from __future__ import annotations

import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest_core.py"
SPEC = importlib.util.spec_from_file_location("dc02_core_test", CORE)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def doc_tag(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


class AdmissionAndPlanningTests(unittest.TestCase):
    def test_windows_portable_source_name_contract(self):
        accepted = ["note.md", "Folder/Note.MD", "café/notes.md", "a.b/c-d_e.md"]
        for name in accepted:
            self.assertEqual(mod.validate_source_name(name), name)
        rejected = [
            r"a\\b.md",
            "/absolute.md",
            "../escape.md",
            "a/../b.md",
            "bad:name.md",
            "bad?.md",
            "trail./note.md",
            "trail /note.md",
            "CON.md",
            "CON .md",
            "COM¹.md",
            "folder/AUX.txt.md",
            "not.txt",
        ]
        for name in rejected:
            with self.subTest(name=name), self.assertRaises(mod.AdapterError):
                mod.validate_source_name(name)

    @unittest.skipIf(sys.platform.startswith("win"), "backslash filename is not representable on Windows")
    def test_posix_backslash_markdown_is_rejected_at_admission(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            (vault / ("a" + chr(92) + "b.md")).write_text("portable boundary test", encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "source_name_invalid"):
                mod.scan_markdown_vault(vault)

    @unittest.skipUnless(hasattr(os, "mkfifo") and not sys.platform.startswith("win"), "POSIX FIFO")
    def test_fifo_markdown_is_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            os.mkfifo(vault / "pipe.md")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_not_regular_file"):
                mod.scan_markdown_vault(vault)

    def test_directory_enumeration_error_aborts_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()

            def broken_walk(_root, *, topdown, onerror, followlinks):
                onerror(PermissionError(13, "denied", str(vault / "secret")))
                yield from ()

            with mock.patch.object(mod.os, "walk", side_effect=broken_walk):
                with self.assertRaisesRegex(mod.AdapterError, "vault_walk_failed"):
                    mod.scan_markdown_vault(vault)

    def test_invalid_utf8_and_size_limit_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            bad = vault / "bad.md"
            bad.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_not_utf8"):
                mod.scan_markdown_vault(vault)
            bad.unlink()
            (vault / "big.md").write_bytes(b"12345")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_file_too_large"):
                mod.scan_markdown_vault(vault, max_file_bytes=4)

    def test_casefold_collision_fails_on_posix_fixture(self):
        if sys.platform.startswith("win"):
            self.skipTest("Windows filesystem cannot create the collision fixture")
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            (vault / "A.md").write_text("one content", encoding="utf-8")
            (vault / "a.md").write_text("two content", encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "casefold_path_collision"):
                mod.scan_markdown_vault(vault)

    def test_hardlinked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            source = vault / "a.md"
            alias = Path(td) / "outside.md"
            source.write_text("hardlink content", encoding="utf-8")
            try:
                os.link(source, alias)
            except OSError as exc:
                self.skipTest(f"hardlinks unavailable: {exc}")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_has_multiple_links"):
                mod.scan_markdown_vault(vault)

    def test_plan_uses_content_digest_not_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            store = Path(td) / "store"
            vault.mkdir(); store.mkdir()
            p = vault / "a.md"
            p.write_text("same content long enough", encoding="utf-8")
            notes = mod.scan_markdown_vault(vault)
            tags = {"a.md": doc_tag("a.md")}
            state = mod._state_payload(vault, store, notes, tags, "a" * 64)
            os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 1_000_000))
            current = mod.scan_markdown_vault(vault)
            plan = mod.build_plan(current, state)
            self.assertEqual(plan.unchanged, ("a.md",))
            self.assertEqual(plan.changed, ())

    def test_historical_doc_tag_collision_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"; store = Path(td) / "store"
            vault.mkdir(); store.mkdir()
            old_note = mod.NoteSnapshot("a/b.md", str(vault / "a" / "b.md"), 1, 1, "0" * 64)
            state = mod._state_payload(vault, store, [old_note], {"a/b.md": doc_tag("a/b.md")}, "b" * 64)
            current = [mod.NoteSnapshot("a-b.md", str(vault / "a-b.md"), 1, 1, "1" * 64)]
            with self.assertRaisesRegex(mod.AdapterError, "historical_doc_tag_collision"):
                mod.validate_doc_tags(current, state, doc_tag)

    def test_fixed_metadata_namespace_has_one_lock(self):
        paths = mod.metadata_paths(Path("/tmp/store"))
        self.assertEqual(paths.state.parent, paths.root)
        self.assertEqual(paths.pending.parent, paths.root)
        self.assertEqual(paths.owner.parent, paths.root)
        self.assertEqual(paths.lock.parent, paths.root)
        self.assertIn("vault-markdown-ingest.apply.lock", paths.lock.name)

    def test_core_entrypoint_is_disabled(self):
        self.assertEqual(mod.main([]), 2)


if __name__ == "__main__":
    unittest.main()
