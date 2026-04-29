# Codex Autoping Context Recovery — 2026-04-29

Wave ID: codex-autoping-context-recovery-2026-04-29
Task: [PIPELINE-RECOVERY]
Class: L4_ENABLER
Lane: control-surface
target_gate_id: G8

## Authorization

Standing pipeline-bug-fix authorization applies to Codex-local pager/autoping
control-surface hardening. This packet is bounded to the autoping context
exhaustion recovery path, startup health classification, orphan cleanup on
watcher restart, and regression tests for those behaviors.

FOUNDER_OVERRIDE:codex-autoping-context-recovery-2026-04-29

## Root Cause Evidence

- Live state before the fix showed
  `/Users/jeffabrams/.codex/state/rcx_autoping_019dc06c-8639-7150-8121-efc11a7aa5df.json`
  with `status: context_exhausted_paused`, `last_exit_code: 1`, and
  `pause_reason: current Codex thread context window is exhausted`.
- `mu/tools/session/codex_autoping_watch.py` converted context-window errors
  into a paused status and then reused that paused state instead of starting a
  fresh diagnostic lane.
- `mu/tools/session/check_codex_startup_state.py` accepted the paused
  context-exhausted state as healthy-enough degradation, so startup did not
  force mechanical recovery.
- Live process inspection after the first fresh-exec fallback showed stale
  orphaned autoping `codex exec` processes with `ppid=1`; the launcher cleanup
  only matched `codex exec resume`, not fresh diagnostic `codex exec`.

## Fix

- Added a fresh `codex exec` diagnostic command path for autoping ticks after
  the primary thread reports context exhaustion.
- Persisted `primary_thread_context_exhausted` and
  `recovery_mode=fresh_exec_after_context_exhaustion` so future ticks for the
  same exhausted thread continue through fresh diagnostic exec instead of
  retrying the dead resume path.
- Preserved unchanged-state suppression after the first recovery tick so a
  recovered watcher does not continuously spawn fresh diagnostic pings while
  bridge state is unchanged.
- Changed startup health so context-exhausted paused state is treated as a
  recovery condition, while fresh-exec recovery state reports as active.
- Expanded launcher orphan cleanup to reap both resume and fresh diagnostic
  autoping exec process groups tied to the same thread/summary slug.

## Validation

- `python3 -m py_compile tools/session/codex_autoping_watch.py tools/session/check_codex_startup_state.py`
- `bash -n tools/session/ensure_codex_autoping.sh`
- `PYTHONHASHSEED=0 PYTHONPATH=. pytest -q mu/tests/tools/test_codex_autoping_watch.py mu/tests/tools/test_codex_startup_state.py`
  - Result: `139 passed in 0.74s`
- Live restart command:
  `./tools/session/ensure_codex_autoping.sh --repo /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX --thread-id 019dc06c-8639-7150-8121-efc11a7aa5df --force-restart --initial-delay 0`
- Live startup-state output after recovery:
  `codex_autoping: OK Codex autoping active pid=10603 thread=019dc06c-8639-7150-8121-efc11a7aa5df status=idle_unchanged_state mode=fresh_exec_after_context_exhaustion recovery=fresh_exec`
- Live tmux window state after restart:
  `1:bash:1`, `2:AUTO-PING:0`

## Scope

- `mu/tools/session/codex_autoping_watch.py`
- `mu/tools/session/check_codex_startup_state.py`
- `mu/tools/session/ensure_codex_autoping.sh`
- `mu/tests/tools/test_codex_autoping_watch.py`
- `mu/tests/tools/test_codex_startup_state.py`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `codex-autoping-context-recovery-2026-04-29`
- Active packet: `reports/control_plane/codex_autoping_context_recovery_2026-04-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `969dbffcc20031e7f6e54323e9aafca7e0a5d5161a86cfd2587312ca7bdd1bfb`
- Indicator artifact: `reports/l4_wave_indicators/codex-autoping-context-recovery-2026-04-29.json`
- Evidence command: `python3 -m py_compile tools/session/codex_autoping_watch.py tools/session/check_codex_startup_state.py && bash -n tools/session/ensure_codex_autoping.sh && PYTHONHASHSEED=0 PYTHONPATH=. pytest -q mu/tests/tools/test_codex_autoping_watch.py mu/tests/tools/test_codex_startup_state.py`.
- Evidence delta: (1) Context-exhausted primary Codex thread now records fresh-exec recovery state instead of parking forever. (2) Startup health fails old context_exhausted paused state closed and accepts fresh_exec recovery as active. (3) Launcher force-restart cleanup now reaps orphaned autoping codex exec process groups, including fresh diagnostic execs. (4) Live verification ended with codex_autoping status=idle_unchanged_state mode=fresh_exec_after_context_exhaustion recovery=fresh_exec and tmux windows 1:bash:1, 2:AUTO-PING:0.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/codex-autoping-context-recovery-2026-04-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_codex_autoping_watch.py`
  - `mu/tests/tools/test_codex_startup_state.py`
  - `mu/tools/session/check_codex_startup_state.py`
  - `mu/tools/session/codex_autoping_watch.py`
  - `mu/tools/session/ensure_codex_autoping.sh`
  - `reports/control_plane/codex_autoping_context_recovery_2026-04-29.md`
  - `reports/l4_wave_indicators/codex-autoping-context-recovery-2026-04-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
