# Preserve structured pytest cleanup HOLD across cancellation and transport

Date: 2026-10-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR]
Wave ID: workingrcx-native-pytest-execution-r3-2026-10-14
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: f09ba76f22802b0690ba80ab95403ea74669c9b76a9c43dc4532d8607fdbe7b4
Purpose: Authorized control-surface L4_ENABLER under existing native repair owner. Correct reproduced cancellation/exception loss of machine-readable pytest cleanup HOLD before standalone/delegated recovery, retaining bounded runner policy, complete validation and all ownership guards.

## Scope

Structured cancellation cleanup HOLD through runner, public Phase B and hybrid recovery consumers; control/test/doc changes only.

Files and surfaces in scope:

- TASKS.md -- owned native execution, hybrid validation or governance evidence
- CHANGELOG.md -- owned native execution, hybrid validation or governance evidence
- mu/tools/executors/phase_b_executor.py -- owned native execution, hybrid validation or governance evidence
- mu/tests/tools/test_phase_b_executor.py -- owned native execution, hybrid validation or governance evidence
- mu/tests/docs/test_growth_caps.py -- owned native execution, hybrid validation or governance evidence
- reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_2026-10-14.md -- owned native execution, hybrid validation or governance evidence
- reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_implementation_evidence.json -- owned native execution, hybrid validation or governance evidence
- reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json -- owned native execution, hybrid validation or governance evidence
- reports/deferred/non_blocking/workingrcx-native-pytest-execution-r3-2026-10-14_bridge_nonblockers.md -- owned native execution, hybrid validation or governance evidence
- mu/tools/executors/recovery_gate.py -- owned native execution, hybrid validation or governance evidence
- mu/tests/tools/test_recovery_gate.py -- owned native execution, hybrid validation or governance evidence
- TASKS.md -- tracker-sync authority. The 2026-10-14 tracker sync note for wave `workingrcx-native-pytest-execution-r3-2026-10-14` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Existing [NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR] owner; FOUNDER_OVERRIDE:workingrcx-native-pytest-execution-r3-2026-10-14. Fresh canonical branch jabramsja/workingrcx-native-pytest-execution-r3-2026-10-14. Fresh canonical branch jabramsja/workingrcx-native-pytest-execution-r3-2026-10-14, comparison parentb75972546901e3a09e08047f1a10c7684bf875bd, PRIMARY tracker SHA256e3c0aa82b5d3448738e0ba0d5b93900528b1cfe7c990d733097615518f0b15f9, admission/Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/native-pytest-execution-r3-admission; live roles/pager{'implementer': 'codex', 'reviewer': 'codex'}/codex; terminal preservation08a2fa66dcfb5a0e9ae83bc6982a1fda89870caeae6a635b4a2374b9b4be3c32.. PredecessorR2 is terminal with exhausted native reentry; preserve that state and never replay or reset it.
2. Phase-B-Launch-Tracker-Restore: required=true; producer=launch_wave.py; version=1
3. Read terminal recovery manifest /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/native-pytest-execution-r2-terminal-preserved/preservation.json and latest public supervisor envelope in /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.scratch/worktrees/native-pytest-execution-r2-20261014/.agent_bus-native-pytest-execution-r2-20261014/meta/raw/meta-[NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR]-8640c186--r1-meta.txt, or its independently restored counterpart. Before changing code reproduce the exact two standalone cancellation failures using real pytest workers/children and failed/partial OS observations. Supervisor reported2failed2.75s: exception carries HOLD prose only, main transports traceback without pytest_result.cleanup_status, learned recovery/fix each runonce while8worker-childPIDs are alive. Retain all reproduction commands/output/hashes and actual process cleanup backstops.
4. Native implementer carries only four independently restored R2 code/test donors after comparing original/restored SHA/mode and b759 baseline path bytes against the fresh actual parent. Keep bounded4workers/worksteal/no-worker-restart, maxfail0, complete module/node selection, configured-failfast coverage, default/ci_fast profiles, deterministic seed, marker semantics, bounded64KiB head-tail diagnostics, typed timeout and process ownership. Never copy old TASKS/CHANGELOG/index/packet/evidence/indicator/receipt/checkpoint authority wholesale.
5. Correct run_pytest_on_files interrupted execution with unverified cleanup so its terminalHOLD survives exceptions and public main result serialization. Use an explicit typed/structured producer-consumer contract rather than matching incidental HOLD prose or traceback strings. Preserve underlying diagnostic output and checkpoint/release evidence; no caller may reinterpret unverified cleanup as successful recovery or continue through learning, fixes, state/budget updates or another actor.
6. Exercise both standalone public main and delegated recovery validator consumers, including actual traceback/exception transport. Preserve failed/partial-query cancellations and verified-release controls. Cover timeout, KeyboardInterrupt/cancellation, producer errors and delegate validation exceptions as applicable. If cleanup release cannot be verified, return terminal structured refusal without new mutation, actors, budget consumption or checkpoint clearing.
7. Keep untrusted diagnostic/prompt examples and provider envelopes containing HOLD text from becoming authority. Retain canonical/inline/private/QUESTION/in-flight/reentry/commit-ready/legacy guards, consumed tracker restoration and latest finding/source/index/launch bindings. Existing one-cycle/exhaustion boundaries must not be disabled or increased to avoid another refusal.
8. Preserve stabilized positive fixture premises: coherent fresh real OS snapshots through late positive consumers; keep disposable pytest controller alive for owned termination where positive release is expected. Raw failed/partial/changed-ancestry/exited-controller controls must still HOLD. Real ownership checks, signals, fresh absence checks and worker/child heartbeats remain actual; no fake positive release, marker stripping, production query weakening or assertion deletion.
9. First run focused reproduced cancellation producer-consumer controls and scoped unchanged test-integrity; then the exact complete declared PhaseB/recovery gate. Do not rerun an unchanged long full baseline or shrink test selection. Preserve every prior/new failure and fixture correction; passing later runs do not establish the historical30s timeout cause.
10. Update owned evidence and tracker with actual command results, exit codes, current source hashes and stage. Reconcile actual PRIMARY outside exact captured Ra, retain268IDs/44orderedowners/history and all held sources/transactions/stashes/linkeddev/lifecycle obligations. Old approvals describe old candidates only. Native outer owns staging/L4/Step5e/freshCOMMIT_GO/prepush/current-head CI/review/merge/separatePRIMARYsync.
11. Keep existing UUID93064AFA-816D-43E3-BCC9-8A514F8F3D7D recovery store/credentials handling; recovery evidence belongs under verifiedWD WorkingRCX-Recovery/reviews, active development stays local. No live archive purge/source retirement/historical-code reconciliation, Claude files, provider/model/access/hook/binary/backup changes.
12. After ACTUAL nativeR3 landing, separately verified PRIMARY sync and released lane, admit fresh retention integration with complete actualcapacity/restore proof, then Mu, monitor and complete original1330/1329/1325 52pathcoverage plus PR1335native disposition. Preserved work is not merged work; old4f CI never approves newer source. Questions? Concerns? Thoughts? -- Think hard
13. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/native-pytest-execution-r3-admission/carry-forward-sources.json and verify four original/restored SHA/mode/base matches before native carry. Native actor owns carry of all four source/test inputs then structured cancellation transport repair; no old root/private authority transfer.
14. Read exact captured /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/native-pytest-execution-r3-admission/PRIMARY-TASKS.md and preserve Ra. New commands/every failed attempt belong under/Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/workingrcx-native-pytest-execution-r3-2026-10-14-phase-b and own implementation evidence. No whole tracker or held stash replay; native actors own product edits/staging/caps/commit/push/merge.

