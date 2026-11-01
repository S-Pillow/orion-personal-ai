#!/usr/bin/env python3
"""Validate the qualified Hermes v0.22.5 isolated environment using Hermes' lock-aware semantics.

This deliberately distinguishes raw distribution-metadata mismatches from unexpected
runtime dependency drift. Hermes v0.22.5 uses [tool.uv] overrides for reviewed security
exceptions (notably Pillow 13 over browser-harness 0.1.13's stale Pillow 12.3 pin), and
pm.pip_check is the release's authority for whether a `uv pip check` report is explained
by the exact uv.lock.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import io
import subprocess
import sys
from pathlib import Path

EXPECTED_HERMES_COMMIT = "bf0203a794a07aac3ff764972ab9087baa4e4f4e"
EXPECTED_VERSIONS = {
    "edge-tts": "7.3.1",
    "Pillow": "13.0.0",
    "browser-harness": "0.1.13",
}


def _run(*argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def _one_line(proc: subprocess.CompletedProcess[str], label: str) -> str:
    if proc.returncode:
        raise RuntimeError(f"{label} failed with exit code {proc.returncode}: {proc.stderr[-400:]}")
    lines = proc.stdout.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise RuntimeError(f"{label} expected one non-empty line; observed {len(lines)}")
    return lines[0].strip()


def _require_version(dist: str, expected: str) -> None:
    observed = importlib.metadata.version(dist)
    if observed != expected:
        raise RuntimeError(f"{dist} version mismatch: expected {expected}, observed {observed}")
    print(f"DIST_VERSION={dist}|{observed}")


def _pillow_api_smoke() -> None:
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    image = Image.new("RGB", (32, 32), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 20, 20), outline="black")
    _ = ImageFont.load_default()
    contained = ImageOps.contain(image.convert("RGBA"), (16, 16))
    buffer = io.BytesIO()
    contained.save(buffer, format="PNG")
    if not buffer.getvalue().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Pillow API smoke did not produce a valid PNG signature")
    print("PILLOW_API_SMOKE=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--runtime-python", required=True, type=Path)
    parser.add_argument("--uv-exe", required=True, type=Path)
    args = parser.parse_args()

    candidate = args.candidate_root.resolve()
    runtime_python = args.runtime_python.resolve()
    uv_exe = args.uv_exe.resolve()

    for path, label in (
        (candidate / ".git", "candidate .git"),
        (candidate / "uv.lock", "candidate uv.lock"),
        (runtime_python, "runtime Python"),
        (uv_exe, "uv executable"),
    ):
        if not path.exists():
            raise RuntimeError(f"missing {label}: {path}")

    head = _one_line(_run("git", "-C", str(candidate), "rev-parse", "HEAD"), "candidate HEAD")
    if head != EXPECTED_HERMES_COMMIT:
        raise RuntimeError(f"candidate HEAD mismatch: expected {EXPECTED_HERMES_COMMIT}, observed {head}")
    print(f"CANDIDATE_HEAD={head}")

    executable = Path(sys.executable).resolve()
    if executable != runtime_python:
        raise RuntimeError(f"validator must run with isolated runtime Python: expected {runtime_python}, observed {executable}")

    pyver = _one_line(_run(str(runtime_python), "-c", "import platform; print(platform.python_version())"), "runtime Python version")
    if pyver != "3.14.9":
        raise RuntimeError(f"runtime Python mismatch: expected 3.14.9, observed {pyver}")
    print(f"RUNTIME_PYTHON_VERSION={pyver}")

    for dist, expected in EXPECTED_VERSIONS.items():
        _require_version(dist, expected)

    for module in (
        "edge_tts",
        "PIL",
        "browser_harness",
        "gateway.platforms.api_server",
        "hermes_cli.web_routers.audio",
        "cron.executions",
        "cron.jobs",
    ):
        importlib.import_module(module)
        print(f"IMPORT={module}|PASS")

    _pillow_api_smoke()

    # Import the exact candidate's lock-aware checker, not a similarly named module elsewhere.
    sys.path.insert(0, str(candidate))
    from pm.pip_check import unexpected_incompatibilities

    check = _run(
        str(uv_exe),
        "pip",
        "check",
        "--no-config",
        "--color",
        "never",
        "--python",
        str(runtime_python),
        cwd=candidate,
    )
    report = f"{check.stdout or ''}\n{check.stderr or ''}"
    raw_lines = [
        line.strip()
        for line in report.splitlines()
        if line.strip().startswith("The package `") and " requires `" in line
    ]

    print(f"RAW_UV_PIP_CHECK_EXIT={check.returncode}")
    print(f"RAW_INCOMPATIBILITY_COUNT={len(raw_lines)}")

    if check.returncode == 0:
        if raw_lines:
            raise RuntimeError("uv pip check returned 0 but still emitted incompatibility records")
        print("LOCK_AWARE_DEPENDENCY_CHECK=PASS")
        print("LOCK_AWARE_UNEXPECTED_COUNT=0")
        return 0

    unexpected = unexpected_incompatibilities(report, candidate / "uv.lock")
    if unexpected is None:
        raise RuntimeError("Hermes lock-aware checker could not safely parse the uv pip check report")
    if unexpected:
        raise RuntimeError("unexpected dependency incompatibilities remain: " + " || ".join(unexpected))

    if len(raw_lines) != 1:
        raise RuntimeError(
            f"v0.22.5 qualification expected exactly one lock-explained metadata mismatch; observed {len(raw_lines)}"
        )
    normalized = raw_lines[0].lower()
    if "browser-harness" not in normalized or "pillow==12.3.0" not in normalized or "13.0.0" not in normalized:
        raise RuntimeError("the sole lock-explained mismatch was not the reviewed browser-harness/Pillow override")

    print("LOCK_AWARE_UNEXPECTED_COUNT=0")
    print("PILLOW_SECURITY_OVERRIDE=ACCEPTED")
    print("LOCK_AWARE_DEPENDENCY_CHECK=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"LOCK_AWARE_DEPENDENCY_CHECK=FAIL|{type(exc).__name__}|{exc}", file=sys.stderr)
        raise SystemExit(1)
