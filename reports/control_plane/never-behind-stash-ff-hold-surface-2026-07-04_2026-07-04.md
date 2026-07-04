# Step 15b: convert the tracked-WIP-overlap and untracked-collision behind-dev skips into stash-ff-hold-and-surface so the realistic founder primary reaches behind zero without losing or clobbering WIP

Date: 2026-07-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: never-behind-stash-ff-hold-surface-2026-07-04
Phase-A-Lock: LOCKED
Purpose: FOUNDER TOP PRIORITY, permanent structural never-behind-dev (asked repeatedly; must live in the pipeline so it works for ANY orchestrator incl. codex). The commit_executor Step 15b _sync_primary_worktree_to_base already ff's a clean-ancestor primary that has ONLY untracked WIP or NON-OVERLAPPING tracked WIP. But the realistic founder primary accumulates STALE mechanical local edits (STATUS.md, TASKS.md, executor_config.json, docs_registry.json, session/observability/test files) that OVERLAP dev's fast-forward range, so Step 15b takes the `if overlap_paths` branch and SKIPS (_behind_dev_dirty_skip, behind_dev.json reason=dirty_primary_worktree) -> the primary is PERMANENTLY behind. It ALSO skips when an untracked file that dev now TRACKS would collide with the ff (git aborts). VERIFIED 2026-07-04: WorkingRCX was 152 behind / 0-ahead / clean-ancestor with 17 overlapping tracked WIP files AND 2 untracked collisions; a hand reconcile (stash the tracked WIP -> move the colliding untracked aside -> git merge --ff-only -> leave the preserved content for review) reached behind=0 with ZERO loss. This wave AUTOMATES that proven-safe procedure into the pipeline so it never has to be done by hand.

## Scope

mu/tools/executors/commit_executor.py (_sync_primary_worktree_to_base, Step 15b) -- REQUIRED CODE CHANGE -- plus regressions in mu/tests/tools/test_commit_executor_post_merge_cleanup.py. Convert the overlap-skip and the untracked-collision skip into a stash-ff-hold-and-surface path. No runtime/substrate files; L4_ENABLER. The wave is INCOMPLETE if commit_executor.py is not modified.

Files and surfaces in scope:

- TASKS.md -- tracker-sync authority. The 2026-07-04 tracker sync note for wave `never-behind-stash-ff-hold-surface-2026-07-04` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/never-behind-stash-ff-hold-surface-2026-07-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Current code truth (dev `0aa76e3a`): `_sync_primary_worktree_to_base` already reaches behind==0 for (a) untracked-only NON-colliding WIP (`FIX-NEVERBEHIND-FF-UNTRACKED`) and (b) NON-overlapping tracked WIP (stash -> ff -> restore-in-place). Those two paths are landed and are OUT of this wave. Only the two remaining SKIP branches are pending:

