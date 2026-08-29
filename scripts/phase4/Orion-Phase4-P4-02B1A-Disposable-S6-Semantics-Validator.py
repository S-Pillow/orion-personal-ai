#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
from typing import Sequence

PINNED_IMAGE = "orion-hermes-iai:v2026.8.18-iai3.0.8-m5-extidle-b6d356e"
EXPECTED_IMAGE_ID = "sha256:db651747ed9e785fa839470d06535e37134a858e2d16077106f77ba6bd2d1517"
SERVICE_NAME = "orion-s6-semantics"
EVIDENCE_BASE = Path(r"E:\Orion-Phase2\P4-02B1A-evidence")


class ValidationError(RuntimeError):
    pass


class CmdResult:
    def __init__(self, args: Sequence[str], returncode: int, stdout: str, stderr: str):
        self.args = list(args)
        self.returncode = int(returncode)
        self.stdout = stdout
        self.stderr = stderr

    @property
    def combined(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout.rstrip("\n"))
        if self.stderr:
            parts.append(self.stderr.rstrip("\n"))
        return "\n".join(parts)

    def require_ok(self, label: str) -> "CmdResult":
        if self.returncode != 0:
            raise ValidationError(
                f"{label} failed: exit={self.returncode}; output={self.combined!r}"
            )
        return self


def run(
    args: Sequence[str],
    timeout: int = 120,
    input_text: str | None = None,
) -> CmdResult:
    cp = subprocess.run(
        list(args),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )
    return CmdResult(
        args,
        cp.returncode,
        cp.stdout.replace("\r\n", "\n").replace("\r", "\n"),
        cp.stderr.replace("\r\n", "\n").replace("\r", "\n"),
    )


def docker(
    *args: str,
    timeout: int = 120,
    input_text: str | None = None,
) -> CmdResult:
    return run(["docker.exe", *args], timeout=timeout, input_text=input_text)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        text.replace("\r\n", "\n").replace("\r", "\n"),
        encoding="utf-8",
        newline="\n",
    )


def save_text(root: Path, name: str, text: str) -> None:
    write_lf(root / name, text)


