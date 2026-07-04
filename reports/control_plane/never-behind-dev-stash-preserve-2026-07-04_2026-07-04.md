# Make commit_executor Step 15b deterministically sync a clean-ancestor primary to dev by stash-preserving tracked WIP instead of skipping

Date: 2026-07-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: never-behind-dev-stash-preserve-2026-07-04
Phase-A-Lock: LOCKED
Purpose: FOUNDER TOP PRIORITY (emphatic, asked repeatedly 2026-07-04): the primary working repo must be PERMANENTLY, AUTOMATICALLY never-behind-dev, IN THE PIPELINE so it works for ANY orchestrator (claude OR codex). VERIFIED ROOT CAUSE 2026-07-04: the founder primary (WorkingRCX) is 147 behind origin/dev, 0-ahead, HEAD is a clean ANCESTOR of origin/dev (a pure fast-forward IS possible), with 22 tracked-dirty files. commit_executor Step 15b _sync_primary_worktree_to_base runs post-merge on every wave and ALREADY HAS stash-preserve machinery (_stash_primary_sync_tracked_wip / _resolve_primary_sync_stash_record / _restore_primary_sync_tracked_wip), yet the primary stays behind -- the GUARD-B / decision logic does NOT complete the stash->ff->restore for the clean-ancestor-with-tracked-WIP case (it skips + writes a behind_dev signal instead of syncing). So the behind-count rises every time dev advances. FIX belongs in commit_executor (auto-runs on every merge, orchestrator-agnostic), NOT a claude-only skill/memory.

## Scope

mu/tools/executors/commit_executor.py (_sync_primary_worktree_to_base, Step 15b) + a hermetic regression in mu/tests/tools/test_commit_executor_post_merge_cleanup.py. Make a clean-ancestor primary with tracked WIP deterministically stash-preserve -> git merge --ff-only origin/base -> restore, instead of skipping. No runtime/substrate files; L4_ENABLER.

Files and surfaces in scope:

- TASKS.md -- tracker-sync authority. The 2026-07-04 tracker sync note for wave `never-behind-dev-stash-preserve-2026-07-04` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/never-behind-dev-stash-preserve-2026-07-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Rewire the clean-ancestor + tracked-WIP branch of `_sync_primary_worktree_to_base` (Step 15b) -- the branch currently guarded by non-empty `dirty_paths` that writes a `dirty_primary_worktree` behind_dev signal and returns a skip. After GUARD-C has proven the primary HEAD is an ancestor of `origin/{base_branch}` and the SHAs differ, when the ONLY obstacle is tracked dirty WIP: isolate that WIP with the existing `_stash_primary_sync_tracked_wip`, run the existing `git merge --ff-only --no-overwrite-ignore origin/{base_branch}`, then restore with `_restore_primary_sync_tracked_wip` (fail-closed on stash drift) and clear the behind_dev signal.
2. Enforce WIP-safety ordering in the new branch: stash ONLY tracked WIP (`_dirty_worktree_paths` already excludes ignored via `ls-files --others --exclude-standard`, and `--no-overwrite-ignore` guards ignored files). If the stash step fails, do NOT fast-forward -- keep WIP in place and fall back to the existing skip + behind_dev. If the ff fails after stashing, restore WIP before returning. If restore reports drift/conflict, surface the error and skip. Founder WIP is never lost or overwritten.
3. Preserve the outcome-dict observability contract: the new success path sets `synced=True`, `skipped=False`, `reason=None`, records `old_sha`/`new_sha`/`primary`, and clears the behind_dev signal; every preserved-skip path keeps `skipped=True` with a precise `reason`. The outer fail-open contract (never raise into the pipeline) is unchanged.
4. Add a hermetic regression to `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` that builds a real temp git repo whose primary worktree is a clean ancestor of `origin/{base_branch}` with tracked dirty WIP, drives the public `sync_primary_worktree_to_base` seam, and asserts: HEAD fast-forwarded to `origin/{base_branch}`; tracked WIP preserved post-restore; `synced=True`/`skipped=False`; behind_dev signal cleared; untracked/ignored files untouched.

## Constraints

