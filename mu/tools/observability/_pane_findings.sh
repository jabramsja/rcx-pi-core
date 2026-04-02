#!/usr/bin/env bash
# _pane_findings.sh — Bridge review findings pane for tmux
# Shows blocking/non-blocking findings from latest bridge rounds
# Auto-reloads when script changes on disk.
set +e
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
RAW_DIR="$REPO_ROOT/.agent_bus/raw"
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
SELF_MTIME=$(stat -f%m "$SELF" 2>/dev/null || stat -c%Y "$SELF" 2>/dev/null || echo 0)

BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"
LAST_HASH=""
TMPOUT="/tmp/rcx_pane_findings_$$.txt"
NOTIFY_MARKER="/tmp/rcx_last_notified_round.txt"
LAST_NOTIFIED_ROUND=$(cat "$NOTIFY_MARKER" 2>/dev/null || echo "")

notify() {
  local title="$1" msg="$2" round="$3"
  osascript -e "display notification \"$msg\" with title \"$title\" sound name \"Glass\"" 2>/dev/null &
  echo "$round" > "$NOTIFY_MARKER"
}

while true; do
  # Build output to temp file, only redraw if content changed
  {
  echo -e "${BOLD}REVIEW FINDINGS${RESET}  $(date '+%H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if [ ! -d "$RAW_DIR" ]; then
    echo -e "  ${DIM}No bridge rounds yet${RESET}"
    sleep 5
    continue
  fi

  # Find the 5 most recent round dirs (newest first)
  # Match phase-a-rN and phase-b-rN dirs, plus reentry dirs
  # Only show the LATEST round — newest first, pick first valid one
  ROUND_DIRS=$(ls -dt "$RAW_DIR"/phase-?-r[0-9]* "$RAW_DIR"/phase-?-reentry-r[0-9]* 2>/dev/null | head -10)

  if [ -z "$ROUND_DIRS" ]; then
    echo -e "  ${DIM}No bridge rounds yet${RESET}"
    sleep 5
    continue
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
      continue
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
    echo -e "  ${DIM}No reviewer output yet${RESET}"
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

  sleep 5
done
