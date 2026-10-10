"""One-shot Orion controls. Requires CPython on Windows; no resident components."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

from protocol import (PIN, VERSION, SafetyError, config, read, write, record,
                      receipt, require)
from win_process import Process, boot_id, same

HERMES = "http://127.0.0.1:8642/health"
OLLAMA = "http://127.0.0.1:11434/api/tags"
LEGACY = ("last-start-failure.json", "last-stop-failure.json",
          "lifecycle-quarantine.json", "lifecycle-quarantine.marker",
          "start-recovery-required.marker")


@contextlib.contextmanager
def lifecycle_lock(root):
    import msvcrt
    root.mkdir(parents=True, exist_ok=True)
    # Opening fails if old FileShare.None controls own this file. All new
    # entry points acquire this byte lock; no lock-file deletion is permitted.
    with (root / "lifecycle.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SafetyError("LIFECYCLE_BUSY") from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def health(uri):
    # Fixed loopback URLs only; ignore proxies and reject redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(uri, timeout=2) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def wait_health(uri, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if health(uri):
            return True
        time.sleep(.5)
    return False


def verify_config(path):
    cfg = config(read(path))
    for name in ("python", "ollama"):
        p = Path(cfg[name])
        require(p.is_absolute() and p.is_file() and p.suffix.lower() == ".exe", "CONFIG_EXECUTABLE_INVALID")
    source = Path(cfg["source"])
    home = Path(cfg["hermesHome"])
    require(source.is_absolute() and source.is_dir(), "CONFIG_SOURCE_INVALID")
    require(home.is_absolute() and (home / "profiles" / "companion").is_dir(), "COMPANION_PROFILE_MISSING")
    require(Path(cfg["ollama"]).name.lower() == "ollama.exe", "OLLAMA_IMAGE_INVALID")
    git = shutil.which("git.exe")
    require(git is not None, "GIT_EXE_NOT_FOUND")
    def git_read(*args):
        r = subprocess.run([git, "-C", str(source), *args], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        require(r.returncode == 0, "PIN_VERIFICATION_FAILED")
        return r.stdout.decode("utf-8").strip()
    require(git_read("rev-parse", "HEAD") == PIN, "HERMES_PIN_MISMATCH")
    from hermes_provenance import verify_hermes_provenance
    provenance_ok, provenance_code = verify_hermes_provenance(
        cfg["source"], PIN, git_exe=git
    )
    require(provenance_ok, provenance_code)
    require((source / "hermes_cli" / "gateway_windows.py").is_file(), "HERMES_SOURCE_MISSING")
    return cfg


def consistent(session, operation):
    if session and operation and session["ollama"] and operation["ollama"]:
        require(same(session["ollama"], operation["ollama"]), "CONFLICTING_OWNERSHIP")


class Controller:
    def __init__(self, root, config_path, cfg):
        self.root = root
        self.config_path = Path(config_path).resolve()
        self.cfg = cfg
        self.boot = boot_id()
        self.journal = root / "active-operation.json"
        self.session_path = root / "launcher-session.json"
        self.op = None
        self.ollama_handle = None

    def close(self):
        if self.ollama_handle:
            self.ollama_handle.close()

    def load(self):
        # Never overwrite legacy/malformed records, even on a rejected retry.
        require(not any((self.root / n).exists() for n in LEGACY), "LEGACY_RECOVERY_METADATA_PRESENT")
        session = record(read(self.session_path), session=True) if self.session_path.exists() else None
        op = record(read(self.journal)) if self.journal.exists() else None
        consistent(session, op)
        return session, op

    def begin(self, action):
        session, prior = self.load()
        if action == "start":
            require(session is None and prior is None, "USE_STOP_OR_RECOVERY_FIRST")
        if prior:
            require(prior["boot"] == self.boot, "USE_RECOVER_AFTER_RESTART")
            require(not prior["inFlight"], "COMMAND_COMPLETION_UNRESOLVED_RESTART_REQUIRED")
        if session:
            require(session["boot"] == self.boot, "USE_RECOVER_AFTER_RESTART")
        if prior:
            self.op = prior
            self.op["action"] = action
            self.op["error"] = ""
        else:
            self.op = {"schema": 4, "id": uuid.uuid4().hex, "boot": self.boot,
                       "ollama": None, "action": action, "inFlight": False, "error": ""}
        if session and session["ollama"]:
            self.op["ollama"] = session["ollama"]
        record(self.op)
        write(self.journal, self.op, exclusive=prior is None)

    def inflight(self, value):
        self.op["inFlight"] = value
        write(self.journal, self.op)

    def invoke(self, verb, seconds):
        require(self.op is not None and not self.op["inFlight"], "COMMAND_ALREADY_UNRESOLVED")
        folder = self.root / "commands" / uuid.uuid4().hex
        folder.mkdir(parents=True)
        nonce = uuid.uuid4().hex
        self.inflight(True)  # Durable BEFORE any process can be launched.
        child = None
        launcher = None
        worker = None
        try:
            child = subprocess.Popen(
                [self.cfg["python"], "-E", "-s", str(Path(__file__).with_name("hermes_worker.py")),
                 str(self.config_path), str(folder), nonce, verb],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
            launcher = Process.from_child(child)
            deadline = time.monotonic() + seconds
            while not (folder / "ready.json").exists():
                require(time.monotonic() < deadline, "WORKER_READY_TIMEOUT")
                time.sleep(.05)
            ready = receipt(read(folder / "ready.json"), nonce, ready=True)
            worker = Process.open(ready["identity"]["pid"])
            require(worker is not None, "WORKER_IDENTITY_UNAVAILABLE")
            require(not worker.exited() and same(worker.identity(), ready["identity"]), "WORKER_IDENTITY_MISMATCH")
            # Only this exact worker, now held by handle, receives execution consent.
            write(folder / "go.json", {"token": nonce})
            while not (worker.exited() and launcher.exited()):
                require(time.monotonic() < deadline, "COMMAND_TIMEOUT_UNRESOLVED")
                time.sleep(.1)
            require(child.wait(timeout=1) == 0, "WORKER_EXIT_UNRESOLVED")
            result = receipt(read(folder / "result.json"), nonce)
            require(result["ok"], "WORKER_RESULT_UNRESOLVED")
            self.inflight(False)
            return result["presence"]
        finally:
            # Never cancel Hermes, its worker, its launcher, or discovered children.
            # Any exception leaves the durable inFlight marker set.
            if worker:
                worker.close()
            if launcher:
                launcher.close()

    def archive(self, path):
        if path.exists():
            target = self.root / "history" / (uuid.uuid4().hex + "-" + path.name)
            target.parent.mkdir(exist_ok=True)
            # Preserve metadata before removing the active record. On failure, stop.
            with target.open("xb") as f:
                f.write(path.read_bytes())
                f.flush()
                os.fsync(f.fileno())
            path.unlink()

    def start(self):
        self.begin("start")
        presence = self.invoke("status", 30)
        healthy = health(HERMES)
        require((presence == "running") == healthy, "PREEXISTING_HERMES_UNHEALTHY_OR_INCONSISTENT")
        if not health(OLLAMA):
            self.inflight(True)  # Covers creation-to-identity-persistence gap.
            child = subprocess.Popen([self.cfg["ollama"], "serve"], stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.ollama_handle = Process.from_child(child)
            require(not self.ollama_handle.exited(), "OLLAMA_EXITED")
            ident = self.ollama_handle.identity()
            require(ident["image"].casefold() == str(Path(self.cfg["ollama"]).resolve()).casefold(), "OLLAMA_IMAGE_MISMATCH")
            self.op["ollama"] = ident
            self.inflight(False)  # Exact identity is durable before health wait.
            require(wait_health(OLLAMA, 45), "OLLAMA_READINESS_TIMEOUT")
            require(not self.ollama_handle.exited(), "OWNED_OLLAMA_EXITED")
        if presence == "absent":
            self.invoke("start", 45)
            require(self.invoke("status", 30) == "running", "HERMES_NOT_DETECTED")
            require(wait_health(HERMES, 90), "HERMES_READINESS_TIMEOUT")
        require(health(HERMES) and health(OLLAMA), "FINAL_HEALTH_FAILED")
        if self.ollama_handle:
            require(not self.ollama_handle.exited(), "OWNED_OLLAMA_EXITED")
        session = {key: self.op[key] for key in ("schema", "id", "boot", "ollama")}
        record(session, session=True)
        require(not self.session_path.exists(), "SESSION_APPEARED_DURING_START")
        write(self.session_path, session)
        self.archive(self.journal)
        print("ORION READY")

    def stop(self):
        self.begin("stop")
        # Explicit operator authority: stop COMPANION even if no owned session.
        # Malformed records or unconfirmed prior commands block BEFORE this call.
        self.invoke("stop", 75)
        require(self.invoke("status", 30) == "absent" and not health(HERMES), "HERMES_SHUTDOWN_NOT_VERIFIED")
        ident = self.op["ollama"]
        if ident:
            proc = Process.open(ident["pid"], terminate=True)
            if proc:
                try:
                    result = proc.kill_verified(ident)
                    require(result in ("stopped", "absent", "different"))
                    print("Owned Ollama:", result)
                finally:
                    proc.close()
            else:
                print("Owned Ollama: absent")
        else:
            print("Ollama ownership not recorded; independent processes left alone.")
        self.archive(self.session_path)
        self.archive(self.journal)
        print("ORION STOPPED; iai remains vendor-managed.")

    def recover(self):
        session, prior = self.load()
        records = [r for r in (session, prior) if r]
        require(records, "NO_RECOVERY_REQUIRED")
        require(all(r["boot"] != self.boot for r in records), "RECOVERY_REQUIRES_WINDOWS_RESTART")
        # Prior processes cannot survive a real Windows restart. Never inspect or
        # terminate potentially reused PIDs from an earlier boot. New processes
        # started since restart remain untouched, regardless of their health.
        self.archive(self.session_path)
        self.archive(self.journal)
        print("Previous-boot records archived. No processes stopped.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "stop", "recover", "preflight"))
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    require(os.name == "nt", "WINDOWS_REQUIRED")
    cfg_path = Path(args.config).resolve()
    cfg = verify_config(cfg_path)
    if args.action == "preflight":
        print(json.dumps({"package": VERSION, "pin": PIN, "python": cfg["python"],
                          "source": cfg["source"], "profileExists": True,
                          "bootIdentityAvailable": boot_id() > 0,
                          "bootId": str(boot_id())}, indent=2))
        print("Source/path checks only. No Hermes imports, runtime starts, or health calls.")
        return
    root = Path(os.environ["LOCALAPPDATA"]) / "Orion" / "operator"
    with lifecycle_lock(root):
        controller = Controller(root, cfg_path, cfg)
        try:
            getattr(controller, args.action)()
        except BaseException:
            # Do not write a new record for rejected preflight/legacy state. If an
            # operation owns a journal, only update its controlled error field.
            if controller.op is not None and controller.journal.exists():
                try:
                    controller.op["error"] = "OPERATION_FAILED"
                    write(controller.journal, controller.op)
                except Exception:
                    pass  # The previously durable journal remains the blocker.
            raise
        finally:
            controller.close()


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        if isinstance(exc, SystemExit):
            raise
        print("ORION ACTION FAILED. Recovery records were preserved.")
        print("Code:", str(exc) if isinstance(exc, SafetyError) else "UNEXPECTED_ERROR")
        print("Do not delete active-operation.json or ownership files to bypass a block.")
        raise SystemExit(1)
