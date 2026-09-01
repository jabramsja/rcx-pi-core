# Review-Convergence-Bootstrap-Atom-R1-2026-08-31 2026-08-31

Date: 2026-08-31
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [REVIEW-CONVERGENCE-BOOTSTRAP-ATOM-R1]
Wave ID: review-convergence-bootstrap-atom-r1-2026-08-31
Phase-A-Lock: LOCKED
Purpose: Define one portable Phase B atom that closes the coupled reviewer-contract and disposition-classifier landing failure without widening runtime or control-plane authority.

## Scope

Phase B is limited to the following current-wave writable files:

- `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md` -- Phase A contract and revisions through lock.
- `TASKS.md` -- builder-owned same-wave tracker synchronization, missing deferred-non-blocker queue entries, and the ordered successor entries described below.
- `mu/tools/agents/bridge_supervisor.py` -- the code-review prompt/template, authoritative finding schema, current-impact blocker eligibility, evidence-receipt instructions, and all-non-blocking GO rule.
- `mu/tools/agents/templates/bridge_reviewer_prompt.txt` -- reviewer-template substitution of the shared authoritative disposition contract.
- `mu/tools/executors/phase_b_executor.py` -- explicit-disposition classification precedence at the Phase B decision seam.
- `mu/tools/executors/recovery_gate.py` -- the matching explicit-disposition precedence at recovery GO deferrability.
- `mu/tests/tools/test_agent_bridge_supervisor.py` -- focused reviewer-contract regressions.
- `mu/tests/tools/test_phase_b_executor.py` -- focused Phase B classifier regressions.
- `mu/tests/tools/test_recovery_gate.py` -- focused recovery classifier regressions.

The outer Phase B pipeline also owns exactly two same-wave generated package
artifacts. They are permitted staged outputs, but are not implementer-writable:

- `reports/deferred/non_blocking/review-convergence-bootstrap-atom-r1-2026-08-31_bridge_nonblockers.md` -- executor-generated deferred-review output.
- `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json` -- pipeline-collected L4 evidence.

Only the staged indexes in these preserved sibling worktree directories are in scope as read-only evidence sources:

- `WorkingRCX-phase-b-code-review-prompt-precedence-r4-20260831/` -- useful staged code and test hunks only.
- `WorkingRCX-phase-b-current-impact-disposition-r1-20260831/` -- useful staged code and test hunks only.

No other implementer-writable file, generated package artifact, or preserved
evidence source is in scope.

## Work items

1. Finalize this Phase A packet as the independently decomposed, portable Phase B contract; obtain agent review and bridge convergence before setting `Phase-A-Lock: LOCKED`.
2. Reconstruct into the authorized current-wave files only the useful staged code and test hunks from both preserved candidates. The two corrections must land as one atom because either candidate alone leaves the reciprocal landing failure in place.
3. In `bridge_supervisor.py` and its reviewer template:
   - make the code-review current-impact rules authoritative over generic exhaustive-review or control-surface prose;
   - require `disposition` in the authoritative JSON finding schema;
   - allow a blocking finding only for a reproduced current regression in an authorized path that the staged candidate introduced or worsened, or for a direct failure of an exact locked acceptance criterion;
   - require `non_blocking`, regardless of severity, for synthetic-only, failure- or interruption-injected, theoretical or not-occurring, pre-existing-unworsened, and unrelated-adjacent findings;
   - replace mandatory exhaustive edge enumeration with a bounded review of staged candidate behavior and the exact locked acceptance criteria;
   - treat executor-provided successful validation results as evidence receipts, forbid reviewer reruns of the canonical evidence suite, and permit only a focused candidate-specific probe when a supplied receipt is insufficient; and
   - require `GO` when every finding is `non_blocking`.
4. In `phase_b_executor.py` and `recovery_gate.py`, implement the same decision precedence: preserve mandatory-evidence promotion first; then honor a present canonical `blocking` or `non_blocking` disposition ahead of severity; fail closed on an invalid present disposition; and invoke the existing severity and lower fallback behavior only when disposition is absent. Preserve all behavior outside this precedence seam.
5. Add focused regressions only to the three authorized existing test files. Cover the exact R5 `GO` plus high-severity `non_blocking` case, required schema disposition, current-candidate blocker eligibility, every absolute deferred category, bounded/no-rerun reviewer instructions, explicit blockers, invalid present values, omitted-disposition high/critical fallback, and mandatory-evidence promotion.
6. Synchronize `TASKS.md` through the builder-owned same-wave entry. If absent, queue the excluded stopped-reviewer edge cases as deferred non-blockers. Record the next landing-critical successor as a fresh native-stub packet-contract wave for `launch_wave.py` and Phase A aggregate packet validation; record a separate reviewer evidence-budget enforcement atom after it only if still needed.
7. Keep `gpt-5.6-sol` with `ultra` reasoning for every model-bearing role and pager, and keep commit execution providerless/null.

## Constraints

- Do not change runtime, substrate, host-semantics, parity, dispatcher, commit-surface, receipt, PR, fleet, Claude-owned, or unrelated edge-case implementation.
- Do not copy or modify either preserved candidate's packet, TASKS text, L4 indicator, deferred report, agent-bus state, branch history, or worktree state. The preserved candidates remain evidence until this combined atom actually merges.
- Do not implement malformed-finding handling, repeat recovery, crash replay, `QUESTION` persistence, non-`GO` semantics, receipt revocation, or any other stopped-reviewer edge case. Missing queue entries may be added only to `TASKS.md` as deferred non-blockers.
- Do not add production files or test files. Tests are limited to the three existing files enumerated in Scope.
- Do not alter behavior outside the exact reviewer-eligibility and disposition-precedence seams.
- Do not implement either successor wave in this atom, and do not add evidence-budget enforcement unless the ordered later atom is still needed.
- Do not hand-edit the auto-derived L4 field block below; its canonical source remains the same-wave `TASKS.md` tracker note.

