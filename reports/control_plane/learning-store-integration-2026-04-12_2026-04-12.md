# Learning-Store-Integration-2026-04-12

Date: 2026-04-12
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Phase-A-Lock: LOCKED
Purpose: Cross-pollination between the learning store (`recovery_gate.py` / `learned_patterns.json`) and `.claude/rules/learning.md`. Subagent warming (Item B) deferred to a separate wave.

## Scope

Files in scope:

- `mu/tools/executors/recovery_gate.py` — write path (export on promotion) + read path (FIXED entry Tier 1 candidacy)
- `.claude/rules/learning.md` — target for promotion exports (append-only) + source for FIXED entries
- `mu/tests/tools/test_recovery_gate.py` — tests for cross-pollination

Directories in scope:

- `mu/tools/executors/` — recovery_gate changes
- `.claude/rules/` — learning.md target

## Work Items

Derived from TASKS.md:182 — `[PIPELINE-RECOVERY]` Phase 5 integration gaps.

### 1. Write path: learning store exports to `.claude/rules/learning.md`

When `observe_outcome()` promotes a pattern (success_count >= 3, unique waves >= 2), append a formatted entry to `.claude/rules/learning.md`:

```
- [DATE] PIPELINE | fingerprint: `<text>` | refs: N
```

Implementation:
- (a) Add `_export_to_learning_md(record, repo_root)` in `recovery_gate.py`. Opens file in append mode (`"a"`) — never reads or rewrites existing content. If file absent, append mode creates it.
- (b) Wire to `observe_outcome()` promotion gate. Trigger ONLY on first promotion transition: capture `prev_tier = record.get("promoted_tier")` before gate, export only if `record["promoted_tier"] == 1 and prev_tier != 1`.
- (c) Use fcntl advisory lock for concurrent safety (same pattern as `_save_learning_store`).

### 2. Read path: recovery gate consults FIXED entries

When `check_learned_patterns()` returns None (no auto-observed match), check `.claude/rules/learning.md` for FIXED entries as fallback Tier 1 candidates.

FIXED entry grammar (defined by this wave):
```
- [DATE] FIXED | fingerprint: `<text>` | action: `<fix description>`
```

Implementation:
- (d) Add `_load_session_fixed_entries(repo_root)` in `recovery_gate.py`. Parses FIXED lines via regex. Returns empty list if file absent.
- (e) Wire into `attempt_recovery()` after `check_learned_patterns()` returns None. Match fingerprints via `_normalize_fingerprint()` substring match. Construct `LearnedMatch(failure_class=classify_failure(result), tier=1, action=<fix text>)`. Existing terminal-policy and fix_fn validation gates apply unchanged.
- (f) Auto-observed patterns take priority over FIXED entries (richer matching semantics).

### 3. Tests

- (g) Promotion triggers learning.md append (round-trip test)
- (h) Non-promotion save does NOT trigger export
- (i) FIXED entry preservation: write FIXED entry before promotion, verify it survives
- (j) Transition safety: repeated qualifying successes produce exactly one export entry
- (k) FIXED entry match constructs LearnedMatch with correct failure_class and tier=1
- (l) Terminal-policy override (tier >= 4) still overrides FIXED match
- (m) Absent rules file is graceful no-op

## Constraints

- NO changes to Tier 1-3 recovery logic (PR #704-706 baseline)
- NO changes to executor dispatch or commit executor
- NO runtime (`mu/host/`) changes
- NO changes to `agent_memory.py`, `run_review.py`, `phase_b_implementer.py`, or `phase_b_executor.py` (subagent warming deferred)
- `.claude/rules/learning.md` stays 644 (writable) — preflight re-sets after bulk protect
- Export is append-only — never reads, rewrites, or clobbers existing content

## Stop Conditions

1. `observe_outcome` promotion appends to `.claude/rules/learning.md`
2. `attempt_recovery` reads FIXED entries for Tier 1 candidacy
3. All new tests pass
4. `bash tools/pre-push-fast` passes

## Acceptance Criteria

- learning.md append verified via round-trip test
- FIXED entry fallback verified with fingerprint match
- Existing recovery tests still pass (no regression)
- pre-push-fast green

## Grounding / Authorization

- **Parent task:** `[PIPELINE-RECOVERY]` (TASKS.md:182). Phase 5 (learning store) landed as code baseline (PR #751).
- **Design:** `mu/docs/agents/PipelineRecovery.v0.md` sections on cross-pollination (lines 253-268)
- **Wave class:** L4_ENABLER
- **target_gate_id:** G8
- **Deferred:** Item B (subagent warming via `agent_memory.py` / `run_review.py` / `phase_b_implementer.py`) — separate wave due to import-boundary architectural decisions needed