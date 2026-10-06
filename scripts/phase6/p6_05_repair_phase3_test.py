from __future__ import annotations

import argparse
import ast
import codecs
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_BRANCH = "feature/p6-05-reminder-crud-hud"
EXPECTED_HEAD = "69309e1559428ffee0455ed9f476222600e392a4"

ALLOWED_PATHS = {
    "hud/orion_hud_bridge.py",
    "hud/reminder_adapter.py",
    "hud/reminder_projection.py",
    "hud/static/app.js",
    "hud/static/index.html",
    "hud/static/target-layout.css",
    "hud/static/workspace-state.js",
    "hud/tests/test_phase3_workspace.py",
    "hud/tests/test_reminder_adapter.py",
    "hud/tests/test_reminder_bridge.py",
    "hud/tests/test_reminder_projection.py",
    "hud/tests/test_reminder_workspace.py",
}

TARGET_CLASS = "Phase3AdaptiveWorkspaceContractTests"
TARGET_TEST = "test_status_observations_sync_before_online_branch"

STALE_MARKERS = (
    "expected = (",
    "syncSystemWorkspace();",
    "if (online) {",
    "self.assertIn(expected, APP)",
)

REPAIRED_MARKERS = (
    'reminder_refresh = "await refreshReminders();"',
    'online_branch = "if (online) {"',
    "refresh.index(sync)",
    "refresh.index(reminder_refresh)",
    "refresh.index(online_branch)",
)

REPLACEMENT = '''    def test_status_observations_sync_before_online_branch(self):
        start = APP.index("async function refreshStatus")
        end = APP.index("function parseSSEFrame", start)
        refresh = APP[start:end]

        bridge = (
            'ui.bridgeValue.textContent = '
            'payload?.bridge?.status || "online";'
        )
        credential = (
            "ui.credentialValue.textContent = "
            'payload?.hermes?.credentials_available ? "available" : "missing";'
        )
        sync = "syncSystemWorkspace();"
        reminder_refresh = "await refreshReminders();"
        online_branch = "if (online) {"

        for token in (
            bridge,
            credential,
            sync,
            reminder_refresh,
            online_branch,
        ):
            with self.subTest(token=token):
                self.assertIn(token, refresh)

        self.assertLess(refresh.index(bridge), refresh.index(credential))
        self.assertLess(refresh.index(credential), refresh.index(sync))
        self.assertLess(
            refresh.index(sync),
            refresh.index(reminder_refresh),
        )
        self.assertLess(
            refresh.index(reminder_refresh),
            refresh.index(online_branch),
        )
'''


class RepairError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise RepairError(message)


def run(args: list[str], cwd: Path, *, capture: bool = False) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if proc.returncode != 0:
        detail = ""
        if capture:
            detail = (proc.stderr or proc.stdout or "").strip()
        fail(
            f"command failed ({proc.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    return proc.stdout if capture else ""


def assert_scope(repo: Path) -> None:
    output = run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        repo,
        capture=True,
    )
    paths = []
    for line in output.splitlines():
        if len(line) < 4:
            fail(f"malformed git status line: {line!r}")
        path = line[3:]
        if " -> " in path or path.startswith('"'):
            fail(f"unexpected status path form: {path}")
        paths.append(path)

    if len(paths) != 12 or set(paths) != ALLOWED_PATHS:
        fail(
            "P6-05 scope mismatch; "
            f"count={len(paths)}; "
            f"unexpected={sorted(set(paths) - ALLOWED_PATHS)}; "
            f"missing={sorted(ALLOWED_PATHS - set(paths))}"
        )


def locate_target(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source, filename="test_phase3_workspace.py")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            matches = [
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == TARGET_TEST
            ]
            if len(matches) != 1:
                fail(f"expected exactly one target test; found {len(matches)}")
            return matches[0]
    fail(f"class {TARGET_CLASS} was not found")


def function_segment(source: str, node: ast.AST) -> str:
    end_lineno = getattr(node, "end_lineno", None)
    if end_lineno is None:
        fail("Python AST did not provide end_lineno")
    lines = source.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1 : end_lineno])


