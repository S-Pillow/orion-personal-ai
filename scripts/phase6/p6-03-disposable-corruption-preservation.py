#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import py_compile
import socket
import sys
from typing import Callable

def emit(key: str, value: object) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(f"{key}={value}", flush=True)

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def apply_disposable_patch(jobs_path: Path) -> str:
    source = jobs_path.read_text(encoding="utf-8")
    helper_anchor = "\ndef load_jobs() -> List[Dict[str, Any]]:\n"
    require(source.count(helper_anchor) == 1, "expected exactly one load_jobs anchor")
    helper = """
def _preserve_jobs_file_before_repair(jobs_file: Path, reason: str) -> Path:
    \"\"\"Preserve exact on-disk jobs.json bytes before an automatic repair rewrite.\"\"\"
    recovery_dir = jobs_file.parent / "recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    safe_reason = re.sub(r"[^a-z0-9_-]+", "-", str(reason).strip().lower()).strip("-")
    if not safe_reason:
        safe_reason = "unspecified-repair"
    final_path = recovery_dir / (
        f"jobs.json.{time.time_ns()}.{os.getpid()}.{safe_reason}.original"
    )
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{final_path.name}.", suffix=".tmp", dir=str(recovery_dir)
    )
    try:
        with open(jobs_file, "rb") as src, os.fdopen(fd, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(tmp_name, final_path)
        try:
            fsync_directory(recovery_dir)
        except OSError:
            pass
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return final_path
"""
    source = source.replace(helper_anchor, "\n" + helper + helper_anchor, 1)

    old = """            save_jobs(jobs)
            if needs_shape_repair:
"""
    new = """            if needs_shape_repair and _strict_retry:
                _repair_reason = "id-keyed-map-control-character-fallback"
            elif needs_shape_repair:
                _repair_reason = "id-keyed-map"
            else:
                _repair_reason = "control-character-fallback"
            _preserve_jobs_file_before_repair(jobs_file, _repair_reason)
            save_jobs(jobs)
            if needs_shape_repair:
"""
    require(source.count(old) == 1, "expected exactly one dict repair save anchor")
    source = source.replace(old, new, 1)

    old = """        if data:
            save_jobs(data)
            logger.warning("Auto-repaired jobs.json (bare list wrapped as dict)")
"""
    new = """        if data:
            _preserve_jobs_file_before_repair(jobs_file, "bare-list")
            save_jobs(data)
            logger.warning("Auto-repaired jobs.json (bare list wrapped as dict)")
"""
    require(source.count(old) == 1, "expected exactly one bare-list repair anchor")
    source = source.replace(old, new, 1)
    jobs_path.write_text(source, encoding="utf-8", newline="\n")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()

def recovery_files(home: Path) -> list[Path]:
    recovery = home / "cron" / "recovery"
    if not recovery.exists():
        return []
    return sorted(p for p in recovery.iterdir() if p.is_file() and p.name.endswith(".original"))

def write_fixture(home: Path, payload: bytes) -> Path:
    cron_dir = home / "cron"
    cron_dir.mkdir(parents=True, exist_ok=True)
    jobs_file = cron_dir / "jobs.json"
    jobs_file.write_bytes(payload)
    return jobs_file

def assert_preserved(home: Path, original: bytes, reason_fragment: str) -> Path:
    files = recovery_files(home)
    require(len(files) == 1, f"expected one recovery artifact, got {[p.name for p in files]}")
    artifact = files[0]
    require(artifact.read_bytes() == original, "recovery artifact is not byte-for-byte identical")
    require(reason_fragment in artifact.name, f"recovery filename missing reason {reason_fragment!r}")
    return artifact

