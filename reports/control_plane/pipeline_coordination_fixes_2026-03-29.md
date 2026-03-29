# Pipeline Coordination Fixes

**Phase-A-Lock: LOCKED**
**Task:** [NEXT-CODEX-POST-REDTEAM]
**Wave class:** L4_ENABLER
**Target gate:** G8
**BOOTSTRAP_PHASE_B_EXCEPTION:** Yes — all changes are to executor/hook surfaces

---

## Scope (4 fixes)

### Fix 1: Phase B executor — branch checkout before implementer

**Problem:** Phase A creates a feature branch via checkpoint commit, but Phase B executor stays on `dev` because the PreToolUse hook blocks `git stash`. Phase B needs to detect and checkout the Phase A branch before invoking the implementer.

**File:** `mu/tools/executors/phase_b_executor.py` (~line 1914)

**Change:** After config load and before implementer invocation, add branch detection:
- Derive expected feature branch from `wave_id` (pattern: `jabramsja/<wave_id>`)
- Check if branch exists (`git rev-parse --verify`)
- If current branch is `dev` and feature branch exists, checkout to it
- If feature branch doesn't exist, create it from current HEAD

### Fix 2: Phase B executor — pass wave_class from routing record

**Problem:** `wave_class` is hardcoded as `"L4_ENABLER"` at lines 1612 and 3038. The implementer generates tracker notes with the wrong class.

**Files:**
- `mu/tools/executors/phase_b_executor.py` (lines 1612, 3038)

**Change:**
- Extract `wave_class` from routing record (with fallback to `"L4_ENABLER"`)
- Extract `target_gate_id` from routing record (with fallback to `"G8"`)
- Pass both through to `_build_phase_b_tracker_note()` and `prepare_commit_handoff()`
- Pass both through to `_build_phase_b_tracker_note()` and `prepare_commit_handoff()`

### Fix 3: pre-push-fast — exact wave_id matching

**Problem:** Line 65 uses substring grep: `grep -q ", ${WAVE_ID_SUFFIX}):"`. This can match `deferred-cleanup` inside `wave10-deferred-cleanup`. The fallback loop at lines 70-77 compounds the problem by trying every note.

**File:** `mu/tools/hooks/pre-push-fast` (lines 62-78)

**Change:**
- Replace substring grep with exact-field grep using word boundary or full-field regex
- Pattern: match `, <EXACT_WAVE_ID>):` where wave_id is the complete field between comma and closing paren
- Use `grep -qE "Tracker sync note \([^,]+, ${WAVE_ID_SUFFIX}\):"` for exact match

### Fix 4: PreToolUse hook — allow stash and checkout -b from dev

**Problem:** `block-protected-branch.sh` blocks `stash` and all git subcommands indiscriminately on dev. This prevents Phase B from stashing changes and switching to a feature branch.

**File:** `.claude/hooks/block-protected-branch.sh` (lines 36-39)

**Change:**
- Remove `stash` from the blocked subcommand list (stash doesn't modify the branch, it saves/restores work)
- Keep blocking: `commit`, `push`, `merge`, `rebase`, `cherry-pick`, `reset`, `revert`, `am`
- `checkout` is already not in the blocked list (only subcommands after `git` are checked)

---

## Files changed

1. `mu/tools/executors/phase_b_executor.py`
2. `mu/tools/hooks/pre-push-fast`
3. `.claude/hooks/block-protected-branch.sh`

## Validation commands (Phase B-local)

```bash
# Fix 1 + 2: executor changes — unit test
PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/executors/ -k "phase_b" 2>&1 | tail -20

# Fix 3: pre-push-fast — manual verification
grep -c "Tracker sync note" TASKS.md  # count notes
bash -x tools/hooks/pre-push-fast </dev/null 2>&1 | head -5  # syntax check

# Fix 4: hook — test with mock input
echo '{"tool_input":{"command":"git stash"}}' | bash .claude/hooks/block-protected-branch.sh

# Full gate
./tools/audit_fast.sh
```

## Out of scope

- derive_wave_id.sh shares logic with pre-push-fast but is only used by CI — fix pre-push-fast first, CI uses its own copy
- `.agent_bus/bridge_config.json` effort flag is local-only config, not committed