def build_candidate(source: str) -> tuple[str, bool]:
    normalized = source.replace("\r\n", "\n")
    target = locate_target(normalized)
    current = function_segment(normalized, target)

    if all(marker in current for marker in REPAIRED_MARKERS):
        return normalized, False

    missing = [marker for marker in STALE_MARKERS if marker not in current]
    if missing:
        fail(
            "target test is neither known-stale nor known-repaired; "
            f"missing stale markers: {missing}"
        )

    lines = normalized.splitlines(keepends=True)
    candidate = "".join(
        lines[: target.lineno - 1]
        + REPLACEMENT.splitlines(keepends=True)
        + lines[target.end_lineno :]
    )

    compile(candidate, "test_phase3_workspace.py", "exec")

    repaired = function_segment(candidate, locate_target(candidate))
    missing = [marker for marker in REPAIRED_MARKERS if marker not in repaired]
    if missing:
        fail(f"candidate missing repaired markers: {missing}")
    if "self.assertIn(expected, APP)" in repaired:
        fail("candidate retained stale adjacency assertion")

    return candidate, True


def atomic_write(path: Path, data: bytes) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        default=r"D:\Orion\orion-personal-ai",
    )
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    print("=== P6-05 PHASE 3 TEST REPAIR PRECONDITIONS ===")

    if not repo.is_dir():
        fail(f"repository unavailable: {repo}")

    branch = run(["git", "branch", "--show-current"], repo, capture=True).strip()
    head = run(["git", "rev-parse", "HEAD"], repo, capture=True).strip()
    if branch != EXPECTED_BRANCH:
        fail(f"unexpected branch: {branch}")
    if head != EXPECTED_HEAD:
        fail(f"unexpected HEAD: {head}")

    assert_scope(repo)
    run(["git", "diff", "--check"], repo, capture=True)

    app = (repo / "hud/static/app.js").read_text(encoding="utf-8")
    start = app.find("async function refreshStatus")
    end = app.find("function parseSSEFrame", start)
    if start < 0 or end < 0:
        fail("refreshStatus boundary unavailable")
    refresh = app[start:end]
    reminder_pos = refresh.find("await refreshReminders();")
    online_pos = refresh.find("if (online) {")
    if reminder_pos < 0 or online_pos < 0 or reminder_pos >= online_pos:
        fail("semantic correction is not present in refreshStatus")

    print("P6_05_REPAIR_SCOPE=PASS")
    print("P6_05_REFRESH_ORDER=PASS")

    test_path = repo / "hud/tests/test_phase3_workspace.py"
    raw = test_path.read_bytes()
    bom = raw.startswith(codecs.BOM_UTF8)
    payload = raw[len(codecs.BOM_UTF8):] if bom else raw
    source = payload.decode("utf-8")

    if "\r\n" in source:
        remainder = source.replace("\r\n", "")
        if "\n" in remainder or "\r" in remainder:
            fail("test file uses mixed newline styles")
        newline = "\r\n"
    else:
        if "\r" in source:
            fail("test file contains bare CR newlines")
        newline = "\n"

    candidate, changed = build_candidate(source)
    if not changed:
        print("P6_05_PHASE3_TEST_REPAIR=ALREADY_PRESENT")
        return 0

    encoded = candidate.replace("\n", newline).encode("utf-8")
    if bom:
        encoded = codecs.BOM_UTF8 + encoded

    before_sha = hashlib.sha256(raw).hexdigest()
    after_sha = hashlib.sha256(encoded).hexdigest()

    print("P6_05_PHASE3_REPAIR_PREFLIGHT=PASS")
    atomic_write(test_path, encoded)

    try:
        run(
            [sys.executable, "-m", "py_compile", str(test_path)],
            repo,
        )
        run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "hud/tests",
                "-p",
                "test_phase3_workspace.py",
                "-v",
            ],
            repo,
        )
    except Exception:
        test_path.write_bytes(raw)
        print(
            "P6_05_PHASE3_TEST_REPAIR="
            "ROLLED_BACK_AFTER_TARGETED_FAILURE",
            file=sys.stderr,
        )
        raise

    assert_scope(repo)
    run(["git", "diff", "--check"], repo, capture=True)

    print(f"P6_05_PHASE3_TEST_BEFORE_SHA256={before_sha}")
    print(f"P6_05_PHASE3_TEST_AFTER_SHA256={after_sha}")
    print("P6_05_PHASE3_TEST_REPAIR=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepairError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(1)
