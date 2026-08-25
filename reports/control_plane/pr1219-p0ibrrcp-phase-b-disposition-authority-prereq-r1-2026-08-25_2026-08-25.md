# PR 1219 P0IBRRCP Phase B Disposition Authority Prerequisite R1 2026-08-25

Date: 2026-08-25
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-NORMAL-ROOT-RECORDED-CHILD-CLEANUP]
Wave ID: pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25
Phase-A-Lock: LOCKED
Purpose: Land only the active shared Phase B/recovery disposition blocker exposed by preserved reviewer-causality R3. An explicit blocking finding must remain blocking regardless of low or medium severity, lifecycle status, or pre-existing provenance; an explicit non_blocking finding remains deferrable below the independent high/critical floor unless exact mandatory-impact evidence promotes it. Recovery and Phase B must share this contract so neither path can silently relabel a blocker.

## Scope

Fresh four-file functional prerequisite from exact PR #1242 merge d59. Correct the single shared Phase B/recovery disposition seam, add exact focused regressions, and atomically replace the stale broad queue row with an exact current/next baton while preserving every existing task and TODO.

Files and surfaces in scope:

- mu/tools/executors/recovery_gate.py (MODIFY) -- make the shared GO-deferrability predicate honor structured blocking/non_blocking, independent severity floors, invalid-disposition fail-closed behavior, and an exact promotion-only mandatory-evidence conjunction.
- mu/tools/executors/phase_b_executor.py (MODIFY) -- continue delegating to the shared recovery contract, consume the same promotion helper before structured disposition and heuristic fallback, and update stale comments/reasons without adding a second divergent classifier.
- mu/tests/tools/test_recovery_gate.py (MODIFY) -- prove recovery cannot Tier-1 defer or rewrite explicit or exact-marker mandatory blockers and still defers valid low/medium explicit nonblockers.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- prove both disposition directions, severity floors, invalid values, exact omission fallback, and non-GO/GO integration behavior.
- TASKS.md (MODIFY) -- record exact PR #1242 landing, make this exact dated wave the sole parser-visible CURRENT row, make bridge-envelope validation the sole exact dated NEXT row, remove the stale numbered broad route, preserve R3 and every earlier attempt as nonlaunchable evidence, serialize the remaining P0IBRRCP chain unambiguously, and retain every existing task/TODO plus the ordered preservation-first PR/fleet cleanup obligations.
- reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md (GENERATED) -- single canonical governing packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json (GENERATED BEFORE REVIEW) -- same-wave staged indicator.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblocking observations only.
- TASKS.md -- tracker-sync authority. The 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Correct recovery_gate._finding_is_deferrable_on_go as the shared authority. Non-dict input, explicit blocking, invalid or ambiguous explicit disposition, high/critical severity, and exact mandatory-evidence promotion are not deferrable. Canonical explicit non_blocking at low/medium remains deferrable. Preserve ordinary missing-disposition low/medium behavior outside the exact promotion case.
2. Add one shared promotion-only helper that parses semicolon/newline-delimited evidence_result key=value clauses with trimmed case-normalized keys and values. Promote only when complete clause values contain both TECHNICAL_IMPACT_CLASS=declared hard-invariant violation and MERGE_DISPOSITION=blocking. Do not generic-substring-search, do not treat free-text non_blocking as downgrade authority, and do not add an envelope field.
3. Use the shared promotion helper in Phase B after the independent high/critical floor but before the structured-disposition branch and before class/path/title fallback. Exact mandatory evidence must not be bypassed by a structured non_blocking value. Keep a distinct reason for this promotion so tests and receipts prove the path.
4. Prove low and medium explicit blocking remain blocking regardless of persisting/pre-existing status or nonblocking-looking context; low/medium explicit non_blocking remains deferrable absent an independent floor; high/critical explicit non_blocking remains blocking; invalid disposition fails closed; and non-dict recovery input is not deferrable.
5. Add integration coverage proving GO and REQUEST_CHANGES/NO_GO with a medium explicit blocker cannot auto-converge or emit a deferred packet; recovery cannot classify or rewrite that blocker through Tier 1; and valid medium explicit nonblocking behavior remains intact.
6. Add the exact omission regression from R3: low/medium finding with no structured disposition but the exact two mandatory evidence_result clauses is blocking in Phase B, not deferrable in recovery, creates no deferred packet, and is never rewritten. Incomplete marker pairs retain existing behavior.
7. Synchronize TASKS atomically. Mark Q2 LANDED through PR #1242 at exact d59; replace numbered pr1219-p0ibrrcp-land-2026-08-23 with this exact dated wave as the sole CURRENT simple row; add exact dated pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r1-2026-08-25 as the sole immediate NEXT simple row; put Task/Wave prose on following indented lines without Wave ID or Packet literals on either numbered line.
8. Under the current row, serialize but do not separately number: fresh reviewer-causality R4, commit-evidence R2, Phase-B evidence handoff R2, fresh routing R4, R3C5, R3C6, exact P0IBRRCP closure, then P0IBRRCO -> P0IBRRC -> P0IBRRT -> P0IBRR -> P0IB1 -> P0IB2. State explicitly that R3C5/R3C6 do not themselves satisfy the later P0IBRRCO obligation.
9. Preserve R3 as Phase B NO_GO with six blocking and three nonblocking findings and preserve all earlier stopped candidates as noncomplete evidence below the NON-LAUNCHABLE/history boundary. Retain every existing policy/TODO item. Keep later order PR-LIVE-CENSUS -> NEVER-BEHIND carry-forward -> PR-DISPOSITION -> FLEET-CLEANUP-BUILDER -> FLEET-CLEANUP-APPLY; if builder/apply rows are absent, add bounded planning/apply obligations without nonexistent config citations or volatile debt counts.
10. After exact merge, create the fresh external bridge-envelope-validation WaveConfig from that merge SHA with the identical NEXT wave ID and launch it through launch_wave.py. Do not resume or copy any preserved candidate.

