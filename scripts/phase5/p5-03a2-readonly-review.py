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
from pathlib import Path

EXPECTED_POST_SHA256 = "d8765b1842f54c340b1d5686355e2919d81313e20fdcbe7f6338321bf515e0aa"
RUN_A = "orion-p5-03a2-review-run-a"
RUN_B = "orion-p5-03a2-review-run-b"


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
    for required in ("approval_notify_callback", "approval_session_key"):
        if required not in arg_names:
            raise RuntimeError(f"_run_agent missing {required}")

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
        'event": "approval.request"',
        '"waiting_for_approval"',
        "self._run_approval_sessions.pop(run_id, None)",
    )
    for marker in required_session_text:
        if marker not in segment:
            raise RuntimeError(f"session-chat planned source missing marker: {marker}")

    drain = find_async_method(tree, "_drain_session_stream_task_on_disconnect")
    drain_segment = ast.get_source_segment(planned, drain) or ""
    unregister_pos = drain_segment.find("unregister_gateway_notify(run_id)")
    agent_pos = drain_segment.find("agent = self._active_run_agents.get(run_id)")
    if unregister_pos < 0 or agent_pos < 0 or unregister_pos > agent_pos:
        raise RuntimeError(
            "disconnect drain does not unregister approval before agent/task wait path"
        )

    print("P5_03A2_STRUCTURAL_REVIEW=PASS")


def native_approval_isolation_probe() -> None:
    from tools import approval

    # Pinned Hermes v0.20.6 defines _ApprovalEntry directly in tools.approval.
    # A later upstream refactor moved it into tools.approval_gateway_wait;
    # this review must follow the installed pinned source, not current main.
    _ApprovalEntry = approval._ApprovalEntry

    # Process-local cleanup only. Hermes server is not running.
    approval.unregister_gateway_notify(RUN_A)
    approval.unregister_gateway_notify(RUN_B)

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

        print("P5_03A2_NATIVE_APPROVAL_ISOLATION=PASS")
        print("P5_03A2_NATIVE_UNREGISTER_WAKE=PASS")
        print("P5_03A2_NATIVE_CONTEXT_SCOPE=PASS")
    finally:
        # Always remove synthetic process-local probe state, including on
        # assertion failure. This process exits after the review either way.
        approval.unregister_gateway_notify(RUN_A)
        approval.unregister_gateway_notify(RUN_B)


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
