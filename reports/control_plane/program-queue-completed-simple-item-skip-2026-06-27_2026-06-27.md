# Program Queue Completed Simple Item Skip 2026-06-27

Date: 2026-06-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: program-queue-completed-simple-item-skip-2026-06-27
Phase-A-Lock: LOCKED
Purpose: Repair the commit-executor post-merge PROGRAM QUEUE selector so completed simple queue items cannot replay after their bounded launcher wave lands under a different explicit wave id, while preventing TASKS tracker notes for the same wave from acting as completion proof before merge. The current stale package after PR #1161 proves W-types still selected even though reviewer evidence proves PR #1161 merged; the selector must advance to Coinduction from current-dev landed proof or a post-merge-only completion marker, not from a pre-commit tracker note alone.

## Scope

Pipeline/control-plane root fix plus active TASKS queue truth only. Touch commit_executor post-merge queue selection, focused post-merge cleanup tests, TASKS.md if needed for current queue truth, this launcher config, generated packet, and indicator artifact. Do not implement Coinduction, Fixpoint, Optimization, runtime semantics, substrate semantics, seeds, registries, projection behavior, pager/autoping, or tmux changes in this wave.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py (MODIFY) -- make simple PROGRAM QUEUE completion detection use matching launcher config plus tracked packet Wave ID/status for identity, then require current-dev merge/landed proof or a post-merge-only completion marker before skipping an entry. TASKS notes for the same wave may bind authorization and wave identity, but pre-commit notes are not completion proof.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py (MODIFY) -- add a regression for completed recursive ordinals and W-types simple entries advancing the post-merge candidate to Coinduction.
- TASKS.md (MODIFY IF NEEDED) -- refresh active queue wording after PR #1160 and PR #1161 so Coinduction is the next active structural item and Optimization remains LAST.
- STATUS.md (MODIFY ONLY IF NEEDED) -- active-next wording only if existing status text contradicts TASKS.md; preserve Phase 8c/L4 posture and debt counts.
- reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_wave_config.json (KEEP) -- launcher config for this repair wave.
- reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md (GENERATED) -- launcher-created control packet.
- reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json (GENERATED) -- indicator artifact for this wave.
- TASKS.md -- tracker-sync authority. The 2026-06-27 tracker sync note for wave `program-queue-completed-simple-item-skip-2026-06-27` is the single source of truth for this packet's L4 fields; the packet derives from it. TASKS tracker notes for earlier queue items authorize their wave metadata only unless they carry a post-merge-only landed/status marker.

## Work items

1. Reproduce the selector defect from current repo truth: .agent_bus/meta/post_merge_package.json has merged_pr 1161 and merge_sha 6a6b4217 but still selects W-types.
2. Read commit_executor._simple_program_queue_entries and _next_open_founder_ordered_queue_entry before changing selector behavior.
3. Keep existing founder-ordered Wave ID plus Packet queue behavior intact.
4. For simple PROGRAM QUEUE entries, use matching launcher configs, config wave_id, tracked packet status, tracked packet Wave ID, and TASKS notes for the same wave only to bind queue identity and authorization. Do not rely on the text-derived wave id alone when the launched bounded wave used an explicit shorter wave id.
5. Require completion proof to be current-dev landed proof or a post-merge-only status marker before skipping a simple queue item. A TASKS note for the same wave with pre-commit receipt-pending evidence is not sufficient completion proof.
6. Add a focused positive regression that reproduces the RecursiveOrdinals plus WTypesInductiveTypes sequence with current-dev landed proof for PR #1160 and PR #1161 and asserts Coinduction is selected next.
7. Add a focused negative regression where a matching TASKS tracker note for the same wave exists, but the wave lacks current-dev merge/landed proof or a post-merge-only completion marker; the selector must not skip that simple queue item as completed.
8. Refresh TASKS.md only as needed to make the active queue truth clear: recursive ordinals and W-types are landed through PR #1160 and PR #1161; Coinduction is next; Fixpoint follows; Optimization remains LAST. Do not use the existing pre-commit pending tracker notes at TASKS.md as the landing proof.
9. Run the configured evidence command, collect the indicator artifact, and leave commit, push, PR, review, CI, merge, receipts, and post-merge refresh to the commit executor.

## Constraints

