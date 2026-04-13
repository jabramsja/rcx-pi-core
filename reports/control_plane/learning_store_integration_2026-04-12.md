# Learning Store Integration — Cross-Pollination + Subagent Warming

Date: 2026-04-12
Status: Phase A (design — not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: learning-store-integration-2026-04-12

## 1. Scope

Two bounded items completing the learning store integration (PR #751 code baseline):

**Item A — `.claude/rules/learning.md` cross-pollination (~0.5 wave):**
When `observe_outcome` in `recovery_gate.py` promotes a pattern (sc>=3, waves>=2),
append a corresponding entry to `.claude/rules/learning.md` in the canonical format:
`- [DATE] PIPELINE | fingerprint: \`...\` | refs: N`. Read learning.md during
`classify_failure` to seed Tier 1 candidacy for manually-documented patterns.
This bridges the learning store (JSON, per-worktree) and the Claude session learning
log (markdown, auto-loaded every session).

**Item B — subagent learning injection (~1 wave):**
Add `load_relevant_learnings()` and `format_learning_context()` to
`mu/tools/runners/run_review.py`, gated by a 1000-token cap. SDK agents get warmed
with promoted patterns from both the learning store and `.claude/rules/learning.md`.
Note: SDK agent review is currently disabled (`agent_review_enabled: false` in
`executor_config.json`, PR #758). This injection wires into the review path for when
agents are re-enabled for security-critical waves.

### Files in scope

- `mu/tools/executors/recovery_gate.py` — `observe_outcome()` promotion path: append to learning.md
- `mu/tools/executors/recovery_gate.py` — `classify_failure()`: read learning.md for Tier 1 seeds
- `mu/tools/runners/run_review.py` — `load_relevant_learnings()`, `format_learning_context()`
- `.claude/rules/learning.md` — target for cross-pollination writes (keep 644 perms)
- `mu/tests/tools/test_recovery_gate.py` — tests for cross-pollination
- `mu/tests/tools/test_run_review.py` — tests for learning injection

### Directories in scope

- `mu/tools/executors/` — recovery_gate cross-pollination
- `mu/tools/runners/` — run_review learning injection
- `.claude/rules/` — learning.md target

## 2. Work items

### Item A — Cross-pollination

1. In `observe_outcome()` at `recovery_gate.py`, after promotion logic: append a learning.md entry
2. In `classify_failure()`: parse `.claude/rules/learning.md` for `PIPELINE` entries with fingerprints, check against failure signal for Tier 1 candidacy
3. Add tests: promotion triggers learning.md append, classify reads learning.md entries

### Item B — Subagent warming

4. Add `load_relevant_learnings(repo_root, failure_classes=None)` to `run_review.py` — reads learning store + learning.md, filters by relevance, caps at 1000 tokens
5. Add `format_learning_context(learnings)` — formats for agent prompt injection
6. Wire into agent prompt construction (when `agent_review_enabled: true`)
7. Add tests: learning context injected, 1000-token cap enforced

## 3. Constraints

- NO changes to Tier 1-3 recovery logic (PR #704-706)
- NO changes to executor dispatch or commit executor
- NO runtime (`mu/host/`) changes
- learning.md stays 644 (writable) — preflight re-sets after bulk protect
- Cross-pollination writes must use fcntl lock (same as learning store persistence)

## 4. Stop conditions

1. `observe_outcome` promotion appends to `.claude/rules/learning.md`
2. `classify_failure` reads learning.md entries for Tier 1 candidacy
3. `run_review.py` has `load_relevant_learnings` + `format_learning_context`
4. All new tests pass
5. `bash tools/pre-push-fast` passes

## 5. Grounding / Authorization

- **Parent task:** `[PIPELINE-RECOVERY]` (TASKS.md). Phase 5 (learning store) landed as code baseline.
- **Design:** `mu/docs/agents/PipelineRecovery.v0.md` sections on cross-pollination (lines 253-268) and subagent injection (lines 270-281)
- **Session handoff:** `reports/control_plane/session_handoff_2026-04-11_block_protected_lexer.md` Part 2, section 2.6 — moves A and B
- **Wave class:** L4_ENABLER
- **target_gate_id:** G8