1. Convert the tracked-WIP-**overlap** skip in `_sync_primary_worktree_to_base` (the `if overlap_paths:` branch that currently returns `_behind_dev_dirty_skip` "instead of risking a conflicting restore") into **stash-ff-HOLD-and-surface**: isolate the overlapping tracked WIP with the existing `_stash_primary_sync_tracked_wip`, run the existing `git merge --ff-only --no-overwrite-ignore` so the primary reaches behind==0, and -- because restoring the WIP over the freshly ff'd dev content is the exact conflicting-3-way-merge risk the current skip exists to avoid -- do NOT call `_restore_primary_sync_tracked_wip`. HOLD the WIP in the executor-owned stash and write a `wip_held_for_review` manifest naming the stash ref/oid and the held paths so the founder can recover it.
2. Convert the untracked/ignored-**collision** skip (the untracked-only branch's `merge_proc.returncode != 0` fall-back that currently `_behind_dev_dirty_skip`s with `signal_reason="ff_only_merge_failed"`, and the equivalent ff-abort-on-collision fall-back in the non-overlapping tracked-WIP path) into **move-aside-and-surface**: move ONLY the colliding untracked/ignored path(s) into an executor-owned backup dir, retry `git merge --ff-only --no-overwrite-ignore` to reach behind==0, and record the moved path(s) + backup location in the same `wip_held_for_review` manifest.
3. Failure-path safety: if the ff fails AFTER isolating (stash created and/or untracked moved) or the manifest cannot be written, RESTORE the stashed tracked WIP and move the relocated untracked file(s) back, then fall back to the existing `_behind_dev_dirty_skip` with a `behind_dev` signal -- never advance HEAD with founder WIP stranded only in the stash/backup, and never silently drop it.
4. Add hermetic regressions to `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` covering (a) overlapping-tracked-WIP -> ff succeeds, WIP held in stash + manifest written, behind==0; (b) untracked collision -> colliding path moved to backup dir, ff succeeds, manifest records it, behind==0; (c) ff-fails-after-isolation -> stash restored + untracked moved back + safe `behind_dev` skip.

## Constraints

- L4_ENABLER: NO runtime/substrate files. No changes under `mu/host/`, `rcx_pi/selfhost/`, or any substrate/runtime dir -- only `mu/tools/executors/commit_executor.py` (tooling) and its regression test.
- Do NOT touch the two already-landed, already-safe paths: the untracked-only NON-colliding ff (`FIX-NEVERBEHIND-FF-UNTRACKED`) and the non-overlapping tracked-WIP stash-ff-**restore**. They already reach behind==0 without loss; this wave converts ONLY the two remaining SKIP branches (overlap, collision).
- Never restore held WIP OVER dev content (HOLD only) -- restoring over the ff'd range is the conflicting-3-way-merge risk the overlap-skip was written to prevent.
- Never clobber, overwrite, or silently drop founder WIP. Keep the pull-only `git merge --ff-only --no-overwrite-ignore`; never push, checkout base, force, or reset the primary.
- Pipeline-only: land via the executor pipeline, no manual git. No new files beyond the two in scope (`commit_executor.py` and its regression test); this packet-content fix touches only this plan file now.
- The packet's L4 fields derive from the canonical 2026-07-04 TASKS.md tracker sync note for `never-behind-stash-ff-hold-surface-2026-07-04`; do not diverge packet <-> note.

## Stop conditions

- STOP and fall back to the existing safe `_behind_dev_dirty_skip` if reaching behind==0 would require restoring WIP over dev, a conflicting/3-way merge, or any non-fast-forward (force / reset / checkout-base).
- STOP (safe-skip + `behind_dev` signal) if the stash cannot be created, a colliding untracked file cannot be moved to the backup dir, or the `wip_held_for_review` manifest cannot be written -- never advance HEAD with WIP unaccounted-for.
- STOP if the change would touch any runtime/substrate file (that would invalidate the L4_ENABLER class).
- STOP-as-INCOMPLETE if `commit_executor.py` is not modified: a docs/test-only result does NOT satisfy this wave (Scope: "INCOMPLETE if commit_executor.py is not modified").
- STOP if the evidence_command regressions are not green.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- `_sync_primary_worktree_to_base`: a clean-ancestor behind-dev primary whose tracked WIP OVERLAPS the ff range fast-forwards to **behind==0** with the overlapping tracked WIP HELD in the executor-owned stash and a `wip_held_for_review` manifest naming the stash ref/oid + held paths (NOT restored over dev).
- A clean-ancestor behind-dev primary with an untracked/ignored file that COLLIDES with the ff moves ONLY the colliding path(s) into an executor-owned backup dir, fast-forwards to **behind==0**, and records the moved path(s) + backup location in the manifest.
- Failure after isolation restores the stashed tracked WIP and moves the relocated untracked file(s) back, then safe-skips with a `behind_dev` signal -- zero loss, zero clobber, HEAD never left advanced with stranded WIP.
- `commit_executor.py` is modified; no runtime/substrate file changed (L4_ENABLER preserved).
- Evidence command is green: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_post_merge_cleanup.py -p no:xdist -q`, including the three new hermetic regressions (overlap-held, untracked-collision-moved, failure-restore); the already-landed untracked-only-ff and non-overlapping-stash-restore regressions stay green.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `never-behind-stash-ff-hold-surface-2026-07-04`.
- Governing packet: this file, `reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md`.
- TASKS.md authority: the 2026-07-04 tracker sync note for wave `never-behind-stash-ff-hold-surface-2026-07-04` is canonical for this packet's L4 fields.
- Authorization: Founder TOP-PRIORITY permanent structural never-behind-dev 2026-07-04: automate the proven-safe stash-ff-hold-and-surface reconcile into Step 15b so the realistic overlapping-WIP/untracked-collision primary reaches behind=0 without loss or clobber, for any orchestrator. FOUNDER_OVERRIDE:never-behind-stash-ff-hold-surface-2026-07-04.

FOUNDER_OVERRIDE:never-behind-stash-ff-hold-surface-2026-07-04

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `never-behind-stash-ff-hold-surface-2026-07-04`
- Active packet: `reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-stash-ff-hold-surface-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `never-behind-stash-ff-hold-surface-2026-07-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/never-behind-stash-ff-hold-surface-2026-07-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id never-behind-stash-ff-hold-surface-2026-07-04 --output reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-stash-ff-hold-surface-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: never-behind-stash-ff-hold-surface-2026-07-04.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `never-behind-stash-ff-hold-surface-2026-07-04`
- Active packet: `reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8b322a3cf0e03fa23e08fc81b854943edac737f4080c3e252726336c09769354`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-stash-ff-hold-surface-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-stash-ff-hold-surface-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-stash-ff-hold-surface-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-stash-ff-hold-surface-2026-07-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