- Use launch_wave.py, executor_dispatch, Phase A, Phase B, bridge review, and commit executor for this wave.
- Do not manually commit, manually author receipts, manually perform phase handoff, or manually run a direct git commit.
- Implementer, reviewer, and pager route are Codex; Codex 5.5 xhigh defaults come from executor_config.json.
- No runtime, substrate, seed, registry, projection, JavaScript parity, Coinduction implementation, Fixpoint implementation, optimization, pager/autoping, or tmux behavior changes are authorized.
- Do not broaden the post-merge selector into arbitrary markdown scraping; completion detection must remain section-bounded, tracker-note-bounded, and conservative.
- TASKS tracker notes for the same wave may not be treated as terminal completion proof unless they carry a post-merge-only landed/completed marker. Pre-commit supervisor package-refresh wording is authorization/status context, not merge proof.
- Do not report queue empty or replay a completed simple queue item when active later PROGRAM QUEUE items remain.
- Optimization remains LAST.

## Stop conditions

- Halt as DEFECT if the fix selects DROPPED, PARKED, Ra history, governance prose, historical tracker notes unrelated to the queue item, or completed items.
- Halt as DEFECT if the fix skips a simple PROGRAM QUEUE item solely because a TASKS tracker note for the same wave exists while the available note still carries pre-commit receipt-pending evidence.
- Halt as DEFECT if old founder-ordered packet selection regresses.
- Halt as DOC_ACCURACY if current-dev landed proof or a post-merge-only status marker does not prove PR #1160 and PR #1161 are merged/current. TASKS.md pre-commit supervisor package-refresh notes are not sufficient by themselves.
- Halt as POLICY_BOUND if implementing Coinduction, Fixpoint, or Optimization is required inside this selector repair wave.
- Do not commit without focused tests, docs consistency, staged L4 contract validation, indicator collection, bridge review, and commit-executor handling.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- commit_executor post-merge refresh skips completed simple PROGRAM QUEUE items even when the text-derived queue wave id differs from the explicit launched wave id.
- Completion skipping requires current-dev landed proof or a post-merge-only completion marker; TASKS notes for the same wave with pre-commit supervisor pending wording are not enough.
- The focused positive regression proves recursive ordinals and W-types are skipped only with landed proof for PR #1160 and PR #1161, so Coinduction becomes the next post-merge candidate.
- The focused negative regression proves a tracker note without landed/current proof does not skip an unmerged simple queue item.
- Existing founder-ordered queue tests still pass.
- TASKS.md queue truth is current after PR #1160 and PR #1161 and preserves Fixpoint plus Optimization LAST.
- No runtime/substrate/seed/registry/projection/parity/pager/autoping/tmux files are touched.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `program-queue-completed-simple-item-skip-2026-06-27`.
- Governing packet: this file, `reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md`.
- TASKS.md authority: the 2026-06-27 tracker sync note for wave `program-queue-completed-simple-item-skip-2026-06-27` is canonical for this packet's L4 fields. TASKS.md show that same-wave queue-item notes can be pre-commit supervisor package-refresh notes with pending receipts; those notes authorize metadata but do not prove merge/completion unless paired with current-dev landed proof or a post-merge-only status marker.
- Authorization: Founder-directed autonomous queue continuation and structural pipeline root fix after PR #1161 post-merge package replayed W-types. Founder directed use of the builder and commit supervisor, pipeline-only execution, and no manual commit process.

FOUNDER_OVERRIDE:program-queue-completed-simple-item-skip-2026-06-27

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `program-queue-completed-simple-item-skip-2026-06-27`
- Active packet: `reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md`
- Indicator artifact: `reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `STATUS.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md`
  - `reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_wave_config.json`
  - `reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id program-queue-completed-simple-item-skip-2026-06-27 --output reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: program-queue-completed-simple-item-skip-2026-06-27.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `program-queue-completed-simple-item-skip-2026-06-27`
- Active packet: `reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `40d44f84c35eb2a5f83bd4ca14175df626df9582666307e00118482fe03820e6`
- Indicator artifact: `reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json`
- Current staged files:
  - `STATUS.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_2026-06-27.md`
  - `reports/control_plane/program-queue-completed-simple-item-skip-2026-06-27_wave_config.json`
  - `reports/l4_wave_indicators/program-queue-completed-simple-item-skip-2026-06-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
