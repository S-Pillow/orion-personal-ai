#!/usr/bin/env python3
"""Run the v0.22.5 Orion compatibility transformer with lossless Git stdout handling.

The underlying transformer predates the migration harness standard and uses ``str.strip()``
on captured Git stdout. That is unsafe for ``git status --porcelain=v1`` because the leading
space in a worktree-status record is meaningful. This runner replaces only the helper seam
before invoking the transformer; no transformation behavior is otherwise changed.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("v0225_build_orion_compat.py")


def _load_transformer():
    spec = importlib.util.spec_from_file_location("orion_v0225_compat_transformer", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load transformer: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_preserving_leading_status_space(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    # Only line terminators are transport noise. Leading spaces are semantic in
    # porcelain status output and must survive intact.
    return proc.stdout.rstrip("\r\n")


def main() -> int:
    module = _load_transformer()
    module._run = _run_preserving_leading_status_space
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
