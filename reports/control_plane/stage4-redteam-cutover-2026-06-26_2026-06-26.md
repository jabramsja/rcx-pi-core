# Stage4 Redteam Cutover 2026-06-26

Date: 2026-06-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stage4-redteam-cutover-2026-06-26
Phase-A-Lock: LOCKED
Purpose: Red-team the landed Stage 4 engine-loop structuralization and matcher-domain cutover from PR #1150 on current dev after the PR #1152 queue-truth refresh. Verify that matcher-visible numeric facts are structural Mu/StructuralNumbers data, host int and float leaves fail closed in the matcher domain, Python and JavaScript preserve parity, and no new host-authority or test-theater loophole was introduced. If a same-scope defect is reproduced, repair it through the pipeline; otherwise land an evidence-backed report and tracker sync only.

## Scope

Stage 4 red-team and same-scope remediation only. Start from TASKS.md queue truth and current PR #1150/#1152 code truth. Inspect matcher-domain numeric authority, StructuralNumbers representation, Python/JS parity, fail-closed behavior, gates, and proof class. Touch runtime/test/docs/report surfaces only if the red-team reproduces a same-scope defect or needs a durable evidence/report artifact.

Files and surfaces in scope:

- TASKS.md (MODIFY) -- launcher/tracker-sync authority and post-red-team queue status.
- STATUS.md (MODIFY IF NEEDED) -- update next milestone only after red-team result is known.
- mu/docs/core/StructuralNumbers.v0.md (READ/MODIFY IF NEEDED) -- Stage 4 design and implementation proof limits.
- mu/docs/core/NorthStarSemantics.v0.md (READ/MODIFY IF NEEDED) -- semantic policy lock for host-smuggling assessment.
- mu/host/python/rcx_pi/selfhost/eval_seed.py (READ/MODIFY IF DEFECT) -- Python matcher-domain structural numeric behavior.
- mu/host/python/rcx_pi/selfhost/engine_pipeline.py (READ/MODIFY IF DEFECT) -- Python engine-loop cutover path.
- mu/host/python/rcx_pi/selfhost/step_mu.py (READ/MODIFY IF DEFECT) -- Python Stage0/matcher execution boundary.
- mu/host/js/core/bootstrap_core.js (READ/MODIFY IF DEFECT) -- JS structural numeric behavior.
- mu/host/js/engine/kernel.js (READ/MODIFY IF DEFECT) -- JS matcher/kernel cutover path.
- mu/host/js/engine/pipeline.js (READ/MODIFY IF DEFECT) -- JS engine-loop cutover path.
- mu/tests/structural/test_engine_pipeline_discipline.py (MODIFY IF NEEDED) -- fail-closed and no-host-numeric leak evidence.
- mu/tests/structural/test_rcx_engine_workload_contract.py (MODIFY IF NEEDED) -- workload contract evidence.
- mu/tests/parity/test_rcx_engine_workload_contract_parity.py (MODIFY IF NEEDED) -- Python/JS parity evidence.
- mu/tests/l4_gates/test_structural_numbers_compare.py (MODIFY IF NEEDED) -- StructuralNumbers compare evidence.
- mu/tests/l4_gates/test_structural_numbers_compare_js_parity.py (MODIFY IF NEEDED) -- JS compare parity evidence.
- mu/tests/l4_gates/test_structural_numbers_add.py (MODIFY IF NEEDED) -- StructuralNumbers add evidence.
- mu/tests/l4_gates/test_structural_numbers_add_js_parity.py (MODIFY IF NEEDED) -- JS add parity evidence.
- reports/deferred/blocking/ or reports/deferred/non_blocking/ (CREATE IF NEEDED) -- red-team findings by severity and proof class.
- reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json (GENERATED) -- indicator artifact for this red-team wave.
- reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md (GENERATED) -- launcher-created control packet.
- reports/control_plane/stage4-redteam-cutover-2026-06-26_wave_config.json (KEEP) -- launcher config for this wave.
- TASKS.md -- tracker-sync authority. The 2026-06-26 tracker sync note for wave `stage4-redteam-cutover-2026-06-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/stage4-redteam-cutover-2026-06-26_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Re-read TASKS.md, STATUS.md, StructuralNumbers.v0.md, NorthStarSemantics.v0.md, and the PR #1150 Stage 4 packet before making runtime claims.
2. Trace the Python and JS matcher-domain numeric paths from engine-loop counters and matcher inputs through StructuralNumbers compare/add behavior.
3. Prove by direct tests or focused probes that raw host int and float leaves fail closed in the matcher-domain cutover path while StructuralNumbers numerals still match.
4. Compare Python and JavaScript accepted inputs, rejected inputs, terminal shapes, and failure modes for the same vectors.
5. Inspect existing gates for proof-class theater: source-lock only, private-attribute peeks, registry-only parity, smoke-only assertions, or tests that do not exercise the live matcher path.
6. If a same-scope defect is reproduced, fix the narrowest Python/JS parity-preserving runtime or test gap without adding host authority, host fallback, or a codec shim.
7. If no same-scope defect is reproduced, create an evidence-backed non-blocking red-team report that states proof class, direct commands, and remaining proof limits.
8. Collect the L4 indicator artifact, run evidence_command and post_gate_contract_sweep, and leave commit/PR handling to the commit executor.
9. If pipeline launch, review, recovery, or commit fails for structural control-plane reasons, fix or queue that pipeline-hardening fault through the same wave or a precise next-wave packet before advancing.

## Constraints

- Use launch_wave.py, executor_dispatch, Phase A, Phase B, bridge review, and commit executor; do not manually implement, hand-author receipts, hand-author PR updates, or bypass the pipeline.
- This is a red-team wave first: reproduce before claiming, and separate DEFECT, POLICY_BOUND, and DOC_ACCURACY findings.
- Do not add host numeric fallback, host float tolerance, hidden scalar side channels, or a codec shim.
- Do not count source-lock or registry inventory alone as closure for a live runtime/parity claim.
- Python and JavaScript behavior must stay mirrored for every semantic change.
- Do not advance surreals, recursive ordinals, W-types, coinduction, fixpoint, or optimization in this wave.
- Do not manually rebase, refresh, or merge PR #1139 or PR #1140; those remain queued after this red-team under pipeline hardening.

## Stop conditions

- Halt as DEFECT if raw host numeric leaves can still reach matcher-domain semantic truth after the cutover.
- Halt as DEFECT if Python and JavaScript differ on accepted/rejected structural numeric inputs, terminal shapes, or failure modes.
- Halt as POLICY_BOUND if the only passing fix adds host authority, host-only scalar semantics, or the parked codec shim.
- Halt as NEEDS_RESCOPING if the red-team proves the Stage 4 cutover requires a broader Mu projection before same-wave repair can be honest.
- Halt as DOC_ACCURACY if trackers or reports claim stronger proof than the current gates execute.
- Do not commit without indicator collection, evidence_command, bridge review, post-gate sweep or a documented reason it is superseded, and commit-executor handling.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stage4-redteam-cutover-2026-06-26 --output reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`

