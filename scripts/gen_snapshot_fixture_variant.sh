#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

(cd rcx_pi_rust && cargo build --examples)

# Same world + rules (rcx_core), but change initial bucket seeds.
# IMPORTANT: keep world=rcx_core so program.rules stays identical; only state differs.
(cd rcx_pi_rust && cargo run --example snapshot_json_cli -- rcx_core "[null,b]" "[inf,b]" "[paradox,b]" "[omega,[b,c]]" \
  > ../docs/fixtures/snapshot_rcx_core_v1_variant.json)
