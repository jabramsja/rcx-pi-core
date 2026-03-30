# TASKS.md NEXT Section Cleanup

**Phase-A-Lock: LOCKED**
**Task:** [NEXT-CODEX-POST-REDTEAM]
**Wave class:** MAINTENANCE
**Target gate:** G8

---

## Problem

TASKS.md NEXT section contains 12 CLOSED items with extensive verbose history (thousands of words each). The post-merge supervisor reads all of this and gets confused about what the canonical next item is, returning CONTINUE_DIALECTIC instead of routing to Phase A/B.

## Fix

1. Replace each CLOSED item in NEXT with a one-line stub: `- ~~**[TASK-ID]**~~ **CLOSED** (date, moved to Ra). [one-line summary].`
2. Keep only `[NEXT-CODEX-POST-REDTEAM]` as the full active entry.
3. Keep the completed items section header and note at the bottom.
4. Move the verbose history to Ra section (it's already duplicated there for most items).
5. Remove stale `pipeline_monitor_2026-03-28_2026-03-28.md` file if it exists in working tree.

## Files changed
- `TASKS.md`

## Validation
```bash
./tools/checks/check_docs_consistency.sh
python3 -m pytest tests/docs/ -q --tb=short
```

## Scope boundary
- ONLY trim CLOSED NEXT items. Do NOT change Ra section, governance, North Star, or active NEXT items.
- Do NOT change tracker sync notes (they are in Ra section, not NEXT).
