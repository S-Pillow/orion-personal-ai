#!/usr/bin/env python3
'''P5-03A2 narrow Hermes session-chat approval compatibility patcher.

Target:
  Hermes v0.20.6 / v2026.8.27
  commit 5fc308a70719a83cccdbba4c0e39c23f5a8239d5
  installed on top of accepted ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1

This patch does not create a new approval engine. It backports only the
approval-session-key + gateway-notify seam needed for
/api/sessions/{session_id}/chat/stream to participate in Hermes' existing
/v1/runs/{run_id}/approval authority path.
'''
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

PATCH_ID = "ORION-P5-03A2-SESSION-CHAT-APPROVAL-COMPAT-v1"
ACCEPTED_HERMES_COMMIT = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
EXPECTED_P4_LIVE_SHA256 = "ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888"
EXPECTED_P4_BACKUP_SHA256 = "8d87036dd488cb811dbabb7048102d0c28fbf54e0e658c464683000118537ec3"
EXPECTED_P4_PATCH_ID = "ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1"
EXPECTED_POST_SHA256 = "eff097373cb1fe91f2f82236f8111501c35ed08cd648b4fe4b435e5a335df41f"

SIG_OLD = '''        confirmed_runtime_lock: bool = False,
    ) -> tuple:
'''
SIG_NEW = '''        confirmed_runtime_lock: bool = False,
        approval_notify_callback=None,
        approval_session_key: Optional[str] = None,
        approval_cancel_event=None,
    ) -> tuple:
'''

RUN_CALL_OLD = '''                    result = agent.run_conversation(
                        user_message=user_message,
                        conversation_history=conversation_history,
                        task_id=effective_task_id,
                    )
                    usage = {
'''

RUN_CALL_NEW = '''                    # ORION-P5-03A2-SESSION-CHAT-APPROVAL-COMPAT-v1
                    # Keep conversation/memory scope separate from approval authority.
                    # The run-scoped approval key is a contextvar visible only to this
                    # executor turn, and Hermes' existing approval registry remains the
                    # sole resolver used by POST /v1/runs/{run_id}/approval.
                    approval_token = None
                    approval_registered = False
                    approval_cancelled = False
                    if approval_notify_callback is not None and approval_session_key:
                        from tools.approval import (
                            register_gateway_notify,
                            reset_current_session_key,
                            set_current_session_key,
                            unregister_gateway_notify,
                        )
                        approval_token = set_current_session_key(approval_session_key)
                        try:
                            # Disconnect may win before this worker reaches registration.
                            # Check both before and after registration so the late-register
                            # race cannot strand a callback or a blocking approval wait.
                            if approval_cancel_event is not None and approval_cancel_event.is_set():
                                approval_cancelled = True
                            else:
                                register_gateway_notify(
                                    approval_session_key,
                                    approval_notify_callback,
                                )
                                approval_registered = True
                                if approval_cancel_event is not None and approval_cancel_event.is_set():
                                    unregister_gateway_notify(approval_session_key)
                                    approval_registered = False
                                    approval_cancelled = True
                        except Exception:
                            try:
                                reset_current_session_key(approval_token)
                            finally:
                                approval_token = None
                            raise
                    try:
                        if approval_cancelled:
                            raise RuntimeError(
                                "session chat disconnected before approval-safe agent execution"
                            )
                        result = agent.run_conversation(
                            user_message=user_message,
                            conversation_history=conversation_history,
                            task_id=effective_task_id,
                        )
                    finally:
                        if approval_registered:
                            try:
                                unregister_gateway_notify(approval_session_key)
                            except Exception:
                                pass
                        if approval_token is not None:
                            try:
                                reset_current_session_key(approval_token)
                            except Exception:
                                pass
                    usage = {
'''

SESSION_HOOK_ANCHOR = '''        async def _run_and_signal() -> None:
'''

