#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== RCX-π Rust: green examples suite =="

cargo run --quiet --example classify_cli -- rcx_core "[null,a]"
cargo run --quiet --example classify_cli -- paradox_1over0 "[1/0]"

cargo run --quiet --example classify_cli -- vars_demo "[inf,a]" | rg -q "route: Some\\(Lobe\\)" || { echo "FAIL: vars_demo [inf,a] not Lobe"; exit 1; }
echo "OK: vars_demo [inf,a] -> Lobe"

cargo run --quiet --example classify_cli -- vars_demo "[paradox,a]" | rg -q "route: Some\\(Sink\\)" || { echo "FAIL: vars_demo [paradox,a] not Sink"; exit 1; }
echo "OK: vars_demo [paradox,a] -> Sink"

cargo run --quiet --example orbit_cli -- pingpong "ping" 12
cargo run --quiet --example state_demo

echo "✅ rust examples suite green"
