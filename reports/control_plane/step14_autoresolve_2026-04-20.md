Phase-A-Lock: LOCKED

# commit_executor Step 14 auto-resolve CONFLICTING/DIRTY PRs — 2026-04-20

wave_id: step14-autoresolve-2026-04-20
phase: A
task_id: [NEXT-CODEX-POST-REDTEAM]
wave_class: L4_ENABLER
target_gate_id: G8

## Problem statement

PR #806 landed the Step 14 fail-fast pre-check — `_check_pr_conflict_state()` at `commit_executor.py:1648` detects `mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` and returns a structured error rather than wasting 900s on the doomed CI poll. That was the narrow first cut. The follow-on: **auto-resolve** the detected conflict using the 2026-04-17 learning recipe (fetch base → merge → resolve TASKS.md tracker-note conflict chronologically → `RCX_SKIP_RECEIPT_CHECK=1` commit → push) instead of asking the caller to run it manually.

Observed 2x this session: PR #803 routing-api-plus-write-gate hit CONFLICTING after PR #802 merged during the same session; recovery required the 5-step manual recipe. The 2026-04-17 learning entry documents the exact sequence — this wave mechanizes it so future concurrent-merge scenarios resolve in-pipeline without human intervention.

## Scope (files in scope)

- `mu/tools/executors/commit_executor.py` — add 5 new helpers before `_poll_ci_checks_fallback`:
  - `_resolve_tasks_md_tracker_note_conflict(path)` — deterministic chronological resolver (origin block first = merged-first wave, HEAD block second = current wave). Returns `True` iff every conflict block's both sides are tracker-note-only; returns `False` WITHOUT modifying the file on any non-tracker-note content or malformed marker (nested/dangling).
  - `_is_tracker_note_only(buf)` — validator accepting `- Tracker sync note (` and `- ~~Tracker sync note (` prefixes with leading-whitespace tolerance; blank lines allowed.
  - `_try_auto_resolve_pr_conflict(repo_root, *, pr_number, base_branch, branch_name, log)` — orchestrator calling the existing `_check_pr_conflict_state` first; on conflict, `git fetch origin <base>` → `git merge origin/<base> --no-edit` → branch: (a) clean merge → push (action=`clean_merge`); (b) conflict in TASKS.md only + resolver succeeds → `git add TASKS.md` + `RCX_SKIP_RECEIPT_CHECK=1 git commit --no-edit` + push (action=`tasks_md_resolved`); (c) otherwise → `git merge --abort` + return aborted (action=`aborted`).
  - `_abort_merge(repo_root, *, log)` — best-effort `git merge --abort` swallowing errors.
  - `_push_branch(repo_root, branch_name)` — `git push origin <branch>` returning `(ok, err)` tuple.
- `mu/tools/executors/commit_executor.py` — Step 14 call site: replace the existing PR #806 `_check_pr_conflict_state`-only pre-check with a `_try_auto_resolve_pr_conflict` call. On `resolved=False`, fail-fast with `failure_class: pr_conflicting` + `auto_resolve_action: <action>` field + updated error message. On `resolved=True`, log action and fall through to normal CI poll.
- `mu/tests/tools/test_commit_executor_step14_autoresolve.py` (new, 19 tests) — covers: `_is_tracker_note_only` (7 tests: standard notes, strikethrough, leading whitespace, blank lines, code-block rejection, prose rejection, empty buffer); `_resolve_tasks_md_tracker_note_conflict` (6 tests: no-conflict no-change, chronological resolution order verified, non-tracker-note rejection without modification, nested-marker rejection, dangling-start-marker rejection, multiple-conflict-blocks success); `_try_auto_resolve_pr_conflict` (6 tests: no-action path, clean_merge path, non-TASKS.md abort path with merge-abort verification, tasks_md_resolved path with `RCX_SKIP_RECEIPT_CHECK=1` env verified in commit call, fetch-failure abort path, non-tracker-note TASKS.md abort path).
- `mu/tests/docs/test_growth_caps.py` — `CAP_TEST_FILES` 113→114 (+1 for new test file).

## Constraints (out of scope)

