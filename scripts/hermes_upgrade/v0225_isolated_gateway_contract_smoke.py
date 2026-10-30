#!/usr/bin/env python3
"""Compatibility entry point for the hardened isolated gateway smoke.

The original implementation deep-copied production COMPANION config into scratch
state and is intentionally retired. Keep this filename as a safe delegating entry
point so older operator commands cannot execute the retired implementation.
"""
from v0225_isolated_gateway_contract_smoke_v2 import main


if __name__ == "__main__":
    raise SystemExit(main())
