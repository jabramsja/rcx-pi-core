#!/usr/bin/env bash
set -euo pipefail

TAG="${TAG:-rcx-omega-stable-baseline-20260103}"
REPO_SLUG="${REPO_SLUG:-jabramsja/rcx-pi-core}"

# Must be run from repo root (avoid scanning home dirs / permission spam)
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "ERROR: not inside a git repo. cd to repo root and re-run."
  exit 2
}

echo "== RCX-Ω Status Postcard =="
echo

echo "-- Repo --"
git remote -v | sed -n '1,2p' || true
echo

echo "-- Branch / Commit --"
echo "branch: $(git branch --show-current)"
echo "head:   $(git rev-parse HEAD)"
git show -s --format='head_msg: %ci %s' HEAD
echo

echo "-- Baseline Tag --"
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "tag:    $TAG"
  echo "tag->:  $(git rev-list -n 1 "$TAG")"
else
  echo "tag:    <not found locally>"
fi
echo

echo "-- GitHub Release URL --"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh -R "$REPO_SLUG" release view "$TAG" --json url -q '.url' || echo "<release not found>"
else
  echo "gh not available/authenticated (skip)"
fi
echo

echo "-- Truth Gate --"
python3 -m pytest -q
