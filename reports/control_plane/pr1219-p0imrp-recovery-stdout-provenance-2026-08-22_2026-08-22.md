# PR 1219 P0IMRP Recovery Stdout Provenance 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMRP-RECOVERY-STDOUT-PROVENANCE-2026-08-22]
Wave ID: pr1219-p0imrp-recovery-stdout-provenance-2026-08-22
Phase-A-Lock: LOCKED
Purpose: From exact merged PR #1236 authority 79e0bb59c8c035370fb2232c65526989cc4f5e5d, land only the demonstrated recovery diagnostic-provenance repair. A mechanically proven dispatcher aggregate with a non-empty transcript prefix and one EOF-consuming terminal JSON object must not let historical text in that prefix impersonate a live bridge-adapter bootstrap fault, while direct/unstructured stdout and every malformed, incomplete, empty-prefix, or identity-mismatched aggregate remain fail closed. Preserve the old 2550e2c lane unchanged, make P0IM the sole next successor after this merge, and do not absorb edge cases or unrelated cleanup.

## Scope

Repair only the bootstrap-fault diagnostic authority used before hybrid delegate_implementer execution. Prove a non-empty transcript prefix plus one EOF-consuming terminal JSON object, bind only the two observed outer/terminal identity tuples, suppress phrase authority only from that proven prefix, preserve legacy fail-closed scanning everywhere else, add focused behavioral and negative-control tests, and advance canonical queue truth from PR #1236 to this wave and then P0IM.

Files and surfaces in scope:

- mu/tools/executors/recovery_gate.py (MODIFY) -- add one local trailing-envelope parser that returns both the non-empty prefix and EOF-consuming terminal object without changing _parse_json_object or merged-result helpers, then narrow _hybrid_bootstrap_fault_detected diagnostic provenance only for two mechanically coherent aggregate result shapes. For those shapes, scan explicit outer step/executor/stderr/error/errors/detail/message/reason fields and terminal step/executor/stderr/stdout/error/errors/detail/message/reason fields; exclude only the proven prefix plus arbitrary nested stream/diff/document/findings bodies. Keep files_in_scope bootstrap-surface rejection first and unchanged, keep the bare bridge-config path error-channel rule unchanged, and keep legacy full-stdout phrase scanning for direct/unstructured or unprovable results.
- mu/tests/tools/test_recovery_gate.py (MODIFY) -- reproduce both demonstrated coherent aggregates and prove historical bridge-config phrases in the proven transcript prefix, including TASKS/diff/summary/bot-finding/stream-json bodies, do not block delegation; prove the same phrases in explicit outer fields or terminal top-level diagnostic fields including terminal stdout do block; prove direct stdout, empty-prefix JSON, malformed/missing/non-EOF terminal JSON, multiple-object tail mismatch, outer/terminal identity mismatch, and unsupported aggregate shapes remain fail closed.
- TASKS.md (MODIFY THROUGH PIPELINE) -- mark target-role authority activation LANDED through PR #1236 at exact merge 79e0bb59c8c035370fb2232c65526989cc4f5e5d; make this recovery-stdout-provenance row CURRENT; make P0IM the sole immediate successor while retaining its exact dependency; preserve P0IB and all later queue rows, every unrelated TODO, all eight legacy-PR unique-delta obligations, and every dirty-worktree preservation record.
- reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json (GENERATED BEFORE REVIEW) -- same-wave current-candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave nonblockers; edge cases and wording residue cannot widen or delay landing.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imrp-recovery-stdout-provenance-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Start from a fresh target branch, worktree, namespaced bus, and detached trusted source all at exact PR #1236 merge 79e0bb59c8c035370fb2232c65526989cc4f5e5d. Do not resume, mutate, cherry-pick, copy from, amend, rebase, or push the preserved 2550e2c lane.
2. Add one bounded trailing-envelope helper used only by _hybrid_bootstrap_fault_detected. Decode a dictionary that consumes stdout through EOF except trailing whitespace, return its exact source start plus the preceding prefix, and require that prefix to contain non-whitespace transcript bytes. Do not change or reuse _parse_json_object for this authority decision, and do not use _extract_result_candidates, _merge_result_candidates, effective-result helpers, recursive walking, or candidate precedence that erases provenance.
3. Bind the coherent bot tuple to explicit outer result['failure_class']=bot_findings_pending and outer executor=commit_executor, with absent outer step as in the chained dispatcher wrapper, plus a terminal object with status=bot_findings_pending and absent terminal step/executor. The captured live terminal keyset was status, bot_findings, p1_unresolved, pr_number, steps_completed, and remediation_rounds_attempted; do not invent a terminal commit_executor step. Bind the coherent pre-push tuple to explicit outer result['failure_class']=test_failure and outer executor=commit_executor, with absent outer step as in the chained dispatcher wrapper, plus terminal status error or failed and terminal step=run_pre_push_script. A class present only in terminal stdout or historical text never authorizes suppression.
4. For only those two coherent tuples, exclude only the proven transcript prefix from bootstrap phrase authority. Build the phrase haystack from explicit outer step/executor/stderr/error/errors/detail/message/reason fields and terminal top-level step/executor/stderr/stdout/error/errors/detail/message/reason fields. Do not recurse through aggregated_output, diff, TASKS/docs, summary, findings, bot_findings, prompt text, or arbitrary nested values. Preserve phrase matching itself and apply the residual bare-path check only to explicit outer/terminal error channels step/stderr/executor.
5. For direct/unstructured failures and for any stdout with an empty prefix, absent/malformed/truncated terminal JSON, non-whitespace after the terminal object, unsupported outer class, missing or mismatched executor/step/status identity, or otherwise unprovable coherence, retain the existing full step/stderr/stdout/executor scan so ambiguity fails closed.
6. Add a compact parameterized acceptance matrix covering all existing phrase fragments and the minimum focused controls: both coherent tuples; phrase-only prefix; phrase in every explicit outer/terminal diagnostic channel including terminal stdout; plain/direct stdout; empty-prefix JSON; malformed/truncated/non-EOF tail; multiple objects with the final object mismatched; class present only inside stdout; tuple mismatch; files_in_scope bootstrap surface; stdout-only bare path; and error-channel bare path. Do not broaden into generic log sanitization, recovery prompt sizing, classifier refactoring, timeouts, retries, adapter configuration, or unrelated recovery behavior.
7. Update canonical queue truth without deleting, closing, or reordering unrelated work. Route implementation, independent review, providerless commit, normal pre-push, CI, merge, exact origin/dev proof, and cleanup only through the pipeline.

