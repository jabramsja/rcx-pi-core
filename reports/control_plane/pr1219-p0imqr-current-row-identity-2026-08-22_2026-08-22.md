# PR 1219 P0IMQR Current Row Identity 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMQR-CURRENT-ROW-IDENTITY]
Wave ID: pr1219-p0imqr-current-row-identity-2026-08-22
Phase-A-Lock: LOCKED
Purpose: After exact P0IMF PR #1230 merge d609cf19b9d71411de2bbdfd5eb8aca9e7009e90 and before P0IMRP, repair post-merge PROGRAM QUEUE identity so a dated bracketed wave row ending in bare CURRENT retains its exact wave ID, remains open before merge, and advances only after exact merge-history proof. This prevents the landed P0IMF row from being re-emitted as a synthetic -current wave without treating CURRENT itself as a completion marker.

## Scope

Strict one-blocker successor to P0IMF and predecessor to P0IMRP. Start and compare at exact P0IMF PR #1230 merge d609cf19b9d71411de2bbdfd5eb8aca9e7009e90 in a fresh unique lane/bus. Candidate production scope is only the simple PROGRAM QUEUE identity/completion helpers in commit_executor.py, with focused tests and exact same-wave governance artifacts. Do not change launch, dispatch, Phase A/B, receipt, adapter, model, commit transaction, cleanup, runtime, or substrate behavior.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py (MODIFY) -- strip bare CURRENT only as a queue identity trailer; recognize only a full dated bracketed label as an explicit wave ID eligible for exact merge-history completion; do not classify CURRENT itself as terminal.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py (MODIFY) -- add focused regressions proving an unmerged explicit CURRENT row stays open and the same row advances after its exact merge even when no WaveConfig is tracked; retain generic/prose fail-closed behavior.
- TASKS.md (MODIFY THROUGH PIPELINE) -- record exact P0IMF PR #1230 landing, insert P0IMQR as the current narrow blocker repair, keep P0IMRP immediately next/nonlaunchable until exact P0IMQR merge, keep P0IM behind P0IMRP, and preserve every other TODO/queue row.
- reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json (GENERATED BEFORE REVIEW) -- same-wave indicator.
- reports/deferred/non_blocking/pr1219-p0imqr-current-row-identity-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblockers only.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imqr-current-row-identity-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the exact clean-dev failure from P0IMF: the bracketed dated CURRENT row derives a synthetic -current identity and is reselected after its merge.
2. Extend state-trailer stripping to bare CURRENT for identity parsing only. Leave _SIMPLE_QUEUE_TERMINAL_MARKER_RE unchanged so CURRENT cannot by itself close work.
3. Extract an explicit label identity only when the state-stripped label is one complete bracketed wave ID with a date suffix. Feed that explicit identity into the existing specificity-filtered merge-history proof; never trust arbitrary prose-derived IDs or generic bracket labels.
4. Add a before/after regression with no tracked WaveConfig: before merge the CURRENT row is still the next candidate; after an exact merge message contains that dated wave ID, refresh skips it and selects the next explicit row.
5. Keep existing config/packet matching and precommit-marker behavior unchanged, update TASKS without deleting/reordering successors, and route implementation, independent review, providerless commit, CI, merge, and cleanup only through the pipeline.

## Constraints

- Exact P0IMF PR #1230 merge d609cf19b9d71411de2bbdfd5eb8aca9e7009e90 is the hard dependency; HEAD, origin/dev, comparison_commit, source, and target must all equal it.
- Candidate allowlist is only TASKS.md, commit_executor.py, test_commit_executor_post_merge_cleanup.py, exact same-wave packet/indicator, and optional same-wave deferral report. This external WaveConfig is excluded.
- CURRENT is identity state only and must not be added to terminal/completed markers. Completion still requires an existing terminal marker, exact packet/config evidence, or exact merge-history evidence from a narrowly explicit identity.
- Do not allow free-form queue prose, short/generic bracket labels, normalized prefixes, tracker prose, an untracked external WaveConfig, or the current handoff alone to prove a merge.
- Do not modify P0IMRP receipt surfaces, P0IM model defaults, launch_wave.py, dispatcher, Phase A/B, adapters, candidate authority, recovery, commit transaction/cleanup, runtime, substrate, or unrelated docs/tests.
- Preserve all terminal/old P0IM and legacy PR/worktree evidence. All roles and pager use Codex; commit remains providerless. Nonblockers and edge cases cannot delay P0IMQR.

## Stop conditions

- Halt before launch unless exact P0IMF PR #1230 merge d609cf19b9d71411de2bbdfd5eb8aca9e7009e90 equals origin/dev, HEAD, and comparison_commit, the fresh lane/bus are unique, roles/pager are Codex, and commit is providerless.
- Halt as NEEDS_RESCOPING if closure requires production code outside the simple PROGRAM QUEUE helper area of commit_executor.py, a test outside test_commit_executor_post_merge_cleanup.py, or any launch/dispatch/Phase A/Phase B/receipt/adapter/model/runtime change.
- Halt as DEFECT if an unmerged CURRENT row is skipped, a generic/prose-derived identity can be completed from merge history, P0IMF remains selected after exact merge proof, or the clean committed post-merge package does not select P0IMRP.
- Do not release P0IMRP until deterministic P0IMQR PR, merge SHA, origin/dev equality, post-merge P0IMRP selection proof, and cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- The exact P0IMF TASKS label [PR1219-P0IMF-LAUNCH-BOUND-MODEL-AUTHORITY-FREEZE-2026-08-22] CURRENT derives pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22, never a -current alias.
- With no matching tracked WaveConfig and no merge evidence, a dated explicit CURRENT row remains the next open queue item; CURRENT alone is never completion proof.
- After an exact merge subject/body contains that same dated explicit wave ID, the clean-dev post-merge package skips it and selects pr1219-p0imrp-receipt-model-provenance-2026-08-22.
- Plain prose queue rows, short/generic bracket labels, precommit tracker notes, and normalized prefix collisions remain fail-closed and cannot be skipped from unrelated merge history.
- No launch, dispatch, Phase A/B, receipt, adapter, model, recovery, commit transaction/cleanup, runtime, substrate, or unrelated change enters the candidate.
- Focused tests, exact candidate receipt verification, staged L4 enforcement, independent review, providerless commit, CI, merge, exact dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMQR-CURRENT-ROW-IDENTITY]; wave id `pr1219-p0imqr-current-row-identity-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imqr-current-row-identity-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous narrower packets when the active chain does not converge. P0IMF landed, but its post-merge queue refresh deterministically reselected a synthetic predecessor identity; P0IMQR isolates only that active recurring landing blocker.

FOUNDER_OVERRIDE:pr1219-p0imqr-current-row-identity-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imqr-current-row-identity-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imqr-current-row-identity-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imqr-current-row-identity-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imqr-current-row-identity-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8a6c5cf6379876a73f95505336cb713ede8dda1d673456b1fbc7eb238c8d9677`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0imqr-current-row-identity-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imqr-current-row-identity-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
