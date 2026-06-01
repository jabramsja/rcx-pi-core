# Recovery Gate Classifier Fix 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: recovery-gate-classifier-fix-2026-06-01
Class: L4_ENABLER
Target-Gate: G8
Phase-A-Lock: LOCKED
Purpose: Fix a false-positive in the recovery_gate failure classifier (mu/tools/executors/recovery_gate.py). The predicate _looks_like_commit_supervisor_out_of_wave_tasks_tracker_note builds a lowercased signal string from the supervisor reason+detail then checks positive substring markers (e.g. 'out-of-wave', 'tracker note') with NO negation awareness, so a Codex pre-commit-supervisor NEEDS_PHASE_B carrying a FAVORABLE reason whose detail says 'staged TASKS.md diff contains no proven out-of-wave tracker-note additions' is MISCLASSIFIED as the commit_supervisor_out_of_wave_tasks_tracker_note class. The paired auto-fix fix_commit_supervisor_out_of_wave_tasks_tracker_note then finds nothing to remove (the staged note is the correct same-wave one), returns no_out_of_wave_tasks_tracker_addition, recovered=False, and the wave fails closed -- wasting a full Phase-A->B->commit cycle. Root motivation: learning.md 2026-06-01 (lane-1 standalone-commit-evidence-guard rerun). Make the classifier negation-aware and let the auto-fix degrade to Phase-B re-entry instead of fail-closed when there is nothing to remove.

## Scope

Files/directories in scope:

- `mu/tools/executors/recovery_gate.py` — the classifier predicate `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` and the paired auto-fix `fix_commit_supervisor_out_of_wave_tasks_tracker_note`.
- `mu/tests/tools/test_recovery_gate.py` — the regression test proving the classifier paths (false-positive, genuine-positive, mixed-signal) and the auto-fix Phase-B re-entry degrade.
- This governing packet plus the wave's tracker note and indicator artifact under `reports/` (control-plane records only).

Tooling-only under `mu/tools/executors/`; touches no runtime dir (L4_ENABLER). Code is cited by function name only, no line numbers.

