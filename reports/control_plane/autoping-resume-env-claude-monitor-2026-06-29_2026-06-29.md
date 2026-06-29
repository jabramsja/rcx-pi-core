# autoping watcher _resume_env sets RCX_CLAUDE_MONITOR=1 so the resume never clobbers orchestrator_session_id (no self-collision pause)

Date: 2026-06-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: autoping-resume-env-claude-monitor-2026-06-29
Phase-A-Lock: LOCKED
Purpose: Fix the recurring CLAUDE autoping WATCHER self-collision pause (2026-06-21 / 2026-06-28 learnings). ROOT (verified on dev): `mu/tools/session/claude_autoping_watch.py` `_resume_env()` (line 127) returns `os.environ.copy()` (line 130) WITHOUT `RCX_CLAUDE_MONITOR=1` (the file has 0 references to it). The watcher uses `_resume_env()` to spawn `claude --resume <claude_monitor_session_id>`; because RCX_CLAUDE_MONITOR is unset, the resumed monitor session's `.claude/hooks/session-start.sh` runs down its ELSE branch and writes the session id into `orchestrator_session_id` (instead of `claude_monitor_session_id`) -> `orchestrator_session_id == claude_monitor_session_id` collision -> the watcher's equal-to-live guard SELF-PAUSES the keepalive on its first ping (functionally dead pager despite a live watcher process). FIX (minimal, additive): in `_resume_env()`, set `env['RCX_CLAUDE_MONITOR'] = '1'` on the copied environment before returning, so the resumed monitor session's session-start writes ONLY `claude_monitor_session_id` and never clobbers `orchestrator_session_id` -> no self-collision, the watcher keeps pinging. Do NOT change any other watcher logic, the ping cadence, the pause/collision guards, or the monitor-id resolution -- only ensure the resume subprocess carries RCX_CLAUDE_MONITOR=1. Add ONE regression in the EXISTING autoping-watch test file (e.g. mu/tests/tools/test_codex_autoping_watch.py or the claude_autoping_watch test if present -- do NOT create a new test file) asserting `_resume_env()` returns a dict with `RCX_CLAUDE_MONITOR == '1'`. No host semantics; this is the orchestrator-side claude pager watcher only.

## Scope

Land the minimal, additive fix for the recurring CLAUDE autoping WATCHER self-collision pause (2026-06-21 / 2026-06-28 learnings): make the watcher's `_resume_env()` carry `RCX_CLAUDE_MONITOR=1` into the `claude --resume <claude_monitor_session_id>` subprocess, so the resumed monitor session's session-start hook takes its monitor branch (writes only `claude_monitor_session_id`) instead of clobbering `orchestrator_session_id`. The full root-cause chain is recorded in the Purpose field above; current dev truth is that `_resume_env()` returns a bare `os.environ.copy()` and the file has no `RCX_CLAUDE_MONITOR` reference (fix unlanded), verified by `grep -c RCX_CLAUDE_MONITOR mu/tools/session/claude_autoping_watch.py` returning no matches.

Files and surfaces in scope:

- `mu/tools/session/claude_autoping_watch.py` -- runtime change. In `_resume_env()` only, set `RCX_CLAUDE_MONITOR=1` on the copied environment before returning. No other function, guard, or cadence touched.
- `mu/tests/tools/test_claude_autoping_watch.py` -- regression. Extend this EXISTING claude-watch test (it already loads the `claude_autoping_watch` module and exercises `_resume_env()`); add one assertion that `_resume_env()` returns a dict with `RCX_CLAUDE_MONITOR == '1'`. Do NOT create a new test file.
- TASKS.md -- tracker-sync authority. The 2026-06-29 tracker sync note for wave `autoping-resume-env-claude-monitor-2026-06-29` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/autoping-resume-env-claude-monitor-2026-06-29_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. `mu/tools/session/claude_autoping_watch.py` `_resume_env()`: copy the live environment into a local dict, set `RCX_CLAUDE_MONITOR = '1'` on it, and return that dict. Additive only -- the inherited auth/session/RCX-overlay environment is preserved; no existing key is removed or rewritten.
2. `mu/tests/tools/test_claude_autoping_watch.py`: add ONE regression asserting `_resume_env()` returns a dict containing `RCX_CLAUDE_MONITOR == '1'`. Reuse the module loader and `_resume_env` harness already present in this file; do NOT add a new test file.

