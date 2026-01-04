#!/usr/bin/env bash
set -euo pipefail
export HISTTIMEFORMAT="${HISTTIMEFORMAT-}"

cd "$(git rev-parse --show-toplevel)"

MODE="${1:-fast}"   # fast | full | python | rust | help

usage() {
  cat <<'USAGE'
usage: scripts/rcx_rehydrate.sh [fast|full|python|rust|help]

Purpose:
- Generate a single paste block for a NEW ChatGPT session that:
  - pins the contract
  - pins repo identity (remote/branch/head)
  - shows where to look (entry points + dirs)
  - shows the task taxonomy anchors (OPTIONAL/DEFERRED/OUT OF SCOPE)
  - optionally runs truth gates (full/python/rust)

Modes:
- fast   (default): NO tests. Quick + paste-friendly.
- full   : runs scripts/green_gate.sh all
- python : runs scripts/green_gate.sh python-only
- rust   : runs scripts/green_gate.sh rust-only
- help   : show this message
USAGE
}

if [[ "$MODE" == "help" || "$MODE" == "-h" || "$MODE" == "--help" ]]; then
  usage
  exit 0
fi

cat <<'CONTRACT'
============================================================
YOU ARE RCX LIBRARIAN MODE + RCX PAIR ENGINEER.

Hard rules:
1) Closed-world default. You must not claim anything about my repo unless I paste it (or I paste command output).
2) Your job is to give me ONE copy-paste-ready terminal block per response (full replacements/heredocs), unless I explicitly ask otherwise.
3) No “wait”, no “should work”, no fake completion. If you can’t verify from my pasted output, say: “Not found in provided corpus/output.”
4) When debugging, ask for the ONE minimum command output you need, then proceed. No multi-question interrogations.
5) Treat files as:
   - Ra = implemented
   - Lobes = ideas / backlog
   - Sink = impossible / parked
   Keep tasks in that taxonomy.

You are bound by this contract for the remainder of the session.
============================================================
CONTRACT

echo
echo "== RCX REHYDRATE BRIEFING =="
echo "mode: $MODE"
echo

echo "-- Repo / Remote --"
git remote -v | sed -n '1,2p' || true
echo

echo "-- Branch / Commit --"
echo "branch: $(git branch --show-current 2>/dev/null || echo '<detached>')"
echo "head:   $(git rev-parse HEAD)"
git show -s --format='head_msg: %ci %s' HEAD || true
echo

echo "-- Key entry points (repo root) --"
for f in rcx_start.py rcx_runtime.py TASKS.md README_BOOTSTRAP.MD README.md .rcx_manifest.json; do
  if [ -f "$f" ]; then echo "present: $f"; else echo "missing: $f"; fi
done
echo

echo "-- Key dirs (repo root) --"
for d in rcx_omega rcx_pi rcx_pi_rust rcx_python_examples scripts tests docs schemas worlds_json .rcx_library; do
  if [ -d "$d" ]; then echo "present: $d/"; else echo "missing: $d/"; fi
done
echo

echo "-- Workflows present --"
ls -la .github/workflows 2>/dev/null || echo "No .github/workflows/"
echo

echo "-- Task taxonomy anchors (OPTIONAL / DEFERRED / OUT OF SCOPE) --"
if [ -f TASKS.md ]; then
  egrep -n "^\*\*Status:\*\* 🟡 OPTIONAL|^\*\*Status:\*\* ⏸ DEFERRED|^\*\*Status:\*\* 🚫 OUT OF SCOPE|^## [FGHI]\." TASKS.md || true
else
  echo "Not found in provided corpus/output: TASKS.md"
fi
echo

echo "-- TASKS (first 70 lines for kernel status + invariants) --"
if [ -f TASKS.md ]; then
  sed -n '1,70p' TASKS.md
else
  echo "Not found in provided corpus/output: TASKS.md"
fi
echo

# Optional truth run (explicit; not default)
run_gate() {
  local gate_mode="$1"
  if [ -x scripts/green_gate.sh ]; then
    echo "-- Truth gate --"
    echo "running: scripts/green_gate.sh $gate_mode"
    echo
    scripts/green_gate.sh "$gate_mode"
    echo
  else
    echo "Not found in provided corpus/output: scripts/green_gate.sh"
    exit 2
  fi
}

case "$MODE" in
  fast)   : ;;
  full)   run_gate "all" ;;
  python) run_gate "python-only" ;;
  rust)   run_gate "rust-only" ;;
  *)
    echo "ERROR: unknown mode: $MODE"
    echo
    usage
    exit 2
    ;;
esac

cat <<'NEXT'
============================================================
NEXT STEP (DO NOT SKIP):

Paste EVERYTHING ABOVE into a NEW ChatGPT session.
Say NOTHING ELSE.

The assistant must respond by:
1) Acknowledging the contract
2) Producing a “Now” task list (max 5) mapped to Ra / Lobe / Sink
3) Giving ONE terminal block for the next concrete task

If it does anything else, it has violated the contract.
============================================================
NEXT