def run_fixture(jobs_mod, root: Path, name: str, payload: bytes, assertion: Callable) -> None:
    home = root / name
    jobs_file = write_fixture(home, payload)
    with jobs_mod.use_cron_store(home):
        loaded = jobs_mod.load_jobs()
    assertion(loaded, jobs_file, payload)
    emit(f"P6_03_FIXTURE_{name.upper().replace('-', '_')}", "PASS")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--disposable-home", required=True)
    args = parser.parse_args()
    source_root = Path(args.source_root).resolve()
    disposable_home = Path(args.disposable_home).resolve()
    jobs_path = source_root / "cron" / "jobs.py"
    require(jobs_path.is_file(), f"missing disposable cron/jobs.py: {jobs_path}")
    disposable_home.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(disposable_home)
    os.environ.pop("HERMES_PROFILE", None)
    emit("P6_03_CHILD_HERMES_HOME", disposable_home)
    emit("P6_03_CHILD_HERMES_PROFILE_PRESENT", "HERMES_PROFILE" in os.environ)
    emit("P6_03_PATCH_TARGET_DISPOSABLE", True)
    patched_sha = apply_disposable_patch(jobs_path)
    emit("P6_03_PATCHED_JOBS_SHA256", patched_sha)
    py_compile.compile(str(jobs_path), doraise=True)
    emit("P6_03_PATCHED_JOBS_PY_COMPILE", "PASS")

    external_attempts = []
    real_connect = socket.socket.connect
    def guarded_connect(sock, address):
        host = str(address[0]) if isinstance(address, tuple) and address else str(address)
        if host not in {"127.0.0.1", "::1", "localhost"}:
            external_attempts.append(repr(address))
            raise RuntimeError(f"P6-03 blocked external network attempt: {address!r}")
        return real_connect(sock, address)
    socket.socket.connect = guarded_connect

    sys.path.insert(0, str(source_root))
    jobs_mod = importlib.import_module("cron.jobs")
    emit("P6_03_CRON_JOBS_IMPORT", "PASS")
    fixtures_root = disposable_home / "fixtures"
    fixtures_root.mkdir(parents=True, exist_ok=True)

    healthy = b'{"jobs":[{"id":"healthy","name":"Healthy"}]}\n'
    def healthy_assert(loaded, jobs_file, original):
        require(len(loaded) == 1 and loaded[0].get("id") == "healthy", "healthy load mismatch")
        require(jobs_file.read_bytes() == original, "healthy store changed unexpectedly")
        require(recovery_files(jobs_file.parent.parent) == [], "healthy store created recovery artifact")
    run_fixture(jobs_mod, fixtures_root, "healthy", healthy, healthy_assert)

    bare = b'[{"id":"bare","name":"Bare"}]\r\n'
    def bare_assert(loaded, jobs_file, original):
        require(len(loaded) == 1 and loaded[0].get("id") == "bare", "bare-list load mismatch")
        artifact = assert_preserved(jobs_file.parent.parent, original, "bare-list")
        repaired = json.loads(jobs_file.read_text(encoding="utf-8"))
        require(isinstance(repaired, dict) and isinstance(repaired.get("jobs"), list), "bare-list not canonical")
        emit("P6_03_BARE_LIST_ARTIFACT", artifact.name)
    run_fixture(jobs_mod, fixtures_root, "bare-list", bare, bare_assert)

    id_map = b'{"jobs":{"map-1":{"name":"Mapped"}}}\n'
    def id_map_assert(loaded, jobs_file, original):
        require(len(loaded) == 1 and loaded[0].get("id") == "map-1", "id-map load mismatch")
        artifact = assert_preserved(jobs_file.parent.parent, original, "id-keyed-map")
        repaired = json.loads(jobs_file.read_text(encoding="utf-8"))
        require(repaired["jobs"][0].get("id") == "map-1", "id-map repair lost key-derived id")
        emit("P6_03_ID_MAP_ARTIFACT", artifact.name)
    run_fixture(jobs_mod, fixtures_root, "id-keyed-map", id_map, id_map_assert)

    control = b'{"jobs":[{"id":"ctrl","prompt":"hello\x01world"}]}\n'
    def control_assert(loaded, jobs_file, original):
        require(len(loaded) == 1 and loaded[0].get("id") == "ctrl", "control-char load mismatch")
        artifact = assert_preserved(jobs_file.parent.parent, original, "control-character-fallback")
        require(b"\x01" not in jobs_file.read_bytes(), "control character remained unescaped")
        emit("P6_03_CONTROL_CHAR_ARTIFACT", artifact.name)
    run_fixture(jobs_mod, fixtures_root, "control-character", control, control_assert)

    invalid_home = fixtures_root / "invalid-json"
    invalid = b'{"jobs":[\n'
    invalid_file = write_fixture(invalid_home, invalid)
    try:
        with jobs_mod.use_cron_store(invalid_home):
            jobs_mod.load_jobs()
    except RuntimeError:
        pass
    else:
        raise AssertionError("invalid JSON should fail closed")
    require(invalid_file.read_bytes() == invalid, "invalid JSON original changed")
    require(recovery_files(invalid_home) == [], "invalid JSON should not create repair artifact")
    emit("P6_03_FIXTURE_INVALID_JSON", "PASS")

    scalar_home = fixtures_root / "scalar"
    scalar = b'"not-a-job-store"\n'
    scalar_file = write_fixture(scalar_home, scalar)
    try:
        with jobs_mod.use_cron_store(scalar_home):
            jobs_mod.load_jobs()
    except RuntimeError:
        pass
    else:
        raise AssertionError("scalar top-level should fail closed")
    require(scalar_file.read_bytes() == scalar, "scalar original changed")
    require(recovery_files(scalar_home) == [], "scalar should not create repair artifact")
    emit("P6_03_FIXTURE_SCALAR", "PASS")

    failure_home = fixtures_root / "preservation-failure"
    failure_payload = b'[{"id":"must-remain-original"}]\n'
    failure_file = write_fixture(failure_home, failure_payload)
    real_preserve = jobs_mod._preserve_jobs_file_before_repair
    def forced_failure(_jobs_file, _reason):
        raise PermissionError("P6-03 forced preservation failure")
    jobs_mod._preserve_jobs_file_before_repair = forced_failure
    try:
        try:
            with jobs_mod.use_cron_store(failure_home):
                jobs_mod.load_jobs()
        except PermissionError as exc:
            require("forced preservation failure" in str(exc), "unexpected preservation failure error")
        else:
            raise AssertionError("preservation failure must block automatic repair")
    finally:
        jobs_mod._preserve_jobs_file_before_repair = real_preserve
    require(failure_file.read_bytes() == failure_payload, "preservation failure overwrote original")
    require(recovery_files(failure_home) == [], "forced failure unexpectedly published artifact")
    emit("P6_03_FIXTURE_PRESERVATION_FAILURE", "PASS")

    emit("P6_03_EXTERNAL_NETWORK_ATTEMPTS", len(external_attempts))
    require(not external_attempts, f"external network attempts observed: {external_attempts!r}")
    emit("P6_03_SCHEDULER_STARTED", False)
    emit("P6_03_JOB_RUN_INVOKED", False)
    emit("P6_03_COMPANION_MUTATION", False)
    emit("P6_03_DISPOSABLE_CORRUPTION_PRESERVATION_PROBE", "PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
