# Deferred-Non-Mu Tests Proof Remediation 2026-05-07

Date: 2026-05-07
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-non-mu-tests-proof-remediation-2026-05-07
Class: L4_ENABLER
Category: tests/proof-integrity
Phase-A-Lock: LOCKED
Source authorization: FOUNDER_OVERRIDE:deferred-non-mu-tests-proof-remediation-2026-05-07
Governing packet: reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md
Routing source packet: reports/control_plane/deferred-non-mu-deferred-lane-truth-sweep-2026-05-07_2026-05-07.md

## Scope

This routed packet is a Phase A plan for the non-`/mu`
tests/proof-integrity gaps authorized by `TASKS.md:471`. It does not itself
prove that every routed gap remains unlanded; Phase B must reproduce each gap
against current code before adding or changing tests.

Files and directories in scope for this packet:

- `reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`
  for this Phase A plan.
- `TASKS.md:471` carrying the `[NEXT-CODEX-POST-REDTEAM]` tracker sync note
  for `deferred-non-mu-tests-proof-remediation-2026-05-07`.
- `reports/archive/deferred/meta-bridge-taskid-path-safety-2026-04-03_bridge_nonblockers_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`
  as the routed source for the meta-bridge envelope-emission proof gap.
- `reports/archive/deferred/post-merge-verify-fetch-fix-2026-04-11_bridge_nonblockers_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`
  as the routed source for the ff-only merge assertion proof gap.
- `reports/archive/deferred/tier-2-auto-retry-tier-3-llm-recovery-loop-2026-03-31_bridge_nonblockers_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`
  as the routed source for the recovery timeout path coverage proof gap.
- `mu/tests/tools/` for focused control-plane tests that prove dispatcher,
  recovery, post-merge, bridge, or related executor behavior. These tests are
  in scope only as non-structural control-plane tooling coverage.
- `mu/tools/executors/` only for reading the behavior under test or for a
  same-wave mechanical fix if a meaningful test cannot be written against the
  current executor behavior.

Closed source excluded from pending work:

- `reports/archive/deferred/w5a_reentry_gate_coverage_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`
  is not pending in this packet because `TASKS.md:471` records it as archived
  closed by current `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`
  re-entry step-monotonicity coverage.

## Work Items

1. Meta-bridge envelope emission:
   Reproduce whether existing tests prove the envelope-emission behavior routed
   from `meta-bridge-taskid-path-safety-2026-04-03_bridge_nonblockers`. If the
   gap remains live, add or update one focused test under `mu/tests/tools/`
   that asserts the envelope emission itself, not only prompt, source, helper,
   or gate text around the zero-match path.

2. FF-only merge assertion:
   Reproduce whether existing tests directly assert the ff-only merge call
   routed from `post-merge-verify-fetch-fix-2026-04-11_bridge_nonblockers`. If
   the gap remains live, add or update one focused post-merge/control-plane test
   under `mu/tests/tools/` that observes the merge invocation and proves the
   ff-only argument or equivalent ff-only contract is used.

3. Recovery timeout path coverage:
   Reproduce whether existing dispatcher/recovery tests exercise the live
   chained timeout path routed from
   `tier-2-auto-retry-tier-3-llm-recovery-loop-2026-03-31_bridge_nonblockers`.
   If the gap remains live, add or update one focused test under
   `mu/tests/tools/` that covers timeout attribution and sequential-cap behavior
   without stubbing around the live timeout chain.

4. Stale-gap handling:
   If current code or tests already prove one of the three routed claims, do
   not relist that claim as unresolved. Record the reproduced stale/closed
   result in the implementation evidence and keep pending work items and
   acceptance criteria limited to still-live gaps.

5. Validation evidence:
   Record each reproduction command, each focused validation command, exit
   status, and a short evidence summary naming the proved or retired gap.

## Constraints

- Do not implement `/mu` structural runtime, Stage0, parity, seed, scheduler,
  registry, or production behavior.
- Do not edit Claude-related residue.
- Do not relist already-landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work.
- Do not reopen the closed W5A re-entry gate coverage source.
- Do not use this packet for broad dispatcher, recovery, bridge, commit,
  runner, observability, or control-plane tooling remediation outside the three
  tests/proof gaps named in `TASKS.md:471`.
- Do not treat prompt/source/helper-only assertions as sufficient proof for
  behavioral claims about envelope emission, ff-only merge invocation, or live
  recovery timeout behavior.

## Stop Conditions

- A fix requires `/mu` structural implementation.
- A fix requires editing Claude-related residue.
- Current tests already prove all three routed claims, making the pending
  implementation work stale.
- A meaningful test for any still-live gap requires broad behavior changes
  outside the scoped control-plane files/directories.
- A gap resolves only by changing unrelated tooling surfaces instead of adding
  or updating focused proof coverage.

## Acceptance Criteria

- Scope remains limited to the concrete files/directories listed above.
- Each of the three `TASKS.md:471` routed gaps is either reproduced as live with
  focused proof coverage or explicitly retired as stale because current code or
  tests already prove the claim.
- Every added or updated test directly targets one live reproduced proof gap:
  meta-bridge envelope emission, ff-only merge invocation, or recovery timeout
  path attribution/sequential-cap behavior.
- No prompt/source/helper-only test is accepted as proof of a routed behavioral
  claim.
- No already-landed engine-state/scheduler work is relisted.
- No `/mu` structural or Claude-related remediation is implemented.
- Validation records include command, exit status, and short evidence summary.
- The closed W5A re-entry gate coverage source remains excluded from pending
  work.

## Grounding / Authorization

