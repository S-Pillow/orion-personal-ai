"""One command, then exit. Never installed as a service; never kills a process.

Runs pinned vendor Python functions, not an executable shim. A ready/go/result
handshake lets the parent retain the REAL worker process handle before execution.
"""
import contextlib
import io
import os
from pathlib import Path
import sys
import time

from protocol import config, read, write, require
from win_process import Process


class LimitedOutput(io.TextIOBase):
    def __init__(self):
        self.parts = []
        self.size = 0

    def write(self, text):
        # Vendor output is only parsed in RAM and never persisted.
        remaining = 65536 - self.size
        if remaining > 0:
            self.parts.append(text[:remaining])
            self.size += min(remaining, len(text))
        return len(text)

    def flush(self):
        pass


def run_vendor(cfg, verb):
    source = Path(cfg["source"]).resolve()
    profile = (Path(cfg["hermesHome"]) / "profiles" / "companion").resolve()
    os.environ["HERMES_HOME"] = str(profile)
    # Remove inherited profile-selection inputs. Explicit home is verified below.
    os.environ.pop("HERMES_PROFILE", None)
    sys.path.insert(0, str(source))
    import hermes_cli.gateway_windows as gw
    from hermes_cli.config import get_hermes_home
    require(Path(gw.__file__).resolve() == source / "hermes_cli" / "gateway_windows.py", "WRONG_HERMES_SOURCE")
    require(Path(get_hermes_home()).resolve() == profile, "WRONG_HERMES_PROFILE")
    require(gw.get_task_name() == "Hermes_Gateway_companion", "WRONG_HERMES_TASK")

    def no_install(*args, **kwargs):
        raise RuntimeError("Installation is not permitted in an operator action")

    # start() can offer install if registration disappears between preflight and
    # invocation. Veto that function locally; do not patch installed vendor files.
    gw.install = no_install
    if verb == "start":
        require(gw.is_task_registered(), "HERMES_TASK_NOT_REGISTERED")
        gw.start()
        return "unknown"
    if verb == "stop":
        gw.stop()
        return "unknown"
    require(verb == "status")
    output = LimitedOutput()
    with contextlib.redirect_stdout(output):
        gw.status()
    text = "".join(output.parts)
    import re
    running = bool(re.search(r"Gateway process running \(PID:\s*[0-9,\s]+\)", text))
    absent = "No gateway process detected" in text
    require(running != absent, "AMBIGUOUS_HERMES_STATUS")
    return "running" if running else "absent"


def main():
    cfg_path, folder_arg, nonce, verb = sys.argv[1:]
    folder = Path(folder_arg)
    require(verb in ("status", "start", "stop"))
    cfg = config(read(cfg_path))
    me = Process.open(os.getpid())
    require(me is not None)
    try:
        write(folder / "ready.json", {"token": nonce, "identity": me.identity()})
    finally:
        me.close()
    deadline = time.monotonic() + 30
    while not (folder / "go.json").exists():
        if time.monotonic() >= deadline:
            return 2  # No vendor import/action occurred. No receipt => unresolved.
        time.sleep(.05)
    require(read(folder / "go.json") == {"token": nonce})
    result = {"token": nonce, "ok": False, "presence": "unknown"}
    try:
        sink = LimitedOutput()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result["presence"] = run_vendor(cfg, verb)
        result["ok"] = True
    except BaseException:
        # Unknown vendor exception may leave a synchronous child alive. Do NOT
        # produce a completion receipt. Parent preserves inFlight and blocks.
        return 3
    write(folder / "result.json", result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(4)
