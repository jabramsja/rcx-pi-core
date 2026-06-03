# Claude Pager Dedicated Monitor 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: claude-pager-dedicated-monitor-2026-06-03
Phase-A-Lock: LOCKED
Class: L4_ENABLER (tooling/observability only; no runtime/substrate dir)
Purpose: Build the DEDICATED Claude-monitor pager dispatch infrastructure so that, in a FUTURE wave, the pager route can be flipped to 'both' and a page to Claude resumes a DEDICATED monitor session (NEVER the live interactive orchestrator session) -- non-interfering, mirroring how the codex leg pages a dedicated codex app-server thread. This wave KEEPS route=codex (the route=both flip + codex-mirrored autoping are a separate follow-up, safe only once a monitor reliably runs). MOST of that infra has ALREADY LANDED in current dev (the constants, the dedicated reader `_read_claude_monitor_session_id`, the dedicated-resume `_dispatch_claude` with no live fallback, the MONITOR_UNSET retryable skip handling, and the `RCX_CLAUDE_MONITOR=1` session-start writer). This revision NARROWS the wave to the ONE remaining delta: making the `CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE` skip RETRYABLE (not terminally parked) in `_dispatch_pending_locked`, so a page is never silently/terminally dropped while the dedicated monitor id transiently equals the live orchestrator id.

## 0. Already landed (verified in current code -- NOT work items)

Per the already-landed Stop condition, the following are removed from Work items / Acceptance criteria because current dev code already implements them (verified by reading the current `pipeline_agent_pager.py` and `.claude/hooks/session-start.sh`). They are recorded here as context ONLY; do NOT re-list, re-port, duplicate, or churn them.

- The dedicated-monitor constants `CLAUDE_MONITOR_SESSION_ID_PATH`, `CLAUDE_SKIP_REASON_MONITOR_UNSET` (`'claude_monitor_session_id_unset_or_malformed'`), and `CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE` (`'claude_monitor_session_id_equals_live_orchestrator'`) are already defined in `pipeline_agent_pager.py` with the verbatim values. (was W1)
- `_read_claude_monitor_session_id` is already defined: reads ONLY the dedicated `claude_monitor_session_id` observability file with the full malformed-tolerance discipline (missing / OSError / non-UTF-8 / empty / whitespace-only / internal-whitespace -> None) and NO fallback to `orchestrator_session_id`. (was W2)
- `_dispatch_claude` already dispatches the DEDICATED monitor session with no live fallback: MONITOR_UNSET skip when the monitor id is absent/malformed; reads the live orchestrator id for the inequality guard ONLY and returns a MONITOR_EQUALS_LIVE skip when it matches; otherwise runs `claude --resume <monitor-id> -p`. It NEVER resumes the live orchestrator. (was W3)
- `_dispatch_pending_locked` already treats `CLAUDE_SKIP_REASON_MONITOR_UNSET` as RETRYABLE: it leaves the target in `pending_targets`, does NOT park it in `skipped_targets`, and writes NO durable skip receipt (the reconcile path already exempts a pre-existing MONITOR_UNSET receipt). (was the MONITOR_UNSET half of W4)
- `.claude/hooks/session-start.sh` already writes `claude_monitor_session_id` (using its existing atomic tmp+mv write) when `RCX_CLAUDE_MONITOR=1`, and writes `orchestrator_session_id` unchanged otherwise. (was W5)

## 1. Scope (files / directories in scope)

- `mu/tools/observability/pipeline_agent_pager.py` -- make the `CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE` skip RETRYABLE in `_dispatch_pending_locked`, mirroring the EXISTING `CLAUDE_SKIP_REASON_MONITOR_UNSET` retryable handling exactly (and extending the matching reconcile guard). This is the ONLY production-tooling change in this wave.
- `mu/tests/tools/test_pipeline_agent_pager.py` -- EXISTING test file; one regression test for the MONITOR_EQUALS_LIVE retryable behavior (NO new test file -- growth cap).