## Acceptance criteria

- A current-dev red-team receipt exists for the Stage 4 structuralization plus matcher cutover.
- Host int and float matcher-domain leaves are rejected or stall/fail closed by direct execution evidence; StructuralNumbers numerals still match by direct execution evidence.
- Python and JavaScript parity is proven behaviorally for the cutover vectors and the relevant StructuralNumbers compare/add gates.
- Host-semantics and host-authority ratchets show no new authority; any accepted split or decrease is explicitly grounded.
- Theater checks and seed police pass, or any discovered proof-class gap is fixed or recorded in the correct deferred lane.
- TASKS.md remains ordered with pipeline hardening next after Stage 4 red-team, including #1139/#1140 conflict-refresh packets; later mathematical queue items remain unchanged.
- The configured evidence command, post-gate sweep, docs consistency, and L4 indicator collection pass or the wave fails closed with a precise report.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `stage4-redteam-cutover-2026-06-26`.
- Governing packet: this file, `reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md`.
- TASKS.md authority: the 2026-06-26 tracker sync note for wave `stage4-redteam-cutover-2026-06-26` is canonical for this packet's L4 fields.
- Authorization: Founder-directed autonomous queue continuation after PR #1152: Stage 4 red-team is the next authorized item, with implementer=codex, reviewer=codex, pager/autoping/tmux in Codex mode, and no founder decision required unless a real stop condition triggers.

FOUNDER_OVERRIDE:stage4-redteam-cutover-2026-06-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `stage4-redteam-cutover-2026-06-26`
- Active packet: `reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md`
- Indicator artifact: `reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `STATUS.md`
  - `TASKS.md`
  - `reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md`
  - `reports/control_plane/stage4-redteam-cutover-2026-06-26_wave_config.json`
  - `reports/deferred/non_blocking/stage4-redteam-cutover-2026-06-26_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/stage4-redteam-cutover-2026-06-26_redteam_receipt.md`
  - `reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `stage4-redteam-cutover-2026-06-26`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/stage4-redteam-cutover-2026-06-26_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stage4-redteam-cutover-2026-06-26 --output reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stage4-redteam-cutover-2026-06-26 --output reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md. (2) Commit handoff carries 7 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: stage4-redteam-cutover-2026-06-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `stage4-redteam-cutover-2026-06-26`
- Active packet: `reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `04561b4b00be61d088bc3a85981d23ce43791f12e9f8dd1a5c38331453f28f3b`
- Indicator artifact: `reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stage4-redteam-cutover-2026-06-26 --output reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md. (2) Commit handoff carries 7 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`
- Current staged files:
  - `STATUS.md`
  - `TASKS.md`
  - `reports/control_plane/stage4-redteam-cutover-2026-06-26_2026-06-26.md`
  - `reports/control_plane/stage4-redteam-cutover-2026-06-26_wave_config.json`
  - `reports/deferred/non_blocking/stage4-redteam-cutover-2026-06-26_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/stage4-redteam-cutover-2026-06-26_redteam_receipt.md`
  - `reports/l4_wave_indicators/stage4-redteam-cutover-2026-06-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
