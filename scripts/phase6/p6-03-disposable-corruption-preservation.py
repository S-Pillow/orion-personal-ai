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
    """Mirror the source-controlled P6-03 patch for standalone disposable qualification."""
    source = jobs_path.read_text(encoding="utf-8")

    old = "from dataclasses import dataclass\nimport json\n"
    new = "from dataclasses import dataclass\nimport hashlib\nimport json\n"
    require(source.count(old) == 1, "expected exactly one hashlib import anchor")
    source = source.replace(old, new, 1)

    old = '''def _parse_jobs_file(jobs_file: Path) -> Tuple[Any, bool]:
    """Tolerantly parse jobs.json; shared by load_jobs and the save-path peek.

    Returns ``(data, used_strict_fallback)``. utf-8-sig absorbs a Windows
    BOM; a strict parse failure is retried with ``strict=False`` to survive
    bare control characters in string values. IO errors from the open and
    parse errors from the fallback propagate to the caller, which decides
    between repair (load_jobs) and bail-out (peek).
    """
    with open(jobs_file, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        return json.loads(raw, strict=False), True
'''
    new = '''def _parse_jobs_bytes(raw: bytes) -> Tuple[Any, bool]:
    """Tolerantly parse exact jobs.json bytes and report strict-fallback use."""
    text = raw.decode("utf-8-sig")
    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        return json.loads(text, strict=False), True


def _parse_jobs_file(jobs_file: Path) -> Tuple[Any, bool]:
    """Repair-free file parser shared with the save-path peek."""
    return _parse_jobs_bytes(jobs_file.read_bytes())


def _preserve_jobs_bytes_before_repair(
    jobs_file: Path, original_bytes: bytes, reason: str
) -> Path:
    """Durably preserve the exact bytes that produced an automatic repair decision."""
    recovery_dir = jobs_file.parent / "recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True)

    safe_reason = re.sub(r"[^a-z0-9_-]+", "-", str(reason).strip().lower()).strip("-")
    if not safe_reason:
        safe_reason = "unspecified-repair"
    source_hash = hashlib.sha256(original_bytes).hexdigest()
    final_path = recovery_dir / (
        f"jobs.json.{time.time_ns()}.{os.getpid()}.{safe_reason}."
        f"{source_hash}.{uuid.uuid4().hex}.original"
    )
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{final_path.name}.", suffix=".tmp", dir=str(recovery_dir)
    )
    try:
        with os.fdopen(fd, "wb") as dst:
            dst.write(original_bytes)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(tmp_name, final_path)

        # The accepted Hermes pin has no shared fsync_directory helper.
        # On POSIX, fsync the published directory entry. Windows cannot open
        # directories this way; the artifact file was already flushed/fsynced.
        if os.name != "nt":
            dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            dir_fd = os.open(str(recovery_dir), dir_flags)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
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
'''
    require(source.count(old) == 1, "expected exactly one parser/preservation anchor")
    source = source.replace(old, new, 1)

    old = "        data, _strict_retry = _parse_jobs_file(jobs_file)\n"
    new = (
        "        raw_bytes = jobs_file.read_bytes()\n"
        "        data, _strict_retry = _parse_jobs_bytes(raw_bytes)\n"
    )
    require(source.count(old) == 1, "expected exactly one load parser anchor")
    source = source.replace(old, new, 1)

    old = '''        if jobs and (_strict_retry or needs_shape_repair):
            # Rewrite into the canonical {"jobs": [...]} form: either the parse
            # hit control-character corruption (_strict_retry) or the store was
            # an id-keyed map. save_jobs() re-emits the list shape every reader
            # expects.
            save_jobs(jobs)
            if needs_shape_repair:
'''
    new = '''        if jobs and (_strict_retry or needs_shape_repair):
            # Re-read under Hermes' existing jobs lock before preserving or
            # rewriting. This prevents an unlocked parse from preserving stale
            # bytes if a sibling writer changed jobs.json in between.
            if not getattr(_jobs_lock_state, "depth", 0):
                with _jobs_lock():
                    return load_jobs()
            if needs_shape_repair and _strict_retry:
                _repair_reason = "id-keyed-map-control-character-fallback"
            elif needs_shape_repair:
                _repair_reason = "id-keyed-map"
            else:
                _repair_reason = "control-character-fallback"
            _preserve_jobs_bytes_before_repair(jobs_file, raw_bytes, _repair_reason)
            save_jobs(jobs)
            if needs_shape_repair:
'''
    require(source.count(old) == 1, "expected exactly one dict repair anchor")
    source = source.replace(old, new, 1)

    old = '''        if data:
            save_jobs(data)
            logger.warning("Auto-repaired jobs.json (bare list wrapped as dict)")
'''
    new = '''        if data:
            if not getattr(_jobs_lock_state, "depth", 0):
                with _jobs_lock():
                    return load_jobs()
            _preserve_jobs_bytes_before_repair(jobs_file, raw_bytes, "bare-list")
            save_jobs(data)
            logger.warning("Auto-repaired jobs.json (bare list wrapped as dict)")
'''
    require(source.count(old) == 1, "expected exactly one bare-list repair anchor")
    source = source.replace(old, new, 1)

    jobs_path.write_text(source, encoding="utf-8", newline="\n")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def recovery_files(home: Path) -> list[Path]:
    recovery = home / "cron" / "recovery"
    if not recovery.exists():
        return []
    return sorted(
        p for p in recovery.iterdir()
        if p.is_file() and p.name.endswith(".original")
    )


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
    source_hash = hashlib.sha256(original).hexdigest()
    require(artifact.read_bytes() == original, "recovery artifact is not byte-for-byte identical")
    require(reason_fragment in artifact.name, f"recovery filename missing reason {reason_fragment!r}")
    require(source_hash in artifact.name, "recovery filename missing exact source SHA-256")
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
    parser.add_argument("--prepatched", action="store_true")
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

    if args.prepatched:
        patched_text = jobs_path.read_text(encoding="utf-8")
        require(
            "def _parse_jobs_bytes" in patched_text
            and "def _preserve_jobs_bytes_before_repair" in patched_text
            and "_preserve_jobs_bytes_before_repair(jobs_file, raw_bytes, _repair_reason)" in patched_text
            and '_preserve_jobs_bytes_before_repair(jobs_file, raw_bytes, "bare-list")' in patched_text
            and 'with _jobs_lock():' in patched_text,
            "prepatched source is missing revised P6-03 compatibility markers",
        )
        patched_sha = hashlib.sha256(patched_text.encode("utf-8")).hexdigest()
        emit("P6_03_SOURCE_CONTROLLED_PATCH_MODE", True)
    else:
        patched_sha = apply_disposable_patch(jobs_path)
        emit("P6_03_SOURCE_CONTROLLED_PATCH_MODE", False)

    emit("P6_03_PATCHED_JOBS_SHA256", patched_sha)
    compile_target = disposable_home / "compiled" / "cron_jobs.pyc"
    compile_target.parent.mkdir(parents=True, exist_ok=True)
    py_compile.compile(str(jobs_path), cfile=str(compile_target), doraise=True)
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

    combined = b'{"jobs":{"combo":{"prompt":"hello\x01world"}}}\n'

    def combined_assert(loaded, jobs_file, original):
        require(len(loaded) == 1 and loaded[0].get("id") == "combo", "combined repair load mismatch")
        artifact = assert_preserved(
            jobs_file.parent.parent,
            original,
            "id-keyed-map-control-character-fallback",
        )
        repaired = json.loads(jobs_file.read_text(encoding="utf-8"))
        require(repaired["jobs"][0].get("id") == "combo", "combined repair lost key-derived id")
        require(b"\x01" not in jobs_file.read_bytes(), "combined repair left raw control character")
        emit("P6_03_COMBINED_ARTIFACT", artifact.name)

    run_fixture(jobs_mod, fixtures_root, "combined-repair", combined, combined_assert)

    race_home = fixtures_root / "race-recheck"
    race_a = b'[{"id":"stale-a"}]\n'
    race_b = b'[{"id":"current-b"}]\n'
    race_file = write_fixture(race_home, race_a)
    real_parse_bytes = jobs_mod._parse_jobs_bytes
    parse_calls = {"count": 0}

    def parse_then_replace(raw):
        result = real_parse_bytes(raw)
        parse_calls["count"] += 1
        if parse_calls["count"] == 1:
            race_file.write_bytes(race_b)
        return result

    jobs_mod._parse_jobs_bytes = parse_then_replace
    try:
        with jobs_mod.use_cron_store(race_home):
            race_loaded = jobs_mod.load_jobs()
    finally:
        jobs_mod._parse_jobs_bytes = real_parse_bytes

    require(parse_calls["count"] >= 2, "repair path did not re-read under the Hermes jobs lock")
    require(
        len(race_loaded) == 1 and race_loaded[0].get("id") == "current-b",
        "locked repair used stale pre-lock parsed data",
    )
    race_artifact = assert_preserved(race_home, race_b, "bare-list")
    require(race_artifact.read_bytes() != race_a, "race fixture preserved stale pre-lock bytes")
    emit("P6_03_RACE_RECHECK_ARTIFACT", race_artifact.name)
    emit("P6_03_FIXTURE_RACE_RECHECK", "PASS")

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

    unreadable_home = fixtures_root / "unreadable"
    unreadable_payload = b'[{"id":"unreadable"}]\n'
    unreadable_file = write_fixture(unreadable_home, unreadable_payload)
    real_read_bytes = Path.read_bytes

    def deny_target_read(self):
        if self == unreadable_file:
            raise PermissionError("P6-03 simulated unreadable jobs.json")
        return real_read_bytes(self)

    Path.read_bytes = deny_target_read
    try:
        try:
            with jobs_mod.use_cron_store(unreadable_home):
                jobs_mod.load_jobs()
        except RuntimeError as exc:
            require("Failed to read cron database" in str(exc), "unexpected unreadable-store error")
        else:
            raise AssertionError("unreadable jobs.json should fail closed")
    finally:
        Path.read_bytes = real_read_bytes

    require(unreadable_file.read_bytes() == unreadable_payload, "unreadable simulation changed source")
    require(recovery_files(unreadable_home) == [], "unreadable store should not create repair artifact")
    emit("P6_03_FIXTURE_UNREADABLE", "PASS")

    failure_home = fixtures_root / "preservation-failure"
    failure_payload = b'[{"id":"must-remain-original"}]\n'
    failure_file = write_fixture(failure_home, failure_payload)
    real_preserve = jobs_mod._preserve_jobs_bytes_before_repair

    def forced_preservation_failure(_jobs_file, _original_bytes, _reason):
        raise PermissionError("P6-03 forced preservation failure")

    jobs_mod._preserve_jobs_bytes_before_repair = forced_preservation_failure
    try:
        try:
            with jobs_mod.use_cron_store(failure_home):
                jobs_mod.load_jobs()
        except PermissionError as exc:
            require("forced preservation failure" in str(exc), "unexpected preservation failure error")
        else:
            raise AssertionError("preservation failure must block automatic repair")
    finally:
        jobs_mod._preserve_jobs_bytes_before_repair = real_preserve

    require(failure_file.read_bytes() == failure_payload, "preservation failure overwrote original")
    require(recovery_files(failure_home) == [], "forced preservation failure published artifact")
    emit("P6_03_FIXTURE_PRESERVATION_FAILURE", "PASS")

    repair_failure_home = fixtures_root / "repair-write-failure"
    repair_failure_payload = b'[{"id":"repair-must-fail"}]\n'
    repair_failure_file = write_fixture(repair_failure_home, repair_failure_payload)
    real_save_jobs = jobs_mod.save_jobs

    def forced_repair_failure(*_args, **_kwargs):
        raise OSError("P6-03 forced repair write failure")

    jobs_mod.save_jobs = forced_repair_failure
    try:
        try:
            with jobs_mod.use_cron_store(repair_failure_home):
                jobs_mod.load_jobs()
        except OSError as exc:
            require("forced repair write failure" in str(exc), "unexpected repair-write error")
        else:
            raise AssertionError("forced repair write failure should propagate")
    finally:
        jobs_mod.save_jobs = real_save_jobs

    require(
        repair_failure_file.read_bytes() == repair_failure_payload,
        "repair-write failure changed original source",
    )
    repair_failure_artifact = assert_preserved(
        repair_failure_home,
        repair_failure_payload,
        "bare-list",
    )
    emit("P6_03_REPAIR_WRITE_FAILURE_ARTIFACT", repair_failure_artifact.name)
    emit("P6_03_FIXTURE_REPAIR_WRITE_FAILURE", "PASS")

    emit("P6_03_EXTERNAL_NETWORK_ATTEMPTS", len(external_attempts))
    require(not external_attempts, f"external network attempts observed: {external_attempts!r}")
    emit("P6_03_SCHEDULER_STARTED", False)
    emit("P6_03_JOB_RUN_INVOKED", False)
    emit("P6_03_COMPANION_MUTATION", False)
    emit("P6_03_DISPOSABLE_CORRUPTION_PRESERVATION_PROBE", "PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
