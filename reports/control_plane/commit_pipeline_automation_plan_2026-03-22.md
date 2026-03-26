<!-- DOC_STATUS: DESIGN_SPEC -->
<!-- DOC_ROLE: Plan packet for mechanical commit pipeline automation -->

# Commit Pipeline Automation Plan (Phase A Locked)

**Wave class:** L4_ENABLER
**Target gate:** G8
**Phase-A-Lock:** LOCKED
**Date:** 2026-03-22
**Sequencing:** Ships as part of EXECUTOR-SURFACES lane. Phase B implementer wave depends on this.

**Review history:** 6 rounds of 4 agents + 19 bridge rounds. Key milestones: R1 (4 agents: over-engineered → thin validator). R5 (supervisor stays with caller). R9 (founder-intent audit: zero recurring steps caller-memory-owned). R12 (dialectic: branch=ensure, hold=terminal, bot findings block). R16 (no resume, HOLD terminal — bridge GO). R18 (indicator after staging, no manufactured diff, force_add_files fixed — bridge GO). Phase A locked after outside-verifier confirmation.

---

## Problem Statement

Claude keeps forgetting commit closeout steps. commit_executor.py must own the full mechanical sequence as a state machine with idempotent ensure-steps. Same command every time. Script infers state. No caller memory.

---

## Design Principle (Founder Decision, R16)

**Maximum automation does NOT mean inventing a fragile resume path. It means:**
- Normal path (`COMMIT_GO`) is fully automated end-to-end
- Exceptional hold path (`COMMIT_GO_HOLD_PUSH`) stops explicitly — terminal for that invocation
- Re-entry happens through a fresh, honest invocation when there is actually new work to commit
- No fake "resume without new changes" — if there's nothing new, there's nothing to do

---

## MCP Probe Result (2026-03-22)

