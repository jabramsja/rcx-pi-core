# Preserve explicit default-bus monitor selection across native owner startup

Date: 2026-10-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-monitor-default-pin-r1-2026-10-04
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 031a0af237c6c8afee3f5135d6d292d55c002a30093a4130f6628417310a459f
Purpose: Fix the actual required CI assertion that stopped cleanup enabler PR1330, then resume both preserved existing PRs and physically retire the five already planned folders. This is not generic observability hardening.

## Scope

Only pipeline_monitor.sh and its existing autofollow tests, plus native packet/evidence/indicator/tracker outputs. Existing program row38; zero new numbered queue rows.

Files and surfaces in scope:

- TASKS.md
- CHANGELOG.md
- reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md
- reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_implementation_evidence.json
- reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json
- reports/deferred/non_blocking/workingrcx-monitor-default-pin-r1-2026-10-04_bridge_nonblockers.md
- mu/tools/observability/pipeline_monitor.sh
- mu/tests/tools/test_pipeline_monitor_autofollow.py
- TASKS.md -- tracker-sync authority. The 2026-10-04 tracker sync note for wave `workingrcx-monitor-default-pin-r1-2026-10-04` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/workingrcx-monitor-default-pin-r1-2026-10-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read exact evidence /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/budget_pr1330_ci_stop_diagnosis_20261004.json and the actual option parse/autofollow/ensure_owner_running/owner-loop hunks. CI command shows RCX_OBS_AUTOFOLLOW_BUS=1 for explicit --bus-dir .agent_bus. The startup code sets EXPLICIT_PIN but omits the default bus from owner_args, resetting that intent in the new shell.
2. Make the smallest production correction retaining explicit default bus selection when spawning the native owner. Preserve unpinned default autofollow and existing nondefault/lane/session semantics. Do not redesign monitor lifecycle or modify default provider configuration.
3. Extend existing test_pipeline_monitor_autofollow.py to exercise the demonstrated owner path deterministically, rather than relying on parent/owner scheduling or test reruns. Keep the original assertion against RCX_OBS_AUTOFOLLOW_BUS and use real script/subprocess behavior with isolated fake-tmux fixture surfaces. Prove the regression fails on original code and passes on the minimal fix; preserve existing default and named-pinned tests.
4. Keep evidence compact and truthful, with exact reproduction/test commands, exits and observed counts. Historical PR1330 CI failure and isolated local PASS are not current fix validation; do not claim physical cleanup or any old PR merged.
5. Keep TASKS row38 and working order current: land/sync this monitor correction, native --land-stranded 1330 on its preserved original bus/receipt chain to bring current and pass fresh CI/review/merge, native preserved PR1329 corrective continuation using the landed600-second runner, then five exact-target APPLY/VERIFY, PR1325 useful-work disposition and existing Mu owner. Preserve all268task IDs and44ordered queue rows; no extra prerequisite or numbered row.
6. Leave PR1330/R2/R1/alias worktrees, staged files, indices, source refs, recovery histories and authority bytes untouched. This packet neither copies their code nor closes their PRs. Fix the failing shared-base behavior here so their existing native continuations can proceed.

## Constraints

- Operator supplies STUB only; launch_wave.py and PhaseA author the full packet. Native actors own all source changes, reviews, staging, commits, pushes, conflict resolution and merges.
- Only the demonstrated pin-loss blocker. No changes to recovery_gate, timeouts, unrelated monitor cases, runtime/host/substrate, Claude-owned surfaces or provider configuration. Already-owned recovery diagnostic deficiencies stay after physical cleanup under row40.
- No assertion weakening, test skips, xfail, rerun-until-green, force merge, receipt edits or counter resets. Existing unpinned default monitor must keep autofollow.
- Retain all prior useful work and private held PRIMARY transaction/stash; never pop/drop/rewrite them. One native mutation lane only. All LLM roles Codex gpt-6-astra/max; providerless commit.
- No folder retirement/APPLY or PR1325/1329/1330 closure in this wave. Native own-carrier lifecycle is unchanged. Successful monitor fix is not fleet completion.

