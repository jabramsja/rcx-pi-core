#!/usr/bin/env bash
set -euo pipefail

# Run from repo root regardless of caller cwd.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Stable invocation surface:
#   scripts/world_trace.sh --help
#   scripts/world_trace.sh --max-steps 50 --json --pretty < world.json
exec python3 -m rcx_pi.worlds.world_trace_cli "$@"
