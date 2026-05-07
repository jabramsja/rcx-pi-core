# Recovery Gate PR Conflicting

Date: 2026-04-20
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Phase-A-Lock: LOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: recovery-gate-pr-conflicting-2026-04-20
Authorization: `TASKS.md:226-238` (the active `[PIPELINE-RECOVERY]` block)
Governing packet (parent lane): `reports/control_plane/hybrid_recovery_agent_2026-04-16.md`

## Purpose

Integrate the `_try_auto_resolve_pr_conflict` helper (landed in PR #807,
currently at `mu/tools/executors/commit_executor.py:1783`) into
`mu/tools/executors/recovery_gate.py` as a new Tier-2
`FailureClass.PR_CONFLICTING` branch so any recovery path, not just the
`commit_executor` Step 14 call site, can classify a CONFLICTING/DIRTY PR
failure and invoke the already-landed auto-resolve recipe.

This slice adds a classifier predicate plus a fixer that reuses the existing
helper. It does not re-implement the CONFLICTING/DIRTY recipe, does not add a
new mutating subsystem, does not delegate to `phase_b_implementer`, and does
not invoke the 2026-04-16 non-bootstrap founder exception, because that
exception is bound to the hybrid-recovery wave's `delegate_implementer` branch
and its packet-bounded files.

## Scope

Files in scope for the Phase A plan and the Phase B implementation slice it
authorizes:

1. `mu/tools/executors/recovery_gate.py` — add a `FailureClass.PR_CONFLICTING`
   enum value, register it in `_TIER_MAP` as tier 2, add a classifier
   predicate that recognizes the signatures locked in Work Item A, and add
   a `fix_pr_conflicting` fixer that (a) fail-closes on a dirty worktree
   via a `git status --short` precondition (mirroring the guard
   `fix_pr_merge_conflict` already performs at `recovery_gate.py:1102-1115`,
   because the helper body at `commit_executor.py:1819-1948` does not check
   worktree cleanliness itself), (b) resolves both `base_branch` and
   `branch_name` via an explicit `gh pr view <pr_number> --json
   baseRefName,headRefName` call (distinct from the
   `baseRefName,mergeStateStatus` query `fix_pr_merge_conflict` issues at
   `recovery_gate.py:1119`, because this fixer needs the head ref to thread
   into `_try_auto_resolve_pr_conflict`'s required `branch_name` argument
   while that sibling does not), (c) proves the currently checked-out branch
   equals the resolved PR head branch before the helper can merge or push,
   (d) lazy-loads `commit_executor` via
   `_load_executor_module_from_repo` and delegates to the already-landed
   `_try_auto_resolve_pr_conflict` helper, (e) translates the helper's
   `resolved/action/detail` return into the recovery-gate
   `fixed/action/detail` `_fix_result` contract, and (f) is registered in
   `_TIER2_FIXES`.
2. `mu/tests/tools/test_recovery_gate.py` — add regression tests for
   classifier match (for each signature), classifier miss (unrelated error
   text, pytest failure, Tier 3 escalate envelope, and the adjacent
   `PR_MERGE_CONFLICT` signature), fixer invocation arguments, fixer
   return-value contract translation (`resolved=True` → `fixed=True` and
   `resolved=False` → `fixed=False`), the clean-worktree fail-closed
   precondition (dirty-worktree case), and the branch-context-missing case
   covering both a missing `baseRefName` and a missing `headRefName` in
   the `gh pr view` response.

`mu/tools/executors/commit_executor.py` is NOT in scope. Work Item D rules
out any module-level import of the helper; the on-demand loader pattern at
`recovery_gate.py:585-600` makes `commit_executor` callable at runtime
without touching its source.

No other files are in scope. Growth-cap configuration is not touched because
no new module file is created.

## Work Items

### A. Enumerate the CONFLICTING/DIRTY failure signatures the classifier must match

Phase A locks the complete signature set against the actual payload shape that
`commit_executor.py` emits today, not against a hypothesized reason-text
string. Current-code evidence:

- `mu/tools/executors/commit_executor.py:3358-3374` (the Step 14 wait_ci
  branch) returns a dict whose **top-level key** `failure_class` is the string
  `"pr_conflicting"`, and whose `errors[0]` text contains the substring
  `"CONFLICTING/DIRTY"`.
- Real-world callers of `commit_executor` wrap its return dict inside an outer
  envelope whose `stdout` field is the JSON-stringified inner payload. That
  wrapped form is the canonical shape the classifier is already written to
  handle: see the pre-existing wrapped-JSON tests at
  `mu/tests/tools/test_recovery_gate.py:377-392` (TRACKER_NOTE_CONTRACT,
  `{"status": "failed", "step": "commit_executor", "stdout":
  json.dumps(payload)}`) and `mu/tests/tools/test_recovery_gate.py:5008-5025`
  (NEEDS_PHASE_B — both the bare `stdout=json.dumps({"status":
  "needs_phase_b"})` form and the `executor: commit_executor` wrapper form).
  For this slice, the wrapped form is the primary real-world shape a Step 14
  failure takes on its way into `classify_failure`; the unwrapped top-level
  shape is a simpler edge case the predicate must also handle.
- `mu/tools/executors/recovery_gate.py:122-158` (`classify_failure`) already
  pre-parses `embedded_stdout = _parse_json_object(stdout)` and
  `embedded_stderr = _parse_json_object(stderr)` at lines 129-130 and uses
  them to derive `embedded_status`, `embedded_step`, and `embedded_reason`
  for existing classifiers (for example the NEEDS_PHASE_B branch at lines
  171-177 reads `embedded_status`). The classifier does **not** inspect the
  `failure_class` field — neither at the top level nor inside the embedded
  dicts — today.
