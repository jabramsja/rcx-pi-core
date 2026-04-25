# Post Reentry Reroute And Notification Truth 2026 04 23

Date: 2026-04-23
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-REENTRY-REROUTE]
Wave ID: post-reentry-reroute-and-notification-truth-2026-04-23
Phase-A-Lock: LOCKED
Wave class: MAINTENANCE
Target gate: G8

## Purpose

Bound the next follow-on wave that fixes the April 23 paused-wave failure mode
without reopening the broader closed recovery lane:

1. when post-reentry supervisor truth says `NEEDS_PHASE_B`, recovery must route
   back into deterministic Phase B re-entry instead of generic Tier 3
   exhaustion
2. dashboard panes must show which pager wake last launched or nudged live
   pipeline work
3. repo-native founder startup audit must surface the repo pager and Codex
   autoping watcher as separate notification channels
4. bridge provider/model changes must be one tracked config edit, not repeated
   hidden `.agent_bus/bridge_config.json` edits

## Grounding / Observed Failure Truth

- The paused April 22 worktree produced a real Phase B reviewer `GO`, but the
  same wave then hit the post-reentry veto path in
  `mu/tools/executors/phase_b_executor.py`: the supervisor returned
  `NEEDS_PHASE_B` after re-entry convergence, so commit did not start.
- The observed recovery behavior was wrong for that specific failure class:
  instead of reseeding deterministic Phase B re-entry, the wave fell into the
  generic recovery path and later exhausted on external agent/session/network
  failures.
- The fresh follow-on launch on 2026-04-23 exposed a second control-plane
  choke point: `phase_b_executor.py` exits `0` after an in-process recovery
  succeeds, but `executor_dispatch.py` was still treating any Phase B exit `0`
  as “converged” and immediately looking for
  `.agent_bus/executors/phase_b_handoff.json`. That produced the false stop
  `Phase B converged but no handoff file found` even though the real next
  action was “retry Phase B after the recovered pre-bridge fix.”
- The operator could not tell from the main dashboard panes that a resumed
  Codex pager turn had launched the later rerun; pane truth lagged behind
  runtime truth because pager provenance was not rendered into the main
  dashboard surfaces.
- Founder startup truth also needed to be explicit that WorkingRCX now has two
  separate Codex notification surfaces:
  - the repo-native pager lane
  - the separate Codex autoping watcher
- Bridge adapter truth also needed a tracked provider/model switch so
  `role_agents` selects Claude versus Codex and `bridge_agent_defaults` selects
  each agent's display/model/effort without treating hidden local bridge config
  as the canonical model source.

## Admitted Scope

This wave is limited to the control-plane files required to fix that exact
failure shape and surface it honestly:

1. `FOUNDER_SESSION_BOOTSTRAP.md`
2. `TASKS.md`
3. `mu/tools/agents/bridge_adapters.py`
4. `mu/tools/agents/bridge_config.example.json`
5. `mu/tools/executors/executor_common.py`
6. `mu/tools/executors/executor_config.json`
7. `mu/tools/executors/executor_dispatch.py`
8. `mu/tools/executors/phase_b_executor.py`
9. `mu/tools/executors/recovery_gate.py`
10. `mu/tools/observability/_pane_findings.sh`
11. `mu/tools/observability/_pane_processes.sh`
12. `mu/tools/observability/_pane_timeline.sh`
13. `mu/tools/observability/pipeline_agent_pager.py`
14. `mu/tools/observability/pipeline_dashboard.py`
15. `mu/tools/observability/pipeline_dashboard_web.py`
16. `mu/tools/observability/pipeline_monitor.sh`
17. `mu/tools/observability/pipeline_status.sh`
18. `mu/tools/session/check_codex_startup_state.py`
19. `mu/tools/session/codex_autoping_watch.py`
20. `mu/tools/session/codex_autoping_window.sh`
21. `mu/tools/session/ensure_codex_autoping.sh`
22. `mu/tools/session/render_codex_autoping_status.py`
23. `mu/tests/tools/test_agent_bridge_supervisor.py`
24. `mu/tests/tools/test_codex_autoping_watch.py`
25. `mu/tests/tools/test_codex_startup_state.py`
26. `mu/tests/tools/test_executor_config_alignment.py`
27. `mu/tests/tools/test_executor_dispatch.py`
28. `mu/tests/tools/test_phase_b_executor.py`
29. `mu/tests/tools/test_pipeline_agent_pager.py`
30. `mu/tests/tools/test_recovery_gate.py`
31. `reports/control_plane/enable_pager_and_hybrid_recovery_2026-04-17.md`
32. `reports/control_plane/post_reentry_reroute_and_notification_truth_2026-04-23.md`
33. `reports/control_plane/role_agent_switch_2026-04-21.md`
34. `reports/l4_wave_indicators/enable-pager-and-hybrid-recovery-2026-04-17.json`
35. `mu/tools/agents/bridge_supervisor.py`
36. `mu/tools/docs/docs_sync_report.py`
37. `mu/tests/tools/test_docs_sync_report.py`
38. `reports/control_plane/session_handoff_2026-04-24_post_reentry_reroute_pipeline_pager_autoping.md`
39. `mu/tests/docs/test_doc_placement_rules.py`
40. `mu/tests/docs/test_growth_caps.py`

