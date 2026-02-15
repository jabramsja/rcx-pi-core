#!/usr/bin/env bash
set -euo pipefail
export PAGER=cat GIT_PAGER=cat LESS='-FRSX'
chmod +x scripts/green_gate.sh
bash scripts/green_gate.sh
