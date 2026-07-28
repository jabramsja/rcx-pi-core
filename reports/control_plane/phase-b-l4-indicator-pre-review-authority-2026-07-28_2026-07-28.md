# Phase B L4 Indicator Pre-Review Authority

Date: 2026-07-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PIPELINE-RECOVERY]
Wave ID: phase-b-l4-indicator-pre-review-authority-2026-07-28
Phase-A-Lock: LOCKED
Purpose: Land only the converged Phase B pre-review package authority: stage the current candidate before canonical same-wave indicator collection, preserve exact-scope authority across restart, require canonical same-wave TASKS authority, and atomically refresh packet scope before every bridge review.

## Scope

Exactly one Phase B pre-review package authority and its focused test module, plus launcher-generated tracker, packet, same-wave indicator, and optional standard reviewer nonblocker report. Recovery, QUESTION lifecycle, dispatcher, commit, provider, pager production behavior, runtime, substrate, parity, and Mu are excluded.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py (MODIFY) -- current-package staging, same-wave indicator collection, exact-scope compatibility, canonical tracker gating, and atomic packet-scope refresh before bridge review
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- focused ordering, restart compatibility, authority, atomicity, failure, and hermetic pager-boundary regressions
- TASKS.md (GENERATED UPDATE) -- launcher-built tracker authority
- reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md (GENERATED) -- launcher-built governing packet
- reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json (GENERATED) -- canonical same-wave indicator
- TASKS.md -- tracker-sync authority. The 2026-07-28 tracker sync note for wave `phase-b-l4-indicator-pre-review-authority-2026-07-28` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/phase-b-l4-indicator-pre-review-authority-2026-07-28_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reproduce the pre-review ordering defect from current origin/dev code before editing; do not copy or cherry-pick the cancelled predecessor candidate.
2. Bootstrap the broken ordering exactly once with launcher-owned artifacts: run this exact config without dispatcher launch to generate TASKS.md and the packet, stage exactly those two launcher-generated files without changing their bytes, then rerun the same config so launch_wave generates and stages the same-wave indicator before dispatcher launch. No source, indicator content, commit, push, PR, or merge may be produced manually.
3. Factor one Phase B pre-review preparation helper around the existing canonical collector and packet-scope machinery; do not add another collector or artifact authority.
4. At initial and bridge-fix reviews, private-attribute remediation reviews, and NEEDS_PHASE_B reentry reviews: reconcile exact scope, stage the current candidate, collect and stage the canonical same-wave indicator, refresh and stage packet scope, then invoke the reviewer.
5. Return a typed Phase B error before reviewer invocation if exact-scope reconciliation, candidate staging, canonical tracker authority, indicator collection, indicator staging, or packet refresh fails.
6. Preserve every historical unversioned generated refresh block's exact-scope interpretation. Determine authority from the original packet before replacement, and add an explicit marker only to newly generated broad-package refresh snapshots so restart does not mistake them for an exact lock.
7. For launcher-rendered packets whose acceptance declares that the final staged set contains exactly the authorized package, treat Files and surfaces in scope as the exact authority and include the canonical optional reviewer-nonblocker path when the packet authorizes that generated artifact.
8. Require the existing canonical same-wave TASKS tracker predicate before collection. Mere TASKS.md existence is not authority.
9. Write refreshed governing packet content through same-directory temporary-file, flush/fsync, mode preservation, and atomic replacement so interruption cannot truncate the packet.
10. Make test_run_phase_b_package_prefers_reclassified_packet_over_stale_routing_class hermetic by mocking the existing _emit_phase_b_event pager boundary; the focused pytest module must not contact a live Codex pager or app server.
11. Keep existing post-convergence pre-supervisor collection and commit_executor Step 5 unchanged as later package and commit-time authorities.
12. Run only the configured evidence during implementation; leave staged L4, final gates, receipts, commit, push, PR, review, merge, and cleanup to the pipeline.

## Constraints

- Only phase_b_executor.py and test_phase_b_executor.py may be hand-authored. TASKS.md, packet, indicator, optional nonblocker report, post-bootstrap staging, handoff, receipt, commit, push, PR, and merge remain pipeline-owned.
- The one bootstrap exception is limited to git-adding the launcher-generated TASKS.md and same-wave packet before the same-config launch pass; no generated bytes, source file, indicator content, commit, push, PR, or merge may be produced manually.
- Do not add, change, or remove terminal QUESTION, QUESTION_FOR_FOUNDER_CHECKPOINT, question checkpoint helpers, _save_state, _load_state, _clear_state, bridge-fix checkpoint schemas, crash-recovery, answer, acknowledgement, pager-delivery, planless-recovery, dispatcher, or recovery-gate behavior. Preserve origin/dev behavior for those surfaces.
- Do not edit launch_wave.py, collect_l4_wave_indicators.py, enforce_l4_execution_contract.py, commit_executor.py, executor_dispatch.py, recovery_gate.py, provider/role configuration, production pager code, timeout budgets, runtime, substrate, seed, parity, or Mu code.
- A test-only pager isolation fix is authorized only in test_phase_b_executor.py; it must not change production pager semantics.
- Do not weaken the L4 requirement, make a missing indicator non-blocking, or invoke a reviewer on a mechanically incomplete package.
- Use only the existing canonical collector, canonical same-wave tracker predicate, and same-wave artifact path.
- A pre-existing recovery/checkpoint finding is blocking for this wave only if this candidate causes or worsens it or makes an acceptance criterion unprovable. Otherwise preserve its class and severity but rescale it to a separate-wave deferred item; do not implement it in this packet.

