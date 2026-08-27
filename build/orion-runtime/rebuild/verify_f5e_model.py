from pathlib import Path
import hashlib
import os

REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
EXPECTED = {
    "model.safetensors": "3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad",
    "tokenizer.json": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    "config.json": "094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750",
}

hf_home = Path(os.environ.get("HF_HOME", "/opt/iai/hf"))
snapshot = hf_home / "hub" / "models--BAAI--bge-small-en-v1.5" / "snapshots" / REVISION

if not snapshot.is_dir():
    raise SystemExit(f"expected pinned snapshot missing: {snapshot}")

for name, expected in EXPECTED.items():
    path = snapshot / name
    if not path.is_file():
        raise SystemExit(f"missing model artifact: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"hash mismatch for {name}: {actual}")

print("F5E_OFFLINE_MODEL_VERIFY=PASS")
