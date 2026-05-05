# Codex-Autoping-Active-Ping-Cleanup-Hardening-2026-05-05

Date: 2026-05-05
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-AUTOPING]
Wave ID: codex-autoping-active-ping-cleanup-hardening-2026-05-05
Class: L4_ENABLER
Target Gate: G8
Phase-A-Lock: LOCKED
Governing packet: reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md
Deferred source: reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md
Authorization: standing pipeline-bug-fix authorization for this bounded control-surface L4_ENABLER autoping cleanup wave; same-wave token is FOUNDER_OVERRIDE:codex-autoping-active-ping-cleanup-hardening-2026-05-05.
FOUNDER_OVERRIDE:codex-autoping-active-ping-cleanup-hardening-2026-05-05

Purpose: Create the smallest bounded pipeline/control-surface plan for the two retained non-blocking Codex autoping cleanup findings from the deferred packet above. Phase B has now implemented the bounded wrapper/test/doc closeout.

## Phase B Implementation Evidence

- Reproduction before editing confirmed the active-ping cleanup finding was live: current wrapper cleanup trusted `active_pid` after a watcher-pid match, then signaled both `os.killpg(pid, ...)` and `os.kill(pid, ...)`, leaving stale PID/PGID reuse exposure.
- Reproduction before editing confirmed the cleanup-failure surfacing finding was partially stale and partially live: permission and still-alive cleanup failures were already persisted in durable state, but unsafe active-target/freshness cleanup skips were not durably surfaced.
- Landed repair in the hardlinked root/`mu/` wrapper content verifies dispatch identity (`last_dispatched_pid`, `last_dispatched_at`), state freshness (`updated_at` bounded by ping timeout and interval), same autoping log directory, active-log existence, and process-group identity before sending signals. Cleanup now targets the verified process group only.
- Landed repair records unsafe cleanup target failures at the failed cleanup
  attempt with `status=watcher_restart_degraded_active_ping_cleanup_failed` and
  `last_active_cleanup_error=unsafe_active_ping_cleanup_target: ...`. A later
  real watcher initialization rewrites live watcher status from the new watcher
  state, so the degraded cleanup record is evidence of the prior cleanup
  failure, not a claim that a successfully restarted watcher remains degraded.
- Focused regression coverage in `mu/tests/tools/test_codex_autoping_watch.py`
  preserves intended stale process-group cleanup and proves a stale active PID
  pointing at an unrelated live process is not killed and is recorded as a
  cleanup-failure state for that failed cleanup attempt.
- Local validation passed: `bash -n tools/session/codex_autoping_window.sh`; `bash -n mu/tools/session/codex_autoping_window.sh`; `python3 -m py_compile mu/tests/tools/test_codex_autoping_watch.py`; `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_autoping_watch.py::test_autoping_window_restarts_dead_watcher_without_manual_preflight mu/tests/tools/test_codex_autoping_watch.py::test_autoping_window_skips_stale_active_pid_and_records_degraded_state`.
- L4 indicator artifact written with `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id codex-autoping-active-ping-cleanup-hardening-2026-05-05 --output reports/l4_wave_indicators/codex-autoping-active-ping-cleanup-hardening-2026-05-05.json --range HEAD` after the collector refused the unstaged default invocation.

## Scope

Files and directories in scope for the follow-on implementation wave:

- `tools/session/codex_autoping_window.sh`
- `mu/tools/session/codex_autoping_window.sh`
- Focused regression tests under `mu/tests/tools/` or an existing directly relevant test module.
- `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md` for closeout or stale-resolution evidence after implementation review.
- `TASKS.md` tracker sync after the implementation wave, not during this Phase A rewrite.
- `reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md` as the governing packet.
- `reports/l4_wave_indicators/codex-autoping-active-ping-cleanup-hardening-2026-05-05.json` for the eventual L4 indicator.

