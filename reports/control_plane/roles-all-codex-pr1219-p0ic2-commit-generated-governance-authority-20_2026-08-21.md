# Roles-All-Codex-Pr1219-P0Ic2-Commit-Generated-Governance-Authority-20 2026-08-21

Date: 2026-08-21
Status: Phase B (locked, implementing)
Task: [ROLES-ALL-CODEX-PR1219-P0IC2-COMMIT-GENERATED-GOVERNANCE-AUTHORITY]
Wave ID: roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21
Phase-A-Lock: LOCKED
Purpose: From exact P0IC1 merge 2ba6847a2f4e20cc35dc96f988a4ddbc3ecea91b (PR #1221), implement and land only post-Step-5e commit-generated governance settlement in commit_executor.py with focused tests in the existing receipt suite. Bind the exact growth-cap path across tracker, separate packet authority, durable handoff, and supervisor package without changing pre-review authority or growth-cap semantics. Reconcile the complete 56-row TASKS queue without losing or reordering any TODO. Keep all roles Codex and commit providerless.

## Scope

This Phase A plan is limited to the P0IC2 Step-5e scope-registration defect authorized by task `[ROLES-ALL-CODEX-PR1219-P0IC2-COMMIT-GENERATED-GOVERNANCE-AUTHORITY]` in canonical `TASKS.md` for wave `roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21`.

Files and surfaces in implementation scope:

- `mu/tools/executors/commit_executor.py`: add the post-Step-5e registration behavior for the exact same-wave growth-cap bump path created or idempotently reused by Step 5e.
- `mu/tests/tools/test_commit_executor_receipt.py`: extend the existing focused receipt coverage for the new registration behavior.
- `TASKS.md`: update only the same-wave tracker scope refs needed for this authorized wave, preserving the complete TODO queue order and content.
- Same-wave generated governance only: durable handoff record, packet commit-time authority block, supervisor package metadata, and evidence handles for the exact growth-cap bump path bound to this wave.
- Existing evidence surfaces named by this packet: `reports/control_plane/roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-20_2026-08-21.md` and `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21.json`.

Out-of-band note for this rewrite turn: the only file to edit now is this packet.

## Work items

1. In `commit_executor.py`, after Step 5e has created or idempotently reused a same-wave growth-cap bump, mechanically register that exact commit-generated governance path.
2. Make the registration fail closed if Step 5e produced a governance path that cannot be bound to the same wave or cannot be represented consistently across the required governance surfaces.
3. Bind the exact path into the durable handoff, `TASKS.md` tracker scope refs, packet commit-time authority block, supervisor package, and evidence handles before meta-review.
4. Preserve the Phase B / pre-review candidate allowlist boundary: the growth-cap bump is commit-time generated governance, not part of the locked pre-review candidate allowlist.
5. Add focused coverage in the existing receipt suite for the registered same-wave growth-cap path and its fail-closed/error behavior.
6. Reconcile the complete 56-row `TASKS.md` queue without dropping, reordering, or silently rewriting unrelated TODO entries.

## Constraints

- Do not change pre-review authority semantics, Phase B candidate allowlist rules, or growth-cap semantics.
- Do not add test files, tool files, role/model work, lifecycle work, or nonblocker work.
- Do not widen implementation beyond `commit_executor.py`, its existing focused receipt test file, `TASKS.md`, and generated same-wave governance for this wave.
- Do not treat stale packet wording as proof that a work item remains unresolved once current code proves otherwise during implementation review.
- Keep all roles Codex and keep the commit providerless.
- Do not resume P0IA before this P0IC2 merge lands.

## Stop conditions

- Stop if the Step-5e growth-cap bump is not same-wave, cannot be uniquely identified, or cannot be registered across the required governance surfaces without broadening authority.
- Stop if the implementation would require modifying pre-review authority, growth-cap semantics, lifecycle behavior, role/model configuration, unrelated executor behavior, or nonblockers.
- Stop if the required `TASKS.md` queue reconciliation cannot preserve all existing TODO rows and ordering.
- Stop if the needed coverage cannot be expressed in the existing focused receipt suite without adding new test/tool files.
- Stop after the Phase A packet is rewritten for this turn; do not implement the underlying code changes in this rewrite task.

## Acceptance criteria

- The packet contains detector-visible `Scope`, `Work items`, `Constraints`, `Stop conditions`, `Acceptance criteria`, and `Grounding / Authorization` sections.
- The packet includes a detector-visible same-wave override line: `FOUNDER_OVERRIDE:roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21`.
- The planned implementation scope is bounded to the authorized files and generated same-wave governance surfaces under task `[ROLES-ALL-CODEX-PR1219-P0IC2-COMMIT-GENERATED-GOVERNANCE-AUTHORITY]` in canonical `TASKS.md`.
- The plan explicitly preserves the boundary between commit-time generated governance and the locked pre-review candidate allowlist.
- The plan requires fail-closed registration of only the exact same-wave growth-cap path after Step 5e.
- The plan rejects new test/tool files, unrelated role/model or lifecycle work, nonblockers, and any widening of pre-review authority or growth-cap semantics.
- Final implementation evidence must use the packet-derived command set in the L4 tracker block unless Phase B review updates it with stricter same-wave evidence.

## Grounding / Authorization

Task `[ROLES-ALL-CODEX-PR1219-P0IC2-COMMIT-GENERATED-GOVERNANCE-AUTHORITY]` in canonical `TASKS.md` authorizes this P0IC2 wave after P0IC1 and limits it to the Step-5e scope-registration defect reproduced by P0IA meta-review. The authorized behavior is: when Step 5e creates or idempotently reuses a same-wave growth-cap bump, register that exact commit-generated governance path in durable handoff, `TASKS.md` tracker scope refs, packet commit-time authority block, and supervisor package without pretending it belonged to the locked pre-review candidate allowlist.

This packet is the governing Phase A control-plane plan for:

- Task: `[ROLES-ALL-CODEX-PR1219-P0IC2-COMMIT-GENERATED-GOVERNANCE-AUTHORITY]`
- Wave: `roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21`
- Routed next-candidate: `roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-20_2026-08-21`

FOUNDER_OVERRIDE:roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21

## Request from Post-Merge Supervisor

From exact P0IC1 merge 2ba6847a2f4e20cc35dc96f988a4ddbc3ecea91b (PR #1221), implement and land only post-Step-5e commit-generated governance settlement in commit_executor.py with focused tests in the existing receipt suite. Bind the exact growth-cap path across tracker, separate packet authority, durable handoff, and supervisor package without changing pre-review authority or growth-cap semantics. Reconcile the complete 56-row TASKS queue without losing or reordering any TODO. Keep all roles Codex and commit providerless.

Routed next-candidate:
roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-20_2026-08-21

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21.json.
- `indicator_collection_command`: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21 --output reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py -k growth_cap_autobump --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py --json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21 --wave-class L4_ENABLER`.
- `evidence_delta`: [PENDING-UNTIL-P0IC2-MERGE] Step 5e's structured outcome drives one fail-closed post-Step-5e governance settlement. Only a staged same-wave mu/tests/docs/test_growth_caps.py bump is classified as commit-time generated governance; TASKS scope refs, the separate packet authorization block, durable handoff, evidence handles, and supervisor package all bind that path before meta-review. The Phase B/pre-review candidate allowlist remains unchanged. scope_refs: `TASKS.md`, `mu/tools/executors/commit_executor.py`, `mu/tests/tools/test_commit_executor_receipt.py`, `reports/control_plane/roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21_2026-08-21.md`, `reports/control_plane/roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-20_2026-08-21.md`, `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: roles-all-codex-pr1219-p0ic2-commit-generated-governance-authority-2026-08-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->