- L4_ENABLER: MUST NOT touch runtime/substrate dirs (`mu/host/python/rcx_pi/selfhost/`, `mu/host/js/`, `tests/l4_gates/`) or add host semantics. No L3-parity surface is touched; no runtime/substrate change.
- Do NOT alter GUARD-A/C/D semantics: base-branch checkouts still skip; non-ancestor / divergent-local-commits still skip + write behind_dev (founder lands those via a PR); sync-lock contention still skips. ONLY the clean-ancestor + tracked-dirty path changes behavior.
- PULL-ONLY: never push, checkout base, force, or reset. The ff only brings `origin/{base_branch}` down into the primary's current feature branch.
- Never stash/restore/`git add`/discard untracked or ignored founder WIP; preservation is via the executor-owned stash for TRACKED paths only.
- Orchestrator-agnostic: no dependence on which LLM/orchestrator ran the wave; no `set_roles` / orchestrator-mode changes. The fix lives in commit_executor so it runs post-merge for claude OR codex.
- Packet L4 fields derive from the 2026-07-04 tracker-sync note; do NOT hand-edit TASKS.md L4 fields outside tracker-sync authority.

## Stop conditions

- If a pure fast-forward is NOT possible (HEAD not an ancestor of `origin/{base_branch}`), STOP the ff path -- that is the divergent-commits case and MUST remain skip + behind_dev, never force.
- If tracked WIP cannot be safely isolated or restored (stash creation failed, pop/apply conflict, stash-oid drift), STOP: preserve WIP in place, skip, and surface the error. Never lose or overwrite founder WIP.
- If the fix would require touching any runtime/substrate dir, STOP and re-scope -- that would break the L4_ENABLER class.
- If the regression cannot be made deterministic under `PYTHONHASHSEED=0 ... -p no:xdist`, STOP -- do not land a flaky test.
- On any POLICY_BOUND conflict (e.g., a gate demanding a runtime-dir change), STOP and present the decision to the founder.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- The evidence_command is green: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_post_merge_cleanup.py -p no:xdist -q`.
- The new hermetic regression proves the target behavior: clean-ancestor primary + tracked dirty WIP -> HEAD fast-forwarded to `origin/{base_branch}`, tracked WIP preserved, `synced=True`/`skipped=False`, behind_dev signal cleared, untracked/ignored files untouched.
- Unchanged-guard coverage still passes: non-ancestor primary skips + writes behind_dev; base-branch checkout skips; lock contention skips; the outer fail-open path is preserved.
- `python3 -m py_compile mu/tools/executors/commit_executor.py` is clean and `git diff --check` is clean.
- No runtime/substrate diff (L4_ENABLER); the L4 execution-contract enforcer is green for this class; the wave indicator is collectible via `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id never-behind-dev-stash-preserve-2026-07-04 --output reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `never-behind-dev-stash-preserve-2026-07-04`.
- Governing packet: this file, `reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md`.
- TASKS.md authority: the 2026-07-04 tracker sync note for wave `never-behind-dev-stash-preserve-2026-07-04` is canonical for this packet's L4 fields.
- Authorization: Founder TOP-PRIORITY structural fix 2026-07-04 (permanent never-behind-dev, IN THE PIPELINE / orchestrator-agnostic; directive #9 + feedback_automate_grunt_work). FOUNDER_OVERRIDE:never-behind-dev-stash-preserve-2026-07-04.

FOUNDER_OVERRIDE:never-behind-dev-stash-preserve-2026-07-04

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `never-behind-dev-stash-preserve-2026-07-04`
- Active packet: `reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-dev-stash-preserve-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `never-behind-dev-stash-preserve-2026-07-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/never-behind-dev-stash-preserve-2026-07-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id never-behind-dev-stash-preserve-2026-07-04 --output reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-dev-stash-preserve-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: never-behind-dev-stash-preserve-2026-07-04.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `never-behind-dev-stash-preserve-2026-07-04`
- Active packet: `reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4d29264424582b0c5f7755b64a03ca0e40674896351c0c8b667ae886c31552b6`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-dev-stash-preserve-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-dev-stash-preserve-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-dev-stash-preserve-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-dev-stash-preserve-2026-07-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
