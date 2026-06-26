# Program Queue Postmerge Selector Truth 2026-06-26

Date: 2026-06-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: program-queue-postmerge-selector-truth-2026-06-26
Phase-A-Lock: LOCKED
Purpose: Repair the commit-executor post-merge queue selector so it cannot mark the active queue empty when TASKS.md still contains PROGRAM QUEUE work. Also refresh STATUS.md and TASKS.md after PR #1158, PR #1139, and PR #1140 are all on current dev, so the active queue advances from the already-merged Surreals wave to recursive ordinals as the next autonomous structural item.

## Scope

Pipeline/control-plane root fix plus active tracker truth only. Touch commit_executor post-merge queue selection, focused post-merge cleanup tests, TASKS.md, STATUS.md, this launcher config, generated packet, and indicator artifact. Do not implement recursive ordinals, W-types, coinduction, fixpoint, optimization, runtime semantics, substrate semantics, seeds, registries, projection behavior, pager/autoping, or tmux changes in this wave.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py (MODIFY) -- add PROGRAM QUEUE fallback parsing for post-merge package refresh while preserving existing founder-ordered packet behavior.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py (MODIFY) -- regression for a simple numbered PROGRAM QUEUE item without Wave ID or Packet metadata producing a non-empty next candidate.
- TASKS.md (MODIFY) -- refresh active queue truth after PR #1158, PR #1139, and PR #1140; remove merged Surreals from pending item 1 and make recursive ordinals the next active structural item.
- STATUS.md (MODIFY) -- update last-updated, next-milestone, and active-next wording to match TASKS.md while preserving Phase 8c/L4 debt posture.
- reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_wave_config.json (KEEP) -- launcher config for this repair wave.
- reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md (GENERATED) -- launcher-created control packet.
- reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json (GENERATED) -- indicator artifact for this wave.
- TASKS.md -- tracker-sync authority. The 2026-06-26 tracker sync note for wave `program-queue-postmerge-selector-truth-2026-06-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the selector defect from current repo truth: TASKS.md has PROGRAM QUEUE items, but .agent_bus/meta/post_merge_package.json says founder-ordered-post-merge-queue-empty after merge commit 9f9a3771.
2. Keep the existing founder-ordered Wave ID plus Packet selector behavior intact for old packetized queues.
3. Add a bounded fallback for TASKS.md PROGRAM QUEUE numbered entries that parses only the PROGRAM QUEUE section and ignores DROPPED, PARKED, governance, and Ra history.
4. For simple PROGRAM QUEUE entries, derive a stable normalized wave id from the entry label and queue text. If a matching reports/control_plane/*_wave_config.json exists, use its tracked_packet and request text. If no config exists yet, still write a non-empty bounded next candidate with a clear request to launch or prepare that queue item through launch_wave.py instead of reporting queue empty.
5. Ensure completed simple items are not selected after docs mark them complete or remove them from the PROGRAM QUEUE.
6. Update tests to prove the exact failure mode: completed founder-ordered packets plus a live simple PROGRAM QUEUE item must result in post_merge_queue_empty false and a next candidate for that simple item.
7. Refresh TASKS.md and STATUS.md using current git evidence: PR #1158 completed Surreals, PR #1139 is merged, PR #1140 is merged, recursive ordinals is next, and optimization remains LAST.
8. Run the configured evidence command, collect the indicator artifact, and leave commit, push, PR, review, CI, merge, receipts, and post-merge refresh to the commit executor.

## Constraints

- Use launch_wave.py, executor_dispatch, Phase A, Phase B, bridge review, and commit executor for this wave.
- Do not manually commit, manually author receipts, manually perform phase handoff, or manually run a direct git commit.
- Implementer, reviewer, and pager route are Codex; Codex 5.5 xhigh defaults come from executor_config.json.
- No runtime, substrate, seed, registry, projection, JavaScript parity, recursive ordinal implementation, W-type implementation, coinduction, fixpoint, optimization, pager/autoping, or tmux behavior changes are authorized.
- Do not broaden the post-merge selector into arbitrary markdown scraping; it must be section-bounded and conservative.
- Do not report queue empty when active PROGRAM QUEUE items remain.
- Optimization remains LAST.

## Stop conditions

- Halt as DEFECT if the fallback selects DROPPED, PARKED, Ra, governance, historical, or completed items.
- Halt as DEFECT if old founder-ordered packet selection regresses.
- Halt as DOC_ACCURACY if git evidence does not prove PR #1158, PR #1139, and PR #1140 are merged on current dev.
- Halt as POLICY_BOUND if implementing the next math structure is required inside this selector repair wave.
- Do not commit without focused tests, docs consistency, staged L4 contract validation, indicator collection, bridge review, and commit-executor handling.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- commit_executor post-merge refresh returns post_merge_queue_empty false when TASKS.md has a live simple PROGRAM QUEUE item even if founder-ordered packet entries are absent or completed.
- The generated post-merge package contains a bounded next candidate for the simple PROGRAM QUEUE item and a request that keeps execution on launch_wave.py / dispatcher / commit_executor surfaces.
- Existing founder-ordered queue tests still pass.
- TASKS.md pending PROGRAM QUEUE starts with recursive ordinals as structure and preserves W-types / inductive types, coinduction, fixpoint, and optimization LAST.
- STATUS.md agrees with TASKS.md and preserves Phase 8c/L4 debt counts and posture.
- No runtime/substrate/seed/registry/projection/parity/pager/autoping/tmux files are touched.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `program-queue-postmerge-selector-truth-2026-06-26`.
- Governing packet: this file, `reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md`.
- TASKS.md authority: the 2026-06-26 tracker sync note for wave `program-queue-postmerge-selector-truth-2026-06-26` is canonical for this packet's L4 fields.
- Authorization: Founder-directed autonomous cleanup of stale queue truth and structural pipeline root fix after the post-merge package falsely reported an empty queue while TASKS.md still had PROGRAM QUEUE items. Founder also directed use of the builder and commit supervisor, and no manual commit process.

FOUNDER_OVERRIDE:program-queue-postmerge-selector-truth-2026-06-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `program-queue-postmerge-selector-truth-2026-06-26`
- Active packet: `reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md`
- Indicator artifact: `reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe the current four-file staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md`
  - `reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id program-queue-postmerge-selector-truth-2026-06-26 --output reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: program-queue-postmerge-selector-truth-2026-06-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `program-queue-postmerge-selector-truth-2026-06-26`
- Active packet: `reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9893c614e69b80b021ff9a7a351d70b3f56eae6d767e79bba4dabd3164f0dc7d`
- Indicator artifact: `reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `reports/control_plane/program-queue-postmerge-selector-truth-2026-06-26_2026-06-26.md`
  - `reports/l4_wave_indicators/program-queue-postmerge-selector-truth-2026-06-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
