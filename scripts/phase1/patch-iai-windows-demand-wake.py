#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PATCH_MARKER = "ORION_WINDOWS_DEMAND_WAKE_PATCH_V2"
EXPECTED_IAI_VERSION = "3.0.8"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def package_version() -> str:
    for name in ("iai-pme", "iai_pme"):
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "unknown"


def default_index_path() -> Path:
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
        / "index.js"
    )


def default_node_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is not set")
    return Path(local) / "hermes" / "node" / "node.exe"


def find_matching_brace(text: str, open_index: int) -> int:
    if open_index < 0 or open_index >= len(text) or text[open_index] != "{":
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

    raise RuntimeError("no matching closing brace found")


def named_block(text: str, marker: str) -> tuple[int, int, str]:
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"required block not found: {marker}")
    if text.find(marker, start + 1) >= 0:
        raise RuntimeError(f"required block appears more than once: {marker}")
    open_brace = text.find("{", start + len(marker))
    if open_brace < 0:
        raise RuntimeError(f"opening brace not found for: {marker}")
    end = find_matching_brace(text, open_brace)
    return start, end + 1, text[start : end + 1]


def splice_block(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


def regex_count(pattern: str, text: str) -> int:
    return len(list(re.finditer(pattern, text, flags=re.MULTILINE)))


def insert_after_regex_in_block(
    text: str,
    marker: str,
    pattern: str,
    insertion: str,
) -> str:
    start, end, block = named_block(text, marker)
    matches = list(re.finditer(pattern, block, flags=re.MULTILINE))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one insertion anchor in {marker}, found {len(matches)}"
        )
    m = matches[0]
    patched = block[: m.end()] + insertion + block[m.end() :]
    return splice_block(text, start, end, patched)


def insert_before_regex_in_block(
    text: str,
    marker: str,
    pattern: str,
    insertion: str,
) -> str:
    start, end, block = named_block(text, marker)
    matches = list(re.finditer(pattern, block, flags=re.MULTILINE))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one insertion anchor in {marker}, found {len(matches)}"
        )
    m = matches[0]
    patched = block[: m.start()] + insertion + block[m.start() :]
    return splice_block(text, start, end, patched)


SOCKET_INSERT = r'''
    // ORION_WINDOWS_DEMAND_WAKE_PATCH_V2
    // iai 3.0.8 uses authenticated loopback TCP on Windows, not a Unix socket.
    if (process.platform === "win32") {
      const { readFile } = await import("node:fs/promises");
      const { dirname: pathDirname, join: pathJoin } = await import("node:path");
      const storeDir = pathDirname(socketPath);
      const endpointOverride = process.env.IAI_DAEMON_SOCKET_PATH;
      const portPath = endpointOverride
        ? `${endpointOverride}.port`
        : pathJoin(storeDir, ".daemon.port");
      const tokenPath = endpointOverride
        ? `${endpointOverride}.token`
        : pathJoin(storeDir, ".daemon.token");

      let port = 0;
      let token = "";
      try {
        port = Number.parseInt(
          (await readFile(portPath, { encoding: "utf-8" })).trim(),
          10,
        );
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
            // Windows daemon contract: token is the first line, then JSON request.
            socket.write(`${token}\n${JSON.stringify({ type: "status" })}\n`);
          } catch {
            settle(false);
          }
        });

        socket.on("data", (chunk) => {
          buffer += chunk;
          const newline = buffer.indexOf("\n");
          if (newline < 0) return;
          try {
            const payload = JSON.parse(buffer.slice(0, newline));
            settle(
              typeof payload === "object" &&
              payload !== null &&
              payload.ok === true,
            );
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
'''

PID_INSERT = r'''
      if (process.platform === "win32") {
        // ORION_WINDOWS_DEMAND_WAKE_PATCH_V2
        // Preserve identity-aware liveness using native Windows CIM rather
        // than the POSIX-only /bin/ps path.
        const { execFile: execFileWin } = await import("node:child_process");
        const { promisify: promisifyWin } = await import("node:util");
        const execFileWinAsync = promisifyWin(execFileWin);
        const psCommand =
          `$p = Get-CimInstance Win32_Process -Filter "ProcessId=${pid}" -ErrorAction SilentlyContinue; ` +
          `if ($null -eq $p) { exit 1 }; ` +
          `[Console]::Out.Write([string]$p.CommandLine)`;
        const { stdout } = await execFileWinAsync(
          "powershell.exe",
          ["-NoProfile", "-NonInteractive", "-Command", psCommand],
          { timeout: PS_TIMEOUT_MS, windowsHide: true },
        );
        return titleIsDaemonOfStore(stdout, resolvedStore);
      }
'''

