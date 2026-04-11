#!/usr/bin/env bash
# Smoke test suite for .claude/hooks/block-protected-branch.sh tokenizer
# rewrite (2026-04-11). Covers the 9 scenarios from
# reports/control_plane/block_protected_branch_lexer_2026-04-11.md
# Work Item 4 and Acceptance criterion 1, plus the helper-level
# fail-closed contract for scenario J (acceptance 6) and the overhead
# bound (acceptance 3).
#
# Exit 0 if all scenarios pass, non-zero otherwise.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/block-protected-branch.sh"
HELPER="$SCRIPT_DIR/_block_protected_branch_tokenize.py"

if [ ! -x "$HOOK" ]; then
  echo "ERROR: $HOOK not found or not executable" >&2
  exit 3
fi
if [ ! -f "$HELPER" ]; then
  echo "ERROR: $HELPER not found" >&2
  exit 3
fi

# Create a throwaway git repo on a protected branch so the hook's
# branch check fires. We use `main` because it's in the protected set
# (dev|main|master).
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
(
  cd "$TMP"
  git init -q .
  git symbolic-ref HEAD refs/heads/main
  git config user.email test@example.invalid
  git config user.name tester
  git commit -q --allow-empty -m "init"
) >/dev/null 2>&1

export CLAUDE_PROJECT_DIR="$TMP"

PASS=0
FAIL=0
FAILURES=""

# run_scenario NAME EXPECT CMD [REASON_SUBSTRING]
#   NAME:             scenario label (A, B, C, ...)
#   EXPECT:           "BLOCK" or "NO_BLOCK"
#   CMD:              command string the hook sees as tool_input.command
#   REASON_SUBSTRING: optional; if set, also require the hook's reason
#                     field to contain this substring
run_scenario() {
  local name="$1"; shift
  local expect="$1"; shift
  local cmd="$1"; shift
  local reason_subs="${1:-}"

  local input_json
  input_json=$(jq -cn --arg c "$cmd" '{tool_input: {command: $c}}')

  local output
  output=$(printf '%s' "$input_json" | bash "$HOOK" 2>/dev/null || true)

  local decision=""
  if [ -n "$output" ]; then
    decision=$(printf '%s' "$output" | jq -r '.decision // ""' 2>/dev/null || echo "")
  fi

  local actual="NO_BLOCK"
  if [ "$decision" = "block" ]; then
    actual="BLOCK"
  fi

  if [ "$actual" != "$expect" ]; then
    FAIL=$((FAIL + 1))
    FAILURES+="
  [$name] EXPECTED $expect but got $actual
    cmd:    $(printf '%q' "$cmd")
    output: $output"
    return
  fi

  if [ -n "$reason_subs" ]; then
    local reason
    reason=$(printf '%s' "$output" | jq -r '.reason // ""' 2>/dev/null || echo "")
    if [[ "$reason" != *"$reason_subs"* ]]; then
      FAIL=$((FAIL + 1))
      FAILURES+="
  [$name] reason did not contain expected substring
    expected substring: $reason_subs
    actual reason:      $reason"
      return
    fi
  fi

  PASS=$((PASS + 1))
  printf '  PASS  [%s] %s\n' "$name" "$expect"
}

echo "Running block-protected-branch smoke suite (hook-level)..."

# Pre-existing scenarios (verified by this wave, not introduced by it).
run_scenario A  BLOCK    "$(printf '# comment\ngit commit -m x')"
run_scenario B  NO_BLOCK 'echo hello # git commit'
run_scenario C  NO_BLOCK 'echo "git commit"'
run_scenario D  BLOCK    'git commit -m test'
run_scenario F  NO_BLOCK 'git checkout -b pre-commit-fix'
run_scenario G  BLOCK    'echo foo#bar; git commit -m x'
run_scenario H  BLOCK    "echo ' #foo'; git commit -m x"