SESSION_HOOK = '''        # ORION-P5-03A2-SESSION-CHAT-APPROVAL-COMPAT-v1
        # Approval authorization is run-scoped, never session-scoped. Two
        # concurrent turns may share one Hermes session without sharing an
        # approval namespace.
        self._run_approval_sessions[run_id] = run_id
        approval_cancel_event = threading.Event()

        def _approval_notify(approval_data: Dict[str, Any]) -> None:
            event = dict(approval_data or {})
            if "command" in event:
                from gateway.run import _redact_approval_command

                event["command"] = _redact_approval_command(event.get("command"))
            event.update({
                "event": "approval.request",
                "message_id": message_id,
                "timestamp": time.time(),
                "choices": _approval_event_choices(
                    smart_denied=bool(event.get("smart_denied")),
                    allow_session=event.get("allow_session") is not False,
                    allow_permanent=event.get("allow_permanent") is not False,
                ),
            })
            self._set_run_status(
                run_id,
                "waiting_for_approval",
                last_event="approval.request",
            )
            _enqueue("approval.request", event)

        async def _run_and_signal() -> None:
'''

SESSION_CALL_OLD = '''                    active_run_id=run_id,
                    gateway_session_key=gateway_session_key,
                    route=route,
'''

SESSION_CALL_NEW = '''                    active_run_id=run_id,
                    gateway_session_key=gateway_session_key,
                    approval_notify_callback=_approval_notify,
                    approval_session_key=run_id,
                    approval_cancel_event=approval_cancel_event,
                    route=route,
'''

SESSION_CLEANUP_OLD = '''            finally:
                self._active_run_agents.pop(run_id, None)
                await queue.put(_event_payload("done", {}))
'''

SESSION_CLEANUP_NEW = '''            finally:
                self._active_run_agents.pop(run_id, None)
                # Async-wrapper cleanup must also wake approval waits. A
                # run_in_executor worker can otherwise remain blocked after
                # task cancellation/disconnect and never reach its own finally.
                try:
                    from tools.approval import unregister_gateway_notify

                    unregister_gateway_notify(run_id)
                except Exception:
                    pass
                self._run_approval_sessions.pop(run_id, None)
                await queue.put(_event_payload("done", {}))
'''

DISCONNECT_CALL_RESET_OLD = '''            await self._drain_session_stream_task_on_disconnect(
                run_id, task, interrupt_message="SSE client disconnected", shield_wait=False
            )
'''

DISCONNECT_CALL_RESET_NEW = '''            await self._drain_session_stream_task_on_disconnect(
                run_id, task, interrupt_message="SSE client disconnected", shield_wait=False,
                approval_cancel_event=approval_cancel_event,
            )
'''

DISCONNECT_CALL_CANCEL_OLD = '''            await self._drain_session_stream_task_on_disconnect(
                run_id, task, interrupt_message="SSE task cancelled", shield_wait=True
            )
'''

DISCONNECT_CALL_CANCEL_NEW = '''            await self._drain_session_stream_task_on_disconnect(
                run_id, task, interrupt_message="SSE task cancelled", shield_wait=True,
                approval_cancel_event=approval_cancel_event,
            )
'''

DISCONNECT_OLD = '''        shield_wait: bool,
    ) -> None:
        """Preserve live run control refs until the executor-backed turn actually exits."""
        agent = self._active_run_agents.get(run_id)
'''

DISCONNECT_NEW = '''        shield_wait: bool,
        approval_cancel_event=None,
    ) -> None:
        """Preserve live run control refs until the executor-backed turn actually exits."""
        # ORION-P5-03A2-SESSION-CHAT-APPROVAL-COMPAT-v1
        # Mark disconnect before unregistering. The worker checks this event
        # both before and after callback registration, closing the race where
        # registration happens just after an early unregister no-op.
        if approval_cancel_event is not None:
            approval_cancel_event.set()
        try:
            from tools.approval import unregister_gateway_notify

            unregister_gateway_notify(run_id)
        except Exception:
            pass
        agent = self._active_run_agents.get(run_id)
'''


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_text(source: str) -> str:
    if PATCH_ID in source:
        return source

    out = _replace_once(source, SIG_OLD, SIG_NEW, "_run_agent signature")
    out = _replace_once(out, RUN_CALL_OLD, RUN_CALL_NEW, "_run_agent approval scope")
    out = _replace_once(out, SESSION_HOOK_ANCHOR, SESSION_HOOK, "session-chat approval hook")
    out = _replace_once(out, SESSION_CALL_OLD, SESSION_CALL_NEW, "session-chat _run_agent call")
    out = _replace_once(out, SESSION_CLEANUP_OLD, SESSION_CLEANUP_NEW, "session-chat approval cleanup")
    out = _replace_once(out, DISCONNECT_CALL_RESET_OLD, DISCONNECT_CALL_RESET_NEW, "session-chat reset disconnect guard")
    out = _replace_once(out, DISCONNECT_CALL_CANCEL_OLD, DISCONNECT_CALL_CANCEL_NEW, "session-chat cancelled disconnect guard")
    out = _replace_once(out, DISCONNECT_OLD, DISCONNECT_NEW, "session-chat disconnect approval cleanup")
    compile(out, "api_server.py", "exec")
    return out


