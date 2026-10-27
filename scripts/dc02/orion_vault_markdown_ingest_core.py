#!/usr/bin/env python3
"""Internal DC-02 primitive loader.

This module intentionally cannot run ingestion itself. The only supported CLI is
``orion_vault_markdown_ingest.py``, which owns durable store ownership,
pre-open recovery journaling, and apply coordination.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_DISABLED = (
    "ORION_VAULT_MARKDOWN_INGEST=FAIL:"
    "internal_core_entrypoint_disabled_use_orion_vault_markdown_ingest.py"
)


def _refuse_core_entrypoint(_argv: list[str] | None = None) -> int:
    print(_DISABLED, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_refuse_core_entrypoint(sys.argv[1:]))

_SOURCE_PATH = Path(__file__).with_name("orion_vault_markdown_ingest_core.source")
try:
    _source = _SOURCE_PATH.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as exc:
    raise RuntimeError(f"dc02_core_source_unavailable:{type(exc).__name__}") from exc

_marker = "\ndef main(argv: list[str] | None = None) -> int:\n"
_prefix, _sep, _unsafe_cli = _source.partition(_marker)
if not _sep:
    raise RuntimeError("dc02_core_source_main_boundary_missing")

# Execute only the library/primitive portion. The legacy standalone main and its
# direct-store transaction ordering are deliberately never compiled into this
# module, so imported callers cannot reach that bypass through ``main`` or an
# alternate helper name.
exec(compile(_prefix, str(_SOURCE_PATH), "exec"), globals(), globals())


def main(argv: list[str] | None = None) -> int:
    """Fail closed if any caller tries to use the internal core as a CLI."""
    return _refuse_core_entrypoint(argv)
