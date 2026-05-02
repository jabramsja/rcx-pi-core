# Hybrid Recovery Inert Structural Gaps

Date: 2026-04-29
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Phase-A-Lock: LOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: hybrid-recovery-inert-structural-gaps-2026-04-17
Wave class: L4_ENABLER
Target gate: G8
Lane: control-surface
Authorization: standing pipeline-bug-fix authorization for bounded pipeline recovery hardening; commit automation may derive `FOUNDER_OVERRIDE:hybrid-recovery-inert-structural-gaps-2026-04-17` for L4 adjacency/rolling-cap clearance.

## Purpose

Close the three remaining structural gaps in
`reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md`
so enabled hybrid recovery can productively delegate bounded pipeline repairs
instead of escalating inertly.

This packet is the Phase A governing packet for a new bounded hardening wave
under the closed `[PIPELINE-RECOVERY]` parent lane. It does not reopen the
landed parent lane or treat stale packet wording as proof that every listed
item remains unlanded in current code.

The prior `pipeline-hardening-bundle-2026-04-17` wave closed only the
`MISSING_BRIDGE_CONFIG` bootstrap gap. This wave closes the remaining scope
validation, Phase B error-signal propagation, and standalone commit recovery
trigger gaps.

## Phase B Closeout

- Implemented and targeted-tested on 2026-04-29.
- Targeted validation:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_doc_placement_rules.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_commit_executor_receipt.py`
  passed; the commit path truth refresh below records the same validation surface.
- Deferred blocker archived to
  `reports/archive/deferred/hybrid_recovery_inert_structural_gaps_2026-04-17_closed-by-hybrid-recovery-inert-structural-gaps-2026-04-17.md`.

## Grounding / Authorization

- `TASKS.md:317-331` is the controlling task-lane authorization boundary:
  `[PIPELINE-RECOVERY]` is closed; the 2026-04-16 tracked packet is
  `reports/control_plane/hybrid_recovery_agent_2026-04-16.md`; and the
  2026-04-22 entry states that no live in-flight recovery branch remains on
  current `dev`, so future recovery hardening must be authorized as new bounded
  waves rather than implied by the landed parent lane.
- Governing packet for this new bounded wave:
  `reports/control_plane/hybrid_recovery_inert_structural_gaps_2026-04-17.md`.
  The older `reports/control_plane/hybrid_recovery_agent_2026-04-16.md` packet
  remains the TASKS-tracked predecessor for the landed hybrid recovery
  mechanism and narrow Tier 3 `phase_b_implementer` reuse exception; it is not
  an open authorization to add unbounded follow-through work.
- `reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md:9-18`
  states that hybrid recovery landed and was enabled, but the
  `delegate_implementer` action has not executed productively because three
  structural gaps remain.
- `reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md:42-51`
  requires widening hybrid `files_in_scope` for executor/test/control-plane
  repairs while preserving runtime denials, plus a regression proving a widened
  scope example is accepted by `_validate_delegate_implementer_payload`.
- `reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md:78-86`
  requires extracting the adapter result envelope and propagating
  `error_subtype: "error_max_turns"` into the Phase B result, with a new
  `FailureClass.MAX_TURNS_REACHED`.
- `reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md:109-122`
  requires widening standalone commit recovery beyond `bot_findings_pending`
  and adding regression coverage that `attempt_recovery` is invoked for each
  widened failure class and that `recovery_gate` has an explicit classifier
  class for each widened failure class.
- Pre-implementation code evidence from the source blocker:
  `mu/tools/executors/recovery_gate.py:2198-2202`
  admits only `recovery_gate.py` and `executor_common.py` in
  `_HYBRID_RUNTIME_SCOPE`; `mu/tools/executors/recovery_gate.py:3582-3585`
  rejects any `files_in_scope` entry outside that exact set.
- Pre-implementation code evidence from the source blocker:
  `mu/tools/executors/recovery_gate.py:2894-2915`
  prompts the recovery agent to target only those two runtime files and two
  validator targets.
- Pre-implementation code evidence from the source blocker:
  `mu/tools/executors/phase_b_executor.py:3490-3502`
  converts an implementer failure into a generic error and returns without
  copying adapter envelope fields such as `error_subtype`, `stop_reason`, or
  `num_turns`.
- Pre-implementation code evidence from the source blocker:
  `mu/tools/executors/commit_executor.py:6093-6096`
  invokes standalone recovery only when `result.get("status") ==
  "bot_findings_pending"` and `args.standalone` is set.

## Scope

Admitted files for this wave:

1. `mu/tools/executors/recovery_gate.py`
2. `mu/tools/executors/phase_b_implementer.py`
3. `mu/tools/executors/phase_b_executor.py`
4. `mu/tools/executors/commit_executor.py`
5. `mu/tests/tools/test_recovery_gate.py`
6. `mu/tests/tools/test_phase_b_executor.py`
7. `mu/tests/tools/test_commit_executor_receipt.py`
8. `reports/control_plane/hybrid_recovery_inert_structural_gaps_2026-04-17.md`
9. `reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md`
10. `reports/archive/deferred/hybrid-recovery-inert-structural-gaps-2026-04-17_bridge_nonblockers_closed-by-deferred-report-truth-cleanup-2026-05-02.md`
11. `reports/archive/deferred/hybrid_recovery_inert_structural_gaps_2026-04-17_closed-by-hybrid-recovery-inert-structural-gaps-2026-04-17.md`
12. `.gitignore`
13. `mu/tests/docs/test_doc_placement_rules.py`

No runtime, substrate, host authority, seed, projection, kernel, or JavaScript
files are in scope.

## Work Items

1. Widen the hybrid `delegate_implementer` payload validator from a two-file
   exact runtime allowlist to a bounded control-surface allowlist:
   `mu/tools/executors/**/*.py`, `mu/tests/tools/test_*.py`,
   `reports/deferred/**/*.md`, and `reports/control_plane/**/*.md`.
2. Preserve hard denials for host/runtime/bootstrap surfaces, including
   `mu/host/**`, `rcx_pi/**`, `.git/**`, `.agent_bus/**`, `.claude/**`,
   `archive/**`, `mu/tools/executors/phase_b_implementer.py`, and
   `.agent_bus/bridge_config.json`.
3. Update the Tier 3 recovery prompt text so recovery agents see the same
   widened bounded scope that `_validate_delegate_implementer_payload` enforces.
4. Add `FailureClass.MAX_TURNS_REACHED`, map it to the appropriate recovery
   tier, and classify structured adapter failures carrying
   `error_subtype == "error_max_turns"` or embedded `subtype == "error_max_turns"`.
5. Teach `phase_b_implementer.invoke_implementer` and/or Phase B failure
   handling to parse adapter result envelopes such as
   `{"type":"result","subtype":"error_max_turns","num_turns":51,"stop_reason":"tool_use"}`
   and propagate `error_subtype`, `stop_reason`, and `num_turns`.
6. Preserve those diagnostic fields in the final Phase B result when the
   implementer fails so recovery can classify the root cause rather than seeing
   only a generic wrapper.
7. Widen standalone `commit_executor` recovery trigger coverage beyond
   `bot_findings_pending` to recoverable non-success statuses and error steps
   while preserving non-recovery exits for `success` and `held`.
8. Add explicit `recovery_gate` classifier coverage for each widened standalone
   failure class: `pre_push_failed`, `stage_failed`, `implementer_error`,
   `bridge_error`, and `l4_contract_violation`.
9. Add focused regression tests for each changed contract and keep the tests
   bounded to the affected executor/test files.
10. On closeout, archive
   `reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md`
   with a closed-by suffix once all three acceptance criteria are implemented
   and verified.
11. Bridge Round 2 structural staging fix: unignore canonical deferred
   `reports/archive/deferred/*_closed-by-*.md` closeout evidence, admit
   `.gitignore` as a root control-surface file in Phase B packet parsing, and
   add doc-placement regression coverage plus mixed-collection `tools` import
   repair so future deferred closeout snapshots are normal-stageable without
   force-add while the historical archive backlog remains ignored.

## Constraints

- Do not weaken the existing bootstrap-surface denial. Hybrid recovery must not
  target the implementer/bootstrap adapter itself.
- Do not allow host/runtime/substrate paths through the hybrid delegation
  allowlist.
- Do not route arbitrary shell validation through `delegate_implementer`; keep
  `validation_spec` structured and targeted.
- Do not invent recovery behavior for terminal human-decision states such as
  founder questions, max bridge rounds, or supervisor rejection.
- Do not bypass L4 checks, pre-push governance, bridge review, or commit
  automation.

## Stop Conditions

1. Stop and split if the widened hybrid scope requires modifying host/runtime,
   substrate, seed, projection, kernel, or JavaScript files.
2. Stop and split if max-turns handling requires changing the bridge adapter
   protocol rather than parsing already-emitted structured result envelopes.
3. Stop and split if commit recovery widening would route terminal
   founder-decision states into automated recovery.
4. Stop for founder direction if Phase A bridge review finds the three gaps too
   large for one bounded `[PIPELINE-RECOVERY]` wave.

## Acceptance Criteria

1. `mu/tests/tools/test_recovery_gate.py` proves widened executor/test/report
   paths are accepted by `_validate_delegate_implementer_payload`, forbidden
   runtime/bootstrap/config paths remain rejected, and validator targets accept
   `mu/tests/tools/test_*.py` paths needed by the widened scope.
2. `mu/tests/tools/test_recovery_gate.py` proves
   `FailureClass.MAX_TURNS_REACHED` classification for top-level and embedded
   adapter `error_max_turns` payloads.
3. `mu/tests/tools/test_phase_b_executor.py` proves a max-turns implementer
   failure produces a Phase B result containing
   `error_subtype: "error_max_turns"`, `stop_reason`, and `num_turns`.
4. `mu/tests/tools/test_commit_executor_receipt.py` proves standalone
   `commit_executor` invokes `attempt_recovery` for each widened failure class:
   `pre_push_failed`, `stage_failed`, `implementer_error`, `bridge_error`, and
   `l4_contract_violation`, and still does not attempt recovery for `success`
   or `held`.
5. `mu/tests/tools/test_recovery_gate.py` proves `recovery_gate` classifies
   each widened standalone failure class with explicit classifier coverage:
   `pre_push_failed`, `stage_failed`, `implementer_error`, `bridge_error`, and
   `l4_contract_violation`.
6. The deferred blocker is archived after all three fixes pass targeted tests.
7. L4 execution contract, host-semantics ratchet, host-authority inventory
   ratchet, and docs consistency remain green before commit.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `hybrid-recovery-inert-structural-gaps-2026-04-17`
- Active packet: `reports/control_plane/hybrid_recovery_inert_structural_gaps_2026-04-17.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `90859543113515aea291b6821cb2fec73433b38b340336bcbfdc7fa35d7f5e57`
- Indicator artifact: `reports/l4_wave_indicators/hybrid-recovery-inert-structural-gaps-2026-04-17.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-29T07-28-26p00-00_191171d9.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_doc_placement_rules.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/hybrid_recovery_inert_structural_gaps_2026-04-17.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Commit handoff carries explicit receipt authority at .agent_bus/meta/pre_commit_receipts/receipt_2026-04-29T07-28-26p00-00_191171d9.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/hybrid-recovery-inert-structural-gaps-2026-04-17.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-29T07-28-26p00-00_191171d9.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/hybrid_recovery_inert_structural_gaps_2026-04-17.md`
  - `reports/l4_wave_indicators/hybrid-recovery-inert-structural-gaps-2026-04-17.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