`TASKS.md:471` authorizes this `[NEXT-CODEX-POST-REDTEAM]` L4_ENABLER packet:
`deferred-non-mu-tests-proof-remediation-2026-05-07`, category
`tests/proof-integrity`, packet
`reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`.

Authorization: FOUNDER_OVERRIDE:deferred-non-mu-tests-proof-remediation-2026-05-07

Governing packet:
`reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`.

Routing source packet:
`reports/control_plane/deferred-non-mu-deferred-lane-truth-sweep-2026-05-07_2026-05-07.md`.

## Phase B Implementation Evidence

Implemented: 2026-05-07

### Reproduction

1. Meta-bridge envelope emission:
   - Command:
     `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_meta_bridge_supervisor.py::TestZeroMatchProbeTemplateGuidance::test_template_warns_against_set_e_pipefail mu/tests/tools/test_agent_bridge_supervisor.py::test_run_adapter_stop_after_meta_envelope_uses_raw_transcript_fallback`
   - Exit status: 0.
   - Evidence summary: existing coverage proved prompt guidance and generic
     meta-envelope capture, but did not run a zero-match probe before the final
     envelope. The proof gap remained live.

2. FF-only merge assertion:
   - Command:
     `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestCommitContinuationAndBotFreshness::test_post_commit_uses_linked_base_worktree_for_merge_verification`
   - Exit status: 0.
   - Evidence summary: existing coverage reached the linked-base verify path,
     but the test only accepted the `git merge --ff-only` branch and asserted
     CWD/fetch behavior; it did not record the merge argv. The proof gap
     remained live.

3. Recovery timeout path coverage:
   - Command:
     `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_sequential_recovery_preserves_original_timeouts mu/tests/tools/test_recovery_gate.py::TestAttemptRecovery::test_distinct_executor_timeouts_separate_buckets`
   - Exit status: 0.
   - Evidence summary: existing coverage proved direct recovery attribution and
     dispatcher override restoration with mocked dispatcher/recovery results,
     but did not exercise the live chained Phase A to Phase B timeout path. The
     proof gap remained live.

### Implemented Proof Coverage

1. Meta-bridge envelope emission:
   `mu/tests/tools/test_agent_bridge_supervisor.py::test_run_adapter_meta_envelope_survives_zero_match_probe`
   now runs a local adapter subprocess that observes a zero-match-style
   nonzero probe result, emits a final `BEGIN_META_ENVELOPE` block, and proves
   the adapter returns that envelope before the lingering process can hang the
   supervisor path.

2. FF-only merge assertion:
   `mu/tests/tools/test_executor_dispatch.py::TestCommitContinuationAndBotFreshness::test_post_commit_uses_linked_base_worktree_for_merge_verification`
   now records the post-merge verification merge command and asserts the exact
   `["git", "merge", "--ff-only", "origin/dev"]` argv.

3. Recovery timeout path coverage:
   `mu/tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_chained_phase_b_live_timeout_attribution_and_cap`
   now drives `_continue_successful_executor_chain()` through a real timed-out
   Phase B subprocess, then proves the missing-step timeout is attributed to
   the `phase_b_executor` recovery bucket and that sequential timeout recovery
   caps at 2x the original baseline before exhaustion.

### Validation

1. Command:
   `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_bridge_supervisor.py::test_run_adapter_meta_envelope_survives_zero_match_probe`
   - Exit status: 0.
   - Evidence summary: zero-match adapter emission proof passed.

2. Command:
   `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestCommitContinuationAndBotFreshness::test_post_commit_uses_linked_base_worktree_for_merge_verification`
   - Exit status: 0.
   - Evidence summary: ff-only merge argv proof passed.

3. Command:
   `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_chained_phase_b_live_timeout_attribution_and_cap`
   - Exit status: 0.
   - Evidence summary: live chained timeout attribution and sequential-cap
     proof passed.

4. Command:
   `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_bridge_supervisor.py::test_run_adapter_meta_envelope_survives_zero_match_probe mu/tests/tools/test_executor_dispatch.py::TestCommitContinuationAndBotFreshness::test_post_commit_uses_linked_base_worktree_for_merge_verification mu/tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_chained_phase_b_live_timeout_attribution_and_cap`
   - Exit status: 0.
   - Evidence summary: all three focused Phase B proof tests passed together
     with `3 passed in 1.99s`.

5. Command:
   `git diff --check -- mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_executor_dispatch.py reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`
   - Exit status: 0.
   - Evidence summary: no whitespace errors in the scoped Phase B diff.

6. Command:
   `python3 mu/tools/checks/linters/check_private_attr_access.py mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_executor_dispatch.py`
   - Exit status: 0.
   - Evidence summary: focused private-helper test access remains annotated
     and accepted by the repo linter.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `deferred-non-mu-tests-proof-remediation-2026-05-07`
- Active packet: `reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`
- Indicator artifact: `reports/l4_wave_indicators/deferred-non-mu-tests-proof-remediation-2026-05-07.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`
  - `reports/l4_wave_indicators/deferred-non-mu-tests-proof-remediation-2026-05-07.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `deferred-non-mu-tests-proof-remediation-2026-05-07`
- Active packet: `reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `83a5f36164da3d3ec2a9f65ec03484356291eda97366ed5d1c96f8163cc09fb8`
- Indicator artifact: `reports/l4_wave_indicators/deferred-non-mu-tests-proof-remediation-2026-05-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/deferred-non-mu-tests-proof-remediation-2026-05-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`
  - `reports/l4_wave_indicators/deferred-non-mu-tests-proof-remediation-2026-05-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
