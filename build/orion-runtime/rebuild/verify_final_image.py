import importlib.metadata
import inspect
import sys

from iai_mcp.session import SessionStartPayload
from iai_mcp.core._serializers import _payload_to_json

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"unexpected iai Python: {sys.version}")

if importlib.metadata.version("iai-pme") != "3.0.8":
    raise SystemExit("iai-pme version is not 3.0.8")

payload = SessionStartPayload(wake_depth="standard", recent_thread="orion-rebuild-check")
serialized = _payload_to_json(payload)

if serialized.get("recent_thread") != "orion-rebuild-check":
    raise SystemExit("recent_thread serializer contract failed")

if '"recent_thread"' not in inspect.getsource(_payload_to_json):
    raise SystemExit("recent_thread serializer source marker missing")

print("REBUILD_IAI_VERSION=3.0.8")
print("REBUILD_RECENT_THREAD_SERIALIZER=PASS")
print("REBUILD_FINAL_IMAGE_VERIFY=PASS")
