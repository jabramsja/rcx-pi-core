#!/usr/bin/env bash
# _pane_findings.sh — Bridge review findings pane for tmux
# Shows blocking/non-blocking findings from latest bridge rounds
# Auto-reloads when script changes on disk.
set +e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
resolve_repo_root() {
  local helper="$SCRIPT_DIR/pipeline_status.sh"
  local root=""
  if [ -f "$helper" ]; then
    root=$(bash "$helper" --print-root 2>/dev/null || true)
  fi
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}
resolve_branch_name() {
  local helper="$SCRIPT_DIR/pipeline_status.sh"
  local branch=""
  if [ -f "$helper" ]; then
    branch=$(bash "$helper" --print-branch-for-root "$REPO_ROOT" 2>/dev/null || true)
  fi
  if [ -n "$branch" ]; then
    printf '%s\n' "$branch"
    return 0
  fi
  git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}
REPO_ROOT="$(resolve_repo_root)"
RAW_DIR="$REPO_ROOT/.agent_bus/raw"
BRANCH_NAME="$(resolve_branch_name)"
SELF="$SCRIPT_DIR/$(basename "$0")"
SELF_MTIME=$(stat -f%m "$SELF" 2>/dev/null || stat -c%Y "$SELF" 2>/dev/null || echo 0)

BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"
LAST_HASH=""
TMPOUT="/tmp/rcx_pane_findings_$$.txt"
NOTIFY_MARKER="/tmp/rcx_last_notified_round.txt"
LAST_NOTIFIED_ROUND=$(cat "$NOTIFY_MARKER" 2>/dev/null || echo "")
ONESHOT="${RCX_PANE_ONESHOT:-0}"

