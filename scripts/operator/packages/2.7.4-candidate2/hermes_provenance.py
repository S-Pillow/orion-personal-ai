# Exact accepted Hermes provenance validator for Orion operator candidate2.
# The accepted state is the pinned Hermes commit plus one qualified Orion overlay.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ACCEPTED_OVERLAY = {
    "agent/monitoring/cron_health.py": {
        "sha256": "e7e4877d0634635397f24b59e549fa4d21186840926843d55d2207205642d198",
        "status": " M"
    },
    "cron/error_classification.py": {
        "sha256": "dae34898d822300c198dcc0dd5d6585079ed36bd11281345e0fa55381a4b3188",
        "status": "??"
    },
    "cron/executions.py": {
        "sha256": "63269d7d36bf22f468038472378f5505b3c3c11407cb27cc61ad87d17ae6010e",
        "status": " M"
    },
    "cron/jobs.py": {
        "sha256": "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5",
        "status": " M"
    },
    "cron/scheduler.py": {
        "sha256": "6c0a43c175aab8e7d2a0107f6b067bcfa42f9a55650ab8cc761824c37fb02bfe",
        "status": " M"
    },
    "gateway/platforms/api_server.py": {
        "sha256": "7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84",
        "status": " M"
    },
    "gateway/platforms/api_server.py.orion-p4-04a.bak": {
        "sha256": "8d87036dd488cb811dbabb7048102d0c28fbf54e0e658c464683000118537ec3",
        "status": "??"
    },
    "gateway/platforms/api_server.py.orion-p4-04a.json": {
        "sha256": "c4327ec3263c2583cbd3f9df03c09a1083a9db31da032aa31a73003abd0bc8b1",
        "status": "??"
    },
    "gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak": {
        "sha256": "ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888",
        "status": "??"
    },
    "gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json": {
        "sha256": "a6bea708c90df1d4f3fbb5709064a09749f1f8e85233be171e88f2ebf21d8fcf",
        "status": "??"
    }
}

ACCEPTED_SIDECARS = {
    "gateway/platforms/api_server.py.orion-p4-04a.json": {
        "fields": {
    "accepted_hermes_commit": "5fc308a70719a83cccdbba4c0e39c23f5a8239d5",
    "patch_id": "ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1",
    "post_sha256": "ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888",
    "pre_git_blob_sha1": "980659c9343d2975040f304e05bf97fa95f6a046",
    "pre_sha256": "8d87036dd488cb811dbabb7048102d0c28fbf54e0e658c464683000118537ec3"
},
        "paths": {
    "backup": "gateway/platforms/api_server.py.orion-p4-04a.bak",
    "target": "gateway/platforms/api_server.py"
},
    },
    "gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json": {
        "fields": {
    "accepted_hermes_commit": "5fc308a70719a83cccdbba4c0e39c23f5a8239d5",
    "p4_backup_sha256": "8d87036dd488cb811dbabb7048102d0c28fbf54e0e658c464683000118537ec3",
    "p4_live_sha256": "ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888",
    "p4_patch_id": "ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1",
    "patch_id": "ORION-P5-03A2-SESSION-CHAT-APPROVAL-COMPAT-v1",
    "post_sha256": "7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84",
    "pre_sha256": "ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888"
},
        "paths": {
    "backup": "gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "target": "gateway/platforms/api_server.py"
},
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(source: Path, git_exe: str, *args: str, binary: bool = False):
    return subprocess.run(
        [git_exe, "-C", str(source), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
        check=False,
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def _parse_porcelain_v1_z(raw: bytes):
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise ValueError("porcelain output is not NUL terminated")

    records = []
    parts = raw.split(b"\0")
    if parts[-1] != b"":
        raise ValueError("porcelain output has an invalid terminator")

    for part in parts[:-1]:
        if not part:
            raise ValueError("porcelain output contains an empty record")
        try:
            text = part.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise ValueError("porcelain path is not UTF-8") from exc

        if len(text) < 4 or text[2] != " ":
            raise ValueError("malformed porcelain record")

        xy = text[:2]
        rel = text[3:]
        if not rel:
            raise ValueError("empty porcelain path")
        if "R" in xy or "C" in xy:
            raise ValueError("rename/copy status is not accepted")
        records.append((xy, rel))

    return records


def _same_path(source: Path, raw_value, expected_rel: str) -> bool:
    if not isinstance(raw_value, str) or not raw_value:
        return False
    actual = os.path.normcase(os.path.abspath(os.path.expandvars(raw_value)))
    expected = os.path.normcase(os.path.abspath(str(source / expected_rel)))
    return actual == expected


def verify_hermes_provenance(
    source,
    expected_pin: str,
    *,
    overlay=None,
    sidecars=None,
    git_exe=None,
):
    source = Path(source)
    overlay = ACCEPTED_OVERLAY if overlay is None else overlay
    sidecars = ACCEPTED_SIDECARS if sidecars is None else sidecars
    git_exe = git_exe or shutil.which("git.exe") or shutil.which("git")
    if not git_exe:
        return False, "GIT_EXE_NOT_FOUND"

    if not source.is_dir():
        return False, "HERMES_SOURCE_MISSING"

    try:
        head = _git(source, git_exe, "rev-parse", "HEAD")
    except (OSError, subprocess.TimeoutExpired):
        return False, "HERMES_GIT_IDENTITY_FAILED"
    if head.returncode != 0:
        return False, "HERMES_GIT_IDENTITY_FAILED"
    if head.stdout.strip() != expected_pin:
        return False, "HERMES_PIN_MISMATCH"

    try:
        status = _git(
            source,
            git_exe,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            binary=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, "HERMES_GIT_STATUS_FAILED"
    if status.returncode != 0:
        return False, "HERMES_GIT_STATUS_FAILED"

    try:
        actual = _parse_porcelain_v1_z(status.stdout)
    except ValueError:
        return False, "HERMES_OVERLAY_STATUS_PARSE_FAILED"

    expected_records = sorted(
        (spec["status"], rel)
        for rel, spec in overlay.items()
    )
    if sorted(actual) != expected_records:
        return False, "HERMES_OVERLAY_STATUS_MISMATCH"

    for rel, spec in overlay.items():
        path = source / rel
        if not path.is_file():
            return False, "HERMES_OVERLAY_FILE_MISSING"
        if _sha256(path) != spec["sha256"]:
            return False, "HERMES_OVERLAY_HASH_MISMATCH"

    for rel, expected in sidecars.items():
        path = source / rel
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return False, "HERMES_OVERLAY_SIDECAR_INVALID"

        if not isinstance(obj, dict):
            return False, "HERMES_OVERLAY_SIDECAR_INVALID"

        for key, value in expected.get("fields", {}).items():
            if obj.get(key) != value:
                return False, "HERMES_OVERLAY_SIDECAR_MISMATCH"

        for key, expected_rel in expected.get("paths", {}).items():
            if not _same_path(source, obj.get(key), expected_rel):
                return False, "HERMES_OVERLAY_SIDECAR_PATH_MISMATCH"

    return True, "OK"
