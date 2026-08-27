from pathlib import Path
import hashlib
import importlib.metadata
import os
import subprocess
import sys

HUGGINGFACE_HUB_VERSION = "0.34.1"
REPO_ID = "BAAI/bge-small-en-v1.5"
REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
EXPECTED = {
    "model.safetensors": "3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad",
    "tokenizer.json": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    "config.json": "094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750",
}


def ensure_huggingface_hub():
    try:
        version = importlib.metadata.version("huggingface-hub")
    except importlib.metadata.PackageNotFoundError:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--no-cache-dir",
                "--only-binary=:all:",
                f"huggingface-hub=={HUGGINGFACE_HUB_VERSION}",
            ],
            check=True,
        )
        version = importlib.metadata.version("huggingface-hub")

    if version != HUGGINGFACE_HUB_VERSION:
        raise SystemExit(
            f"unexpected huggingface-hub version: {version}; "
            f"expected {HUGGINGFACE_HUB_VERSION}"
        )

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from huggingface_hub import snapshot_download

    print(f"F5E_ACQUISITION_DEPENDENCY=huggingface-hub=={version}")
    print("F5E_ACQUISITION_DEPENDENCY=PASS")
    return snapshot_download


snapshot_download = ensure_huggingface_hub()

hf_home = Path(os.environ.get("HF_HOME", "/opt/iai/hf"))
snapshot = Path(
    snapshot_download(
        repo_id=REPO_ID,
        revision=REVISION,
        cache_dir=str(hf_home / "hub"),
    )
)

for name, expected in EXPECTED.items():
    path = snapshot / name
    if not path.is_file():
        raise SystemExit(f"missing model artifact: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"hash mismatch for {name}: {actual}")

print(f"F5E_SNAPSHOT={snapshot}")
print("F5E_MODEL_ARTIFACTS=PASS")
