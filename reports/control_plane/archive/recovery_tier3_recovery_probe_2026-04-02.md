# Recovery Tier 3 Recovery Probe

Date: 2026-04-02
Status: Phase A (design -- probe packet for routed recovery validation)
Phase-A-Lock: UNLOCKED

## Scope

- Exercise dispatcher-routed Phase A failure recovery with a real plan packet.

## Work Items

- Force an SDK preflight failure.
- Verify the dispatcher routes the Phase A failure into Tier 3 recovery.
- Verify the recovery loop records a structured skip for caller-supplied env state.

## Constraints

- No implementation changes should come from this probe packet.

## Stop Conditions

- Stop if the dispatcher bypasses recovery.
- Stop if Tier 3 returns malformed output instead of a structured skip/escalate result.

## Acceptance Criteria

- Dispatcher classifies the forced Phase A SDK failure and enters Tier 3.
- Tier 3 records a bounded skip for `RCX_AGENT_PREFLIGHT_FORCE_FAIL=1`.

## Grounding

- Disposable proof packet for live recovery validation on 2026-04-02.