def parse_key_values(text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key and key.replace("_", "").isalnum():
            values.setdefault(key, []).append(value.strip())
    return values


def require_single(values: dict[str, list[str]], key: str) -> str:
    found = values.get(key, [])
    if len(found) != 1:
        raise ValidationError(
            f"Expected exactly one {key}=... line; found {len(found)}: {found!r}"
        )
    return found[0]


def remove_container(name: str) -> None:
    if docker("inspect", name, timeout=20).returncode == 0:
        docker("rm", "-f", "-v", name, timeout=60)


def remove_image(name: str) -> None:
    if docker("image", "inspect", name, timeout=20).returncode == 0:
        docker("image", "rm", "-f", name, timeout=120)


def docker_cp_text(container: str, dest: str, text: str, scratch: Path, name: str) -> None:
    local = scratch / name
    write_lf(local, text)
    docker("cp", str(local), f"{container}:{dest}", timeout=60).require_ok(
        f"docker cp {name}"
    )


def set_mode(
    container: str,
    mode: str,
    hermes_uid: int,
    hermes_gid: int,
    tee_path: str,
) -> None:
    r = docker(
        "exec",
        "-i",
        "--user",
        f"{hermes_uid}:{hermes_gid}",
        container,
        tee_path,
        "/orion-test-control/mode",
        timeout=20,
        input_text=mode + "\n",
    )
    r.require_ok("write disposable mode as Hermes UID")


def cat_container(container: str, path: str) -> CmdResult:
    return docker("exec", container, "/bin/cat", path, timeout=30)


def get_start_count(container: str) -> int:
    r = cat_container(container, "/orion-test-control/start-count")
    if r.returncode != 0:
        return 0
    raw = r.stdout.strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValidationError(f"Invalid start-count value: {raw!r}") from exc


def wait_start_count(container: str, minimum: int, timeout_seconds: int = 30) -> int:
    deadline = time.monotonic() + timeout_seconds
    last = 0
    while time.monotonic() < deadline:
        last = get_start_count(container)
        if last >= minimum:
            return last
        time.sleep(0.25)
    raise ValidationError(f"Timed out waiting for start-count >= {minimum}; last={last}")


def runtime_service_dir(runtime_service_root: str) -> str:
    return f"{runtime_service_root.rstrip('/')}/{SERVICE_NAME}"


def service_status(container: str, runtime_service_root: str) -> CmdResult:
    return docker(
        "exec",
        container,
        "/command/s6-svstat",
        runtime_service_dir(runtime_service_root),
        timeout=20,
    )


def wait_service_state(
    container: str,
    runtime_service_root: str,
    state: str,
    timeout_seconds: int = 30,
) -> CmdResult:
    deadline = time.monotonic() + timeout_seconds
    last = CmdResult([], -1, "", "no attempt")
    expected = state.lower() + " "
    while time.monotonic() < deadline:
        last = service_status(container, runtime_service_root)
        if last.returncode == 0 and last.stdout.strip().lower().startswith(expected):
            return last
        time.sleep(0.25)
    raise ValidationError(
        f"Timed out waiting for service state {state}; "
        f"last_exit={last.returncode}; last_output={last.combined!r}"
    )


def assert_container_running(container: str) -> None:
    r = docker("inspect", container, timeout=20).require_ok("inspect disposable container")
    info = json.loads(r.stdout)
    running = bool(info and info[0].get("State", {}).get("Running"))
    if not running:
        logs = docker("logs", "--tail", "200", container, timeout=30)
        raise ValidationError(f"Disposable container is not running. logs={logs.combined!r}")


def write_summary(path: Path, status: str, error: str | None, extra: dict | None = None) -> None:
    payload = {
        "schema_version": 4,
        "status": status,
        "recorded_at": utc_iso(),
        "pinned_image": PINNED_IMAGE,
        "expected_image_id": EXPECTED_IMAGE_ID,
        "production_mutation": "NONE",
        "production_container_touched": False,
        "production_volume_mounted": False,
        "docker_socket_mounted": False,
        "host_ports_published": False,
        "production_threshold_changes": "NONE",
        "implementation": "python-subprocess-argv",
        "error": error,
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def discover_real_s6(
    container: str,
    root: Path,
    scratch: Path,
) -> tuple[str, str, int, int, str]:
    probe = r'''#!/bin/sh
set -eu
echo "PID1_COMM=$(cat /proc/1/comm)"
echo "PID1_EXE=$(readlink /proc/1/exe || true)"
echo "S6_SVC=$(test -x /command/s6-svc && echo YES || echo NO)"
echo "S6_SVSTAT=$(test -x /command/s6-svstat && echo YES || echo NO)"
echo "S6_SVPERMS=$(test -x /command/s6-svperms && echo YES || echo NO)"
echo "S6_RC_ROOT=$(test -d /etc/s6-overlay/s6-rc.d && echo YES || echo NO)"
echo "S6_RC_SERVICEDIRS=$(test -d /run/s6-rc/servicedirs && echo /run/s6-rc/servicedirs || true)"
echo "TEE_PATH=$(command -v tee || true)"
for p in \
  /etc/s6-overlay/s6-rc.d/user/contents.d \
  /etc/s6-overlay/user-bundles.d/user/contents.d
do
  if [ -d "$p" ]; then
    echo "USER_CONTENTS_DIR=$p"
  fi
done
if id hermes >/dev/null 2>&1; then
  echo "HERMES_UID=$(id -u hermes)"
  echo "HERMES_GID=$(id -g hermes)"
else
  echo "HERMES_UID=UNKNOWN"
  echo "HERMES_GID=UNKNOWN"
fi
echo "--- /etc/s6-overlay/s6-rc.d ---"
find /etc/s6-overlay/s6-rc.d -maxdepth 3 \( -type f -o -type d \) 2>/dev/null | sort | head -n 240
echo "--- /run/service ---"
find /run/service -maxdepth 2 \( -type f -o -type d \) 2>/dev/null | sort | head -n 240
'''
    local_probe = scratch / "s6-discovery-probe.sh"
    write_lf(local_probe, probe)
    docker("cp", str(local_probe), f"{container}:/tmp/orion-s6-discovery-probe.sh", timeout=60).require_ok(
        "copy disposable discovery probe"
    )
    r = docker("exec", container, "/bin/sh", "/tmp/orion-s6-discovery-probe.sh", timeout=60).require_ok(
        "inspect real s6 layout"
    )
    save_text(root, "s6-discovery.txt", r.stdout)
    print(r.stdout, end="" if r.stdout.endswith("\n") else "\n")

    values = parse_key_values(r.stdout)
    for key in ("S6_SVC", "S6_SVSTAT", "S6_SVPERMS", "S6_RC_ROOT"):
        if require_single(values, key) != "YES":
            raise ValidationError(f"Required installed s6 primitive missing: {key}")

    candidates = values.get("USER_CONTENTS_DIR", [])
    preferred = "/etc/s6-overlay/s6-rc.d/user/contents.d"
    if preferred in candidates:
        bundle_path = preferred
    elif len(candidates) == 1:
        bundle_path = candidates[0]
    elif not candidates:
        raise ValidationError("No supported s6 user contents directory found.")
    else:
        raise ValidationError(f"Ambiguous s6 user bundle paths: {candidates!r}")

    uid_raw = require_single(values, "HERMES_UID")
    gid_raw = require_single(values, "HERMES_GID")
    try:
        uid = int(uid_raw)
        gid = int(gid_raw)
    except ValueError as exc:
        raise ValidationError(
            f"Hermes UID/GID are not integers: uid={uid_raw!r}, gid={gid_raw!r}"
        ) from exc
    runtime_service_root = require_single(values, "S6_RC_SERVICEDIRS")
    if not runtime_service_root.startswith("/"):
        raise ValidationError(
            f"s6-rc runtime service root is not absolute: {runtime_service_root!r}"
        )

    tee_path = require_single(values, "TEE_PATH")
    if not tee_path.startswith("/"):
        raise ValidationError(f"tee path is not absolute: {tee_path!r}")

    return bundle_path, runtime_service_root, uid, gid, tee_path


def build_context(context_dir: Path) -> None:
    service_dir = context_dir / "s6" / SERVICE_NAME
    service_dir.mkdir(parents=True, exist_ok=True)

    run_script = rf'''#!/command/with-contenv sh
set -eu
SERVICE_DIR="$1"
hermes_gid="$(id -g hermes)"
/command/s6-svperms -G ":${{hermes_gid}}" "$SERVICE_DIR"
exec /command/s6-setuidgid hermes /usr/local/bin/orion-semantics-payload
'''

    payload = r'''#!/bin/sh
set -eu
CONTROL=/orion-test-control
count=0
if [ -f "$CONTROL/start-count" ]; then
  count="$(cat "$CONTROL/start-count" 2>/dev/null || echo 0)"
fi
case "$count" in
  ''|*[!0-9]*) count=0 ;;
esac
count=$((count + 1))
printf '%s\n' "$count" > "$CONTROL/start-count"
printf 'run start=%s pid=%s\n' "$count" "$$" >> "$CONTROL/events.log"

while :; do
  mode="$(cat "$CONTROL/mode" 2>/dev/null || echo hold)"
  case "$mode" in
    hold)
      sleep 1
      ;;
    fail-once)
      printf 'hold\n' > "$CONTROL/mode"
      printf 'run exit=42 reason=fail-once start=%s\n' "$count" >> "$CONTROL/events.log"
      exit 42
      ;;
    clean-once)
      printf 'hold\n' > "$CONTROL/mode"
      printf 'run exit=0 reason=clean-once start=%s\n' "$count" >> "$CONTROL/events.log"
      exit 0
      ;;
    *)
      printf 'run exit=64 reason=bad-mode mode=%s start=%s\n' "$mode" "$count" >> "$CONTROL/events.log"
      exit 64
      ;;
  esac
done
'''

    finish_script = r'''#!/command/with-contenv sh
set -eu
CONTROL=/orion-test-control
code="${1:-999}"
sig="${2:-999}"
printf 'finish code=%s signal=%s\n' "$code" "$sig" >> "$CONTROL/events.log"

if [ "$code" = "0" ]; then
  printf 'finish action=park-clean\n' >> "$CONTROL/events.log"
  exit 125
fi

printf 'finish action=allow-restart\n' >> "$CONTROL/events.log"
exit 0
'''

    dockerfile = f'''ARG BASE_IMAGE
FROM ${{BASE_IMAGE}}

ARG USER_CONTENTS_DIR

COPY s6/{SERVICE_NAME}/run /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/run
COPY s6/{SERVICE_NAME}/finish /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/finish
COPY orion-semantics-payload /usr/local/bin/orion-semantics-payload

RUN mkdir -p /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/dependencies.d
RUN mkdir -p "$USER_CONTENTS_DIR"
RUN mkdir -p /orion-test-control
RUN echo longrun > /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/type
RUN touch /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/dependencies.d/base
RUN touch "$USER_CONTENTS_DIR/{SERVICE_NAME}"
RUN echo hold > /orion-test-control/mode
RUN chown -R hermes:hermes /orion-test-control
RUN chmod 0755 /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/run
RUN chmod 0755 /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/finish
RUN chmod 0755 /usr/local/bin/orion-semantics-payload

CMD ["/bin/sleep", "600"]
'''

    write_lf(service_dir / "run", run_script)
    write_lf(service_dir / "finish", finish_script)
    write_lf(context_dir / "orion-semantics-payload", payload)
    write_lf(context_dir / "Dockerfile", dockerfile)


def validate_generated_context(context_dir: Path) -> None:
    dockerfile = (context_dir / "Dockerfile").read_text(encoding="utf-8")
    required = [
        f"RUN echo longrun > /etc/s6-overlay/s6-rc.d/{SERVICE_NAME}/type",
        f'RUN touch "$USER_CONTENTS_DIR/{SERVICE_NAME}"',
        "RUN echo hold > /orion-test-control/mode",
        'CMD ["/bin/sleep", "600"]',
    ]
    missing = [line for line in required if line not in dockerfile]
    if missing:
        raise ValidationError(f"Generated Dockerfile missing required lines: {missing!r}")

    bad_lines = [
        line for line in dockerfile.splitlines()
        if line.startswith("'") or line.startswith('"')
    ]
    if bad_lines:
        raise ValidationError(
            f"Generated Dockerfile contains stray quoted instruction lines: {bad_lines!r}"
        )

    shell_files = [
        context_dir / "s6" / SERVICE_NAME / "run",
        context_dir / "s6" / SERVICE_NAME / "finish",
        context_dir / "orion-semantics-payload",
    ]
    for path in shell_files:
        result = subprocess.run(
            ["/bin/sh", "-n", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        if result.returncode != 0:
            raise ValidationError(
                f"Generated shell syntax check failed for {path.name}: "
                f"exit={result.returncode}; stderr={result.stderr!r}"
            )


def main() -> int:
    stamp = utc_stamp()
    root = EVIDENCE_BASE / f"p4-02b1a-disposable-s6-python-{stamp}"
    context = root / "build-context"
    scratch = root / "scratch"
    summary = root / "disposable-s6-python-summary.json"
    discovery = f"orion-p4-s6-discovery-{stamp}".lower()
    test = f"orion-p4-s6-test-{stamp}".lower()
    image = f"orion-p4-s6-python:{stamp.lower()}"

    root.mkdir(parents=True, exist_ok=True)
    context.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)

    bundle_path = None
    runtime_service_root = None
    hermes_uid = None
    hermes_gid = None
    tee_path = None
    initial_count = 0
    post_crash_count = 0
    post_wake_count = 0
    post_restart_count = 0
    passed = False

    print("P4-02B1A disposable s6 lifecycle semantics validator (Python v4)")
    print("DISPOSABLE ONLY: no production container stop/start/restart/recreate.")
    print("No production volume, Docker socket, host ports, or lifecycle threshold overrides.")
    print(f"P4_02B1A_PY_DISPOSABLE_EVIDENCE={root}")

    try:
        print("=== GATE A: PINNED IMAGE ===")
        r = docker("image", "inspect", PINNED_IMAGE, timeout=30).require_ok("inspect pinned image")
        info = json.loads(r.stdout)
        if len(info) != 1:
            raise ValidationError(f"Expected one image object; got {len(info)}")
        actual_id = str(info[0].get("Id", ""))
        if actual_id != EXPECTED_IMAGE_ID:
            raise ValidationError(
                f"Pinned image ID mismatch. expected={EXPECTED_IMAGE_ID}; actual={actual_id}"
            )
        save_text(root, "pinned-image-inspect.json", r.stdout)
        print(f"P4_02B1A_PY_DISPOSABLE_IMAGE_ID={actual_id}")
        print("P4_02B1A_PY_DISPOSABLE_IMAGE_PIN=PASS")

        print("=== GATE B: REAL ENTRYPOINT / S6 DISCOVERY ===")
        docker(
            "run", "-d", "--name", discovery, "--network", "none",
            PINNED_IMAGE, "/bin/sleep", "600", timeout=60
        ).require_ok("start disposable discovery container through inherited entrypoint")
        assert_container_running(discovery)

        (
            bundle_path,
            runtime_service_root,
            hermes_uid,
            hermes_gid,
            tee_path,
        ) = discover_real_s6(discovery, root, scratch)
        print(f"P4_02B1A_PY_DISPOSABLE_USER_CONTENTS_DIR={bundle_path}")
        print(f"P4_02B1A_PY_DISPOSABLE_RUNTIME_SERVICE_ROOT={runtime_service_root}")
        print(f"P4_02B1A_PY_DISPOSABLE_HERMES_ID={hermes_uid}:{hermes_gid}")
        print(f"P4_02B1A_PY_DISPOSABLE_TEE_PATH={tee_path}")
        print("P4_02B1A_PY_DISPOSABLE_REAL_ENTRYPOINT_S6_DISCOVERY=PASS")
        remove_container(discovery)

        print("=== GATE C: BUILD SEMANTIC TEST SERVICE ===")
        build_context(context)
        validate_generated_context(context)
        print("P4_02B1A_PY_DISPOSABLE_GENERATED_CONTEXT_STATIC=PASS")
        br = docker(
            "build", "--pull=false", "--network=none",
            "--build-arg", f"BASE_IMAGE={PINNED_IMAGE}",
            "--build-arg", f"USER_CONTENTS_DIR={bundle_path}",
            "-t", image, str(context), timeout=300
        )
        save_text(root, "semantic-image-build.log", br.combined)
        br.require_ok("build disposable semantic image")
        print("P4_02B1A_PY_DISPOSABLE_SEMANTIC_IMAGE_BUILD=PASS")

        print("=== GATE D: REAL S6 BOOT / NARROW CONTROL ===")
        docker("run", "-d", "--name", test, "--network", "none", image, timeout=60).require_ok(
            "start disposable semantic test container"
        )
        assert_container_running(test)
        initial_count = wait_start_count(test, 1, 30)
        up = wait_service_state(test, runtime_service_root, "up", 30)

        perms = docker(
            "exec", test, "/command/s6-svperms", runtime_service_dir(runtime_service_root), timeout=20
        ).require_ok("read disposable service permissions")
        save_text(root, "permissions-initial.txt", perms.stdout)
        print(perms.stdout, end="" if perms.stdout.endswith("\n") else "\n")
        if "control: group:" not in perms.stdout:
            raise ValidationError(f"Service control is not group-scoped: {perms.stdout!r}")
        print(f"P4_02B1A_PY_DISPOSABLE_INITIAL_STATUS={up.stdout.strip()}")
        print(f"P4_02B1A_PY_DISPOSABLE_INITIAL_START_COUNT={initial_count}")
        print("P4_02B1A_PY_DISPOSABLE_NARROW_CONTROL_PERMISSION=PASS")

        print("=== GATE E: ABNORMAL FAILURE MUST RESTART ===")
        before_crash = get_start_count(test)
        set_mode(test, "fail-once", hermes_uid, hermes_gid, tee_path)
        post_crash_count = wait_start_count(test, before_crash + 1, 30)
        crash_up = wait_service_state(test, runtime_service_root, "up", 30)
        events = cat_container(test, "/orion-test-control/events.log").require_ok(
            "read events after abnormal failure"
        ).stdout
        save_text(root, "events-after-crash.log", events)
        if "finish code=42" not in events or "finish action=allow-restart" not in events:
            raise ValidationError(f"Abnormal-exit evidence missing: {events!r}")
        print(f"P4_02B1A_PY_DISPOSABLE_ABNORMAL_RESTART_COUNT={before_crash}->{post_crash_count}")
        print(f"P4_02B1A_PY_DISPOSABLE_ABNORMAL_STATUS={crash_up.stdout.strip()}")
        print("P4_02B1A_PY_DISPOSABLE_ABNORMAL_FAILURE_RESTART=PASS")

        print("=== GATE F: CLEAN EXIT MUST PARK ===")
        set_mode(test, "clean-once", hermes_uid, hermes_gid, tee_path)
        wait_service_state(test, runtime_service_root, "down", 30)
        count_at_down = get_start_count(test)
        time.sleep(4)
        count_after_wait = get_start_count(test)
        down_again = wait_service_state(test, runtime_service_root, "down", 5)
        events = cat_container(test, "/orion-test-control/events.log").require_ok(
            "read events after clean park"
        ).stdout
        save_text(root, "events-after-clean-park.log", events)
        if "finish code=0" not in events or "finish action=park-clean" not in events:
            raise ValidationError(f"Clean-park evidence missing: {events!r}")
        if count_after_wait != count_at_down:
            raise ValidationError(
                f"Clean exit respawned unexpectedly. count_at_down={count_at_down}; "
                f"count_after_wait={count_after_wait}"
            )
        print(f"P4_02B1A_PY_DISPOSABLE_CLEAN_PARK_STATUS={down_again.stdout.strip()}")
        print(f"P4_02B1A_PY_DISPOSABLE_CLEAN_PARK_COUNT={count_after_wait}")
        print("P4_02B1A_PY_DISPOSABLE_CLEAN_EXIT_PARK=PASS")

        print("=== GATE G: HERMES-UID EXPLICIT WAKE ===")
        set_mode(test, "hold", hermes_uid, hermes_gid, tee_path)
        wake = docker(
            "exec", "--user", f"{hermes_uid}:{hermes_gid}", test,
            "/command/s6-svc", "-u", runtime_service_dir(runtime_service_root), timeout=30
        )
        save_text(root, "hermes-uid-wake.txt", f"exit={wake.returncode}\n{wake.combined}\n")
        wake.require_ok("Hermes UID explicit s6 wake")
        post_wake_count = wait_start_count(test, count_after_wait + 1, 30)
        wake_up = wait_service_state(test, runtime_service_root, "up", 30)
        print(f"P4_02B1A_PY_DISPOSABLE_WAKE_COUNT={count_after_wait}->{post_wake_count}")
        print(f"P4_02B1A_PY_DISPOSABLE_WAKE_STATUS={wake_up.stdout.strip()}")
        print("P4_02B1A_PY_DISPOSABLE_NARROW_EXPLICIT_WAKE=PASS")

        print("=== GATE H: DISPOSABLE CONTAINER RESTART ===")
        before_restart = get_start_count(test)
        set_mode(test, "hold", hermes_uid, hermes_gid, tee_path)
        docker("restart", "-t", "10", test, timeout=60).require_ok(
            "restart disposable semantic test container"
        )
        assert_container_running(test)
        post_restart_count = wait_start_count(test, before_restart + 1, 45)
        restart_up = wait_service_state(test, runtime_service_root, "up", 45)

        perms2 = docker(
            "exec", test, "/command/s6-svperms", runtime_service_dir(runtime_service_root), timeout=20
        ).require_ok("read permissions after disposable restart")
        save_text(root, "permissions-after-restart.txt", perms2.stdout)
        if "control: group:" not in perms2.stdout:
            raise ValidationError(
                f"Narrow permission not restored after restart: {perms2.stdout!r}"
            )

        set_mode(test, "clean-once", hermes_uid, hermes_gid, tee_path)
        wait_service_state(test, runtime_service_root, "down", 30)
        restart_park_count = get_start_count(test)
        time.sleep(3)
        if get_start_count(test) != restart_park_count:
            raise ValidationError("Clean park did not remain parked after container restart.")

        set_mode(test, "hold", hermes_uid, hermes_gid, tee_path)
        docker(
            "exec", "--user", f"{hermes_uid}:{hermes_gid}", test,
            "/command/s6-svc", "-u", runtime_service_dir(runtime_service_root), timeout=30
        ).require_ok("Hermes UID explicit wake after disposable restart")
        wait_start_count(test, restart_park_count + 1, 30)
        wait_service_state(test, runtime_service_root, "up", 30)

        final_events = cat_container(test, "/orion-test-control/events.log").require_ok(
            "read final events"
        ).stdout
        save_text(root, "events-final.log", final_events)

        print(f"P4_02B1A_PY_DISPOSABLE_RESTART_COUNT={before_restart}->{post_restart_count}")
        print(f"P4_02B1A_PY_DISPOSABLE_RESTART_STATUS={restart_up.stdout.strip()}")
        print("P4_02B1A_PY_DISPOSABLE_CONTAINER_RESTART_RECOVERY=PASS")
        print("P4_02B1A_PY_DISPOSABLE_POST_RESTART_WAKE=PASS")

        passed = True
        write_summary(
            summary, "PASS", None,
            {
                "evidence_root": str(root),
                "user_contents_dir": bundle_path,
                "runtime_service_root": runtime_service_root,
                "hermes_uid": hermes_uid,
                "hermes_gid": hermes_gid,
                "tee_path": tee_path,
                "initial_start_count": initial_count,
                "post_abnormal_restart_count": post_crash_count,
                "post_explicit_wake_count": post_wake_count,
                "post_container_restart_count": post_restart_count,
                "clean_exit_parks": True,
                "abnormal_exit_restarts": True,
                "hermes_uid_can_explicitly_wake": True,
                "narrow_control_reapplies_after_restart": True,
            },
        )
        print(f"P4_02B1A_PY_DISPOSABLE_SUMMARY={summary}")
        print("P4_02B1A_PY_DISPOSABLE_PRODUCTION_MUTATION=NONE")
        print("P4_02B1A_PY_DISPOSABLE_S6_SEMANTICS_GATE=PASS")

    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        try:
            logs = docker("logs", "--tail", "240", test, timeout=30)
            if logs.returncode == 0:
                save_text(root, "failure-test-container.log", logs.combined)
        except Exception:
            pass
        write_summary(
            summary, "FAIL", error_text,
            {
                "evidence_root": str(root),
                "user_contents_dir": bundle_path,
                "runtime_service_root": runtime_service_root,
                "hermes_uid": hermes_uid,
                "hermes_gid": hermes_gid,
                "tee_path": tee_path,
                "initial_start_count": initial_count,
                "post_abnormal_restart_count": post_crash_count,
                "post_explicit_wake_count": post_wake_count,
                "post_container_restart_count": post_restart_count,
            },
        )
        print(f"P4_02B1A_PY_DISPOSABLE_FATAL={error_text}")
        print(f"P4_02B1A_PY_DISPOSABLE_SUMMARY={summary}")
        print("P4_02B1A_PY_DISPOSABLE_PRODUCTION_MUTATION=NONE")
        print("P4_02B1A_PY_DISPOSABLE_S6_SEMANTICS_GATE=FAIL")

    finally:
        remove_container(discovery)
        remove_container(test)
        remove_image(image)
        print("P4_02B1A_PY_DISPOSABLE_CLEANUP=COMPLETE")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
