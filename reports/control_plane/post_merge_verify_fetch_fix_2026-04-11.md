# Post-Merge Verify Fetch Fix + Reasoning-Depth Hook Word-Boundary Fix

Date: 2026-04-11
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Phase-A-Lock: LOCKED
Task: [ANTI-DRIFT-ENFORCEMENT]
Wave ID: post-merge-verify-fetch-fix-2026-04-11

## 1. Scope

Two bounded, independently-testable items combined into one control-surface wave:

**Item A — commit_executor post-merge verify uses `git pull` where `git fetch` is safer**:
After `ensure_review_clear_and_merge` calls `merge_pr.sh`, `commit_executor.py:2509-2528` runs
`git pull` against `verify_root` (the post-merge verification worktree path) before asserting
`git rev-parse HEAD` + `git status --short` are clean. `git pull` is `fetch + merge` and has
side-effects on HEAD. Any local divergence in `verify_root` at that moment could produce a
merge commit or cause the pull to fail — both of which corrupt post-merge verification for a
step that is supposed to be read-only. The safer primitive for a verification step is
`git fetch origin <base_branch>`, which updates refs without touching HEAD, followed by
`git merge --ff-only origin/<base_branch>` to advance HEAD. The `--ff-only` flag
fail-closes on any local divergence — the correct behavior for a verification step.
`git reset --hard` is explicitly rejected because `_resolve_post_merge_verify_root()` can
return `repo_root` (lines 362, 370), making `reset --hard` a destructive state discard
on the main working tree rather than a fail-closed verification.

**Item B — `check-reasoning-depth.sh:167` HAS_RESTART regex false-positive**:
The Check 8 regex at `.claude/hooks/check-reasoning-depth.sh:167` reads:
`grep -iEc "(restart|re-dispatch|re-launch|retry the pipeline|clear stale state|restart from)"`.
The alternative `re-launch` is matched as a literal substring by ERE alternation with no word
boundaries. Any response text containing a hyphenated word whose tail 9 characters spell
`re-launch` triggers HAS_RESTART=1, and if HAS_DIAGNOSIS=0 the Stop hook blocks legitimate
prose. Documented in `.claude/rules/learning.md` 2026-04-11 HOOK entry
(fingerprint `check-reasoning-depth.sh Check 8 re-launch substring match ...`).
Recommended structural fix: wrap each alternative with portable character-class boundaries:
`(^|[^A-Za-z-])(restart|re-dispatch|re-launch|retry the pipeline|clear stale state|restart from)([^A-Za-z-]|$)`.

### Files in scope

- `mu/tools/executors/commit_executor.py` — change line 2511 (currently `_run(["git", "pull"], ...)`)
- `.claude/hooks/check-reasoning-depth.sh` — change line 167 (HAS_RESTART regex)
- `mu/tests/tools/test_executor_dispatch.py` — impacted dispatch test module; contains 9 `git pull` mock sites (lines 3750, 3932, 4272, 4395, 4502, 4646, 4757, 4951, 5107) and a `pull_cwds` tracking variable (line 5057) + assertion (line 5132) that must be updated to mock `git fetch` + ff-only merge instead of `git pull`
- `.claude/hooks/check-reasoning-depth.sh` — smoke-test verification via a deliberate input containing a hyphenated word whose tail 9 chars spell `re-launch`, asserting no block when HAS_DIAGNOSIS=0 for text that is not actually about restarting the pipeline

### Directories in scope

- `mu/tools/executors/` — commit_executor source
- `.claude/hooks/` — the reasoning-depth hook
- `mu/tests/tools/` — regression test

## 2. Work items

### Item A — commit_executor fetch fix

1. Read `commit_executor.py:2509-2528` in full to understand the surrounding control flow (the `try:`/`except subprocess.CalledProcessError` block).
2. Replace `_run(["git", "pull"], cwd=verify_root, timeout=60)` with a two-step sequence:
   - `_run(["git", "fetch", "origin", base_branch], cwd=verify_root, timeout=60)`
   - Followed by `_run(["git", "merge", "--ff-only", f"origin/{base_branch}"], cwd=verify_root, timeout=60)`. The `--ff-only` flag fail-closes on any local divergence. `git reset --hard` is rejected: `_resolve_post_merge_verify_root()` can return `repo_root` (line 362 or 370), so `reset --hard` would silently discard state in the main working tree instead of failing closed.
3. Verify the surrounding `rev-parse HEAD` + `status --short` assertions still hold after the change.

### Item B — check-reasoning-depth.sh regex fix

