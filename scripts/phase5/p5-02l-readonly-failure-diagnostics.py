#!/usr/bin/env python3
"""Read-only P5-02L startup failure diagnostics.

This script does not start or stop Hermes and does not mutate COMPANION files.
It classifies post-failure state, checks whether Hermes rewrote .env, and emits
only filtered/redacted recent gateway log lines relevant to startup failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


RECOVERY_ENV = "ORION_P5_PRODUCTION_RECOVERY_ROOT"
FORBIDDEN = (
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT",
)
INTEREST = re.compile(
    r"(?i)(traceback|error|exception|failed|failure|critical|fatal|"
    r"plugin|orion|api_server|bind|address|port|health|dotenv|recovery|"
    r"gateway|mcp|iai|ollama)"
)
SENSITIVE_ASSIGN = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)"
    r"(\s*[=:]\s*)([^\s,;]+)"
)
JSON_SECRET = re.compile(
    r'(?i)("(?:api[_-]?key|token|secret|password)"\s*:\s*")[^"]*(")'
)
BEARER = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+")
QUERY_SECRET = re.compile(
    r"(?i)([?&](?:api[_-]?key|token|secret|password)=)[^&#\s]+"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def redact(line: str) -> str:
    line = BEARER.sub(r"\1<REDACTED>", line)
    line = JSON_SECRET.sub(r"\1<REDACTED>\2", line)
    line = SENSITIVE_ASSIGN.sub(r"\1\2<REDACTED>", line)
    line = QUERY_SECRET.sub(r"\1<REDACTED>", line)
    return line


def active_env_values(text: str, name: str) -> list[str]:
    values: list[str] = []
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=\s*(.*)$")
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = pattern.match(line)
        if match:
            values.append(match.group(1).strip())
    return values


def filtered_tail(path: Path, *, max_lines: int = 300, max_emit: int = 80) -> list[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [f"<READ_ERROR {type(exc).__name__}>"]
    lines = text.splitlines()[-max_lines:]
    selected = [redact(line) for line in lines if INTEREST.search(line)]
    return selected[-max_emit:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("expected_recovery_root", type=Path)
    parser.add_argument("p5_02k_backup_dir", type=Path)
    args = parser.parse_args()

    profile = args.profile.resolve(strict=True)
    recovery_root = args.expected_recovery_root.resolve(strict=True)
    backup = args.p5_02k_backup_dir.resolve(strict=True)

    env_file = profile / ".env"
    config_file = profile / "config.yaml"
    plugin_init = profile / "plugins" / "orion-vault-actions" / "__init__.py"
    metadata_file = backup / "metadata.json"

    for required in (env_file, config_file, plugin_init, metadata_file):
        if not required.is_file():
            raise RuntimeError(f"required file missing: {required}")
    if not recovery_root.is_dir():
        raise RuntimeError("accepted production recovery root missing")

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    accepted_env_hash = str(metadata.get("env_sha256_after") or "").upper()
    current_env_hash = sha256(env_file)
    if not accepted_env_hash:
        raise RuntimeError("P5-02K metadata lacks env_sha256_after")

    env_bytes = env_file.read_bytes()
    if b"\x00" in env_bytes:
        raise RuntimeError("COMPANION .env contains NUL bytes")
    env_text = env_bytes.decode("utf-8-sig", errors="strict")

    recovery_values = active_env_values(env_text, RECOVERY_ENV)
    forbidden_present = {
        name: bool(active_env_values(env_text, name)) for name in FORBIDDEN
    }

    print(f"P5_02L_POSTFAIL_ENV_MATCHES_P5_02K={str(current_env_hash == accepted_env_hash).lower()}")
    print(f"P5_02L_POSTFAIL_RECOVERY_ASSIGNMENT_COUNT={len(recovery_values)}")
    print(
        "P5_02L_POSTFAIL_RECOVERY_VALUE_MATCH="
        + str(len(recovery_values) == 1 and Path(recovery_values[0]).resolve() == recovery_root).lower()
    )
    print(
        "P5_02L_POSTFAIL_FORBIDDEN_PERSISTED="
        + str(any(forbidden_present.values())).lower()
    )
    print(
        "P5_02L_POSTFAIL_RECOVERY_ROOT_EMPTY="
        + str(not any(recovery_root.iterdir())).lower()
    )
    print(f"P5_02L_POSTFAIL_CONFIG_SHA256={sha256(config_file)}")
    print(f"P5_02L_POSTFAIL_PLUGIN_SHA256={sha256(plugin_init)}")
    print(f"P5_02L_POSTFAIL_ENV_SHA256={current_env_hash}")
    print(f"P5_02L_P5_02K_ACCEPTED_ENV_SHA256={accepted_env_hash}")

    logs = profile / "logs"
    candidates = [
        logs / "gateway-stdio.log",
        logs / "gateway.log",
        logs / "gateway.error.log",
        logs / "errors.log",
        logs / "gateway-exit-diag.log",
    ]

    for path in candidates:
        print(f"--- P5_02L_FILTERED_LOG {path.name} ---")
        lines = filtered_tail(path)
        if not lines:
            print("<NO_MATCHING_RECENT_LINES>")
        else:
            for line in lines:
                print(line)

    print("P5_02L_READONLY_FAILURE_DIAGNOSTICS=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02L_READONLY_FAILURE_DIAGNOSTICS=FAIL; "
            f"ERROR={type(exc).__name__}:{redact(str(exc))}",
            file=sys.stderr,
        )
        raise SystemExit(2)
