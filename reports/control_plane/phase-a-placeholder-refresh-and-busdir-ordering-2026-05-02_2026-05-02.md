# Phase-A-Placeholder-Refresh-And-Busdir-Ordering-2026-05-02

Date: 2026-05-02
Status: Phase B (implementation-complete, bridge-converged)
Task: [PIPELINE-RECOVERY]
Wave ID: phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02
Purpose: Create a bounded Phase A packet for the mechanical recovery follow-up from PR #854 and the structural failures exposed while routing that follow-up. The wave is limited to Phase A same-file placeholder packet refresh, bridge/dialectic `bridge_supervisor` global-argument ordering for namespaced bus lanes, Phase A lock/header normalization, stale-turn bridge decision parsing, and hybrid recovery scratch-cache tolerance, plus targeted regression tests. This is pipeline hardening, not manual cleanup or a reopening of the closed `[PIPELINE-RECOVERY]` parent lane.
## Scope

Files and directories in scope for the implementation wave:

- `reports/control_plane/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_2026-05-02.md`
  - Governing Phase A packet only.
- `mu/tools/executors/`
  - Phase A packet-generation / packet-refresh code that writes or refreshes same-file placeholder packets.
  - Bridge `bridge_supervisor` invocation assembly for namespaced bus lanes.
  - Dialectic `bridge_supervisor` invocation assembly for namespaced bus lanes.
  - Phase A plan-lock/header parsing for decorated `Phase-A-Lock` metadata.
  - Phase A bridge decision extraction from rendered transcripts containing stale and completed reviewer turns.
  - Recovery-gate hybrid scratch inventory checks for generated Python bytecode cache paths.
  - Recovery-gate fallback routing from `next_candidates[].tracked_packet` when Phase B needs a plan-bound retry.
- `mu/tools/session/codex_autoping_watch.py`
  - Codex autoping diagnostic classifier only; the wake path remains read-only and must not mutate repo or launch executor processes.
- `tests/`
  - Targeted regression coverage for same-file placeholder packet refresh, Phase A namespaced `--bus-dir` / global-argument ordering, and dialectic namespaced `--bus-dir` / global-argument ordering.
  - Targeted regression coverage for any root-cause repair added during this wave.
- `mu/tests/`
  - Targeted regression coverage for same-file placeholder packet refresh, Phase A namespaced `--bus-dir` / global-argument ordering, and dialectic namespaced `--bus-dir` / global-argument ordering.
  - Targeted regression coverage for Phase A lock/header normalization, stale-turn bridge decision parsing, and hybrid recovery scratch-cache tolerance.
  - Targeted regression coverage for Codex autoping hard-fail attention and recovery-gate `next_candidates[].tracked_packet` fallback.
- `TASKS.md`
  - Canonical tracker sync note only when mechanically inserted or refreshed by Phase B before pre-commit supervisor validation.
- `reports/l4_wave_indicators/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02.json`
  - Canonical L4 indicator artifact mechanically generated and staged by Phase B before pre-commit supervisor validation.
