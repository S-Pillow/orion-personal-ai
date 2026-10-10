#!/usr/bin/env python3
"""Read-only Phase 4 Sherpa wake-word preflight for the accepted Hermes pin.

This script performs no config write, package install, model download, microphone
open, gateway start, or wake enablement. Run it with the accepted Hermes venv's
Python to establish whether the installed source still contains the pinned
open-vocabulary Sherpa path and what prerequisites are already present.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

PROFILE_ID = "companion"
EXPECTED_WAKE_WORD_GIT_BLOB = "f433dc660233cb010d75d2f38fccfece60794113"
EXPECTED_CONFIG_DEFAULTS_GIT_BLOB = "c9bf9ad6e2ad054461a959e86bfc028467ce9975"
EXPECTED_HERMES_COMMIT = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"

REQUIRED_WAKE_ANCHORS = (
    'class _SherpaKwsEngine(_Engine):',
    '"sherpa" (free, no API key, open vocabulary)',
    'Detects ANY typed phrase with no training',
    'provider in ("sherpa", "sherpa-onnx", "kws", "open")',
    'keywords_threshold=threshold',
)

REQUIRED_DEFAULT_ANCHORS = (
    '"provider": "openwakeword"',
    '"sherpa" (free, ANY phrase, no training)',
    '"phrase": "hey hermes"',
    '"model_dir": ""',
)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def spec_path(module: str) -> Path | None:
    spec = importlib.util.find_spec(module)
    origin = getattr(spec, "origin", None) if spec else None
    if not origin or origin in {"built-in", "frozen"}:
        return None
    return Path(origin).resolve()


def module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def safe_wake_config() -> dict[str, Any] | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    profile = Path(local) / "hermes" / "profiles" / PROFILE_ID
    candidates = (profile / "config.yaml", profile / "config.yml")
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return None
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {"_read_error": type(exc).__name__, "_path": str(path)}
    wake = payload.get("wake_word")
    if not isinstance(wake, dict):
        return {"_path": str(path), "_configured": False}
    # Wake configuration contains no provider secret; never print the rest of
    # profile config because it may contain credentials or unrelated settings.
    allowed = {
        "enabled", "surface", "input_device", "capture", "provider", "phrase",
        "sensitivity", "confirmation_frames", "start_new_session",
        "profile_routing", "sherpa",
    }
    return {
        "_path": str(path),
        "_configured": True,
        **{str(k): v for k, v in wake.items() if k in allowed},
    }


def main() -> int:
    wake_path = spec_path("tools.wake_word")
    defaults_path = spec_path("hermes_cli.config_defaults")
    result: dict[str, Any] = {
        "accepted_hermes_commit": EXPECTED_HERMES_COMMIT,
        "profile": PROFILE_ID,
        "mutation_performed": False,
        "network_performed": False,
        "package_install_performed": False,
        "microphone_opened": False,
        "config_written": False,
    }

    if wake_path is None:
        result["source_error"] = "tools.wake_word_not_found"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    wake_text = wake_path.read_text(encoding="utf-8", errors="strict")
    wake_blob = git_blob_sha(wake_path)
    result["wake_word_source"] = {
        "path": str(wake_path),
        "git_blob_sha1": wake_blob,
        "matches_accepted_blob": wake_blob == EXPECTED_WAKE_WORD_GIT_BLOB,
        "sherpa_anchors": {
            anchor: anchor in wake_text for anchor in REQUIRED_WAKE_ANCHORS
        },
    }

    if defaults_path is not None:
        defaults_text = defaults_path.read_text(encoding="utf-8", errors="strict")
        defaults_blob = git_blob_sha(defaults_path)
        result["config_defaults_source"] = {
            "path": str(defaults_path),
            "git_blob_sha1": defaults_blob,
            "matches_accepted_blob": defaults_blob == EXPECTED_CONFIG_DEFAULTS_GIT_BLOB,
            "sherpa_anchors": {
                anchor: anchor in defaults_text for anchor in REQUIRED_DEFAULT_ANCHORS
            },
        }

    result["dependencies_installed"] = {
        "sherpa_onnx": module_available("sherpa_onnx"),
        "sentencepiece": module_available("sentencepiece"),
        "sounddevice": module_available("sounddevice"),
        "numpy": module_available("numpy"),
    }

    try:
        from hermes_constants import get_hermes_home

        cache_root = Path(get_hermes_home()) / "cache" / "wakewords"
    except Exception:
        local = os.environ.get("LOCALAPPDATA")
        cache_root = (
            Path(local) / "hermes" / "cache" / "wakewords"
            if local else Path("<unknown>")
        )

    model_dir = cache_root / "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
    result["sherpa_model_cache"] = {
        "path": str(model_dir),
        "present": model_dir.is_dir(),
        "tokens_present": (model_dir / "tokens.txt").is_file(),
        "bpe_present": (model_dir / "bpe.model").is_file(),
    }
    result["current_wake_config"] = safe_wake_config()
    result["proposed_test_config"] = {
        "enabled": False,
        "provider": "sherpa",
        "phrase": "hey orion",
        "sensitivity": 0.6,
        "start_new_session": True,
        "note": "proposal only; this script does not write it",
    }

    source_ok = (
        wake_blob == EXPECTED_WAKE_WORD_GIT_BLOB
        and all(result["wake_word_source"]["sherpa_anchors"].values())
    )
    result["interpretation"] = (
        "accepted pin contains the Sherpa open-vocabulary path"
        if source_ok
        else "installed wake-word source differs from the accepted pin; investigate before wake testing"
    )

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if source_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
