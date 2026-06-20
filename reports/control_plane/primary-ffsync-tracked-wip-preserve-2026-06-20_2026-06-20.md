# NEXT-CODEX-POST-REDTEAM - primary ff-sync tracked WIP preservation

Date: 2026-06-20
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: primary-ffsync-tracked-wip-preserve-2026-06-20
Phase-A-Lock: LOCKED
Purpose: Permanently harden the post-merge primary worktree fast-forward helper so tracked founder WIP no longer strands the main workspace behind origin/dev while still preserving that WIP deterministically.

## Scope

Pipeline hardening only. This wave may modify commit_executor Step 15b primary-worktree sync logic, focused commit-executor post-merge cleanup tests, this control packet/config, TASKS.md via the launcher tracker-note builder, and the generated L4 indicator artifact.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py (MODIFY) -- add executor-owned tracked-WIP preservation around primary ff-sync.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py (MODIFY) -- add focused Step 15b regressions for tracked WIP preservation, clean restore, and overlap preservation.
- reports/control_plane/primary-ffsync-tracked-wip-preserve-2026-06-20_wave_config.json (NEW) -- launcher input for this wave.
- reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `primary-ffsync-tracked-wip-preserve-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Move the tracked-dirty decision behind fetch, ancestor, and already-current checks so Step 15b only isolates WIP when a real fast-forward is pending.
2. Save exact tracked dirty paths in an executor-owned stash before the ff-only merge, preserving staged and unstaged tracked state while leaving untracked files alone.
3. Run the ff-only merge with the existing no-overwrite-ignore protection and keep all existing no-push, no-base-checkout, no-force, no-reset guarantees.
4. After a successful ff-only merge, restore the stash when the origin/dev range did not change any stashed path.
5. When the origin/dev range overlaps a stashed path, do not apply the stash into primary; leave it recoverable and report stash ref, stash oid, path list, and overlap list in the outcome/log.
6. Preserve existing skip behavior for base-branch primary checkouts, divergent local commits, fetch failures, lock contention, and ignored-file overwrite hazards.
7. Run the configured evidence command and collect the L4 indicator artifact.

## Constraints

- Use the launcher and dispatcher path; do not hand-commit this wave.
- Do not modify runtime, substrate, seed, registry, JS production, StructuralNumbers gates, or docs outside the wave packet/config/tracker note.
- Do not use force checkout, reset, rebase, push, or destructive commands in the primary-sync helper.
- Do not hide preserved WIP: outcome fields and logs must expose the stash ref/oid/path list when WIP is isolated or left stashed.
- Do not include untracked files in the tracked-WIP stash; existing untracked-preservation behavior must remain.
- Keep tests focused on real git repos and the public sync_primary_worktree_to_base seam.

## Stop conditions

- Stop as DEFECT if tracked WIP cannot be preserved without force/reset/destructive cleanup.
- Stop as POLICY_BOUND if the fix would silently drop or hide founder WIP without a recoverable stash reference.
- Stop as INTEGRATION if the helper cannot distinguish non-overlap from overlap without broad or flaky git behavior.
- Do not proceed to commit without the configured evidence command passing and the indicator artifact collected.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- A primary feature branch behind origin/dev with non-overlapping tracked WIP fast-forwards and restores the tracked WIP with staged/unstaged state preserved.
- A primary feature branch behind origin/dev with overlapping tracked WIP fast-forwards and leaves the WIP recoverable in an executor-owned stash with explicit outcome fields.
- Untracked files still do not block primary ff-sync and are not included in the tracked-WIP stash.
- Divergent local commits, primary-on-base checkouts, fetch failures, lock contention, and ignored-file overwrite hazards still skip safely.
- The helper remains pull-only: no push, no checkout of base, no force, no reset.
- The configured evidence command passes.
- reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `primary-ffsync-tracked-wip-preserve-2026-06-20`.
- Governing packet: this file, `reports/control_plane/primary-ffsync-tracked-wip-preserve-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `primary-ffsync-tracked-wip-preserve-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder requested a permanent fix after the post-merge primary ff-sync skipped because tracked WIP was present and left main 0 ahead / 43 behind origin/dev. This wave hardens the pipeline instead of manually reconciling main.

FOUNDER_OVERRIDE:primary-ffsync-tracked-wip-preserve-2026-06-20 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id primary-ffsync-tracked-wip-preserve-2026-06-20 --output reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Routed commit handoff scopes 6 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: primary-ffsync-tracked-wip-preserve-2026-06-20 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `primary-ffsync-tracked-wip-preserve-2026-06-20`
- Active packet: `reports/control_plane/primary-ffsync-tracked-wip-preserve-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `243dc8b00ad97ef0e98feafcd33cad3c768c485e225e2c5d8015ebed4f7d7fdf`
- Indicator artifact: `reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Routed commit handoff scopes 6 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json..
- Evidence handles:
  - `docs_consistency`: `./tools/checks/check_docs_consistency.sh`
  - `focused_sync_primary_tests`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py -k "sync_primary" --tb=short`
  - `full_post_merge_cleanup_tests`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short`
  - `indicator`: `reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json`
  - `l4_contract`: `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id primary-ffsync-tracked-wip-preserve-2026-06-20 --wave-class L4_ENABLER`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/primary-ffsync-tracked-wip-preserve-2026-06-20_2026-06-20.md`
  - `reports/control_plane/primary-ffsync-tracked-wip-preserve-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/primary-ffsync-tracked-wip-preserve-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
