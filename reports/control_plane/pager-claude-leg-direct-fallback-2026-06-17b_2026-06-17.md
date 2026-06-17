# Pager-Claude-Leg-Direct-Fallback-2026-06-17B 2026-06-17

Date: 2026-06-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pager-claude-leg-direct-fallback-2026-06-17b
Phase-A-Lock: LOCKED
Purpose: Pager Claude-leg fix: when no usable dedicated monitor session, fall back to a direct `claude -p` page (fresh, never resumes the orchestrator) instead of failing closed -- restores direct pipeline paging for Claude; keep monitor --resume when a distinct monitor is registered.

Class: L4_ENABLER (control-plane/observability tooling prerequisite for gate G8).
Provenance: routed NEXT-CODEX-POST-REDTEAM candidate from the post-merge supervisor; bound to the canonical TASKS.md tracker note (2026-06-17, pager-claude-leg-direct-fallback-2026-06-17b).

## Problem (current behavior)

The dedicated-monitor refactor replaced the pager's direct Claude page with a fail-closed branch. Today, when no dedicated Claude monitor session is running, `_dispatch_claude` in `mu/tools/observability/pipeline_agent_pager.py` skips every pipeline event with `CLAUDE_SKIP_REASON_MONITOR_UNSET`, so Claude is never paged from the pipeline. This is a regression from the pre-refactor direct `claude -p` dispatch (tracker `progress_proof_before`).

## 1. Scope (files / directories in scope)

- `mu/tools/observability/pipeline_agent_pager.py` — the `_dispatch_claude` Claude-leg dispatch path only. This is the single structural surface (`structural_artifact_ref`).
- `mu/tests/tools/test_pipeline_agent_pager.py` — regression tests locking the three delivery cases.
- `reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md` — this governing packet.
- `reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json` — generated indicator artifact (`indicator_artifact_ref`).
- `TASKS.md` — the existing wave tracker note (already present; bound here, not re-authored).

## 2. Work items (concrete, bounded; all three currently pending)

1. **Direct fallback in `_dispatch_claude`.** When the dedicated `claude_monitor_session_id` is (a) absent, (b) malformed, or (c) equal to the live orchestrator session id, stop returning `CLAUDE_SKIP_REASON_MONITOR_UNSET` and instead page Claude with a DIRECT `claude -p` call in a fresh subprocess. The direct page MUST NOT pass `--resume` and MUST NOT target the orchestrator session under any of those three conditions.
2. **Retain the monitor `--resume` path.** When a distinct dedicated monitor session is registered (id present, well-formed, and `!=` orchestrator id), keep the existing `claude --resume <monitor>` dispatch unchanged.
3. **Regression tests.** In `mu/tests/tools/test_pipeline_agent_pager.py`, lock all three delivery cases:
   - monitor absent/unset → direct `claude -p` (never resume);
   - distinct monitor registered → `claude --resume <monitor>`;
   - monitor `==` orchestrator → direct `claude -p`, never resume-orchestrator.

## 3. Constraints (NOT in scope)

- L4_ENABLER class: MUST NOT touch runtime/substrate dirs (`mu/host/`, `rcx_pi/selfhost/`, seeds, parity semantics, `mu/host/js/eval_step.js`). This wave is control-plane observability tooling only.
- No new host capabilities or host-only semantics; `check_host_semantics_ratchet.py` must stay green.
- Claude leg only — do not change the codex (or any other) pager leg, monitor-registration semantics, or bridge dispatch beyond the fallback decision inside `_dispatch_claude`.
- Do not hand-edit the auto-derived `L4_FIELDS_FROM_TRACKER` block below.
- No manual git operations — pipeline (Phase B → `commit_executor.py`) only.

## 4. Stop conditions

- All three delivery cases implemented and locked by regression tests, and the `evidence_command` passes end-to-end → proceed to Phase B / commit.
- If "never resumes the orchestrator" cannot be guaranteed without host-only semantics, or the fix cannot be made without touching runtime/substrate dirs (which would contradict the L4_ENABLER class) → STOP and escalate as POLICY_BOUND (possible misclassification).
- If the existing distinct-monitor `--resume` path cannot be retained without regressing it → STOP and report; do not weaken the distinct-monitor case to satisfy the fallback.

## 5. Acceptance criteria

- `evidence_command` passes: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id pager-claude-leg-direct-fallback-2026-06-17b`.
- Each of the three delivery cases is proven by a dedicated regression test in `mu/tests/tools/test_pipeline_agent_pager.py`.
- `check_host_semantics_ratchet.py` reports no new host semantics.
- L4 staged contract passes for wave `pager-claude-leg-direct-fallback-2026-06-17b`.
- Indicator artifact regenerated via the `indicator_collection_command`.
- `progress_proof_after` holds: the pager pages Claude directly (`claude -p`) whenever no distinct dedicated monitor session is available, never resuming the live orchestrator, with the monitor `--resume` path retained.

## 6. Grounding / Authorization

- TASKS.md authorization: tracker sync note (2026-06-17, `pager-claude-leg-direct-fallback-2026-06-17b`) — `[NEXT-CODEX-POST-REDTEAM]`, Class `L4_ENABLER`, `target_gate_id: G8`, `structural_artifact_ref: mu/tools/observability/pipeline_agent_pager.py`.
- Governing packet: this file (`reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md`).
- Wave-bound founder override (canonical token form; commit automation derives the same-wave override from this line):

FOUNDER_OVERRIDE:pager-claude-leg-direct-fallback-2026-06-17b

- Authorization: standing pipeline-bug-fix authorization — this wave restores a regressed pipeline control-plane behavior (the Claude pager leg) in tooling only, under the founder's standing authorization for autonomous pipeline-bug fixes (manual-fix-then-structural). Mechanical-gate bypass and force-merge are NOT covered and remain ask-first.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-claude-leg-direct-fallback-2026-06-17b --output reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pager-claude-leg-direct-fallback-2026-06-17b.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pager-claude-leg-direct-fallback-2026-06-17b`
- Active packet: `reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md`
  - `reports/deferred/non_blocking/pager-claude-leg-direct-fallback-2026-06-17b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pager-claude-leg-direct-fallback-2026-06-17b`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pager-claude-leg-direct-fallback-2026-06-17b_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-claude-leg-direct-fallback-2026-06-17b`
- Active packet: `reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `888bc484b2b3d6c356aee0816a250287237647f244f5ce6ceaeaa3ef38a28cac`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pager-claude-leg-direct-fallback-2026-06-17b_2026-06-17.md`
  - `reports/deferred/non_blocking/pager-claude-leg-direct-fallback-2026-06-17b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-leg-direct-fallback-2026-06-17b.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