- `mu/tools/executors/recovery_gate.py:5272-5300` (`_summarize_result_reason`)
  walks only `error/errors/stderr/detail/message/stdout/status/step`, so a
  payload that carries the CONFLICTING/DIRTY signal only on the
  `failure_class` key — at the top level OR on the embedded stdout/stderr
  dict — currently classifies as `FailureClass.UNKNOWN_ERROR`. Reproduced at
  Phase A review time with the reviewer's command: the wrapped payload
  `{"status": "failed", "step": "commit_executor", "stdout":
  json.dumps({"status": "error", "step": "wait_ci", "failure_class":
  "pr_conflicting", ...})}` returns `FailureClass.UNKNOWN_ERROR`, and so does
  the unwrapped top-level form with the same inner dict; both are the
  expected pre-slice baseline. The slice must classify **both** shapes as
  `FailureClass.PR_CONFLICTING`.

Given that evidence, Phase A locks the following signature set as the complete
match set for this slice (signatures are combined with logical OR):

1. **Field-aware, authoritative, candidate-walking:** the string
   `"pr_conflicting"` appears as the `failure_class` value on **any** of
   these three dicts — the top-level `result`, the embedded-stdout dict
   already computed at `recovery_gate.py:129` as
   `embedded_stdout = _parse_json_object(stdout)`, or the embedded-stderr
   dict computed at line 130 as
   `embedded_stderr = _parse_json_object(stderr)`. Concretely, the
   predicate evaluates as
   `result.get("failure_class") == "pr_conflicting" or
   embedded_stdout.get("failure_class") == "pr_conflicting" or
   embedded_stderr.get("failure_class") == "pr_conflicting"`. The
   candidate-walking form is required, not optional: the top-level-only
   variant would miss the wrapped shape that is the primary real-world
   carrier for a `commit_executor` Step 14 failure. This mirrors the
   pattern `_extract_result_pr_number` already uses at
   `recovery_gate.py:1079-1092` to extract `pr_number` across the same
   three-candidate list, and the NEEDS_PHASE_B predicate at
   `recovery_gate.py:171-177` which reads `embedded_status` alongside
   `status`. Text-based matching on a literal `"failure_class:
   pr_conflicting"` string does not match the emitted payload and is NOT a
   valid signature.
2. **Text-based, gh-CLI fallback:** the substring `"mergeable=CONFLICTING"`
   appears in any of `reason_text`, `combined_text`, or `stdout` (case-
   insensitive). This covers external callers that route raw `gh pr view`
   key=value output through `recovery_gate.classify_failure` without first
   normalizing into the `failure_class` field shape. This fallback does not
   match the Step 14 error text (which contains `"CONFLICTING/DIRTY"`
   slash-separated, not `"mergeable=CONFLICTING"` key=value), so it cannot
   collide with signature (1) on a Step 14 input.
3. **Text-based, gh-CLI fallback:** the substring `"mergeStateStatus=DIRTY"`
   appears in the same channels (case-insensitive). Same rationale as (2);
   same non-collision argument.

Signature #1 is mandatory; (2) and (3) are defense-in-depth for external
callers and do not replace (1). Any other signature is out of scope for this
slice; Phase A must not widen the list silently. If an additional signature
is discovered during Phase A agent review, it must be added to this Work
Item before Phase B starts.

Adjacency note: `FailureClass.PR_MERGE_CONFLICT` (already landed at
`recovery_gate.py:73`, classifier at `:183-188`, fixer
`fix_pr_merge_conflict` at `:1095`) matches a different upstream signature
(`merge_pr.sh failed` combined with `not mergeable | cannot be cleanly
created | merge conflict`). The two classes are deliberately distinct:
`PR_MERGE_CONFLICT` covers the `merge_pr.sh` path; `PR_CONFLICTING` covers
the Step 14 `wait_ci` pre-poll path added in PR #807. Work Item B must place
the new predicate so it does not intercept traffic that the pre-existing
`PR_MERGE_CONFLICT` predicate should still match.

### B. Add `FailureClass.PR_CONFLICTING` and classifier predicate

1. Add `PR_CONFLICTING = "pr_conflicting"` to the `FailureClass` enum at
   `mu/tools/executors/recovery_gate.py:57-83`, under the Tier 2 band alongside
   the existing `PR_MERGE_CONFLICT` (line 73). Map it to tier 2 in `_TIER_MAP`.
2. Add a classifier predicate in `classify_failure` (around line 122) that
   returns `FailureClass.PR_CONFLICTING` when, and only when, the input
   matches any of the three signatures locked in Work Item A:
   - the candidate-walking field check
     `result.get("failure_class") == "pr_conflicting" or
     embedded_stdout.get("failure_class") == "pr_conflicting" or
     embedded_stderr.get("failure_class") == "pr_conflicting"` (mandatory;
     uses the `embedded_stdout` and `embedded_stderr` dicts already
     computed at `recovery_gate.py:129-130`), OR
   - `"mergeable=conflicting"` appears in `reason_lower`, `combined_lower`,
     or the lower-cased `stdout`, OR
   - `"mergestatestatus=dirty"` appears in the same channels.
