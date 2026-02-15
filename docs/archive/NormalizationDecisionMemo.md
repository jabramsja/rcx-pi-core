# Normalization Strategy Decision Memo (v0)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document is a DECISION MEMO only. It authorizes proceeding to Gate 1.

Status: decision memo only. This is intentionally short and precedes a full spec.

## Decision
Adopt a single, canonical normalized state format for algorithm projections and refactor recurrence/exhaustion (and rcx_engine orchestration) to operate on that normalized format. Structural match/subst remain the only execution path for algorithms once refactor is complete.

## Context
Algorithm projections currently rely on a custom state shape, while structural match/subst normalize all input into linked-list Mu form. This mismatch forces a hybrid execution path that uses Python match/subst for algorithms. The mismatch is the blocker to true meta-circular algorithm execution.

## Rationale
1. One canonical representation eliminates dual execution paths and drift.
2. Structural honesty improves because algorithm logic stays in projections, not host code.
3. Long-term maintenance is simpler with a single structural substrate and shared parity vectors.

## Consequences
1. Requires refactoring recurrence/exhaustion state machines to the normalized form.
2. Requires updates to parity vectors, execution-path verification tests, and spec mapping.
3. Requires explicit migration plan and temporary adapters during the transition.

## Alternatives Considered
1. Normalization-free structural matcher for algorithm execution. Rejected because it adds a second matcher with long-term maintenance and drift risk.
2. Permanently accept bootstrap-only algorithm execution. Rejected because it blocks true meta-circular execution and undermines structural purity claims.

## Next Step
Write the full normalization spec (Gate 1) with concrete normalized state examples for recurrence and exhaustion. This memo is the authorization to proceed.