Out of scope:

- new watcher daemons or tmux scraping as the source of truth
- parallel-pipeline namespacing / per-worktree bus identity work
- Claude-local config or hook edits
- reopening the broader closed `[PIPELINE-RECOVERY]` parent lane

## Work Items

1. Classify post-reentry supervisor `NEEDS_PHASE_B` separately from the generic
   `NEEDS_PHASE_B` family so recovery can deterministically resume
   `needs_phase_b_reentry` instead of falling into generic Tier 3.
2. Preserve enough structured Phase B failure metadata for recovery to prove it
   is handling the post-reentry veto path, not a generic ambiguous failure.
3. Persist last pager-dispatch provenance in pager state and render it into the
   main dashboard panes so pane truth shows who last woke dispatcher.
4. Require repo-native startup audit/preflight canaries to surface both
   `Codex pager:` and `Codex autoping:` explicitly.
5. Prevent dispatcher from chaining Phase B to commit on exit code alone: it
   must distinguish true `commit_ready` convergence from an exit-0
   “recovery succeeded, rerun Phase B” shape.
6. Keep bridge agent provider/model/effort switching in
   `mu/tools/executors/executor_config.json`: `role_agents` selects provider,
   and `bridge_agent_defaults` overlays hidden bridge configs at load time.
7. Keep Codex autoping diagnostic-only: it may summarize provided bridge/tmux
   state, but it must not mutate repo files, run git, run shell commands or
   tools, run tests/preflight/docs consistency, apply structural fixes, or
   restart executors from the headless wake path. The watcher accepts only
   `Autoping summary:` output as the ping summary and terminates stale resumed
   ping subprocesses after the configured wake timeout. After it captures a
   summary for an unchanged bridge/tmux state, it suppresses repeated model
   resumes until that visible pipeline state changes.
8. Honor executor-provided bridge turn budgets above adapter defaults so long
   Codex reviews launched by Phase B are not killed at the stale hidden adapter
   timeout when the foreground executor timeout is larger.

## Constraints

- Do not widen recovery by inventing a new generic LLM loop or by silently
  treating all `NEEDS_PHASE_B` failures as equivalent.
- Do not rely on the paused April 22 worktree as the next execution target.
  The next run must happen in a fresh linked worktree from current `dev`.
- Do not claim that the autoping watcher replaces the pager lane. They are two
  distinct notification surfaces and must remain described that way.
- Do not widen startup scope beyond repo-tracked founder/bootstrap truth and
  the repo-native startup audit.

## Stop Conditions

1. Stop and split the work if fixing this path requires parallel-pipeline
   namespacing, per-worktree tmux session names, or per-worktree dashboard
   ports. That belongs under `[PARALLEL-PIPELINE]`.
2. Stop and split the work if correct operator truth requires a second passive
   observer stack, log scraping, or pane parsing as the authoritative source.
3. Stop and split the work if the repo-native startup audit needs to edit
   Claude-owned surfaces instead of repo or Codex-local startup surfaces.

## Acceptance Criteria

1. Post-reentry supervisor vetoes are mechanically classified into a
   deterministic reroute path that reseeds Phase B re-entry instead of generic
   Tier 3 recovery.
2. Pager state persists the last wake provenance clearly enough for the main
   dashboard panes to show who last woke dispatcher and why.
3. Repo-native founder startup audit fails closed when the preflight wrapper no
   longer surfaces both `Codex pager:` and `Codex autoping:` channels.
4. Tests prove the new classifier path, pager provenance persistence, pane
   render truth, and startup canary enforcement directly from the in-scope
   files.
5. Dispatcher and recoverable surface entrypoints retry Phase B when it exits
   `0` because an in-process recovery already succeeded, and they no longer
   mis-report that shape as `Phase B converged but no handoff file found`.
6. Tests prove `bridge_agent_defaults` overlays hidden bridge config command
   arguments and display names, so Codex model/effort changes are made from one
   tracked config block.
