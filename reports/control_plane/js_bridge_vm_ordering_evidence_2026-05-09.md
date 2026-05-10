# JS Bridge VM Ordering Evidence

Date: 2026-05-10
Status: Routed - Phase A required before implementation
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: js-bridge-vm-ordering-evidence-2026-05-09
Class: L4_ENABLER
Category: /mu structural evidence
Source authorization: routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md

## Scope

- Reproduce the `repo_truth_non_blockers_2026-03-14.md` N2 claim that JS
  bridge-mode VM evidence is thinner than the Python/core lane.
- Evidence surfaces:
  - `mu/host/js/engine/kernel.js`
  - `mu/host/js/tests/self_tests.js`
  - `mu/tests/parity/test_js_vm_bridge_parity.py`
  - focused JS parity tests only if Phase A proves a still-live gap.

## Work Items

1. Reproduce current JS bridge-mode smoke and ordering evidence.
2. Decide whether the missing proof is an end-to-end JS test for
   `kernel.v1 -> bridge -> match.v2 -> subst.v2` ordering under the Stage0 VM,
   or whether current parity tests already close the advisory.
3. If a proof gap remains, route a later implementation packet limited to
   focused JS/pytest evidence. The later packet must exercise existing Mu
   projections and Stage0 VM bundles rather than adding JavaScript semantic
   shortcuts.

## Constraints

- No JS runtime semantics, seed registration, scheduler, Stage0 VM, or
  production behavior changes in Phase A.
- No new host-only semantics may be introduced for ordering proof.
- Preserve the fact that `mu/host/js/engine/kernel.js` has no coverage system.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if current JS parity tests already prove the exact bridge ordering claim.
- Stop if the proof would require runtime behavior changes instead of focused
  evidence.
- Stop if Phase A discovers the advisory is actually a coverage-system request;
  route that back to the coverage packet instead of merging scopes.

## Acceptance Criteria

- Phase A identifies the exact remaining JS bridge evidence gap or closes it
  with current command/file evidence.
- Any later implementation packet is evidence-only unless Phase A separately
  proves a runtime defect.
- The packet states how the proof executes existing Mu projections rather than
  importing host ordering semantics.

## Grounding / Authorization

- Source advisory:
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` N2.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization:
  repo-truth-mu-structural-advisory-triage-2026-05-09 routing packet.
