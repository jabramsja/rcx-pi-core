# PR 1219 P0IC4R TASKS Base Authority Recovery 2026-08-21

Date: 2026-08-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IC4R-TASKS-BASE-AUTHORITY-RECOVERY]
Wave ID: p0ic4r-tasks-base-authority-recovery-2026-08-21
Phase-A-Lock: LOCKED
Purpose: From exact P0IC3 merge 7f13c4f647db9f8aa7f9a07cf8a54d065b27d900 (PR #1224), land only the Step-14 convergence prerequisite for preserved P0IA PR #1223. This short-identity recovery supersedes the stopped nonconvergent P0IC4 launch while preserving its implementation atom: exact stage-3 TASKS whole-document authority, fully validated P0IA tracker records only, unchanged generic tracker/growth-cap behavior, and fail-closed exact P0IA identity gates. Use one Phase-A-safe canonical packet from WaveConfig through TASKS, review/lock, Phase B, commit, and merge.

## Scope

Strict successor to P0IC3 and immediate prerequisite to preserved P0IA PR #1223. Start from exact P0IC3 merge 7f13c4f647db9f8aa7f9a07cf8a54d065b27d900 in a fresh unique lane and bus. Scope only the Step-14 TASKS conflict resolver, its existing focused test module, complete 60-row TASKS reconciliation, one canonical packet, one indicator, and an optional same-wave nonblocker report. The stopped P0IC4 lane, root WaveConfigs, and P0IA preservation state remain external inputs.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py (MODIFY) -- retain generic tracker-note-only and growth-cap behavior, then add one exact-state P0IA base-authority resolver threaded from normal Step 14.
- mu/tests/tools/test_commit_executor_step14_autoresolve.py (MODIFY) -- reproduce the P0IA-shaped older-queue/current-superset merge and cover exact preservation plus all negative guards in the existing suite.
- TASKS.md (MODIFY THROUGH PIPELINE) -- mark P0IC3 landed, place P0IC4R immediately before P0IA, retain every active TODO in relative order as exactly 60 unique sequential rows 0 through 59, and add the normalized-packet single-authority recurrence obligation to the existing deterministic launch-wave builder row.
- reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md (GENERATED) -- sole governing same-wave packet reviewed, locked, and handed to Phase B.
- reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json (GENERATED) -- same-wave indicator.
- reports/deferred/non_blocking/p0ic4r-tasks-base-authority-recovery-2026-08-21_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave reviewer deferrals; nonblockers cannot widen or delay P0IC4R.
- TASKS.md -- tracker-sync authority. The 2026-08-21 tracker sync note for wave `p0ic4r-tasks-base-authority-recovery-2026-08-21` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/p0ic4r-tasks-base-authority-recovery-2026-08-21_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Preserve the existing generic tracker-note-only TASKS resolver and growth-cap resolver behavior. Invoke the special atom only after tracker-only resolution refuses and only when normal Step 14 supplies exact active P0IA identity.
2. Require exact active wave roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20, PR 1223, base dev, target branch jabramsja/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20-restart-2026-08-21, and conflicted paths exactly [TASKS.md]. Never infer authority from prose or a branch substring.
3. Read exact UTF-8 regular stage-2 and stage-3 TASKS blobs from the active merge index. Treat stage 3 as the entire authoritative document; do not semantically merge conflict blocks or preserve stale feature queue prose.
4. Require exactly one canonical P0IA tracker note in stage 2 and validate its wave, L4_ENABLER class, G8 gate, exact packet, indicator, founder token, and existing tracker-note contract. Admit only strictly parsed same-wave follow-ups that explicitly preserve phase/task state and whose normalized paths remain within P0IA's authorized touched scope.
5. If stage 3 already contains a P0IA record, require byte equality and deduplicate it; differing same-wave truth fails closed. Insert only missing validated P0IA records in deterministic origin-first order at the canonical tracker ledger location.
6. Require the stage-3 queue to be exactly the P0IC4R 60-row sequential unique contract. Prove the final PROGRAM QUEUE is byte-identical to stage 3 and that removing exactly the inserted P0IA records reproduces stage-3 bytes before atomically replacing the conflicted file.
7. Add an actual temporary-Git merge regression shaped like P0IA and negative controls for wave/PR/base/branch mismatch, a second conflict, missing/non-UTF8 stage blobs, malformed/duplicate/foreign/differing records, phase-changing or outside-scope follow-ups, invalid queue numbering/order/count, malformed markers, and unrelated conflicts. Preserve every existing generic resolver regression.
8. Reconcile TASKS to exactly 60 rows: rows 0-3 P0IC0-P0IC3 LANDED; row 4 exact [ROLES-ALL-CODEX-PR1219-P0IC4R-TASKS-BASE-AUTHORITY-RECOVERY] first; row 5 preserved P0IA PR #1223 blocked pending P0IC4R and not falsely landed; row 6 exact [ROLES-ALL-CODEX-PR1219-P0IAH-CANDIDATE-AUTHORITY-TRUST-ORDERING-HARDENING]; row 7 P0IM; row 18 P5; row 19 exact [LAUNCH-WAVE-DETERMINISTIC-CANDIDATE-CARRY-FORWARD-BUILDER]; row 20 exact [PHASE-A-POST-REMEDIATION-LINE-REF-PREBRIDGE-GUARD]; row 21 PIPELINE-FIX-61; row 59 MU-OPTIMIZATION-LAST. Preserve every intervening TODO in relative order.
9. At row 19, preserve the existing deterministic candidate/hunk-ledger builder and add a bounded recurrence requirement: launch preparation must produce one canonical Phase-A-safe packet identity, or fail before dispatch; reviewed lock authority and Phase B handoff may never split across normalized alias/source files. This queued builder work must not enter or delay P0IC4R/P0IA.
10. Run the complete Step-14 and land-stranded regression modules, host-semantics ratchet, staged L4 enforcement, then route implementation, review, providerless commit, CI, merge, and cleanup only through the normal all-Codex pipeline.

## Constraints

- P0IC3 landed through PR #1224 at exact merge 7f13c4f647db9f8aa7f9a07cf8a54d065b27d900. P0IC4R must start from refreshed origin/dev at that exact commit in a fresh unique lane and bus.
- The exact candidate scope contains only TASKS.md; mu/tools/executors/commit_executor.py; mu/tests/tools/test_commit_executor_step14_autoresolve.py; the one same-wave packet; the same-wave indicator; and, only if produced, the exact same-wave deferred nonblocker report. mu/tests/tools/test_land_stranded_pr.py is validation-only and must not be modified.
- Do not modify recovery_gate.py, executor_dispatch.py, launch_wave.py, phase_a_executor.py, phase_b_executor.py, bridge supervisor/client, growth-cap resolver semantics, role/model configuration, runtime, substrate, P0IA candidate files, or unrelated hardening.
- Current dev is whole-document TASKS authority only inside this exact P0IA recovery atom. Preserve no feature semantic prose and carry only fully validated P0IA tracker records.
- Use reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md as the sole packet identity in WaveConfig output, TASKS tracker authority, persisted routing, Phase A review/lock, and Phase B input. Do not create or route a sibling authority packet.
- P0IC4R inherits only the declared pre-P0IA review-authority waiver. It waives no implementation review, scope, tests, staged L4, providerless commit, CI, or merge gate.
- Do not launch, resume, unstage, edit, reset, commit, push, or merge the preserved P0IA lane while P0IC4R is in flight. Nonblockers and unproved edge cases cannot delay P0IC4R.

## Stop conditions

- Halt before launch unless origin/dev equals exact P0IC3 merge 7f13c4f647db9f8aa7f9a07cf8a54d065b27d900, the lane and bus are fresh/unique, all model-bearing roles and pager route are Codex, commit is providerless, and setup-only routing keeps the configured tracked_packet unchanged without recovery_authority or authority_tracked_packet.
- Halt as NEEDS_RESCOPING if closure requires a production file outside commit_executor.py, a test file outside the existing Step-14 autoresolve suite, dispatcher/recovery/Phase B changes, a manual P0IA candidate edit, or generalized semantic merge authority.
- Halt and leave the merge unmodified if exact P0IA wave/PR/base/branch identity is absent, any second path conflicts, a stage blob is missing or malformed, canonical tracker records cannot be validated/deduped, the stage-3 queue differs from the exact 60-row contract, or resolved-minus-insertions differs byte-for-byte from stage 3.
- Halt as a launch-input identity defect if TASKS, WaveConfig, persisted routing, reviewed/locked plan, or Phase B names another packet or produces authority_tracked_packet.
- Do not release P0IA until exact P0IC4R PR, merge SHA, origin/dev equality, and cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`

## Acceptance criteria

- Existing tracker-note-only TASKS merge behavior and growth-cap mechanical resolution remain unchanged and green.
- A P0IA-shaped temporary repository conflict resolves deterministically to exact stage-3 TASKS bytes plus the validated P0IA canonical note and phase-neutral same-wave follow-ups exactly once, then continues through Step 14 under action tasks_md_base_authority_resolved.
- Any identity mismatch, second conflict, missing stage, malformed/foreign/differing record, phase-changing or outside-scope follow-up, invalid 60-row queue, malformed conflict, or unrelated conflict fails closed without modifying TASKS.
- Candidate TASKS contains exactly 60 unique sequential rows 0 through 59 with P0IC3 landed, P0IC4R first, P0IA then exact P0IAH then P0IM, P5 row 18, exact deterministic builder row 19 with the packet-identity recurrence obligation, exact line-reference guard row 20, PIPELINE-FIX-61 row 21, every prior TODO retained in relative order, and MU-OPTIMIZATION-LAST row 59.
- The P0IC4R tracker note, WaveConfig, persisted routing, reviewed/locked plan, Phase B plan, handoff, packet refresh, and committed packet all use the same canonical packet path; no recovery_authority or authority_tracked_packet exists.
- The preserved P0IA lane remains at HEAD 3d57747ede2e8e8da35b7f11ea03a55a1fca9fb9 with exactly five staged paths and cached binary-diff SHA-256 37d1db3a5b47c11f2513f41ce0feab5f60123a036ea9d51e9ea89f9d6d7c803f throughout P0IC4R.
- Complete focused tests, host-semantics ratchet, staged L4 enforcement, independent review, providerless commit, CI, deterministic merge, exact origin/dev proof, and cleanup are green.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IC4R-TASKS-BASE-AUTHORITY-RECOVERY]; wave id `p0ic4r-tasks-base-authority-recovery-2026-08-21`.
- Governing packet: this file, `reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md`.
- TASKS.md authority: the 2026-08-21 tracker sync note for wave `p0ic4r-tasks-base-authority-recovery-2026-08-21` is canonical for this packet's L4 fields.
- Authorization: Founder directed autonomous convergence, narrower packets when a wave diverges, complete TASKS synchronization, deterministic launch-wave work in its queued builder, and no delay for nonblockers or edge cases.

FOUNDER_OVERRIDE:p0ic4r-tasks-base-authority-recovery-2026-08-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `p0ic4r-tasks-base-authority-recovery-2026-08-21`
- Active packet: `reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md`
- Indicator artifact: `reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md`
  - `reports/deferred/non_blocking/p0ic4r-tasks-base-authority-recovery-2026-08-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `p0ic4r-tasks-base-authority-recovery-2026-08-21`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/p0ic4r-tasks-base-authority-recovery-2026-08-21_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id p0ic4r-tasks-base-authority-recovery-2026-08-21 --output reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md`, `reports/deferred/non_blocking/p0ic4r-tasks-base-authority-recovery-2026-08-21_bridge_nonblockers.md`, `reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: p0ic4r-tasks-base-authority-recovery-2026-08-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `p0ic4r-tasks-base-authority-recovery-2026-08-21`
- Active packet: `reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8ad7a3604448dc037e67f035bdab26f98397230c5dad5353da3ac6187dd35934`
- Indicator artifact: `reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md`, `reports/deferred/non_blocking/p0ic4r-tasks-base-authority-recovery-2026-08-21_bridge_nonblockers.md`, `reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/p0ic4r-tasks-base-authority-recovery-2026-08-21_2026-08-21.md`
  - `reports/deferred/non_blocking/p0ic4r-tasks-base-authority-recovery-2026-08-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/p0ic4r-tasks-base-authority-recovery-2026-08-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
