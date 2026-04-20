Phase-A-Lock: LOCKED

# commit_executor Step 14 fail-fast on CONFLICTING/DIRTY PRs — 2026-04-20

wave_id: step14-autoconflict-resolve-2026-04-20
phase: A
task_id: [NEXT-CODEX-POST-REDTEAM]
wave_class: L4_ENABLER
target_gate_id: G8

## Problem statement

`commit_executor.py` Step 14 invokes `gh pr checks --watch --required` then falls back to `_poll_ci_checks_fallback` on a 900-second budget. When the PR is `mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` (documented 2026-04-17 learning), GitHub Actions silently skips `pull_request`-triggered workflows (green-gate, fixture-gates) because it cannot compute a merge-ref. The required-checks list is therefore permanently incomplete — polling CANNOT succeed within any finite timeout. The executor wastes ~15 minutes on the doomed poll before error-exiting, and the user/Claude must then run the 2026-04-17 recovery recipe manually (observed 2x this session: PR #803 routing-api-plus-write-gate and initial investigation before PR #805 ast-anticheat).

## Scope (files in scope)

- `mu/tools/executors/commit_executor.py` — add `_check_pr_conflict_state()` helper (fails open on any `gh` / JSON error so pre-check is perf optimization, not correctness guard) + insert pre-check at Step 14 entry. On CONFLICTING/DIRTY detection, fail-fast with structured error containing the recovery recipe pointer and `failure_class: pr_conflicting`. All other conditions proceed to normal `_wait_for_required_checks_to_register` + `gh pr checks --watch` path unchanged.
- `mu/tests/tools/test_commit_executor_step14_conflict_precheck.py` — 9 unit tests covering: CONFLICTING detection, DIRTY-only detection, MERGEABLE+CLEAN returns None, MERGEABLE+BLOCKED returns None (transient state), gh nonzero exit fails open, SubprocessError fails open, malformed JSON fails open, empty stdout fails open, log callback invoked on error path. All mock `subprocess.run` for `gh pr view`.
- `mu/tests/docs/test_growth_caps.py` — `CAP_TEST_FILES` 112→113 (+1 for the new test file).

## Constraints (out of scope)

- Automatic merge-dev recovery (the full 2026-04-17 recipe: fetch base, merge, resolve TASKS.md tracker-note conflict chronologically, `RCX_SKIP_RECEIPT_CHECK=1` commit, push, resume) — queued as a follow-on wave. Fail-fast is the structural first step; auto-resolve is the second. Splitting reduces blast-radius on a critical-path runtime surface.
- Any change to `_wait_for_required_checks_to_register` or `_poll_ci_checks_fallback` — pre-check runs BEFORE those.
- `gh pr view`'s `UNKNOWN` mergeable state (transient during post-merge API processing) is treated as "not conflicting" by the narrow `== "CONFLICTING"` check; that is the correct behavior (don't fail a PR for a transient race).
- Recovery-gate classification — the `failure_class: pr_conflicting` tag is added to the error dict but existing recovery-gate consumers are not updated this wave.

## Work items

1. Add `_check_pr_conflict_state(repo_root, *, pr_number, log)` function in `commit_executor.py` right before `_poll_ci_checks_fallback`. Query via `gh pr view <N> --json mergeable,mergeStateStatus` with 20s timeout + text=True + check=False. Parse JSON with `json.loads`. Return `"mergeable=CONFLICTING"` when `mergeable == "CONFLICTING"`; `"mergeStateStatus=DIRTY"` when `merge_state == "DIRTY"`; otherwise `None`. Fail open on `SubprocessError`, `OSError`, nonzero exit, and `JSONDecodeError` (all return `None` with optional `log` diagnostic).
2. In `run_commit_pipeline` at the Step 14 entry, call the helper before `_wait_for_required_checks_to_register`. On non-None result, return `{"status":"error", "step":"wait_ci", "errors":[<human-readable recovery-recipe pointer>], "failure_class":"pr_conflicting", "steps_completed":..., "pr_number":...}`.
3. Add the 9-test regression file per Scope.
4. Bump `CAP_TEST_FILES` 112→113 with wave-attribution comment.

## Stop conditions

- Any change to a file outside the 3-file scope → HALT, escalate.
- Attempt to auto-resolve the conflict (vs fail-fast) → HALT (explicitly out-of-scope this wave).
- Plan body > 100 lines → HALT, re-scope.
- Founder amends directive before Phase B → HALT, re-plan.

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_step14_conflict_precheck.py` passes with 9 test cases green.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_growth_caps.py` passes with 3 test cases green.
- `python3 -c "import ast; ast.parse(open('mu/tools/executors/commit_executor.py').read()); print('OK')"` exits 0.
- Behavior unchanged for non-CONFLICTING/non-DIRTY PRs — verified by the 2 positive pre-check tests returning `None`.
- Pre-check fails open on every `gh` / JSON error path — verified by 5 fail-open tests.
- The structured error message references the 2026-04-17 recovery recipe explicitly so a future Claude session hitting it can follow the steps without re-reading the learning entry.

## Grounding / Authorization

- **Governing tracked packet:** this file. Fourth sibling narrow control-surface pipeline-hardening wave this session (after PRs #802/#803/#804/#805).
- **`task_id` is a procedural Gate 8 anchor** — same pattern as PRs #802-#805.
- **Direct learning trigger:** `.claude/rules/learning.md` 2026-04-20 entry `commit_executor Step 14 waiting for CI PR CONFLICTING DIRTY mergeStateStatus pull_request workflow silent skip 300s 900s timeout doomed poll`. The "Structural fix candidate" note in that entry names this wave's narrow scope (detect + fail-fast) as the first structural step before full auto-resolve.
- **Founder autonomous directive 2026-04-20**: standing auth + "after this wave, automatically do next valuable highest roi wave autonomously. If override needed give override." — fourth exercise.
- **`FOUNDER_OVERRIDE:step14-autoconflict-resolve-2026-04-20`** — wave-specific single-use token; fourth self-test of the `founder_override_token` mechanization from PR #803.
- **Lane: control-surface (pipeline hardening)**.
- **Bootstrap classification: NOT bootstrap.** Touches `commit_executor.py` (tooling surface, not `mu/host/python/rcx_pi/selfhost/` substrate) + test file + growth caps. Narrow additive surface (one new helper function + one call site + one test file).
