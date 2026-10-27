#!/usr/bin/env python3
"""Import-only compatibility surface for the rebuilt DC-02 transaction core."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

_MODULES = tuple(
    importlib.import_module(name)
    for name in (
        "orion_vault_ingest_model",
        "orion_vault_ingest_fs",
        "orion_vault_ingest_state",
        "orion_vault_ingest_runtime",
        # Cross-module invariants load last so the public/core surface uses
        # the hardened store/state contracts rather than the lower-level
        # module primitives directly.
        "orion_vault_ingest_contract",
    )
)
for _module in _MODULES:
    for _name in dir(_module):
        if not _name.startswith("__"):
            globals()[_name] = getattr(_module, _name)

_DISABLED = "ORION_VAULT_MARKDOWN_INGEST=FAIL:internal_core_entrypoint_disabled_use_orion_vault_markdown_ingest.py"


def main(_argv: list[str] | None = None) -> int:
    print(_DISABLED, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
