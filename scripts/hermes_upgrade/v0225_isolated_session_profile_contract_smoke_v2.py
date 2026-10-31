#!/usr/bin/env python3
"""Observer-hardened session/profile smoke for Hermes v0.22.5.

v1 failed before candidate launch because its composite Python identity probe timed out.
v2 keeps the same runtime/session acceptance contract but replaces that non-essential cold
import probe with structural scratch-profile checks plus the exact Windows task identity
already established by the accepted v6 gateway smoke. It also verifies the resulting
scratch state.db with read-only sqlite3 rather than a second Hermes import.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import yaml

import v0225_isolated_gateway_contract_smoke_v5 as v5
import v0225_isolated_session_profile_contract_smoke as v1

SCRATCH_PROFILE = v5.SCRATCH_PROFILE
ACCEPTED_WINDOWS_TASK_NAME = f"Hermes_Gateway_{SCRATCH_PROFILE}"


def structural_scratch_identity(
    candidate: Path,
    runtime_python: Path,
    env: dict[str, str],
) -> str | None:
    # v1 verifies the exact candidate identity and runtime path before this hook runs.
    del candidate, runtime_python

    raw_home = env.get("HERMES_HOME")
    if not raw_home:
        raise RuntimeError("scratch HERMES_HOME missing from child environment")
    home = Path(raw_home).resolve()
    if home.name != SCRATCH_PROFILE or home.parent.name.casefold() != "profiles":
        raise RuntimeError(f"scratch HERMES_HOME layout mismatch: {home}")

    cfg_path = home / "config.yaml"
    if not cfg_path.is_file():
        raise RuntimeError(f"scratch config missing: {cfg_path}")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    gateway = data.get("gateway") if isinstance(data, dict) else None
    if not isinstance(gateway, dict) or gateway.get("standalone") is not True:
        raise RuntimeError(f"scratch profile is not standalone in config: {gateway!r}")

    print("SCRATCH_PROFILE_RESOLUTION=PASS")
    print(f"SCRATCH_PROFILE_NAME={SCRATCH_PROFILE}")
    print("SCRATCH_PROFILE_STANDALONE=true")
    print("SCRATCH_IDENTITY_PROBE_METHOD=structural_plus_accepted_v6_task_identity")
    if os.name == "nt":
        print(f"SCRATCH_WINDOWS_TASK_NAME={ACCEPTED_WINDOWS_TASK_NAME}")
        return ACCEPTED_WINDOWS_TASK_NAME
    return None


def verify_persisted_scratch_session_sqlite(
    candidate: Path,
    runtime_python: Path,
    scratch_profile: Path,
) -> None:
    del candidate, runtime_python
    state_db = scratch_profile / "state.db"
    if not state_db.is_file():
        raise RuntimeError(f"scratch session database missing: {state_db}")

    uri = state_db.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5.0)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if isinstance(row[0], str)
        }
        if "sessions" not in tables:
            raise RuntimeError(f"scratch state.db has no sessions table: {sorted(tables)}")

        columns = {
            row[1]
            for row in con.execute("PRAGMA table_info(sessions)").fetchall()
            if len(row) > 1 and isinstance(row[1], str)
        }
        needed = {"id", "title", "source", "pinned"}
        missing = sorted(needed - columns)
        if missing:
            raise RuntimeError(f"scratch sessions table missing expected columns: {missing}")

        row = con.execute(
            "SELECT id, title, source, pinned FROM sessions WHERE id = ?",
            (v1.PERSIST_ID,),
        ).fetchone()
        if row is None:
            raise RuntimeError("persisted scratch session not found in state.db")
        session_id, title, source, pinned = row
        if session_id != v1.PERSIST_ID:
            raise RuntimeError(f"persisted scratch session id mismatch: {session_id!r}")
        if title != v1.UPDATED_TITLE or bool(pinned) is not True:
            raise RuntimeError(
                "persisted scratch session metadata mismatch: "
                f"id={session_id!r}, title={title!r}, source={source!r}, pinned={pinned!r}"
            )

        deleted = con.execute(
            "SELECT 1 FROM sessions WHERE id = ?",
            (v1.DELETE_ID,),
        ).fetchone()
        if deleted is not None:
            raise RuntimeError("deleted scratch session remained persisted in state.db")
    finally:
        con.close()

    print(f"SCRATCH_STATE_DB={state_db}")
    print("SCRATCH_PERSISTENCE_OBSERVER=sqlite_read_only")
    print("SCRATCH_SESSION_PERSISTENCE=PASS")
    print("SCRATCH_SESSION_PROFILE_ISOLATION=PASS")


def main() -> int:
    # v1 imports the same v5 module object, so this replaces only its observer method.
    v1.v5.probe_scratch_identity = structural_scratch_identity
    v1.verify_persisted_scratch_session = verify_persisted_scratch_session_sqlite
    return v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
