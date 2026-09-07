#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PATCH_MARKER = "ORION_WINDOWS_DEMAND_WAKE_PATCH_V1"
EXPECTED_IAI_VERSION = "3.0.8"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def default_lifecycle_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is not set")
    return (
        Path(local)
        / "hermes"
        / "profiles"
        / "companion"
        / "iai"
        / "venv"
        / "Lib"
        / "site-packages"
        / "iai_mcp"
        / "_wrapper"
        / "lifecycle.js"
    )


def default_node_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is not set")
    return Path(local) / "hermes" / "node" / "node.exe"


def package_version() -> str:
    for name in ("iai-pme", "iai_pme"):
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return "unknown"


def find_matching_brace(text: str, open_index: int) -> int:
    if text[open_index] != "{":
        raise ValueError("open_index does not point to '{'")
    depth = 0
    i = open_index
    state = "code"
    quote = ""
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if state == "line_comment":
            if ch == "\n":
                state = "code"
            i += 1
            continue
        if state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
            i += 1
            continue
        if state == "string":
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                state = "code"
            i += 1
            continue

        if ch == "/" and nxt == "/":
            state = "line_comment"
            i += 2
            continue
        if ch == "/" and nxt == "*":
            state = "block_comment"
            i += 2
            continue
        if ch in ("'", '"', "`"):
            state = "string"
            quote = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("no matching closing brace found")


def replace_named_function(text: str, name: str, replacement: str) -> str:
    marker = f"function {name}("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"required function not found: {name}")
    second = text.find(marker, start + 1)
    if second >= 0:
        raise RuntimeError(f"function appears more than once: {name}")
    open_brace = text.find("{", start)
    if open_brace < 0:
        raise RuntimeError(f"opening brace not found for {name}")
    end = find_matching_brace(text, open_brace)
    return text[:start] + replacement.rstrip() + text[end + 1 :]


SOCKET_REACHABLE = r'''function defaultSocketReachable(socketPath) {
  // ORION_WINDOWS_DEMAND_WAKE_PATCH_V1: on Windows, iai uses authenticated
  // loopback TCP (.daemon.port + .daemon.token), not a Unix-domain socket.
  return async () => {
    const { createConnection } = await import("node:net");
    if (process.platform === "win32") {
      const { readFile } = await import("node:fs/promises");
      const storeDir = dirname(socketPath);
      const portPath = join(storeDir, ".daemon.port");
      const tokenPath = join(storeDir, ".daemon.token");
      let port = 0;
      let token = "";
      try {
        port = Number.parseInt((await readFile(portPath, { encoding: "utf-8" })).trim(), 10);
        token = (await readFile(tokenPath, { encoding: "utf-8" })).trim();
      } catch {
        return false;
      }
      if (!Number.isInteger(port) || port < 1 || port > 65535 || token.length === 0) {
        return false;
      }
      return await new Promise((resolve) => {
        let settled = false;
        let buffer = "";
        const socket = createConnection({ host: "127.0.0.1", port });
        const settle = (value) => {
          if (settled) return;
          settled = true;
          try {
            socket.destroy();
          } catch {
          }
          resolve(value);
        };
        socket.setEncoding("utf8");
        socket.setTimeout(SOCKET_PROBE_TIMEOUT_MS);
        socket.once("connect", () => {
          try {
            socket.write(`${token}\n`);
            socket.write(`${JSON.stringify({ type: "status" })}\n`);
          } catch {
            settle(false);
          }
        });
        socket.on("data", (chunk) => {
          buffer += chunk;
          const nl = buffer.indexOf("\n");
          if (nl < 0) return;
          try {
            const payload = JSON.parse(buffer.slice(0, nl));
            settle(typeof payload === "object" && payload !== null);
          } catch {
            settle(false);
          }
        });
        socket.once("error", () => settle(false));
        socket.once("timeout", () => settle(false));
        socket.once("end", () => settle(false));
        socket.once("close", () => {
          if (!settled) settle(false);
        });
      });
    }
    return await new Promise((resolve) => {
      let settled = false;
      const settle = (v) => {
        if (settled) return;
        settled = true;
        try {
          socket.destroy();
        } catch {
        }
        resolve(v);
      };
      const socket = createConnection({ path: socketPath });
      socket.setTimeout(SOCKET_PROBE_TIMEOUT_MS);
      socket.once("connect", () => settle(true));
      socket.once("error", () => settle(false));
      socket.once("timeout", () => settle(false));
    });
  };
}'''

