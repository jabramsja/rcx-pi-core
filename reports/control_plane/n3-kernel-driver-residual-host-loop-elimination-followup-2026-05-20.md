# N3-Kernel-Driver-Residual-Host-Loop-Elimination-Followup-2026-05-20

Date: 2026-05-20
Status: QUEUED / PHASE A REQUIRED
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20
Class: L4_STRUCTURAL
Category: /mu structural host-semantics reduction
Target gate: G8
Phase-A-Lock: UNLOCKED
Source authorization: `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]` plus the bounded split from `n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20`

## Purpose

Plan the remaining structural step after the bounded fuel-loop narrowing wave.
The current implementation makes supplied Mu linked-list fuel own progress in
both kernel drivers, but the no-fuel compatibility path still needs a host loop
watchdog. This packet must decide whether that residual loop can be eliminated
without moving authority into a helper, recursion, host iterator abstraction, or
substrate-specific behavior.

## Scope

- `mu/host/js/engine/kernel.js::_stepKernelCore`
- `mu/host/python/rcx_pi/selfhost/step_mu.py::step_kernel_mu`
- Focused parity/structural tests that prove the same residual contract in both
  substrates
- Ratchet and host-authority inventory evidence

## Required Phase A questions

1. Can legacy no-fuel callers be made to supply explicit Mu fuel at the public
   boundary without breaking Python/JS API parity?
2. If implicit fuel is required for compatibility, can that fuel be represented
   as existing Mu data without host-counted construction becoming the semantic
   progress owner?
3. Can the residual loop be removed from the two target functions without
   adding a new authority site, recursion signal, or unaccepted authority
   inventory split?
4. What focused gate fails if `maxSteps` / `max_steps` becomes semantic progress
   authority again?

## Stop conditions

- The proposed fix moves the loop into a new helper, recursion, array method,
  iterator abstraction, or substrate-specific primitive without reducing host
  authority.
- Python and JavaScript would diverge in accepted inputs, fuel behavior,
  metadata fields, or failure modes.
- Host-authority inventory would require a new unreviewed split allowance.
- The wave cannot prove marker elimination as structural reduction rather than
  marker movement.

## Acceptance criteria

- Either both residual `@host_iteration` kernel-driver sites are eliminated with
  no new authority site, or Phase A produces a smaller locked implementation
  packet with explicit residual gates and proof limits.
- Ratchet evidence distinguishes real marker reduction from marker movement.
- Host-authority inventory evidence shows no unaccepted total or authority-site
  increase.
- Python/JS focused parity proves identical KernelRunResult behavior for
  supplied fuel, empty fuel, no-fuel compatibility if retained, and watchdog
  exhaustion.

## Non-authorization

This packet is not Phase B authorization. It must be locked by Phase A and
paired with a detector-visible `TASKS.md` tracker entry before implementation.