4. Read `.claude/hooks/check-reasoning-depth.sh:167` in context (lines 160-175) to understand Check 8's behavior and the HAS_RESTART + HAS_DIAGNOSIS paired logic.
5. Replace the HAS_RESTART regex with the character-class boundary form recommended in `.claude/rules/learning.md` 2026-04-11:
   `grep -iEc "(^|[^A-Za-z-])(restart|re-dispatch|re-launch|retry the pipeline|clear stale state|restart from)([^A-Za-z-]|$)"`
6. Verify BSD grep (macOS default) accepts the character-class expression — test with `echo "pre-launch verification" | grep -iEc ...` expecting 0 matches, and `echo "restart the pipeline" | grep -iEc ...` expecting 1 match.

### Item C — regression test

7. Update the 9 `git pull` mock sites in `mu/tests/tools/test_executor_dispatch.py` (lines 3750, 3932, 4272, 4395, 4502, 4646, 4757, 4951, 5107) to mock `git fetch` + `git merge --ff-only` instead of `git pull`. Update the `pull_cwds` tracking variable (line 5057) and assertion (line 5132) to verify `fetch` invocation instead.
8. Add a negative assertion: no subprocess call in the post-merge verify path should contain `["git", "pull"]`.
9. Run `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_receipt.py -q --tb=short` to confirm no regressions.

## 3. Constraints (what is NOT in scope)

- **NO changes to runtime directories** (`mu/host/`, `rcx_pi/`). This wave is L4_ENABLER (tooling) and must not touch runtime.
- **NO TASKS.md META-BRIDGE deletion**. Investigation showed no test dependencies on those Ra entries and no clear reason for removal; dropping from scope.
- **NO bundled fixes from the 2026-04-11 session handoff**. The block-protected-branch lexer sub-wave, learning store integration, TASKS.md:164 PIPELINE-RECOVERY item 5 correction, worktree pruning, and main-repo dirty file commits are all parallel open work — NOT in this wave.
- **NO other hook changes** beyond `check-reasoning-depth.sh:167`.
- **NO changes to `block-protected-branch.sh`** — that's the lexer sub-wave's scope.

## 4. Stop conditions

Stop when ALL of the following are true:

1. `commit_executor.py:2511` uses `git fetch` + `git merge --ff-only` in place of `git pull`. No `git reset --hard` anywhere in the post-merge verify path.
2. `check-reasoning-depth.sh:167` regex uses character-class word boundaries around every alternative.
3. Regression test in `mu/tests/tools/` asserts the fetch invocation (not pull) in the post-merge verify path.
4. `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_receipt.py -q --tb=short` — all tests pass.
5. `bash tools/pre-push-fast` — passes end-to-end.
6. L4 indicator artifact at `reports/l4_wave_indicators/post-merge-verify-fetch-fix-2026-04-11.json` is collected and non-empty.

## 5. Acceptance criteria

1. `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_receipt.py -q --tb=short` — all tests pass.
2. `./tools/checks/check_docs_consistency.sh` — clean.
3. `python3 tools/checks/enforce_l4_execution_contract.py --staged` — clean (FOUNDER_OVERRIDE required; see §6).
4. `bash .claude/hooks/check-reasoning-depth.sh` invoked on a stub input that contains a hyphenated word with tail 9 chars `re-launch` but no pipeline-restart prose — does NOT block.
5. `bash .claude/hooks/check-reasoning-depth.sh` invoked on a stub input that actually says "restart the pipeline" without a file:line citation — DOES block (the check still fires on real restart language).

## 6. Grounding / Authorization