notify() {
  local title="$1" msg="$2" round="$3"
  osascript -e "display notification \"$msg\" with title \"$title\" sound name \"Glass\"" 2>/dev/null &
  echo "$round" > "$NOTIFY_MARKER"
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

while true; do
  # Build output to temp file, only redraw if content changed
  {
  echo -e "${BOLD}REVIEW FINDINGS${RESET}  $(date '+%H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
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
    RENDERED_FILE="$REPO_ROOT/.agent_bus/rendered/$ROUND_NAME.md"
    if [ -s "$RENDERED_FILE" ]; then
      REVIEW_SOURCE="$RENDERED_FILE"
    fi

    ENVELOPE=$(python3 -c "
import json, re, sys
content = open('$REVIEW_SOURCE', errors='replace').read()
matches = list(re.finditer(r'BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE', content, re.DOTALL))
env = None
for m in reversed(matches):
    try:
        candidate = json.loads(m.group(1))
        dec = candidate.get('decision', '')
        if '|' not in dec and dec:  # Skip 'GO|NO_GO|...' schema examples
            env = candidate
            break
    except (json.JSONDecodeError, KeyError):
        continue
if env is None:
    sections = list(re.finditer(r'(?ms)^### .*? — reviewer\n(.*?)(?=^### |\Z)', content))
    decision_re = re.compile(r'(?m)^\s*-\s*Decision:\s*(GO|REQUEST_CHANGES|NO_GO|QUESTION|STALE|ERROR|SYNTHETIC)\b')
    summary_re = re.compile(r'(?m)^\s*-\s*Summary:\s*(.*)')
    finding_re = re.compile(r'(?m)^\s*\d+\.\s+\*\*(DEFECT|POLICY_BOUND|DOC_ACCURACY)\*\* \(([^)]+)\):\s*(.*)$')
    for section in reversed(sections):
        block = section.group(1)
        decision_match = decision_re.search(block)
        if not decision_match:
            continue
        dec = decision_match.group(1)
        if dec == 'SYNTHETIC':
            continue
        summary_match = summary_re.search(block)
        disposition = 'non_blocking' if dec == 'GO' else 'blocking'
        env = {
            'decision': dec,
            'summary': summary_match.group(1).strip() if summary_match else '',
            'findings': [
                {
                    'class': cls,
                    'severity': sev.strip().lower(),
                    'title': title.strip(),
                    'disposition': disposition,
                }
                for cls, sev, title in finding_re.findall(block)
            ],
        }
        break
if env is None:
    sys.exit(0)
dec = env.get('decision', '?')
summary = env.get('summary', '')[:120]
findings = env.get('findings', [])
blk = [f for f in findings if f.get('disposition') == 'blocking']
nb = [f for f in findings if f.get('disposition') != 'blocking']
print(f'DECISION={dec}')
print(f'SUMMARY={summary}')
print(f'BLOCKING={len(blk)}')
print(f'NONBLOCKING={len(nb)}')
for f in blk:
    sev = f.get('severity', '?')
    title = (f.get('title') or f.get('description') or '?')[:100]
    print(f'BLK|{sev}|{title}')
for f in nb:
    sev = f.get('severity', '?')
    title = (f.get('title') or f.get('description') or '?')[:100]
    print(f'NB|{sev}|{title}')
" 2>/dev/null)

    if [ -z "$ENVELOPE" ]; then
      # No envelope yet — review still in progress. Show this and stop.
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

    # Show blocking findings
    echo "$ENVELOPE" | grep "^BLK|" | while IFS='|' read -r _ sev title; do
      case "$sev" in
        critical) sev_color="$RED" ;;
        high) sev_color="$RED" ;;
        medium) sev_color="$YELLOW" ;;
        *) sev_color="$DIM" ;;
      esac
      echo -e "    ${RED}B${RESET} ${sev_color}[$sev]${RESET} $title"
    done

    # Show non-blocking findings
    echo "$ENVELOPE" | grep "^NB|" | while IFS='|' read -r _ sev title; do
      case "$sev" in
        critical|high) sev_color="$YELLOW" ;;
        medium) sev_color="$YELLOW" ;;
        *) sev_color="$DIM" ;;
      esac
      echo -e "    ${YELLOW}N${RESET} ${sev_color}[$sev]${RESET} $title"
    done

    # Only show the latest round — break after first valid one
    break
  done

  if [ "$found_any" = false ]; then
    echo -e "  ${DIM}No active Phase A/Phase B bridge rounds${RESET}"

    META_DIR="$REPO_ROOT/.agent_bus/meta/raw"
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

      META_ENVELOPE=$(python3 -c "
import json, re, sys
content = open('$META_FILE', errors='replace').read()
matches = list(re.finditer(r'BEGIN_META_ENVELOPE\s*\n(.*?)\nEND_META_ENVELOPE', content, re.DOTALL))
env = None
for m in reversed(matches):
    try:
        candidate = json.loads(m.group(1))
        dec = candidate.get('decision', '')
        if '|' not in dec and dec:
            env = candidate
            break
    except (json.JSONDecodeError, KeyError):
        continue
if env is None:
    sys.exit(0)
print(f'DECISION={env.get(\"decision\", \"?\")}')
print(f'SUMMARY={(env.get(\"summary\", \"\") or \"\")[:120]}')
" 2>/dev/null)

      if [ -n "$META_ENVELOPE" ]; then
        META_DECISION=$(echo "$META_ENVELOPE" | grep "^DECISION=" | cut -d= -f2-)
        META_SUMMARY=$(echo "$META_ENVELOPE" | grep "^SUMMARY=" | cut -d= -f2-)
        case "$META_DECISION" in
          COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION) meta_color="$GREEN" ;;
          NEEDS_PHASE_A|NEEDS_PHASE_B|STOP_FOR_FOUNDER|STOP_FOR_TRIAGE_DISCUSSION) meta_color="$YELLOW" ;;
          ERROR_VALIDATION_FAILED) meta_color="$RED" ;;
          *) meta_color="$CYAN" ;;
        esac
        echo ""
        echo -e "  ${CYAN}Latest meta review${RESET} ${DIM}($meta_age_str)${RESET}"
        echo -e "  Decision: ${meta_color}${BOLD}${META_DECISION}${RESET}"
        [ -n "$META_SUMMARY" ] && echo -e "  ${DIM}$META_SUMMARY${RESET}"
      else
        SIZE=$(wc -c < "$META_FILE" | xargs)
        echo ""
        echo -e "  ${CYAN}Meta review${RESET} ${DIM}($meta_age_str, ${SIZE}B)${RESET}"
        echo -e "  ${YELLOW}In progress...${RESET}"
      fi
    fi

    COMMIT_LOG="$REPO_ROOT/.scratch/commit_executor_live.log"
    if [ -f "$COMMIT_LOG" ]; then
      COMMIT_STATE=$(python3 -c "
import sys
path = '$COMMIT_LOG'
lines = []
with open(path, errors='replace') as fh:
    for raw in fh:
        raw = raw.strip()
        if not raw.startswith('[commit-executor]'):
            continue
        if 'Waiting for chatgpt-codex-connector review signal' in raw:
            continue
        lines.append(raw.replace('[commit-executor] ', '', 1))
if lines:
    print(lines[-1][:160])
" 2>/dev/null)
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
      echo -e "${BOLD}SDK AGENTS${RESET}  ${DIM}($(( agent_age / 60 ))m ago)${RESET}" >> "$TMPOUT"
      echo "─────────────────────────────────────" >> "$TMPOUT"
      python3 -c "
import json
d = json.load(open('$AGENT_STATUS'))
status = d.get('status', '?')
completed = d.get('completed_agents', {})
running = d.get('running_agents', [])
if running:
    print('  Running: ' + ', '.join(running))
for name, info in completed.items():
    mark = '\033[32m\u2713\033[0m' if info.get('passed') else '\033[31m\u2717\033[0m'
    verdict = info.get('verdict', '?')
    print(f'  {mark} {name}: {verdict}')
if not completed and not running:
    print(f'  Status: {status}')
" >> "$TMPOUT" 2>/dev/null
    fi
  fi

  # Only full redraw if content changed (skip title+separator for hash)
  NEW_HASH=$(tail -n +3 "$TMPOUT" 2>/dev/null | md5 -q 2>/dev/null || tail -n +3 "$TMPOUT" | md5sum 2>/dev/null | cut -d' ' -f1)
  if [ "$NEW_HASH" != "$LAST_HASH" ]; then
    clear
    cat "$TMPOUT"
    LAST_HASH="$NEW_HASH"
  else
    # Data unchanged — just update timestamp so user knows it's alive
    tput cup 0 0 2>/dev/null
    echo -e "${BOLD}REVIEW FINDINGS${RESET}  $(date '+%H:%M:%S')"
  fi

  # Auto-reload
  NEW_MTIME=$(stat -f%m "$SELF" 2>/dev/null || stat -c%Y "$SELF" 2>/dev/null || echo 0)
  if [ "$NEW_MTIME" != "$SELF_MTIME" ]; then
    rm -f "$TMPOUT"
    sleep 1
    exec bash "$SELF"
  fi

  if [ "$ONESHOT" = "1" ]; then
    rm -f "$TMPOUT"
    exit 0
  fi

  sleep 5
done
