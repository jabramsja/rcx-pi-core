# Finish PR1312 CI fixture and observed recovery misclassification

Date: 2026-09-23
Status: Phase B (locked, implementing)
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-pr1312-ci-continuation-r1-2026-09-23
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 039e3831036a3384da344d7e145f1644a72fb74c189ae6cccfbda8310a67cfa4
Purpose: Authorized control-surface L4_ENABLER repair on the existing PR branch for PR1312. Fix the single remaining CI fixture and the reproduced historical-transcript bootstrap misclassification through the normal native pipeline; same carrier, same task, same PR.

## Scope

Nine exact paths: the remaining failed cleanup fixture, recovery classifier and its test, two trackers, bounded growth governance, native packet/indicator and optional report. Keep all other committed R8 implementation and lifecycle tests intact.

Files and surfaces in scope:

- TASKS.md -- Existing row40 ownership; preserve all268task IDs,39parked obligations, R8 history and accurate directly-next physical cleanup/useful-work/Mu work.
- CHANGELOG.md -- Record only this bounded existing-PR correction.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py -- Reproduce and repair test_native_merge_owner_survives_lane_retirement_without_closing_predecessor under the actual runner-like Git-filter condition; preserve real cleanup assertions.
- mu/tools/executors/recovery_gate.py -- Correct the observed historical successful-review transcript being treated as current bootstrap-error authority; keep genuine bootstrap and scope guards and finite attempt budgets.
- mu/tests/tools/test_recovery_gate.py -- Regression for the actual captured commit stdout/current CI terminal and existing genuine bootstrap fault behavior.
- mu/tests/docs/test_growth_caps.py -- Only native mechanical governance adjustment if the real changed footprint requires it; retain actual counts and proof.
- reports/control_plane/workingrcx-pr1312-ci-continuation-r1-2026-09-23_2026-09-23.md -- Native PhaseA full packet authored from this external STUB.
- reports/l4_wave_indicators/workingrcx-pr1312-ci-continuation-r1-2026-09-23.json -- Native same-wave indicator.
- reports/deferred/non_blocking/workingrcx-pr1312-ci-continuation-r1-2026-09-23_bridge_nonblockers.md -- Optional generated report only for an actual non-blocking finding.
- TASKS.md -- tracker-sync authority. The 2026-09-23 tracker sync note for wave `workingrcx-pr1312-ci-continuation-r1-2026-09-23` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. PhaseA authors the full packet with explicit existing-PR control-surface authority. Target existing PR1312 branch jabramsja/workingrcx-fleet-native-prevention-r8-2026-09-22 in /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-fleet-native-prevention-r8-20260922; baseline is current clean pushed58fe35e1332608dd8919ce98643c299fba5b1f56. The prior successful pattern is /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/control_plane/workingrcx-pr1311-fixture-continuation-r2-2026-09-22_wave_config.json. Native PhaseB must build caller phase_b handoff from the indexed authorized packet and keep this existing branch.
2. Read exact CI and recovery evidence at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-native-prevention-r8-evidence-2026-09-22/pr1312_followup_green_gate.log, post_ci_bootstrap_false_positive_diagnosis.json, pr1312_followup_captured_commit_stdout.txt and pr1312_followup_native_ci_error.json. Full captured stdout SHA256ff0f6c8f9943539287fc3fc0ae430669660958e9aea7a39187845a6ea64aa1b7; terminal JSON SHA2565445f19b6ac57d737bc4c8e1282aeefd198d0993860abf7dd933f5e91f070d4e. Use bounded extraction rather than dumping logs or scratch trees.
3. Reproduce the one named cleanup fixture failure with ambient runner Git filters, then fix fixture environment isolation at the Git exec boundary. Existing census drops inherited GIT_* overrides deliberately; the already-repaired lifecycle fixture and fleet fixtures show the actual pattern. Preserve production filter refusal, useful-work checks, exact closeout/PR-owner assertions and all committed R8 safeguards. Keep mu/tests/tools/test_worktree_lifecycle.py unchanged.
4. Reproduce recovery_gate bootstrap detection on the preserved command stdout: it currently returns blocked for a historical TASKS2026-04-17 phrase, while the actual current terminal CI error alone returns clear. Correct current-versus-historical diagnostic authority for this observed native envelope using the existing classifier architecture, with a real regression. Genuine current bootstrap faults still fail closed; retained scope/Git-control audits and attempt budgets stay intact.
5. Keep the generated packet valid under commit_executor._packet_declares_same_wave_id and _packet_authorizes_control_surface_l4 before expensive tests and after all bookkeeping. The latter checks negative-authorization vocabulary across the complete packet. Preserve precise positive existing-PR authority and refer to raw evidence by path rather than pasting historical prose.
6. Run the declared anti-theater-first tool/docs chain through native capture. Use PYTHONHASHSEED=0 and owned system temporary directories outside every checkout for pytest, fixtures and cache. Existing .scratch evidence stays intact; avoid creating scratch logs/backups/custom temp forests.
7. Native PhaseB/commit stages, reviews and commits the narrow repair, runs normal pre-push/CI and merges existing PR1312. Keep root and carrier TASKS/to-do truth synchronized, preserve unrelated PRIMARY WIP and held journals/stashes, and verify PRIMARY sync and carrier closeout. Root writes this STUB only.