3. Place the new predicate **before** the existing `PR_MERGE_CONFLICT`
   predicate at line 183 so that a Step 14 wait_ci payload — whether routed
   through `classify_failure` in its unwrapped top-level form OR in the
   wrapped `{"status": "failed", "step": "commit_executor", "stdout":
   json.dumps(...)}` form — is classified `PR_CONFLICTING` rather than
   falling through. Neither shape carries `merge_pr.sh failed` text. The
   existing `PR_MERGE_CONFLICT` predicate's signature (`merge_pr.sh
   failed` + a merge phrase) cannot collide with any of the three
   signatures above, so this placement does not re-route existing
   `PR_MERGE_CONFLICT` traffic. Phase B must demonstrate this
   non-collision with a dedicated regression test (Work Item E.2).

### C. Add the `PR_CONFLICTING` fixer that delegates to the existing helper, translating contract keys

The helper and the Tier-2 caller speak different dict contracts. Phase A
locks the translation to prevent silent misclassification:

- Helper contract, from `mu/tools/executors/commit_executor.py:1800-1813`:
  `{"resolved": bool, "action": str, "detail": str}`, where `action` is one
  of `'no_action' | 'clean_merge' | 'tasks_md_resolved' | 'aborted'`.
- Recovery-gate Tier-2 contract, from
  `mu/tools/executors/recovery_gate.py:405-406` (`_fix_result`) and the
  Tier-2 plumbing at `:5915-5950`:
  `{"fixed": bool, "action": str, "detail": str}`. The dispatcher reads
  `fix_result.get("fixed")` for success, `fix_result.get("action")` for the
  recovery log action, and `fix_result.get("detail")` for the detail
  message. A raw helper dict passed through unchanged would record
  `fix_result.get("fixed") is None`, i.e. falsy, causing every successful
  auto-resolve to be logged as `outcome="failed"` and returned as
  `recovered=False`.

The fixer therefore must:

1. Add `fix_pr_conflicting(repo_root: Path, **kw: Any) -> dict[str, Any]` to
   `recovery_gate.py`, following the existing fixer pattern (for example
   `fix_pr_merge_conflict` at `:1095`). Extract `pr_number` with
   `_extract_result_pr_number(result)`; if missing, return
   `_fix_result(False, "missing_pr_number", "could not determine PR
   number")` without issuing any further subprocess calls.
2. **Fail-closed clean-worktree precondition.** Before any branch-context
   lookup or helper invocation, run `git status --short` with
   `cwd=repo_root`, `capture_output=True`, `timeout=30`, mirroring the
   guard in `fix_pr_merge_conflict` at `recovery_gate.py:1102-1115`:
   - on subprocess error or non-zero return, return
     `_fix_result(False, "status_failed", ...)`;
   - on non-empty stdout, return `_fix_result(False, "dirty_worktree",
     "worktree is not clean enough for auto-resolve")` **without invoking
     the helper and without issuing the `gh pr view` call in step 3**.

   This precondition is load-bearing. The helper body at
   `commit_executor.py:1819-1948` has no clean-worktree check of its own;
   it immediately runs `git fetch origin <base>`, `git merge
   origin/<base> --no-edit`, and on a TASKS.md-only conflict `git add
   TASKS.md`, `git commit --no-edit` (with `RCX_SKIP_RECEIPT_CHECK=1`), and
   `_push_branch(repo_root, branch_name)`. The existing Step 14 call site
   at `commit_executor.py:3348` is safe today only because the commit
   pipeline has just pushed the feature branch before reaching Step 14, so
   HEAD is implicitly clean at that call site. This slice explicitly
   widens the helper's reach to "any recovery path" (see `## Purpose`),
   which breaks that implicit invariant; the guard restores the
   fail-closed semantics that every other Tier-2 fixer already enforces.
3. Resolve `base_branch` **and** `branch_name` explicitly. The helper
   signature at `commit_executor.py:1783-1790` is
   `_try_auto_resolve_pr_conflict(repo_root, *, pr_number, base_branch,
   branch_name, log=None)` — both `base_branch` and `branch_name` are
   required keyword-only arguments. The Step 14 error envelope at
   `commit_executor.py:3358-3374` carries `pr_number`, `failure_class`,
   and `auto_resolve_action` as structured fields, but carries neither
   `base_branch` nor `branch_name` as structured fields (branch names
   appear only inside the human-readable `errors[0]` f-string at lines
   3362-3368 and MUST NOT be parsed back out of that text). Precedence:

   (a) **Structured-fields branch.** Walk the same candidate list the
       rest of the recovery gate uses — the top-level `result`, the
       embedded-stdout dict, and the embedded-stderr dict (mirroring
       `_extract_result_pr_number` at `recovery_gate.py:1079-1092`) —
       and for each of `base_branch` and `branch_name`, take the first
       non-empty string value found. If both names resolve to non-empty
       strings via this walk, use them as-is. Reserved for hypothetical
       future callers that structure these fields; the current Step 14
       caller at `commit_executor.py:3358-3374` does not populate them
       at any candidate level (neither on the top-level envelope nor on
       the embedded inner dict), so this branch is never taken for the
       Step 14 failure class in its current emitted shape.
   (b) **`gh pr view` branch.** Otherwise, issue a single subprocess call
       `gh pr view <pr_number> --json baseRefName,headRefName`
       (`cwd=repo_root`, `capture_output=True`, `timeout=30`), parse the
       JSON payload, and extract `baseRefName` and `headRefName`. Note:
       this query shape is intentionally distinct from the
       `baseRefName,mergeStateStatus` query `fix_pr_merge_conflict`
       issues at `recovery_gate.py:1119`; the sibling fixer does not need
       the head ref because it merges `origin/<base>` into the implicit
       HEAD and never calls `_push_branch(branch_name)`, while this fixer
       must thread `branch_name` into the helper's required argument.
   (c) On subprocess error, non-zero return code, or JSON parse failure,
       return `_fix_result(False, "pr_view_failed", ...)` **without
       invoking the helper**.
   (d) If `base_branch` (from `baseRefName`) or `branch_name` (from
       `headRefName`) is still empty after (a) and (b), return
       `_fix_result(False, "missing_branch_context", ...)` **without
       invoking the helper**.
4. **Checked-out-branch invariant.** Before invoking the helper, run
   `git rev-parse --abbrev-ref HEAD` with `cwd=repo_root`. If the command
   fails, returns non-zero, or produces an empty value, return
   `_fix_result(False, "current_branch_failed", ...)` without invoking the
   helper. If the current branch differs from resolved `branch_name`, return
   `_fix_result(False, "branch_mismatch", ...)` without invoking the helper.
   Detached `HEAD` is a mismatch. This guard is load-bearing because
   `_try_auto_resolve_pr_conflict` merges into implicit `HEAD` and then pushes
   `branch_name`; recovery must prove those names refer to the same checked-out
   branch before delegating.
5. Invoke `_try_auto_resolve_pr_conflict(repo_root, pr_number=<str>,
   base_branch=<str>, branch_name=<str>, log=None)` via the lazy loader
   defined in Work Item D, using the exact keyword-only signature at
   `commit_executor.py:1783-1790`.
6. Translate the helper's return into the `_fix_result` shape **explicitly**:
   `return _fix_result(fixed=helper["resolved"], action=helper["action"],
   detail=helper["detail"])`. Do NOT construct an ad-hoc dict; use
   `_fix_result` so the contract stays aligned with the rest of the Tier-2
   fixers.
6. The fixer must not mask helper failure. When `helper["resolved"] is False`
   (including the `action == "aborted"` case), the fixer propagates
   `fixed=False` together with the helper's `action`/`detail`, so the
   Tier-2 dispatcher logs `outcome="failed"` and returns `recovered=False`
   through `_make_result`. No auto-retry, no silent downgrade.
7. The fixer must not re-implement the CONFLICTING/DIRTY recipe. Its only
   **mutating** call is `_try_auto_resolve_pr_conflict`. The step-2 and
   step-3 subprocess calls (`git status --short` and `gh pr view ... --json
   baseRefName,headRefName`) are read-only preconditions — they do not
   touch refs, files, index state, or the remote. All fetch / merge / add
   / commit / push side-effects live inside the helper.
8. Register the fixer in `_TIER2_FIXES` at
   `mu/tools/executors/recovery_gate.py:1203-1209` as
   `FailureClass.PR_CONFLICTING: fix_pr_conflicting`.

### D. Use the existing on-demand executor loader; do NOT add a module-level import

Direct module-level import of `_try_auto_resolve_pr_conflict` from
`commit_executor` into `recovery_gate` is forbidden by the documented import
boundary, independent of whether a module-import cycle exists. Current-code
evidence:

- `mu/tools/executors/recovery_gate.py:4-6` states: *"Import constraints:
  stdlib + executor_common at module import time. The hybrid Tier 3
  implementer path lazy-loads phase_b_implementer at runtime."*
- `mu/tools/executors/commit_executor.py:75-93` performs module-level imports
  of `bridge_adapters` (line 81) and `tracker_sync_note` (line 91) via
  `sys.path` manipulation. A module-level import of `commit_executor` from
  `recovery_gate` would therefore transitively pull `bridge_adapters` and
  `tracker_sync_note` into recovery_gate's import-time closure, violating the
  `stdlib + executor_common` boundary documented in (the line above).
- `mu/tools/executors/recovery_gate.py:585-600` already provides the
  `_load_executor_module_from_repo(repo_root, module_name)` helper — the
  canonical on-demand loader for exactly this class of runtime dependency.
  This is the same pattern the hybrid Tier 3 branch uses to lazy-load
  `phase_b_implementer`.

Cycle absence is therefore NOT a sufficient safety criterion. Phase A locks
the import direction as follows:

1. The fixer function body (Work Item C) MUST invoke
   `commit_executor = _load_executor_module_from_repo(repo_root,
   "commit_executor")` inside the function body, then call
   `commit_executor._try_auto_resolve_pr_conflict(...)`. The import does not
   live at module scope.
2. `recovery_gate.py` MUST NOT add a module-level `from mu.tools.executors
   import commit_executor` or any equivalent that executes at import time.
3. `commit_executor.py` MUST NOT be edited in this slice to expose the
   helper via a new public surface. The helper is already module-level and
   accessible through the loaded module object. The `## Scope` entry for
   `commit_executor.py` is therefore **not used** and is removed below.
4. If a later reviewer demonstrates that the on-demand loader cannot satisfy
   the call (for example because `repo_root` is not available in the fixer's
   `kw` arguments), Phase B stops and spins a separate packet instead of
   adding a module-level import. Phase A does not widen the import boundary.

The fixer receives `repo_root` as its first positional argument (matching
the `_TIER2_FIXES` fixer signature visible at
`mu/tools/executors/recovery_gate.py:5917-5919`), so
`_load_executor_module_from_repo(repo_root, "commit_executor")` is
directly available without any additional plumbing.

### E. Regression tests

Add tests to `mu/tests/tools/test_recovery_gate.py` covering:

1. Classifier returns `FailureClass.PR_CONFLICTING` for each of the three
   signatures locked in Work Item A. Signature (1) has two sub-shapes that
   MUST both be tested — a grep-level only test of the unwrapped form would
   miss the wrapped form that is the primary real-world Step 14 carrier:
   - **Signature (1), unwrapped top-level shape:** the exact Step 14
     wait_ci payload taken directly from `commit_executor.py:3358-3374`
     (`{"status": "error", "step": "wait_ci", "errors": [...],
     "pr_number": "...", "failure_class": "pr_conflicting",
     "auto_resolve_action": ...}`).
   - **Signature (1), wrapped embedded-stdout shape:** the same inner
     payload JSON-stringified into the `stdout` field of an outer
     envelope, matching the canonical wrapper form already tested at
     `mu/tests/tools/test_recovery_gate.py:377-392` and 5008-5025 —
     `{"status": "failed", "step": "commit_executor", "stdout":
     json.dumps(step14_inner_payload)}` — and a parallel case that puts
     the same inner JSON on the `stderr` field rather than `stdout`, to
     prove the `embedded_stderr` branch of Signature (1) is also
     exercised. Both sub-cases must assert
     `FailureClass.PR_CONFLICTING`.
   - **Signature (2):** a payload whose `stdout` or `stderr` contains
     `mergeable=CONFLICTING` (case-insensitive) without any
     `failure_class` field at any candidate level.
   - **Signature (3):** a payload whose `stdout` or `stderr` contains
     `mergeStateStatus=DIRTY` (case-insensitive) without any
     `failure_class` field at any candidate level.
2. Classifier does NOT return `PR_CONFLICTING` for unrelated errors:
   - a normal pytest failure envelope;
   - a shell non-zero exit without any merge signature;
   - a Tier 3 escalate envelope (terminal-status payload);
   - **an existing `PR_MERGE_CONFLICT` payload** (i.e. `merge_pr.sh failed`
     + `not mergeable`), which MUST continue to classify as
     `PR_MERGE_CONFLICT` per the adjacency note in Work Item A.
3. Fixer lazy-loads `commit_executor` via `_load_executor_module_from_repo`
   (do not import it at test-module scope) and invokes
   `_try_auto_resolve_pr_conflict` with the expected `pr_number`,
   `base_branch`, and `branch_name`, using a monkeypatched helper spy
   rather than a live `gh`/`git` invocation.
4. Fixer **translates** a helper success return
   `{"resolved": True, "action": "clean_merge", "detail": "..."}` into a
   recovery-gate `{"fixed": True, "action": "clean_merge", "detail": "..."}`
   dict. Assert on the `fixed` key, not `resolved`. Also assert that the
   Tier-2 dispatcher path (exercising `recover_failure` end-to-end with the
   fixer in `_TIER2_FIXES`) returns `recovered=True` for this input.
5. Fixer translates a helper failure return
   `{"resolved": False, "action": "aborted", "detail": "..."}` into
   `{"fixed": False, "action": "aborted", "detail": "..."}` without
   masking, auto-retry, or silent downgrade. Assert the Tier-2 dispatcher
   returns `recovered=False` for this input.
6. Fixer returns `_fix_result(False, "dirty_worktree", ...)` when a
   monkeypatched `git status --short` produces non-empty stdout, without
   invoking `_try_auto_resolve_pr_conflict` and without issuing the
   `gh pr view` branch-context query. Assert the helper spy is never
   called, assert the `gh pr view` spy is never called, and assert the
   Tier-2 dispatcher (`recover_failure` path at
   `recovery_gate.py:5915-5950`) reports `recovered=False` for this input.
7. Fixer returns `_fix_result(False, "missing_branch_context", ...)`
   without invoking `_try_auto_resolve_pr_conflict` when the
   `gh pr view <pr_number> --json baseRefName,headRefName` call returns a
   payload whose `baseRefName` **or** `headRefName` is missing/empty.
   Cover both precedence branches from Work Item C.3:
   - (a) `result` carries no structured `base_branch`/`branch_name`
     fields AND the monkeypatched `gh pr view` returns a partial JSON
     payload (for example `{"baseRefName": "dev"}` with no
     `headRefName`);
   - (b) `result` carries structured `base_branch`/`branch_name` but one
     of them is an empty string.

   Use a monkeypatched `subprocess.run` spy for `gh pr view` so the test
   does not issue a live network call.
8. Step 14 auto-resolve behavior in `commit_executor.py` is not disturbed —
   since this slice does not edit `commit_executor.py`, the existing Step
   14 test (`test_clean_merge_then_push` and its siblings) continues to
   pass unchanged on the Phase B branch.
9. Fixer returns `_fix_result(False, "status_failed", ...)` when the
   monkeypatched `git status --short` subprocess raises or returns a
   non-zero exit code, **without** invoking
   `_try_auto_resolve_pr_conflict` and **without** issuing the
   `gh pr view` branch-context query. Assert the helper spy is never
   called, assert the `gh pr view` spy is never called, and assert the
   Tier-2 dispatcher (`recover_failure` path at
   `recovery_gate.py:5915-5950`) reports `recovered=False` for this
   input. Parameterize the test across at least the raise path
   (`subprocess.CalledProcessError`) and the non-zero-return path so
   both halves of Work Item C.2's first bullet are exercised.
10. Fixer returns `_fix_result(False, "pr_view_failed", ...)` when the
    monkeypatched `gh pr view <pr_number> --json baseRefName,headRefName`
    subprocess raises, returns a non-zero exit code, **or** returns
    stdout that fails `json.loads`, without invoking
    `_try_auto_resolve_pr_conflict`. Parameterize the test across all
    three failure modes listed in Work Item C.3(c). Assert the helper
    spy is never called and that the Tier-2 dispatcher reports
    `recovered=False` for each mode.
11. Module-scope boundary regression tests that back Acceptance
    Criterion 7.b:
    (a) An `ast`-based static check parses
        `mu/tools/executors/recovery_gate.py` and asserts: for every
        `ast.Call` whose callable name resolves to
        `_load_executor_module_from_repo` and whose argument list
        includes the string literal `"commit_executor"` (either
        positionally or via the `module_name=` keyword), the call has
        **some** ancestor `ast.FunctionDef` — i.e. the call is inside
        a function body, not at module scope. A match with no
        enclosing `FunctionDef` (i.e. the call is at module scope or
        inside an `if`/`try`/`with` at module scope) fails the test.
        The assertion must NOT require the enclosing function to be
        named `fix_pr_conflicting`: the baseline already contains a
        valid module-body lazy-load at
        `mu/tools/executors/recovery_gate.py:622` inside
        `fix_tracker_note_contract`, and a name-match assertion would
        therefore fail before this slice lands, forcing an unrelated
        scope change. The assertion must use `ast.walk` paired with a
        parent map, not string search, so a renamed identifier or a
        multi-line call expression cannot evade detection.
    (b) A behavioral subprocess check invokes
        `subprocess.check_call([sys.executable, "-c", "import
        mu.tools.executors.recovery_gate, sys; sys.exit(0 if
        ('commit_executor' not in sys.modules and
        'mu.tools.executors.commit_executor' not in sys.modules) else
        1)"])` from inside the test. The test fails if the subprocess
        exits non-zero. Both keys must be checked because the
        existing on-demand loader at
        `mu/tools/executors/recovery_gate.py:585-600` calls
        `importlib.import_module("commit_executor")` which registers
        the **bare** `"commit_executor"` key in `sys.modules`, while
        a hypothetical module-level `from mu.tools.executors import
        commit_executor` would register the fully-qualified
        `"mu.tools.executors.commit_executor"` key. Checking only the
        fully-qualified key would false-pass the exact import-time
        lazy-load path this test is meant to guard against. This
        catches any module-import-time path — including a future
        refactor that uses a name other than
        `_load_executor_module_from_repo` — that would transitively
        pull `commit_executor` into `recovery_gate`'s import-time
        closure.

### F. Phase A deliverable

Phase A converges on a written plan (this packet) that:

1. Locks the three signatures in Work Item A as the complete match set,
   grounded against the actual payload shape that `commit_executor.py:3358-
   3374` emits today and the wrapped-envelope form in which that payload
   reaches `classify_failure` via outer callers (as established by the
   pre-existing wrapped-JSON tests at
   `mu/tests/tools/test_recovery_gate.py:377-392` and 5008-5025). The
   locked Signature #1 walks the same three-candidate list
   (`result`, `embedded_stdout`, `embedded_stderr`) the classifier already
   uses at `recovery_gate.py:129-130` so both the unwrapped top-level and
   the wrapped embedded-stdout/stderr shapes match.
2. Locks the import direction per Work Item D: the fixer lazy-loads
   `commit_executor` via `_load_executor_module_from_repo` from inside the
   function body; no module-level import is added; `commit_executor.py` is
   not edited.
3. Locks the contract translation per Work Item C: the fixer maps
   `helper["resolved"]` → `_fix_result.fixed`, not a raw passthrough.
4. Locks the fail-closed preconditions per Work Item C steps 2-3: before
   any helper invocation, the fixer performs a `git status --short`
   clean-worktree guard and an explicit `gh pr view <pr_number> --json
   baseRefName,headRefName` branch-context lookup. A dirty worktree, a
   missing `pr_number`, or a missing `baseRefName` / `headRefName` each
   cause the fixer to return a `_fix_result(False, ...)` envelope
   without calling `_try_auto_resolve_pr_conflict`.
5. Confirms no change to Step 14 semantics and no new delegation surface.
6. Leaves implementation, test authoring, and bridge-backed review to Phase B.

## Constraints (what is NOT in scope)

1. Do not widen into the hybrid `delegate_implementer` branch or any surface
   described by the governing packet
   `reports/control_plane/hybrid_recovery_agent_2026-04-16.md`. This slice
   reuses an already-landed intra-package helper; it does not delegate to
   `phase_b_implementer` and therefore does not invoke or extend the
   2026-04-16 founder non-bootstrap exception.
2. Do not add a new code-writing or review subsystem. Reuse
   `_try_auto_resolve_pr_conflict` as the sole mutating actor for this
   failure class.
3. Do not edit `commit_executor.py` at all in this slice. Work Item D
   establishes the on-demand executor loader as the required call path,
   which makes any edit to `commit_executor.py` unnecessary and out of
   scope. Step 14 semantics are therefore preserved by construction.
4. Do not modify runtime / substrate files (`mu/host/`, `rcx_pi/`, seeds, or
   JS parity surfaces). This slice is control-surface only.
5. Do not modify adapter / bridge / implementer bootstrap infrastructure
   (`mu/tools/executors/phase_b_implementer.py`,
   `.agent_bus/bridge_config.json`, or bridge adapter loading / selection).
   Those surfaces remain outside this slice.
6. Do not bypass commit / push gates. Use `commit_executor.py` for the full
   commit-through-merge pipeline; do not invoke `git push --no-verify` outside
   the bounded executor path.
7. Do not treat a classifier match as proof of fix success. The fixer's return
   value, derived from the helper's actual outcome, is authoritative.
8. Do not add signatures to the classifier beyond those locked in Work Item A
   without updating this packet first.
9. Do not modify dispatcher semantics outside `recovery_gate.py`; if a
   dispatcher change is discovered to be required, stop and spin a separate
   packet rather than widening this slice silently.
10. Do not edit the packet-owned validator module
    `mu/tests/tools/test_recovery_gate.py` in a way that weakens the
    classifier-miss or fixer-failure-propagation assertions; new tests must be
    additive.

## Stop Conditions

1. Tier-2 recovery-gate classification routes a failure through
   `FailureClass.PR_CONFLICTING` only when the input matches one of the three
   signatures locked in Work Item A; every other input keeps its existing
   classification, including the adjacent `PR_MERGE_CONFLICT` path.
2. The fixer's only **mutating** call is `_try_auto_resolve_pr_conflict`.
   Read-only preconditions (`git status --short` for the clean-worktree
   guard, `gh pr view <pr_number> --json baseRefName,headRefName` for
   branch context) do not touch refs, files, index state, or the remote.
   The helper invocation is gated on the clean-worktree guard: if
   `git status --short` produces any stdout, the fixer returns
   `_fix_result(False, "dirty_worktree", ...)` and the helper is never
   called. Translating the helper's return into a `_fix_result(fixed=...,
   action=..., detail=...)` dict is the only post-helper transformation;
   the CONFLICTING/DIRTY recipe is not re-implemented inside
   `recovery_gate.py`.
3. `recovery_gate.py` imports no new module at module scope. The call into
   `commit_executor._try_auto_resolve_pr_conflict` is made via
   `_load_executor_module_from_repo(repo_root, "commit_executor")` from
   within the fixer body. The existing `stdlib + executor_common` import-
   time boundary documented at `recovery_gate.py:4-6` is preserved.
4. Step 14 auto-resolve in `commit_executor.py` retains identical semantics
   by construction — this slice does not edit `commit_executor.py`. The
   existing Step 14 test suite continues to pass without modification.
5. The fixer's return dict maps `helper["resolved"]` to `_fix_result.fixed`;
   a successful auto-resolve is recorded by the Tier-2 dispatcher at
   `recovery_gate.py:5915-5950` as `outcome="success"` and surfaced as
   `recovered=True`.
6. Regression tests added under Work Item E pass locally via
   `./tools/pre-push-fast` on the Phase B branch.
7. If any Work Item cannot be satisfied inside the in-scope files listed in
   `## Scope`, Phase B stops and spins a separate packet rather than widening
   silently.