7. Tests prove autoping prompts forbid file mutation, git operations,
   structural fixes, executor relaunch, shell/tool diagnostics, and
   preflight/test suites from the headless wake path, and prove autoping summary
   parsing ignores unrelated live-thread operator messages after a ping summary.
   The watcher should also avoid repeated pings for unchanged visible state.
8. Tests prove bridge supervisor turn timeout overrides can exceed the adapter
   default when Phase B explicitly supplies a larger executor budget.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py::test_dispatcher_state_persists_last_dispatch_provenance mu/tests/tools/test_codex_startup_state.py::test_preflight_wrapper_missing_autoping_canaries_fails mu/tests/tools/test_codex_startup_state.py::test_preflight_wrapper_accepts_autoping_aware_wrapper mu/tests/tools/test_recovery_gate.py::TestNeedsPhaseB_Tier3::test_post_reentry_needs_phase_b_classified_as_tier1_resume mu/tests/tools/test_recovery_gate.py::TestNeedsPhaseB_Tier3::test_attempt_recovery_seeds_phase_b_reentry_checkpoint_for_post_reentry_veto mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pane_timeline_shows_last_pager_wake_summary mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pane_processes_shows_last_pager_wake_line`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pane_findings_uses_bridge_db_failed_turn_when_envelope_missing`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_bridge_supervisor.py::test_bridge_turn_timeout_env_override_can_exceed_adapter_timeout`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_autoping_watch.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_docs_sync_report.py::test_docs_sync_report_ignores_tracker_sections_in_exempt_paths mu/tests/tools/test_docs_sync_report.py::test_docs_sync_report_check_mode_passes_in_repo_state`
- `python3 tools/session/check_codex_startup_state.py`
- `./tools/checks/check_docs_consistency.sh`

## Notes

- This packet intentionally uses a fresh active task bucket instead of
  pretending the closed `[PIPELINE-RECOVERY]` parent lane is still open.
- The local Codex wrapper/hook updates that surface the same two notification
  channels are out-of-repo operator surfaces. They are not part of the git wave
  scope here, but the repo-native startup audit must still verify their visible
  canaries.
- Pane 2 must render terminal bridge DB truth when a reviewer raw output file
  exists without a parseable envelope. The observed failure shape is
  `jobs.status=AWAITING_REVIEWER_APPROVAL` with the latest reviewer turn
  `FAILED / ERROR`; that is stopped/error state, not live progress.
- Codex executor/reviewer defaults now target `gpt-5.5` with xhigh reasoning in
  `mu/tools/executors/executor_config.json` under
  `bridge_agent_defaults.codex`. `role_agents.implementer` and
  `role_agents.reviewer` remain the provider switch; `bridge_agent_defaults`
  is the tracked model/display/effort switch. The bridge loader overlays those
  defaults onto `.agent_bus/bridge_config.json`, so the hidden file remains a
  local command skeleton rather than the model source of truth.
  Any already-running older Codex bridge turns must be stopped and relaunched
  to pick up the new model because subprocess arguments are fixed at launch time.
- The 2026-04-24 retry exposed a bridge timeout bug: Phase B passed the larger
  executor timeout through `RCX_BRIDGE_MAX_TURN_WALL_TIME_S`, but
  `bridge_supervisor.py` still capped the adapter with
  `min(adapter.timeout_s, override)`. The supervisor now treats the explicit
  executor override as authoritative, preserving the short direct-call cap only
  when no override is supplied.
- Autoping is not a mutation lane. Its prompt now explicitly forbids file edits,
  git operations, shell commands/tools, tests/preflight/docs consistency,
  structural fixes, and executor relaunch from the headless watchdog wake path.
- Docs sync now ignores tracker section headers in `exempt` markdown paths such
  as `.scratch/` staged review copies, so temporary validator artifacts do not
  create false tracker-section placement failures.
- Pre-commit doc governance now applies the same transient-artifact principle to
  tracker-section placement checks, and the growth caps record the founder-signed
  one-test/four-tool increase required by the Codex autoping watcher surface.
- Follow-up after this wave is clean: mechanize the live-dashboard code root so
  tmux panes execute the active worktree's observability scripts, or maintain a
  repo-native sync path for root-launched pane scripts. During this pass the
  live panes were respawned from the active worktree after the old tmux session
  was observed running root-checkout scripts while resolving active-worktree data.
- Follow-up after this wave is clean: add a dispatcher/autoping mutual-exclusion
  guard so an autoping-triggered recovery restart and an operator-started
  foreground restart cannot launch the same Phase B wave concurrently.
