#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

./scripts/build_orbit_artifacts.sh >/dev/null

# Serve docs/fixtures so fetch() works reliably in browsers (file:// can be finicky).
PORT="${PORT:-8009}"
cd docs/fixtures

echo "Serving fixtures at: http://127.0.0.1:${PORT}/index.html"
python3 -m http.server "$PORT" >/dev/null 2>&1 &
PID=$!
cleanup(){ kill "$PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# macOS open
open "http://127.0.0.1:${PORT}/index.html"

# Keep server alive until you Ctrl+C
wait "$PID"