SPAWN_INSERT = r'''
    if (process.platform === "win32") {
      // ORION_WINDOWS_DEMAND_WAKE_PATCH_V2
      // Reuse iai's vendor platform abstraction. `iai-mcp daemon start`
      // dispatches to the installed per-user Task Scheduler task on Windows.
      const { execFile: execFileWin } = await import("node:child_process");
      const { promisify: promisifyWin } = await import("node:util");
      const execFileWinAsync = promisifyWin(execFileWin);
      await execFileWinAsync("iai-mcp", ["daemon", "start"], {
        timeout: KICKSTART_TIMEOUT_MS,
        windowsHide: true,
      });
      return;
    }
'''


def validate_unpatched_shape(text: str) -> None:
    required_markers = [
        "function defaultSocketReachable(socketPath)",
        "function defaultDaemonPidAlive(socketPath)",
        "function defaultSpawnKickstart()",
        "async ensureDaemonAlive()",
        'WRAPPER_VERSION = "3.0.8"',
    ]
    missing = [m for m in required_markers if m not in text]
    if missing:
        raise RuntimeError(f"source-shape mismatch; missing anchors: {missing}")

    for marker in required_markers[:4]:
        if text.count(marker) != 1:
            raise RuntimeError(
                f"source-shape mismatch; expected one occurrence of {marker!r}, "
                f"found {text.count(marker)}"
            )

    _, _, socket_block = named_block(text, "function defaultSocketReachable(socketPath)")
    socket_anchor = r'const\s*\{\s*createConnection\s*\}\s*=\s*await\s+import\(["\']node:net["\']\)\s*;'
    if regex_count(socket_anchor, socket_block) != 1:
        raise RuntimeError("source-shape mismatch in defaultSocketReachable")

    _, _, pid_block = named_block(text, "function defaultDaemonPidAlive(socketPath)")
    pid_anchor = r'const\s*\{\s*stdout\s*\}\s*=\s*await\s+execFileAsync\(PS_BIN\s*,'
    if regex_count(pid_anchor, pid_block) != 1:
        raise RuntimeError("source-shape mismatch in defaultDaemonPidAlive")

    _, _, spawn_block = named_block(text, "function defaultSpawnKickstart()")
    spawn_anchor = r'const\s+uid\s*=\s*typeof\s+process\.getuid\s*===\s*["\']function["\']'
    if regex_count(spawn_anchor, spawn_block) != 1:
        raise RuntimeError("source-shape mismatch in defaultSpawnKickstart")

    _, _, ensure_block = named_block(text, "async ensureDaemonAlive()")
    old_branch = r'if\s*\(\s*this\.platform\s*===\s*["\']darwin["\']\s*\)\s*\{'
    if regex_count(old_branch, ensure_block) != 1:
        raise RuntimeError("source-shape mismatch in ensureDaemonAlive Darwin branch")


def validate_patched_shape(text: str) -> None:
    if text.count(PATCH_MARKER) < 3:
        raise RuntimeError("patch marker count is incomplete")
    _, _, ensure_block = named_block(text, "async ensureDaemonAlive()")
    new_branch = r'if\s*\(\s*this\.platform\s*===\s*["\']darwin["\']\s*\|\|\s*this\.platform\s*===\s*["\']win32["\']\s*\)\s*\{'
    if regex_count(new_branch, ensure_block) != 1:
        raise RuntimeError("patched Windows activation branch not found")