def required_markers() -> list[str]:
    return [
        PATCH_ID,
        "approval_notify_callback=None",
        "approval_session_key: Optional[str] = None",
        "approval_cancel_event=None",
        "from tools.approval import (",
        "register_gateway_notify(",
        "set_current_session_key(approval_session_key)",
        "unregister_gateway_notify(approval_session_key)",
        "reset_current_session_key(approval_token)",
        "self._run_approval_sessions[run_id] = run_id",
        "approval_notify_callback=_approval_notify",
        "approval_session_key=run_id",
        "approval_cancel_event=approval_cancel_event",
        "approval_cancel_event = threading.Event()",
        "approval_cancel_event.is_set()",
        "approval_cancelled = True",
        "session chat disconnected before approval-safe agent execution",
        "approval_cancel_event.set()",
        "self._run_approval_sessions.pop(run_id, None)",
        "unregister_gateway_notify(run_id)",
        "registration happens just after an early unregister no-op",
        '"event": "approval.request"',
        '"waiting_for_approval"',
    ]


def verify_patched_text(text: str) -> list[str]:
    return [m for m in required_markers() if m not in text]


def _sidecars(target: Path) -> tuple[Path, Path]:
    return (
        target.with_name(target.name + ".orion-p5-03a2-approval-compat.bak"),
        target.with_name(target.name + ".orion-p5-03a2-approval-compat.json"),
    )


def _p4_sidecars(target: Path) -> tuple[Path, Path]:
    return (
        target.with_name(target.name + ".orion-p4-04a.bak"),
        target.with_name(target.name + ".orion-p4-04a.json"),
    )


def verify_p4_base(target: Path) -> None:
    live = target.read_bytes()
    if sha256(live) != EXPECTED_P4_LIVE_SHA256:
        raise RuntimeError(
            "accepted P4-04A live target SHA mismatch; refusing P5-03A2 patch"
        )

    p4_backup, p4_manifest = _p4_sidecars(target)
    if not p4_backup.is_file() or not p4_manifest.is_file():
        raise RuntimeError("accepted P4-04A sidecars are missing")

    if sha256(p4_backup.read_bytes()) != EXPECTED_P4_BACKUP_SHA256:
        raise RuntimeError("P4-04A backup SHA mismatch")

    meta = json.loads(p4_manifest.read_text(encoding="utf-8"))
    if meta.get("patch_id") != EXPECTED_P4_PATCH_ID:
        raise RuntimeError("P4-04A manifest patch id mismatch")
    if meta.get("accepted_hermes_commit") != ACCEPTED_HERMES_COMMIT:
        raise RuntimeError("P4-04A manifest Hermes commit mismatch")
    if str(meta.get("pre_sha256", "")).lower() != EXPECTED_P4_BACKUP_SHA256:
        raise RuntimeError("P4-04A manifest pre SHA mismatch")
    if str(meta.get("post_sha256", "")).lower() != EXPECTED_P4_LIVE_SHA256:
        raise RuntimeError("P4-04A manifest post SHA mismatch")


def plan(target: Path) -> int:
    verify_p4_base(target)
    source = target.read_text(encoding="utf-8")
    if PATCH_ID in source:
        raise RuntimeError("P5-03A2 patch marker already present; use --verify")
    patched = patch_text(source).encode("utf-8")
    missing = verify_patched_text(patched.decode("utf-8"))
    if missing:
        raise RuntimeError(f"planned source missing markers: {missing}")
    planned_sha = sha256(patched)
    if planned_sha != EXPECTED_POST_SHA256:
        raise RuntimeError(
            f"planned post SHA drift: expected {EXPECTED_POST_SHA256}, observed {planned_sha}"
        )
    print("P5-03A2 PLAN PASS")
    print(f"Target={target}")
    print(f"PreSha256={EXPECTED_P4_LIVE_SHA256}")
    print(f"PlannedPostSha256={planned_sha}")
    print("WritesPerformed=false")
    return 0