- `reports/deferred/non_blocking/recovery-gate-classifier-fix-2026-06-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks (mirrors the authorizing tracker note's evidence_delta):

1. Make `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` negation-aware **with anchored, not blanket, suppression**. The predicate joins `_summarize_result_reason`, `_extract_classifier_signal`, and every candidate summary into one lowercased `signal`; a single absence phrase anywhere in that aggregate MUST NOT veto classification by itself. Instead, anchor the negation to the out-of-wave marker occurrence: an out-of-scope marker (e.g. 'out-of-wave', 'out of wave') counts as genuine evidence only when it is NOT governed by a negation cue in a bounded preceding window ('no', 'no proven', 'contains no', 'without', 'not', 'free of', 'zero'). Acceptable equivalent: evaluate the out-of-scope / tracker / staged markers per text-part (reason, classifier signal, each candidate) so a negation in one part cannot suppress genuine evidence carried by another. Precedence invariant: if any un-negated out-of-wave occurrence co-occurs with the required tracker-note and staged markers, classify positive even when a negated absence phrase (e.g. 'no proven out-of-wave tracker-note additions') is also present elsewhere in the aggregate; return False only when EVERY out-of-scope occurrence is negated. This removes the favorable-NEEDS_PHASE_B false positive without dropping genuine mixed-signal positives.
2. Degrade `fix_commit_supervisor_out_of_wave_tasks_tracker_note` to Phase-B re-entry on the no-removal branch (`not removals`) instead of the fail-closed no-op (`_fix_result(False, "no_out_of_wave_tasks_tracker_addition", ...)`). Arm re-entry through the existing proven channel `fix_post_reentry_needs_phase_b` already uses — seed the Phase-B resume-state file resolved by `_bus_path(repo_root, "executors", "phase_b_state.json")` (`completed_step="needs_phase_b_reentry"`, plan_path, wave_id, bridge_rounds, reentry_findings) and return `fixed=True` with a `resume_phase_b_reentry`(-style) action — by delegating to it or factoring a shared helper; do NOT invent a new re-entry channel. Derive plan_path/wave_id from the same result the classifier consumed; if no re-entry target (plan_path) can be resolved, keep a fail-closed no-op as the explicit fallback (re-entry cannot be armed without a target).
3. Add regression tests in `mu/tests/tools/test_recovery_gate.py` (named so the `-k out_of_wave` evidence selector exercises each) covering: (a) favorable NEEDS_PHASE_B with the 'no proven out-of-wave...' detail is NOT classified as out_of_wave; (b) a genuine out-of-wave tracker-note addition still IS classified and the auto-fix removes+restages it (`remove_out_of_wave_tasks_tracker_note`, `fixed=True`); (b') mixed-signal — an aggregate carrying BOTH a negated absence phrase AND a genuine un-negated out-of-wave tracker-note addition still classifies positive and is fixed (guards against a blanket-veto regression); (c) the no-removal branch with a resolvable re-entry target arms Phase-B re-entry — asserts `fixed=True`, the `resume_phase_b_reentry`(-style) action, and that the `_bus_path(repo_root, "executors", "phase_b_state.json")` resume-state file is seeded — rather than the fail-closed no-op.

Verified against current code (code truth over packet wording): `_looks_like_commit_supervisor_out_of_wave_tasks_tracker_note` has no negation handling, and `fix_commit_supervisor_out_of_wave_tasks_tracker_note` still returns the `no_out_of_wave_tasks_tracker_addition` fail-closed no-op on the `not removals` branch. All three items remain pending.

## Constraints

Not in scope:

- No runtime/substrate edits: do not touch `mu/host/python/rcx_pi/selfhost/`, `mu/host/js/`, seeds, registries, or any L4 runtime dir. An L4_ENABLER MUST NOT touch runtime dirs.
- No change to the upstream pre-commit / post-merge supervisor or to the reason/detail contract it emits; this wave only fixes consumption of that signal in recovery_gate.
- No generalization of the negation guard to other recovery classifier predicates or auto-fixes in this wave; scope is the single out-of-wave tracker-note class and its paired auto-fix.
- No line numbers when citing code; function names only.
- No new source or test files: no new runtime/tooling modules and no new test files beyond additions to the existing `mu/tests/tools/test_recovery_gate.py`; do not create parallel packets or split the wave. This does NOT bar the wave's required control-plane records under `reports/` (Scope, above) — this governing packet, its tracker note, and the indicator artifact `reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json` that acceptance collects are records, not source/test surface, and are expected to be created.

## Stop conditions

- Stop and escalate if the fix would require touching a runtime dir or adding host-only semantics — that exits L4_ENABLER scope.
- Stop if, after the anchored negation guard, the genuine-positive path (a real out-of-wave tracker-note addition) — including the mixed-signal case where a genuine addition co-occurs with a negated absence phrase — can no longer be classified and fixed; that is a regression, not a fix.
- Stop and request a founder decision if the Phase-B re-entry degrade would change commit-gate or recovery semantics for any recovery class other than the out-of-wave tracker-note class.
- Stop after the bounded two-function fix plus its regression test; do not expand into a broader recovery_gate refactor.

## Acceptance criteria

- Wave evidence_command passes: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k out_of_wave` (the new tests are named so `-k out_of_wave` selects every path below).
- Classifier paths proven: false-positive (favorable NEEDS_PHASE_B + 'no proven out-of-wave...' detail -> NOT out_of_wave); genuine-positive (real out-of-wave tracker-note addition -> classified); and mixed-signal (aggregate carrying BOTH a negated absence phrase AND a genuine un-negated out-of-wave tracker-note addition -> still classified positive), proving the negation handling is anchored, not a blanket aggregate veto.
- Auto-fix no-removal branch ARMS Phase-B re-entry (not fail-closed): with a resolvable re-entry target, `fix_commit_supervisor_out_of_wave_tasks_tracker_note` returns `fixed=True` with a `resume_phase_b_reentry`(-style) action and seeds the resume-state file resolved by `_bus_path(repo_root, "executors", "phase_b_state.json")` (the same file `fix_post_reentry_needs_phase_b` seeds), replacing the prior `no_out_of_wave_tasks_tracker_addition`/`fixed=False` no-op for that case.
- Auto-fix genuine-removal branch still removes+restages the proven out-of-wave addition (`remove_out_of_wave_tasks_tracker_note`, `fixed=True`), proving the re-entry degrade did not cannibalize the removal path.
- Indicator artifact collected: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id recovery-gate-classifier-fix-2026-06-01 --output reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json`.
- No runtime dir touched (L4_ENABLER contract); tooling-only, so L3 Python/JS parity is not implicated.

## Grounding / Authorization

- Authorized by the `TASKS.md` tracker sync note (2026-06-01, recovery-gate-classifier-fix-2026-06-01) under task `[NEXT-CODEX-POST-REDTEAM]`: Class L4_ENABLER, target_gate_id G8, governing Packet `reports/control_plane/recovery_gate_classifier_fix_2026-06-01.md` (this file).
- Governing parent: `[NEXT-CODEX-POST-REDTEAM]` (UNPARKED 2026-03-28, founder-authorized); tracked packet `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`. The active [FOUNDER-ORDERED-REDTEAM-WAVE-QUEUE] directive authorizes a same-wave mechanical/automated fix in a pipeline surface (here: recovery) as an unblocker.
- FOUNDER_OVERRIDE:recovery-gate-classifier-fix-2026-06-01
- Authorization: standing pipeline-bug-fix authorization per memory `feedback_autonomous_executor_fix.md` — recovery_gate.py is a pipeline/control-surface bug fix, so the same-wave override is mechanically derivable by commit automation from the wave-bound FOUNDER_OVERRIDE above (commit-gate + pre-push adjacency-cap clearance).
- L4 metadata (mirrors the authorizing tracker note): primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.

## Request from Post-Merge Supervisor

Fix a false-positive in the recovery_gate failure classifier (mu/tools/executors/recovery_gate.py). The predicate _looks_like_commit_supervisor_out_of_wave_tasks_tracker_note builds a lowercased signal string from the supervisor reason+detail then checks positive substring markers (e.g. 'out-of-wave', 'tracker note') with NO negation awareness, so a Codex pre-commit-supervisor NEEDS_PHASE_B carrying a FAVORABLE reason whose detail says 'staged TASKS.md diff contains no proven out-of-wave tracker-note additions' is MISCLASSIFIED as the commit_supervisor_out_of_wave_tasks_tracker_note class. The paired auto-fix fix_commit_supervisor_out_of_wave_tasks_tracker_note then finds nothing to remove (the staged note is the correct same-wave one), returns no_out_of_wave_tasks_tracker_addition, recovered=False, and the wave fails closed -- wasting a full Phase-A->B->commit cycle. Root motivation: learning.md 2026-06-01 (lane-1 standalone-commit-evidence-guard rerun). Make the classifier negation-aware and let the auto-fix degrade to Phase-B re-entry instead of fail-closed when there is nothing to remove.

Routed next-candidate:
recovery-gate-classifier-fix-2026-06-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `recovery-gate-classifier-fix-2026-06-01`
- Active packet: `reports/control_plane/recovery_gate_classifier_fix_2026-06-01.md`
- Indicator artifact: `reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery_gate_classifier_fix_2026-06-01.md`
  - `reports/deferred/non_blocking/recovery-gate-classifier-fix-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `recovery-gate-classifier-fix-2026-06-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/recovery-gate-classifier-fix-2026-06-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-gate-classifier-fix-2026-06-01`
- Active packet: `reports/control_plane/recovery_gate_classifier_fix_2026-06-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `bda7556757d0d56ddfa40b7857fffa9fad6c3452177f48a6183462b8c53e7cde`
- Indicator artifact: `reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/recovery_gate_classifier_fix_2026-06-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery_gate_classifier_fix_2026-06-01.md`
  - `reports/deferred/non_blocking/recovery-gate-classifier-fix-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-gate-classifier-fix-2026-06-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
