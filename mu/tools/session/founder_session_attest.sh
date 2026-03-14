#!/usr/bin/env bash
set -uo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./tools/session/founder_session_attest.sh <mode>

Modes:
  redteam
  parity
  docs
  closeout

Purpose:
  Run narrow attestation checks that founder bootstrap / broad green suites do not
  prove by themselves:
  - proof-class mismatch in L4 JS parity/runtime gates
  - active founder-facing doc governance blind spots
  - root README current-state drift against canonical STATUS truth
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -eq 0 ]; then
    usage
    exit 0
fi

MODE="$1"
shift || true

case "$MODE" in
    redteam|parity|docs|closeout)
        ;;
    *)
        echo "ERROR: unknown mode '$MODE'" >&2
        usage >&2
        exit 2
        ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "ERROR: must run inside the WorkingRCX git repo" >&2
    exit 2
}
cd "$REPO_ROOT"

FAILURES=0

run_check() {
    local title="$1"
    shift
    echo "=== $title ==="
    if "$@"; then
        echo "OK"
    else
        local status=$?
        echo "FAIL (exit $status)"
        FAILURES=$((FAILURES + 1))
    fi
    echo ""
}

check_js_claim_proof_contracts() {
    python3 - <<'PY'
import json
import subprocess
import sys

out = subprocess.check_output(
    ['python3', 'tools/checks/check_gate_behavioral_pairs.py', '--json'],
    text=True,
)
data = json.loads(out)['files']
issues = []

for rel, file_data in sorted(data.items()):
    for class_name, methods in file_data.get('classes', {}).items():
        text = class_name.lower()
        if 'js' not in text:
            continue
        if 'parity' not in text and 'runtime' not in text and 'wiring' not in text:
            continue
        cats = set(methods.values())
        if 'behavioral' in cats or 'hybrid' in cats:
            continue
        if cats == {'source_lock'}:
            issues.append((rel, class_name, sorted(cats)))

if issues:
    print("JS proof-class contract violations:")
    for rel, class_name, cats in issues:
        print(f"  {rel}::{class_name} -> {cats}")
    sys.exit(1)

print("No JS parity/runtime classes are source-lock-only.")
PY
}

check_active_report_governance() {
    python3 - <<'PY'
import sys
from pathlib import Path
from tools.docs.shared_doc_config import classify_md_path, REPO_ROOT

codex_dir = REPO_ROOT / 'reports' / 'codex'
issues = []
for path in sorted(codex_dir.rglob('*.md')):
    rel = path.relative_to(REPO_ROOT)
    parts = rel.parts
    if 'archive' in [p.lower() for p in parts] or 'Archive' in parts:
        continue
    kind = classify_md_path(path)
    if kind == 'exempt':
        issues.append(str(rel))

if issues:
    print("Active reports/codex markdown is still exempt from docs governance:")
    for rel in issues[:20]:
        print(f"  {rel}")
    if len(issues) > 20:
        print(f"  ... and {len(issues) - 20} more")
    sys.exit(1)

print("Active reports/codex markdown is not exempt from governance.")
PY
}

check_root_readme_truth() {
    python3 - <<'PY'
import re
import sys
from pathlib import Path

readme = Path('README.md').read_text(encoding='utf-8')
status = Path('STATUS.md').read_text(encoding='utf-8')
issues = []

status_current = re.search(r'CURRENT[:\s]+(\d+)', status)
readme_tracked = re.search(r'(\d+)\s+tracked\s+@host_', readme, re.I)
if status_current and readme_tracked:
    if int(status_current.group(1)) != int(readme_tracked.group(1)):
        issues.append(
            f"README tracked marker count {readme_tracked.group(1)} != STATUS CURRENT {status_current.group(1)}"
        )

if 'open feasibility questions' in readme and '_STAGE0_VM_CUTOVER = False' in status:
    issues.append(
        "README still frames L4 only as open feasibility while current repo truth has active Stage0 reduction work"
    )

if issues:
    print("Root README current-state drift:")
    for issue in issues:
        print(f"  {issue}")
    sys.exit(1)

print("Root README current-state claims align with STATUS current truth checks.")
PY
}

echo "RCX Founder Session Attestation"
echo "mode: $MODE"
echo "repo: $REPO_ROOT"
echo ""

case "$MODE" in
    redteam)
        run_check "JS claim proof contracts" check_js_claim_proof_contracts
        run_check "Active report governance" check_active_report_governance
        run_check "Root README truth" check_root_readme_truth
        ;;
    parity)
        run_check "JS claim proof contracts" check_js_claim_proof_contracts
        ;;
    docs)
        run_check "Active report governance" check_active_report_governance
        run_check "Root README truth" check_root_readme_truth
        ;;
    closeout)
        run_check "JS claim proof contracts" check_js_claim_proof_contracts
        run_check "Active report governance" check_active_report_governance
        run_check "Root README truth" check_root_readme_truth
        ;;
esac

if [ "$FAILURES" -ne 0 ]; then
    echo "Founder session attestation found $FAILURES failing check(s)." >&2
    exit 1
fi

echo "Founder session attestation passed."