## Stop conditions

- Stop as NEEDS_RESCOPING before changing any production or test file outside the two declared paths.
- Stop as NEEDS_RESCOPING if a finding requires terminal-QUESTION, recovery/checkpoint lifecycle, dispatcher, recovery-gate, commit, provider, or production pager behavior.
- Stop if any Phase B review seam can invoke a reviewer before the current candidate and same-wave indicator are staged.
- Stop before reviewer invocation on any reconciliation, staging, tracker-authority, collection, packet-refresh, or exact-scope failure.
- Stop if any existing unversioned refresh packet changes its exact-scope interpretation.
- Stop if the focused test module can reach a live pager/app-server boundary.
- Stop on any configured evidence, independent review, final gate, commit, PR, merge, or fresh-origin verification failure.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Initial, bridge-fix, private-attribute, and NEEDS_PHASE_B reentry reviews all receive a staged package containing the current candidate, canonical same-wave indicator, and refreshed packet scope.
- The collector runs only after the current candidate is staged, and each bridge-fix round regenerates the artifact before its next review.
- Canonical same-wave TASKS authority is required before collection; missing authority returns a typed error with zero collector and reviewer calls.
- Every historical packet containing an unversioned Phase B refresh block retains its pre-wave exact-scope parse; newly generated broad snapshots are explicitly marked and remain non-authoritative on restart.
- Launcher-rendered exact-final-set packets parse Files and surfaces in scope as exact and include the canonical optional reviewer-nonblocker path without admitting unrelated read-only or validation references.
- A simulated interruption during packet refresh leaves the original governing packet byte-for-byte intact and returns a typed error before reviewer launch.
- The configured full Phase B test module is hermetic at the pager boundary and completes without contacting a live Codex pager or app server.
- No terminal-QUESTION, recovery/checkpoint, dispatcher, recovery-gate, commit, provider, or production pager behavior differs from origin/dev; the staged diff proves the excluded recovery symbols and paths are unchanged.
- The existing post-convergence pre-supervisor path and commit Step 5 remain unchanged.
- The final staged set contains exactly TASKS.md, the two declared source/test paths, the generated packet, and the generated same-wave indicator, plus only the standard generated reviewer nonblocker report if one is required.
- Every live LLM boundary is observed as Codex gpt-5.6-sol with ultra effort, and the deterministic pipeline alone commits, pushes, opens, reviews, merges, and verifies the wave.

## Grounding / Authorization

- Task: [PIPELINE-RECOVERY]; wave id `phase-b-l4-indicator-pre-review-authority-2026-07-28`.
- Governing packet: this file, `reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md`.
- TASKS.md authority: the 2026-07-28 tracker sync note for wave `phase-b-l4-indicator-pre-review-authority-2026-07-28` is canonical for this packet's L4 fields.
- Authorization: Founder-directed narrow structural pipeline repair after R4 proved that mixing terminal-QUESTION recovery lifecycle into the predecessor packet caused scope oscillation.

FOUNDER_OVERRIDE:phase-b-l4-indicator-pre-review-authority-2026-07-28

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `phase-b-l4-indicator-pre-review-authority-2026-07-28`
- Active packet: `reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `TASKS.md`
  - `reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md`
  - `reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json`
  - `reports/deferred/non_blocking/phase-b-l4-indicator-pre-review-authority-2026-07-28_bridge_nonblockers.md`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `phase-b-l4-indicator-pre-review-authority-2026-07-28`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/phase-b-l4-indicator-pre-review-authority-2026-07-28_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-l4-indicator-pre-review-authority-2026-07-28 --output reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md`, `reports/deferred/non_blocking/phase-b-l4-indicator-pre-review-authority-2026-07-28_bridge_nonblockers.md`, `reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: phase-b-l4-indicator-pre-review-authority-2026-07-28.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-l4-indicator-pre-review-authority-2026-07-28`
- Active packet: `reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `dc765cf37c43e5f0a1ea38518a2ef6034e3c63bf037ed463d1a0055a2dd444db`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md`, `reports/deferred/non_blocking/phase-b-l4-indicator-pre-review-authority-2026-07-28_bridge_nonblockers.md`, `reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-l4-indicator-pre-review-authority-2026-07-28_2026-07-28.md`
  - `reports/deferred/non_blocking/phase-b-l4-indicator-pre-review-authority-2026-07-28_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-b-l4-indicator-pre-review-authority-2026-07-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
