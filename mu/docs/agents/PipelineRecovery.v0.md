<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-03-31
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

---
DOC_STATUS: DRAFT
---

# Pipeline Recovery System — Design v0

**Date:** 2026-03-31
**Status:** DRAFT — design only, not implemented
**Author:** Claude Opus 4.6 / Jeff Abrams

---

## Architecture Overview

The recovery system sits between `executor_dispatch.py` and the individual executors. It intercepts failure results and classifies them into four tiers.

```
                     executor_dispatch.py
                             |
                      dispatch() result
                             |
                +--- recovery_gate.py ---+
                |                        |
         classify_failure()        recovery_log.json
                |
   +------+------+------+------+
   |      |      |      |      |
 Tier 1  Tier 2  Tier 3  Tier 4
 (fix)   (retry) (diag)  (esc)
   |      |      |      |
 cleanup retry  claude   STOP
 + retry        haiku    + report
                + retry
```

**Key constraint:** `recovery_gate.py` is a single-file module importing only stdlib + `executor_common.py`. It never imports `bridge_supervisor`, `bridge_adapters`, or any agent module. Tier 3 diagnosis calls `claude --print` directly via subprocess — no bridge loop, no SDK agents.

---

## Failure Classification Taxonomy

```python
class FailureClass(Enum):
    # Tier 1 — deterministic auto-fix (zero tokens)
    STALE_BRIDGE_LOCK = "stale_bridge_lock"
    STALE_GIT_INDEX_LOCK = "stale_git_index_lock"
    STALE_EXECUTOR_STATE = "stale_executor_state"
    STALE_CONTINUATION = "stale_continuation"
    MIXED_STAGING = "mixed_staging"

    # Tier 2 — auto-retry with adjustment (zero tokens)
    PROCESS_TIMEOUT = "process_timeout"
    TRANSIENT_KILL = "transient_kill"
    AGGREGATION_HANG = "aggregation_hang"
    IMPLEMENTER_STALE = "implementer_stale"

    # Tier 3 — LLM diagnosis (small focused prompt)
    GIT_STAGING_CONFLICT = "git_staging_conflict"
    TEST_FAILURE = "test_failure"
    AGENT_REVIEW_CRASH = "agent_review_crash"
    UNKNOWN_ERROR = "unknown_error"

    # Tier 4 — escalate (never recover)
    TERMINAL_POLICY = "terminal_policy"
    UNCLASSIFIED = "unclassified"
```

Classification is pure dict inspection — reads `result["status"]`, `result["step"]`, `result.get("stderr")`, exit codes. No external calls.

---

## Tier Definitions

### Tier 1: Deterministic Auto-Fix (zero tokens)

| Failure Signal | Detection | Recovery |
|---|---|---|
| `.agent_bus/bridge.lock` held by dead PID | `kill -0 pid` fails | Truncate lock file |
| `.git/index.lock` exists | `Path.exists()` | `os.unlink()` |
| Stale `phase_b_state.json` from prior run | wave_id mismatch with current routing | `Path.unlink()` |
| Stale commit_executor continuation records | File age > 1h, no executor alive | `Path.unlink()` |
| Mixed staged/unstaged state | `git status --porcelain` shows both index and worktree changes | `git reset HEAD -- <files>` |

After fix: retry the failed step via `dispatch()` with same routing.

### Tier 2: Auto-Retry with Adjustment (zero tokens)

| Failure Signal | Detection | Recovery |
|---|---|---|
| Process timeout | `status == "timeout"` | Increase timeout 50% (capped 2x), retry once |
| Transient process kill | exit_code in (-9, -15, 137) | Retry with same parameters |
| Bridge aggregation hang | stderr contains "aggregation" | Clear bridge state, retry |
| Implementer stale timeout | `implementer_status == "stale"` | Increase stale timeout, retry |

Timeout adjustments passed via `RCX_RECOVERY_TIMEOUT_OVERRIDE` env var.

### Tier 3: LLM Diagnosis (one focused API call)

| Failure Signal | Detection | Recovery |
|---|---|---|
| Git staging conflict | `git add` failure in commit_executor | Claude reads git status + error, emits shell commands |
| Test failure in pre-commit | supervisor_rejected with test output | Claude reads test output (last 100 lines), emits diagnosis |
| Agent review crash | partial status JSON, no report | Claude reads partial status + agent log, decides retry/skip/escalate |
| Unknown executor error | `status == "error"` with no Tier 1/2 match | Claude reads error JSON + log tail, emits recovery plan |

**Tier 3 uses a Recovery Loop (not one-shot):**

```
Recovery Loop:  Diagnose → Implement Fix → Verify → ─(pass)─→ Re-enter Pipeline
                  ↑                          |
                  └───────(fail, max 3)──────┘
                              |
                         (exhausted)
                              ↓
                    Escalate + Learning Store
```

- **Diagnose**: Claude reads error + logs (~2K token focused prompt)
- **Implement Fix**: Claude emits shell commands OR small code edits (NOT a full Phase B pass)
- **Verify**: Run the specific check that failed (one gate, not full audit_fast)
- **Max 3 iterations**, then escalate to Tier 4
- Invocation: `subprocess.run(["claude", "--print", "-p", prompt_text], timeout=60)` — NOT through bridge adapter stack (bootstrap paradox)
- Token budget: ~2000 input, ~200 output per iteration