## Constraints

- Touch ONLY `_resume_env()` in `claude_autoping_watch.py`. Do NOT change the ping cadence, the pause / equal-to-live collision guards, the monitor-id resolution (`_read_monitor_session_id`), or any other watcher logic.
- Do NOT modify `.claude/hooks/session-start.sh`, `pipeline_agent_pager.py`, the codex watcher (`codex_autoping_watch.py` / `test_codex_autoping_watch.py`), or any orchestrator-mode-switch surface.
- Do NOT create a new test file -- extend the existing `test_claude_autoping_watch.py`.
- L4_ENABLER: MUST NOT touch runtime dirs (`mu/host/`, `rcx_pi/selfhost/`). No host semantics and no new host-authority sites; this is the orchestrator-side claude pager watcher only.

## Stop conditions

- The fix cannot be expressed as a single additive change inside `_resume_env()` (e.g. it would require editing the session-start hook or a collision guard) -- STOP and re-scope rather than widen the blast radius.
- `grep -c RCX_CLAUDE_MONITOR mu/tools/session/claude_autoping_watch.py` already returns a match before this wave (fix already landed) -- STOP; nothing to do. (Verified 0 on dev at packet time, so the work is live.)
- The regression cannot assert `RCX_CLAUDE_MONITOR == '1'` without adding a new test file or exercising real subprocess/IO -- STOP and escalate.
- Any autoping-watch test regresses, or the diff extends beyond `_resume_env()` plus the one added assertion -- STOP and revert.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_autoping_watch.py`

## Acceptance criteria

- evidence_command passes: `grep -q 'RCX_CLAUDE_MONITOR' mu/tools/session/claude_autoping_watch.py` exits 0 (was non-zero / no refs on dev).
- `_resume_env()` returns a dict with `RCX_CLAUDE_MONITOR == '1'` while preserving every other inherited environment key.
- The new regression in `mu/tests/tools/test_claude_autoping_watch.py` passes and the existing autoping-watch suite stays green: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_claude_autoping_watch.py`.
- The change is confined to `_resume_env()` plus the one added assertion -- no other watcher behavior, guard, or cadence changed.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `autoping-resume-env-claude-monitor-2026-06-29`.
- Governing packet: this file, `reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md`.
- TASKS.md authority: the 2026-06-29 tracker sync note for wave `autoping-resume-env-claude-monitor-2026-06-29` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:autoping-resume-env-claude-monitor-2026-06-29

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `autoping-resume-env-claude-monitor-2026-06-29`
- Active packet: `reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md`
- Indicator artifact: `reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_autoping_watch.py`
  - `mu/tools/session/claude_autoping_watch.py`
  - `reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md`
  - `reports/deferred/non_blocking/autoping-resume-env-claude-monitor-2026-06-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `autoping-resume-env-claude-monitor-2026-06-29`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/autoping-resume-env-claude-monitor-2026-06-29_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id autoping-resume-env-claude-monitor-2026-06-29 --output reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_autoping_watch.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_claude_autoping_watch.py`, `mu/tools/session/claude_autoping_watch.py`, `reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md`, `reports/deferred/non_blocking/autoping-resume-env-claude-monitor-2026-06-29_bridge_nonblockers.md`, `reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: autoping-resume-env-claude-monitor-2026-06-29.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `autoping-resume-env-claude-monitor-2026-06-29`
- Active packet: `reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6f51b7622f25077006e5a68b78cd8fcc7645d503aa59157cdc17e27c97ef86e2`
- Indicator artifact: `reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_autoping_watch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_claude_autoping_watch.py`, `mu/tools/session/claude_autoping_watch.py`, `reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md`, `reports/deferred/non_blocking/autoping-resume-env-claude-monitor-2026-06-29_bridge_nonblockers.md`, `reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_autoping_watch.py`
  - `mu/tools/session/claude_autoping_watch.py`
  - `reports/control_plane/autoping-resume-env-claude-monitor-2026-06-29_2026-06-29.md`
  - `reports/deferred/non_blocking/autoping-resume-env-claude-monitor-2026-06-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/autoping-resume-env-claude-monitor-2026-06-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