def _cleanup_failed_apply_sidecars_if_base_unchanged(
    target: Path, backup: Path, manifest: Path, pre_sha: str
) -> bool:
    """Remove P5 sidecars after a failed apply only if the live target stayed at pre-image."""
    try:
        if not target.is_file() or sha256(target.read_bytes()) != pre_sha:
            return False
    except OSError:
        return False

    cleaned = True
    for artifact in (backup, manifest):
        try:
            artifact.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            cleaned = False
    return cleaned


def apply_patch(target: Path) -> int:
    verify_p4_base(target)
    source_bytes = target.read_bytes()
    source = source_bytes.decode("utf-8")
    if PATCH_ID in source:
        raise RuntimeError("P5-03A2 patch marker already present; refusing ambiguous second apply")

    backup, manifest = _sidecars(target)
    if backup.exists() or manifest.exists():
        raise RuntimeError("P5-03A2 backup/manifest already exists; resolve before applying")

    patched_text = patch_text(source)
    missing = verify_patched_text(patched_text)
    if missing:
        raise RuntimeError(f"patched source verification failed; missing: {missing}")
    patched_bytes = patched_text.encode("utf-8")
    post_sha = sha256(patched_bytes)
    if post_sha != EXPECTED_POST_SHA256:
        raise RuntimeError(
            f"post-patch SHA drift: expected {EXPECTED_POST_SHA256}, observed {post_sha}"
        )

    pre_sha = sha256(source_bytes)
    metadata = {
        "patch_id": PATCH_ID,
        "accepted_hermes_commit": ACCEPTED_HERMES_COMMIT,
        "target": str(target),
        "pre_sha256": pre_sha,
        "post_sha256": post_sha,
        "rollback_restores": "accepted P4-04A patched state",
        "p4_patch_id": EXPECTED_P4_PATCH_ID,
        "p4_live_sha256": EXPECTED_P4_LIVE_SHA256,
        "p4_backup_sha256": EXPECTED_P4_BACKUP_SHA256,
        "backup": str(backup),
    }

    temp = target.with_name(target.name + ".orion-p5-03a2-approval-compat.tmp")
    try:
        backup.write_bytes(source_bytes)
        manifest.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        temp.write_bytes(patched_bytes)
        compile(temp.read_text(encoding="utf-8"), str(target), "exec")
        os.replace(temp, target)
    except Exception:
        # A target-replacement failure must not strand apparently-installed
        # P5 sidecars around an unchanged P4 target. Retain them only when the
        # target changed, where rollback evidence is more important than retry.
        _cleanup_failed_apply_sidecars_if_base_unchanged(
            target, backup, manifest, pre_sha
        )
        raise
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass

    if sha256(target.read_bytes()) != post_sha:
        raise RuntimeError("post-apply target SHA mismatch")

    print("P5-03A2 APPLY PASS")
    print(f"Target={target}")
    print(f"PreSha256={metadata['pre_sha256']}")
    print(f"PostSha256={post_sha}")
    print(f"Backup={backup}")
    return 0


