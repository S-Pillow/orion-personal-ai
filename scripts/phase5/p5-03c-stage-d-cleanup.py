#!/usr/bin/env python3
"""Bounded cleanup for an accepted P5-03C Stage D disposable fixture."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


EXPECTED_PREFIX = "orion-p5-03c-stage-d-"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()

    fixture = args.fixture.resolve()
    parent = fixture.parent.resolve()

    if fixture.name == "" or not fixture.name.startswith(EXPECTED_PREFIX):
        raise RuntimeError("fixture_name_not_p5_03c_stage_d")
    if str(parent).lower() != str(Path(r"D:\Orion").resolve()).lower():
        raise RuntimeError(f"fixture_parent_not_D_Orion:{parent}")
    if not fixture.is_dir():
        raise RuntimeError(f"fixture_missing:{fixture}")

    required = [fixture / "vault", fixture / "inbox", fixture / "recovery"]
    if not all(path.is_dir() for path in required):
        raise RuntimeError("fixture_shape_invalid")

    protected = [
        Path(r"C:\Personal\Me").resolve(),
        Path(r"C:\Personal\Orion-Inbox").resolve(),
    ]
    for child in required:
        resolved = child.resolve()
        for live in protected:
            if resolved == live:
                raise RuntimeError("fixture_overlaps_live_root")

    print(f"P5_03C_CLEANUP_TARGET={fixture}", flush=True)
    print("P5_03C_CLEANUP_REAL_VAULT_INBOX_TARGETED=false", flush=True)

    shutil.rmtree(fixture)

    if fixture.exists() or os.path.lexists(fixture):
        raise RuntimeError("fixture_cleanup_incomplete")

    print("P5_03C_DISPOSABLE_FIXTURE_CLEANED=true", flush=True)
    print("P5_03C_STAGE_D_CLEANUP=PASS", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            "P5_03C_STAGE_D_CLEANUP=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