## Acceptance Criteria

1. `mu/tests/tools/test_recovery_gate.py` proves `FailureClass.PR_CONFLICTING`
   is returned by the classifier for each of the three signatures locked in
   Work Item A. Signature (1) has two sub-shapes that must both be asserted
   (the packet cannot ship with the wrapped form left to Phase B's
   discretion):
   - **Signature (1) unwrapped:** a Step 14 wait_ci payload at top level
     with `"failure_class": "pr_conflicting"` (shape taken directly from
     `commit_executor.py:3358-3374`);
   - **Signature (1) wrapped:** the same Step 14 inner payload
     JSON-stringified into an outer envelope's `stdout` field
     (`{"status": "failed", "step": "commit_executor", "stdout":
     json.dumps(step14_inner_payload)}`, mirroring the wrapper form
     already tested at `mu/tests/tools/test_recovery_gate.py:377-392`
     and 5008-5025), plus a parallel case with the same inner JSON on
     `stderr` instead of `stdout` so the `embedded_stderr` branch of
     Signature (1) is also exercised;
   - **Signature (2):** a payload containing `mergeable=CONFLICTING` in
     stdout/stderr without any `failure_class` field at any candidate
     level;
   - **Signature (3):** a payload containing `mergeStateStatus=DIRTY` in
     stdout/stderr without any `failure_class` field at any candidate
     level.
   The classifier returns a different class (or `UNKNOWN_ERROR`) for the
   four negative cases listed in Work Item E.2, including the adjacent
   `PR_MERGE_CONFLICT` signature which must still classify as
   `PR_MERGE_CONFLICT`.
