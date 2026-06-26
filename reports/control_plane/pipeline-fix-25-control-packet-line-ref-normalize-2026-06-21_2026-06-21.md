# NEXT-CODEX-POST-REDTEAM - normalize control-packet line-refs (strip ext-colon-digit to name-only) before the pre-finalization line-ref lint instead of stranding the wave

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21
Phase-A-Lock: LOCKED
Purpose: STRUCTURAL recovery/pipeline hardening (founder-directed: always harden the pipeline when it breaks so the same failure self-heals). VERIFIED ROOT CAUSE: a Phase-B implementer addressing a finding that cites code or docs by line writes an extension-colon-digit reference (for example a TASKS.md line citation) into the control packet. The pre-finalization control-packet line-ref lint (`_control_packet_line_ref_lint_error` in phase_b_executor, the checker built by `_load_line_ref_checker` via `find_offending_lines`) then HARD-FAILS with result step `control_packet_line_ref_lint`; the wave strands and tier-3 recovery cannot remove the reference because control-plane artifacts are edit-gated, so recovery exhausts. Observed: a Stage0 wave stranded because its packet Purpose line carried a TASKS.md line citation the implementer added. FIX: the PRODUCING executor (phase_b) NORMALIZES the control packet before the line-ref lint -- it rewrites any extension-colon-digit reference down to the extension/name-only form (dropping the colon-digit), writes the packet back, then lints. An implementer-added line-ref is auto-corrected to the compliant name-only form instead of stranding the wave; the no-line-refs invariant is preserved (the packet ends line-ref-free). Only the failure mode changes (strand-and-exhaust -> auto-normalize). This is allowed because phase_b is the producing executor of its own packet (not an external artifact edit).

## Scope

Normalize control-packet line-refs (strip extension-colon-digit to name-only) in the producing executor phase_b before the pre-finalization line-ref lint, so an implementer-added line-ref self-heals instead of stranding the wave. Executor tooling + an existing test file; no runtime dirs; no new test file. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py (MODIFY) -- add a normalizer that rewrites any extension-colon-digit reference in the control packet to the name-only form (drop the colon-digit) and writes the packet back, invoked immediately BEFORE `_control_packet_line_ref_lint_error` at each pre-finalization line-ref-lint site, so the lint sees a normalized (line-ref-free) packet. Preserve the lint as the post-normalization guard (it still fails closed on anything the normalizer cannot fix).
- mu/tests/tools/test_phase_b_executor.py (MODIFY -- existing file, do NOT create a new test file) -- add a regression: a control packet containing an extension-colon-digit reference (e.g. a TASKS.md line citation) is normalized to name-only and `_control_packet_line_ref_lint_error` then returns no error (no strand).
- reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-21 tracker sync note for wave `pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read `_control_packet_line_ref_lint_error` and the checker from `_load_line_ref_checker` / `find_offending_lines`, and every pre-finalization site in phase_b_executor that calls the lint and sets result step `control_packet_line_ref_lint`.
2. Add a normalizer (a regex that rewrites extension-colon-digit references to name-only, scoped to the same extensions the checker flags) that mutates the control packet on disk before the lint; phase_b is the producing executor so this is not an external artifact edit.
3. Invoke the normalizer immediately before the lint at every pre-finalization site; keep the lint as the fail-closed post-normalization guard.
4. Add the regression to the EXISTING mu/tests/tools/test_phase_b_executor.py (no new test file).
5. Run the evidence_command; confirm the phase_b line-ref/control-packet tests pass; emit the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- L4_ENABLER: do NOT touch runtime dirs (mu/host/**, rcx_pi/selfhost/**). Executor tooling + tests only.
- Do NOT create a new test file; add the regression to the existing mu/tests/tools/test_phase_b_executor.py.
- Preserve the no-line-refs invariant: the normalized packet must end line-ref-free, and the lint stays as the fail-closed guard after normalization (do NOT weaken the lint to a warning).
- Normalize ONLY the colon-digit suffix on file/doc references the checker flags; do NOT alter other packet content.

## Stop conditions

- Stop done when the evidence_command passes (a packet with a line-ref is normalized to name-only and the lint passes) and the indicator is collected.
- Halt as POLICY_BOUND if normalizing the packet on disk in phase_b conflicts with the artifact-edit gate for the producing executor; surface the exact conflict rather than weakening the lint.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- A control packet containing an extension-colon-digit reference is normalized to name-only before the lint, and `_control_packet_line_ref_lint_error` returns no error (the wave does not strand).
- The no-line-refs invariant holds (normalized packet is line-ref-free); the lint remains fail-closed after normalization.
- Executor tooling + an existing test file only; no runtime dirs; no new test file.
- evidence_command clean; indicator emitted.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21`.
- Governing packet: this file, `reports/control_plane/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21` is canonical for this packet's L4 fields.
- Authorization: Founder-directed 2026-06-21 (verbatim, emphatic: WE ARE ALWAYS HARDENING PIPELINE WHEN IT BREAKS). This is the LANDED structural fix for the control-packet line-ref strand that exhausted a Stage0 carry-forward wave (filing != fixing). Auto-authorized structural pipeline fix (feedback_manual_then_structural_autonomy).

FOUNDER_OVERRIDE:pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21`
- Active packet: `reports/control_plane/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21_2026-06-21.md`
  - `reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21 --output reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21`
- Active packet: `reports/control_plane/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21_2026-06-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a1a480d7c3caa7fb65f1794813ba6e30d07548390ec804dcbd3146c97dd5a324`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21_2026-06-21.md`
  - `reports/l4_wave_indicators/pipeline-fix-25-control-packet-line-ref-normalize-2026-06-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
