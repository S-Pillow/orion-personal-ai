from pathlib import Path
import importlib.util
import py_compile

spec = importlib.util.find_spec("iai_mcp.core._serializers")
if spec is None or not spec.origin:
    raise SystemExit("serializer module not found")

path = Path(spec.origin)
text = path.read_text(encoding="utf-8")

old = '        "wake_depth": getattr(payload, "wake_depth", "minimal"),\n    }\n'
new = (
    '        "wake_depth": getattr(payload, "wake_depth", "minimal"),\n'
    '        "recent_thread": getattr(payload, "recent_thread", ""),\n'
    '    }\n'
)

if '"recent_thread": getattr(payload, "recent_thread", "")' in text:
    raise SystemExit("serializer already contains recent_thread; refusing non-baseline overlay")

if text.count(old) != 1:
    raise SystemExit(f"expected exactly one serializer anchor, found {text.count(old)}")

patched = text.replace(old, new, 1)
path.write_text(patched, encoding="utf-8")
py_compile.compile(str(path), doraise=True)

print("M5_RECENT_THREAD_OVERLAY=PASS")