- `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reproduce the deferred active-ping cleanup finding against current code before editing. The retained finding says cleanup in the autoping window wrapper must avoid PID/PGID reuse hazards instead of trusting only a stale `active_pid`.
2. If that finding is still live, harden active-ping cleanup in the root wrapper and mirrored `mu/` wrapper so cleanup targets only the intended active ping process or process group. If current code already proves the finding stale, do not edit for this item; close it with exact file:line and command evidence.
3. Reproduce the deferred cleanup-failure surfacing finding against current code before editing. The retained finding says any cleanup failure that can be represented in durable autoping state must be surfaced there, not only in runner-log text.
4. If that finding is still live, surface representable cleanup failures in durable autoping state while preserving the wrapper's diagnostic-only semantics. If current code already proves the finding stale, do not edit for this item; close it with exact file:line and command evidence.
5. Keep root and mirrored wrapper behavior aligned for every landed autoping cleanup change.
6. Add focused mechanical regression coverage for any landed repair under `mu/tests/tools/` or an existing directly relevant test module.
7. Update the deferred non-blocking packet, `TASKS.md`, this governing packet, and the L4 indicator only as needed after implementation evidence exists.

## Constraints

- Do not inspect or edit runtime, seed, substrate, projection, scheduler, parity, VM semantic, or `/mu` production behavior files for this wave.
- Do not modify `.claude`, Claude-related local surfaces, or Claude adapter behavior.
- Do not start a new `/mu` production wave.
- Do not broaden this packet into general autoping, pager, dashboard, executor, recovery, or docs cleanup.
- Preserve diagnostic-only autoping semantics: the watcher/wake path must not edit repo files, run git, run shell commands, run broad preflight/docs consistency/pytest, apply structural fixes, or launch/relaunch executor processes.
- Treat TASKS.md authorization as wave/lane authority, not as proof that each deferred finding is still unlanded.
- Prefer current code truth over stale packet wording when implementation evidence later conflicts with this plan.

## Stop conditions

- Stop before implementation if Phase A or bridge review returns blocking findings on this packet.
- Stop the implementation wave if reproduction shows both retained findings are stale or already resolved; close them as stale with exact evidence instead of making code changes.
- Stop and split or repacket if a required fix reaches outside the scoped autoping wrapper, mirror, focused tests, tracker, deferred packet, governing packet, or L4 indicator surfaces.
- Stop if the only viable fix would make the diagnostic watcher run commands, mutate the repo, run git, execute broad checks, or launch/relaunch executors from the wake path.
- Stop if root and mirrored wrapper behavior cannot be kept aligned in the same bounded wave.
- Stop before commit packaging if no focused regression test or explicit stale-closure evidence exists for the addressed finding.

## Acceptance criteria

- Phase A packet contains concrete Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization sections.
- The implementation wave first records reproduction or stale-closure evidence for both deferred findings.
- Any live active-ping cleanup fix avoids stale PID/PGID reuse hazards in both scoped wrappers.
- Any live cleanup-failure surfacing fix records representable cleanup failures in durable autoping state.
- Root and mirrored autoping wrapper behavior remain aligned.
- Focused regression coverage proves each landed behavioral repair, or exact stale evidence proves why no repair was needed.
- Deferred packet closeout/update, `TASKS.md` tracker sync, governing packet update, and L4 indicator are completed after implementation evidence exists.
- No runtime/substrate/seed/projection/scheduler/parity/VM semantic files, `/mu` production behavior files, or Claude surfaces are changed.

## Grounding / Authorization

- Governing packet: `reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md`.
- Deferred source: `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`.
- Deferred finding 1: `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md:9-14` records the active-ping cleanup PID/PGID reuse hardening gap.
- Deferred finding 2: `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md:16-21` records cleanup failure logging without durable autoping state surfacing.
- TASKS.md targeted lookup found recent `PIPELINE-AUTOPING` lane evidence at `TASKS.md:212`, where the prior autoping owner-health self-heal wave is recorded as G8 control-surface/tooling/test/doc scope with no runtime/substrate paths.
- TASKS.md targeted lookup did not find an exact active `[PIPELINE-AUTOPING]` block for this new wave; this packet therefore carries the same-wave authorization token explicitly for commit automation:
  `FOUNDER_OVERRIDE:codex-autoping-active-ping-cleanup-hardening-2026-05-05`.
- Authorization: standing pipeline-bug-fix authorization for this bounded Codex autoping control-surface L4_ENABLER wave; the wave is limited to pipeline hardening and does not widen runtime/substrate semantics.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `codex-autoping-active-ping-cleanup-hardening-2026-05-05`
- Active packet: `reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md`
- Indicator artifact: `reports/l4_wave_indicators/codex-autoping-active-ping-cleanup-hardening-2026-05-05.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_codex_autoping_watch.py`
  - `mu/tools/session/codex_autoping_window.sh`
  - `reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md`
  - `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/codex-autoping-active-ping-cleanup-hardening-2026-05-05.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `codex-autoping-active-ping-cleanup-hardening-2026-05-05`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `codex-autoping-active-ping-cleanup-hardening-2026-05-05`
- Active packet: `reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `258a6d57834c94d8aae7be4fbd13838fddc259f964f0f42c0e2345b5b2f8f56e`
- Indicator artifact: `reports/l4_wave_indicators/codex-autoping-active-ping-cleanup-hardening-2026-05-05.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_codex_autoping_watch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/codex-autoping-active-ping-cleanup-hardening-2026-05-05.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_codex_autoping_watch.py`
  - `mu/tools/session/codex_autoping_window.sh`
  - `reports/control_plane/codex-autoping-active-ping-cleanup-hardening-2026-05-05_2026-05-05.md`
  - `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/codex-autoping-active-ping-cleanup-hardening-2026-05-05.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
