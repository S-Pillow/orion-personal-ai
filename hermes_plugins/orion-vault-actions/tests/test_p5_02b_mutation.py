"""P5-02B disposable mutation candidate tests.

These tests opt into the private source-only executor with temporary roots.
The registered Hermes apply tool remains the P5-01 refusing placeholder.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "orion_vault_actions_p502b", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class DisposableMutationCandidateTests(unittest.TestCase):
    def _open_windows_shared_writer(self, path):
        if os.name != "nt":
            self.skipTest("Windows-only shared-handle fixture")

        import ctypes
        from ctypes import wintypes

        create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        handle = create_file(
            str(path),
            0x40000000,  # GENERIC_WRITE
            0x1 | 0x2 | 0x4,  # FILE_SHARE_READ | WRITE | DELETE
            None,
            3,  # OPEN_EXISTING
            0,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle == invalid:
            raise OSError(ctypes.get_last_error(), "CreateFileW writer fixture failed")
        return handle

    def _write_windows_handle(self, handle, data):
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        set_pointer = kernel32.SetFilePointerEx
        set_pointer.argtypes = [
            wintypes.HANDLE, ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
        ]
        set_pointer.restype = wintypes.BOOL
        write_file = kernel32.WriteFile
        write_file.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        write_file.restype = wintypes.BOOL
        set_eof = kernel32.SetEndOfFile
        set_eof.argtypes = [wintypes.HANDLE]
        set_eof.restype = wintypes.BOOL
        flush = kernel32.FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL

        position = ctypes.c_longlong()
        if not set_pointer(handle, 0, ctypes.byref(position), 0):
            raise OSError(ctypes.get_last_error(), "SetFilePointerEx writer failed")
        buffer = ctypes.create_string_buffer(data)
        written = wintypes.DWORD()
        if not write_file(
            handle, buffer, len(data), ctypes.byref(written), None
        ):
            raise OSError(ctypes.get_last_error(), "WriteFile fixture failed")
        if int(written.value) != len(data):
            raise OSError("short_write_in_windows_fixture")
        if not set_eof(handle):
            raise OSError(ctypes.get_last_error(), "SetEndOfFile fixture failed")
        if not flush(handle):
            raise OSError(ctypes.get_last_error(), "FlushFileBuffers fixture failed")

    def _close_windows_handle(self, handle):
        import ctypes
        from ctypes import wintypes

        close = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        if not close(handle):
            raise OSError(ctypes.get_last_error(), "CloseHandle fixture failed")

    def setUp(self):
        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        plugin._APPROVAL_ATTEMPTS.clear()
        plugin._CANDIDATE_CONSUMED_PLANS.clear()

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.inbox = self.root / "inbox"
        self.recovery = self.root / "recovery"
        for path in (self.vault, self.inbox, self.recovery):
            path.mkdir()

        self.env = patch.dict(os.environ, {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(self.recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _edit_preview(self, before=b"before\n", after="after\n"):
        note = self.vault / "note.md"
        note.write_bytes(before)
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": after,
        }))
        self.assertTrue(preview["success"])
        return note, preview

    def _draft_preview(self, target="Folder/draft.md"):
        (self.vault / "Folder").mkdir(exist_ok=True)
        draft = self.inbox / "draft.md"
        draft.write_bytes(
            b"---\r\norion_draft: true\r\nstatus: draft\r\n---\r\nbody"
        )
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md",
            "target_relative_path": target,
        }))
        self.assertTrue(preview["success"])
        return draft, self.vault / Path(target), preview

    def test_candidate_rejects_live_default_root_identity(self):
        with patch.dict(os.environ, {
            "ORION_VAULT_ROOT": plugin.DEFAULT_VAULT_ROOT,
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(self.recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        }):
            with self.assertRaisesRegex(RuntimeError, "live_vault_root_overlap_rejected"):
                plugin._candidate_disposable_roots()

    def test_candidate_rejects_ancestor_descendant_overlap_with_live_roots(self):
        cases = [
            ("ORION_VAULT_ROOT", r"C:\\Personal", "live_vault_root_overlap_rejected"),
            ("ORION_VAULT_ROOT", r"C:\\Personal\\Me\\fixture", "live_vault_root_overlap_rejected"),
            ("ORION_INBOX_ROOT", r"C:\\Personal", "live_inbox_root_overlap_rejected"),
            ("ORION_INBOX_ROOT", r"C:\\Personal\\Orion-Inbox\\fixture", "live_inbox_root_overlap_rejected"),
            (plugin.RECOVERY_ROOT_ENV, r"C:\\Personal\\Me\\recovery", "live_recovery_root_overlap_rejected"),
        ]
        base = {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(self.recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        }
        for key, value, error in cases:
            with self.subTest(key=key, value=value):
                env = dict(base)
                env[key] = value
                with patch.dict(os.environ, env):
                    with self.assertRaisesRegex(RuntimeError, error):
                        plugin._candidate_disposable_roots()

    def test_candidate_rechecks_resolved_parent_alias_against_protected_root(self):
        protected_parent = self.root / "protected-parent"
        protected_vault = protected_parent / "vault"
        protected_parent.mkdir()
        protected_vault.mkdir()
        alias_parent = self.root / "alias-parent"

        created = False
        try:
            os.symlink(protected_parent, alias_parent, target_is_directory=True)
            created = True
        except (OSError, NotImplementedError):
            if os.name == "nt":
                proc = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J",
                     str(alias_parent), str(protected_parent)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
                created = proc.returncode == 0
        if not created:
            self.skipTest("Platform did not permit a parent symlink/junction fixture")

        with patch.object(plugin, "DEFAULT_VAULT_ROOT", str(protected_vault)):
            with patch.dict(os.environ, {
                "ORION_VAULT_ROOT": str(alias_parent / "vault"),
                "ORION_INBOX_ROOT": str(self.inbox),
                plugin.RECOVERY_ROOT_ENV: str(self.recovery),
                plugin.DISPOSABLE_MUTATION_FLAG: "1",
            }):
                with self.assertRaisesRegex(
                    RuntimeError, "resolved_live_vault_overlap_rejected"
                ):
                    plugin._candidate_disposable_roots()

    def test_candidate_requires_recovery_root_disjoint_from_data_roots(self):
        nested = self.vault / "recovery"
        nested.mkdir()
        with patch.dict(os.environ, {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(nested),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        }):
            with self.assertRaisesRegex(RuntimeError, "recovery_root_must_be_disjoint"):
                plugin._candidate_disposable_roots()

    def test_candidate_is_not_registered_and_requires_disposable_opt_in(self):
        class Context:
            def __init__(self):
                self.tools = {}

            def register_tool(self, *, name, handler, **_kwargs):
                self.tools[name] = handler

            def register_hook(self, *_args, **_kwargs):
                pass

        ctx = Context()
        plugin.register(ctx)
        self.assertIs(ctx.tools[plugin.APPLY_TOOL], plugin.apply_plan_placeholder)

        note, preview = self._edit_preview()
        with patch.dict(os.environ, {plugin.DISPOSABLE_MUTATION_FLAG: "0"}):
            result = plugin._execute_disposable_plan_candidate(
                preview["plan_token"]
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "disposable_mutation_not_enabled")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")

    def test_edit_commit_creates_recovery_and_replay_fails(self):
        note, preview = self._edit_preview()
        token = preview["plan_token"]

        result = plugin._execute_disposable_plan_candidate(token)

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")
        recovery = Path(result["recovery_dir"])
        self.assertEqual((recovery / "original.bin").read_bytes(), b"before\n")
        manifest = json.loads((recovery / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "committed")
        self.assertEqual(manifest["plan_token"], token)

        replay = plugin._execute_disposable_plan_candidate(token)
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_edit_stale_hash_fails_before_recovery_or_mutation(self):
        note, preview = self._edit_preview()
        note.write_bytes(b"external change\n")

        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "stale_original_hash")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"external change\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_edit_failure_after_replace_preserves_original_recovery_bytes(self):
        note, preview = self._edit_preview()

        def fail(name):
            if name == "edit_after_replace":
                raise RuntimeError("simulated crash window")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(note.read_bytes(), b"after\n")
        recovery = Path(result["recovery_dir"])
        self.assertEqual((recovery / "original.bin").read_bytes(), b"before\n")
        self.assertEqual(
            json.loads((recovery / "manifest.json").read_text(encoding="utf-8"))["state"],
            "prepared",
        )

    def test_recovery_inspector_classifies_committed_edit(self):
        note, preview = self._edit_preview()
        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])
        self.assertTrue(result["success"])

        inspected = plugin._inspect_disposable_recovery_candidate(
            preview["plan_token"]
        )

        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["classification"], "committed")
        self.assertFalse(inspected["recovery_required"])
        self.assertFalse(inspected["mutation_performed"])
        self.assertEqual(inspected["target_sha256"], preview["plan"]["proposed_sha256"])
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_recovery_inspector_classifies_prepared_edit_without_effect(self):
        note, preview = self._edit_preview()

        def fail(name):
            if name == "edit_after_recovery":
                raise RuntimeError("simulated before replace")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )
        self.assertFalse(result["success"])

        inspected = plugin._inspect_disposable_recovery_candidate(
            preview["plan_token"]
        )

        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["classification"], "prepared_no_effect")
        self.assertFalse(inspected["recovery_required"])
        self.assertEqual(note.read_bytes(), b"before\n")

    def test_recovery_inspector_classifies_applied_unfinalized_edit(self):
        note, preview = self._edit_preview()

        def fail(name):
            if name == "edit_after_replace":
                raise RuntimeError("simulated after replace")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )
        self.assertFalse(result["success"])

        inspected = plugin._inspect_disposable_recovery_candidate(
            preview["plan_token"]
        )

        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["classification"], "applied_unfinalized")
        self.assertTrue(inspected["recovery_required"])
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_recovery_inspector_classifies_duplicate_unresolved_move(self):
        draft, target, preview = self._draft_preview()

        def fail(name):
            if name == "move_before_source_delete":
                raise RuntimeError("simulated duplicate state")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )
        self.assertFalse(result["success"])

        inspected = plugin._inspect_disposable_recovery_candidate(
            preview["plan_token"]
        )

        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["classification"], "duplicate_unresolved")
        self.assertTrue(inspected["recovery_required"])
        self.assertTrue(draft.exists())
        self.assertTrue(target.exists())

    def test_recovery_inspector_classifies_committed_move(self):
        draft, target, preview = self._draft_preview()
        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])
        self.assertTrue(result["success"])

        inspected = plugin._inspect_disposable_recovery_candidate(
            preview["plan_token"]
        )

        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["classification"], "committed")
        self.assertFalse(inspected["recovery_required"])
        self.assertFalse(draft.exists())
        self.assertTrue(target.exists())

    def test_recovery_inspector_rejects_corrupt_backup(self):
        _note, preview = self._edit_preview()

        def fail(name):
            if name == "edit_after_recovery":
                raise RuntimeError("prepared record")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )
        self.assertFalse(result["success"])
        recovery = Path(result["recovery_dir"])
        (recovery / "original.bin").write_bytes(b"corrupt")

        inspected = plugin._inspect_disposable_recovery_candidate(
            preview["plan_token"]
        )

        self.assertFalse(inspected["success"])
        self.assertEqual(inspected["error"], "recovery_backup_hash_mismatch")
        self.assertFalse(inspected["mutation_performed"])

    def test_restore_edit_preview_binds_recovery_current_hash_and_exact_diff(self):
        note, preview = self._edit_preview()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])
        note.write_bytes(b"later\n")

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )

        self.assertTrue(restore["success"])
        self.assertFalse(restore["mutation_performed"])
        self.assertEqual(restore["plan"]["action"], "restore_edit")
        self.assertEqual(
            restore["plan"]["recovery_id"], preview["plan_token"]
        )
        self.assertEqual(
            restore["plan"]["current_sha256"],
            plugin._sha_bytes(b"later\n"),
        )
        self.assertEqual(
            restore["plan"]["restore_sha256"],
            plugin._sha_bytes(b"before\n"),
        )
        self.assertIn("-later\n", restore["diff"])
        self.assertIn("+before\n", restore["diff"])
        self.assertEqual(note.read_bytes(), b"later\n")

        cached = plugin._lookup_preview(restore["plan_token"])
        summary = plugin._approval_summary(cached)
        self.assertIn("historical edit restore preview", summary)
        self.assertIn(preview["plan_token"], summary)
        self.assertIn(str(note.resolve(strict=True)), summary)
        self.assertIn(restore["diff"], summary)

    def test_restore_edit_revalidation_rejects_stale_current_content(self):
        note, preview = self._edit_preview()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )
        self.assertTrue(restore["success"])
        note.write_bytes(b"newer user edit\n")

        checked = plugin._revalidate_disposable_restore_preview(
            restore["plan_token"]
        )

        self.assertFalse(checked["success"])
        self.assertEqual(checked["error"], "restore_current_state_changed")
        self.assertEqual(note.read_bytes(), b"newer user edit\n")

    def test_windows_restore_edit_revalidation_rejects_same_bytes_replacement(self):
        if os.name != "nt":
            self.skipTest("Windows file identity is the hardening target")

        note, preview = self._edit_preview()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )
        self.assertTrue(restore["success"])
        self.assertIn("target_file_id", restore["plan"])

        replacement = self.vault / "replacement.md"
        replacement.write_bytes(note.read_bytes())
        os.replace(replacement, note)

        checked = plugin._revalidate_disposable_restore_preview(
            restore["plan_token"]
        )

        self.assertFalse(checked["success"])
        self.assertEqual(checked["error"], "restore_target_file_id_changed")
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_restore_preview_rejects_unresolved_prepared_record(self):
        _note, preview = self._edit_preview()

        def fail(name):
            if name == "edit_after_replace":
                raise RuntimeError("leave prepared record after protected effect")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )
        self.assertFalse(result["success"])

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )

        self.assertFalse(restore["success"])
        self.assertEqual(
            restore["error"], "historical_restore_requires_committed_record"
        )

    def test_restore_move_source_preview_is_creation_only_and_exact(self):
        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])
        target_before = target.read_bytes()

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )

        self.assertTrue(restore["success"])
        self.assertFalse(restore["mutation_performed"])
        self.assertEqual(
            restore["plan"]["action"], "restore_move_source"
        )
        self.assertEqual(restore["plan"]["source_state"], "absent")
        self.assertEqual(
            restore["plan"]["restore_sha256"],
            plugin._sha_bytes(source_bytes),
        )
        self.assertIn("--- /dev/null", restore["diff"])
        self.assertIn("+++ inbox/draft.md", restore["diff"])
        self.assertFalse(draft.exists())
        self.assertEqual(target.read_bytes(), target_before)

        cached = plugin._lookup_preview(restore["plan_token"])
        summary = plugin._approval_summary(cached)
        self.assertIn("historical move-source restore preview", summary)
        self.assertIn(preview["plan_token"], summary)
        self.assertIn(str(draft.resolve(strict=False)), summary)

        checked = plugin._revalidate_disposable_restore_preview(
            restore["plan_token"]
        )
        self.assertTrue(checked["success"])
        self.assertTrue(checked["valid"])
        self.assertFalse(draft.exists())
        self.assertEqual(target.read_bytes(), target_before)

    def test_restore_move_source_preview_does_not_require_reference_target_survival(self):
        draft, target, preview = self._draft_preview()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])
        target.unlink()

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )

        self.assertTrue(restore["success"])
        self.assertEqual(
            restore["plan"]["reference_target_state"], "absent"
        )
        self.assertIsNone(restore["plan"]["reference_target_sha256"])
        self.assertFalse(draft.exists())
        self.assertFalse(target.exists())

    def test_restore_move_source_revalidation_rejects_source_appearance(self):
        draft, _target, preview = self._draft_preview()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )
        self.assertTrue(restore["success"])
        draft.write_bytes(b"someone created this after preview\n")

        checked = plugin._revalidate_disposable_restore_preview(
            restore["plan_token"]
        )

        self.assertFalse(checked["success"])
        self.assertEqual(
            checked["error"], "restore_source_no_longer_absent"
        )
        self.assertEqual(
            draft.read_bytes(), b"someone created this after preview\n"
        )

    def test_restore_preview_cannot_execute_through_existing_mutators(self):
        note, preview = self._edit_preview()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])
        self.assertEqual(note.read_bytes(), b"after\n")

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )
        self.assertTrue(restore["success"])

        public_result = json.loads(plugin.apply_plan_placeholder({
            "plan_token": restore["plan_token"],
        }))
        self.assertFalse(public_result["success"])
        self.assertEqual(
            public_result["error"], "p5_01_mutation_not_authorized"
        )
        self.assertTrue(public_result["plan_known"])
        self.assertFalse(public_result["mutation_performed"])

        private_result = plugin._execute_disposable_plan_candidate(
            restore["plan_token"]
        )
        self.assertFalse(private_result["success"])
        self.assertEqual(private_result["error"], "unsupported_action")
        self.assertFalse(private_result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_restore_preview_rejects_corrupt_recovery_backup(self):
        _note, preview = self._edit_preview()
        committed = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )
        self.assertTrue(committed["success"])
        recovery = Path(committed["recovery_dir"])
        (recovery / "original.bin").write_bytes(b"corrupt")

        restore = plugin._preview_disposable_restore_candidate(
            preview["plan_token"]
        )

        self.assertFalse(restore["success"])
        self.assertEqual(
            restore["error"], "recovery_backup_hash_mismatch"
        )
        self.assertFalse(restore["mutation_performed"])

    def test_move_commit_is_exclusive_verified_and_replay_fails(self):
        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()

        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertFalse(draft.exists())
        self.assertEqual(target.read_bytes(), source_bytes)
        recovery = Path(result["recovery_dir"])
        self.assertEqual((recovery / "source.bin").read_bytes(), source_bytes)
        self.assertEqual(
            json.loads((recovery / "manifest.json").read_text(encoding="utf-8"))["state"],
            "committed",
        )

        replay = plugin._execute_disposable_plan_candidate(preview["plan_token"])
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")
        self.assertEqual(target.read_bytes(), source_bytes)

    def test_move_target_race_fails_without_touching_source(self):
        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()
        target.write_bytes(b"someone else won\n")

        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "target_already_exists")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertEqual(target.read_bytes(), b"someone else won\n")

    def test_move_source_change_after_target_create_cleans_our_target(self):
        draft, target, preview = self._draft_preview()

        if os.name == "nt":
            blocked = {"value": False}

            def change_source(name):
                if name == "move_after_target_create":
                    try:
                        draft.write_bytes(b"external source change\n")
                    except OSError:
                        blocked["value"] = True

            result = plugin._execute_disposable_plan_candidate(
                preview["plan_token"], failure_hook=change_source
            )

            self.assertTrue(blocked["value"])
            self.assertTrue(result["success"])
            self.assertFalse(draft.exists())
            self.assertTrue(target.is_file())
            return

        def change_source(name):
            if name == "move_after_target_create":
                draft.write_bytes(b"external source change\n")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=change_source
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "source_changed_before_delete")
        self.assertTrue(result["mutation_performed"])
        self.assertFalse(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), b"external source change\n")
        self.assertFalse(target.exists())
        self.assertTrue(Path(result["recovery_dir"], "source.bin").is_file())

    def test_windows_move_binds_file_id_and_rejects_same_bytes_replacement(self):
        if os.name != "nt":
            self.skipTest("Windows file identity is the hardening target")

        draft, target, preview = self._draft_preview()
        self.assertIn("source_file_id", preview["plan"])
        original_bytes = draft.read_bytes()
        replacement = self.inbox / "replacement.md"
        replacement.write_bytes(original_bytes)
        os.replace(replacement, draft)

        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "source_file_id_changed")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(draft.read_bytes(), original_bytes)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_windows_move_refuses_preexisting_writer_before_mutation(self):
        if os.name != "nt":
            self.skipTest("Windows shared-handle fixture")

        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()
        writer = self._open_windows_shared_writer(draft)

        try:
            result = plugin._execute_disposable_plan_candidate(
                preview["plan_token"]
            )
        finally:
            self._close_windows_handle(writer)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "source_handle_unavailable")
        self.assertFalse(result["mutation_performed"])
        self.assertFalse(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_windows_move_failure_after_delete_mark_stays_recovery_required(self):
        if os.name != "nt":
            self.skipTest("Windows handle-delete checkpoint")

        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()

        def fail(name):
            if name == "move_after_delete_mark":
                raise RuntimeError("simulated interruption after delete mark")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        # The finally/exception cleanup closes the marked handle, so Windows
        # may have completed the delete even though the operation did not get
        # far enough to record a committed manifest.
        self.assertFalse(draft.exists())
        self.assertEqual(target.read_bytes(), source_bytes)
        self.assertEqual(
            json.loads(Path(result["recovery_dir"], "manifest.json").read_text(
                encoding="utf-8"
            ))["state"],
            "prepared",
        )

    def test_move_failure_before_source_delete_reports_recovery_state(self):
        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()

        def fail(name):
            if name == "move_before_source_delete":
                raise RuntimeError("simulated interruption")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertEqual(target.read_bytes(), source_bytes)
        self.assertTrue(Path(result["recovery_dir"], "source.bin").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
