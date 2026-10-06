from __future__ import annotations

import argparse
import ast
import codecs
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

EXPECTED_BRANCH = "feature/p6-05-reminder-crud-hud"
EXPECTED_HEAD = "69309e1559428ffee0455ed9f476222600e392a4"
EXPECTED_HERMES_HEAD = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
EXPECTED_HERMES_VERSION = "0.20.6"

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


class FinalizeError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextFile:
    text: str
    newline: str
    bom: bool


def fail(message: str) -> NoReturn:
    raise FinalizeError(message)


def run_capture(args: list[str], *, cwd: Path) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        fail(
            f"command failed ({proc.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    return proc.stdout


def run_live(args: list[str], *, cwd: Path, label: str) -> None:
    print()
    print(f"=== {label} ===", flush=True)
    proc = subprocess.run(args, cwd=str(cwd))
    if proc.returncode != 0:
        fail(f"{label} failed with exit code {proc.returncode}")


def read_utf8_preserving(path: Path) -> TextFile:
    raw = path.read_bytes()
    bom = raw.startswith(codecs.BOM_UTF8)
    payload = raw[len(codecs.BOM_UTF8):] if bom else raw
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{path} is not UTF-8: {exc}")
    if "\r\n" in text:
        remainder = text.replace("\r\n", "")
        if "\n" in remainder or "\r" in remainder:
            fail(f"{path} uses mixed newline styles")
        newline = "\r\n"
    else:
        if "\r" in text:
            fail(f"{path} contains unsupported bare CR newlines")
        newline = "\n"
    return TextFile(text=text, newline=newline, bom=bom)


def encode_utf8_preserving(text: str, *, newline: str, bom: bool) -> bytes:
    normalized = text.replace("\r\n", "\n")
    encoded_text = normalized.replace("\n", newline).encode("utf-8")
    return (codecs.BOM_UTF8 + encoded_text) if bom else encoded_text


def find_target(tree: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            matches = [
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == TARGET_TEST
            ]
            if len(matches) != 1:
                fail(
                    f"expected exactly one {TARGET_CLASS}.{TARGET_TEST}; "
                    f"found {len(matches)}"
                )
            return matches[0]
    fail(f"class {TARGET_CLASS} was not found")


def function_segment(
    source: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    if node.end_lineno is None:
        fail("Python AST did not provide end_lineno")
    lines = source.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def is_repaired_function(segment: str) -> bool:
    return all(marker in segment for marker in REPAIRED_MARKERS)


def repair_phase3_source(source: str) -> tuple[str, bool]:
    normalized = source.replace("\r\n", "\n")
    tree = ast.parse(normalized, filename="test_phase3_workspace.py")
    target = find_target(tree)
    segment = function_segment(normalized, target)

    if is_repaired_function(segment):
        return normalized, False

    old_markers = (
        "expected = (",
        "syncSystemWorkspace();",
        "if (online) {",
        "self.assertIn(expected, APP)",
    )
    missing_old = [marker for marker in old_markers if marker not in segment]
    if missing_old:
        fail(
            "target Phase 3 test is neither the known stale form nor the "
            f"known repaired form; missing stale markers: {missing_old}"
        )

    if target.end_lineno is None:
        fail("Python AST did not provide end_lineno")

    lines = normalized.splitlines(keepends=True)
    candidate = "".join(
        lines[: target.lineno - 1]
        + REPLACEMENT.splitlines(keepends=True)
        + lines[target.end_lineno :]
    )

    compile(candidate, "test_phase3_workspace.py", "exec")

    candidate_tree = ast.parse(candidate, filename="test_phase3_workspace.py")
    candidate_target = find_target(candidate_tree)
    candidate_segment = function_segment(candidate, candidate_target)

    missing = [
        marker
        for marker in REPAIRED_MARKERS
        if marker not in candidate_segment
    ]
    if missing:
        fail(f"candidate target test is missing repaired markers: {missing}")

    if "self.assertIn(expected, APP)" in candidate_segment:
        fail("candidate still contains the stale adjacency assertion")

    return candidate, True


def self_test_transformer() -> None:
    fixture = '''import unittest
APP = ""

class Phase3AdaptiveWorkspaceContractTests(unittest.TestCase):
    def test_status_observations_sync_before_online_branch(self):
        expected = (
            '    ui.bridgeValue.textContent = '
            'payload?.bridge?.status || "online";\n'
            '    ui.credentialValue.textContent = '
            'payload?.hermes?.credentials_available '
            '? "available" : "missing";\n'
            '    syncSystemWorkspace();\n'
            '\n'
            '    if (online) {\n'
        )

        self.assertIn(expected, APP)

    def test_sibling_is_preserved(self):
        self.assertTrue(True)
'''
    candidate, changed = repair_phase3_source(fixture)
    if not changed:
        fail("transformer self-test did not change the stale fixture")
    if "def test_sibling_is_preserved" not in candidate:
        fail("transformer self-test damaged a sibling test")
    second, changed_again = repair_phase3_source(candidate)
    if changed_again or second != candidate:
        fail("transformer self-test is not idempotent")
    compile(candidate, "<p6-05-transformer-self-test>", "exec")


def parse_status_paths(output: str) -> list[str]:
    paths: list[str] = []
    for raw_line in output.splitlines():
        if not raw_line:
            continue
        if len(raw_line) < 4:
            fail(f"malformed git status line: {raw_line!r}")
        path = raw_line[3:]
        if " -> " in path:
            fail(f"rename/copy status is outside the P6-05 scope: {path}")
        if path.startswith('"') and path.endswith('"'):
            fail(
                "quoted git status path is outside the expected "
                f"simple scope: {path}"
            )
        paths.append(path)
    return paths


def assert_scope(repo: Path) -> list[str]:
    status = run_capture(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo,
    )
    paths = parse_status_paths(status)
    if len(paths) != 12:
        fail(
            f"expected exactly twelve P6-05 working-tree paths; "
            f"found {len(paths)}"
        )
    if set(paths) != ALLOWED_PATHS:
        unexpected = sorted(set(paths) - ALLOWED_PATHS)
        missing = sorted(ALLOWED_PATHS - set(paths))
        fail(
            f"P6-05 scope mismatch; unexpected={unexpected}; "
            f"missing={missing}"
        )
    return paths


def parse_project_identity(pyproject: str) -> tuple[str | None, str | None]:
    in_project = False
    name = None
    version = None
    for raw in pyproject.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            if line == "[project]":
                in_project = True
                continue
            if in_project:
                break
            continue
        if not in_project or not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            r"name\s*=\s*['\"]([^'\"]+)['\"]",
            line,
        )
        if match:
            name = match.group(1)
            continue
        match = re.fullmatch(
            r"version\s*=\s*['\"]([^'\"]+)['\"]",
            line,
        )
        if match:
            version = match.group(1)
    return name, version


def verify_semantic_correction(repo: Path) -> None:
    adapter = (repo / "hud/reminder_adapter.py").read_text(encoding="utf-8")
    app = (repo / "hud/static/app.js").read_text(encoding="utf-8")
    index = (repo / "hud/static/index.html").read_text(encoding="utf-8")

    required_adapter = (
        'EXPECTED_HERMES_VERSION = "0.20.6"',
        'REMINDER_DELIVERY_TARGET = "discord"',
        "version = read_hermes_project_version(root)",
        "deliver=REMINDER_DELIVERY_TARGET",
    )
    for token in required_adapter:
        if token not in adapter:
            fail(f"corrected reminder adapter marker missing: {token}")

    if 'placeholder="30m or every 30m"' not in index:
        fail("corrected schedule examples are missing")
    for token in ("tomorrow at 9am", "every weekday at 8am"):
        if token in index:
            fail(f"unsupported schedule prose remains: {token}")

    if "scheduler inactive" not in app:
        fail("scheduler-liveness presentation marker is missing")
    if "Hermes offline // reminder authority unavailable" in app:
        fail("false offline reminder-authority statement remains")

    start = app.find("async function refreshStatus")
    end = app.find("function parseSSEFrame", start)
    if start < 0 or end < 0:
        fail("refreshStatus source boundary is unavailable")
    refresh = app[start:end]

    reminder = refresh.find("await refreshReminders();")
    online = refresh.find("if (online) {")
    if reminder < 0 or online < 0 or reminder >= online:
        fail(
            "reminder refresh is not independent of the conversation "
            "online branch"
        )


def atomic_write_bytes(path: Path, data: bytes) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=f"{path.name}.",
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
        help="Orion repository root",
    )
    parser.add_argument(
        "--self-test-only",
        action="store_true",
        help="Run only the built-in transformer self-test",
    )
    args = parser.parse_args()

    print("=== P6-05 FINALIZER SELF-TEST ===", flush=True)
    self_test_transformer()
    print("P6_05_FINALIZER_SELF_TEST=PASS", flush=True)
    if args.self_test_only:
        return 0

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        fail(f"repository path is unavailable: {repo}")

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        fail("LOCALAPPDATA is unavailable")
    hermes_root = Path(local_app_data) / "hermes" / "hermes-agent"

    print()
    print("=== P6-05 FINALIZE PRECONDITIONS ===", flush=True)

    branch = run_capture(
        ["git", "branch", "--show-current"],
        cwd=repo,
    ).strip()
    head = run_capture(["git", "rev-parse", "HEAD"], cwd=repo).strip()
    if branch != EXPECTED_BRANCH:
        fail(f"unexpected Orion branch: {branch}")
    if head != EXPECTED_HEAD:
        fail(f"unexpected Orion HEAD: {head}")

    assert_scope(repo)
    run_capture(["git", "diff", "--check"], cwd=repo)

    if not hermes_root.is_dir():
        fail(f"accepted Hermes checkout is unavailable: {hermes_root}")
    hermes_head = run_capture(
        ["git", "-C", str(hermes_root), "rev-parse", "HEAD"],
        cwd=repo,
    ).strip()
    if hermes_head != EXPECTED_HERMES_HEAD:
        fail(f"unexpected Hermes HEAD: {hermes_head}")

    pyproject_path = hermes_root / "pyproject.toml"
    if not pyproject_path.is_file():
        fail("Hermes pyproject.toml is unavailable")
    pyproject = pyproject_path.read_text(encoding="utf-8")
    project_name, project_version = parse_project_identity(pyproject)
    if project_name != "hermes-agent":
        fail(f"unexpected Hermes project identity: {project_name!r}")
    if project_version != EXPECTED_HERMES_VERSION:
        fail(f"unexpected Hermes project version: {project_version!r}")

    print("P6_05_SCOPE=PASS")
    print("P6_05_HERMES_BASELINE=PASS")

    print()
    print(
        "=== VERIFY SEMANTIC CORRECTION ALREADY PRESENT ===",
        flush=True,
    )
    verify_semantic_correction(repo)
    print("P6_05_SEMANTIC_CORRECTION_PRESENT=PASS")

    print()
    print(
        "=== REPAIR ONLY THE STALE PHASE 3 STATIC ASSERTION ===",
        flush=True,
    )
    test_path = repo / "hud/tests/test_phase3_workspace.py"
    original_file = read_utf8_preserving(test_path)
    candidate_text, changed = repair_phase3_source(original_file.text)

    if changed:
        candidate_bytes = encode_utf8_preserving(
            candidate_text,
            newline=original_file.newline,
            bom=original_file.bom,
        )
        original_bytes = test_path.read_bytes()
        before_sha = hashlib.sha256(original_bytes).hexdigest()
        after_sha = hashlib.sha256(candidate_bytes).hexdigest()

        candidate_for_compile = candidate_bytes
        if (
            original_file.bom
            and candidate_for_compile.startswith(codecs.BOM_UTF8)
        ):
            candidate_for_compile = candidate_for_compile[
                len(codecs.BOM_UTF8):
            ]
        compile(
            candidate_for_compile.decode("utf-8"),
            str(test_path),
            "exec",
        )
        print("P6_05_PHASE3_REPAIR_PREFLIGHT=PASS")

        atomic_write_bytes(test_path, candidate_bytes)
        try:
            run_live(
                [
                    sys.executable,
                    "-m",
                    "py_compile",
                    str(test_path),
                ],
                cwd=repo,
                label="REPAIRED PHASE 3 TEST COMPILE",
            )
            run_live(
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
                cwd=repo,
                label="TARGETED PHASE 3 WORKSPACE",
            )
        except Exception:
            atomic_write_bytes(test_path, original_bytes)
            print(
                "P6_05_PHASE3_TEST_REPAIR="
                "ROLLED_BACK_AFTER_TARGETED_FAILURE",
                file=sys.stderr,
            )
            raise

        print(f"P6_05_PHASE3_TEST_BEFORE_SHA256={before_sha}")
        print(f"P6_05_PHASE3_TEST_AFTER_SHA256={after_sha}")
        print("P6_05_PHASE3_TEST_REPAIR=PASS")
    else:
        print("P6_05_PHASE3_TEST_REPAIR=ALREADY_PRESENT")

    compile_targets = [
        repo / "hud/reminder_adapter.py",
        repo / "hud/reminder_projection.py",
        repo / "hud/orion_hud_bridge.py",
        test_path,
    ]
    run_live(
        [
            sys.executable,
            "-m",
            "py_compile",
            *map(str, compile_targets),
        ],
        cwd=repo,
        label="PYTHON COMPILE",
    )

    focused = [
        ("FRONTEND HARDENING", "test_frontend_hardening.py"),
        ("REMINDER SUITE", "test_reminder_*.py"),
        ("PHASE 3 WORKSPACE", "test_phase3_workspace.py"),
        ("UI CONVERGENCE", "test_ui_convergence_contract.py"),
        ("BRIDGE REGRESSION", "test_bridge.py"),
        ("POST CONNECTION CLOSE", "test_post_connection_close.py"),
    ]
    for label, pattern in focused:
        run_live(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "hud/tests",
                "-p",
                pattern,
                "-v",
            ],
            cwd=repo,
            label=label,
        )

    print()
    print("P6_05_FOCUSED_EXPECTED_TESTS=98")
    print("P6_05_FOCUSED_REGRESSION_GATE=PASS")

    run_live(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "hud/tests",
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=repo,
        label="FULL HUD PYTHON DISCOVERY",
    )
    print("P6_05_FULL_HUD_TEST_GATE=PASS")

    print()
    print("=== FINAL DIFF AND SCOPE CHECK ===", flush=True)
    run_capture(["git", "diff", "--check"], cwd=repo)
    paths = assert_scope(repo)

    final_text = read_utf8_preserving(test_path).text.replace(
        "\r\n",
        "\n",
    )
    final_tree = ast.parse(final_text, filename=str(test_path))
    final_target = find_target(final_tree)
    final_segment = function_segment(final_text, final_target)
    if not is_repaired_function(final_segment):
        fail("final Phase 3 ordering contract is missing")

    app = (repo / "hud/static/app.js").read_text(encoding="utf-8")
    index = (repo / "hud/static/index.html").read_text(encoding="utf-8")
    for token in (
        "tomorrow at 9am",
        "every weekday at 8am",
        "Hermes offline // reminder authority unavailable",
    ):
        if token in app or token in index:
            fail(f"forbidden stale P6-05 token remains: {token}")

    report_path = (
        Path(tempfile.gettempdir())
        / "orion-p6-05-finalize-correction-report.txt"
    )
    report = [
        "ORION P6-05 FINALIZE CORRECTION REPORT",
        f"repo={repo}",
        f"branch={branch}",
        f"head={head}",
        f"hermes_head={hermes_head}",
        f"hermes_version={EXPECTED_HERMES_VERSION}",
        "semantic_correction=PASS",
        "phase3_test_repair=PASS",
        "focused_regression_gate=PASS",
        "focused_expected_tests=98",
        "full_hud_test_gate=PASS",
        "git_diff_check=PASS",
        f"working_tree_paths={len(paths)}",
        "production_reminder_created=NO",
        "hermes_run_invoked=NO",
        "hermes_restart=NO",
        "companion_config_changed=NO",
        "commit_push_merge_deploy=NO",
        "p6_05_status=READY_FOR_FINAL_DIFF_REVIEW_NOT_COMMITTED",
    ]
    report_path.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    print(f"P6_05_REPORT={report_path}")
    print()
    subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(repo),
    )
    print()
    print("P6_05_FINAL_CORRECTION_GATE=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FinalizeError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        raise SystemExit(1)