**Key constraint:** Recovery does NOT invoke Phase B, bridge review, or SDK agents. The recovery loop is lighter than the main pipeline — it diagnoses, applies a bounded fix, and verifies the specific gate that failed. If the fix works, re-enter the main pipeline at the failed step.

### Tier 4: Escalate

| Failure Signal | Detection | Recovery |
|---|---|---|
| Same failure after 3 recovery loop iterations | Recovery loop exhausted | Stop + detailed report |
| Same failure after 2 recovery gate attempts | Recovery log shows 2 prior attempts for (wave_id, step, class) | Stop + report |
| Terminal executor outcome | `question_for_founder`, `max_rounds_reached`, `supervisor_rejected` | Never recover — these are policy decisions |
| Unknown failure class | Classifier returns None | Stop + report |
| Recovery script itself failed | Tier 3 commands returned nonzero | Stop + report both errors |

---

## Learning Store

Every recovery attempt is logged to `.agent_bus/recovery/recovery_log.json`. Over time, the learning store enables automatic promotion:

- **Pattern detection**: If the same (failure_class, fix_action) succeeds 3+ times, promote to Tier 1 (deterministic auto-fix)
- **Environment learning**: The pipeline learns YOUR machine's specific failure modes (e.g., "Bun AVX warnings always appear but are harmless", "pkill -f is dangerous on this machine")
- **Regression detection**: If a previously-promoted Tier 1 fix starts failing, demote back to Tier 3

This transforms the recovery gate from a static classifier into an adaptive system that improves with each pipeline run.

---

## Bounded Retry Policy

- **Recovery loop**: max 3 diagnose/fix/verify iterations per Tier 3 invocation
- **Recovery gate**: max 2 attempts per (wave_id, step, failure_class) tuple
- Different failure classes counted independently
- Recovery log at `.agent_bus/recovery/recovery_log.json` (capped at 500 entries)
- Dispatch `max_attempts` is independent outer bound
- Terminal policy outcomes are never recovered

```json
{
  "attempts": [
    {
      "timestamp": "2026-03-31T14:22:00Z",
      "wave_id": "wave1a-validation",
      "step": "stage_files",
      "failure_class": "stale_git_index_lock",
      "tier": 1,
      "action": "unlink .git/index.lock",
      "outcome": "success",
      "duration_s": 0.3,
      "tokens_used": 0
    }
  ]
}
```

---

## Re-entry Protocol

After recovery, the pipeline resumes at the failed step using existing mechanisms:

1. **Phase B resume** — `phase_b_executor.py` persists state at `.agent_bus/executors/phase_b_state.json`. Recovery preserves valid state (environmental failure) or clears stale state.
2. **Commit continuation** — `commit_executor.py:_load_post_commit_continuation()` resumes post-commit steps from continuation records.
3. **Dispatch retry** — `executor_dispatch.py` retry loop (line ~1098-1144) with `_clear_phase_b_state_for_retry()` and `_auto_refresh_routing()`.

The recovery gate hooks into the dispatch retry loop between `_is_terminal_executor_outcome()` and the retry sleep. Returns modified result with `status: "recovered"` (loop retries) or original result (loop handles normally).

---

## Observability

**Recovery log** — `.agent_bus/recovery/recovery_log.json` is source of truth.

**Web dashboard** — Add `recovery_status()` to `get_state()`:
- "Idle" / "Recovering (Tier N): failure_class" / "Escalated: reason"
- Recent attempts table

**tmux pane** — Add "RECOVERY" section after "BRIDGE" block:
- Last attempt: tier, action, outcome, age
- Active recovery indicator

---

## Anti-Patterns

1. **Bootstrap paradox** — Never import bridge_supervisor/bridge_adapters in recovery. Use `claude --print` directly for Tier 3.
2. **Infinite loops** — 2-attempt bound per (wave, step, class). Never retry terminal policy outcomes.
3. **Masking real bugs** — Recovery doesn't modify source code or skip tests. Tier 3 can diagnose but only emit cleanup commands.
4. **Accidental kills** — Never use `pkill -f`. Use `terminate_process_tree()` with specific PIDs.
5. **Expensive Tier 3** — Cap at 2000 input tokens, 200 output. Not a code review task.
6. **Recovering policy decisions** — `question_for_founder`, `supervisor_rejected`, etc. are the pipeline working correctly.

---

## Implementation Phases

| Phase | Scope | Effort |
|---|---|---|
| **1** | Classifier + Tier 1 auto-fix + recovery log | 1 wave |
| **2** | Tier 2 auto-retry + timeout adjustment | 0.5 wave |
| **3** | Observability (dashboard + tmux) | 0.5 wave |
| **4** | Tier 3 LLM diagnosis + remediation | 1 wave |
| **5** | Bounded retry integration + end-to-end test | 0.5 wave |

**New file:** `mu/tools/executors/recovery_gate.py`
**Modified files:** `executor_dispatch.py` (hook), `pipeline_dashboard_web.py` (UI), `_pane_processes.sh` (tmux)
