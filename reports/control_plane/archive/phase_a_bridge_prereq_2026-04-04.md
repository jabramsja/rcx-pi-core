# Phase A Bridge Prerequisite Fix

Date: 2026-04-04
Status: Local proof complete; routed closeout pending
Phase-A-Lock: UNLOCKED
Task: [PIPELINE-RECOVERY/phase-a-bridge-prereq-2026-04-04]
Wave ID: phase-a-bridge-prereq-2026-04-04

## Scope

Repair the smallest Phase A control-plane defect that is currently blocking the
authorized routed observability wave from entering a real bridge review:

1. stop passing the removed `--packet-review` flag to `bridge_supervisor.py`
2. make the Phase A findings parser ignore the prompt's example envelope and
   use the real reviewer envelope instead

This is a prerequisite control-surface fix, not a new feature wave.

## Trigger

Live routed replay of the clean observability wave in
`/private/tmp/workingrcx_obs_split.YYYYYY` failed before honest review:

- dispatcher launched `phase-a`
- Phase A reached bridge review
- bridge subprocess exited immediately with
  `bridge_supervisor.py: error: unrecognized arguments: --packet-review`

The same mixed replay history also exposed a second Phase A truth bug:

- when a bridge prompt included the template `BEGIN_AGENT_ENVELOPE` example
  before the reviewer's real envelope, `_parse_phase_a_findings()` could read
  the fake schema block and miss the actual blocking findings

## Changed surfaces

- `mu/tools/executors/phase_a_executor.py`
- `mu/tests/tools/test_executor_dispatch.py`

## Proof points

1. `run_bridge_design_review()` now launches bridge review with `--no-diff`
   only, matching the current `bridge_supervisor.py review` CLI contract.
2. `_parse_phase_a_findings()` now scans all envelope blocks, skips schema-like
   template envelopes whose `decision` field is a pipe-delimited placeholder,
   and keeps the last real reviewer envelope.
3. Regression coverage now proves both the bridge command shape and the
   template-envelope parsing trap directly.
4. This wave does not widen Phase A semantics beyond the minimum needed to
   unblock routed proof of the already-authorized observability wave.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q --tb=short -k 'test_phase_a_bridge_review_does_not_pass_removed_packet_review_flag or test_parse_phase_a_findings_ignores_template_envelope_and_uses_real_reviewer_envelope'`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; control-plane only
