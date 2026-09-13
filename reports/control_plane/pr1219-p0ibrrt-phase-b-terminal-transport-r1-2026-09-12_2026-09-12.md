# PR1219 P0IBRRT lossless Phase B terminal-result transport

Date: 2026-09-12
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRT-PHASE-B-REFUSAL-TRANSPORT]
Wave ID: pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 0256cabc1396a052cd7565490a2b30240a59cc96edad602025fb0f4193493206
Purpose: Land the EXISTING NEXT P0IBRRT obligation after PR1295, not a new prerequisite. Preserve the strict bridge terminal result across the four existing Phase B review failure paths so the already-queued RR consumer receives actual terminal evidence. Transport only; do not implement provider-refusal policy.

## Scope

One production module and its existing test module: lossless opaque terminal-result transport through normal, reentry, private-attribute and reentry-private-attribute review failures. Preserve recognized verdict precedence and all landed lifecycle authority. Bounded tracker/governance only; existing RRT current, RR next.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py -- preserve qualified opaque bridge terminal objects with exact invocation and complete-stream artifact bindings on the four existing failure paths; no policy consumer or other production module.
- mu/tests/tools/test_phase_b_executor.py -- fresh public-path before/after transport reproductions, full object equality beyond stderr byte500, same four-path schema, focused job/role/format/sentinel rejection and established verdict controls.
- TASKS.md and CHANGELOG.md -- bounded PR1295 landing credit and existing RRT CURRENT/RR immediately NEXT; preserve every queue identity/semantic order and all stopped/held/consumed-operation evidence.
- reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md, reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json, optional reports/deferred/non_blocking/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_bridge_nonblockers.md -- fresh native same-wave governance; root external WaveConfig is excluded from candidate staging.
- TASKS.md -- tracker-sync authority. The 2026-09-12 tracker sync note for wave `pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start only in an unused exact-e8bb22ee251c5bf81f7ca6d98651fd507e508257 worktree/branch/bus. Read current merged code and reproduce the missing transport through actual public Phase B paths; existing historical stub is intent/evidence only, never packet/receipt/checkpoint authority. Root authors this STUB and bounded TASKS seed; native Phase A writes the full packet.
2. Only after an existing bridge-review failure with nonzero integer exit other than executor sentinels -1/-2/-3, consider its final nonblank complete stderr line. That whole line must decode as one top-level JSON object whose direct agent_role is exactly "reviewer", direct job_id equals the exact nonempty active invocation id AND bridge_result["job_id"], and direct error_code and terminal_decision are nonempty strings after strip. Nested, historical, prose-wrapped, malformed, mismatched or successful data does not qualify. Extra direct members remain opaque; preserve the complete decoded object unchanged, not selected/normalized fields.
3. For a qualifying existing failure return the sole canonical direct bridge_terminal_result key with that entire object, together with bridge_exit_code exactly equal to bridge_result["exit_code"], bridge_job_id equal to active invocation id, bridge_stdout_path equal to bridge_result["stdout_path"] and bridge_stderr_path equal to bridge_result["stderr_path"]. Paths refer to the complete captured streams. Apply the same schema to normal, reentry, private-attribute and reentry-private-attribute failures, including replacement mappings; a bounded errors summary is not authority. Nonqualifying failures omit bridge_terminal_result and bridge_exit_code.
4. Keep existing recognized GO/NO_GO/REQUEST_CHANGES/QUESTION precedence, success/recoverable-review behavior, checkpoint cleanup/ownership and failure status/step semantics unchanged. Add evidence only to actual failure returns; do not reinterpret terminal_decision/error_code, reparse other fields downstream, or implement refusal classification/retry/staleness policy. RR remains the queued policy consumer.
5. Use the smallest public before/after tests proving the actual transport gap, with existing lifecycle and verdict tests as controls. Run cheap current control-surface invariants first, focused regressions while iterating, then the complete unchanged declared Phase B module suite. Use ordinary external OS temporary fixtures, never new .scratch test trees or repo-nested TMPDIR. Do not alter production/test bytes during a full validation run.
6. Native owners regenerate only same-wave governance, then independent review, providerless commit/push/PR/CI/merge and primary fast-forward. Preserve the exact RRC landing/exit1 evidence and held TASKS stash249344221c03f8c1baa551f36e51efb61a2c4422. Do not replay merged/stopped carriers or either consumed fleet operation. RR immediately follows; no added queue position.

## Constraints

- Root supplies external STUB and bounded tracker seed only; launch_wave.py/dispatcher/Phase A/Phase B/native commit/recovery own full packet, implementation, staging, receipts and GitHub landing. No manual git fallback or copied old approval authority.
- Production changes limited to phase_b_executor.py; tests limited to test_phase_b_executor.py. Do not modify dispatcher, recovery_gate, executor_common, launcher, commit executor, adapters, bridge supervisor/prompts, model topology, Claude-owned files, runtime/host/substrate/seed/projection or OS/fleet handling.
- All selected local model-bearing roles use Codex gpt-6-astra/max; commit remains providerless. Committed configuration already provides these settings and must remain untouched.
- This is the existing RRT queue identity, not a new prerequisite. Preserve RR/IB1/IB2 and every later task; Mu production before optimization. Do not chase generic robustness, hypothetical lifecycle windows or unrelated nonblockers.

## Stop conditions

- Before launch require exact e8bb22ee251c5bf81f7ca6d98651fd507e508257, fresh unused target/branch/bus/session, PR1295 actually merged and PRIMARY fast-forward verified, old mutating owners absent, model pins correct and providerless commit. Predecessor's diagnosed post-retirement exit1 is preserved; exit0 is not falsely required or claimed.
- If fresh public reproduction establishes existing coverage already satisfies this obligation, return exact evidence for honest native reclassification/closeout; do not invent a defect.
- If a reproduced blocker requires an excluded production module, report its exact producer/consumer boundary once; do not silently expand or repeat a known scope contradiction.
- Fail closed for unbound/altered/omitted qualified terminal authority or changed established verdict behavior. Do not halt for unrelated hypothetical cases or nonblockers.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py --tb=short`

## Acceptance criteria

- Fresh public-path before/after proof on exact PR1295 shows lossless strict terminal transport through all four paths, including data beyond byte500; complete object equality and all four exact companion bindings are asserted.
- Unqualified data remains generic without bridge_terminal_result/bridge_exit_code; sentinel/success and established GO/NO_GO/REQUEST_CHANGES/QUESTION handling are unchanged.
- Prepared-review, ordinary/general ownership and reentry-private context guarantees from1291/1292/1294/1295 remain intact. No provider-policy consumer or unrelated production path changes.
- Complete Phase B tests, current invariants, fresh independent reviews and native required gates pass. Actual commit/CI/merge/primary fast-forward are verified, not inferred from review approval.
- Existing RRT is the sole CURRENT queue row, RR immediately NEXT and every later queue/TODO identity and order retained; no new prerequisite.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRT-PHASE-B-REFUSAL-TRANSPORT]; wave id `pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md`.
- TASKS.md authority: the 2026-09-12 tracker sync note for wave `pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12 --output reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md`, `reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `01a70aac675003c0f28a5dc57ad0f9fc0c9cc5e48634b338673bcdfcff4b4c28`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md`, `reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12_2026-09-12.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrt-phase-b-terminal-transport-r1-2026-09-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