## Constraints

- Literal production/test scope is only recovery_gate.py, phase_b_executor.py, test_recovery_gate.py, and test_phase_b_executor.py, plus TASKS.md and exact same-wave generated governance.
- Do not edit bridge_supervisor.py, test_agent_bridge_supervisor.py, commit_executor.py, bridge_adapters.py, launch_wave.py, executor_dispatch.py, receipt code, runtime, substrate, hosts, seeds, projections, registries, provider routing, process cleanup, Claude-owned files, or preserved candidates.
- Do not broaden missing-disposition heuristics beyond the exact promotion conjunction. Do not add named-finding allowlists, baseline fingerprints, lifecycle-based downgrades, causal-provenance downgrades, or reviewer-envelope rewriting.
- Do not fix the separate malformed nested-envelope blocker or the explicitly nonblocking wrong-identity, stale-count, or missing-future-config observations in this wave. Bridge-envelope validation is the one serialized NEXT packet.
- Do not retain numbered pr1219-p0ibrrcp-land-2026-08-23. Do not leave R3 open in PROGRAM QUEUE. Do not create numbered rows for any successor beyond the exact bridge-envelope-validation NEXT.
- Source HEAD, target initial HEAD, comparison_commit, origin/dev, and remote dev must equal d59c591a7f802c3cfcd744a30e0edb2dd8d56760 before launch; identities must be collision-free.
- Use launch_wave.py and the normal immutable-source dispatcher, Phase A, Phase B, providerless commit, push, PR, CI, and merge surfaces. No manual candidate patch, stage, commit, push, PR mutation, merge, or target-source substitution.
- Codex implements and reviews; pager route is Codex; commit remains providerless. Do not weaken literal allowlist, staged L4, candidate authority, commit verification, CI, or merge gates.

## Stop conditions

- Stop before launch if exact d59 source/remote authority is unavailable, the source is attached or dirty, identity collides, providerless commit is unavailable, or the Codex implementer/reviewer route is unavailable.
- Stop as NEEDS_RESCOPING if closure requires a functional file beyond the four declared production/test files or requires bridge, commit, launcher, dispatcher, adapter, receipt, runtime, substrate, or provider changes.
- Stop as DEFECT if explicit low/medium blocking can be deferred, explicit low/medium non_blocking is promoted without independent proof, high/critical can be deferred, invalid structured disposition is accepted, Phase B and recovery use divergent rules, or recovery can rewrite a mandatory blocker.
- Stop as DEFECT if generic text matching promotes ordinary findings, free-text non_blocking becomes downgrade authority, persisting/pre-existing status authorizes deferral, or incomplete marker pairs change existing missing-disposition behavior.
- Stop and preserve if blockers fail to decrease after one bounded correction or require malformed-envelope validation. Do not absorb the bridge NEXT packet or any nonblocker.
- Do not stop or widen for documentation polish, dynamic fleet counts, missing future configs, wrong envelope identity without a demonstrated live replay, or any other explicitly nonblocking/non-occurring edge.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- The candidate changes only TASKS.md, the four declared production/test files, and exact same-wave packet/indicator/optional-nonblocker artifacts.
- One shared recovery-owned predicate/helper keeps Phase B and recovery behavior identical: explicit blocking and exact mandatory promotion block; explicit low/medium non_blocking defers absent an independent floor; high/critical and invalid structured disposition block.
- The exact evidence_result conjunction is parsed at clause boundaries and is promotion-only. The R3 omission probe returns blocking, recovery refuses Tier 1, no deferred packet is created, and no blocker is rewritten.
- Focused unit/integration tests cover both explicit-disposition directions, independent severity floors, invalid values, persisting/pre-existing context, exact and incomplete marker pairs, GO plus non-GO decisions, and recovery fix-path behavior without broadening ordinary missing-disposition handling.
- TASKS records Q2 LANDED through PR #1242 at exact d59, this exact wave as sole CURRENT, bridge-envelope validation as sole immediate NEXT, no numbered broad P0IBRRCP row, unambiguous remaining P0IB order, all stopped candidates including R3 as noncomplete evidence, every existing TODO, and the later preservation-first PR/fleet cleanup sequence.
- A direct parser probe selects this exact wave before merge; the same probe with exact current-wave merge-history completion simulated selects bridge-envelope validation and never selects pr1219-p0ibrrcp-land-2026-08-23.
- The exact two-file evidence command passes, Python compilation passes, staged L4 is compliant, and providerless commit, push, PR, CI, and merge complete through the normal pipeline.
- After merge, bridge-envelope validation is freshly configured and launched from the exact merge SHA; no preserved candidate is resumed, copied, or mutated.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-NORMAL-ROOT-RECORDED-CHILD-CLEANUP]; wave id `pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md`.
- TASKS.md authority: the 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25` is canonical for this packet's L4 fields.
- Authorization: Committed d59 TASKS already authorizes the P0IBRRCP parent task after Q2. It also retains PBNOGO authority requiring explicit blocking NO_GO/REQUEST_CHANGES findings to remain blocking. Preserved R3 directly reproduced both shared disposition directions and the exact omission fallback, while the founder directed autonomous builder-only landing, narrower packets on nonconvergence, full TASKS/TODO preservation, and no delay for nonblockers. This packet addresses only that active shared mechanism and its required queue baton.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 9 pytest selector(s) across 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2114de8a66917fd25a780ba08bc6f12c4cf6d699c3a9dd382f63a8c0a31ced8b`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 9 pytest selector(s) across 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_2026-08-25.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-phase-b-disposition-authority-prereq-r1-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
