# Phase-A-Postwrite-Canonical-Read-Only-R5-2026-08-27 2026-08-27

Date: 2026-08-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PHASE-A-POSTWRITE-CANONICAL-READ-ONLY-R5]
Wave ID: phase-a-postwrite-canonical-read-only-r5-2026-08-27
Phase-A-Lock: LOCKED
Purpose: Design the bounded Phase A change that orders the ordinary regular bridge-loop post-implementer canonical packet read before implementer-completed emission, fails closed for missing, directory, unreadable, and invalid-UTF-8 inputs, and preserves readable-packet behavior.

## Scope

- `mu/tools/executors/phase_a_executor.py`: only the existing ordinary regular bridge-loop post-implementer canonical `plan_file.read_text` boundary and its immediately adjacent `phase_a_implementer_completed` emission block. The event block is in scope solely for relocation after a successful canonical read; its payload, transition key, and emission-failure behavior are not redesigned.
- `mu/tests/tools/test_phase_a_executor.py`: only focused coverage for the four targeted canonical-read failures and the currently uncovered readable-unchanged post-implementer branch. The existing readable-changed post-implementer test remains the regression evidence for that already-covered branch and is not a pending coverage item.
- This Markdown file is the governing Phase A design packet. This rewrite does not implement the executor or test changes.

- `reports/deferred/non_blocking/phase-a-postwrite-canonical-read-only-r5-2026-08-27_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reorder the two adjacent executor blocks so the post-implementer canonical `plan_file.read_text(encoding="utf-8")` attempt and its failure decision occur before `phase_a_implementer_completed`. Relocate the existing completion-event block to the successful-read path without changing its arguments or its existing pager-emission error handling.
2. Replace the current read-failure fallback-to-`current_plan_content` behavior with one existing-style structured `status = "error"` / `error = <message>` return for missing-file, directory, unreadable/permission-denied, and invalid-UTF-8 failures. Return immediately, before implementer-completed, any later review, or lock, and make exactly one post-implementer canonical-read attempt.
3. Add one compact parametrized focused test that arranges each targeted failure after the implementer: missing packet, packet path replaced by a directory, permission denied by mocking the canonical read, and invalid UTF-8 bytes. For every case, assert the structured error, one post-implementer read attempt, absence of `phase_a_implementer_completed`, and no post-failure review or lock advancement.
4. Add a dedicated readable-unchanged post-implementer test whose mocked `_invoke_implementer` succeeds without modifying the packet. Assert that the canonical read succeeds, packet bytes remain unchanged, no read error is returned, `phase_a_implementer_completed` is emitted, and the executor retains its pre-existing unchanged-branch result and call sequence.

## Constraints

- The implementation change is limited to the two scoped files. In the executor, edits are limited to the existing ordinary regular canonical read/failure block and relocation of its immediately preceding completion-event block far enough to make successful read a prerequisite for that event.
- Do not change the completion event's type, state, transition key, summary, artifacts, bus routing, or existing pager-emission failure result; only its order relative to the canonical read may change.
- Do not add or change changed-path snapshots, changed-path scope enforcement, agent-bus or scratch filtering or authority, line-reference logic, git index or HEAD handling, or pycache behavior.
- Do not broaden behavior for path aliases, symlinks, hardlinks, FIFOs, or any other special files.
- Do not change implementer or checker exception handling, concurrency, lifecycle, reentry or recovery, strict-L4 or lock behavior, the launcher, Phase B, commit or later executors, documentation wording, no-op metadata, or related tests outside the focused coverage.
- Do not add a second readable-changed test or otherwise re-list that existing coverage as pending work.
- Do not add retry behavior or changed-path authority work.
- During the implementation wave, Phase A alone owns generated-packet revisions; any out-of-scope observation belongs only in the optional same-wave nonblocking report.
- Keep all model-bearing roles and the pager on Codex; keep terminal commit execution providerless/null.

## Stop conditions

- Stop without widening scope if the required ordering cannot be achieved by the bounded canonical-read edit and relocation of the one adjacent completion-event block, or if it would require any other file, boundary, behavior, or test excluded above.
- For any of the four targeted read failures, stop Phase A advancement at the structured error: do not emit implementer-completed, request further review, lock, or retry.
- Stop before review or lock if the new readable-unchanged test or the existing readable-changed regression evidence fails.
- Stop and leave the wave unclosed if the focused evidence command does not pass.

## Acceptance criteria

- The implementation diff is confined to `mu/tools/executors/phase_a_executor.py` and `mu/tests/tools/test_phase_a_executor.py`; the executor diff touches only the ordinary regular post-implementer canonical read/failure block and the immediately adjacent completion-event block needed for ordering.
- The canonical read completes successfully before `phase_a_implementer_completed` is emitted. The relocated event retains its existing arguments and pager-emission error behavior.
- Missing-file, directory, mocked permission-denied, and invalid-UTF-8 reads all produce one existing-style structured error and return before implementer-completed, any later review, or lock, with no canonical-read retry.
- One compact parametrized focused test covers all four targeted failure cases, including permission denied by mocking the canonical read, and proves the error, event absence, downstream non-advancement, and single-attempt behavior.
- One dedicated test drives a successful `_invoke_implementer` that leaves the readable packet unchanged and proves the existing unchanged-branch result, unchanged packet bytes, successful completion emission, and absence of a canonical-read error.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_phase_a_executor.py` passes.
- No excluded control surface, behavior, executor, documentation wording, metadata, or unrelated test is changed.

