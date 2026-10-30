#!/usr/bin/env python3
"""Read-only Orion/Hermes v0.22.5 gateway-topology inventory.

Uses the exact candidate runtime to classify whether the current COMPANION profile
would remain standalone or is eligible for v0.22.5's multiplex-only convergence.
No config, profile, service, process, database, or runtime state is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from hermes_cli.gateway_multiplex_mode import explicit_multiplex_flag, host_serves_named_profile
from hermes_cli.profiles import profile_is_standalone, profiles_to_serve


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def token(value: object) -> str:
    if value is None:
        return "unset"
    return "true" if bool(value) else "false"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", required=True)
    parser.add_argument("--profile", default="companion")
    args = parser.parse_args()

    root = Path(args.hermes_root).resolve()
    profile_home = root / "profiles" / args.profile
    profiles_dir = root / "profiles"

    if not root.is_dir():
        raise RuntimeError(f"Hermes root missing: {root}")
    if not profile_home.is_dir():
        raise RuntimeError(f"Profile home missing: {profile_home}")

    watched = [
        root / "config.yaml",
        root / ".env",
        profile_home / "config.yaml",
        profile_home / ".env",
        root / "active_profile",
    ]
    before = {str(p): sha256(p) for p in watched}

    profile_names = sorted(
        p.name
        for p in profiles_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ) if profiles_dir.is_dir() else []

    # Point read-only topology helpers at the same named profile Orion launches.
    previous_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(profile_home)
    try:
        standalone = profile_is_standalone(profile_home)
        default_explicit = explicit_multiplex_flag(root)
        offline_host_verdict = host_serves_named_profile(root, profile_home)
        served = profiles_to_serve(multiplex=True, include_parked=True)
    finally:
        if previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous_home

    served_names = sorted({p.name for p in served})
    after = {str(p): sha256(p) for p in watched}
    if before != after:
        raise RuntimeError("Read-only topology inventory detected a watched configuration mutation")

    if standalone:
        risk = "STANDALONE_SHIM_ALREADY_SET"
    elif len(served) < 2:
        risk = "SINGLE_PROFILE_GUARD"
    else:
        # None means boot decides; with >=2 profiles this is the path that may
        # auto-converge once transient migration blockers are absent.
        risk = "MULTIPLEX_AUTO_MIGRATION_POSSIBLE"

    print(f"HERMES_ROOT_PRESENT={str(root.is_dir()).lower()}")
    print(f"COMPANION_PROFILE_PRESENT={str(profile_home.is_dir()).lower()}")
    print(f"NAMED_PROFILE_COUNT={len(profile_names)}")
    print("NAMED_PROFILES=" + (",".join(profile_names) if profile_names else "<none>"))
    print(f"COMPANION_STANDALONE={str(bool(standalone)).lower()}")
    print(f"DEFAULT_MULTIPLEX_EXPLICIT={token(default_explicit)}")
    print(f"OFFLINE_HOST_SERVES_COMPANION={token(offline_host_verdict)}")
    print(f"MULTIPLEX_SERVABLE_PROFILE_COUNT={len(served_names)}")
    print("MULTIPLEX_SERVABLE_PROFILES=" + (",".join(served_names) if served_names else "<none>"))
    print(f"V0225_TOPOLOGY_RISK={risk}")
    print("WATCHED_CONFIG_UNCHANGED=PASS")
    print("WRITES_PERFORMED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
