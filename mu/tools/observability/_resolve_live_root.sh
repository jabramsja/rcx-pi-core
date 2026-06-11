#!/usr/bin/env bash
set -euo pipefail

# Opt-in pair mode (WI-1): when --emit-pair is passed, emit the freshest active
# (worktree_root, bus_dir) PAIR across .agent_bus plus every .agent_bus-<id> bus
# present in any linked worktree (see emit_freshest_pair). With no flag the
# behavior is UNCHANGED: print only the resolved root for the fixed bus.
EMIT_PAIR=0
for _arg in "$@"; do
  case "$_arg" in
    --emit-pair) EMIT_PAIR=1 ;;
  esac
done

BUS_DIR="${RCX_AGENT_BUS_DIR:-${BUS_DIR:-.agent_bus}}"
if [[ "$BUS_DIR" == /* || "$BUS_DIR" == *"/"* || "$BUS_DIR" == *"\\"* || "$BUS_DIR" == *".."* ]]; then
  echo "ERROR: invalid RCX_AGENT_BUS_DIR: $BUS_DIR" >&2
  exit 2
fi
if [[ "$BUS_DIR" != ".agent_bus" && ! "$BUS_DIR" =~ ^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  echo "ERROR: RCX_AGENT_BUS_DIR must be .agent_bus or .agent_bus-<id>" >&2
  exit 2
fi

file_mtime_seconds() {
  local path="$1"
  stat -f%m "$path" 2>/dev/null || stat -c%Y "$path" 2>/dev/null || echo 0
}

list_linked_worktrees() {
  local current_path="" is_bare=false
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      worktree\ *)
        current_path="${line#worktree }"
        is_bare=false
        ;;
      bare)
        is_bare=true
        ;;
      "")
        if [ "$is_bare" = false ] && [ -n "$current_path" ]; then
          printf '%s\n' "$current_path"
        fi
        current_path=""
        is_bare=false
        ;;
    esac
  done < <(git worktree list --porcelain 2>/dev/null || true)

  if [ "$is_bare" = false ] && [ -n "$current_path" ]; then
    printf '%s\n' "$current_path"
  fi
}

normalize_path() {
  local path="$1"
  (
    cd "$path" 2>/dev/null && pwd -P
  ) || printf '%s\n' "$path"
}

worktree_score() {
  # Score a (root, bus) pair by the freshest pipeline-activity file mtime.
  # bus defaults to the fixed $BUS_DIR so existing no-flag callers are unchanged.
  #
  # scope (3rd arg, default "full"): which subset of activity files to count.
  #   full -> legacy behavior: also count the bus-AGNOSTIC .scratch executor
  #           live logs and agent-review status files. Used by the no-flag root
  #           resolver, which compares ONE bus across roots ("which root is
  #           freshest"), so root-level signals are the right liveness proxy.
  #   bus  -> count ONLY bus-relative ($root/$bus/...) activity. Used by pair
  #           mode, which compares DIFFERENT buses. The .scratch signals live at
  #           the worktree ROOT, not under any bus, so in full scope they score
  #           every candidate bus identically -- propping up .agent_bus and tying
  #           a genuinely-active lane against the default so the lane is never
  #           followed (bridge round-1 DEFECT). "bus" scope is a strict SUBSET of
  #           the same inputs -- no new liveness source, no new scoring input, no
  #           new state -- so each bus is scored by its OWN activity.
  local root="$1" bus="${2:-$BUS_DIR}" scope="${3:-full}" best=0 candidate="" mtime=0
  if [ "$scope" = "full" ]; then
    for candidate in \
      "$root/.scratch/phase_a_executor_live.log" \
      "$root/.scratch/phase_b_executor_live.log" \
      "$root/.scratch/commit_executor_live.log"
    do
      [ -f "$candidate" ] || continue
      mtime=$(file_mtime_seconds "$candidate")
      [ "$mtime" -gt "$best" ] && best="$mtime"
    done
  fi
  for candidate in \
    "$root/$bus/recovery/recovery_status.json" \
    "$root/$bus/executors/phase_b_state.json"
  do
    [ -f "$candidate" ] || continue
    mtime=$(file_mtime_seconds "$candidate")
    [ "$mtime" -gt "$best" ] && best="$mtime"
  done

  if [ "$scope" = "full" ]; then
    candidate=$(ls -t \
      "$root"/"$bus"/raw/phase-?-r[0-9]*/*reviewer*.txt \
      "$root"/"$bus"/raw/phase-?-reentry-r[0-9]*/*reviewer*.txt \
      "$root"/.scratch/phase_a_agent_review_*.status.json \
      "$root"/.scratch/phase_b_agent_review_*.status.json \
      2>/dev/null | head -1) || true
  else
    candidate=$(ls -t \
      "$root"/"$bus"/raw/phase-?-r[0-9]*/*reviewer*.txt \
      "$root"/"$bus"/raw/phase-?-reentry-r[0-9]*/*reviewer*.txt \
      2>/dev/null | head -1) || true
  fi
  if [ -n "$candidate" ]; then
    mtime=$(file_mtime_seconds "$candidate")
    [ "$mtime" -gt "$best" ] && best="$mtime"
  fi

  printf '%s\n' "$best"
}

emit_freshest_pair() {
  # Opt-in pair mode (WI-1/WI-3). Print two lines: the freshest active worktree
  # root, then the bus_dir to follow. Candidate buses = .agent_bus plus every
  # .agent_bus-<id> dir present in any candidate root (current root + linked
  # worktrees), each scored with worktree_score in bus-specific scope (only
  # $root/$bus activity, so bus-agnostic .scratch signals can't tie an active
  # lane against .agent_bus). Selection rule (fixed; no
  # tunable margin, no state): emit a lane bus ONLY when it is the UNIQUE strict
  # maximum across ALL candidate buses (its score strictly greater than every
  # other bus, .agent_bus included, with no bus tying it). In every other case
  # (.agent_bus greatest-or-equal, a tie at the top, or no lane bus) fall back to
  # .agent_bus with the freshest root by FULL-scope scoring -- IDENTICAL to the
  # no-flag resolver, so the default monitor (which always autofollows and takes
  # this root verbatim) keeps its prior root-follow even when a worktree is fresh
  # only by root-level .scratch liveness.
  local r="" norm="" roots="" score=""

  roots="$CURRENT_ROOT"
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    norm="$(normalize_path "$r")"
    if ! printf '%s\n' "$roots" | grep -Fxq -- "$norm"; then
      roots="$roots
$norm"
    fi
  done < <(list_linked_worktrees)

  # The default fallback needs TWO independent quantities, because the lane-vs-
  # default DECISION and the emitted fallback ROOT have different correctness
  # criteria:
  #
  #   * default_bus_score -- the max BUS-SPECIFIC .agent_bus score across roots.
  #     Used ONLY for the lane-vs-default comparison, so a bus-agnostic .scratch
  #     signal in a lane worktree can't prop up .agent_bus and tie a genuinely
  #     active lane against it (bridge round-1 DEFECT; worktree_score scope="bus").
  #   * default_root -- the freshest root by FULL-scope .agent_bus scoring,
  #     IDENTICAL to the no-flag resolver below (which counts the bus-agnostic
  #     .scratch executor live-logs / agent-review status files). When pair mode
  #     falls back to .agent_bus it MUST emit the SAME root the no-flag path would:
  #     the default monitor always sets RCX_OBS_AUTOFOLLOW_BUS=1 and its panes take
  #     this root verbatim, so scoring the fallback root bus-specifically would
  #     silently drop the prior root-follow whenever the freshest worktree is
  #     proven only by root-level .scratch liveness (bridge round-2 DEFECT). We
  #     score .agent_bus explicitly (not $BUS_DIR) so the fallback root stays
  #     consistent with the always-.agent_bus fallback bus even if a caller's
  #     in-loop BUS_DIR has drifted to a lane on a prior refresh.
  local default_root="$CURRENT_ROOT" default_bus_score="" default_full_score=""
  default_bus_score="$(worktree_score "$CURRENT_ROOT" ".agent_bus" bus)"
  default_full_score="$(worktree_score "$CURRENT_ROOT" ".agent_bus" full)"
  local bus_score="" full_score=""
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    bus_score="$(worktree_score "$r" ".agent_bus" bus)"
    full_score="$(worktree_score "$r" ".agent_bus" full)"
    if [ "$bus_score" -gt "$default_bus_score" ] 2>/dev/null; then
      default_bus_score="$bus_score"
    fi
    if [ "$full_score" -gt "$default_full_score" ] 2>/dev/null; then
      default_full_score="$full_score"
      default_root="$r"
    fi
  done < <(printf '%s\n' "$roots")

  # Candidate lane buses present under any candidate root (deduped).
  local lane_buses="" bus="" base="" d=""
  lane_buses="$(
    while IFS= read -r r; do
      [ -n "$r" ] || continue
      for d in "$r"/.agent_bus-*; do
        [ -d "$d" ] || continue
        base="$(basename "$d")"
        if printf '%s' "$base" | grep -Eq '^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$'; then
          printf '%s\n' "$base"
        fi
      done
    done < <(printf '%s\n' "$roots") | sort -u
  )"

  # Best lane bus by score (max over roots), tracking ties at the top.
  local best_lane_bus="" best_lane_root="" best_lane_score=-1 best_lane_count=0
  local lane_root="" lane_score=""
  while IFS= read -r bus; do
    [ -n "$bus" ] || continue
    lane_root=""
    lane_score=-1
    while IFS= read -r r; do
      [ -n "$r" ] || continue
      score="$(worktree_score "$r" "$bus" bus)"
      if [ "$score" -gt "$lane_score" ] 2>/dev/null; then
        lane_score="$score"
        lane_root="$r"
      fi
    done < <(printf '%s\n' "$roots")
    if [ "$lane_score" -gt "$best_lane_score" ] 2>/dev/null; then
      best_lane_score="$lane_score"
      best_lane_bus="$bus"
      best_lane_root="$lane_root"
      best_lane_count=1
    elif [ "$lane_score" -eq "$best_lane_score" ] 2>/dev/null; then
      best_lane_count=$((best_lane_count + 1))
    fi
  done < <(printf '%s\n' "$lane_buses")

  # Unique strict maximum held by exactly one lane bus => follow that lane.
  if [ -n "$best_lane_bus" ] \
     && [ "$best_lane_count" -eq 1 ] \
     && [ "$best_lane_score" -gt "$default_bus_score" ] 2>/dev/null; then
    printf '%s\n' "$best_lane_root"
    printf '%s\n' "$best_lane_bus"
    return 0
  fi

  printf '%s\n' "$default_root"
  printf '%s\n' ".agent_bus"
}

CURRENT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
CURRENT_ROOT="$(normalize_path "$CURRENT_ROOT")"

if [ "$EMIT_PAIR" = "1" ]; then
  emit_freshest_pair
  exit 0
fi

BEST_ROOT="$CURRENT_ROOT"
BEST_SCORE="$(worktree_score "$CURRENT_ROOT")"

while IFS= read -r path; do
  [ -n "$path" ] || continue
  path="$(normalize_path "$path")"
  score="$(worktree_score "$path")"
  if [ "$score" -gt "$BEST_SCORE" ] 2>/dev/null; then
    BEST_ROOT="$path"
    BEST_SCORE="$score"
  fi
done < <(list_linked_worktrees)

printf '%s\n' "$BEST_ROOT"
