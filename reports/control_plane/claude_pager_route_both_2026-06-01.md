# Claude Pager Route Both 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: claude-pager-route-both-2026-06-01b
Phase-A-Lock: LOCKED
Purpose: Enable the Claude pager so pipeline transition events page CLAUDE in addition to Codex, MIRRORING codex's pager/autoping protocol, WITHOUT interfering with codex's pager/autoping (founder directive 2026-05-31). pipeline_agent_pager.py already supports route in {codex, claude, both, notify-only}; _dispatch_claude delivers via claude --resume <orchestrator_session_id> where that id currently equals the LIVE orchestrator session. CRITICAL CONSTRAINT: a bare route=both would dispatch claude --resume against the live orchestrator conversation -- not acceptable. The claude target must be a DEDICATED monitor session distinct from the live orchestrator session (mirroring how codex's pager targets the codex monitor, not the interactive codex).

## Scope

Route pipeline pager events to Claude as well as Codex via a DEDICATED claude monitor (mirror of codex's protocol), non-interfering with codex. The claude-target resolution is LOCKED (see `Locked design` below): `_dispatch_claude` resolves the dedicated claude-monitor session id from a single dedicated monitor-session-id file (a sibling of the live `orchestrator_session_id` file), never falling back to the live orchestrator file, so route=both can never resume the live orchestrator conversation. Scope: mu/tools/observability/pipeline_agent_pager.py (claude-target resolution + the new dedicated-monitor resolver + the equal-to-live guard) + mu/tools/executors/executor_config.json (the `route` selector value only) + regression tests in `mu/tests/tools/test_pipeline_agent_pager.py`. Must NOT touch codex_autoping_* or the codex dispatch path. Claude autoping (keeping the monitor warm) is a separate follow-up; deliver safe pager routing first. Validation gate: tests proving (a) route=both reaches a claude target whose session id is NOT the live orchestrator session, AND (b) the claude leg fails closed (no `claude --resume`) when the dedicated monitor id is missing, malformed, or equal to the live orchestrator session id AND that fail-closed leg is recorded as a distinct skip (never added to `delivered_targets`, no delivery receipt, removed from `pending_targets` so it is neither falsely reported delivered nor retried indefinitely), AND (c) codex dispatch is unchanged. Cite code by function name only, no line numbers.

## Work items

1. In `pipeline_agent_pager.py`, add a read-only dedicated-monitor resolver (proposed `_read_claude_monitor_session_id`) that mirrors `_read_orchestrator_session_id`'s malformed-tolerance discipline exactly (missing file / OSError / non-UTF-8 / empty / whitespace-only / internal-whitespace -> unset) and reads ONLY the dedicated monitor-session-id file. Make `_dispatch_claude` resolve the dedicated claude-monitor session id from that resolver before it issues `claude --resume`, apply the equal-to-live guard (compare against `_read_orchestrator_session_id` for an inequality check only), and fail closed (issue no `claude --resume`) when the monitor id is unset/malformed/equal-to-live. `_dispatch_claude` must no longer use the live orchestrator session id as a `--resume` target. The `route` enum already exists per Purpose (`ALLOWED_ROUTES` / `_resolve_route` / `_requested_targets`), so the delta is the monitor-target resolution, NOT re-adding the enum. Fail-closed dispatch-state & receipt contract: on the fail-closed branch `_dispatch_claude` issues NO subprocess and returns a DISTINCT skip result -- `acknowledged=False` (so `_dispatch_pending_locked`'s delivered branch is never entered: the claude target is never added to `delivered_targets` and `_append_delivery_receipt` is never called for it) PLUS a `skipped`/`skip_reason` marker that distinguishes it from a retryable transient delivery error (which carries `error` and stays pending). Extend `_dispatch_pending_locked` with one claude-only branch on that marker that records the skip distinctly (per-target `attempts`/dispatch record + a distinct skip receipt, NOT a delivery receipt) and parks the claude target in a new `skipped_targets` map on the event entry; extend `_refresh_pending_targets` (and the `_ensure_event_state` entry init) to subtract `skipped_targets` alongside `delivered_targets` so the fail-closed claude target LEAVES `pending_targets` without being marked delivered -- neither falsely reported delivered nor retried indefinitely. Codex never emits the skip marker, so the codex delivered/pending/retry semantics and receipts are unchanged.
2. In `executor_config.json`, carry the pager `route` selector value only (e.g. `pipeline_agent_pager.route = both`), WITHOUT changing codex routing, `codex_autoping_*`, or the codex dispatch path. The dedicated monitor session id is NOT a config value -- it is runtime identity sourced from the dedicated monitor-session-id file (mirror of how the live orchestrator id is a hook-written file, not config), so no session-id value is added to `executor_config.json`.
3. Add regression tests in `mu/tests/tools/test_pipeline_agent_pager.py` asserting the full fail-closed matrix: (a) happy path -- route=both dispatches `claude --resume <monitor id>` where the monitor id is present and != the live orchestrator session id, the claude target lands in `delivered_targets`, a delivery receipt is written, and claude leaves `pending_targets`; (b) missing -- monitor file absent/empty -> the claude leg issues NO `claude --resume` and never targets the live orchestrator session; (c) malformed -- monitor file with internal whitespace / non-UTF-8 / whitespace-only -> treated as unset -> fail closed (no `--resume`); (d) equal-to-live -- monitor id equals the live orchestrator id -> fail closed (no `--resume`, never pages the live conversation). For every fail-closed case (b)/(c)/(d) ALSO assert the locked skip semantic: claude is NOT added to `delivered_targets`, NO delivery receipt is written for the claude target, a distinct skip is recorded (skip marker / skip receipt), and claude is removed from `pending_targets` (parked in `skipped_targets`) so a SECOND `dispatch_pending_events` call does NOT re-attempt the claude leg -- proving it is neither falsely reported delivered nor retried indefinitely. (e) codex unchanged -- the codex dispatch path/payload, its `delivered_targets`/`pending_targets`/retry semantics and receipts, and `codex_autoping_*` are diff-proven unchanged.

Locked design (source / precedence / unset / dispatch-state & receipt behavior) -- no open design point remains for bridge convergence:
- Source (LOCKED): the dedicated claude-monitor session id is read from a single dedicated monitor-session-id file under the observability dir (a sibling of the existing live `orchestrator_session_id` file) via the new read-only resolver, which mirrors `_read_orchestrator_session_id`'s malformed-tolerance discipline exactly. Session ids are runtime identity, so the id lives in a file written by the monitor's own session-start (mirror of how `.claude/hooks/session-start.sh` writes the live orchestrator id), NOT in `executor_config.json`. The pager is read-only on this file; its writer is out of scope for this enabler wave (separate concern, like the live orchestrator writer), and until that writer exists the pager simply fails closed.
- Precedence (LOCKED): single-source. The claude-target resolution reads ONLY the dedicated monitor file. There is NO fallback chain to the live `orchestrator_session_id` file -- the live orchestrator file is never used as a `claude --resume` target.
- Unset / fail-closed behavior (LOCKED): if the dedicated monitor id is unset, missing, malformed, OR equal to the live orchestrator session id, the claude pager leg fails closed -- it issues NO `claude --resume` and does not target the live orchestrator session (the claude leg is recorded as a distinct skip per the Dispatch-state & receipt bullet below -- never marked delivered, no delivery receipt, removed from `pending_targets`, never retried; codex routing is unaffected). The equal-to-live guard reads the live orchestrator id for an inequality check ONLY, never as a resume target.
- Dispatch-state & receipt (LOCKED): the fail-closed claude leg is a DISTINCT SKIP -- not a delivery and not a retryable error. `_dispatch_claude` returns `acknowledged=False` (so `_dispatch_pending_locked`'s acknowledged/delivered branch is never entered: the claude target is never written to `delivered_targets` and `_append_delivery_receipt` is never called for it) together with a `skipped`/`skip_reason` marker that distinguishes it from a transient delivery failure (which carries `error` and stays pending for retry). `_dispatch_pending_locked` records the skip distinctly (per-target `attempts`/dispatch record + a distinct skip receipt, never a delivery receipt) and parks the claude target in a `skipped_targets` map on the event entry; `_refresh_pending_targets` subtracts `skipped_targets` alongside `delivered_targets`, so the claude target LEAVES `pending_targets` without being marked delivered. Net: a fail-closed event is NEITHER silently reported delivered NOR left pending/retried indefinitely. The skip is terminal for that event (a later monitor-writer wave does not re-flood pre-existing skipped wakeups); the happy path (monitor present and != live) is unchanged and still routes through the normal delivered/receipt flow. Codex never emits the skip marker, so the codex delivered/pending/retry semantics and receipts are untouched.

## Constraints (NOT in scope)

- MUST NOT touch `codex_autoping_*` or the codex dispatch path.
- MUST NOT dispatch `claude --resume` against the live orchestrator session under any route value or monitor-id state.
- MUST fail closed: when the dedicated monitor id is unset/missing/malformed/equal-to-live, the claude leg issues NO `claude --resume`, does NOT fall back to the live orchestrator session, and is recorded as a DISTINCT SKIP -- never added to `delivered_targets`, no delivery receipt, and removed from `pending_targets` so it is neither falsely reported delivered nor retried indefinitely.
- MUST NOT touch runtime/substrate dirs (L4_ENABLER: no `mu/host/...`, no `rcx_pi/selfhost/...` changes).
- Claude autoping (keeping the monitor warm) is a SEPARATE follow-up; deliver safe pager routing first.
- Cite code by function name only; no line numbers (doc governance).

## Stop conditions

- STOP when the validation gate passes: tests prove (a) route=both reaches a dedicated claude target whose session id != the live orchestrator session id, (b) the claude leg fails closed (no `claude --resume`) for missing/malformed/equal-to-live monitor ids, AND (c) codex dispatch is unchanged.
- STOP and re-plan (do NOT widen) if resolving the dedicated monitor session id would require editing `codex_autoping_*` or the codex dispatch path -- that signals the boundary is wrong.
- DO NOT implement claude autoping in this wave; record it as the scoped follow-up only.
- STOP at the Phase A boundary: this packet defines design only. The source / precedence / unset / dispatch-state & receipt behavior is LOCKED above, so no open design point remains for bridge convergence; Phase B implements the locked design and authors the fail-closed tests before exit.

## Acceptance criteria

- A regression test proves route=both dispatches to a claude target whose session id != the live orchestrator session id (happy path).
- Fail-closed regression tests (required before Phase B exit) prove the claude leg issues NO `claude --resume` against the live orchestrator session when the dedicated monitor id is (a) missing/empty, (b) malformed (internal whitespace / non-UTF-8 / whitespace-only), or (c) equal to the live orchestrator session id.
- For each fail-closed case the claude target is recorded as a DISTINCT SKIP: it is NOT in `delivered_targets`, NO delivery receipt is written for it, a distinct skip is recorded, and it is removed from `pending_targets` (parked in `skipped_targets`) so a subsequent `dispatch_pending_events` call does NOT re-attempt it -- proving the event is neither falsely reported delivered nor retried indefinitely.
- The codex dispatch path, its `delivered_targets`/`pending_targets`/retry semantics and receipts, and `codex_autoping_*` are diff-proven unchanged.
- L4 evidence_command passes: `python3 -m py_compile mu/tools/observability/pipeline_agent_pager.py && python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id claude-pager-route-both-2026-06-01b --output reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json`.
- No runtime/substrate dir is touched (L4_ENABLER invariant).

## Grounding / Authorization

- TASKS.md authorization: the `[NEXT-CODEX-POST-REDTEAM]` tracker sync note dated 2026-06-01 for wave `claude-pager-route-both-2026-06-01b` ("route pipeline pager to a dedicated Claude monitor (mirror codex), non-interfering"). TASKS.md is the governing task authority for this wave.
- Governing packet: this file, `reports/control_plane/claude_pager_route_both_2026-06-01.md`, named as `Packet:` in the TASKS.md note above.
- Authorization: standing pipeline-enabler authorization per memory feedback_autonomous_executor_fix.md (founder directive 2026-05-31).
- FOUNDER_OVERRIDE:claude-pager-route-both-2026-06-01b

L4 contract binding (from the TASKS.md note, authoritative):
- Class: L4_ENABLER. target_gate_id: G8.
- evidence_command: `python3 -m py_compile mu/tools/observability/pipeline_agent_pager.py && python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id claude-pager-route-both-2026-06-01b --output reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json`
- primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION.
- indicator_artifact_ref: reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json
- indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id claude-pager-route-both-2026-06-01b --output reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.

## Request from Post-Merge Supervisor

Enable the Claude pager so pipeline transition events page CLAUDE in addition to Codex, MIRRORING codex's pager/autoping protocol, WITHOUT interfering with codex's pager/autoping (founder directive 2026-05-31). pipeline_agent_pager.py already supports route in {codex, claude, both, notify-only}; _dispatch_claude delivers via claude --resume <orchestrator_session_id> where that id currently equals the LIVE orchestrator session. CRITICAL CONSTRAINT: a bare route=both would dispatch claude --resume against the live orchestrator conversation -- not acceptable. The claude target must be a DEDICATED monitor session distinct from the live orchestrator session (mirroring how codex's pager targets the codex monitor, not the interactive codex).

Routed next-candidate:
claude-pager-route-both-2026-06-01b

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `claude-pager-route-both-2026-06-01b`
- Active packet: `reports/control_plane/claude_pager_route_both_2026-06-01.md`
- Indicator artifact: `reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/claude_pager_route_both_2026-06-01.md`
  - `reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `claude-pager-route-both-2026-06-01b`
- Active packet: `reports/control_plane/claude_pager_route_both_2026-06-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5c6c64e60fec279261100ed30726a85c6d20fe73a0f510772f291644f63ac35b`
- Indicator artifact: `reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/claude_pager_route_both_2026-06-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/claude_pager_route_both_2026-06-01.md`
  - `reports/l4_wave_indicators/claude-pager-route-both-2026-06-01b.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
