# Phase B Implementer Recursive Dispatch Guard

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: phase-b-implementer-recursive-dispatch-guard-2026-05-15
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: dispatcher/control-plane repair
Founder override: FOUNDER_OVERRIDE:phase-b-implementer-recursive-dispatch-guard-2026-05-15

## Scope

- `mu/tools/executors/phase_b_implementer.py`
  - Render outer-pipeline commands from locked plans as inert text before the
    plan is injected into the inner Phase B implementer prompt.
  - Add an explicit Phase B execution boundary telling the implementer that
    dispatcher/executor launch, startup/preflight, attestation, commit, push,
    PR, merge, and closeout commands in locked-plan context are not executable.
- `mu/tests/tools/test_phase_b_executor.py`
  - Add regression coverage proving executable dispatcher and preflight command
    lines are removed from the implementer prompt while the execution boundary
    remains visible.
- `mu/tools/executors/commit_executor.py`
  - Keep synthesized routing-record handoffs from labeling code/test scopes as
    `update_tracker_only`.
- `mu/tools/agents/templates/meta_bridge_task.txt`
  - Tell the meta-reviewer to use the current package JSON and staged diff for
    package-scope authority, not stale `.scratch/*package*.json` residue.
- `mu/tools/agents/meta_bridge_supervisor.py`
  - Mechanically refute a reviewer-only package-scope drift finding when all
    validation gates pass and current package `changed_files` exactly equals
    `git diff --cached --name-only`.
- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tests/tools/test_meta_bridge_supervisor.py`
  - Cover the lane repair and stale scratch-package prompt guard.

## Root Cause Evidence

- Active process readback showed an outer dispatcher and Phase B executor:
  `40340 executor_dispatch.py` -> `40393 phase_b_executor.py` -> `40537 codex`.
- The same process readback showed an inner dispatcher launched beneath that
  implementer Codex process: `40537 codex` -> `30664 executor_dispatch.py` ->
  `30786 phase_b_executor.py`.
- The routed N3 packet at
  `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md:320-326`
  contains an executable dispatcher launch command under `Pipeline Requirement`.
- The Phase B implementer raw output at
  `.scratch/phase_b_implementer_output_impl-feab4abb.txt:79-80` recorded the
  implementer saying it was rerunning the locked dispatcher command, followed by
  a tool call for `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --loop --max-waves 1 --json`.
- Code readback before this repair showed `build_implementation_prompt(...)`
  injected the locked plan directly into the implementer prompt. The executable
  command was therefore reachable by the inner implementer instead of remaining
  an operator-facing outer-pipeline instruction.

## Mechanical Fix

`phase_b_implementer.py` now sanitizes the locked plan before prompt assembly.
Executable lines for the outer dispatcher/executors, founder startup/attest
commands, and `codex-rcx-preflight` are replaced with a placeholder:

```text
[outer-pipeline command omitted from Phase B implementer prompt]
```

The prompt also contains a Phase B execution boundary that marks locked-plan
pipeline launch, startup/preflight, attestation, commit, push, PR, merge, and
closeout commands as non-executable context for the inner implementer.

This is a pipeline-control repair only. It does not implement `/mu` runtime
semantics, does not add Python or JavaScript core semantics, and does not
authorize host-debt expansion.

## Commit-Path Follow-up Repair

The first commit-executor attempt failed closed in pre-commit supervisor review.
The direct supervisor envelope said the package lane was `update_tracker_only`
while staged scope included control-plane code and tests. That lane criticism was
correct: the operator handoff used an `UPDATE_TRACKER_ONLY` routing decision for
a code/test repair. `commit_executor.py` now keeps true tracker/report-only
handoffs in `update_tracker_only` and labels code/test routing-record handoffs as
`phase_b`.

The same supervisor envelope also claimed the package carried
`mu/tools/executors/phase_b_executor.py`. Direct readback of
`.scratch/auto_supervisor_package.json` and `git diff --cached --name-status`
showed the current package/staged diff contained the same five files and did not
include `phase_b_executor.py`. The matching stale file was
`.scratch/pre_commit_supervisor_package.json`, so the meta-reviewer prompt now
forbids treating other `.scratch/*package*.json` files as current package
authority.

The retry still produced the same stale package-scope reviewer claim after the
reviewer directly ran `git diff --cached --name-status -- mu/tools/executors/phase_b_executor.py`
and got empty output. `meta_bridge_supervisor.py` now treats this exact class of
reviewer-only package drift claim as mechanically refutable only when all
validation gates pass and the current package file list exactly equals the
current staged diff path list.

## Validation

```text
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestBuildImplementationPrompt --tb=short
```

Result: exit `0`; `11 passed in 0.05s`.

```text
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_prepare_handoff_update_tracker_only_code_scope_uses_phase_b_lane mu/tests/tools/test_meta_bridge_supervisor.py::TestTemplateValidationFailureRouting::test_prompt_includes_bounded_review_contract mu/tests/tools/test_meta_bridge_supervisor.py::TestTemplateValidationFailureRouting::test_reviewer_package_scope_false_positive_guard_requires_exact_staged_match --tb=short
```

Result: exit `0`; included in `14 passed in 0.30s` with the Phase B prompt regression.

## Retry Boundary

After this repair is committed and merged through the pipeline, retry the N3
runtime wave with the existing canonical route:

```text
python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --loop --max-waves 1 --json
```

The retry must continue to obey the N3 packet: implementation must be pipeline
owned, must narrow/remove host semantics rather than add them, and must not turn
Mu into a Python/JavaScript simulation.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-implementer-recursive-dispatch-guard-2026-05-15`
- Active packet: `reports/control_plane/phase-b-implementer-recursive-dispatch-guard-2026-05-15.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `1b62903f4b62afcc80ac4fe7abb7ee57f8d57779886e508cadc69e21fedfc711`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-implementer-recursive-dispatch-guard-2026-05-15.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestBuildImplementationPrompt mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_prepare_handoff_update_tracker_only_code_scope_uses_phase_b_lane mu/tests/tools/test_meta_bridge_supervisor.py::TestTemplateValidationFailureRouting::test_prompt_includes_bounded_review_contract mu/tests/tools/test_meta_bridge_supervisor.py::TestTemplateValidationFailureRouting::test_reviewer_package_scope_false_positive_guard_requires_exact_staged_match --tb=short`.
- Evidence delta: (1) Active process readback showed the inner implementer launched `executor_dispatch.py` beneath the outer Phase B Codex process. (2) The routed N3 packet contains an executable dispatcher launch at `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md:320-326`, and the implementer raw output recorded that command being rerun from inside Phase B. (3) `phase_b_implementer.py` now renders outer-pipeline launcher/startup command lines inert before injecting locked-plan text into the inner implementer prompt. (4) The commit handoff builder now labels code/test routing-record scopes as `phase_b` instead of `update_tracker_only`, the meta-review prompt forbids stale `.scratch/*package*.json` files as current package authority, and the supervisor mechanically refutes reviewer-only package-scope drift claims when Gate 1 plus current staged-name readback prove package/staged equality.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-implementer-recursive-dispatch-guard-2026-05-15.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/agents/templates/meta_bridge_task.txt`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_implementer.py`
  - `reports/control_plane/phase-b-implementer-recursive-dispatch-guard-2026-05-15.md`
  - `reports/l4_wave_indicators/phase-b-implementer-recursive-dispatch-guard-2026-05-15.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
