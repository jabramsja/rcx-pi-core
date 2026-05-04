# Mu Preproduction Red-Team

Date: 2026-05-04
Status: QUEUED (blocked on deferred-findings-fix-sweep-2026-05-04)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: mu-preproduction-redteam-2026-05-04
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Target gate: G8
FOUNDER_OVERRIDE:mu-preproduction-redteam-2026-05-04

## Purpose

Run a full code-truth red-team of `/mu` before production-forward movement.
This is a production gate, not a documentation sweep.

## Scope

Required audit surfaces:

- `mu/host/python/`
- `mu/host/js/`
- `mu/tools/compilers/`
- Stage0, lowering, and runtime execution paths under `mu/`
- seed JSON programs and registry/load paths under `mu/programs/` and related
  loader surfaces
- `/mu` parity, structural, L4, and runtime tests
- `/mu` tooling that claims to enforce runtime, parity, Stage0, seed, or
  production gates
- `/mu` docs that make current-state, production, Stage0, parity, or L4 claims

## Work Items

1. Inventory production-critical `/mu` execution paths across Python, JavaScript,
   Stage0/lowering, seeds, registries, and test gates.
2. Compare Python and JavaScript authority for every current production or
   parity claim.
3. Red-team Stage0, lowering, seed execution, host-boundary, and fail-closed
   behavior for host-smuggling, bypasses, dead gates, or proof-class mismatch.
4. Red-team tests for theater: source-lock-only checks claiming behavioral
   proof, smoke tests that do not exercise the live path, and parity gates that
   do not prove both substrates.
5. Red-team tooling and docs for production claims that are not backed by code
   and tests.
6. Write blockers to `reports/deferred/blocking/` and non-blockers to
   `reports/deferred/non_blocking/` with direct file:line or command evidence.
7. If a bounded fix is obvious and low-risk, implement it only when it does not
   compromise the audit; otherwise route the finding into the correct deferred
   lane for a follow-up implementation packet.

## Constraints

- Do not accept documentation as proof of runtime behavior.
- Do not treat green broad checks as closure unless the check exercises the
  claimed live path with the right proof class.
- Do not move production forward while red-team blockers remain unresolved.
- Do not collapse non-blockers into blockers or blockers into non-blockers
  without severity and production-risk evidence.

## Stop Conditions

Stop and report immediately if:

1. A production-critical runtime path is missing behavioral proof on a claimed
   live substrate.
2. Python/JavaScript parity authority diverges for a production claim.
3. Stage0/lowering/seed execution relies on hidden host semantics that the
   current docs or gates claim have been reduced.
4. A test or tool claims a production gate but can pass without exercising the
   claimed invariant.

## Acceptance Criteria

- Every required audit surface is either inspected or explicitly listed as
  blocked with why it could not be inspected.
- Findings include concrete file:line or command evidence.
- Blockers are written under `reports/deferred/blocking/`.
- Non-blockers are written under `reports/deferred/non_blocking/`.
- TASKS/report indexes identify whether production-forward movement is blocked.
- Validation includes targeted runtime/parity/test commands selected from the
  findings, docs consistency, and L4/current-state checks where claims touch L4,
  Stage0, or production state.
