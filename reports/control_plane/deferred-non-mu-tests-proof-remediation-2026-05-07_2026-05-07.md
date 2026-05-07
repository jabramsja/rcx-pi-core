# Deferred-Non-Mu Tests Proof Remediation 2026-05-07

Date: 2026-05-07
Status: Routed - Phase A required before implementation
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-non-mu-tests-proof-remediation-2026-05-07
Class: L4_ENABLER
Category: tests/proof-integrity
Phase-A-Lock: UNLOCKED
Source authorization: FOUNDER_OVERRIDE:deferred-non-mu-deferred-lane-truth-sweep-2026-05-07
Governing source packet: reports/control_plane/deferred-non-mu-deferred-lane-truth-sweep-2026-05-07_2026-05-07.md

## Scope

This routed packet groups non-`/mu` test/proof-integrity findings from archived
deferred source packets. It excludes `/mu` structural remediation and excludes
the already-closed W5A re-entry gate coverage packet.

In scope for a future implementation wave:

- Test gaps where an existing test proves prompt, source, or narrow helper
  behavior but not the behavioral claim made by the packet.
- Focused tests for dispatcher/recovery/bridge proof paths when the
  implementation behavior is non-`/mu` control-plane tooling.

Out of scope:

- `/mu` structural runtime, Stage0, parity, seed, or scheduler implementation.
- Already-landed engine-state/scheduler seed, fixture, structural-test,
  scheduler-parity, or seed-registration work from `TASKS.md:433`.
- Claude-related residue.

## Source Findings

- `meta-bridge-taskid-path-safety-2026-04-03_bridge_nonblockers.md`:
  zero-match regression backfill is prompt/gate coverage, not envelope-emission
  coverage.
- `post-merge-verify-fetch-fix-2026-04-11_bridge_nonblockers.md`: updated
  dispatch regression does not directly assert the ff-only merge call.
- `tier-2-auto-retry-tier-3-llm-recovery-loop-2026-03-31_bridge_nonblockers.md`:
  dispatcher/recovery timeout tests stub around live chained-timeout paths and
  miss timeout attribution/sequential-cap behavior.

Closed source excluded from this routed packet:

- `w5a_reentry_gate_coverage.md` is archived as closed because current
  `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py` includes
  `TestPythonBoot1ReentryStepMonotonicity::test_step_monotonic_across_reentry`.

## Work Items

1. Reproduce each test/proof gap against current tests before adding coverage.
2. Add focused tests only for the current non-`/mu` control-plane proof gap.
3. Do not use this packet to implement runtime/tooling behavior unless a test
   cannot be made meaningful without a same-wave mechanical fix; if that occurs,
   split the wave or route back to the tooling packet.
4. Record validation command, exit status, and short evidence summary.

## Stop Conditions

- A fix requires `/mu` structural implementation.
- A fix requires editing Claude-related residue.
- The current tests already prove the claim, making the source finding stale.
- A meaningful test requires broad behavior changes outside this bounded packet.

## Acceptance Criteria

- Every added/updated test directly targets one reproduced proof gap.
- No already-landed engine-state/scheduler work is relisted.
- No `/mu` structural or Claude-related remediation is implemented.
- Validation records include command, exit status, and short evidence summary.

## Grounding / Authorization

Routed by `deferred-non-mu-deferred-lane-truth-sweep-2026-05-07` under
`FOUNDER_OVERRIDE:deferred-non-mu-deferred-lane-truth-sweep-2026-05-07`.
