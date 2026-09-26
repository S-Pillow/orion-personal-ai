#!/usr/bin/env python3
"""Read-only P5-03A2 candidate review.

This script:
- imports the local source candidate patcher;
- generates the planned combined api_server.py in memory;
- verifies its exact SHA-256;
- prints the exact unified diff;
- performs structural AST/text assertions on the planned source;
- exercises Hermes' native approval primitives with synthetic in-process
  run keys only (no Hermes server, no vault, no protected action).

It never writes the installed Hermes source.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import importlib.util
import sys
import threading
from pathlib import Path

EXPECTED_POST_SHA256 = "7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84"
RUN_A = "orion-p5-03a2-review-run-a"
RUN_B = "orion-p5-03a2-review-run-b"
RUN_C = "orion-p5-03a2-review-run-c"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_patcher(path: Path):
    spec = importlib.util.spec_from_file_location("orion_p5_03a2_patcher", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load patcher: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_async_method(tree: ast.AST, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise RuntimeError(f"planned source missing async method {name}")


def call_names(node: ast.AST) -> list[str]:
    out: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            fn = child.func
            if isinstance(fn, ast.Name):
                out.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                parts = []
                cur = fn
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                out.append(".".join(reversed(parts)))
    return out


def structural_checks(planned: str) -> None:
    tree = ast.parse(planned, filename="planned_api_server.py")

    run_agent = find_async_method(tree, "_run_agent")
    arg_names = [a.arg for a in run_agent.args.args]
    for required in ("approval_notify_callback", "approval_session_key", "approval_cancel_event"):
        if required not in arg_names:
            raise RuntimeError(f"_run_agent missing {required}")

    run_segment = ast.get_source_segment(planned, run_agent) or ""
    for marker in (
        "approval_cancelled = False",
        "approval_cancel_event is not None and approval_cancel_event.is_set()",
        "approval_cancelled = True",
        "session chat disconnected before approval-safe agent execution",
    ):
        if marker not in run_segment:
            raise RuntimeError(f"_run_agent late-registration guard missing marker: {marker}")

    abort_pos = run_segment.find("if approval_cancelled:")
    run_pos = run_segment.find("result = agent.run_conversation(")
    if abort_pos < 0 or run_pos < 0 or abort_pos > run_pos:
        raise RuntimeError(
            "disconnect cancellation does not abort before agent.run_conversation"
        )

    calls = call_names(run_agent)
    for required in (
        "register_gateway_notify",
        "set_current_session_key",
        "unregister_gateway_notify",
        "reset_current_session_key",
        "agent.run_conversation",
    ):
        if required not in calls:
            raise RuntimeError(f"_run_agent planned source missing call: {required}")

    session = find_async_method(tree, "_handle_session_chat_stream")
    session_calls = call_names(session)
    if "self._run_agent" not in session_calls:
        raise RuntimeError("session-chat no longer calls self._run_agent")
    if "unregister_gateway_notify" not in session_calls:
        raise RuntimeError("session-chat terminal cleanup lacks native unregister")

    segment = ast.get_source_segment(planned, session) or ""
    required_session_text = (
        "self._run_approval_sessions[run_id] = run_id",
        "approval_notify_callback=_approval_notify",
        "approval_session_key=run_id",
        "approval_cancel_event = threading.Event()",
        "approval_cancel_event=approval_cancel_event",
        "session chat approval transport disconnected",
        'event": "approval.request"',
        '"waiting_for_approval"',
        "self._run_approval_sessions.pop(run_id, None)",
    )
    for marker in required_session_text:
        if marker not in segment:
            raise RuntimeError(f"session-chat planned source missing marker: {marker}")

    disconnect_calls = [
        node for node in ast.walk(session)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_drain_session_stream_task_on_disconnect"
    ]
    if len(disconnect_calls) != 2:
        raise RuntimeError(
            f"expected two session disconnect drain calls, found {len(disconnect_calls)}"
        )
    for call in disconnect_calls:
        if "approval_cancel_event" not in {kw.arg for kw in call.keywords}:
            raise RuntimeError("session disconnect drain call lacks approval_cancel_event")

    drain = find_async_method(tree, "_drain_session_stream_task_on_disconnect")
    drain_segment = ast.get_source_segment(planned, drain) or ""
    cancel_pos = drain_segment.find("approval_cancel_event.set()")
    unregister_pos = drain_segment.find("unregister_gateway_notify(run_id)")
    agent_pos = drain_segment.find("agent = self._active_run_agents.get(run_id)")
    if (
        cancel_pos < 0
        or unregister_pos < 0
        or agent_pos < 0
        or not (cancel_pos < unregister_pos < agent_pos)
    ):
        raise RuntimeError(
            "disconnect drain must mark cancellation, unregister approval, then enter agent/task wait path"
        )

    print("P5_03A2_STRUCTURAL_REVIEW=PASS")
    print("P5_03A2_LATE_REGISTRATION_GUARD=PASS")
    print("P5_03A2_DISCONNECT_ABORT_BEFORE_RUN=PASS")


def native_approval_isolation_probe() -> None:
    from tools import approval

    # Pinned Hermes v0.20.6 defines _ApprovalEntry directly in tools.approval.
    # A later upstream refactor moved it into tools.approval_gateway_wait;
    # this review must follow the installed pinned source, not current main.
    _ApprovalEntry = approval._ApprovalEntry

    # Process-local cleanup only. Hermes server is not running.
    approval.unregister_gateway_notify(RUN_A)
    approval.unregister_gateway_notify(RUN_B)
    approval.unregister_gateway_notify(RUN_C)

    try:
        callbacks: dict[str, list[dict]] = {RUN_A: [], RUN_B: []}
        approval.register_gateway_notify(
            RUN_A, lambda data: callbacks[RUN_A].append(dict(data or {}))
        )
        approval.register_gateway_notify(
            RUN_B, lambda data: callbacks[RUN_B].append(dict(data or {}))
        )

        a = _ApprovalEntry({"request_id": "a-1", "command": "synthetic-a"})
        b = _ApprovalEntry({"request_id": "b-1", "command": "synthetic-b"})
        with approval._lock:
            approval._gateway_queues[RUN_A] = [a]
            approval._gateway_queues[RUN_B] = [b]

        resolved_a = approval.resolve_gateway_approval(RUN_A, "once")
        if resolved_a != 1:
            raise RuntimeError(f"run A resolution count was {resolved_a}, expected 1")
        if not a.event.is_set() or a.result != "once":
            raise RuntimeError(
                "run A approval entry did not receive the expected once decision"
            )
        if b.event.is_set() or b.result is not None:
            raise RuntimeError("resolving run A leaked into run B")
        if approval.list_gateway_approvals(RUN_B) != [
            {"request_id": "b-1", "command": "synthetic-b"}
        ]:
            raise RuntimeError("run B pending approval was altered by run A resolution")

        approval.unregister_gateway_notify(RUN_B)
        if not b.event.is_set():
            raise RuntimeError("unregister did not wake run B blocked approval entry")
        if approval.list_gateway_approvals(RUN_B):
            raise RuntimeError("unregister did not clear run B approval queue")

        token_a = approval.set_current_session_key(RUN_A)
        try:
            if approval.get_current_session_key() != RUN_A:
                raise RuntimeError("approval context did not bind run A")
            token_b = approval.set_current_session_key(RUN_B)
            try:
                if approval.get_current_session_key() != RUN_B:
                    raise RuntimeError("nested approval context did not bind run B")
            finally:
                approval.reset_current_session_key(token_b)
            if approval.get_current_session_key() != RUN_A:
                raise RuntimeError(
                    "approval context did not restore run A after nested reset"
                )
        finally:
            approval.reset_current_session_key(token_a)

        cancel_event = threading.Event()

        # Disconnect-before-register: pre-check must suppress registration.
        cancel_event.set()
        registered = False
        if not cancel_event.is_set():
            approval.register_gateway_notify(RUN_C, lambda _data: None)
            registered = True
            if cancel_event.is_set():
                approval.unregister_gateway_notify(RUN_C)
                registered = False
        with approval._lock:
            if RUN_C in approval._gateway_notify_cbs:
                raise RuntimeError("pre-cancelled run registered an approval callback")

        # Disconnect racing immediately after register: post-check must remove it.
        cancel_event.clear()
        if not cancel_event.is_set():
            approval.register_gateway_notify(RUN_C, lambda _data: None)
            registered = True
            cancel_event.set()
            if cancel_event.is_set():
                approval.unregister_gateway_notify(RUN_C)
                registered = False
        with approval._lock:
            if RUN_C in approval._gateway_notify_cbs:
                raise RuntimeError("late-registration race left an approval callback")
        if registered:
            raise RuntimeError("late-registration guard retained registered state")

        print("P5_03A2_NATIVE_APPROVAL_ISOLATION=PASS")
        print("P5_03A2_NATIVE_UNREGISTER_WAKE=PASS")
        print("P5_03A2_NATIVE_CONTEXT_SCOPE=PASS")
        # A callback captured before disconnect must fail closed if invoked
        # after disconnect. Hermes' native wait path must convert that notify
        # failure into a nonblocking refusal and remove the synthetic queue entry.
        stale_callback_cancel = threading.Event()
        stale_callback_cancel.set()

        def _stale_captured_notify(_data):
            if stale_callback_cancel.is_set():
                raise RuntimeError("session chat approval transport disconnected")

        decision = approval._await_gateway_decision(
            RUN_C,
            _stale_captured_notify,
            {
                "command": "synthetic-after-disconnect",
                "description": "synthetic approval after disconnect",
                "pattern_key": "synthetic-after-disconnect",
                "pattern_keys": ["synthetic-after-disconnect"],
            },
        )
        if not decision.get("notify_failed") or decision.get("resolved"):
            raise RuntimeError(
                "stale captured approval callback did not fail closed without blocking"
            )
        if approval.list_gateway_approvals(RUN_C):
            raise RuntimeError(
                "stale captured approval callback left a pending approval entry"
            )

        print("P5_03A2_NATIVE_LATE_REGISTRATION_GUARD=PASS")
        print("P5_03A2_NATIVE_POST_DISCONNECT_NOTIFY_FAIL_CLOSED=PASS")
    finally:
        # Always remove synthetic process-local probe state, including on
        # assertion failure. This process exits after the review either way.
        approval.unregister_gateway_notify(RUN_A)
        approval.unregister_gateway_notify(RUN_B)
        approval.unregister_gateway_notify(RUN_C)


def failed_apply_cleanup_probe(patcher) -> None:
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
    cleaned = patcher._cleanup_failed_apply_sidecars_if_base_unchanged(
        target, backup, manifest, sha256(pre)
    )
    if not cleaned or backup.is_file() or manifest.is_file():
        raise RuntimeError("failed-apply cleanup did not remove sidecars for unchanged target")

    target = _FakePath(b"changed")
    backup = _FakePath(b"backup")
    manifest = _FakePath(b"manifest")
    cleaned = patcher._cleanup_failed_apply_sidecars_if_base_unchanged(
        target, backup, manifest, sha256(pre)
    )
    if cleaned or not backup.is_file() or not manifest.is_file():
        raise RuntimeError("failed-apply cleanup removed recovery sidecars after target change")

    print("P5_03A2_FAILED_APPLY_SIDECAR_CLEANUP=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--patcher", type=Path, required=True)
    args = parser.parse_args()

    try:
        original_bytes = args.target.read_bytes()
        original = original_bytes.decode("utf-8")

        patcher = load_patcher(args.patcher)
        planned = patcher.patch_text(original)
        planned_bytes = planned.encode("utf-8")
        post_sha = sha256(planned_bytes)

        if post_sha != EXPECTED_POST_SHA256:
            raise RuntimeError(
                f"planned post SHA drift: expected {EXPECTED_POST_SHA256}, observed {post_sha}"
            )

        structural_checks(planned)
        native_approval_isolation_probe()
        failed_apply_cleanup_probe(patcher)

        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                planned.splitlines(keepends=True),
                fromfile="installed/P4-04A/api_server.py",
                tofile="planned/P5-03A2/api_server.py",
                n=5,
            )
        )
        if not diff:
            raise RuntimeError("planned source diff is unexpectedly empty")

        print(f"P5_03A2_REVIEW_ORIGINAL_SHA256={sha256(original_bytes)}")
        print(f"P5_03A2_REVIEW_PLANNED_SHA256={post_sha}")
        print(f"P5_03A2_REVIEW_DIFF_LINES={len(diff.splitlines())}")
        print("P5_03A2_REVIEW_DIFF_BEGIN")
        print(diff, end="" if diff.endswith("\n") else "\n")
        print("P5_03A2_REVIEW_DIFF_END")
        print("P5_03A2_VAULT_READ=false")
        print("P5_03A2_VAULT_MUTATION=false")
        print("P5_03A2_HERMES_STARTED=false")
        print("P5_03A2_APPROVAL_REQUESTED=false")
        print("P5_03A2_PROTECTED_ACTION_EXECUTED=false")
        print("P5_03A2_INSTALLED_SOURCE_CHANGED=false")
        print("P5_03A2_READONLY_REVIEW=PASS")
        return 0
    except Exception as exc:
        print(f"P5_03A2_READONLY_REVIEW=FAIL", file=sys.stderr)
        print(f"P5_03A2_REVIEW_EXCEPTION={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