2. `mu/tests/tools/test_recovery_gate.py` proves the fixer invokes
   `_try_auto_resolve_pr_conflict` with the expected `pr_number`,
   `base_branch`, and `branch_name` arguments derived from the classified-
   input payload, using a monkeypatched helper spy rather than a live
   `gh`/`git` invocation. The test also proves the fixer obtains the helper
   via `_load_executor_module_from_repo` (not via a module-scope import).
3. `mu/tests/tools/test_recovery_gate.py` proves the fixer translates a
   helper success return (`resolved=True, action, detail`) into a
   `_fix_result` dict with `fixed=True` and the same `action`/`detail`,
   and that the Tier-2 dispatcher (`recover_failure` path at
   `recovery_gate.py:5915-5950`) reports `recovered=True` for this input.
4. `mu/tests/tools/test_recovery_gate.py` proves the fixer translates a
   helper failure return (`resolved=False, action, detail`) into a
   `_fix_result` dict with `fixed=False` and the same `action`/`detail`
   without masking, auto-retry, or silent downgrade, and that the Tier-2
   dispatcher reports `recovered=False` for this input.
5. `mu/tests/tools/test_recovery_gate.py` proves the fixer's fail-closed
   preconditions, **asserting in each sub-case that the monkeypatched
   `_try_auto_resolve_pr_conflict` spy is never called**. All five
   precondition-failure branches declared in Work Item C must be
   covered; listing only a subset would let Phase B silently drop the
   ones the packet did not name:
   (a) `_fix_result(False, "missing_pr_number", ...)` when `pr_number` is
       absent from the classifier input (Work Item C.1);
   (b) `_fix_result(False, "status_failed", ...)` when the
       monkeypatched `git status --short` subprocess raises (for
       example `subprocess.CalledProcessError`, `TimeoutExpired`, or
       `FileNotFoundError`) or returns a non-zero exit code, per Work
       Item C.2 first bullet. The test must also assert the
       `gh pr view` spy is never called in this branch (the guard
       short-circuits before step 3) and that the Tier-2 dispatcher
       (`recover_failure` path at `recovery_gate.py:5915-5950`) reports
       `recovered=False` for this input;
   (c) `_fix_result(False, "dirty_worktree", ...)` when `git status
       --short` returns zero with non-empty stdout, per Work Item C.2
       second bullet. The guard lives in the fixer, mirroring the one
       `fix_pr_merge_conflict` performs at `recovery_gate.py:1102-1115`;
       the helper body at `commit_executor.py:1819-1948` does not
       perform this check itself, so widening the helper's reach
       beyond the Step 14 call site into "any recovery path" (per
       `## Purpose`) requires this explicit precondition. The test
       must also assert the `gh pr view` spy is never called in this
       branch (the guard short-circuits before step 3);
   (d) `_fix_result(False, "pr_view_failed", ...)` when the
       monkeypatched `gh pr view <pr_number> --json baseRefName,
       headRefName` subprocess raises or returns a non-zero exit code,
       **or** returns stdout that fails `json.loads`, per Work Item
       C.3(c). The test must assert the Tier-2 dispatcher reports
       `recovered=False` for this input;
   (e) `_fix_result(False, "missing_branch_context", ...)` when the
       `gh pr view <pr_number> --json baseRefName,headRefName` call
       succeeds (exit zero, parseable JSON) but returns a payload
       whose `baseRefName` or `headRefName` is missing or empty,
       covering both precedence branches from Work Item C.3(d). This
       sub-case is distinct from (d): (d) fails the view-call itself;
       (e) passes the view-call and fails on its content.