def verify_target(target: Path) -> int:
    data = target.read_bytes()
    text = data.decode("utf-8")
    missing = verify_patched_text(text)
    if missing:
        if sha256(data) == EXPECTED_P4_LIVE_SHA256:
            print("P5-03A2 VERIFY: accepted P4-04A base is present; compatibility patch is not installed")
            print(f"Sha256={sha256(data)}")
            return 3
        raise RuntimeError(f"P5-03A2 patch verification failed; missing: {missing}")

    compile(text, str(target), "exec")
    backup, manifest = _sidecars(target)
    if not backup.is_file() or not manifest.is_file():
        raise RuntimeError("P5-03A2 patch markers exist but sidecars are missing")

    meta = json.loads(manifest.read_text(encoding="utf-8"))
    if meta.get("patch_id") != PATCH_ID:
        raise RuntimeError("P5-03A2 manifest patch id mismatch")
    if str(meta.get("pre_sha256", "")).lower() != EXPECTED_P4_LIVE_SHA256:
        raise RuntimeError("P5-03A2 manifest pre SHA is not accepted P4-04A state")
    if sha256(backup.read_bytes()) != EXPECTED_P4_LIVE_SHA256:
        raise RuntimeError("P5-03A2 backup does not preserve accepted P4-04A state")

    live_sha = sha256(data)
    if str(meta.get("post_sha256", "")).lower() != live_sha:
        raise RuntimeError("P5-03A2 live SHA does not match manifest post SHA")

    print("P5-03A2 VERIFY PASS")
    print(f"Target={target}")
    print(f"Sha256={live_sha}")
    print(f"RollbackSha256={EXPECTED_P4_LIVE_SHA256}")
    return 0


def rollback(target: Path) -> int:
    backup, manifest = _sidecars(target)
    if not backup.is_file() or not manifest.is_file():
        raise RuntimeError("P5-03A2 rollback backup or manifest is missing")

    meta = json.loads(manifest.read_text(encoding="utf-8"))
    if meta.get("patch_id") != PATCH_ID:
        raise RuntimeError("P5-03A2 rollback manifest patch id mismatch")

    original = backup.read_bytes()
    if sha256(original) != EXPECTED_P4_LIVE_SHA256:
        raise RuntimeError("P5-03A2 rollback backup is not the accepted P4-04A state")

    current = target.read_bytes()
    current_sha = sha256(current)
    if current_sha != str(meta.get("post_sha256", "")).lower():
        raise RuntimeError(
            "current target does not match P5-03A2 manifest post SHA; refusing destructive rollback"
        )
    if PATCH_ID not in current.decode("utf-8"):
        raise RuntimeError("target lacks P5-03A2 marker; refusing destructive rollback")

    temp = target.with_name(target.name + ".orion-p5-03a2-approval-compat.rollback.tmp")
    try:
        temp.write_bytes(original)
        os.replace(temp, target)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass

    verify_p4_base(target)
    backup.unlink()
    manifest.unlink()

    print("P5-03A2 ROLLBACK PASS")
    print(f"Target={target}")
    print(f"RestoredSha256={EXPECTED_P4_LIVE_SHA256}")
    print("RestoredState=accepted P4-04A patched Hermes")
    return 0