- **Parent task:** `[ANTI-DRIFT-ENFORCEMENT]` (TASKS.md lines 153-156). Sub-wave inherits founder authorization. Does NOT mint its own task_id.
- **Founder authorization:** Authorized under `[ANTI-DRIFT-ENFORCEMENT]` parent task (TASKS.md:153-156). Governing packet: `reports/control_plane/post_merge_verify_fetch_fix_2026-04-11.md` (this file). Wave scope: Item A (fetch fix), Item B (hook regex fix).
- **Wave class:** L4_ENABLER (tooling / pipeline hardening; no runtime changes).
- **FOUNDER_OVERRIDE**: `FOUNDER_OVERRIDE:post-merge-verify-fetch-fix-2026-04-11` — required for non-structural-adjacency cap (this is the 6th consecutive L4_ENABLER wave after Ra entries at TASKS.md:101-106, all L4_ENABLER). Authorized under parent task `[ANTI-DRIFT-ENFORCEMENT]` (TASKS.md:153-156).
- **target_gate_id:** G8 (classification gate).
- **indicator_artifact_ref:** `reports/l4_wave_indicators/post-merge-verify-fetch-fix-2026-04-11.json`
- **indicator_collection_command:** `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id post-merge-verify-fetch-fix-2026-04-11 --output reports/l4_wave_indicators/post-merge-verify-fetch-fix-2026-04-11.json`
- **primary_blocker_class:** INTEGRATION
- **primary_invariant_id:** INV_STRUCTURAL_FORWARD_MOTION
- **bootstrap_endgame_policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **boot0_track_id:** V1
- **boot0_progress_state:** HOLD
- **evidence_command:** `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_receipt.py -q --tb=short && bash tools/pre-push-fast`
- **evidence_delta:** (1) `commit_executor.py:2511` no longer uses `git pull`; the post-merge verify step is read-only on HEAD. (2) `check-reasoning-depth.sh:167` regex uses character-class word boundaries; false-positive on hyphenated prose eliminated. (3) All 9 `git pull` mock sites in `mu/tests/tools/test_executor_dispatch.py` updated to mock `git fetch` + ff-only merge; `pull_cwds` assertion replaced with `fetch` verification.
- **progress_proof_before:** `commit_executor.py:2511` invokes `git pull`; `check-reasoning-depth.sh:167` has unbounded alternation; hook false-positives block legitimate prose; post-merge verify step has hidden HEAD side-effects.
- **progress_proof_after:** `commit_executor.py:2511` invokes `git fetch` (+ ff-only merge); `check-reasoning-depth.sh:167` regex has character-class boundaries; hook no longer false-positives on hyphenated words; post-merge verify step is read-only on HEAD until explicit ff-only merge.

## 7. Open questions / decision points

**Q1 — resolved**: `git fetch` + `git merge --ff-only` is the only acceptable replacement. `git reset --hard` is rejected because `_resolve_post_merge_verify_root()` returns `repo_root` when already on `base_branch` (line 362) or after `git checkout` (line 370), so `reset --hard` would authorize destructive state discard on the main working tree. `--ff-only` fail-closes on any divergence, which is the correct behavior for a verification step.

**Q2 — base_branch parameter name**: the current `ensure_review_clear_and_merge` function signature takes `base_branch` as an argument. The reviewer should confirm the exact name used in the surrounding scope at `commit_executor.py:2500-2530` to avoid a NameError.

**Q3 — resolved**: The impacted test module is `mu/tests/tools/test_executor_dispatch.py` (contains 9 `git pull` mock sites and existing `pull_cwds` tracking infrastructure). `test_commit_executor.py` does not exist; `test_commit_executor_receipt.py` has no `git pull` references.

## 8. References

- `TASKS.md:153-156`: `[ANTI-DRIFT-ENFORCEMENT]` parent task authorization (repo-tracked).
- `reports/control_plane/post_merge_verify_fetch_fix_2026-04-11.md`: governing packet (this file, repo-tracked).
- `.claude/rules/learning.md` 2026-04-11 HOOK entry: fingerprint `check-reasoning-depth.sh Check 8 re-launch substring match inside pre-launch false positive ...` — structural fix recommendation (option b, character-class boundaries).
- `mu/tests/tools/test_executor_dispatch.py`: impacted dispatch test module with 9 `git pull` mock sites (lines 3750, 3932, 4272, 4395, 4502, 4646, 4757, 4951, 5107) and `pull_cwds` tracking (lines 5057, 5132).
- Ra tracker notes at `TASKS.md:101-106`: prior 5 L4_ENABLER waves (establishes the adjacency override context).

## Instructions

1. Read the plan carefully.
2. Implement ALL specified changes.
3. Run only the Phase B-local validation commands listed in the plan.
4. Report your results.

## Constraints

- Do NOT modify files outside the plan's scope.
- Do NOT create new subsystems not described in the plan.
- Do NOT bypass any gates (--no-verify, etc.).
- Do NOT run commit/push governance commands from inside this Phase B implementer.
  Specifically: do NOT run `./tools/pre-push-fast`, `./tools/audit_fast.sh`,
  `./dev.sh`, `git push`, `gh pr`, or merge scripts as part of Phase B-local
  validation. Those belong to commit/pre-push execution, not the implementer.
- If the plan includes broader governance or closeout commands, treat them as
  executor/closeout-owned surfaces unless the plan explicitly says they are
  required as Phase B-local validation.
- If you encounter a blocker, report it — do not work around it.

## Wave Context

- wave_id: post-merge-verify-fetch-fix-2026-04-11
- repo_root: /private/tmp/workingrcx_fetch_fix_1775959299


## Required Output

Report your results as:
- List of files changed
- Validation command results
- Any issues encountered