## Constraints

- Exact PR #1236 merge 79e0bb59c8c035370fb2232c65526989cc4f5e5d is the hard dependency and must equal source HEAD, target HEAD before implementation, comparison_commit, and origin/dev immediately before launch.
- The comparison-relative candidate allowlist is only TASKS.md, recovery_gate.py, test_recovery_gate.py, the exact same-wave packet/indicator, and only if generated the exact same-wave deferred report. This external WaveConfig and all bus-local receipts are excluded from candidate content.
- Do not modify commit_executor.py, executor_dispatch.py, executor_common.py, executor_config.json, launch_wave.py, phase_a_executor.py, phase_b_executor.py, bridge adapters/client/config, candidate authority, model/timeout/retry defaults, hooks, observability, runtime, substrate, seeds, registry, JS files, or unrelated tests/docs.
- Do not introduce a generic scrubber, substring deletion, line truncation, regex over arbitrary log bodies, or silent fallback that could conceal a real adapter/bootstrap fault. Provenance selection must precede existing phrase matching, require a non-empty prefix plus EOF-consuming terminal object, and be mechanically bound to the two exact coherent tuples.
- Do not treat aggregate stdout as trusted merely because some object parses, do not let a class found only inside stdout authorize suppression, and do not trust summary/findings/bot_findings/aggregated_output/diff/document fields as error authority. Conversely, do not remove stdout authority from direct/unstructured failures or from a coherent terminal object's top-level stdout diagnostic field.
- This is Python control-plane authority only: it adds no runtime/substrate semantics and requires no JS mirror. Host-semantics and host-authority inventories must remain unchanged.
- Preserve all conflicting PR/worktree evidence unchanged. All model-bearing roles and pager use Codex; commit remains providerless. Nonblockers and edge cases cannot delay this landing.

## Stop conditions

