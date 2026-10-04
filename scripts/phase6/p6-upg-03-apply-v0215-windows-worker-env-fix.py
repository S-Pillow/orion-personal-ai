from __future__ import annotations

import argparse
import ast
from pathlib import Path


OLD_BODY = '''    root = str(repo_root)
    if _installed_purelib() == Path(root).resolve():
        return worker_env
    existing = [e for e in worker_env.get("PYTHONPATH", "").split(os.pathsep) if e]
    worker_env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys([root, *existing]))
    return worker_env
'''

NEW_BODY = '''    root_path = Path(repo_root).resolve()
    root = str(root_path)
    if _installed_purelib() == root_path:
        return worker_env

    # v0.21.5's Windows detached gateway supports a legacy base-interpreter
    # topology: VIRTUAL_ENV points at <repo>/venv while the gateway process
    # itself may run under the base Python. The shared child sanitizer
    # deliberately strips both that marker and its Lib/site-packages path.
    # A restart-safe cron worker is Hermes itself, so restore this producer-
    # owned dependency path next to the checkout before spawning it.
    pinned = [root]
    if os.name == "nt":
        runtime_venv = root_path / "venv"
        runtime_site = runtime_venv / "Lib" / "site-packages"
        try:
            if (runtime_venv / "pyvenv.cfg").is_file() and runtime_site.is_dir():
                pinned.append(str(runtime_site))
        except OSError:
            pass

    existing = [e for e in worker_env.get("PYTHONPATH", "").split(os.pathsep) if e]
    worker_env["PYTHONPATH"] = os.pathsep.join(
        dict.fromkeys([*pinned, *existing])
    )
    return worker_env
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True)
    args = parser.parse_args()

    root = Path(args.candidate_root).resolve()
    path = root / "cron" / "scheduler_worker_env.py"
    source = path.read_text(encoding="utf-8")

    count = source.count(OLD_BODY)
    if count != 1:
        raise RuntimeError(
            f"v0.21.5 worker-env body drift: expected one exact anchor, found {count}"
        )

    updated = source.replace(OLD_BODY, NEW_BODY, 1)
    ast.parse(updated)
    path.write_text(updated, encoding="utf-8", newline="\n")

    print("P6_UPG_03_EXACT_TARGET_WORKER_ENV_FIX_APPLIED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
