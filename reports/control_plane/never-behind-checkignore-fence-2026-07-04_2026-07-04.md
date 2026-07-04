# Step 15b completion: auto-advance the tracked-overlap and untracked-collision primary via stash-ff-hold plus move-aside, fencing locally-ignored founder WIP at the single shared move-aside helper so ignored files are never relocated

Date: 2026-07-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: never-behind-checkignore-fence-2026-07-04
Phase-A-Lock: LOCKED
Purpose: FOUNDER TOP PRIORITY permanent never-behind-dev COMPLETION (the collision case the realistic founder primary hits). dev 0aa76e3a already auto-ff's a clean-ancestor primary with ONLY untracked non-colliding WIP (FIX-NEVERBEHIND-FF-UNTRACKED) and stash-ff's non-overlapping tracked WIP. The remaining gap: a primary with tracked-WIP OVERLAPPING the ff range, OR an untracked/ignored file that dev now TRACKS (a real recurring case -- e.g. a scratch file the founder holds locally that becomes tracked on dev), currently SKIPS. This wave auto-advances those via stash-ff-HOLD (stash overlapping tracked WIP, ff, HOLD the stash for review) + move-aside (relocate a colliding untracked-that-dev-tracks file to an executor backup, ff). CRITICAL never-clobber lesson (verified by adversarial audit of a prior attempt): the move-aside MUST NOT relocate a locally-IGNORED founder file -- an earlier attempt fenced only TRACKED paths and RELOCATED ignored founder WIP that dev now tracks. Fence ignored files at the SINGLE shared move-aside helper.

## Scope

mu/tools/executors/commit_executor.py (_sync_primary_worktree_to_base Step 15b + the shared move-aside helper) -- REQUIRED CODE CHANGE -- plus regressions in mu/tests/tools/test_commit_executor_post_merge_cleanup.py. No runtime/substrate files; L4_ENABLER. INCOMPLETE if commit_executor.py is not modified.

Files and surfaces in scope:

- TASKS.md -- tracker-sync authority. The 2026-07-04 tracker sync note for wave `never-behind-checkignore-fence-2026-07-04` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/never-behind-checkignore-fence-2026-07-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. In `_sync_primary_worktree_to_base` (Step 15b, `mu/tools/executors/commit_executor.py`), replace the current tracked-WIP-overlap SKIP branch (today `_behind_dev_dirty_skip("...overlapping the fast-forward range...")`) with a **stash-ff-HOLD**: stash the overlapping tracked WIP via the executor-owned stash helper, run the existing `git merge --ff-only --no-overwrite-ignore` to reach `behind==0`, and on success HOLD the stash (do NOT `stash pop --index`) — record the held stash ref in the outcome dict for founder review. On ff failure, restore the WIP in place and fall back to the existing behind_dev skip (never leave WIP only in a stash on a failure path).
2. In the same Step 15b, replace the untracked/ignored-collision SKIP branch (today `_behind_dev_dirty_skip("...aborted on an untracked/ignored collision...")`) with a **move-aside** for a colliding NON-ignored untracked file that dev now tracks: relocate the colliding file to an executor-owned backup, run the `--ff-only --no-overwrite-ignore` merge to reach `behind==0`, and record the backup location in the outcome dict. On ff failure, restore the moved file to its original path and fall back to the behind_dev skip.
3. Add a **single shared move-aside helper** and fence it with `git check-ignore`: before relocating ANY path, probe `git check-ignore`; if the path is locally IGNORED, REFUSE to relocate it — clean SKIP + behind_dev signal, the file left BYTE-IDENTICAL in place. All move-aside callers route through this one fenced helper. This is the wave's core never-clobber invariant (adversarial audit of a prior attempt fenced only TRACKED paths and RELOCATED ignored founder WIP that dev now tracks).
4. Add hermetic regressions in `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` for the four named cases: (a) **held-overlap** — tracked WIP overlapping the ff range is stashed, ff proceeds to `behind==0`, stash is HELD (not restored); (b) **untracked-collision-moved** — a non-ignored untracked file that dev now tracks is moved aside, ff reaches `behind==0`, backup location recorded; (c) **ignored-collision-fenced** — a locally-ignored file dev now tracks is FENCED (check-ignore refusal → clean skip + behind_dev), left byte-identical in place, never relocated; (d) **failure-restore** — a forced ff failure after hold/move-aside restores the original working-tree state (WIP never stranded or clobbered).
5. Reconcile the two existing SKIP-asserting regressions this behavior change flips, so the whole-file evidence_command stays green: `test_sync_primary_dirty_overlap_does_not_stash_or_overwrite` (currently asserts the tracked-overlap SKIP → now the stash-ff-HOLD outcome) and `test_sync_primary_untracked_collision_skips_and_preserves_founder_wip` (currently asserts the non-ignored untracked-collision SKIP → now the move-aside outcome). This is required for honest closure: without it the evidence_command below cannot pass.

