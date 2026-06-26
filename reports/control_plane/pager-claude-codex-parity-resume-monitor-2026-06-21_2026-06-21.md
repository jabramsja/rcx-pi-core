# NEXT-CODEX-POST-REDTEAM - PAGER codex-parity: claude pager delivers each page INTO the persistent warm monitor (claude --resume), mirroring the codex app-server/shared-thread model

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pager-claude-codex-parity-resume-monitor-2026-06-21
Phase-A-Lock: LOCKED
Purpose: Give the CLAUDE pager the SAME model the CODEX pager has (founder 2026-06-21: 'I want the same thing codex has for the claude pager'). CODEX (code-verified, works): the codex autoping keeps a PERSISTENT codex monitor thread warm; `_dispatch_codex` delivers each pager event as a `turn/start` INTO that SAME persistent thread (shared via `_read_latest_autoping_thread_id`) through the persistent `codex app-server --listen` daemon -- async fast-ack, codex processes the turn async; it skips a paused/foreign thread and starts a NEW thread on a stale-thread error. CLAUDE DIVERGES: `_dispatch_claude` enqueues to `claude_pager_receiver`, whose `delivery_command` is a FRESH, resume-less `claude -p` per page (the monitor-resume path was dropped 2026-06-17 because the SYNC `claude --resume` turn timed out under the ~10-20s ack budget) -- so every page is an ephemeral subprocess with NO continuous monitor conversation, unlike codex's persistent thread. The w2b ASYNC receiver (file-queue drain) now provides the claude equivalent of the app-server's async delivery (no timeout), so the reason for dropping monitor-resume is gone. FIX (codex-parity): the claude pager delivers each page INTO the persistent warm monitor -- `claude --resume <claude_monitor_session_id>` (the SAME session the autoping WATCHER keeps warm, mirroring codex's shared autoping thread) -- via the existing async/serialized + event_id-dedup + ensure_draining receiver (NO timeout regression), instead of a fresh resume-less `claude -p`. MIRROR codex's guards: when the monitor session id is UNSET/malformed (MONITOR_UNSET) or EQUALS the live orchestrator id (MONITOR_EQUALS_LIVE) -- never resume the live orchestrator -- and when the monitor resume fails (stale/dead session, codex's stale-thread case), FALL BACK to the existing fresh `claude -p` page (fail-open, no page lost). Set RCX_CLAUDE_MONITOR=1 in the delivery env so the resumed monitor's session-start re-writes claude_monitor_session_id (idempotent) and NEVER clobbers orchestrator_session_id. Keep the existing shared `_event_prompt`. Supersedes the 2026-06-17 fresh-`claude -p` separation decision per the founder direction. Pager-tooling only: NO runtime, substrate, seed, projection, or JS change.

## Scope

Pager-tooling codex-parity: the claude pager delivers each page into the persistent warm monitor (claude --resume) via the async receiver, mirroring the codex pager; guards (equal-to-live/unset skip, stale-resume fresh fallback, no-clobber env). No runtime/substrate change. TASKS.md is tracker-sync authority. Non-conflicting with Stage0 (eval_seed/bootstrap_core) + FIX-34 (recovery_gate).

Files and surfaces in scope:

- mu/tools/session/claude_pager_receiver.py (MODIFY) -- delivery: when claude_monitor_session_id is set, distinct from the live orchestrator (orchestrator_session_id), and resumable, deliver the page via `claude --resume <monitor> -p <prompt>` (INTO the persistent monitor), instead of the fresh resume-less `claude -p`; set RCX_CLAUDE_MONITOR=1 in the delivery env so the resume cannot clobber orchestrator_session_id; on monitor UNSET/EQUALS_LIVE or a resume failure (stale/dead), FALL BACK to the existing fresh `claude -p` page (fail-open, no page lost); keep the existing _event_prompt, async/serialized delivery, event_id dedup, ensure_draining, and the per-delivery process-group reaper.
- mu/tools/observability/pipeline_agent_pager.py (MODIFY) -- _dispatch_claude: resolve claude_monitor_session_id + the MONITOR_UNSET / MONITOR_EQUALS_LIVE state (the constants already exist) and make it available to the receiver delivery so the resume-vs-fresh decision and the never-resume-live guard hold at delivery time; keep the enqueue + ensure_draining async flow unchanged.
- mu/tests/tools/test_pipeline_agent_pager.py + mu/tests/tools/test_claude_pager_receiver.py (MODIFY) -- regression tests: resume-the-monitor delivery argv when monitor set+distinct+resumable; fresh-`claude -p` fallback on MONITOR_UNSET, on MONITOR_EQUALS_LIVE, and on resume-failure; RCX_CLAUDE_MONITOR=1 no-clobber env; dedup/serialized/ensure_draining preserved.
- reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json (GENERATED).
- TASKS.md -- tracker-sync authority for the wave's L4 GOVERNANCE fields (Class L4_ENABLER, target_gate_id G8, FOUNDER_OVERRIDE, primary_blocker_class INTEGRATION, primary_invariant_id INV_STRUCTURAL_FORWARD_MOTION, indicator refs); the packet derives those from the 2026-06-21 tracker sync note for wave `pager-claude-codex-parity-resume-monitor-2026-06-21`. RECONCILED: the staged 2026-06-21 tracker note's `evidence_command` and this packet both use the code-verified test paths `mu/tests/tools/test_pipeline_agent_pager.py` + `mu/tests/tools/test_claude_pager_receiver.py`; an earlier packet draft flagged an `mu/tests/observability/...` + `mu/tests/session/...` mismatch, but the staged tracker note now uses the `mu/tests/tools/...` paths, so commit/L4 automation deriving evidence from TASKS.md runs a valid command and no tracker correction is pending.

- `reports/deferred/non_blocking/pager-claude-codex-parity-resume-monitor-2026-06-21_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read the codex pager leg (_dispatch_codex: thread-id resolve, paused/foreign skip, turn/start into the shared thread, new-thread-on-stale) and the claude leg (_dispatch_claude enqueue + claude_pager_receiver delivery_command/_event_prompt/delivery_env/async drain + event_id dedup + ensure_draining + reaper) to ground the codex-parity change.
2. Change the claude receiver delivery to resume the persistent monitor (claude --resume <claude_monitor_session_id> -p <prompt>) when the monitor is set, distinct from the live orchestrator, and resumable -- INTO the same warm monitor the watcher keeps, mirroring codex's turn/start-into-the-shared-thread; keep the existing async/serialized + event_id dedup + ensure_draining + reaper (no timeout regression).
3. Set RCX_CLAUDE_MONITOR=1 in the delivery env so the resumed monitor's session-start re-writes claude_monitor_session_id (idempotent) and never clobbers orchestrator_session_id.
4. Mirror codex's guards: skip the resume (use the fresh `claude -p` page) when claude_monitor_session_id is UNSET/malformed (MONITOR_UNSET) or EQUALS the live orchestrator (MONITOR_EQUALS_LIVE) -- never resume the live orchestrator; on a resume failure (stale/dead monitor) fall back to a fresh `claude -p` page (fail-open, no page lost).
5. Add regression tests for the resume-monitor argv, the three fresh-`claude -p` fallbacks (unset / equal-to-live / resume-failure), the no-clobber env, and dedup/serialized/ensure_draining preserved.
6. Run the evidence command and collect the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Pager-tooling only: NO runtime (eval_seed), substrate, seed, projection, or JS change; bounded to pipeline_agent_pager.py + claude_pager_receiver.py + their tests.
- NEVER resume the live orchestrator: MONITOR_EQUALS_LIVE and MONITOR_UNSET must force the fresh-`claude -p` fallback (mirror codex's paused/foreign-thread skip).
- Set RCX_CLAUDE_MONITOR=1 in the delivery env so the monitor resume cannot clobber orchestrator_session_id (the watcher self-collision class).
- Preserve the async/serialized delivery + event_id dedup + ensure_draining + reaper (no blocking-timeout regression); fail-open to a fresh `claude -p` page on any resume failure so no page is lost.
- Keep the existing shared _event_prompt (codex and claude share it); this wave changes the delivery TARGET to the persistent monitor, not the prompt.

## Stop conditions

- Stop done when the evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if codex-parity would require a persistent claude app-server-style daemon beyond the existing receiver (claude has no app-server mode) -- the receiver's async drain is the claude equivalent; do not build a new daemon.
- If the fix would require touching runtime/substrate files, re-scope rather than relaxing the tooling-only boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py`
- evidence_command path authority: code-verified -- both test files exist at `mu/tests/tools/` (`test_pipeline_agent_pager.py`, `test_claude_pager_receiver.py`). The staged 2026-06-21 TASKS.md tracker note and the supervisor package both use these `mu/tests/tools/...` paths, so this packet's evidence_command and the TASKS.md-derived evidence_command agree and commit/L4 automation derives a valid command (no tracker correction pending).

## Acceptance criteria

- the claude pager delivers via `claude --resume <claude_monitor_session_id>` (into the persistent monitor) when the monitor is set, distinct from the live orchestrator, and resumable.
- fresh-`claude -p` fallback on MONITOR_UNSET, MONITOR_EQUALS_LIVE, and resume-failure (no page lost; live orchestrator never resumed).
- RCX_CLAUDE_MONITOR=1 is set in the delivery env (no orchestrator_session_id clobber).
- async/serialized delivery + event_id dedup + ensure_draining preserved (no timeout regression).
- the two pager/receiver test files cover the resume + 3 fallbacks + no-clobber + dedup paths and pass; net host semantics delta 0; indicator collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pager-claude-codex-parity-resume-monitor-2026-06-21`.
- Governing packet: this file, `reports/control_plane/pager-claude-codex-parity-resume-monitor-2026-06-21_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `pager-claude-codex-parity-resume-monitor-2026-06-21` is canonical for this packet's L4 GOVERNANCE fields (Class L4_ENABLER, target_gate_id G8, FOUNDER_OVERRIDE, primary_blocker_class INTEGRATION, primary_invariant_id INV_STRUCTURAL_FORWARD_MOTION, indicator_artifact_ref + indicator_collection_command). The staged tracker note's `evidence_command` uses the code-verified `mu/tests/tools/test_pipeline_agent_pager.py` + `mu/tests/tools/test_claude_pager_receiver.py` paths, matching the Validation gates command above, so this packet and TASKS.md agree on the evidence paths and no tracker correction is pending.
- Authorization: Founder 2026-06-21: 'I want the same thing codex has for the claude pager.' Codex delivers each pager event into a persistent shared monitor thread (autoping-kept-warm) via the app-server; the claude pager currently uses a fresh resume-less `claude -p`. This wave brings claude to codex-parity: deliver into the persistent warm monitor via the async receiver. Supersedes the 2026-06-17 fresh-`claude -p` separation decision. Runs parallel to Stage0 + FIX-34 (non-overlapping files).

FOUNDER_OVERRIDE:pager-claude-codex-parity-resume-monitor-2026-06-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pager-claude-codex-parity-resume-monitor-2026-06-21`
- Active packet: `reports/control_plane/pager-claude-codex-parity-resume-monitor-2026-06-21_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_pager_receiver.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `mu/tools/session/claude_pager_receiver.py`
  - `reports/control_plane/pager-claude-codex-parity-resume-monitor-2026-06-21_2026-06-21.md`
  - `reports/deferred/non_blocking/pager-claude-codex-parity-resume-monitor-2026-06-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pager-claude-codex-parity-resume-monitor-2026-06-21`
- Purpose: no active same-wave deferred non-blocking bridge findings packet is authorized for this commit package.
- Authorized deferred packet(s): none
- Scope binding: no generated bridge packet for this wave is authorized in `reports/deferred/non_blocking/` unless it exists as a staged file and is listed in `deferred_items`.
- Acceptance binding: generated bridge packet paths for this wave must remain absent from active deferred lanes unless the package carries an existing staged deferred packet.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-claude-codex-parity-resume-monitor-2026-06-21 --output reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-codex-parity-resume-monitor-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pager-claude-codex-parity-resume-monitor-2026-06-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-claude-codex-parity-resume-monitor-2026-06-21`
- Active packet: `reports/control_plane/pager-claude-codex-parity-resume-monitor-2026-06-21_2026-06-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `db2c667f34e5c83650b55e2db8b29f8617cc28829031191118b70e58cef02c2a`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-codex-parity-resume-monitor-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_pager_receiver.py`
  - `mu/tools/session/claude_pager_receiver.py`
  - `reports/control_plane/pager-claude-codex-parity-resume-monitor-2026-06-21_2026-06-21.md`
  - `reports/l4_wave_indicators/pager-claude-codex-parity-resume-monitor-2026-06-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
