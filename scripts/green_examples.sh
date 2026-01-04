#!/usr/bin/env bash
set -euo pipefail

# Repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# RCX rust lives under rcx_pi_rust/
if [ -f rcx_pi_rust/Cargo.toml ]; then
  # Prefer the canonical script inside rcx_pi_rust if present
  if [ -x rcx_pi_rust/scripts/green_examples.sh ]; then
    exec bash rcx_pi_rust/scripts/green_examples.sh
  fi

  # Fallback: run the same commands from within rcx_pi_rust
  cd rcx_pi_rust
  echo "== RCX-π Rust: green examples suite =="

  cargo run --quiet --example classify_cli -- rcx_core "[null,a]"
  cargo run --quiet --example classify_cli -- paradox_1over0 "[1/0]"

  # ripgrep is expected on CI; locally you likely have it already
  cargo run --quiet --example classify_cli -- vars_demo "[inf,a]" | rg -q "route: Some\\(Lobe\\)" || { echo "FAIL: vars_demo [inf,a] not Lobe"; exit 1; }
  echo "OK: vars_demo [inf,a] -> Lobe"

  cargo run --quiet --example classify_cli -- vars_demo "[paradox,a]" | rg -q "route: Some\\(Sink\\)" || { echo "FAIL: vars_demo [paradox,a] not Sink"; exit 1; }
  echo "OK: vars_demo [paradox,a] -> Sink"

  cargo run --quiet --example orbit_cli -- pingpong "ping" 12
  cargo run --quiet --example state_demo

  echo "✅ rust examples suite green"
  exit 0
fi

echo "SKIP: no rcx_pi_rust/Cargo.toml; Rust examples gate not applicable."
exit 0