## Constraints

- MUST NOT touch runtime/substrate dirs. This wave is class `L4_ENABLER` (per the 2026-07-04 `never-behind-checkignore-fence-2026-07-04` tracker sync note), which per `.claude/rules/l4-contract.md` is a tooling prerequisite that MUST NOT modify runtime/substrate production dirs (no `rcx_pi/selfhost/`, no `mu/` runtime/substrate). The note records "No runtime/substrate change" ⇒ L3 Python/JS parity is N/A for this wave.
- MUST NOT relocate ANY locally-ignored file. The move-aside helper fences ignored paths via `git check-ignore` and REFUSES to relocate them (clean skip + behind_dev, byte-identical in place). This is the wave's load-bearing safety invariant, not an optional guard.
- Scope is limited to Step 15b in `_sync_primary_worktree_to_base` + the single shared move-aside helper + the named test file `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`. Do NOT change other executor surfaces or other pipeline steps.
- PULL-ONLY discipline is preserved unchanged: never push, never checkout base, never force/reset — real merges to base stay on the PR path.
- Do NOT alter the already-landed paths: the clean-ancestor untracked-non-colliding ff and the non-overlapping tracked-WIP stash-and-restore behavior stay exactly as-is.

## Stop conditions

- STOP when the four named regression cases pass AND the two reconciled existing tests pass — i.e. the evidence_command is green.
- STOP when a tracked-overlap primary and a non-ignored-untracked-collision primary both reach `behind==0` post-sync.
- STOP when a locally-ignored file that dev now tracks remains byte-identical in place (never relocated) with a clean skip + behind_dev signal.
- Do NOT proceed past a red evidence_command. Do NOT touch runtime/substrate dirs to force a gate green — on any unsafe condition fall back to the existing behind_dev skip rather than ever clobbering or relocating founder WIP.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- All four named regressions assert the specified behavior: **held-overlap** (overlapping tracked WIP stashed and HELD, `behind==0`), **untracked-collision-moved** (non-ignored colliding file moved to an executor backup, backup recorded, `behind==0`), **ignored-collision-fenced** (check-ignore refusal → clean skip + behind_dev, file byte-identical in place, never relocated), and **failure-restore** (a forced post-hold/post-move ff failure restores the original working-tree state).
- The locally-ignored founder file is byte-identical in place after the run and was never relocated — the wave's core never-clobber invariant, asserted by the ignored-collision-fenced regression.
- Tracked-overlap and non-ignored-untracked-collision primaries reach `behind==0` against origin/dev post-sync.
- No runtime/substrate change ⇒ L3 Python/JS parity is N/A (not exercised by this wave).
- evidence_command is green: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_post_merge_cleanup.py -p no:xdist -q`.
- Indicator artifact collected: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id never-behind-checkignore-fence-2026-07-04 --output reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `never-behind-checkignore-fence-2026-07-04`.
- Governing packet: this file, `reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md`.
- TASKS.md authority: the 2026-07-04 tracker sync note for wave `never-behind-checkignore-fence-2026-07-04` is canonical for this packet's L4 fields.
- Authorization: Founder TOP-PRIORITY permanent never-behind-dev completion 2026-07-04; fences ignored founder WIP at the shared move-aside helper (adversarial-audit-confirmed clobber path). FOUNDER_OVERRIDE:never-behind-checkignore-fence-2026-07-04.

FOUNDER_OVERRIDE:never-behind-checkignore-fence-2026-07-04

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `never-behind-checkignore-fence-2026-07-04`
- Active packet: `reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-checkignore-fence-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `never-behind-checkignore-fence-2026-07-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/never-behind-checkignore-fence-2026-07-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id never-behind-checkignore-fence-2026-07-04 --output reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-checkignore-fence-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: never-behind-checkignore-fence-2026-07-04.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `never-behind-checkignore-fence-2026-07-04`
- Active packet: `reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `babbd302a43a5fb84425ce97ef7e1b6b53df4767f78868484ceb6697620fb963`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-checkignore-fence-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-checkignore-fence-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-checkignore-fence-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-checkignore-fence-2026-07-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