6. `mu/tools/executors/commit_executor.py` Step 14 behavior is unchanged
   because this slice does not edit `commit_executor.py`. The existing Step
   14 auto-resolve test (baseline: `test_clean_merge_then_push` updated by
   `da0f5829 test: update test_clean_merge_then_push expected argv for
   --no-verify`) continues to pass unchanged on the Phase B branch.
7. `mu/tools/executors/recovery_gate.py` adds no new module-level
   import AND no module-scope runtime call that loads `commit_executor`
   at import time. Two independent proofs are required because a
   module-scope assignment of the form `_X =
   _load_executor_module_from_repo(repo_root, "commit_executor")`
   executes at import time, still violates the `stdlib +
   executor_common` boundary documented at `recovery_gate.py:4-6`, yet
   does not match an `^(import|from)` line and would false-pass a
   grep-only check:
   (a) `grep -E "^(import|from)" mu/tools/executors/recovery_gate.py`
       on the Phase B branch yields the same set of imports as on the
       base branch (plus/minus only stdlib adjustments, if any), with
       no new `commit_executor` reference at module scope.
   (b) The regression test declared in Work Item E.11 (i) parses
       `mu/tools/executors/recovery_gate.py` with `ast` and asserts
       that every `ast.Call` whose callable name is
       `_load_executor_module_from_repo` and whose argument tuple
       includes the string literal `"commit_executor"` (positionally
       or via the `module_name=` keyword) has **some** ancestor
       `ast.FunctionDef` — i.e. no such call exists at module scope.
       The enclosing function is NOT required to be named
       `fix_pr_conflicting`, because the baseline already contains a
       valid module-body lazy-load at `recovery_gate.py:622` inside
       `fix_tracker_note_contract`; a name-match assertion would
       fail before this slice lands. (ii) Spawns a fresh `python -c`
       subprocess that runs `import mu.tools.executors.recovery_gate`
       in a clean interpreter and asserts that **both**
       `"commit_executor"` (the bare key the on-demand loader at
       `recovery_gate.py:585-600` registers via
       `importlib.import_module("commit_executor")`) **and**
       `"mu.tools.executors.commit_executor"` (the fully-qualified
       key a hypothetical module-level `from mu.tools.executors
       import commit_executor` would register) are NOT in
       `sys.modules` afterwards. Checking only the fully-qualified
       key would false-pass a module-scope call to
       `_load_executor_module_from_repo(repo_root,
       "commit_executor")` — the exact import-time path this
       regression test is meant to guard against. The subprocess
       check catches any future refactor that routes the import-time
       load through a name other than
       `_load_executor_module_from_repo`.
