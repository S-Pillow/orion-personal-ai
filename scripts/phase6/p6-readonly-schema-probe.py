"""Read-only Phase 6 SQLite schema probe.

Opens the supplied SQLite database in URI read-only mode and prints table
presence plus column metadata only. It never reads execution rows.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: p6-readonly-schema-probe.py <executions.db>", file=sys.stderr)
        return 2

    db = Path(sys.argv[1]).resolve()
    uri = db.as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        print("SQLITE_MODE=read_only")
        for table in ("executions", "cron_incidents"):
            found = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            print(f"TABLE={table};present={bool(found)}")
            if found:
                for row in conn.execute(f"PRAGMA table_info({table})"):
                    print(
                        f"SCHEMA={table};name={row[1]};type={row[2]};"
                        f"notnull={row[3]};pk={row[5]}"
                    )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