- Halt before launch unless origin/dev, clean detached launcher source, fresh target HEAD, and comparison_commit all equal exact 79e0bb59c8c035370fb2232c65526989cc4f5e5d; canonical branch/worktree/bus identities are unique; roles/pager are Codex; and commit is providerless.
- Halt as NEEDS_RESCOPING if the fix requires any functional file beyond recovery_gate.py and test_recovery_gate.py, changes failure classification or retry/delegation policy, alters bridge/adapter configuration, or requires model/timeout/observability/runtime work.
- Halt as DEFECT if a direct stdout adapter/bootstrap phrase no longer blocks, if empty-prefix/direct JSON or malformed/missing/non-EOF/mismatched aggregate evidence fails open, if a terminal top-level stdout phrase is suppressed, if a class found only in stdout authorizes suppression, if arbitrary nested fields become trusted error authority, if files_in_scope or bare-path guards weaken, or if a coherent demonstrated aggregate still blocks solely because its proven transcript prefix contains the phrase.
- Halt if TASKS removes, closes, or rewrites any unrelated TODO/queue/history/preservation item; treats 2550e2c as pushed or landed; advances P0IM before this exact merge; closes any legacy PR before its unique delta lands; or treats HOLD/preservation as cleanup authority.
- Do not claim this blocker complete or launch P0IM until deterministic PR merge, exact merge SHA, origin/dev equality, and pipeline cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- A non-empty transcript prefix plus EOF-consuming terminal object under the exact outer bot_findings_pending/commit_executor tuple and terminal status bot_findings_pending does not block delegation when 'bridge config not found' appears only in that prefix, including TASKS/diff/summary, bot-finding bodies, or stream-json aggregated_output.
- A non-empty transcript prefix plus EOF-consuming terminal object under the exact outer test_failure/commit_executor tuple, terminal status error-or-failed, and terminal step run_pre_push_script does not block delegation when the phrase appears only in that prefix, including the preserved attempt's actual shape.
- For either coherent tuple, any existing adapter/bootstrap phrase in explicit outer step/executor/stderr/error/errors/detail/message/reason fields or terminal top-level step/executor/stderr/stdout/error/errors/detail/message/reason fields blocks delegation with the existing bootstrap/adapter-fault result.
- Direct/unstructured stdout carrying an adapter/bootstrap error phrase remains blocking. Empty-prefix/direct JSON, missing/malformed/truncated/non-EOF terminal JSON, multiple-object final-tail mismatch, unsupported aggregate class, class found only inside stdout, and outer/terminal executor/step/status mismatch retain legacy full-stdout fail-closed behavior.
- The files_in_scope bootstrap-surface guard, bare .agent_bus/bridge_config.json error-channel guard, hybrid scope audit, recovery classifier, retries, and delegate execution behavior remain unchanged outside the diagnostic-provenance selector.
- Host-semantics and host-authority inventories remain unchanged; no JS/runtime/substrate delta is introduced.
- TASKS records PR #1236/79e0bb59 as landed, this wave current, P0IM next behind its exact merge, and preserves all unrelated queue, legacy-PR, and worktree evidence.
- Focused tests, exact live candidate receipt verification, staged L4 enforcement, cached diff check, independent review, providerless commit, normal pre-push, required CI, merge, exact dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMRP-RECOVERY-STDOUT-PROVENANCE-2026-08-22]; wave id `pr1219-p0imrp-recovery-stdout-provenance-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imrp-recovery-stdout-provenance-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder made landing valuable work the primary goal, authorized narrower packets when needed for convergence, and prohibited edge cases or nonblockers from delaying landings. The preserved 2550e2c attempt and its three-entry recovery ledger reproduce this exact active blocker; PR #1236 independently landed the preceding target-role authority repair, so this two-functional-file provenance packet is the minimum honest successor before P0IM.

FOUNDER_OVERRIDE:pr1219-p0imrp-recovery-stdout-provenance-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imrp-recovery-stdout-provenance-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md`
  - `reports/deferred/non_blocking/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0imrp-recovery-stdout-provenance-2026-08-22`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrp-recovery-stdout-provenance-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md`, `reports/deferred/non_blocking/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imrp-recovery-stdout-provenance-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a66bf4c982059fefdfaff20df32598a2b341a8c8c6a2abbe0c819592aad7cba0`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md`, `reports/deferred/non_blocking/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_2026-08-22.md`
  - `reports/deferred/non_blocking/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0imrp-recovery-stdout-provenance-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