## Constraints

- No runtime, seed, JS/Python semantic or compiled-bundle changes. No old Task/Changelog wholesale copy, historical code reconciliation, live archive purge or source retirement.
- Preserve all current native retry, canonical/inline, private, QUESTION, in-flight implementer, reentry, commit-ready and legacy guard ownership.
- Do not recapture or restore consumed tracker authority. Preserve valid checkpoints and launch evidence on uncertainty and refusal.
- Keep active development local under main WorkingRCX; recovery evidence/review restores on UUID93064AFA-816D-43E3-BCC9-8A514F8F3D7D via existing access wrapper. No credential inspection or production-store mutation from fixtures.
- No manual Step5e/cap changes; native commit collector remains authority.
- Outer pipeline owns commit/push/review/merge/PRIMARY sync. Declared baseline/candidate module tests are Phase B-local; do not invoke broad pre-push or commit governance inside implementation.
- No frozen authority/old receipt replay, validation weakening, global/inner timeout increases, model/access change or shell safety-guard bypass.

## Stop conditions

- Hold on source/base/branch/config/candidate authority drift, concurrent mutations, provider capacity stop or exhausted native recovery.
- Hold every late continuation on uncertain process observation, missing ownership/release proof or invalid checkpoint/source/index/launch/restore binding.
- Stop dependent retention admission until actual query-proof repair/review/landing/sync and released ownership. No data retirement from age alone.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal -p no:cacheprovider --import-mode=importlib mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py --tb=short --durations=20`

## Acceptance criteria

- Actual real-process standalone/delegate cancellation and exception transport retains terminal structured cleanupHOLD on failed/partial observations; no learning/fixes/budget/state/actors and protected source/index/checkpoint unchanged. Verified-release controls remain valid.
- Complete declared two-module gate and independent native governance/current-head CI/review succeed before actual merge/separate PRIMARY sync. Prior3089-test receipts describe pre-fix source only.
- Four donor inputs verified; all old exhausted authority/held sources and later retention/capacity/Mu/monitor/PR obligations remain preserved/open.

## Grounding / Authorization

- Task: [NATIVE-STUB-PHASE-B-SAME-CONFIG-RELAUNCH-REPAIR]; wave id `workingrcx-native-pytest-execution-r3-2026-10-14`.
- Governing packet: this file, `reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_2026-10-14.md`.
- TASKS.md authority: the 2026-10-14 tracker sync note for wave `workingrcx-native-pytest-execution-r3-2026-10-14` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-native-pytest-execution-r3-2026-10-14

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-native-pytest-execution-r3-2026-10-14`
- Active packet: `reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_2026-10-14.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_2026-10-14.md`
  - `reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-native-pytest-execution-r3-2026-10-14 --output reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal -p no:cacheprovider --import-mode=importlib mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py --tb=short --durations=20`.
- `evidence_delta`: Admission states expected behavior only. Record actual pre-fix reproductions and post-fix commands, source hashes, return codes and limitations in owned implementation evidence. No retroactive test or merge claim..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-native-pytest-execution-r3-2026-10-14.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-native-pytest-execution-r3-2026-10-14`
- Active packet: `reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_2026-10-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `21716eca0e92b679652b7451b073b3912c432171cdc1238b2774a664a78a94e6`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal -p no:cacheprovider --import-mode=importlib mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py --tb=short --durations=20`.
- Evidence delta: Admission states expected behavior only. Record actual pre-fix reproductions and post-fix commands, source hashes, return codes and limitations in owned implementation evidence. No retroactive test or merge claim..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_2026-10-14.md`
  - `reports/control_plane/workingrcx-native-pytest-execution-r3-2026-10-14_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-native-pytest-execution-r3-2026-10-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
