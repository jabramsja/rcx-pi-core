# VM Cutover Coverage Bookkeeping Proof

Date: 2026-05-10
Status: Routed - Phase A required before implementation
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: vm-cutover-coverage-bookkeeping-proof-2026-05-09
Class: L4_ENABLER
Category: /mu structural evidence
Source authorization: routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md

## Scope

- Reproduce the `repo_truth_non_blockers_2026-03-14.md` N1 claim that Python
  VM cutover coverage bookkeeping is reconstructed in host code rather than
  directly locked by VM-emitted evidence.
- Read-only evidence surfaces:
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - existing coverage tests under `mu/tests/`
- Phase A may propose a later bounded implementation packet only after proving
  the exact bookkeeping gap still reproduces.

## Work Items

1. Reproduce the coverage-path evidence at `_step_kernel_with_vm`.
2. Decide whether the correct next action is focused proof coverage, Stage0 VM
   attempt/match event materialization, or no-op closure by existing tests.
3. If implementation is needed, define a later Phase B scope that narrows host
   coverage reconstruction by deriving bookkeeping from Stage0 VM structural
   program attempts or a parity-preserving VM result trace.

## Constraints

- Do not edit runtime, Stage0, coverage, seed, scheduler, registry, parity, or
  production `/mu` code in Phase A.
- Do not add host-only bookkeeping semantics. Any later implementation must
  reduce or bound the existing host reconstruction assumption.
- Preserve Python/JS parity claims. JS has no coverage system, so a Python
  coverage proof must not imply JS behavior that does not exist.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if current tests already prove exact `record_no_match` / `record_match`
  parity.
- Stop if the only possible fix would add host-only coverage semantics instead
  of deriving proof from Mu/Stage0 execution structure.
- Stop if implementation would need broader Stage0 or runtime changes before a
  locked Phase A packet exists.

## Acceptance Criteria

- Phase A records current file:line and command evidence for the coverage gap.
- Any later implementation packet states how it programs in Mu or narrows the
  bootstrap coverage reconstruction boundary without adding host-only semantics.
- No runtime implementation occurs before Phase A is reviewed and locked.

## Grounding / Authorization

- Source advisory:
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` N1.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization:
  repo-truth-mu-structural-advisory-triage-2026-05-09 routing packet.