- `reports/deferred/non_blocking/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

Only files under the explicit paths above may be edited, and only for the bounded behaviors named in this packet. If the required change resolves outside this explicit file/directory list, stop for re-authorization instead of widening this packet.

## Work Items

1. Replace the Phase A placeholder-refresh stub behavior with a same-file refresh path that rewrites the intended placeholder packet instead of leaving stale placeholder content behind.
2. Correct the Phase A bridge `bridge_supervisor` invocation so global arguments for namespaced bus lanes are ordered where the supervisor parser treats them as global arguments.
3. Correct the dialectic bridge `bridge_supervisor` invocation with the same namespaced bus-lane global-argument ordering rule.
4. Add or update targeted regressions that fail on the PR #854 follow-up defects and pass when the placeholder refresh and both bus-dir ordering paths are correct.
5. Mechanically canonicalize a single decorated Phase A lock metadata line such as `Phase-A-Lock: UNLOCKED (...)` while continuing to fail closed on contradictory mixed canonical/decorated lock metadata.
6. Mechanically parse rendered bridge transcripts by turn status so a stale reviewer turn does not override a later completed reviewer `GO`, while stale-only reviewer output remains fail-closed.
7. Mechanically tolerate generated `.scratch/__pycache__` bytecode cache paths in hybrid recovery scratch inventory checks without allowing arbitrary scratch descendants.
8. Before implementation, check current code truth for each item actually touched. If a listed item is already implemented in current code, remove it from pending work and acceptance criteria rather than re-listing it as unresolved.
9. Mechanically sync a canonical same-wave tracker note into `TASKS.md` before Phase B pre-commit supervisor validation, so Gate 2 and Gate 8 consume trusted tracker authority instead of failing after bridge convergence.
10. Mechanically collect and stage the same-wave L4 indicator artifact after pre-supervisor tracker sync and before pre-commit supervisor validation, so the L4 contract does not reference an absent artifact.
11. Mechanically mark Codex autoping `attention_required` when the visible tmux/pager tail contains terminal hard-fail events such as `executor_hard_fail` or `pipeline_hard_fail`, even if the latest bridge job remains `DONE/GO`.
12. Mechanically recover plan-bound Phase B retries from routing records that carry the governing packet in `next_candidates[].tracked_packet`.
13. Mechanically authorize the same-wave generated deferred non-blocking report in packet scope and acceptance when it is staged by commit-path truth refresh, so deferred bridge findings do not become an out-of-scope package contradiction.

## Constraints

- Do not treat the closed `[PIPELINE-RECOVERY]` lane as standing authorization.
- Do not reopen broad pipeline recovery, Tier 3 recovery, learning-store, dispatcher retry-loop, hybrid recovery, bridge linger, or commit-continuation work.
- Do not perform manual cleanup of reports, buses, generated packets, or executor state as a substitute for fixing the mechanical path.
- Do not change runtime semantics, bootstrap boundaries, adapter authority, or host/substrate behavior.
- Do not touch unrelated dirty files or unrelated executor/test changes.
- Do not add broad integration suites unless a targeted regression cannot honestly prove the packet-bounded behavior.
- Do not expand beyond the files/directories in Scope without a new bounded packet or explicit founder authorization.

## Stop Conditions

Stop and return to Phase A review if any of the following occurs:

- The required fix resolves to files outside `reports/control_plane/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_2026-05-02.md`, `mu/tools/executors/`, `mu/tools/session/codex_autoping_watch.py`, `tests/`, `mu/tests/`, `reports/deferred/non_blocking/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers.md`, or a canonical `TASKS.md` tracker note for this wave.
- Current code truth proves one of the planned items has already landed; update the packet instead of implementing stale work.
- The implementation requires reopening `[PIPELINE-RECOVERY]` or relying on its closed parent lane as standing authorization.
- The global-argument ordering issue cannot be reproduced or specified with targeted tests.
- The placeholder refresh issue requires report cleanup rather than a mechanical same-file refresh fix.
- Commit automation cannot derive the same-wave authorization from `FOUNDER_OVERRIDE:phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02`.
- Any new root-cause repair requires files outside this packet's explicit scope.
- The L4 indicator artifact cannot be generated by `mu/tools/metrics/collect_l4_wave_indicators.py` after Phase B stages the pre-supervisor tracker note.
- The recovery scratch-cache repair would require broad `.scratch` deletion instead of a narrow mechanical cache-path exemption.

## Acceptance Criteria

The implementation wave is acceptable only when:

- Same-file Phase A placeholder packet refresh is mechanically covered by a targeted regression.
- Phase A bridge `bridge_supervisor` invocations place namespaced bus-lane global arguments where `bridge_supervisor` parses them as global arguments.
- Dialectic bridge `bridge_supervisor` invocations apply the same global-argument ordering rule.
- Phase A lock/header parsing canonicalizes a single decorated lock metadata line, rejects mixed contradictory lock metadata, and is mechanically covered by targeted regressions.
- Phase A rendered bridge decision parsing ignores stale turn decisions when a completed real reviewer decision exists, preserves stale-only fail-closed behavior, and is mechanically covered by targeted regressions.
- Hybrid recovery scratch inventory checks ignore generated `.scratch/__pycache__` cache paths without widening arbitrary scratch descendant permissions, and are mechanically covered by targeted regressions.
- Targeted regressions cover placeholder refresh, Phase A bus-dir ordering, dialectic bus-dir ordering, lock/header normalization, stale-turn decision parsing, and scratch-cache tolerance.
- Phase B mechanically inserts or refreshes the same-wave `TASKS.md` tracker note before pre-commit supervisor validation, carries the package-bound founder override token, and covers that ordering with a targeted regression.
- Phase B mechanically collects and force-stages `reports/l4_wave_indicators/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02.json` before pre-commit supervisor validation, includes it in the supervisor package scope, and covers that ordering with targeted regression assertions.
- Codex autoping marks visible `executor_hard_fail` / `pipeline_hard_fail` pager tails as `attention_required` before unchanged-state suppression can hide the event, and targeted regression coverage proves the DONE/GO bridge case.
- Recovery-gate plan fallback reads `next_candidates[].tracked_packet` when `plan_path` and `scope_items` do not identify the Phase B packet, and targeted regression coverage proves the fallback.
- No pending work item remains in the packet if current code truth proves it already landed.
- The final touched-file set stays within `reports/control_plane/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_2026-05-02.md`, `reports/l4_wave_indicators/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02.json`, `reports/deferred/non_blocking/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers.md`, `mu/tools/executors/`, `mu/tools/session/codex_autoping_watch.py`, `tests/`, `mu/tests/`, and the same-wave canonical `TASKS.md` tracker note, or returns for re-authorization.
- The packet retains explicit grounding, constraints, stop conditions, acceptance criteria, and wave-bound authorization.

## Grounding / Authorization

- Governing packet: `reports/control_plane/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_2026-05-02.md`.
- TASKS.md grounding: `TASKS.md:358-373` marks `[PIPELINE-RECOVERY]` **CLOSED**, records its historical design/file context, and classifies the lane as control-surface pipeline hardening.
- TASKS.md policy bound: `TASKS.md:370` states that future recovery hardening must be authorized as new bounded waves rather than implied by the landed parent lane.
- Authorization: this packet is that new bounded wave for the PR #854 mechanical follow-up. It does not assert standing pipeline-bug-fix authorization from `[PIPELINE-RECOVERY]`.
- Same-wave override for control-surface L4_ENABLER automation: `FOUNDER_OVERRIDE:phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02`.

## Phase B Current Code Truth / Bridge Round 9 Repair Notes

- Current code truth before the bridge round 9 fix already contained staged repairs for Phase A and dialectic namespaced `--bus-dir` global-argument ordering, decorated `Phase-A-Lock` canonicalization with mixed-line fail-closed behavior, stale/completed turn status parsing, and narrow `.scratch/__pycache__/*.pyc` hybrid scratch-cache tolerance.
- Bridge round 9 left only two blocking root-cause repairs pending in this packet: generated-looking placeholder packets with authored required H2 sections after `Request` were still overwritten, and multiline rendered `Summary` text could inject later `Status: completed` / `Decision: GO` metadata into a stale-only reviewer turn.
- Phase B repair is limited to the scoped executor/test packet: required Phase A H2 sections after `Request` are treated as authored packet sections even when the header looks executor-generated, and rendered bridge turns ignore post-summary status/decision text while completing a turn only on that turn's own raw-output artifact line.
- The already-present bus-dir ordering, decorated lock/header normalization, and hybrid scratch-cache tolerance repairs remain covered by targeted tests in this same packet and are not reopened as broader pipeline recovery work.

## Bridge Round 10 Repair Notes

- Bridge round 10 narrowed the remaining blocker to stale-only rendered reviewer turns whose multiline `Summary` included the matching raw-output terminator before fake `Status: completed` / `Decision: GO` metadata.
- Phase B repair keeps the same bounded parser surface: after a turn's own raw-output artifact line is reached, subsequent non-heading lines in that rendered turn are ignored, so stale-only reviewer output remains fail-closed while later real completed reviewer turns still outrank stale turns.

## Dispatcher Continuation Repair Notes

- The Phase A surface was invoked with a larger bridge-round budget, but the Phase A -> Phase B continuation did not forward that budget into the chained `phase_b_executor.py` command.
- The continuation path now forwards the surface `--max-rounds` value into chained Phase B, with a regression asserting the generated Phase B argv preserves the requested value.

## Bridge Round 2 Repair Notes

- Bridge round 2 narrowed the remaining blocker to structured rendered reviewer turns whose `Status: completed` / `Decision: GO` metadata was accepted at EOF without the turn's own matching raw-output artifact terminator.
- Phase B repair keeps the same bounded parser surface: rendered turns are decision-eligible only after `- Raw output: .../<turn_id>.txt` has completed that turn, so incomplete completed reviewer metadata fails closed instead of authorizing convergence.

## Bridge Round 4 Repair Notes

- Bridge round 4 narrowed the remaining blocker to stale-only rendered reviewer turns that reused the same raw-output artifact after a blank-line fake heading with the same turn id.
- Phase B repair remains in the scoped rendered-turn parser: after a turn's own raw-output artifact completes it, a later rendered heading must identify a distinct turn in the same job family before it can start a new decision-eligible turn. Same-turn raw-output reuse stays fail-closed as stale-only reviewer output.

## Pre-Commit Supervisor Tracker Binding Repair Notes

- Pre-commit supervisor rejected the bridge-converged package because `tools/checks/enforce_l4_execution_contract.py --staged --wave-id phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02` could not find the wave id in any trusted `TASKS.md` tracker sync note.
- Phase B now mechanically inserts or refreshes the canonical same-wave tracker note before building and running the pre-commit supervisor package, includes `TASKS.md` in the package scope when it changed, and carries the package-bound `founder_override_token` so Gate 8 can use the staged-token-bound validation path.

## Pre-Commit Supervisor Indicator Artifact Repair Notes

- Pre-commit supervisor next rejected the bridge-converged package because `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02` reported `indicator_artifact_ref 'reports/l4_wave_indicators/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02.json' not in changed files` and `Indicator artifact ... does not exist on disk`.
- Phase B now mechanically runs the canonical indicator collector after staging the pre-supervisor tracker note, force-stages the generated indicator artifact, includes it in the supervisor package `changed_files`, and refreshes `evidence_handles.indicator` before pre-commit supervisor validation.

## Autoping / Recovery Continuation Repair Notes

- Codex autoping failed to surface the live commit hard fail because the latest bridge job stayed `DONE/GO` while pane 4 showed `Last pager wake: 20:04:15 | executor_hard_fail | executor_dispatch/failed`; unchanged-state suppression then held the stale no-intervention summary.
- Autoping now classifies visible `executor_hard_fail` and `pipeline_hard_fail` pager tails locally before unchanged-state suppression and writes an `attention_required` summary without launching tools from the wake path.
- Dispatcher recovery failed to re-enter Phase B after the supervisor returned `NEEDS_PHASE_B` because the active routing record carried the packet as `next_candidates[].tracked_packet`, while recovery only read `plan_path` and `scope_items`.
- Recovery now resolves plan-bound Phase B retries from `next_candidates[].tracked_packet` with targeted regression coverage.

## Commit Path Deferred Report Authorization Repair Notes

- Commit executor refresh staged `reports/deferred/non_blocking/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers.md` as commit-bound truth while this packet's scope and final touched-file acceptance criteria still omitted that same-wave deferred report.
- Commit-path truth refresh now mechanically authorizes the same-wave generated deferred non-blocking report in the packet scope, stop conditions, and final touched-file acceptance criteria when the report is present in `deferred_items` or current staged files.

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02`
- Active packet: `reports/control_plane/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_2026-05-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `fa69de1ebcefedd0558e9aca238e18b1c935c981ce1ed6cfd818e36e471f03a1`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bus_namespacing.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_2026-05-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bus_namespacing.py`
  - `reports/control_plane/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02_2026-05-02.md`
  - `reports/l4_wave_indicators/phase-a-placeholder-refresh-and-busdir-ordering-2026-05-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