# New scenarios added by this wave.
run_scenario I  NO_BLOCK "$(printf 'cat <<EOF\n# git commit\nEOF')"
run_scenario J  BLOCK    "echo 'unclosed" "tokenizer parser error"

# Regression invariance checks (acceptance criterion 7): NO_BLOCK for
# ordinary read-only git commands so we know the tokenizer rewrite did
# not introduce new false-positives in the happy path.
run_scenario K1 NO_BLOCK 'git status'
run_scenario K2 NO_BLOCK 'git log --oneline'
run_scenario K3 NO_BLOCK 'git diff'
run_scenario K4 NO_BLOCK 'git fetch'
run_scenario K5 NO_BLOCK 'git -C /some/path status'

echo
echo "Running helper-level direct probes..."

# Acceptance criterion 6: scenario J helper-level contract.
#   stdout empty, rc=2, stderr contains 'unclosed single quote'.
probe_helper_j() {
  local name="helper-J"
  local out rc err err_file
  err_file=$(mktemp)
  out=$(printf '%s' "echo 'unclosed" | python3 "$HELPER" 2>"$err_file") || rc=$?
  rc=${rc:-0}
  err=$(cat "$err_file")
  rm -f "$err_file"
  if [ "$rc" != "2" ]; then
    FAIL=$((FAIL + 1))
    FAILURES+="
  [$name] expected rc=2, got rc=$rc"
    return
  fi
  if [ -n "$out" ]; then
    FAIL=$((FAIL + 1))
    FAILURES+="
  [$name] expected empty stdout, got: $(printf '%q' "$out")"
    return
  fi
  if [[ "$err" != *"unclosed single quote"* ]]; then
    FAIL=$((FAIL + 1))
    FAILURES+="
  [$name] stderr did not contain 'unclosed single quote'
    actual stderr: $err"
    return
  fi
  PASS=$((PASS + 1))
  printf '  PASS  [%s] rc=2, stdout empty, stderr contains substring\n' "$name"
}

probe_helper_j

# Acceptance criterion 3: overhead bound <200ms for `git status`.
# Stdout must be exactly 'git\nstatus', exit status 0. We measure 5
# runs and use the median to guard against one-off scheduling noise.
probe_helper_overhead() {
  local name="helper-overhead"
  local out
  out=$(printf '%s' "git status" | python3 "$HELPER")
  if [ "$out" != "$(printf 'git\nstatus')" ]; then
    FAIL=$((FAIL + 1))
    FAILURES+="
  [$name] stdout mismatch
    expected: 'git\\nstatus'
    actual:   $(printf '%q' "$out")"
    return
  fi
  local real_ms
  real_ms=$(HELPER_PATH="$HELPER" python3 - <<'PY'
import os, subprocess, time
helper = os.environ["HELPER_PATH"]
runs = []
for _ in range(5):
    t0 = time.perf_counter()
    subprocess.run(
        ["python3", helper],
        input=b"git status",
        check=True,
        capture_output=True,
    )
    runs.append((time.perf_counter() - t0) * 1000)
runs.sort()
print(int(runs[2]))  # median of 5
PY
)
  if ! [[ "$real_ms" =~ ^[0-9]+$ ]]; then
    FAIL=$((FAIL + 1))
    FAILURES+="
  [$name] could not measure time (got: $real_ms)"
    return
  fi
  if [ "$real_ms" -ge 200 ]; then
    FAIL=$((FAIL + 1))
    FAILURES+="
  [$name] overhead ${real_ms}ms >= 200ms bound"
    return
  fi
  PASS=$((PASS + 1))
  printf '  PASS  [%s] median overhead=%sms (< 200ms bound)\n' "$name" "$real_ms"
}

probe_helper_overhead

echo
echo "================================================"
echo "PASS: $PASS  FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "FAILURES:$FAILURES"
  exit 1
fi
echo "All scenarios passed."
exit 0