DAEMON_PID_ALIVE = r'''function defaultDaemonPidAlive(socketPath) {
  // Identity-verified liveness. Windows does not have /bin/ps, so use the
  // native CIM process table and preserve the same iai_mcp.daemon/store check.
  return async () => {
    const { readFile, realpath } = await import("node:fs/promises");
    const storeDir = dirname(socketPath);
    const statePath = join(storeDir, ".daemon-state.json");
    let pid = 0;
    try {
      const raw = await readFile(statePath, { encoding: "utf-8" });
      const parsed = JSON.parse(raw);
      pid = typeof parsed.daemon_pid === "number" ? parsed.daemon_pid : 0;
    } catch {
      return false;
    }
    if (!Number.isInteger(pid) || pid <= 0) {
      return false;
    }
    let resolvedStore = storeDir;
    try {
      resolvedStore = await realpath(storeDir);
    } catch {
      resolvedStore = storeDir;
    }
    try {
      if (process.platform === "win32") {
        const psCommand =
          `$p = Get-CimInstance Win32_Process -Filter "ProcessId=${pid}" -ErrorAction SilentlyContinue; ` +
          `if ($null -eq $p) { exit 1 }; [Console]::Out.Write([string]$p.CommandLine)`;
        const { stdout } = await execFileAsync(
          "powershell.exe",
          ["-NoProfile", "-NonInteractive", "-Command", psCommand],
          { timeout: PS_TIMEOUT_MS, windowsHide: true },
        );
        return titleIsDaemonOfStore(stdout, resolvedStore);
      }
      const { stdout } = await execFileAsync(PS_BIN, ["-o", "command=", "-p", String(pid)], {
        timeout: PS_TIMEOUT_MS,
      });
      return titleIsDaemonOfStore(stdout, resolvedStore);
    } catch {
      return false;
    }
  };
}'''

SPAWN_KICKSTART = r'''function defaultSpawnKickstart() {
  return async () => {
    if (process.platform === "win32") {
      // Reuse iai's own platform abstraction. On Windows this resolves to
      // the installed per-user Task Scheduler task via `iai-mcp daemon start`.
      await execFileAsync("iai-mcp", ["daemon", "start"], {
        timeout: KICKSTART_TIMEOUT_MS,
        windowsHide: true,
      });
      return;
    }
    const uid = typeof process.getuid === "function" ? process.getuid() : 0;
    await execFileAsync(LAUNCHCTL_BIN, kickstartArgs(uid), {
      timeout: KICKSTART_TIMEOUT_MS,
    });
  };
}'''


def preflight(path: Path) -> tuple[str, str]:
    if os.name != "nt":
        raise RuntimeError("this patch is Windows-only")
    if not path.is_file():
        raise RuntimeError(f"lifecycle.js not found: {path}")
    version = package_version()
    if version != EXPECTED_IAI_VERSION:
        raise RuntimeError(
            f"expected iai-pme {EXPECTED_IAI_VERSION}, found {version}; refusing to patch"
        )
    text = path.read_text(encoding="utf-8")
    digest = sha256(path)
    required = [
        'WRAPPER_VERSION = "3.0.8"',
        "function defaultSocketReachable(socketPath)",
        "function defaultDaemonPidAlive(socketPath)",
        "function defaultSpawnKickstart()",
    ]
    missing = [x for x in required if x not in text]
    if missing:
        raise RuntimeError(f"source-shape mismatch; missing anchors: {missing}")
    condition = 'if (this.platform === "darwin") {'
    patched_condition = 'if (this.platform === "darwin" || this.platform === "win32") {'
    if PATCH_MARKER in text:
        if patched_condition not in text:
            raise RuntimeError("patch marker present but Windows activation condition missing")
        return text, digest
    count = text.count(condition)
    if count != 1:
        raise RuntimeError(f"expected exactly one Darwin activation branch, found {count}")
    return text, digest


