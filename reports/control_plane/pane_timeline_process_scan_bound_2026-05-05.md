# Pane Timeline Process Scan Bound

Date: 2026-05-05
Status: LOCKED - post-commit pre-push pipeline repair
Task: [NEXT-CODEX-POST-REDTEAM]
Parent wave: founder-ordered-redteam-wave-packet-seed-2026-05-05
Wave ID: pane-timeline-process-scan-bound-2026-05-05
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Founder override: FOUNDER_OVERRIDE:pane-timeline-process-scan-bound-2026-05-05

## Purpose

Repair the mechanical pre-push failure surfaced while committing the founder
ordered red-team packet seed. The seed wave had already converged through Phase
A and Phase B, but commit executor pre-push reported two pane timeline timeout
failures under the full `pre-push-fast` xdist suite.

This packet authorizes only the observability/test repair needed to make the
pipeline one-shot pane render bounded and repeatable. It does not authorize any
repo-code, docs, tests, tooling, or `/mu` structural audit remediation.

## Evidence

Direct failing output from commit executor pre-push:

- `tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pane_timeline_shows_last_pager_wake_summary`
- `tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pane_timeline_honors_rcx_codex_home_for_autoping_state`
- Both failures were `subprocess.TimeoutExpired` after 10 seconds while running
  `mu/tools/observability/_pane_timeline.sh` with `RCX_PANE_ONESHOT=1`.

Direct code path:

- `mu/tools/observability/_pane_timeline.sh` always renders the current status
  pointer before one-shot exit.
- The status pointer calls live process scans through `repo_has_bridge_role`,
  `repo_has_process`, and `repo_has_any_process`.
- Those scans can walk every live `codex exec` / `claude --print` match and can
  call `lsof` for candidates that do not include the repo root in the command
  line.

The direct repair target is therefore the live process-scan path most consistent
with the observed timeout. The full pre-push rerun remains the confirmation
step; this packet treats the change as a pipeline unblocker, not as an audit
finding or remediation wave.

Second repair iteration evidence:

- After the process-scan bound was committed locally, the full `pre-push-fast`
  suite reported a timeout in the new regression itself:
  `test_pane_timeline_bounds_live_process_scan_candidates`.
- Direct file review showed that the regression had not isolated `HOME` or
  `RCX_CODEX_HOME`, so the pane script could still inspect the operator's live
  Codex state while the regression was intended to exercise only process-scan
  bounds.
- The regression now uses temporary `HOME` and `RCX_CODEX_HOME` directories so
  it tests the bounded scan path without relying on user-local autoping state.

## Scope

Files in scope:

- `mu/tools/observability/_pane_timeline.sh`
- `tests/tools/test_recovery_gate.py`
- `reports/control_plane/pane_timeline_process_scan_bound_2026-05-05.md`
- `reports/control_plane/founder_ordered_redteam_wave_packet_seed_2026_05_0_2026-05-05.md`
- `TASKS.md`

No Claude-related files are in scope.

## Work Items

1. Bound `_pane_timeline.sh` live process candidate scans with a configurable
   `RCX_PANE_PROCESS_SCAN_LIMIT`.
2. Prefer the newest process candidates so current operator subprocesses remain
   visible while stale historical subprocesses do not dominate the scan budget.
3. Add a regression test proving one-shot pane rendering enforces the process
   scan bound even when many live Codex process candidates exist.
4. Re-run the two previously failing pane timeline tests and the new bounded
   scan regression.
5. Resume commit executor from the failed pre-push point after the repair is
   committed.

## Constraints

- Do not bypass `pre-push-fast` or use `git push --no-verify`.
- Do not alter the founder-ordered audit queue semantics.
- Do not start any red-team audit or remediation wave.
- Do not edit Claude-related files.

## Acceptance Criteria

- One-shot `_pane_timeline.sh` renders without unbounded live process scans.
- `RCX_PANE_PROCESS_SCAN_LIMIT` defaults to a bounded value and rejects invalid
  values back to the default.
- The regression test proves the live process scan cap limits `lsof` calls.
- The two previously failing pane timeline tests pass locally with the new
  regression test.
- Commit executor can resume from the pre-push failure and continue without a
  manual bypass.

## Grounding / Authorization

- Parent seed packet:
  `reports/control_plane/founder_ordered_redteam_wave_packet_seed_2026_05_0_2026-05-05.md`.
- Parent active task: `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]`.
- Parent directive token:
  `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- Repair wave-bound authorization:
  `FOUNDER_OVERRIDE:pane-timeline-process-scan-bound-2026-05-05`.
