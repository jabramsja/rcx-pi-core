# Recovery-Routing-Record-Resolver-R1-2026-08-30 2026-08-30

Date: 2026-08-30
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [RECOVERY-ROUTING-RECORD-RESOLVER-R1]
Wave ID: recovery-routing-record-resolver-r1-2026-08-30
Phase-A-Lock: LOCKED
Purpose: Define a behavior-preserving Phase B atom that closes recovery_gate's routing-record read boundary behind one auditable, bus-aware seam. The wave separates the production refactor, structural bypass prevention, and bus-selection equivalence proof while deliberately deferring new invocation authority and broader recovery-policy changes.

## Scope

`TASKS.md` authorizes this bounded L4_ENABLER wave. The current Phase A rewrite changes only this governing packet; the planned Phase B implementation is limited to the following two files:

- `mu/tools/executors/recovery_gate.py`: add the private resolver and route existing production canonical routing-record reads through it.
- `mu/tests/tools/test_recovery_gate.py`: add the mechanical bypass regression and focused default/non-default `bus_dir` equivalence coverage.

`TASKS.md` is a read-only authorization and grounding source, not an implementation target. No directory-wide refactor or additional production, test, executor, dispatcher, configuration, runtime, or documentation file is in scope.

- `reports/deferred/non_blocking/recovery-routing-record-resolver-r1-2026-08-30_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. At Phase B start, inventory the canonical `load_routing_record` call sites inside `recovery_gate.py` only and compare live code with the tracker’s commit-scoped baseline. If the exact resolver boundary and required regressions are already present, invoke the corresponding stop condition rather than duplicate them.
2. Add exactly one private internal resolver that receives `repo_root` and the already selected `bus_dir`, delegates to the existing canonical `load_routing_record` behavior, and returns that result without normalization, conversion, caching, mutation, or a new fallback.
3. Replace every production canonical routing-record read in `recovery_gate.py` outside that resolver with a call to the resolver. Keep each consumer’s existing argument values, exception boundary, malformed-input handling, empty fallback, return representation, ordering, and side effects at the caller.
4. Add a mechanical structural regression in `test_recovery_gate.py` that fails when a production canonical routing-record read bypasses the resolver. The assertion must enforce the resolver boundary without depending on generated line numbers or treating the tracker’s historical call count as permanent.
5. Add focused behavioral tests for both the default bus directory and an explicitly selected non-default `bus_dir`. Prove that the selected directory reaches the canonical loader unchanged and that caller-visible results and failure/fallback behavior remain equivalent to the pre-refactor paths.
6. Run the tracker-authorized targeted recovery-gate test command and retain its result as the Phase B behavioral evidence.

### Design choices and trade-offs

- Use a thin resolver rather than introducing supplied-record authority. This creates one auditable load boundary now but intentionally leaves record injection and nested-invocation policy for a later atom.
- Pass `repo_root` and selected `bus_dir` explicitly rather than deriving either from ambient state. This keeps non-default bus selection visible and testable, at the cost of not adding caching or implicit context.
- Leave exception handling, malformed-input policy, and fallback ownership with existing callers. Some caller-level duplication therefore remains by design, avoiding a semantic change disguised as centralization.
- Enforce the boundary structurally and prove behavior separately. The source-level regression is coupled to the intended architectural seam, while focused behavioral tests prevent that structural rule from masking argument or outcome drift.

## Constraints

- Do not change any public function signature.
- Do not add a supplied-record parameter, `ContextVar`, mapping conversion, nested invocation policy, identity fence, Wave-ID rebinding, exhaustion or recovery-budget change, dispatcher forwarding, or any new fallback.
- Do not add fixer, mutation, routing-decision, accounting, launcher, commit-execution, Phase A/B executor, runtime, substrate, provider, fleet, PR, or Claude-owned behavior.
- Do not move caller-owned exception handling, malformed-input handling, empty fallback, ordering, return representation, or side effects into the resolver.
- Do not alter the canonical loader’s contract or add another routing-record reader.
- Keep all model-bearing roles and the pager on Codex; keep terminal commit execution providerless/null. No configuration change is authorized by this wave.
- Do not broaden Phase B source edits beyond `mu/tools/executors/recovery_gate.py` and `mu/tests/tools/test_recovery_gate.py`.

## Stop conditions

Stop Phase B implementation and return the packet for disposition if any of the following is true:

1. Live in-scope code and tests already satisfy the exact single-resolver boundary, mechanical bypass regression, and default/non-default bus coverage; do not land a duplicate or cosmetic rewrite.
2. Centralizing a live call site requires a public signature change, a change to the canonical loader, or an edit outside the two planned Phase B files.
3. A single resolver cannot preserve a caller’s current arguments, exception boundary, malformed-input behavior, empty fallback, return representation, ordering, or side effects without adding conditional policy.
4. The implementation would require or implicitly introduce any authority, recovery-policy, mutation, forwarding, or runtime behavior excluded by this packet.
5. A reliable mechanical bypass check cannot be expressed in the scoped test file without relying on generated line positions or a stale hard-coded call count.
6. The targeted evidence command fails for a cause that cannot be corrected within the authorized two-file implementation scope; report the exact failure without widening the wave.

## Acceptance criteria

Phase B is acceptable only when all of the following are mechanically or behaviorally demonstrated:

1. Excluding this governing packet and pipeline-generated receipts, the implementation diff is limited to `mu/tools/executors/recovery_gate.py` and `mu/tests/tools/test_recovery_gate.py`.
2. Exactly one private internal resolver accepts `repo_root` and the selected `bus_dir`, delegates to the existing canonical `load_routing_record` behavior, and returns its representation unchanged.
3. The resolver contains the only production canonical routing-record load in `recovery_gate.py`; every recovery consumer that needs the canonical record reaches that seam.
4. A mechanical regression fails if a production call bypasses the resolver and does not depend on source line numbers or a fixed historical number of consumers.
5. Focused tests prove correct and behaviorally equivalent routing-record loading for the default bus directory and a non-default selected `bus_dir`, including exact argument propagation.
6. Existing caller behavior remains unchanged for successful loads, loader exceptions, malformed input, empty fallback, return representation, ordering, and side effects.
7. Public APIs and every explicitly excluded authority, policy, mutation, forwarding, and runtime surface remain unchanged.
8. The tracker-authorized evidence command exits successfully:

   `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_recovery_gate.py`

## Grounding / Authorization

- `TASKS.md` is the canonical tracker authorization for `[RECOVERY-ROUTING-RECORD-RESOLVER-R1]`. It classifies the wave as `L4_ENABLER`, targets `G8`, names `mu/tools/executors/recovery_gate.py` as the structural artifact, supplies the targeted evidence command, and binds the wave to this packet.
- The tracker’s reproduced-before claim is explicitly tied to commit `0794696582002eb8c938c228bac1bc22deccee65`, where it records nine branch-separated canonical reads. Its after-state is marked `[PENDING-UNTIL-MERGE]`; neither that historical statement nor this packet rewrite independently proves current implementation state.
- No blocking bridge finding supplied for this rewrite proves that a planned implementation item is already landed. Consistent with the rewrite-only constraint, no downstream implementation file was inspected; Work item 1 and Stop condition 1 require live in-scope verification before Phase B edits.
- Governing Phase A packet: `reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md` (this document).
- Bridge disposition entering this rewrite: `REQUEST_CHANGES`, limited to replacing the echoed stub with an independent plan, adding stop conditions and acceptance criteria, and restoring grounding plus mechanically consumable same-wave authorization.

Authorization: TASKS.md authorizes this bounded same-wave L4_ENABLER plan for G8.

FOUNDER_OVERRIDE:recovery-routing-record-resolver-r1-2026-08-30

Routed next-candidate:
recovery-routing-record-resolver-r1-2026-08-30

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id recovery-routing-record-resolver-r1-2026-08-30 --output reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md`, `reports/deferred/non_blocking/recovery-routing-record-resolver-r1-2026-08-30_bridge_nonblockers.md`, `reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: recovery-routing-record-resolver-r1-2026-08-30.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `recovery-routing-record-resolver-r1-2026-08-30`
- Active packet: `reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md`
- Indicator artifact: `reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md`
  - `reports/deferred/non_blocking/recovery-routing-record-resolver-r1-2026-08-30_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `recovery-routing-record-resolver-r1-2026-08-30`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/recovery-routing-record-resolver-r1-2026-08-30_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-routing-record-resolver-r1-2026-08-30`
- Active packet: `reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `82529bb689f16f9c8f3546d7b4c8610124fd07f420d25f99a6d411c00c6feb55`
- Indicator artifact: `reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md`, `reports/deferred/non_blocking/recovery-routing-record-resolver-r1-2026-08-30_bridge_nonblockers.md`, `reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery-routing-record-resolver-r1-2026-08-30_2026-08-30.md`
  - `reports/deferred/non_blocking/recovery-routing-record-resolver-r1-2026-08-30_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-routing-record-resolver-r1-2026-08-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