## Stop conditions

- This Phase A rewrite stops after this packet contains the required contract sections; no underlying implementation is performed in this turn.
- Phase B must not begin until agent review and bridge convergence are complete and this packet is locked. A requested acceptance change returns the packet to Phase A rather than being improvised during execution.
- If current code truth at Phase B start proves a listed item already landed, count that criterion as satisfied and do not reimplement it. If the remaining work no longer forms this bounded combined atom, stop and return to Phase A.
- Stop and report the dependency if any acceptance criterion requires a path or behavior outside Scope; do not widen the atom.
- Stop without commit-ready status if mandatory-evidence promotion, invalid-present fail-closed behavior, or absent-disposition fallback cannot be preserved exactly, or if the exact evidence command fails.
- Stop when this one atom is commit-ready. Do not implement the ordered successors or remove the preserved candidates; their cleanup remains gated on the combined atom actually merging.

## Acceptance criteria

1. The Phase A packet has an explicit file/directory scope, concrete work items, constraints, stop conditions, testable acceptance criteria, and wave-bound grounding/authorization; it contains no repeated supervisor-request echo.
2. The authoritative reviewer JSON schema requires `disposition`, and the code-review current-impact contract cannot be overridden by generic exhaustive-review or control-surface wording.
3. A finding is eligible to block only when evidence reproduces a current authorized-path regression introduced or worsened by the staged candidate, or directly demonstrates failure of an exact locked acceptance criterion.
4. Synthetic-only, failure- or interruption-injected, theoretical or not-occurring, pre-existing-unworsened, and unrelated-adjacent findings remain `non_blocking` at every severity. When all findings are `non_blocking`, the reviewer emits `GO`, including the exact R5 high-severity `non_blocking` case.
5. Successful executor validation results are accepted as evidence receipts. Reviewer instructions prohibit rerunning the canonical evidence suite and allow only a focused candidate-specific probe when the provided evidence is insufficient.
6. Phase B and recovery apply the same precedence: mandatory-evidence promotion first; a valid present canonical disposition before severity; invalid present values fail closed; and existing severity/lower fallback behavior only when disposition is absent. Explicit blockers, omitted-disposition high/critical findings, and mandatory-evidence failures retain their required blocking behavior.
7. Focused regressions for criteria 2-6 exist only in the three authorized test files, and the exact `evidence_command` in the L4 field block passes under executor control.
8. The current-wave staged package is limited to the nine implementer-writable files enumerated in Scope plus the two separately enumerated outer-generated governance artifacts. This governing packet is the sole manually authored new file; the deferred non-blocker report and L4 indicator are the only additional new files. No new production or test files are created, preserved evidence is unchanged, and behavior outside the two named seams is unchanged.
9. The builder-owned `TASKS.md` entry reflects same-wave completion evidence, any missing excluded-edge deferred non-blockers, and the required successor ordering. The preserved R5 and classifier candidates remain intact until this atom merges.
10. Every model-bearing role and pager uses Codex `gpt-5.6-sol` with `ultra` reasoning, and commit execution remains providerless/null.

## Grounding / Authorization

- Governing packet: `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md`, task `[REVIEW-CONVERGENCE-BOOTSTRAP-ATOM-R1]`, wave `review-convergence-bootstrap-atom-r1-2026-08-31`.
- Tracker authority: the same-wave `[REVIEW-CONVERGENCE-BOOTSTRAP-ATOM-R1]` tracker sync note in `TASKS.md` classifies this as `L4_ENABLER`, targets G8 / `INV_STRUCTURAL_FORWARD_MOTION`, names the authorized structural seam and evidence command, supplies the no-op boundary, and records progress-after as `[PENDING-UNTIL-MERGE]`.
- Evidence authority: the bridge `REQUEST_CHANGES` reproductions establish that the prior packet had only `## Scope` and echoed the supervisor directive; they do not establish that any downstream implementation item has landed. Per the task instruction, no downstream implementation file was inspected to draft this first real plan.
- Preserved-candidate authority: the two sibling worktree staged indexes named in Scope are evidence sources only under the supervisor directive carried by this governing packet.

FOUNDER_OVERRIDE:review-convergence-bootstrap-atom-r1-2026-08-31

Routed next-candidate:
review-convergence-bootstrap-atom-r1-2026-08-31

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id review-convergence-bootstrap-atom-r1-2026-08-31 --output reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md. (2) Final pytest gate covered 10 pytest selector(s) across 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/agents/bridge_supervisor.py`, `mu/tools/agents/templates/bridge_reviewer_prompt.txt`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md`, `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: review-convergence-bootstrap-atom-r1-2026-08-31.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `review-convergence-bootstrap-atom-r1-2026-08-31`
- Active packet: `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md`
- Indicator artifact: `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `mu/tools/agents/templates/bridge_reviewer_prompt.txt`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md`
  - `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `review-convergence-bootstrap-atom-r1-2026-08-31`
- Active packet: `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c5a75aaedbb25eb0970cc171ce47dd5acccabb5ffd00983734120b7a66bdd463`
- Indicator artifact: `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md. (2) Final pytest gate covered 10 pytest selector(s) across 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/agents/bridge_supervisor.py`, `mu/tools/agents/templates/bridge_reviewer_prompt.txt`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md`, `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json`
- Current staged files:
  - `reports/control_plane/review-convergence-bootstrap-atom-r1-2026-08-31_2026-08-31.md`
  - `reports/l4_wave_indicators/review-convergence-bootstrap-atom-r1-2026-08-31.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