def patch_text(text: str) -> str:
    if PATCH_MARKER in text:
        return text
    out = replace_named_function(text, "defaultSocketReachable", SOCKET_REACHABLE)
    out = replace_named_function(out, "defaultDaemonPidAlive", DAEMON_PID_ALIVE)
    out = replace_named_function(out, "defaultSpawnKickstart", SPAWN_KICKSTART)
    old = 'if (this.platform === "darwin") {'
    new = 'if (this.platform === "darwin" || this.platform === "win32") {'
    if out.count(old) != 1:
        raise RuntimeError("Darwin activation branch changed during patch construction")
    out = out.replace(old, new, 1)
    if PATCH_MARKER not in out:
        raise RuntimeError("internal error: patch marker missing from patched source")
    return out


def run_node_check(node: Path, lifecycle: Path) -> None:
    if not node.is_file():
        raise RuntimeError(f"Hermes Node executable not found: {node}")
    proc = subprocess.run(
        [str(node), "--check", str(lifecycle)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:]
        raise RuntimeError(f"node --check failed: {detail[0] if detail else 'unknown error'}")


def apply_patch(path: Path, node: Path) -> None:
    text, before = preflight(path)
    if PATCH_MARKER in text:
        print("Already patched: True")
        print(f"lifecycle.js SHA256: {before}")
        return

    patched = patch_text(text)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + f".orion-pre-demand-wake-{stamp}.bak")
    shutil.copy2(path, backup)

    tmp = path.with_name(path.name + ".orion.tmp")
    try:
        tmp.write_text(patched, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
        run_node_check(node, path)
    except Exception:
        try:
            shutil.copy2(backup, path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    print(f"Backup: {backup}")
    print(f"Before SHA256: {before}")
    print(f"After SHA256:  {sha256(path)}")
    print("Node syntax check: PASS")
    print("Patch apply: PASS")


def rollback_latest(path: Path, node: Path) -> None:
    backups = sorted(
        path.parent.glob(path.name + ".orion-pre-demand-wake-*.bak"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        raise RuntimeError("no Orion demand-wake backup found")
    backup = backups[0]
    shutil.copy2(backup, path)
    run_node_check(node, path)
    print(f"Restored: {backup}")
    print(f"lifecycle.js SHA256: {sha256(path)}")
    print("Rollback: PASS")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Preflight/apply the narrow iai-pme 3.0.8 Windows demand-wake wrapper patch."
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="apply the patch after preflight")
    mode.add_argument("--rollback-latest", action="store_true", help="restore the newest patch backup")
    ap.add_argument("--lifecycle", type=Path, default=None)
    ap.add_argument("--node", type=Path, default=None)
    args = ap.parse_args()

    lifecycle = args.lifecycle or default_lifecycle_path()
    node = args.node or default_node_path()

    print("=== ORION IAI WINDOWS DEMAND-WAKE PATCH ===")
    print(f"Mode: {'ROLLBACK' if args.rollback_latest else 'APPLY' if args.apply else 'PREFLIGHT'}")
    print(f"iai-pme version: {package_version()}")
    print(f"lifecycle.js: {lifecycle}")

    if args.rollback_latest:
        rollback_latest(lifecycle, node)
        return 0

    text, digest = preflight(lifecycle)
    print(f"Current SHA256: {digest}")
    print(f"Already patched: {PATCH_MARKER in text}")
    print("Source-shape validation: PASS")

    if not args.apply:
        print("PREFLIGHT: READY TO APPLY")
        return 0

    apply_patch(lifecycle, node)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