def self_test() -> int:
    fixture = (
        "from typing import Optional, Dict, Any\n"
        "import time\n"
        "class X:\n"
        "    async def _run_agent(\n"
        "        self,\n"
        "        user_message: str,\n"
        "        conversation_history: list,\n"
        "        ephemeral_system_prompt: Optional[str] = None,\n"
        "        session_id: Optional[str] = None,\n"
        "        stream_delta_callback=None,\n"
        "        tool_progress_callback=None,\n"
        "        tool_start_callback=None,\n"
        "        tool_complete_callback=None,\n"
        "        agent_ref: Optional[list] = None,\n"
        "        active_run_id: Optional[str] = None,\n"
        "        gateway_session_key: Optional[str] = None,\n"
        "        requested_model: Optional[str] = None,\n"
        "        requested_provider: Optional[str] = None,\n"
        "        model_options: Optional[Dict[str, Any]] = None,\n"
        "        route: Optional[Dict[str, Any]] = None,\n"
        "        session_model: Optional[str] = None,\n"
        "        requested_runtime: Optional[Dict[str, Any]] = None,\n"
        "        route_source: str = \"global\",\n"
        "        confirmed_runtime_lock: bool = False,\n"
        "    ) -> tuple:\n"
        "        def f():\n"
        "            agent = None\n"
        "            effective_task_id = session_id or \"x\"\n"
        "            if True:\n"
        "                if True:\n"
        "                    result = agent.run_conversation(\n"
        "                        user_message=user_message,\n"
        "                        conversation_history=conversation_history,\n"
        "                        task_id=effective_task_id,\n"
        "                    )\n"
        "                    usage = {\n"
        "                        \"input_tokens\": 0,\n"
        "                    }\n"
        "    async def _handle_session_chat_stream(self, request):\n"
        "        run_id = f\"run_x\"\n"
        "        message_id = f\"msg_x\"\n"
        "        def _enqueue(name, payload):\n"
        "            pass\n"
        "        def _tool_progress(event_type, tool_name=None, preview=None, args=None, **kwargs):\n"
        "            pass\n"
        "        async def _run_and_signal() -> None:\n"
        "            try:\n"
        "                result, usage = await self._run_agent(\n"
        "                    user_message=\"u\",\n"
        "                    conversation_history=[],\n"
        "                    active_run_id=run_id,\n"
        "                    gateway_session_key=gateway_session_key,\n"
        "                    route=route,\n"
        "                )\n"
        "            finally:\n"
        "                self._active_run_agents.pop(run_id, None)\n"
        "                await queue.put(_event_payload(\"done\", {}))\n"
        "        task = asyncio.create_task(_run_and_signal())\n"
        "        try:\n"
        "            pass\n"
        "        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):\n"
        "            await self._drain_session_stream_task_on_disconnect(\n"
        "                run_id, task, interrupt_message=\"SSE client disconnected\", shield_wait=False\n"
        "            )\n"
        "        except asyncio.CancelledError:\n"
        "            await self._drain_session_stream_task_on_disconnect(\n"
        "                run_id, task, interrupt_message=\"SSE task cancelled\", shield_wait=True\n"
        "            )\n"
        "    async def _drain_session_stream_task_on_disconnect(\n"
        "        self,\n"
        "        run_id: str,\n"
        "        task,\n"
        "        *,\n"
        "        interrupt_message: str,\n"
        "        shield_wait: bool,\n"
        "    ) -> None:\n"
        "        \"\"\"Preserve live run control refs until the executor-backed turn actually exits.\"\"\"\n"
        "        agent = self._active_run_agents.get(run_id)\n"
    )
    patched = patch_text(fixture)
    missing = verify_patched_text(patched)
    if missing:
        raise RuntimeError(f"self-test markers missing: {missing}")
    if patched.count(PATCH_ID) < 2:
        raise RuntimeError("self-test expected patch markers in both execution and session-stream seams")

    class _FakePath:
        def __init__(self, data: bytes = b"", exists: bool = True):
            self.data = data
            self.exists = exists

        def is_file(self) -> bool:
            return self.exists

        def read_bytes(self) -> bytes:
            if not self.exists:
                raise FileNotFoundError
            return self.data

        def unlink(self) -> None:
            if not self.exists:
                raise FileNotFoundError
            self.exists = False

    pre = b"accepted-p4"
    target = _FakePath(pre)
    backup = _FakePath(b"backup")
    manifest = _FakePath(b"manifest")
    if not _cleanup_failed_apply_sidecars_if_base_unchanged(
        target, backup, manifest, sha256(pre)
    ):
        raise RuntimeError("self-test expected unchanged-target sidecar cleanup")
    if backup.is_file() or manifest.is_file():
        raise RuntimeError("self-test failed to remove unchanged-target sidecars")

    changed_target = _FakePath(b"changed")
    changed_backup = _FakePath(b"backup")
    changed_manifest = _FakePath(b"manifest")
    if _cleanup_failed_apply_sidecars_if_base_unchanged(
        changed_target, changed_backup, changed_manifest, sha256(pre)
    ):
        raise RuntimeError("self-test must retain sidecars when target changed")
    if not changed_backup.is_file() or not changed_manifest.is_file():
        raise RuntimeError("self-test unexpectedly removed recovery sidecars")

    print("P5-03A2 SELF-TEST PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--self-test", action="store_true")
    action.add_argument("--plan", action="store_true")
    action.add_argument("--verify", action="store_true")
    action.add_argument("--apply", action="store_true")
    action.add_argument("--rollback", action="store_true")
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()

    try:
        if args.self_test:
            return self_test()
        if args.target is None:
            raise RuntimeError("--target is required for plan/verify/apply/rollback")
        target = args.target.resolve()
        if not target.is_file():
            raise RuntimeError(f"target file not found: {target}")
        if args.plan:
            return plan(target)
        if args.verify:
            return verify_target(target)
        if args.apply:
            return apply_patch(target)
        return rollback(target)
    except Exception as exc:
        print(f"P5-03A2 FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
