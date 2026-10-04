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

NEW_BODY = '''    root = str(repo_root)
    if _installed_purelib() == Path(root).resolve():
        return worker_env

    entries = [root]
    try:
        from pm.environments import selected_venv, site_packages

        venv = selected_venv(repo_root)
        if venv is not None:
            venv_site_packages = site_packages(venv)
            if venv_site_packages is not None and venv_site_packages.is_dir():
                entries.append(str(venv_site_packages))
    except Exception:
        pass

    existing = [e for e in worker_env.get("PYTHONPATH", "").split(os.pathsep) if e]
    worker_env["PYTHONPATH"] = os.pathsep.join(
        dict.fromkeys([*entries, *existing])
    )
    return worker_env
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True)
    args = parser.parse_args()

    path = Path(args.candidate_root).resolve() / "cron" / "scheduler_worker_env.py"
    source = path.read_text(encoding="utf-8")

    count = source.count(OLD_BODY)
    if count != 1:
        raise RuntimeError(
            f"pinned worker-env body drift: expected one exact anchor, found {count}"
        )

    updated = source.replace(OLD_BODY, NEW_BODY, 1)
    ast.parse(updated)
    path.write_text(updated, encoding="utf-8", newline="\n")

    print("P6_UPG_03_DISPOSABLE_WORKER_FIX_APPLIED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