- Any auto-resolve for conflicts in files other than TASKS.md — non-TASKS.md conflicts intentionally fail-fast because code merges require judgment beyond mechanical chronological ordering.
- Any change to `_check_pr_conflict_state()` from PR #806 — kept unchanged, called by the new orchestrator.
- Any change to `_wait_for_required_checks_to_register` or `_poll_ci_checks_fallback` — orchestrator runs BEFORE them.
- Automatic rollback of the auto-resolve's push if CI fails after — if the merged branch still fails CI, the caller's responsibility to investigate; we don't auto-revert.
- Handling `mergeable: UNKNOWN` transient state — the existing PR #806 pre-check treats UNKNOWN as not-conflicting (correct behavior; don't fail on a transient race).

## Work items

1. Add the 5 helper functions in `commit_executor.py` immediately before `_poll_ci_checks_fallback`. Preserve docstrings explaining the contract and `RCX_SKIP_RECEIPT_CHECK=1` authorization.
2. Update Step 14 entry in `run_commit_pipeline` to call `_try_auto_resolve_pr_conflict` with the in-scope `base_branch` and `target_branch` parameters. On `resolved=False`, return the structured error with `failure_class: pr_conflicting` and the new `auto_resolve_action` diagnostic field.
3. Add 19-test regression file at `mu/tests/tools/test_commit_executor_step14_autoresolve.py`. Each private-attr call site uses `# ANTICHEAT_OK: <reason>` to pass the PR #805 AST linter.
4. Bump `CAP_TEST_FILES` 113→114 with wave-attribution comment.

## Stop conditions

- Any change to a file outside the 3-file scope → HALT, escalate.
- TASKS.md chronological resolver produces an output that is NOT text-equivalent to "origin lines then HEAD lines" for each block → HALT (would corrupt tracker notes).
- `_try_auto_resolve_pr_conflict` attempts to push something other than the current feature branch → HALT.
- Plan body > 100 lines → HALT, re-scope.

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_step14_autoresolve.py` passes with 19 test cases green.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_growth_caps.py` passes with 3 test cases green.
- `python3 -c "import ast; ast.parse(open('mu/tools/executors/commit_executor.py').read()); print('OK')"` exits 0.
- `python3 tools/checks/linters/check_private_attr_access.py` (PR #805 linter) exits 0 on tests/ tree.
- Behavior of `_check_pr_conflict_state` unchanged — orchestrator calls it first and short-circuits on `None` return.
- `RCX_SKIP_RECEIPT_CHECK=1` passed via env in the commit call — verified by the `test_tasks_md_only_conflict_resolves` regression test.
- Chronological invariant (origin block first, HEAD block second) verified by the `test_chronological_resolution_origin_first_head_second` regression test.

## Grounding / Authorization

- **Governing tracked packet:** this file. Sixth sibling narrow control-surface pipeline-hardening wave this session (after PRs #802/#803/#804/#805/#806).
- **`task_id` is a procedural Gate 8 anchor** — same pattern as PRs #802-#806 (see `memory/project_mechanization_index.md` "`task_id: [NEXT-CODEX-POST-REDTEAM]` as procedural Gate 8 anchor" entry).
- **Direct learning trigger:** `.claude/rules/learning.md` 2026-04-20 entry `commit_executor Step 14 waiting for CI PR CONFLICTING DIRTY mergeStateStatus pull_request workflow silent skip 300s 900s timeout doomed poll` — the "Structural fix candidate" note explicitly names this wave (full auto-merge) as the follow-on to PR #806's narrow fail-fast.
- **Founder autonomous directive 2026-04-20**: "after this wave, automatically do next valuable highest roi wave autonomously. If override needed give override." + explicit approval this turn ("sure, go ahead").
- **Founder persistence directive 2026-04-20** ("if it doesn't happen automatically, would suggest putting somewhere where new sessions know"): executed before this wave via `memory/project_mechanization_index.md` creation (documents opt-in mechanisms landed PRs #802-#806+).
- **`FOUNDER_OVERRIDE:step14-autoresolve-2026-04-20`** — wave-specific single-use token; 7th self-test of the `founder_override_token` mechanization landed in PR #803.
- **Lane: control-surface (pipeline hardening)**.
- **BOOTSTRAP_PHASE_B_EXCEPTION applies** — wave modifies `commit_executor.py` (the commit-stage executor itself), so bridge review cannot validate the change without self-dependency. Same precedent as PR #806 (`step14-autoconflict-resolve`) and PR #800 (`revert-convergence-budget-2026-04-19`).
- **Bootstrap classification: NOT bootstrap (substrate-wise).** Touches `commit_executor.py` + test file + growth caps. No substrate code.
