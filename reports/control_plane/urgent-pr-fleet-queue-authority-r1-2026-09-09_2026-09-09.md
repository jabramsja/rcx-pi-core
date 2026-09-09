# Urgent PR and Fleet Queue Authority R1

Date: 2026-09-09
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [URGENT-PR-FLEET-QUEUE-AUTHORITY-R1]
Wave ID: urgent-pr-fleet-queue-authority-r1-2026-09-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 54be7e60ca8791963b7e0e2d687e57386943251f88616c4de71b39aa5337b347
Purpose: Make the preservation-first open-PR and WorkingRCX fleet work the unambiguous immediate queue without performing that work in this wave, while preserving the stopped nonconvergent Phase B candidate and every later recovery, PR1219, and Mu-production obligation.

## Scope

Synchronize TASKS queue authority only so preservation-first PR and WorkingRCX fleet handling becomes the immediate post-merge axis.

Files and surfaces in scope:

- TASKS.md queue authority and TODO truth
- The builder-generated same-wave control-plane packet
- The same-wave L4 indicator
- An optional same-wave deferred non-blocker report
- TASKS.md -- tracker-sync authority. The 2026-09-09 tracker sync note for wave `urgent-pr-fleet-queue-authority-r1-2026-09-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Treat this external JSON WaveConfig as the operator stub and the builder-generated Markdown at the tracked packet path as the sole canonical Phase A plan; do not hand-author or revise the packet in place.
2. Record that merge be56521bde9a6453a14399d0f46f0c74d12bf043, PR 1276, remains the latest landed authority for this queue wave.
3. Record the stopped broad Phase B candidate as PRESERVED_NONCONVERGENT_NOT_COMPLETE at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-preservation/phase-b-private-review-byte-preserving-resume-r1-nonconvergent-r3-20260909, based on be56521bde9a6453a14399d0f46f0c74d12bf043, with staged-diff SHA-256 9c30c179f804ef7cdce58703c250eb97f57ec4a3006b3c06c05de1a2ff8c266f, packet SHA-256 f1bdc2752f3bc2013e6214e703ae4de1cab6dbc4195bd2945fb8d965b099f015, 646 passing focused tests, and final reviewer job phase-b-reentry-r3-faf68423 finding that recovered QUESTION bypasses retained-envelope validation and rewrites the pending checkpoint. Remove it from CURRENT and do not resume, copy, mutate, delete, or claim completion for it.
4. Resolve the contradictory queue ordering. While this wave runs, make URGENT-PR-FLEET-QUEUE-AUTHORITY-R1 the sole CURRENT item. After it lands, make PR-LIVE-CENSUS-RECONCILIATION the sole immediate NEXT item, followed serially by NEVER-BEHIND-FLEET-AUTHORITY, PR-DISPOSITION-EXECUTION, FLEET-CLEANUP-BUILDER, and FLEET-CLEANUP-APPLY.
5. Retain the recovery R2, fresh R3C6-R2, exact PR1219 closure, and all later PR1219 obligations behind the urgent PR/fleet axis without loss, followed by the already-recorded Mu-production work.
6. Record volatile observations as observations requiring fresh action-time census, not as completed work: exactly 8 GitHub PRs were open and conflicting when checked on 2026-09-09, and exactly 223 top-level WorkingRCX-prefixed directories were present under RCXStackminimal when checked on 2026-09-09.
7. Mark legacy-pr-worktree-carry-forward-plan-2026-08-21_wave_config.json and open-pr-disposition-apply-2026-08-21_wave_config.json as stale, overbroad, nonlaunchable planning evidence because they contain unresolved future comparison authority and combine too many independently convergent actions. Require fresh narrow builder inputs after exact predecessor merges.
8. Keep the TODO list and binding queue synchronized with the same ordering. Do not claim that any PR was classified, closed, merged, or reconstructed, or that any WorkingRCX directory was inventoried, preserved, retired, or deleted in this queue-only wave.
9. Land through staged L4, independent Codex review, providerless commit, pre-push, required CI, review policy, merge, and cleanup; then create the fresh narrow PR live-census WaveConfig from the exact merge authority.

## Constraints

- Only the four candidate-allowlisted paths may change, and substantive authoring is confined to TASKS.md; no runtime, executor, test, configuration, PR, branch, worktree, preservation directory, or Claude-owned file may change.
- Do not run the PR census, fleet census, never-behind reconciliation, PR disposition, preservation, deletion, cleanup, or Mu-production work inside this wave.
- Do not relaunch or modify the preserved nonconvergent Phase B candidate, copy its staged bytes, or represent its 646 passing tests as reviewer approval.
- Do not launch either stale 2026-08-21 combined config; future execution packets must be narrow builder-generated packets with exact merged predecessor comparison authority.
- Do not add edge-case work, code fixes, executor fixes, packet-schema changes, or speculative prerequisites. Record a real nonblocker and continue when it does not prevent this queue-only landing.
- The external JSON WaveConfig is the operator stub. The generated Markdown is canonical and must not be edited or replaced by a handwritten packet.
- Every model-bearing role and pager remains Codex gpt-5.6-sol ultra; commit remains providerless.

## Stop conditions

- Stop before launch unless source, target, and comparison authority are exact be56521bde9a6453a14399d0f46f0c74d12bf043, the linked worktree and bus are fresh, every model-bearing role resolves to Codex, and commit is providerless.
- Stop if TASKS cannot preserve every named recovery, PR1219, cleanup, and Mu-production obligation while establishing one noncontradictory urgent ordering.
- Stop if any implementation beyond the allowlisted governance paths is required; that belongs in a later narrow wave.
- Do not stop or widen for wording preferences, speculative edge cases, or observations that do not block an unambiguous executable queue.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id urgent-pr-fleet-queue-authority-r1-2026-09-09 --output reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`

