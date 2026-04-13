# Learning Store Warming (Item B)

Date: 2026-04-12
Status: Phase A (design — not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: learning-store-warming-2026-04-12

## 1. Scope

Subagent warming: inject learning store patterns into SDK agent and implementer prompts.

### Files in scope

- `mu/tools/executors/recovery_gate.py` — new `load_relevant_learnings(agent_name, files, repo_root)` function. Single owner of `learned_patterns.json` + `.claude/rules/learning.md` read paths (both already consumed by this file via `_load_learning_store()` and `_load_session_fixed_entries()`).
- `mu/tools/runners/run_review.py` — call `load_relevant_learnings()` at prompt construction (line 731, alongside existing `get_pattern_context()`). Import via `from tools.executors.recovery_gate import load_relevant_learnings` (verified: `sys.path` includes `mu` at `run_review.py:65-66`).
- `mu/tools/executors/phase_b_executor.py` — compute `learning_context` once via `load_relevant_learnings()` (already has `mu/tools/executors` on `sys.path` at line 2167-2169), pass as string to `build_implementation_prompt()` at all four call sites (lines 2317, 2738, 2795, 3095).
- `mu/tools/executors/phase_b_implementer.py` — `build_implementation_prompt()` receives `learning_context: str = ""` kwarg and injects it. No import needed — receives pre-computed string from caller.
- `mu/tests/tools/test_recovery_gate.py` — tests for `load_relevant_learnings()`
- `mu/tests/tools/test_run_review.py` — tests for warming injection

### Directories in scope

- `mu/tools/executors/` — recovery_gate + phase_b_executor + phase_b_implementer
- `mu/tools/runners/` — run_review warming wiring
- `mu/tests/tools/` — tests

## 2. Architecture Decision (resolved)

**Single ownership in `recovery_gate.py`** — `load_relevant_learnings()` lives in `recovery_gate.py` because it reads `learned_patterns.json` (already owned by `_load_learning_store()`) and `.claude/rules/learning.md` (already owned by `_load_session_fixed_entries()` from PR #768). No cross-package file reads.

**Import paths (verified 2026-04-12):**
- `run_review.py` → `from tools.executors.recovery_gate import load_relevant_learnings` (sys.path includes `mu` at line 65-66, verified via `python3 -c "sys.path.insert(0, 'mu'); from tools.executors.recovery_gate import _load_learning_store"`)
- `phase_b_executor.py` → direct import (sys.path includes `mu/tools/executors` at line 2167-2169)
- `phase_b_implementer.py` → no import (receives pre-computed string from `phase_b_executor.py`)

**Metadata asymmetry handling:** JSON entries (`learned_patterns.json`) have `failure_class` → filtered by agent-specific mapping. Markdown entries (`.claude/rules/learning.md`) lack `failure_class` → included unfiltered, markdown fills remaining budget after JSON entries. 1000-token cap enforced inside `load_relevant_learnings()`.

## 3. Work Items

### (a) `load_relevant_learnings(agent_name, files, repo_root)` in `recovery_gate.py`

- Reads `learned_patterns.json` via `_load_learning_store(repo_root)` (existing function)
- Reads `.claude/rules/learning.md` via `_load_session_fixed_entries(repo_root)` (PR #768)
- Filters JSON entries by `failure_class` matching agent domain (static mapping: `{"adversary": ["SECURITY_*"], "expert": ["COMPLEXITY_*"], "implementer": ["BUILD_*", "IMPORT_*", "TEST_*"]}` etc.)
- Markdown entries unfiltered (no metadata for filtering)
- Budget: JSON entries first (filtered, higher signal), markdown fills remainder. Cap 1000 tokens. Most recent first.
- Returns formatted string or empty string

### (b) Wire `run_review.py` prompt construction

- At line 731 (alongside `get_pattern_context()`): call `load_relevant_learnings(agent_name, self.files, active_repo_root)`
- Inject result as `learning_context` section in prompt (parallel to `memory_context` at line 762)
- Separate 1000-token budget (does not share with `memory_context`'s 4000-char cap)

### (c) Wire `phase_b_executor.py` → `phase_b_implementer.py`

- `phase_b_executor.py`: compute `learning_context = load_relevant_learnings("implementer", plan_declared_files, repo_root)` once
- Pass to `build_implementation_prompt(learning_context=learning_context)` at all 4 call sites (lines 2317, 2738, 2795, 3095)
- `phase_b_implementer.py`: add `learning_context: str = ""` kwarg to `build_implementation_prompt()` (line 65), inject as `## Learning Context` section

### (d) Tests

- `load_relevant_learnings` returns formatted string with promoted patterns
- Agent-specific filtering: adversary gets security patterns, expert gets complexity patterns
- 1000-token cap enforced
- Empty store/file → empty string (graceful)
- `run_review.py` injects learning_context into prompt
- `phase_b_implementer.py` injects learning_context into prompt

## 4. Constraints

- NO changes to Tier 1-3 recovery logic
- NO changes to runtime (`mu/host/`)
- NO changes to `agent_memory.py` (warming ownership stays in `recovery_gate.py`)
- Existing `get_pattern_context()` in `agent_memory.py` is NOT modified
- `learned_patterns.json` read via existing `_load_learning_store()` — no new file readers

## 5. Stop Conditions

1. `load_relevant_learnings()` returns agent-specific filtered content
2. `run_review.py` injects learning_context into all agent prompts
3. `phase_b_implementer.py` receives learning_context from `phase_b_executor.py`
4. All new tests pass
5. `bash tools/pre-push-fast` passes

## 6. Grounding / Authorization

- **Parent task:** `[PIPELINE-RECOVERY]` (TASKS.md:182). Phase 5 learning store code baseline (PR #751). Item A cross-pollination (PR #768).
- **Design:** `mu/docs/agents/PipelineRecovery.v0.md` lines 270-281 (subagent learning injection)
- **Wave class:** L4_ENABLER
- **target_gate_id:** G8