Claude Code subagents CAN call GitHub MCP tools (all 4 succeeded on PR #662). BUT commit_executor.py (Python script) CANNOT call MCP. Required path uses `gh` CLI. MCP is optional read/debug for Claude.

---

## Handoff Contract

```json
{
  "wave_id": "commit-pipeline-automation",
  "task_id": "[EXECUTOR-SURFACES]",
  "wave_class": "L4_ENABLER",
  "target_gate_id": "G8",
  "caller": "phase_b",
  "branch_prefix": "jabramsja",

  "tracker_note_text": "- Tracker sync note (2026-03-22, commit-pipeline-automation): ...",
  "fixes_implemented": ["precondition validator", "receipt-driven hold", "fail-closed verify"],
  "files_to_stage": ["mu/tools/executors/commit_executor.py", "TASKS.md"],
  "force_add_files": [],

  "commit_message": "feat: ...\n\nCo-Authored-By: ...",
  "pr_title": "feat: ...",
  "pr_body": "## Summary\n...",

  "base_branch": "dev",
  "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json"
}
```

**wave_id regex:** `^[a-z0-9][a-z0-9-]*[a-z0-9]$`

**`force_add_files`:** Only for PRE-EXISTING gitignored artifacts that must be committed. The indicator artifact is NOT included here — step 5 creates it and force-adds it independently. If no pre-existing gitignored artifacts need staging, this is an empty list.

**Removed from handoff:** `head_branch` (derived), `hold_push` (receipt-driven), `indicator_artifact_path` (script generates and stages at step 5), `supervisor_package_path` (script builds), `wave_name` (collapsed into wave_id).

---

## State Machine Pipeline (15 steps)

Every invocation runs the same pipeline. No resume mode. No special flags.

```
STEP  NAME                      WHAT THE SCRIPT DOES                              FAIL
----  ----                      ----------------                                  ----
1     validate_inputs           All handoff fields present + correct types         Error+stop
                                base_branch == "dev"
                                wave_id matches regex
                                Path traversal check on ALL path fields
                                force_add_files: DENY .git/, .env, .agent_bus/meta/*.db
                                files_to_stage non-empty
                                tracker_note_text non-empty
                                fixes_implemented is non-empty list of strings
                                Clear RCX_SKIP_* env vars for all subprocesses

2     ensure_feature_branch     Determine target: <branch_prefix>/<wave_id>        Error+stop
                                If on dev:
                                  Check local: fail if target branch exists
                                  Check remote: git ls-remote, fail if remote exists
                                  git checkout -b <prefix>/<wave_id>
                                If already on target branch:
                                  Continue (prior bot-fix re-invocation)
                                If on any other branch:
                                  Fail loudly

3     ensure_tracker_note       Check if TASKS.md already contains wave_id         Error+stop
                                If wave_id NOT in TASKS.md:
                                  Find last "^- Tracker sync note" in Ra section
                                  (between "## Ra" and next "---")
                                  Insert tracker_note_text AFTER that line
                                  Fail if "## Ra" not found
                                  Verify TASKS.md contains wave_id after write
                                If wave_id already in TASKS.md:
                                  Skip (already appended in prior invocation)
                                If wave_id appears multiple times:
                                  Fail (duplicate)

4     stage_files               git add <files_to_stage>                           Error+stop
                                git add -f <force_add_files>
                                Auto-add TASKS.md if modified in step 3
                                Do NOT auto-add indicator artifact (step 5 handles)
                                Verify: git diff --cached --name-only is non-empty
                                Fail if nothing staged (nothing to commit —
                                  this is the honest no-change-after-hold stop)

5     collect_and_stage_indicator                                                  Error+stop
                                python3 mu/tools/metrics/
                                  collect_l4_wave_indicators.py
                                  --wave-id <wave_id>
                                  --output reports/l4_wave_indicators/<wave_id>.json
                                Collector uses staged diff (no --range needed —
                                  step 4 already staged code files).
                                Verify exit 0 and file exists.
                                git add -f reports/l4_wave_indicators/<wave_id>.json
                                (indicator is now part of the staged set)

6     build_and_run_supervisor  Build 11-field package from handoff + git state:   Error+stop
                                  task_id, wave_name=wave_id, lane=caller,
                                  changed_files (git diff --cached --name-only),
                                  scope_items=files_to_stage,
                                  fixes_implemented (from handoff),
                                  deferred_items=[], bridge_status={},
                                  evidence_handles={indicator: <path>},
                                  blocker_report_paths (scan deferred/blocking/),
                                  current_judgment="COMMIT_GO"
                                Validate changed_files non-empty
                                Write to .scratch/auto_supervisor_package.json
                                Run: python3 mu/tools/agents/
                                  meta_bridge_supervisor.py --package <path> --json
                                Verify decision == COMMIT_GO or COMMIT_GO_HOLD_PUSH

7     validate_receipt          Verify Phase B handoff receipt exists at          Error+stop
                                 pre_commit_receipt_path and still authorizes
                                 commit continuity
                                Then read decision field from the fresh Step 6
                                 supervisor receipt JSON directly
                                (do NOT call verify_pre_commit_receipt() — see
                                 Receipt Truth section below)
                                Final supervisor decision must be COMMIT_GO or
                                 COMMIT_GO_HOLD_PUSH

8     run_pre_commit_script     bash mu/tools/hooks/pre-commit-doc-check           Error+stop
                                Explicit run (~5s). Hook re-runs at step 9.

9     git_commit                git commit -m <commit_message>                     Error+stop
                                Pre-commit hook runs automatically

10    hold_check                If receipt decision == COMMIT_GO_HOLD_PUSH:        Held+return
                                  Return {status: "held", commit_sha: <SHA>}
                                  Pipeline TERMINATES. Steps 11-15 do NOT run.
                                  This is an intentional terminal stop.
                                  Re-entry requires fresh invocation with
                                  new changes and fresh supervisor review.
                                If receipt decision == COMMIT_GO:
                                  Continue to step 11 (full pipeline)

11    run_pre_push_script       bash mu/tools/hooks/pre-push-fast                   Error+stop
                                Script-owned gate — not dependent on hook symlink

12    git_push                  git push -u origin <prefix>/<wave_id>              Error+stop
                                Pre-push hook runs (belt+suspenders)

13    ensure_pr                 Check for existing open PR:                         Error+stop
                                  gh pr list --head <prefix>/<wave_id> --base dev
                                  --state open --json number
                                If open PR exists: reuse + sync metadata
                                  gh pr edit <PR#> --title --body
                                If no open PR: create new
                                  gh pr create --base dev --head <prefix>/<wave_id>
                                  --title <pr_title> --body <pr_body>
                                If multiple open PRs: fail (ambiguous)
                                Validate PR number is numeric (isdigit)

14    wait_ci                   gh pr checks <PR#> --watch --required               Error+stop
                                600s timeout

15    ensure_review_clear       Query via gh api graphql:                           Stop/Error
      _and_merge                  reviewDecision on PR
                                  latestReviews (exclude bot)
                                  reviewThreads (all — human and bot)
                                Block if reviewDecision == CHANGES_REQUESTED
                                Block if any human review CHANGES_REQUESTED
                                Block if any unresolved human thread
                                Block if any UNRESOLVED bot thread:
                                  return {status: "bot_findings_pending",
                                    bot_findings: [...], pr_number: N}
                                  (Resolved threads do NOT block)
                                If review state is clear:
                                  bash mu/tools/hooks/merge_pr.sh <PR#> --sweep
                                  (merge_pr.sh handles only late-arriving/
                                   race-window bot threads that appeared
                                   between the query and the merge call.
                                   Step 15's query IS the real merge gate.
                                   merge_pr.sh is mechanical cleanup.)
                                  git checkout dev && git pull
                                  Verify HEAD SHA, clean working tree
                                  FAIL-CLOSED on verify failure
```

**15 steps. All script-owned. Same command every time. No resume mode.**

---

## Hold Semantics (explicit, bounded)

### COMMIT_GO — full pipeline
Steps 1-15 run end-to-end. No stopping. No bouncing back to supervisor between steps. Supervisor is a gate (step 6), not a per-step router.

### COMMIT_GO_HOLD_PUSH — terminal stop
Steps 1-9 run (through commit). Step 10 detects HOLD and returns:
```json
{
  "status": "held",
  "commit_sha": "abc123",
  "steps_completed": ["validate_inputs", ..., "git_commit", "hold_check"],
  "message": "Committed locally. Pipeline held before push per COMMIT_GO_HOLD_PUSH."
}
```
**Pipeline terminates.** Steps 11-15 do not run. This is intentional.

### After a hold — fresh invocation only
If the founder later wants to continue:
1. Make new changes (new changes are REQUIRED — no-change re-invocation fails at step 4)
2. Prepare a new handoff with updated content
3. Run `python3 mu/tools/executors/commit_executor.py --handoff <path> -v --json`
4. Fresh pipeline runs: new supervisor review, new receipt, new commit
5. `ensure_feature_branch` sees "already on target branch" → continues
6. `ensure_tracker_note` sees wave_id in TASKS.md → skips
7. `collect_indicator` re-collects (fresh evidence)
8. Normal pipeline proceeds through push/PR/CI/merge

**There is no "resume without new changes."** Mechanically enforced:
- Step 4 stages only code files from `files_to_stage` + auto-added TASKS.md
- Step 4 does NOT auto-stage the indicator artifact
- If `files_to_stage` contains only already-committed files, `git add` stages nothing new
- Step 4 fails: "nothing staged (nothing to commit)"
- Step 5 (indicator collection) never runs — pipeline stopped at step 4
- No fake diff is manufactured. The pipeline stops honestly.

---

## Receipt Truth (why verify_pre_commit_receipt() is not a resume oracle)

Current receipt schema (`meta_bridge_supervisor.py` lines 900-906):
```json
{"decision": "COMMIT_GO", "staged_sha": "<hash>", "timestamp_utc": "<iso>"}
```

`verify_pre_commit_receipt()` (`meta_bridge_supervisor.py` lines 915+) checks:
- `staged_sha` matches current staged state
- Receipt age < 1800 seconds (30 min)

**Post-commit, both checks are invalid:**
- `staged_sha` no longer matches (staging area is empty after commit)
- Age may exceed 30 minutes if founder held for a while

**Therefore:** Step 7 reads the receipt JSON directly for the `decision` field only. It does NOT call `verify_pre_commit_receipt()`. The pre-commit hook (step 9) calls `verify_pre_commit_receipt()` independently — that's fine because the hook runs DURING `git commit` when staging is still valid.

---

## Bot Findings Handling

When `ensure_review_clear_and_merge` finds unresolved bot threads:
```json
{
  "status": "bot_findings_pending",
  "bot_findings": [
    {"author": "chatgpt-codex-connector[bot]", "body": "P1: ...", "path": "file.py", "line": 42}
  ],
  "pr_number": "664",
  "steps_completed": ["validate_inputs", ..., "wait_ci"]
}
```

Caller reads `bot_findings`, fixes real issues, prepares new handoff:
- `tracker_note_text`: new note (ensure_tracker_note skips — wave_id already present)
- `fixes_implemented`: what was fixed
- `files_to_stage`: files changed by fix
- `force_add_files`: any new gitignored artifacts
- `commit_message`: fix commit message
- `pr_title` / `pr_body`: updated (ensure_pr syncs via `gh pr edit`)
- All structural fields unchanged

Same command: `python3 mu/tools/executors/commit_executor.py --handoff <path> -v --json`
Alternative (from dispatcher): `python3 mu/tools/executors/commit_executor.py --routing-record '<json>' -v --json`

Full pipeline runs. Ensure-steps handle state:
- `ensure_feature_branch` → already on target, continue
- `ensure_tracker_note` → wave_id present, skip
- `stage_files` → stages fix files (non-empty — new changes exist)
- `collect_and_stage_indicator` → collects from staged diff (fix files), force-adds artifact
- Supervisor, commit, push → fresh for the fix
- `ensure_pr` → reuses existing PR, syncs metadata
- `ensure_review_clear_and_merge` → re-queries threads, merges if clear

---

## Bug Fixes (from 4 rounds of 4 agents)

1. **Hold is receipt-driven** — `hold_push` removed from handoff. Receipt decision controls.
2. **Post-merge verify fail-closed** — error on failure, not success.
3. **TimeoutExpired handling** — inline at each except block.
4. **Env var sanitization** — clear RCX_SKIP_* at step 1.
5. **Dead code removal** — CommitExecutorError (never raised). `--routing-record` now accepted as an alternative entry path (prepares handoff from routing record internally).
6. **Path traversal** — component-level on ALL path fields.
7. **PR number validation** — isdigit().
8. **base_branch enforcement** — must be "dev".
9. **force_add_files denylist** — .git/, .env, .agent_bus/meta/*.db.

---

## Handoff Schema Migration

**`prepare_commit_handoff()` in `phase_b_executor.py` has been updated to the new 15-field schema** (wave_id, wave_class, target_gate_id, branch_prefix, tracker_note_text, fixes_implemented, files_to_stage, force_add_files, etc.). Old fields (staged_files, head_branch, hold_push, wave_name) removed.

**`commit_executor.py` now also accepts `--routing-record`** as an alternative to `--handoff`, but the route is intentionally decision-scoped. `prepare_handoff_from_routing_record()` may synthesize tracker-only handoffs for `UPDATE_TRACKER_ONLY`, while `COMMIT_GO` and `COMMIT_GO_HOLD_PUSH` still require a pre-prepared or valid embedded Phase B handoff so the exact receipt chain is preserved. This means dispatcher→commit is mechanically closed for tracker-only routes, but commit-capable routes remain fail-closed without the explicit Phase B handoff.

**`phase_b_executor.py` now accepts planless invocation** (omit `--plan`). When no plan is provided, Phase B derives bounded context from the routing record (requires wave_name, summary, next_candidates). Fails closed on under-specified records.

---

## Shared Module: executor_common.py

- `load_routing_record()` — 4 copies → 1 (canonical: executor_dispatch.py version with JSON decode + required-keys).

---

## What hooks own

| Gate | Hook | Runs during |
|------|------|-------------|
| Doc consistency, debt ceiling, receipt verify | pre-commit-doc-check | git commit (step 9) |
| Tracker sync, audit_fast, L4 contract | pre-push-fast | git push (step 12) |
| Late-arriving bot thread cleanup + merge | merge_pr.sh | Step 15 (after review gate clears) |

Step 8 runs pre-commit-doc-check explicitly. Step 11 runs pre-push-fast explicitly. Both are belt+suspenders with their hooks.

**merge_pr.sh boundary:** Within the pipeline, step 15 IS the merge gate. merge_pr.sh handles race-window bot threads that arrive between step 15's query and the merge call.

**Known limitation:** merge_pr.sh warns on human threads but does NOT block (returns 0). If a human thread arrives in the race window between step 15 and merge_pr.sh, merge_pr.sh will warn and merge anyway via `--admin`. This is a gap: step 15 gates human threads, but the race window is unprotected for human threads specifically.

**Fix (out of scope):** Making merge_pr.sh fail-closed on unresolved human threads requires a separate merge_pr.sh modification wave. The current plan acknowledges this limitation honestly rather than claiming full human-thread safety in the race window. The practical risk is low (human threads rarely arrive in the ~1s race window), but the gap is real.

Direct invocation of merge_pr.sh outside the pipeline bypasses step 15 entirely.

---

## Testing

Extend `mu/tests/tools/test_executor_dispatch.py`:

1. Missing tracker_note_text → error
2. Missing files_to_stage → error
3. Missing fixes_implemented → error
4. base_branch != "dev" → error
5. wave_id fails regex → error
6. Path traversal in any path field → error
7. force_add_files with .git/ path → error (denylist)
8. ensure_feature_branch: on dev → creates target
9. ensure_feature_branch: already on target → continues
10. ensure_feature_branch: on other branch → error
11. ensure_feature_branch: remote collision → error (create path only)
12. ensure_tracker_note: missing → appends after last in Ra
13. ensure_tracker_note: wave_id present → skips
14. ensure_tracker_note: duplicate → error
15. ensure_tracker_note: "## Ra" missing → error
16. stage_files: nothing to stage → error (no manufactured diff)
17. stage_files: auto-adds TASKS.md but NOT indicator (step 5 handles)
18. collect_and_stage_indicator: runs AFTER staging, uses staged diff (mock collector)
19. collect_and_stage_indicator: force-adds artifact to staging
20. Supervisor package built with correct 11 fields
21. changed_files empty → error before supervisor
22. Supervisor invoked with sanitized env
23. Receipt read directly (JSON parse, not verify_pre_commit_receipt)
24. Pre-commit script failure → error at step 8
25. COMMIT_GO → full pipeline (steps 11-15 run)
26. COMMIT_GO_HOLD_PUSH → held at step 10 (steps 11-15 NOT run, terminal)
27. Post-merge verify failure → error (not success)
28. TimeoutExpired → structured error
29. PR number non-numeric → error
30. ensure_pr: no PR → creates
31. ensure_pr: existing PR → reuses + syncs
32. ensure_pr: multiple PRs → error
33. ensure_review_clear: human CHANGES_REQUESTED → error
34. ensure_review_clear: unresolved human thread → error
35. ensure_review_clear: unresolved bot thread → bot_findings_pending
36. ensure_review_clear: resolved bot threads only → clear, merge proceeds
37. merge_pr.sh exit 1 → error
38. No-change-after-hold: already-committed files in files_to_stage → nothing staged → error at step 4
39. **Full pipeline integration test** — mock externals, COMMIT_GO, all 15 steps
40. **Bot-fix re-invocation test** — ensure_tracker_note skips, indicator re-collects from new staged diff, ensure_pr reuses, pipeline reaches merge

---

## Files Changed

| File | Change |
|------|--------|
| `mu/tools/executors/executor_common.py` | NEW: load_routing_record (canonical) |
| `mu/tools/executors/commit_executor.py` | Full 15-step state machine, all bug fixes, dead code removal |
| `mu/tools/executors/phase_b_executor.py` | Import from common. Update prepare_commit_handoff() to new schema. |
| `mu/tools/executors/phase_a_executor.py` | Import from common |
| `mu/tools/executors/executor_dispatch.py` | Import from common |
| `mu/tools/executors/dialectic_executor.py` | Import from common |
| `mu/tests/tools/test_executor_dispatch.py` | 40 new tests |
| `protocol_wave_execution.md` (memory) | Reduce commit section to "prepare handoff, invoke" |

---

## Deferred Items

| Finding | Source | Defer Reason |
|---------|-------|-------------|
| Receipt crypto/provenance | Adversary R1 | Needs HMAC/signing design |
| Receipt wave_id/branch binding | Adversary R15 | Not needed now that resume is removed |
| merge_pr.sh --admin flag | Structural R1 | Existing policy, separate script |
| Dispatcher commit_executor gap | Advisor R1 | Needs dispatcher redesign |
| Resume without new changes | Founder R16 | Intentionally excluded. If wanted, must be separate explicit future design. |

---

## Validation

```bash
PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q
python3 tools/checks/enforce_l4_execution_contract.py --files <changed files>
./tools/checks/check_docs_consistency.sh
```

---

## Memory/Docs Consequence

After implementation, `protocol_wave_execution.md` commit section reduces to:

```
### Commit Protocol
1. Prepare handoff JSON (judgment-dependent only)
2. python3 mu/tools/executors/commit_executor.py --handoff <path> -v --json
3. Script owns ALL 15 steps. No memory required.
4. COMMIT_GO = full pipeline. COMMIT_GO_HOLD_PUSH = terminal stop.
5. If bot_findings_pending: read, fix, re-invoke with new handoff.
6. If held: fresh invocation with new changes when ready.
```