## Acceptance criteria

- Only the four candidate-allowlisted paths change, with substantive changes confined to TASKS.md and same-wave generated governance.
- TASKS has one unambiguous binding order: this wave while active, then PR live census, never-behind preservation, PR disposition, fleet cleanup plan, and fleet cleanup apply.
- The preserved nonconvergent Phase B lane is recorded exactly as stopped evidence, not CURRENT, complete, resumed, copied, mutated, or deleted.
- Recovery R2, fresh R3C6-R2, the exact PR1219 closure chain, all later obligations, and Mu production remain present and ordered behind the urgent axis.
- The 8 open PRs and 223 top-level WorkingRCX-prefixed directories are explicitly dated volatile observations requiring fresh census, not asserted outcomes.
- The two stale combined 2026-08-21 configs are explicitly nonlaunchable evidence, and the immediate successor is a fresh narrow PR census builder input created from this wave's exact merge.
- The packet is generated and locked by launch_wave.py, all roles remain Codex gpt-5.6-sol ultra, and staged L4, independent review, providerless commit, required checks, merge, and cleanup complete through the pipeline.

## Grounding / Authorization

- Task: [URGENT-PR-FLEET-QUEUE-AUTHORITY-R1]; wave id `urgent-pr-fleet-queue-authority-r1-2026-09-09`.
- Governing packet: this file, `reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md`.
- TASKS.md authority: the 2026-09-09 tracker sync note for wave `urgent-pr-fleet-queue-authority-r1-2026-09-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:urgent-pr-fleet-queue-authority-r1-2026-09-09

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `urgent-pr-fleet-queue-authority-r1-2026-09-09`
- Active packet: `reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md`
- Indicator artifact: `reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md`
  - `reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id urgent-pr-fleet-queue-authority-r1-2026-09-09 --output reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id urgent-pr-fleet-queue-authority-r1-2026-09-09 --output reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md`, `reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: urgent-pr-fleet-queue-authority-r1-2026-09-09.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `urgent-pr-fleet-queue-authority-r1-2026-09-09`
- Active packet: `reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `479b163ef0c8161469d1d0aeb79dabf0a738efd024be39c10f84223e0584a7cf`
- Indicator artifact: `reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id urgent-pr-fleet-queue-authority-r1-2026-09-09 --output reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md`, `reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/urgent-pr-fleet-queue-authority-r1-2026-09-09_2026-09-09.md`
  - `reports/l4_wave_indicators/urgent-pr-fleet-queue-authority-r1-2026-09-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