def patch_text(text: str) -> str:
    if PATCH_MARKER in text:
        validate_patched_shape(text)
        return text

    validate_unpatched_shape(text)

    socket_anchor = r'const\s*\{\s*createConnection\s*\}\s*=\s*await\s+import\(["\']node:net["\']\)\s*;'
    out = insert_after_regex_in_block(
        text,
        "function defaultSocketReachable(socketPath)",
        socket_anchor,
        SOCKET_INSERT,
    )

    pid_anchor = r'const\s*\{\s*stdout\s*\}\s*=\s*await\s+execFileAsync\(PS_BIN\s*,'
    out = insert_before_regex_in_block(
        out,
        "function defaultDaemonPidAlive(socketPath)",
        pid_anchor,
        PID_INSERT,
    )

    spawn_anchor = r'const\s+uid\s*=\s*typeof\s+process\.getuid\s*===\s*["\']function["\']'
    out = insert_before_regex_in_block(
        out,
        "function defaultSpawnKickstart()",
        spawn_anchor,
        SPAWN_INSERT,
    )

    start, end, ensure_block = named_block(out, "async ensureDaemonAlive()")
    old_branch = re.compile(
        r'if\s*\(\s*this\.platform\s*===\s*["\']darwin["\']\s*\)\s*\{',
        flags=re.MULTILINE,
    )
    matches = list(old_branch.finditer(ensure_block))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one Darwin activation branch in ensureDaemonAlive, found {len(matches)}"
        )
    ensure_patched = old_branch.sub(
        'if (this.platform === "darwin" || this.platform === "win32") {',
        ensure_block,
        count=1,
    )
    out = splice_block(out, start, end, ensure_patched)

    validate_patched_shape(out)
    return out


def preflight(path: Path) -> tuple[str, str, bool]:
    if os.name != "nt":
        raise RuntimeError("this patch is Windows-only")
    version = package_version()
    if version != EXPECTED_IAI_VERSION:
        raise RuntimeError(
            f"expected iai-pme {EXPECTED_IAI_VERSION}, found {version}; refusing to patch"
        )
    if not path.is_file():
        raise RuntimeError(f"installed wrapper bundle not found: {path}")

    text = path.read_bytes().decode("utf-8")
    digest = sha256(path)
    patched = PATCH_MARKER in text

    if patched:
        validate_patched_shape(text)
    else:
        validate_unpatched_shape(text)
        # Construct the patch in-memory during preflight. This proves all
        # surgery anchors resolve before any file write is allowed.
        candidate = patch_text(text)
        validate_patched_shape(candidate)

    return text, digest, patched


def run_node_check(node: Path, bundle: Path) -> None:
    if not node.is_file():
        raise RuntimeError(f"Hermes Node executable not found: {node}")
    proc = subprocess.run(
        [str(node), "--check", str(bundle)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = details[-1] if details else "unknown syntax error"
        raise RuntimeError(f"node --check failed: {tail}")


def apply_patch(path: Path, node: Path) -> None:
    text, before, already = preflight(path)
    if already:
        print("Already patched: True")
        print(f"index.js SHA256: {before}")
        return

    patched = patch_text(text)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + f".orion-pre-demand-wake-{stamp}.bak")
    shutil.copy2(path, backup)

    tmp = path.with_name(path.name + ".orion.tmp")
    try:
        tmp.write_bytes(patched.encode("utf-8"))
        os.replace(tmp, path)
        run_node_check(node, path)
        # Re-read what is actually on disk, not just the in-memory candidate.
        validate_patched_shape(path.read_bytes().decode("utf-8"))
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
    print("Patched-shape validation: PASS")
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
    print(f"index.js SHA256: {sha256(path)}")
    print("Rollback: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Guarded native-Windows demand-wake compatibility patch for the "
            "installed iai-pme 3.0.8 MCP wrapper bundle."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback-latest", action="store_true")
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--node", type=Path, default=None)
    args = parser.parse_args()

    bundle = args.index or default_index_path()
    node = args.node or default_node_path()

    print("=== ORION IAI WINDOWS DEMAND-WAKE PATCH V2 ===")
    print(
        "Mode:",
        "ROLLBACK" if args.rollback_latest else "APPLY" if args.apply else "PREFLIGHT",
    )
    print(f"iai-pme version: {package_version()}")
    print(f"index.js: {bundle}")

    if args.rollback_latest:
        rollback_latest(bundle, node)
        return 0

    _text, digest, patched = preflight(bundle)
    print(f"Current SHA256: {digest}")
    print(f"Already patched: {patched}")
    print("Installed-bundle source-shape validation: PASS")
    print("In-memory patched-shape construction: PASS")

    if not args.apply:
        print("PREFLIGHT: READY TO APPLY")
        return 0

    apply_patch(bundle, node)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
