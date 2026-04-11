# Learning Store + Enforcement Architecture

Date: 2026-04-08
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: learning-store-enforcement-2026-04-08

## 1. Scope

Two bounded items combined into one control-surface wave:

**Item A — Learning Store (PIPELINE-RECOVERY item 5):**
Complete the recovery ecosystem by adding persistent learned patterns to `recovery_gate.py`.
Design: `mu/docs/agents/PipelineRecovery.v0.md` (Learning Store section, lines 156-342).

**Item B — Enforcement Architecture (founder-directed 2026-04-08):**
Add mechanical enforcement hooks that prevent workaround cascades. Based on founder diagnosis that reactive hooks fire too late — need pre-action gates.

### Files in scope

- `mu/tools/executors/recovery_gate.py` — learning store: `learned_patterns.json`, `check_learned_patterns()`, `observe_outcome()`, promotion/demotion
- `.claude/hooks/workaround-gate.sh` — NEW: PreToolUse:Bash hook that asks "workaround or structural fix?" before action
- `.claude/rules/workaround-budget.md` — NEW: rule file enforcing max 1 workaround per obstacle
- `.claude/settings.json` — wire workaround-gate hook into PreToolUse
- `mu/tests/tools/test_recovery_gate.py` — tests for learning store

### Directories in scope

- `.agent_bus/recovery/` — `learned_patterns.json` persistence
- `.claude/hooks/` — new workaround gate hook
- `.claude/rules/` — new workaround budget rule

## 2. Work items

### Learning Store (Item A)

1. Add `LEARNED_PATTERNS_FILE`, promotion/demotion constants to `recovery_gate.py`
2. Implement `_load_learning_store()`, `_save_learning_store()` persistence functions
3. Implement `check_learned_patterns(repo_root, failure_class, stderr_signal)` — check if a learned pattern matches before static classification
4. Implement `observe_outcome(repo_root, failure_class, action, fingerprint, outcome, wave_id)` — record outcome, check promotion/demotion
5. Wire `check_learned_patterns()` into `classify_failure()` (top, before static)
6. Wire `observe_outcome()` into `_save_recovery_log()` call sites (6 total per design doc)
7. Add tests: promotion after 3 successes across 2 waves, single-failure demotion, pattern expiry

### Enforcement Architecture (Item B)

8. Create `workaround-gate.sh` PreToolUse:Bash hook: on commands that create files or run subprocess (not grep/read/ls), inject "Is this a workaround or structural fix? Name the structural alternative."
9. Create `.claude/rules/workaround-budget.md`: max 1 workaround per obstacle, second workaround = protocol violation, mandatory structural fix
10. Wire hook into `.claude/settings.json` PreToolUse section

## 3. Constraints (what is NOT in scope)

- No changes to Tier 1-3 recovery logic (already landed)
- No changes to dispatcher or commit executor
- No runtime (`mu/host/`) changes
- No subagent learning injection (deferred per design doc — future wave)
- No cross-session persistence bridge (deferred — requires worktree teardown hooks)

## 4. Stop conditions

Stop when ALL of the following are true:

1. `learned_patterns.json` is created and loaded by `classify_failure()`
2. `observe_outcome()` is called at recovery log save sites
3. Promotion works: 3+ successes across 2+ waves promotes to Tier 1
4. Demotion works: single failure demotes immediately
5. `workaround-gate.sh` hook fires on Bash tool calls and injects structural-fix prompt
6. `.claude/rules/workaround-budget.md` exists with max-1-workaround rule
7. All tests pass

## 5. Acceptance criteria

1. `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short` — all tests pass
2. `./tools/checks/check_docs_consistency.sh` — clean
3. `python3 tools/checks/enforce_l4_execution_contract.py --staged` — clean

## 6. Grounding / Authorization

- **TASKS.md authorization:** Lines 159-165, `[PIPELINE-RECOVERY]` **IN PROGRESS**, remaining: (5) Learning store.
- **Enforcement architecture:** Founder-directed 2026-04-08, saved to `feedback_workaround_budget.md` in memory.
- **Design doc:** `mu/docs/agents/PipelineRecovery.v0.md` (Learning Store section).
- **Lane:** control-surface (pipeline hardening + enforcement).
