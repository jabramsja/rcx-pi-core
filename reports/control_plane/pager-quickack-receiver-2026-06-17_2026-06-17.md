# Pager-Quickack-Receiver-2026-06-17 2026-06-17

Date: 2026-06-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pager-quickack-receiver-2026-06-17
Phase-A-Lock: LOCKED
Purpose: Pager quick-ack Wave 1: new DORMANT mu/tools/session/claude_pager_receiver.py (file-queue inbox + serialized fresh `claude -p` async delivery + reaper + idempotency + fail-open) + unit tests; growth caps bumped. No pager wiring yet (Wave 2). Restores reliable direct pipeline paging for Claude, separate from the autoping monitor.

## Scope

Files/directories in scope (additive, tooling-only -- no runtime/substrate):

- `mu/tools/session/claude_pager_receiver.py` -- NEW. The dormant quick-ack receiver daemon (created this wave).
- `mu/tests/tools/test_claude_pager_receiver.py` -- NEW. Unit tests for the receiver (created this wave).
- Growth-caps registry -- bump `CAP_TOOL_SCRIPTS` +1 and `CAP_TEST_FILES` +1 (enforced by `mu/tests/docs/test_growth_caps.py`) to admit the two new files.
- `mu/tools/observability/pipeline_agent_pager.py` -- READ-ONLY reuse of its existing `_claude_dispatch_env` helper. NOT modified by this wave.

- `reports/deferred/non_blocking/pager-quickack-receiver-2026-06-17_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

Concrete bounded tasks (derived from the TASKS.md:541 `evidence_delta`):

1. Create `mu/tools/session/claude_pager_receiver.py` -- a DORMANT, self-contained quick-ack receiver daemon implementing:
   - Per-bus file-queue inbox; atomic enqueue IS the quick-ack (enqueue returns as soon as the event is durably queued).
   - Serialized, single-flight delivery via a fresh `claude -p` invocation, run asynchronously; never `--resume`.
   - ~120s per-delivery timeout plus a process-group reaper (kill the whole child process group on timeout/exit).
   - Delivery environment sourced through `pipeline_agent_pager._claude_dispatch_env` (no session-id clobber).
   - Exit-0 -> write a receipt; non-zero exit or timeout -> fail-open re-queue.
   - Idempotency keyed by `event_id` / `transition_key` (a duplicate event is not re-delivered).
   - DORMANT: nothing imports, wires, or starts it (no pager wiring, no preflight start).
2. Create `mu/tests/tools/test_claude_pager_receiver.py` -- unit tests that lock every behavior in Work Item 1 using a MOCKED subprocess (no real `claude` process): atomic-enqueue quick-ack, serialized single-flight, never-`--resume`, timeout + process-group reap, env passthrough without session-id clobber, exit-0-receipt vs fail-open re-queue, and `event_id`/`transition_key` idempotency.
3. Bump growth caps: `CAP_TOOL_SCRIPTS` +1 (new tool script) and `CAP_TEST_FILES` +1 (new test file) so the additive files pass `mu/tests/docs/test_growth_caps.py`.

## Constraints (NOT in scope)

- NO pager wiring -- the receiver stays dormant; nothing dispatches into it. (Wave 2.)
- NO preflight or daemon auto-start. (Wave 3.)
- NO changes to `pipeline_agent_pager.py` dispatch behavior -- reuse `_claude_dispatch_env` read-only only.
- NO real `claude` subprocess in tests -- the subprocess boundary must be mocked.
- NO runtime/substrate edits -- must NOT touch `rcx_pi/selfhost/` or `mu/host/` (L4_ENABLER must not touch runtime dirs); no L3 parity / JS-mirror change.
- NO autoping-monitor changes -- this direct-paging path is separate from the autoping monitor.
- NO `--resume` -- deliveries are always a fresh `claude -p`.

## Stop Conditions

- Stop once the three work items land and the evidence command is green. Do NOT begin Wave 2 (pager wiring) or Wave 3 (preflight start).
- If the receiver cannot be built without modifying `pipeline_agent_pager.py` dispatch logic (beyond read-only `_claude_dispatch_env` reuse) or touching a runtime dir, STOP and re-scope -- that exceeds L4_ENABLER bounds.
- If the growth-caps reconciliation needs anything other than +1 tool script / +1 test file, STOP and reconcile the file inventory before proceeding.
- Phase A ends when this packet is agent-reviewed and bridge-converged; do NOT start Phase B implementation from within Phase A.

## Acceptance Criteria

- `mu/tools/session/claude_pager_receiver.py` exists, is dormant (no importers/starters in the tree), and implements all seven behaviors in Work Item 1.
- `mu/tests/tools/test_claude_pager_receiver.py` exists and passes, locking every listed behavior with a mocked subprocess (no real `claude`).
- Growth caps reflect exactly `CAP_TOOL_SCRIPTS` +1 and `CAP_TEST_FILES` +1; `mu/tests/docs/test_growth_caps.py` passes.
- Evidence command green: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_claude_pager_receiver.py --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- `mu/tools/checks/check_host_semantics_ratchet.py` passes -- no new host semantics (additive observability tooling only).
- No diff under `rcx_pi/selfhost/` or `mu/host/`; no JS parity change required.

## Grounding / Authorization

- Authorized by TASKS.md:541 -- Tracker sync note (2026-06-17, pager-quickack-receiver-2026-06-17), task `[NEXT-CODEX-POST-REDTEAM]`, Class L4_ENABLER, `target_gate_id` G8, `structural_artifact_ref` `mu/tools/session/claude_pager_receiver.py`.
- Governing packet: this file -- `reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md`.
- Control-surface L4_ENABLER wave-bound override: `FOUNDER_OVERRIDE:pager-quickack-receiver-2026-06-17 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)` (present at TASKS.md:541; recorded here verbatim so commit automation derives the same-wave override mechanically).
- `primary_blocker_class`: INTEGRATION; `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION. Full machine-readable L4 field set is in the auto-derived block below.

## Request from Post-Merge Supervisor

Pager quick-ack Wave 1: new DORMANT mu/tools/session/claude_pager_receiver.py (file-queue inbox + serialized fresh `claude -p` async delivery + reaper + idempotency + fail-open) + unit tests; growth caps bumped. No pager wiring yet (Wave 2). Restores reliable direct pipeline paging for Claude, separate from the autoping monitor.

Routed next-candidate:
pager-quickack-receiver-2026-06-17

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pager-quickack-receiver-2026-06-17.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-quickack-receiver-2026-06-17 --output reports/l4_wave_indicators/pager-quickack-receiver-2026-06-17.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_claude_pager_receiver.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pager-quickack-receiver-2026-06-17 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pager-quickack-receiver-2026-06-17`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pager-quickack-receiver-2026-06-17_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-quickack-receiver-2026-06-17`
- Active packet: `reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `eec98121bb113dc1b0605bc1a2c7dfcfbbe9d54014e20e21c01cdc028121aed8`
- Indicator artifact: `reports/l4_wave_indicators/pager-quickack-receiver-2026-06-17.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_claude_pager_receiver.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pager-quickack-receiver-2026-06-17.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_claude_pager_receiver.py`
  - `mu/tools/session/claude_pager_receiver.py`
  - `reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md`
  - `reports/deferred/non_blocking/pager-quickack-receiver-2026-06-17_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-quickack-receiver-2026-06-17.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
