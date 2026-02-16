#!/usr/bin/env bash
set -euo pipefail
export HISTTIMEFORMAT="${HISTTIMEFORMAT-}"

cd "$(git rev-parse --show-toplevel)"

python3 scripts/rcx_manifest.py "$@"

echo
echo "-- quick peek --"
python3 - <<'PY'
import json
from pathlib import Path
p = Path(".rcx_manifest.json")
obj = json.loads(p.read_text(encoding="utf-8"))
print("format:", obj.get("format"))
print("file_count:", obj.get("file_count"))
print("manifest_sha256:", obj.get("manifest_sha256"))
print("included_roots:", obj.get("included_roots"))
print("missing_roots:", obj.get("missing_roots"))
PY