## Constraints

- All selected LLM roles Codex gpt-6-astra/max; providerless commit; one native writer.
- Existing row40, branch, carrier and PR1312 only. Preserve the full already-committed R8 implementation. Keep source changes to the two demonstrated blockers; physical cleanup/useful-work landing stays directly next.
- Keep every predecessor bus, receipt, index-history snapshot, attempt counter, stash and journal intact. Fresh native authority belongs to this new bounded continuation; prior exhausted authority remains preserved.
- Required safety, review, pytest, receipt, CI and merge gates remain in force. Preserve real bootstrap failure handling and production retention protections.
- Use system temporary storage outside checkouts and native output capture; no new scratch logs or directories. Any individual non-blocking warning stays non-blocking.

## Stop conditions

- Stop with exact evidence if existing PR/branch target changes, a prior owner is live, packet authority fails, any edit escapes the nine-path scope, preserved work would be lost, or a required gate fails.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -c 'from pathlib import Path; import sys; sys.path.insert(0, str(Path("mu/tools/executors").resolve())); import commit_executor as ce; text=Path("reports/control_plane/workingrcx-pr1312-ci-continuation-r1-2026-09-23_2026-09-23.md").read_text(); assert ce._packet_declares_same_wave_id(text, "workingrcx-pr1312-ci-continuation-r1-2026-09-23"); assert ce._packet_authorizes_control_surface_l4(text); print("Existing-PR packet authorization: PASS")' && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/checks/check_theater_risk_ratchet.py --json && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_recovery_gate.py mu/tests/docs/test_growth_caps.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- Actual failed cleanup test passes under reproduced runner Git configuration; existing lifecycle protections and their tests remain intact.
- Actual captured transcript no longer impersonates a current bootstrap fault, while genuine current faults and finite recovery budgets retain their existing protections.
- Real indexed packet/handoff authorizes caller phase_b on existing PR1312 branch; all required native gates pass and PR1312 merge/PRIMARY sync/carrier closeout are verified.
- All268task IDs/39parked obligations remain; no new PR, carrier or numbered task. Physical cleanup/useful-work obligations remain correctly owned and directly next, then Mu.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-pr1312-ci-continuation-r1-2026-09-23`.
- Governing packet: this file, `reports/control_plane/workingrcx-pr1312-ci-continuation-r1-2026-09-23_2026-09-23.md`.
- TASKS.md authority: the 2026-09-23 tracker sync note for wave `workingrcx-pr1312-ci-continuation-r1-2026-09-23` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-pr1312-ci-continuation-r1-2026-09-23

## Phase B implementation evidence

- Existing branch and HEAD match the locked target and comparison commit.
  The two preserved capture SHA256 values match Work item 2. The unmodified
  cleanup fixture escalated under an injected runner system clean filter;
  the full capture triggered the bootstrap guard while its current CI terminal
  alone cleared it.
- The cleanup fixture now isolates system/global Git configuration at exec and
  exercises all four system/global clean/process combinations with actual
  lifecycle retirement and durable PR ownership. Exposing the ambient filters
  still produces a retained UNKNOWN useful-work inventory without executing them.
- Recovery recognizes the matching native commit/test_failure/wait_ci envelope;
  current diagnostics and CI excerpts retain bootstrap authority. The captured
  successful read and verbatim terminal JSON form a self-contained regression.
  Existing scope/Git-control audits and finite recovery budgets remain intact.
- Packet authorization and anti-theater passed with zero findings/exceptions.
  The required tools/growth gate stopped at 7 failed, 1717 passed in 119.51s.
  Repaired cleanup and recovery cases passed; the docs command short-circuited.
  The measured footprint is 361 test files,
  131 tool scripts and 67 core docs; existing caps 171/63/19 cover it.
  Native indicator collection, indexed handoff, reviews, commit, CI, PR1312 merge,
  PRIMARY sync and operational closeout remain outer-pipeline stages.
- Existing row40 retains all 268 task IDs and 39 parked obligations. Eligible
  physical cleanup/useful-work landing remains directly next, followed by Mu.
  Runtime/substrate source and tracked host-debt surfaces are unchanged.

### Required-gate stop evidence

The declared anti-theater-first command chain exited 1 at its tools/growth
pytest command. All seven failures are in the unchanged
`mu/tests/tools/test_worktree_lifecycle.py`:

- `test_terminal_completion_preserves_lane_history_and_survives_source_absence[success]`
- `test_terminal_completion_preserves_lane_history_and_survives_source_absence[stopped]`
- `test_terminal_completion_preserves_lane_history_and_survives_source_absence[superseded]`
- `test_completion_rechecks_inventory_before_preservation_admission[untracked-stopped]`
- `test_stopped_useful_candidate_retains_exact_landing_owner`
- `test_completed_native_receipt_detects_retired_index_only_drift`
- `test_commit_closeout_and_bridge_config_are_durable_before_retirement[success]`

Five assertions observed ESCALATED instead of COMPLETE with attempts_exhausted=3;
other failures were missing `manifest` and `landing_owner` keys. The native
captured stdout contains the exact short tracebacks at lines 203, 365, 224, 428
and 999 of that unchanged test module. The cause of these failures remains
unresolved. The locked-plan stop condition applies; lifecycle source/tests and
all predecessor evidence remain preserved. The final docs command was skipped
by the chain's `&&` boundary. Validation used PYTHONHASHSEED=0,
PYTHONDONTWRITEBYTECODE=1, four workstealing workers, no pytest cache provider,
and an owned system temporary directory for fixtures and caches outside every
checkout. No scope expansion or gate bypass was performed.

### Bridge round 1 implementation stop

The same declared command chain was executed once during bridge remediation,
with the existing staged source/test repairs intact. Packet authorization and
anti-theater passed again with zero findings/exceptions. Tools/growth exited 1:
**8 failed, 1716 passed in 122.96s**. Docs again short-circuited at the required
`&&` boundary. The repaired cleanup and recovery cases passed. This result
supersedes the earlier run for current validation status; the earlier evidence
above remains historical.

All eight failures are in `mu/tests/tools/test_worktree_lifecycle.py`:

- `test_terminal_completion_preserves_lane_history_and_survives_source_absence[success]`
- `test_terminal_completion_preserves_lane_history_and_survives_source_absence[stopped]`
- `test_terminal_completion_preserves_lane_history_and_survives_source_absence[superseded]`
- `test_completion_rechecks_inventory_before_preservation_admission[index_only-stopped]`
- `test_completion_rechecks_inventory_before_preservation_admission[untracked-success]`
- `test_native_completion_late_index_drift_keeps_explicit_landing_owner`
- `test_stopped_useful_candidate_retains_exact_landing_owner`
- `test_completed_native_receipt_detects_retired_index_only_drift`

Before the owned system temporary directory was removed, six failing fixture
completion receipts and their three attempt results were printed to native
stdout. Each attempt was PENDING with the exact reason
`Active process references target identity`; each completion was ESCALATED
with `attempts_exhausted=3`. These receipts cover terminal stopped/superseded,
both inventory cases, stopped useful work and retired-index verification.
The success and late-index-drift cases retain their captured short tracebacks;
their complete receipts were outside that bounded extraction. The extraction
also printed the expected missing-closeout negative control; it passed and is
excluded from these six failure receipts.

Code inspection identifies the hold at
`mu/tools/executors/workingrcx_fleet_apply.py`: `process_idle` matches the
branch token against every other process command. The lifecycle fixture uses
the same `native-wave` branch for its disposable repositories
(`mu/tests/tools/test_worktree_lifecycle.py`). Interference between workers
is a supported hypothesis; the exact matching processes and candidate causation
remain unresolved. The unchanged test file alone establishes neither causation
nor a pre-existing passing/failing baseline.

The bridge finding remains blocking. The locked scope preserves lifecycle
tests and excludes fleet process-guard changes, so a bounded repair of that
fixture/guard interaction needs fresh outer-pipeline scope authority. This
implementer stopped at the required-gate failure, retained all existing repairs,
and updated only this packet and its two trackers. Same-wave indicator bytes
remain staged. Indexed handoff, remaining review, commit, CI, PR1312 merge,
PRIMARY sync and carrier closeout remain outer-pipeline stages. Physical
cleanup/useful-work landing remains directly next, followed by Mu.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-pr1312-ci-continuation-r1-2026-09-23`
- Active packet: `reports/control_plane/workingrcx-pr1312-ci-continuation-r1-2026-09-23_2026-09-23.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-pr1312-ci-continuation-r1-2026-09-23.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-pr1312-ci-continuation-r1-2026-09-23_2026-09-23.md`
  - `reports/l4_wave_indicators/workingrcx-pr1312-ci-continuation-r1-2026-09-23.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
