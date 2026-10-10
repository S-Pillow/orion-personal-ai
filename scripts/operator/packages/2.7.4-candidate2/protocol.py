"""Strict, allowlisted records. No runtime exception text or vendor output on disk."""
import json
import os
from pathlib import Path
import uuid

PIN = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
VERSION = "2.7.4-candidate2"


class SafetyError(RuntimeError):
    pass


def require(ok, code="INVALID_RECORD"):
    if not ok:
        raise SafetyError(code)


def fields(obj, names):
    require(type(obj) is dict and set(obj) == set(names))


def integer(value):
    return type(value) is int and value > 0


def token(value):
    require(type(value) is str and len(value) == 32)
    require(uuid.UUID(value).hex == value)


def identity(obj):
    fields(obj, ("pid", "created", "image"))
    require(integer(obj["pid"]) and obj["pid"] <= 0xFFFFFFFF)
    require(integer(obj["created"]) and obj["created"] <= 0xFFFFFFFFFFFFFFFF)
    require(type(obj["image"]) is str and bool(obj["image"]))


def config(obj):
    fields(obj, ("schema", "python", "source", "hermesHome", "ollama", "commit"))
    require(type(obj["schema"]) is int and obj["schema"] == 4)
    require(obj["commit"] == PIN)
    for key in ("python", "source", "hermesHome", "ollama"):
        require(type(obj[key]) is str and bool(obj[key]))
    return obj


def record(obj, session=False):
    names = ("schema", "id", "boot", "ollama") if session else (
        "schema", "id", "boot", "ollama", "action", "inFlight", "error")
    fields(obj, names)
    require(type(obj["schema"]) is int and obj["schema"] == 4)
    token(obj["id"])
    require(integer(obj["boot"]) and obj["boot"] < (1 << 128))
    if obj["ollama"] is not None:
        identity(obj["ollama"])
        # Windows paths can be validated in Linux unit tests too.
        require(obj["ollama"]["image"].replace("\\", "/").split("/")[-1].lower() == "ollama.exe")
    if not session:
        require(obj["action"] in ("start", "stop", "inspect"))
        require(type(obj["inFlight"]) is bool)
        require(obj["error"] in ("", "OPERATION_FAILED"))
    return obj


def receipt(obj, expected_token, ready=False):
    fields(obj, ("token", "identity") if ready else ("token", "ok", "presence"))
    require(obj["token"] == expected_token)
    if ready:
        identity(obj["identity"])
    else:
        require(type(obj["ok"]) is bool)
        require(obj["presence"] in ("running", "absent", "unknown"))
    return obj


def no_duplicates(pairs):
    obj = {}
    for k, v in pairs:
        require(k not in obj, "DUPLICATE_JSON_KEY")
        obj[k] = v
    return obj


def read(path):
    path = Path(path)
    require(path.stat().st_size <= 65536, "RECORD_TOO_LARGE")
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f, object_pairs_hook=no_duplicates)


def write(path, obj, exclusive=False):
    path = Path(path)
    data = (json.dumps(obj, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii")
    if exclusive:
        # A partial exclusive marker also blocks future operations: it is not
        # deleted if writing/fsync fails. Never spawn until this succeeds.
        with path.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        return
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
