"""DC-02 cross-module fail-closed transaction contract."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import orion_vault_ingest_fs as _fs
import orion_vault_ingest_state as _state
from orion_vault_ingest_model import AdapterError, canonical_path


def validate_store(vault_root: Path, store_root: Path, *, require_db: bool) -> Path:
    """Require one physical semantic-store topology for one Orion lock namespace."""
    store = canonical_path(store_root)
    hippo = store / "hippo"
    if os.path.lexists(hippo):
        if _fs._is_reparse_point(hippo):
            raise AdapterError(f"semantic_store_hippo_is_reparse_point:{hippo}")
        try:
            info = os.lstat(hippo)
        except OSError as exc:
            raise AdapterError(
                f"semantic_store_hippo_stat_failed:{type(exc).__name__}"
            ) from exc
        if not stat.S_ISDIR(info.st_mode):
            raise AdapterError(f"semantic_store_hippo_not_directory:{hippo}")
    return _fs.validate_store(vault_root, store_root, require_db=require_db)


def load_state(path: Path, vault_root: Path, store_root: Path) -> dict[str, Any]:
    """Load only a real successful persisted checkpoint or synthetic empty state."""
    persisted = path.exists()
    state = _state.load_state(path, vault_root, store_root)
    if persisted and state.get("successful_run_utc") is None:
        raise AdapterError("state_success_timestamp_invalid")
    return state