## Grounding / Authorization

- Canonical authorization: `TASKS.md` records this wave as `L4_ENABLER`, targets `G8`, names this packet, names `mu/tools/executors/phase_a_executor.py` as the structural artifact, supplies the focused evidence command, and marks the post-merge progress proof pending.
- Governing packet: `reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md`.
- Current executor truth: `mu/tools/executors/phase_a_executor.py` emits `phase_a_implementer_completed` before attempting the canonical read, then converts `OSError` read failures into unchanged content. Therefore both the adjacent event relocation and the fail-closed read result remain pending; a read-boundary-only edit cannot satisfy the required ordering.
- Current test truth: `mu/tests/tools/test_phase_a_executor.py` has a mocked implementer that appends `Implementation note.` and asserts implementer-completed, so readable-changed post-implementer coverage is already present and is not pending. The targeted reviewer search found no corresponding mocked-implementer test that leaves a readable packet unchanged, so that dedicated branch proof remains pending.
- Grounding boundary: this rewrite uses only the governing packet, `TASKS.md`, the cited executor ordering/read block, the cited focused-test matches, and the two authoritative bridge blocking findings. The auto-derived tracker field block below is preserved verbatim; the human-authored scope resolves its stale read-boundary-only wording by including only the adjacent event relocation mechanically required by current code order.

FOUNDER_OVERRIDE:phase-a-postwrite-canonical-read-only-r5-2026-08-27

Routed next-candidate: `phase-a-postwrite-canonical-read-only-r5-2026-08-27`

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-a-postwrite-canonical-read-only-r5-2026-08-27 --output reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tools/executors/phase_a_executor.py`, `reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md`, `reports/deferred/non_blocking/phase-a-postwrite-canonical-read-only-r5-2026-08-27_bridge_nonblockers.md`, `reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: phase-a-postwrite-canonical-read-only-r5-2026-08-27.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `phase-a-postwrite-canonical-read-only-r5-2026-08-27`
- Active packet: `reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md`
  - `reports/deferred/non_blocking/phase-a-postwrite-canonical-read-only-r5-2026-08-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `phase-a-postwrite-canonical-read-only-r5-2026-08-27`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/phase-a-postwrite-canonical-read-only-r5-2026-08-27_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-a-postwrite-canonical-read-only-r5-2026-08-27`
- Active packet: `reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `64db5382c13cec21236808f5fcff6f98f589360c771d09a0250bda47d88c07d3`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_a_executor.py`, `mu/tools/executors/phase_a_executor.py`, `reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md`, `reports/deferred/non_blocking/phase-a-postwrite-canonical-read-only-r5-2026-08-27_bridge_nonblockers.md`, `reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/phase-a-postwrite-canonical-read-only-r5-2026-08-27_2026-08-27.md`
  - `reports/deferred/non_blocking/phase-a-postwrite-canonical-read-only-r5-2026-08-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-a-postwrite-canonical-read-only-r5-2026-08-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