NOT touched this wave (already landed -- see section 0): the dedicated-monitor constants, `_read_claude_monitor_session_id`, `_dispatch_claude`, the MONITOR_UNSET retryable branch, and the `.claude/hooks/session-start.sh` writer. `.claude/hooks/session-start.sh` is therefore OUT of scope now (its writer already landed) -- only the two files above are touched.

Reference: `.scratch/pager_1052_reference.py` (the closed-PR-#1052 infra) is ALREADY PORTED into current dev. The remaining delta is precisely the bot-P1 fix that #1052 LACKED (it parked the monitor skip TERMINALLY). Model the fix on the EXISTING MONITOR_UNSET retryable branch in the CURRENT code -- NOT on the #1052 reference. Cite code by FUNCTION / CONSTANT name only; NO file:line.

## 2. Work items (concrete bounded tasks)

W1. Make `CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE` RETRYABLE in `_dispatch_pending_locked`, mirroring the existing `CLAUDE_SKIP_REASON_MONITOR_UNSET` retryable handling EXACTLY. Today `_dispatch_pending_locked` routes an EQUALS_LIVE skip into the genuinely-terminal skip branch, which parks the target in `skipped_targets` and appends a durable skip receipt -- a silent, PERMANENT drop of the page once the dedicated monitor id transiently equals the live orchestrator id. Extend the existing retryable monitor-state branch so that a `dispatch_result` with `skipped=True` AND `skip_reason` in {`CLAUDE_SKIP_REASON_MONITOR_UNSET`, `CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE`} is retryable: LEAVE the target in `pending_targets` (do NOT park it in `skipped_targets`), do NOT append a durable skip receipt, and ensure the state-rebuild/reconcile path (`_reconcile_delivery_state`) treats a PRE-EXISTING EQUALS_LIVE skip receipt as non-terminal too -- the same guard that already exempts MONITOR_UNSET -- so a restart/replay never re-terminalizes a page that the current terminal branch may already have receipted. A LATER dispatch (once a DISTINCT monitor id has been written) then acts on the still-pending page. Both monitor-state reasons are transient (no distinct monitor id available yet) and clear when the monitor's session-start writes a distinct id; any OTHER genuinely-terminal/future skip_reason keeps the existing terminal `skipped_targets` + skip-receipt behavior. A page to Claude must NEVER be silently or terminally dropped because the dedicated monitor was not yet up with a distinct id. The fail-closed invariant is preserved: while the guard trips, NO `claude --resume` is issued -- the page simply stays pending.

W2. REGRESSION TEST in the EXISTING `test_pipeline_agent_pager.py` (NO new file -- growth cap): `_dispatch_pending_locked` given a `_dispatch_claude` result with `skip_reason=CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE` leaves the claude target in `pending_targets` (retryable), does NOT park it in `skipped_targets`, writes NO durable skip receipt, and a SUBSEQUENT dispatch -- once a DISTINCT monitor id exists -- delivers the page (prove no silent/terminal drop). Assert the already-landed MONITOR_UNSET retryable behavior and the codex leg remain unaffected.

## 3. Constraints (NOT in scope)

- Do NOT flip route to 'both'. Route STAYS codex. (The route=both flip + codex-mirrored autoping are a separate follow-up, safe only once a monitor reliably runs; flipping now would let pages pile up with no receiver.)
- Do NOT change `executor_config.json`.
- Do NOT touch the codex leg (`_dispatch_codex` / autoping) -- it must be entirely unaffected.
- Do NOT re-implement, re-port, duplicate, or churn the ALREADY-LANDED constants, `_read_claude_monitor_session_id`, `_dispatch_claude`, or the `.claude/hooks/session-start.sh` writer (section 0) -- they are done.
- Do NOT change the already-landed MONITOR_UNSET retryable handling -- only EXTEND the retryable branch (and the matching reconcile guard) to ALSO cover MONITOR_EQUALS_LIVE.
- Do NOT add a new test file -- the regression test goes into the EXISTING `test_pipeline_agent_pager.py` (growth cap).
- Do NOT touch any runtime / substrate dir (L4_ENABLER: tooling/observability only).
- Do NOT add a `claude_monitor_session_id` fallback to `orchestrator_session_id` -- the live conversation is never a `--resume` target.
- Files touched: exactly the TWO listed in Scope (`pipeline_agent_pager.py` + the EXISTING `test_pipeline_agent_pager.py`) -- nothing else (`.claude/hooks/session-start.sh` is no longer touched).
- Cite code by FUNCTION / CONSTANT name only; NO file:line in the plan.

## 4. Stop conditions

- Phase-A stop (this turn): stop when the packet contains all six required sections (Scope, Work items, Constraints, Stop conditions, Acceptance criteria, Grounding / Authorization) and the bridge reviewer converges (APPROVE). Do NOT begin implementation until Phase-A-Lock flips to LOCKED. Do NOT inspect downstream implementation files during Phase A.
- Stop-and-land (implementation success termination): stop implementing and hand off to the commit pipeline when W1-W2 are complete, the MONITOR_EQUALS_LIVE retryable regression test passes under the Validation gate, the diff is confined to the two in-scope files, route is still codex, the codex leg is untouched, and the already-landed constants / reader / dispatch / MONITOR_UNSET branch / session-start writer are unchanged.
- Stop-and-halt (halt + report; do NOT proceed) when ANY of:
  - the change would require touching a file outside the two in-scope files (scope creep);
  - flipping route to 'both', modifying the codex leg, or editing `executor_config.json` appears necessary;
  - making MONITOR_EQUALS_LIVE retryable cannot reuse the existing MONITOR_UNSET retryable path without redesign;
  - a remaining work item is found ALREADY landed in current code -- stop, remove it from Work items / Acceptance criteria, and report (do NOT re-list or duplicate it);
  - an L4_ENABLER contract violation would be required (touching a runtime/substrate dir), the growth cap would be breached (a new test file), or any gate check fails.
- Push/merge block: do NOT push or merge until the Validation gate passes and a pre-commit supervisor receipt exists. Commit only through the pipeline (`commit_executor.py`); never manual git.

## 5. Acceptance criteria

- AC1. `_dispatch_pending_locked` treats BOTH `CLAUDE_SKIP_REASON_MONITOR_UNSET` and `CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE` as RETRYABLE: the target stays in `pending_targets`, is NOT parked in `skipped_targets`, and no durable skip receipt is written. (The MONITOR_UNSET half is already landed; the delta delivered by this wave is the MONITOR_EQUALS_LIVE half.)
- AC2. The state-rebuild/reconcile path (`_reconcile_delivery_state`) treats a PRE-EXISTING EQUALS_LIVE skip receipt as non-terminal -- the same guard that already exempts MONITOR_UNSET -- so a restart/replay does NOT re-terminalize the page.
- AC3. A later dispatch delivers the page once a DISTINCT monitor id exists; the EQUALS_LIVE skip is never a silent/terminal drop. While the guard trips, no `claude --resume` is issued (fail-closed preserved).
- AC4. The codex leg and route are unchanged (route still codex; `_dispatch_codex` / autoping / `executor_config.json` untouched), and the already-landed constants, `_read_claude_monitor_session_id`, `_dispatch_claude`, MONITOR_UNSET retryable handling, and `.claude/hooks/session-start.sh` writer are unchanged.
- AC5. The MONITOR_EQUALS_LIVE retryable regression test exists in the EXISTING `test_pipeline_agent_pager.py` and the Validation gate passes.

Validation gate: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py -k "monitor or claude or skip or dispatch"`

## 6. Grounding / Authorization

- Umbrella task: `[NEXT-CODEX-POST-REDTEAM]` in TASKS.md -- UNPARKED 2026-03-28, founder-authorized.
- Wave authorization: the TASKS.md tracker sync note (2026-06-03, claude-pager-dedicated-monitor-2026-06-03) authorizes THIS wave with the following fields: Class: L4_ENABLER; target_gate_id: G8; Packet: `reports/control_plane/claude_pager_dedicated_monitor_2026-06-03.md`; primary_blocker_class: INTEGRATION; primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES; indicator_artifact_ref: `reports/l4_wave_indicators/claude-pager-dedicated-monitor-2026-06-03.json`; indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id claude-pager-dedicated-monitor-2026-06-03 --output reports/l4_wave_indicators/claude-pager-dedicated-monitor-2026-06-03.json`; bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id: V1; boot0_progress_state: HOLD. (The tracker note authorizes the wave; it does NOT prove every originally-listed deliverable is still unlanded -- current code shows most have landed, so this packet is narrowed to the remaining delta per the already-landed Stop condition.)
- Governing packet: this file (`reports/control_plane/claude_pager_dedicated_monitor_2026-06-03.md`) is the governing packet for this wave.
- Same-wave override (so commit automation can derive the same-wave override mechanically): FOUNDER_OVERRIDE:claude-pager-dedicated-monitor-2026-06-03
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md (control-surface L4_ENABLER; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance).

## Request from Post-Merge Supervisor (provenance -- verbatim source request)

NOTE (provenance only -- not the active work list): the verbatim source request below predates the current dev code. Deliverables (1)-(3) and (5) below, plus the MONITOR_UNSET half of (4), have SINCE LANDED in current dev (see section 0). This wave is NARROWED to the remaining half of deliverable (4): making the MONITOR_EQUALS_LIVE skip retryable in `_dispatch_pending_locked` (see Work items W1-W2). The original request is preserved verbatim for traceability.

Build the DEDICATED Claude-monitor pager dispatch infrastructure so that, in a FUTURE wave, the pager route can be flipped to 'both' and a page to Claude resumes a DEDICATED monitor session (NEVER the live interactive orchestrator session) -- non-interfering, mirroring how the codex leg pages a dedicated codex app-server thread. This wave KEEPS route=codex (do NOT flip route to 'both' -- that flip + codex-mirrored autoping are a separate follow-up that is safe only once a monitor reliably runs; flipping now would let pages pile up with no receiver). REFERENCE (READ FIRST -- this is KNOWN-GOOD code from the closed PR #1052; PORT it, do not redesign): .scratch/pager_1052_reference.py contains the exact infra to port -- the constant CLAUDE_MONITOR_SESSION_ID_PATH, the two skip-reason constants CLAUDE_SKIP_REASON_MONITOR_UNSET = 'claude_monitor_session_id_unset_or_malformed' and CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE = 'claude_monitor_session_id_equals_live_orchestrator', the reader _read_claude_monitor_session_id, and the dedicated-resume _dispatch_claude. Also READ the CURRENT dev mu/tools/observability/pipeline_agent_pager.py: the current _dispatch_claude (which resumes the LIVE orchestrator via _read_orchestrator_session_id -- the behavior to REPLACE), _read_orchestrator_session_id, _dispatch_pending_locked, _refresh_pending_targets, and how a dispatch_result's 'skipped'/'skip_reason' would flow (the current dev _dispatch_claude never returns skipped, so dev _dispatch_pending_locked has NO skip handling yet). And READ .claude/hooks/session-start.sh (the existing atomic tmp+mv writer of observability/orchestrator_session_id from the SessionStart hook's session_id). DELIVER (all in this wave, route stays codex): (1) PORT the constants into pipeline_agent_pager.py: CLAUDE_MONITOR_SESSION_ID_PATH = OBSERVABILITY_DIR / 'claude_monitor_session_id' plus the two CLAUDE_SKIP_REASON_* constants (verbatim values above). (2) PORT _read_claude_monitor_session_id verbatim: it reads ONLY the dedicated 'claude_monitor_session_id' observability file with the SAME malformed-tolerance discipline as _read_orchestrator_session_id (missing / OSError / non-UTF-8 / empty / whitespace-only / internal-whitespace all -> None); there is NO fallback to orchestrator_session_id (the live conversation is never a --resume target). (3) REPLACE the current dev _dispatch_claude with the dedicated-resume version: read monitor_session_id via _read_claude_monitor_session_id; if absent/None -> return {acknowledged:False, skipped:True, skip_reason: CLAUDE_SKIP_REASON_MONITOR_UNSET} (NEVER fall back to the orchestrator session); read the live orchestrator id for an INEQUALITY guard ONLY (never as a resume target) and if monitor_session_id == live id -> return {acknowledged:False, skipped:True, skip_reason: CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE}; otherwise run `claude --resume <monitor_session_id> -p <event_prompt>` exactly as the #1052 version (same timeout/OSError/returncode handling, ack carries session_id=monitor_session_id). (4) THE KEY FIX over #1052 (this is the bot P1 that CLOSED #1052 -- #1052 parked the monitor-absent skip TERMINALLY in skipped_targets = a silent permanent drop): add skip handling to _dispatch_pending_locked so a dispatch_result with skipped=True AND skip_reason in {CLAUDE_SKIP_REASON_MONITOR_UNSET, CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE} is RETRYABLE -- LEAVE the target in pending_targets (do NOT park it in a terminal skipped_targets), record the skip_reason for observability (e.g. an attempt/last_skip_reason field), and continue; so a LATER dispatch (once a distinct monitor session-id has been written) acts on the still-pending page. A page to Claude must NEVER be silently or terminally dropped because the monitor was not yet up. Any OTHER (genuinely terminal) skip_reason, if one ever arises, keeps whatever terminal behavior is appropriate, but the two monitor-state skip reasons above are explicitly retryable. (5) THE MISSING WRITER: extend .claude/hooks/session-start.sh so that when the env var RCX_CLAUDE_MONITOR=1 is set, it writes the SessionStart session_id to observability/claude_monitor_session_id (the DEDICATED monitor file) using the SAME atomic tmp+mv write it already uses, INSTEAD OF writing orchestrator_session_id (a dedicated monitor session is NOT the live orchestrator; writing both would defeat the equal-to-live guard). When RCX_CLAUDE_MONITOR is unset/not '1' (the normal interactive session), keep the EXISTING behavior exactly (write orchestrator_session_id, untouched). session-start.sh is TRACKED, so no gitignore staging issue. SCOPE: ONLY mu/tools/observability/pipeline_agent_pager.py + .claude/hooks/session-start.sh + regression tests in the EXISTING mu/tests/tools/test_pipeline_agent_pager.py (NO new test file -- growth cap). Do NOT change executor_config.json (route stays codex). Do NOT touch the codex leg (_dispatch_codex / autoping) -- it must be entirely unaffected. L4_ENABLER: tooling/observability only, no runtime/substrate dir. Cite code by FUNCTION NAME only; NO file:line in the plan.

Routed next-candidate:
claude-pager-dedicated-monitor-2026-06-03

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `claude-pager-dedicated-monitor-2026-06-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/claude-pager-dedicated-monitor-2026-06-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `claude-pager-dedicated-monitor-2026-06-03`
- Active packet: `reports/control_plane/claude_pager_dedicated_monitor_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c28329418dfaaa77b950e69325720b24a0d2a80d5e749921bd615681eca29cf0`
- Indicator artifact: `reports/l4_wave_indicators/claude-pager-dedicated-monitor-2026-06-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/claude_pager_dedicated_monitor_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/claude-pager-dedicated-monitor-2026-06-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/claude_pager_dedicated_monitor_2026-06-03.md`
  - `reports/deferred/non_blocking/claude-pager-dedicated-monitor-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/claude-pager-dedicated-monitor-2026-06-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