8. Pre-push-fast (`./tools/pre-push-fast`) passes on the Phase B branch
   before any commit is pushed.
9. No file outside `## Scope` is modified by the Phase B slice, and no
   growth cap is updated (because no new module file is created).

## Grounding / Authorization

1. `TASKS.md:226-238` is the active parent authorization for the
   `[PIPELINE-RECOVERY]` control-surface lane. It lists
   `mu/docs/agents/PipelineRecovery.v0.md` as the design anchor and
   `mu/tools/executors/recovery_gate.py` as the file anchor, which are exactly
   the surfaces this slice extends. That block marks `[PIPELINE-RECOVERY]` as
   **IN PROGRESS** since 2026-03-31 under founder authorization.
2. `TASKS.md:237` lists the currently-tracked packet for the
   `[PIPELINE-RECOVERY]` lane as
   `reports/control_plane/hybrid_recovery_agent_2026-04-16.md`. This 2026-04-20
   PR_CONFLICTING integration is a separate, narrower follow-up slice under
   the same parent `[PIPELINE-RECOVERY]` authorization; it does not replace,
   extend, or invoke the governing packet's `delegate_implementer` branch.
3. `TASKS.md:236` records the explicit 2026-04-16 founder non-bootstrap
   exception, which authorizes hybrid-recovery Tier 3 reuse of
   `phase_b_implementer` bounded to "the exact packet-bounded files" listed
   in the governing packet's `## Scope`. This slice does NOT delegate to
   `phase_b_implementer` and therefore does not invoke or widen that
   exception; its bootstrap posture is the pre-exception baseline for
   non-delegating recovery-gate additions.
