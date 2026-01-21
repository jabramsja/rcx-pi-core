#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

e() { echo "== $* =="; }

e "1/5 replay fixture gate"
./scripts/check_replay_fixture.sh

e "2/5 orbit DOT fixture gate"
./scripts/check_orbit_dot_fixture.sh

e "3/5 orbit SVG semantic gate"
./scripts/check_orbit_svg_fixture.sh

e "4/5 orbit index semantic gate"
./scripts/check_orbit_index_fixture.sh

e "5/5 done"
echo "OK: all deterministic gates passed"
