#!/usr/bin/env bash
# _pane_findings.sh — Bridge review findings pane for tmux
# Shows blocking/non-blocking findings from latest bridge rounds.
set +e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUS_DIR="${RCX_AGENT_BUS_DIR:-${BUS_DIR:-.agent_bus}}"
if [[ "$BUS_DIR" == /* || "$BUS_DIR" == *"/"* || "$BUS_DIR" == *"\\"* || "$BUS_DIR" == *".."* ]]; then
  echo "ERROR: invalid RCX_AGENT_BUS_DIR: $BUS_DIR" >&2
  exit 2
fi
if [[ "$BUS_DIR" != ".agent_bus" && ! "$BUS_DIR" =~ ^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  echo "ERROR: RCX_AGENT_BUS_DIR must be .agent_bus or .agent_bus-<id>" >&2
  exit 2
fi
resolve_repo_root() {
  local helper="$SCRIPT_DIR/_resolve_live_root.sh"
  local root=""
  if [ -f "$helper" ]; then
    root=$(bash "$helper" 2>/dev/null || true)
  fi
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}
resolve_branch_name_for_root() {
  local root="${1:-$REPO_ROOT}"
  git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}
refresh_context() {
  local next_root="" next_branch=""
  # Optional autofollow (WI-2B): when RCX_OBS_AUTOFOLLOW_BUS=1, re-resolve the
  # freshest active (root,bus) pair each refresh and rebind the effective bus so
  # the default monitor's panes follow the freshest active lane. Fail-safe: empty
  # or invalid helper output keeps the CURRENT bus (never blank, never error,
  # validation unchanged). Signal unset = today's behavior exactly.
  if [ "${RCX_OBS_AUTOFOLLOW_BUS:-}" = "1" ]; then
    local _af_helper="$SCRIPT_DIR/_resolve_live_root.sh" _af_root="" _af_bus=""
    if [ -f "$_af_helper" ]; then
      { IFS= read -r _af_root; IFS= read -r _af_bus; } < <(RCX_AGENT_BUS_DIR="$BUS_DIR" bash "$_af_helper" --emit-pair 2>/dev/null) || true
    fi
    if [ -n "$_af_root" ] && { [ "$_af_bus" = ".agent_bus" ] || [[ "$_af_bus" =~ ^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; }; then
      BUS_DIR="$_af_bus"
      export BUS_DIR
      export RCX_AGENT_BUS_DIR="$_af_bus"
      next_root="$_af_root"
    fi
  fi
  [ -n "$next_root" ] || next_root="$(resolve_repo_root)"
  [ -n "$next_root" ] || next_root="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
  next_branch="$(resolve_branch_name_for_root "$next_root")"
  if [ "${REPO_ROOT:-}" != "$next_root" ] || [ "${BRANCH_NAME:-}" != "$next_branch" ]; then
    LAST_HASH=""
  fi
  REPO_ROOT="$next_root"
  RAW_DIR="$REPO_ROOT/$BUS_DIR/raw"
  BRANCH_NAME="$next_branch"
}
REPO_ROOT=""
RAW_DIR=""
BRANCH_NAME=""
BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"
LAST_HASH=""
TMPOUT="/tmp/rcx_pane_findings_$$.txt"
NOTIFY_MARKER="${RCX_PANE_NOTIFY_MARKER:-/tmp/rcx_last_notified_round.txt}"
LAST_NOTIFIED_ROUND=$(cat "$NOTIFY_MARKER" 2>/dev/null || echo "")
ONESHOT="${RCX_PANE_ONESHOT:-0}"

notify() {
  local title="$1" msg="$2" round="$3"
  # Oneshot renders are automation/test reads; keep them side-effect free.
  if [ "$ONESHOT" = "1" ]; then
    return 0
  fi
  if command -v osascript >/dev/null 2>&1; then
    osascript - "$title" "$msg" >/dev/null 2>&1 <<'APPLESCRIPT' &
on run argv
  display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"
end run
APPLESCRIPT
  fi
  echo "$round" > "$NOTIFY_MARKER"
}

parse_agent_envelope_file() {
  python3 - "$1" "${2:-}" <<'PY'
import json
import re
import sys

review_source = sys.argv[1]
reviewer_file = sys.argv[2] if len(sys.argv) > 2 else ""

def _read(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""

def _latest_json_envelope(content):
    matches = list(re.finditer(r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE", content, re.DOTALL))
    for match in reversed(matches):
        try:
            candidate = json.loads(match.group(1))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        if not isinstance(candidate, dict):
            continue
        dec = candidate.get("decision", "")
        if dec and "|" not in dec:
            return candidate
    return None

def _markdown_envelope(content):
    sections = list(re.finditer(r"(?ms)^### .*? — reviewer\n(.*?)(?=^### |\Z)", content))
    decision_re = re.compile(r"(?m)^\s*-\s*Decision:\s*(COMMIT_GO|GO|REQUEST_CHANGES|NO_GO|QUESTION|STALE|ERROR|SYNTHETIC)\b")
    summary_re = re.compile(r"(?m)^\s*-\s*Summary:\s*(.*)")
    finding_re = re.compile(r"(?m)^\s*\d+\.\s+\*\*(DEFECT|POLICY_BOUND|DOC_ACCURACY)\*\* \(([^)]+)\):\s*(.*)$")
    for section in reversed(sections):
        block = section.group(1)
        decision_match = decision_re.search(block)
        if not decision_match:
            continue
        dec = decision_match.group(1)
        if dec == "SYNTHETIC":
            continue
        summary_match = summary_re.search(block)

        def _md_disposition(cls, sev, dec):
            severity = sev.strip().lower()
            if severity in ("critical", "high"):
                return "blocking"
            if cls in ("DOC_ACCURACY", "POLICY_BOUND") and severity in ("medium", "low"):
                return "non_blocking"
            return "non_blocking" if dec == "GO" else "blocking"

        return {
            "decision": dec,
            "summary": summary_match.group(1).strip() if summary_match else "",
            "findings": [
                {
                    "class": cls,
                    "severity": sev.strip().lower(),
                    "title": title.strip(),
                    "disposition": _md_disposition(cls, sev, dec),
                }
                for cls, sev, title in finding_re.findall(block)
            ],
        }
    return None

content = _read(review_source)
env = _latest_json_envelope(content)
if env is None and reviewer_file and reviewer_file != review_source:
    env = _latest_json_envelope(_read(reviewer_file))
if env is None:
    env = _markdown_envelope(content)
if env is None:
    sys.exit(0)

findings = env.get("findings", []) or []
blocking = [finding for finding in findings if finding.get("disposition") == "blocking"]
non_blocking = [finding for finding in findings if finding.get("disposition") != "blocking"]
print(f"DECISION={env.get('decision', '?')}")
print(f"SUMMARY={(env.get('summary', '') or '')[:120]}")
print(f"BLOCKING={len(blocking)}")
print(f"NONBLOCKING={len(non_blocking)}")
for finding in blocking:
    sev = finding.get("severity", "?")
    title = (finding.get("title") or finding.get("description") or "?")[:100]
    print(f"BLK|{sev}|{title}")
for finding in non_blocking:
    sev = finding.get("severity", "?")
    title = (finding.get("title") or finding.get("description") or "?")[:100]
    print(f"NB|{sev}|{title}")
PY
}

render_findings_lines() {
  # Shared BLK|/NB| finding renderer. Reused by the latest-round block and the
  # clean-GO review-history block so finding lines format identically. Takes the
  # parse_agent_envelope_file output (with BLK|/NB| lines) as its only argument.
  local envelope="$1"
  echo "$envelope" | grep "^BLK|" | while IFS='|' read -r _ sev title; do
    case "$sev" in
      critical) sev_color="$RED" ;;
      high) sev_color="$RED" ;;
      medium) sev_color="$YELLOW" ;;
      *) sev_color="$DIM" ;;
    esac
    echo -e "    ${RED}B${RESET} ${sev_color}[$sev]${RESET} $title"
  done
  echo "$envelope" | grep "^NB|" | while IFS='|' read -r _ sev title; do
    case "$sev" in
      critical|high) sev_color="$YELLOW" ;;
      medium) sev_color="$YELLOW" ;;
      *) sev_color="$DIM" ;;
    esac
    echo -e "    ${YELLOW}N${RESET} ${sev_color}[$sev]${RESET} $title"
  done
}

render_clean_go_history() {
  # When the latest round is a clean GO/COMMIT_GO with zero findings, the
  # latest-round block alone reads "GO 0B 0NB" and the reviewer's earlier work
  # disappears. Re-surface it: (a) a one-line same-phase review arc, and (b) the
  # blocking/non-blocking titles of the most-recent PRIOR round that had
  # findings. Same-phase rounds only; reuses parse_agent_envelope_file (no second
  # parser). Caller guarantees this runs only on the clean-GO display path.
  local latest_round="$1"
  local rendered_dir="$REPO_ROOT/$BUS_DIR/rendered"
  local raw_dir="$REPO_ROOT/$BUS_DIR/raw"
  [ -d "$rendered_dir" ] || return 0

  # Phase prefix of the latest round (e.g. phase-a- / phase-b-): same-phase only.
  local phase_prefix=""
  if [[ "$latest_round" =~ ^(phase-[a-z]-) ]]; then
    phase_prefix="${BASH_REMATCH[1]}"
  else
    return 0
  fi

  # Round number of the latest round (after the phase prefix and optional reentry-).
  local latest_num=""
  local latest_rest="${latest_round#"$phase_prefix"}"
  latest_rest="${latest_rest#reentry-}"
  if [[ "$latest_rest" =~ ^r([0-9]+) ]]; then
    latest_num="${BASH_REMATCH[1]}"
  fi

  # Same-phase rendered rounds as "<num>\t<round>\t<file>", ordered by round number.
  # Restrict to the CURRENT bridge chain: a rendered round only counts if its live
  # raw round dir still exists. Rendered files persist across waves, but round
  # numbers (rN) restart each wave, so an orphaned phase-?-rN-*.md left over from a
  # previous Phase B wave would otherwise be pulled in as a bogus "prior round" of
  # this wave's chain. The raw dir is the same round universe the main render loop
  # keys off, so requiring it ties the history to the live chain.
  local sorted
  sorted=$(
    for f in "$rendered_dir/${phase_prefix}"*.md; do
      [ -s "$f" ] || continue
      rname="$(basename "$f" .md)"
      [ -d "$raw_dir/$rname" ] || continue
      rest="${rname#"$phase_prefix"}"
      rest="${rest#reentry-}"
      if [[ "$rest" =~ ^r([0-9]+) ]]; then
        printf '%s\t%s\t%s\n' "${BASH_REMATCH[1]}" "$rname" "$f"
      fi
    done | sort -n
  )
  [ -n "$sorted" ] || return 0

  # Build the arc and locate the most-recent prior round that had findings.
  local arc="" last_findings_round="" last_findings_file=""
  local num rname file env dec blk nb
  while IFS=$'\t' read -r num rname file; do
    [ -n "$num" ] || continue
    env="$(parse_agent_envelope_file "$file" 2>/dev/null)"
    dec="$(echo "$env" | grep '^DECISION=' | cut -d= -f2-)"
    blk="$(echo "$env" | grep '^BLOCKING=' | cut -d= -f2-)"
    nb="$(echo "$env" | grep '^NONBLOCKING=' | cut -d= -f2-)"
    [ -n "$dec" ] || dec="?"
    [ -n "$blk" ] || blk=0
    [ -n "$nb" ] || nb=0
    if [ -n "$arc" ]; then
      arc="$arc -> r${num} ${dec}.${blk}B"
    else
      arc="r${num} ${dec}.${blk}B"
    fi
    # "Prior" = a strictly-earlier round number than the latest, with findings.
    if [ -n "$latest_num" ] && [ "$num" -lt "$latest_num" ] 2>/dev/null \
       && [ "$(( ${blk:-0} + ${nb:-0} ))" -gt 0 ] 2>/dev/null; then
      last_findings_round="$num"
      last_findings_file="$file"
    fi
  done <<< "$sorted"

  [ -n "$arc" ] || return 0
  echo -e "  ${DIM}Review arc:${RESET} $arc"

  if [ -n "$last_findings_file" ]; then
    echo -e "  ${DIM}Last findings (r${last_findings_round}, addressed):${RESET}"
    render_findings_lines "$(parse_agent_envelope_file "$last_findings_file" 2>/dev/null)"
  fi
}

parse_meta_envelope_file() {
  python3 - "$1" <<'PY'
import json
import re
import sys

try:
    content = open(sys.argv[1], errors="replace").read()
except OSError:
    sys.exit(0)

matches = list(re.finditer(r"BEGIN_META_ENVELOPE\s*\n(.*?)\nEND_META_ENVELOPE", content, re.DOTALL))
env = None
for match in reversed(matches):
    try:
        candidate = json.loads(match.group(1))
    except (json.JSONDecodeError, KeyError, TypeError):
        continue
    if not isinstance(candidate, dict):
        continue
    dec = candidate.get("decision", "")
    if dec and "|" not in dec:
        env = candidate
        break
if env is None:
    sys.exit(0)

print(f"DECISION={env.get('decision', '?')}")
print(f"SUMMARY={(env.get('summary', '') or '')[:120]}")
findings = env.get("findings", []) or []
if findings:
    print(f"FINDING={((findings[0].get('title', '') or '')[:120])}")
request = (env.get("request_for_agent") or env.get("request_for_claude", "") or "")[:120]
if request:
    print(f"NEXT={request}")
PY
}

latest_commit_state() {
  python3 - "$1" <<'PY'
import sys

lines = []
try:
    with open(sys.argv[1], errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw.startswith("[commit-executor]"):
                continue
            if "Waiting for chatgpt-codex-connector review signal" in raw:
                continue
            lines.append(raw.replace("[commit-executor] ", "", 1))
except OSError:
    pass
if lines:
    print(lines[-1][:160])
PY
}

agent_status_label() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

try:
    data = json.load(open(sys.argv[1]))
except (OSError, json.JSONDecodeError):
    print("?")
    sys.exit(0)

status = data.get("status", "?")
alive = bool(sys.argv[2])
if status == "running" and not alive:
    print("completed")
elif status == "completed":
    print("completed")
elif status == "running":
    print("running")
else:
    print(status)
PY
}

render_agent_status_details() {
  python3 - "$1" <<'PY'
import json
import sys

try:
    data = json.load(open(sys.argv[1]))
except (OSError, json.JSONDecodeError):
    sys.exit(0)

status = data.get("status", "?")
completed = data.get("completed_agents", {})
running = data.get("running_agents", [])
if running:
    print("  Running: " + ", ".join(running))
for name, info in completed.items():
    mark = "\033[32m\u2713\033[0m" if info.get("passed") else "\033[31m\u2717\033[0m"
    verdict = info.get("verdict", "?")
    print(f"  {mark} {name}: {verdict}")
if not completed and not running:
    print(f"  Status: {status}")
PY
}

decision_meaning() {
  case "$1" in
    GO|COMMIT_GO) echo "Ready to continue." ;;
    REQUEST_CHANGES) echo "Needs fixes before continuing." ;;
    NEEDS_PHASE_A) echo "Needs planning changes." ;;
    NEEDS_PHASE_B) echo "Needs code changes." ;;
    COMMIT_GO_HOLD_PUSH) echo "Okay to commit, but push is intentionally paused." ;;
    NO_GO|ERROR|STALE) echo "Stopped because something is broken or unsafe." ;;
    *) echo "Waiting for the next decision." ;;
  esac
}

meta_decision_meaning() {
  case "$1" in
    COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION) echo "Ready to continue." ;;
    NEEDS_PHASE_A) echo "The plan needs more work before continuing." ;;
    NEEDS_PHASE_B) echo "The implementation needs more work before continuing." ;;
    STOP_FOR_FOUNDER) echo "A founder decision is needed before continuing." ;;
    STOP_FOR_TRIAGE_DISCUSSION) echo "This needs a human triage decision." ;;
    ERROR_VALIDATION_FAILED) echo "The package was stopped by a failed validation check." ;;
    *) echo "Waiting for the next decision." ;;
  esac
}

meta_failure_reason() {
  local file="$1"
  if grep -q 'TASKS\.md auth: FAIL' "$file" 2>/dev/null; then
    echo "TASKS.md does not list this wave as an active NOW or NEXT item yet."
    return 0
  fi
  if grep -q 'dirty_state: FAIL' "$file" 2>/dev/null; then
    echo "The worktree changed in a way the package did not expect."
    return 0
  fi
  if grep -q 'deferred_blockers: FAIL' "$file" 2>/dev/null; then
    echo "A blocking report is still open and not fully acknowledged."
    return 0
  fi
  if grep -q 'L4 contract: FAIL' "$file" 2>/dev/null; then
    echo "The staged diff breaks the L4 execution contract."
    return 0
  fi
  if grep -q 'docs_consistency: FAIL' "$file" 2>/dev/null; then
    echo "The docs and repo indexes disagree right now."
    return 0
  fi
  if grep -q 'closeout_attestation: FAIL' "$file" 2>/dev/null; then
    echo "The closeout proof does not match the claimed result yet."
    return 0
  fi
  return 1
}

meta_next_fix() {
  local file="$1"
  if grep -q 'TASKS\.md auth: FAIL' "$file" 2>/dev/null; then
    echo "Add this wave's exact task id to active NOW or NEXT in TASKS.md."
    return 0
  fi
  if grep -q 'dirty_state: FAIL' "$file" 2>/dev/null; then
    echo "Restage the real wave cleanly and rerun the package."
    return 0
  fi
  if grep -q 'deferred_blockers: FAIL' "$file" 2>/dev/null; then
    echo "Acknowledge or resolve the open blocking report before retrying."
    return 0
  fi
  return 1
}

bridge_reviewer_state_for_round() {
  local round="$1"
  local db="$REPO_ROOT/$BUS_DIR/bridge.db"
  [ -s "$db" ] || return 1
  python3 - "$db" "$round" <<'PY' 2>/dev/null
import sqlite3
import sys

db_path, round_name = sys.argv[1:3]
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    turn = conn.execute(
        """
        SELECT status, COALESCE(decision, '') AS decision,
               COALESCE(finished_at, '') AS finished_at,
               COALESCE(raw_output_path, '') AS raw_output_path
        FROM turns
        WHERE job_id = ? AND agent_role = 'reviewer'
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (round_name,),
    ).fetchone()
    job = conn.execute(
        """
        SELECT status, COALESCE(terminal_decision, '') AS terminal_decision,
               COALESCE(updated_at, '') AS updated_at
        FROM jobs
        WHERE job_id = ?
        LIMIT 1
        """,
        (round_name,),
    ).fetchone()
finally:
    conn.close()
if turn is None and job is None:
    sys.exit(1)

def emit(key: str, value: object) -> None:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ")[:500]
    print(f"{key}={text}")

if turn is not None:
    emit("TURN_STATUS", turn["status"])
    emit("TURN_DECISION", turn["decision"])
    emit("TURN_FINISHED_AT", turn["finished_at"])
    emit("TURN_RAW_OUTPUT", turn["raw_output_path"])
if job is not None:
    emit("JOB_STATUS", job["status"])
    emit("JOB_TERMINAL_DECISION", job["terminal_decision"])
    emit("JOB_UPDATED_AT", job["updated_at"])
PY
}

# Main-guard the infinite refresh driver so the test can source this script and
# call refresh_context() in isolation. Running `bash _pane_findings.sh` normally
# keeps $0 == BASH_SOURCE, so the loop still runs unchanged.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
while true; do
  refresh_context
  # Build output to temp file, only redraw if content changed
  {
  echo -e "${BOLD}Pane 2: review findings${RESET}  $(date '+%H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "  ${DIM}This pane shows the latest reviewer decision and why it passed or failed.${RESET}"
  echo -e "  ${DIM}Watching:${RESET} $BRANCH_NAME"
  echo -e "  ${DIM}Worktree:${RESET} $REPO_ROOT"
  echo ""

  # Find the 5 most recent round dirs (newest first)
  # Match phase-a-rN and phase-b-rN dirs, plus reentry dirs
  # Only show the LATEST round — newest first, pick first valid one
  ROUND_DIRS=""
  if [ -d "$RAW_DIR" ]; then
    ROUND_DIRS=$(ls -dt "$RAW_DIR"/phase-?-r[0-9]* "$RAW_DIR"/phase-?-reentry-r[0-9]* 2>/dev/null | head -10)
  fi

  found_any=false
  for dir in $ROUND_DIRS; do
    ROUND_NAME=$(basename "$dir")
    # Pick the newest non-empty reviewer file (timestamp-sorted, skip 0-byte placeholders)
    REVIEWER_FILE=""
    for rf in $(ls -t "$dir"/*reviewer*.txt 2>/dev/null); do
      [ -s "$rf" ] && REVIEWER_FILE="$rf" && break
    done

    if [ -z "$REVIEWER_FILE" ] || [ ! -s "$REVIEWER_FILE" ]; then
      # Round directory exists but reviewer file not yet written — still in progress
      found_any=true
      echo -e ""
      echo -e "  ${CYAN}$ROUND_NAME${RESET} ${DIM}(awaiting reviewer output)${RESET}"
      echo -e "  ${YELLOW}Starting...${RESET}"
      break
    fi

    found_any=true
    file_age=$(( $(date +%s) - $(stat -f%m "$REVIEWER_FILE" 2>/dev/null || stat -c%Y "$REVIEWER_FILE" 2>/dev/null || echo 0) ))
    age_str=""
    if [ "$file_age" -lt 60 ]; then
      age_str="${file_age}s ago"
    elif [ "$file_age" -lt 3600 ]; then
      age_str="$(( file_age / 60 ))m ago"
    else
      age_str="$(( file_age / 3600 ))h ago"
    fi

    # Parse the AGENT_ENVELOPE for decision and findings
    REVIEW_SOURCE="$REVIEWER_FILE"
    RENDERED_FILE="$REPO_ROOT/$BUS_DIR/rendered/$ROUND_NAME.md"
    if [ -s "$RENDERED_FILE" ]; then
      REVIEW_SOURCE="$RENDERED_FILE"
    fi

    ENVELOPE=$(parse_agent_envelope_file "$REVIEW_SOURCE" "$REVIEWER_FILE" 2>/dev/null)

    if [ -z "$ENVELOPE" ] && [ "$REVIEW_SOURCE" != "$REVIEWER_FILE" ]; then
      # Rendered file had no envelope — retry with the raw reviewer file
      REVIEW_SOURCE="$REVIEWER_FILE"
      ENVELOPE=$(parse_agent_envelope_file "$REVIEW_SOURCE" "$REVIEWER_FILE" 2>/dev/null)
    fi

    if [ -z "$ENVELOPE" ]; then
      BRIDGE_STATE=$(bridge_reviewer_state_for_round "$ROUND_NAME" || true)
      TURN_STATUS=$(echo "$BRIDGE_STATE" | grep '^TURN_STATUS=' | cut -d= -f2-)
      TURN_DECISION=$(echo "$BRIDGE_STATE" | grep '^TURN_DECISION=' | cut -d= -f2-)
      TURN_RAW_OUTPUT=$(echo "$BRIDGE_STATE" | grep '^TURN_RAW_OUTPUT=' | cut -d= -f2-)
      JOB_STATUS=$(echo "$BRIDGE_STATE" | grep '^JOB_STATUS=' | cut -d= -f2-)
      if [ "$TURN_STATUS" = "FAILED" ] || [ "$TURN_STATUS" = "ERROR" ] || [ "$TURN_DECISION" = "ERROR" ]; then
        echo -e ""
        echo -e "  ${CYAN}$ROUND_NAME${RESET} ${DIM}($age_str)${RESET}"
        echo -e "  Decision: ${RED}${BOLD}ERROR${RESET}"
        echo -e "  ${DIM}Meaning: $(decision_meaning ERROR)${RESET}"
        echo -e "  Why it stopped: bridge reviewer turn is ${TURN_STATUS:-unknown}${TURN_DECISION:+ / $TURN_DECISION}."
        if [ -n "$JOB_STATUS" ]; then
          echo -e "  ${DIM}Bridge job status: $JOB_STATUS${RESET}"
        fi
        if [ -n "$TURN_RAW_OUTPUT" ]; then
          echo -e "  ${DIM}Raw output: $TURN_RAW_OUTPUT${RESET}"
        fi
        found_any=true
        break
      fi
      # No envelope and no terminal reviewer state yet — review still in progress.
      SIZE=$(wc -c < "$REVIEW_SOURCE" | xargs)
      echo -e ""
      echo -e "  ${CYAN}$ROUND_NAME${RESET} ${DIM}($age_str, ${SIZE}B)${RESET}"
      echo -e "  ${YELLOW}In progress...${RESET}"
      found_any=true
      break
    fi

    # Parse envelope output
    DECISION=$(echo "$ENVELOPE" | grep "^DECISION=" | cut -d= -f2-)
    SUMMARY=$(echo "$ENVELOPE" | grep "^SUMMARY=" | cut -d= -f2-)
    BLK_COUNT=$(echo "$ENVELOPE" | grep "^BLOCKING=" | cut -d= -f2-)
    NB_COUNT=$(echo "$ENVELOPE" | grep "^NONBLOCKING=" | cut -d= -f2-)

    # Decision color
    case "$DECISION" in
      GO|COMMIT_GO) dec_color="$GREEN" ;;
      REQUEST_CHANGES|NEEDS_PHASE_B|NEEDS_PHASE_A|COMMIT_GO_HOLD_PUSH) dec_color="$YELLOW" ;;
      NO_GO|ERROR|STALE) dec_color="$RED" ;;
      *) dec_color="$CYAN" ;;
    esac

    # Desktop notification — only once per round+decision (persisted across reloads)
    NOTIFY_KEY="${ROUND_NAME}:${DECISION}"
    if [ "$NOTIFY_KEY" != "$LAST_NOTIFIED_ROUND" ] && [ -n "$DECISION" ]; then
      LAST_NOTIFIED_ROUND="$NOTIFY_KEY"
      case "$DECISION" in
        GO|COMMIT_GO)
          notify "RCX Pipeline" "GO — ready to commit (${NB_COUNT} advisory)" "$NOTIFY_KEY" ;;
        NO_GO)
          notify "RCX Pipeline" "NO_GO — ${BLK_COUNT} blocker(s) found" "$NOTIFY_KEY" ;;
        REQUEST_CHANGES)
          notify "RCX Pipeline" "REQUEST_CHANGES — ${BLK_COUNT} blocking, ${NB_COUNT} advisory" "$NOTIFY_KEY" ;;
        *)
          notify "RCX Pipeline" "Review: $DECISION" "$NOTIFY_KEY" ;;
      esac
    fi

    echo -e ""
    echo -e "  ${CYAN}$ROUND_NAME${RESET} ${DIM}($age_str)${RESET}"
    echo -e "  Decision: ${dec_color}${BOLD}$DECISION${RESET}  ${RED}${BLK_COUNT}B${RESET} ${YELLOW}${NB_COUNT}NB${RESET}"
    echo -e "  ${DIM}Meaning: $(decision_meaning "$DECISION")${RESET}"

    if [ -n "$SUMMARY" ]; then
      echo -e "  ${DIM}$SUMMARY${RESET}"
    fi

    render_findings_lines "$ENVELOPE"

    # Clean-GO review history — ONLY when the latest round passed with zero
    # findings. Re-surface the same-phase review arc plus the last findings round
    # so the reviewer's work stays visible after the wave converges. Any other
    # latest round (non-GO or has-findings) renders exactly as before this block.
    if { [ "$DECISION" = "GO" ] || [ "$DECISION" = "COMMIT_GO" ]; } \
       && [ "${BLK_COUNT:-}" = "0" ] && [ "${NB_COUNT:-}" = "0" ]; then
      render_clean_go_history "$ROUND_NAME"
    fi

    # Only show the latest round — break after first valid one
    break
  done

  if [ "$found_any" = false ]; then
    echo -e "  ${DIM}No active Phase A/Phase B bridge rounds${RESET}"

    META_DIR="$REPO_ROOT/$BUS_DIR/meta/raw"
    META_FILE=$(ls -t "$META_DIR"/meta-*.txt 2>/dev/null | head -1) || true
    if [ -n "$META_FILE" ] && [ -s "$META_FILE" ]; then
      meta_age=$(( $(date +%s) - $(stat -f%m "$META_FILE" 2>/dev/null || stat -c%Y "$META_FILE" 2>/dev/null || echo 0) ))
      if [ "$meta_age" -lt 60 ]; then
        meta_age_str="${meta_age}s ago"
      elif [ "$meta_age" -lt 3600 ]; then
        meta_age_str="$(( meta_age / 60 ))m ago"
      else
        meta_age_str="$(( meta_age / 3600 ))h ago"
      fi

      META_ENVELOPE=$(parse_meta_envelope_file "$META_FILE" 2>/dev/null)

      if [ -n "$META_ENVELOPE" ]; then
        META_DECISION=$(echo "$META_ENVELOPE" | grep "^DECISION=" | cut -d= -f2-)
        META_SUMMARY=$(echo "$META_ENVELOPE" | grep "^SUMMARY=" | cut -d= -f2-)
        META_FINDING=$(echo "$META_ENVELOPE" | grep "^FINDING=" | cut -d= -f2-)
        META_NEXT=$(echo "$META_ENVELOPE" | grep "^NEXT=" | cut -d= -f2-)
        case "$META_DECISION" in
          COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION) meta_color="$GREEN" ;;
          NEEDS_PHASE_A|NEEDS_PHASE_B|STOP_FOR_FOUNDER|STOP_FOR_TRIAGE_DISCUSSION) meta_color="$YELLOW" ;;
          ERROR_VALIDATION_FAILED) meta_color="$RED" ;;
          *) meta_color="$CYAN" ;;
        esac
        META_REASON=""
        META_HINT=""
        if [ "$META_DECISION" = "ERROR_VALIDATION_FAILED" ]; then
          META_REASON="$(meta_failure_reason "$META_FILE" || true)"
          META_HINT="$(meta_next_fix "$META_FILE" || true)"
        fi
        echo ""
        echo -e "  ${CYAN}Latest meta review${RESET} ${DIM}($meta_age_str)${RESET}"
        echo -e "  Decision: ${meta_color}${BOLD}${META_DECISION}${RESET}"
        echo -e "  ${DIM}Meaning: $(meta_decision_meaning "$META_DECISION")${RESET}"
        if [ -n "$META_REASON" ]; then
          echo -e "  Why it stopped: $META_REASON"
        elif [ -n "$META_FINDING" ]; then
          echo -e "  Why it stopped: $META_FINDING"
        elif [ -n "$META_SUMMARY" ]; then
          echo -e "  ${DIM}$META_SUMMARY${RESET}"
        fi
        if [ -n "$META_HINT" ]; then
          echo -e "  ${DIM}Next fix: $META_HINT${RESET}"
        elif [ -n "$META_NEXT" ]; then
          echo -e "  ${DIM}Next fix: $META_NEXT${RESET}"
        fi
      else
        SIZE=$(wc -c < "$META_FILE" | xargs)
        echo ""
        echo -e "  ${CYAN}Meta review${RESET} ${DIM}($meta_age_str, ${SIZE}B)${RESET}"
        echo -e "  ${YELLOW}In progress...${RESET}"
      fi
    fi

    COMMIT_LOG="$REPO_ROOT/.scratch/commit_executor_live.log"
    if [ -f "$COMMIT_LOG" ]; then
      COMMIT_STATE=$(latest_commit_state "$COMMIT_LOG" 2>/dev/null)
      if [ -n "$COMMIT_STATE" ]; then
        echo ""
        echo -e "  ${CYAN}Commit path${RESET}"
        echo -e "  ${DIM}${COMMIT_STATE}${RESET}"
      fi
    fi
  fi

  echo ""
  } > "$TMPOUT" 2>/dev/null

  # SDK agent results — outside redirect block (python braces conflict)
  AGENT_STATUS=$(ls -t "$REPO_ROOT/.scratch/phase_b_agent_review_"*.status.json 2>/dev/null | head -1) || true
  if [ -n "$AGENT_STATUS" ]; then
    agent_age=$(( $(date +%s) - $(stat -f%m "$AGENT_STATUS" 2>/dev/null || stat -c%Y "$AGENT_STATUS" 2>/dev/null || echo 0) ))
    if [ "$agent_age" -lt 1800 ]; then
      echo "" >> "$TMPOUT"
      # Cross-check status file with live processes — if no run_review.py
      # is alive, the status file is stale even if it says "running"
      agent_process_alive=$(pgrep -f "run_review.py" 2>/dev/null | head -1)
      agent_status_label=$(agent_status_label "$AGENT_STATUS" "$agent_process_alive" 2>/dev/null) || agent_status_label="?"
      echo -e "${BOLD}SDK AGENTS${RESET}  ${DIM}($agent_status_label, $(( agent_age / 60 ))m ago)${RESET}" >> "$TMPOUT"
      echo "─────────────────────────────────────" >> "$TMPOUT"
      render_agent_status_details "$AGENT_STATUS" >> "$TMPOUT" 2>/dev/null
    fi
  fi

  # Only full redraw if content changed (skip title+separator for hash)
  NEW_HASH=$(tail -n +3 "$TMPOUT" 2>/dev/null | md5 -q 2>/dev/null || tail -n +3 "$TMPOUT" | md5sum 2>/dev/null | cut -d' ' -f1)
  if [ "$NEW_HASH" != "$LAST_HASH" ]; then
    printf '\033[H\033[2J\033[3J'
    cat "$TMPOUT"
    LAST_HASH="$NEW_HASH"
  else
    # Data unchanged — just update timestamp so user knows it's alive
    tput cup 0 0 2>/dev/null
    echo -e "${BOLD}Pane 2: review findings${RESET}  $(date '+%H:%M:%S')"
  fi

  if [ "$ONESHOT" = "1" ]; then
    rm -f "$TMPOUT"
    exit 0
  fi

  # Auto-reload: re-exec if script changed on disk
  _SELF="${BASH_SOURCE[0]}"
  _NEW_MTIME=$(stat -f%m "$_SELF" 2>/dev/null || stat -c%Y "$_SELF" 2>/dev/null || echo 0)
  if [ "${_SELF_MTIME:-0}" != "0" ] && [ "$_NEW_MTIME" != "$_SELF_MTIME" ]; then
    rm -f "$TMPOUT"
    sleep 1
    exec bash "$_SELF"
  fi
  _SELF_MTIME="$_NEW_MTIME"

  sleep 5
done
fi