4. The helper this slice integrates (`_try_auto_resolve_pr_conflict`) was
   landed in PR #807. Current-code-truth evidence comes from the recent
   branch history at session start: `97570b97 feat: commit_executor Step 14
   auto-resolve CONFLICTING/DIRTY PRs` and `ac77bdc2 Merge pull request #807
   from jabramsja/jabramsja/step14-autoresolve-2026-04-20`. At Phase A
   review time the helper's definition is at `commit_executor.py:1783` and
   its Step 14 call site is at `commit_executor.py:3348`. Phase B must
   re-read both regions before landing the fixer, in case later patches
   (for example `da0f5829 test: update test_clean_merge_then_push expected
   argv for --no-verify` or `461e1edb fix: address bot review findings
   (round 1)`) moved, renamed, or changed the helper's signature. The
   grounded signature at review time is `_try_auto_resolve_pr_conflict(
   repo_root, *, pr_number, base_branch, branch_name, log=None) ->
   dict[str, Any]` returning `{"resolved": bool, "action": str,
   "detail": str}`.
5. This packet does not claim authority over any file outside `## Scope`. Any
   scope widening discovered during Phase A agent review or Phase B
   implementation must stop work and spin a separate packet rather than
   silently expanding this slice.

## Validation

Packet-draft validation for the Phase A plan itself (not the hybrid runtime
`validation_spec` allowlist from the governing packet):

- `./tools/checks/check_docs_consistency.sh`

Implementation-wave validation (pre-push-fast plus the new regression tests
in `mu/tests/tools/test_recovery_gate.py`) is deferred to Phase B, gated by
Phase A convergence on Work Items A and D.