## Stop conditions

- Report exact path if required implementation exceeds this immutable scope; do not silently widen it.
- Stop immediately on founder stop or observed quota at/below10 percent. No new watchdog.
- Do not work on the separately paused runtime investigation.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_pipeline_monitor_autofollow.py`

## Acceptance criteria

- The existing default-bus pin contract survives real background-owner startup, with deterministic regression evidence on old and corrected code.
- The declared full autofollow test module and all native required validation/review/CI gates pass without weakening tests.
- Native merge and protected PRIMARYsync complete; then resume preservedPR1330 through its existing native landing operation, not a replacement packet.
- TASKS/working to-do truthfully leave five-target cleanup and useful-work disposition pending and next, with no queue growth.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-monitor-default-pin-r1-2026-10-04`.
- Governing packet: this file, `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md`.
- TASKS.md authority: the 2026-10-04 tracker sync note for wave `workingrcx-monitor-default-pin-r1-2026-10-04` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-monitor-default-pin-r1-2026-10-04

## Phase B implementation observation (2026-10-04)

The production change only broadens the owner argument condition to retain
`EXPLICIT_PIN=1` for the default bus. The existing autofollow tests now include
an isolated fake-tmux mode in which the real spawned owner constructs all four
pane commands. The fixture verifies the builder PID and a completed layout
milestone; the original autofollow assertions remain unchanged. Ordinary-start,
unpinned-default, named-bus, lane and session-override coverage remains.

Both runs used the exact Validation gates command above with identical extended
tests: original production source exited 1 (1 failed, 23 passed in 65.81s) at
`test_b2_pinned_monitor_panes_have_no_autofollow_signal[owner-default-bus-pin]`;
the corrected source exited 0 (45 passed in 96.28s). The explicit-default owner
emitted the forbidden signal in 4 of 4 pane commands before the fix and 0 of 4
after it. Exact source hashes, commands and counts are recorded in
`reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_implementation_evidence.json`.
Historical PR1330 CI failure and the old isolated local pass are diagnosis only.

The 2026-10-04 TASKS tracker note remains the sole L4 field authority. Native
indicator collection and bridge findings are outer-executor outputs, pending
actual collection/review; this implementer does not fabricate those artifacts.
Native review, mandatory gates, CI, merge and protected PRIMARY synchronization
remain pending. Then use the original PR1330 native landing chain, the preserved
PR1329 continuation with the landed600-second runner, five exact-target
APPLY/VERIFY, PR1325 useful-work disposition and the existing Mu owner in the
order recorded in row38. No old PR, folder, recovery history, receipt, index,
source ref or private held PRIMARY transaction/stash was changed by this pass.
The separate runtime investigation remains paused.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-monitor-default-pin-r1-2026-10-04`
- Active packet: `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md`
  - `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_implementation_evidence.json`
  - `reports/deferred/non_blocking/workingrcx-monitor-default-pin-r1-2026-10-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `workingrcx-monitor-default-pin-r1-2026-10-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/workingrcx-monitor-default-pin-r1-2026-10-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-monitor-default-pin-r1-2026-10-04 --output reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_pipeline_monitor_autofollow.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md`, `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_implementation_evidence.json`, `reports/deferred/non_blocking/workingrcx-monitor-default-pin-r1-2026-10-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-monitor-default-pin-r1-2026-10-04.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-monitor-default-pin-r1-2026-10-04`
- Active packet: `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `bef31418199e1ba49f38ec3f8ff0c84916f6476025a5cd3f7d62a2728684a136`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_pipeline_monitor_autofollow.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md`, `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_implementation_evidence.json`, `reports/deferred/non_blocking/workingrcx-monitor-default-pin-r1-2026-10-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_2026-10-04.md`
  - `reports/control_plane/workingrcx-monitor-default-pin-r1-2026-10-04_implementation_evidence.json`
  - `reports/deferred/non_blocking/workingrcx-monitor-default-pin-r1-2026-10-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/workingrcx-monitor-default-pin-r1-2026-10-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
