# Stage0 Capture Path Provenance Boundary

Date: 2026-05-10
Status: Routed - Phase A required before implementation
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stage0-capture-path-provenance-boundary-2026-05-09
Class: L4_ENABLER
Category: /mu structural Stage0 boundary
Source authorization: routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md

## Scope

- Deduplicated source advisories:
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md` N1
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` N14
- Evidence surfaces:
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
  - `mu/host/js/core/stage0_vm.js`
  - focused Stage0 VM direct-API tests under `mu/tests/`

## Work Items

1. Reproduce that `capture_path` stores the raw resolved value before
   `capture_ref` materialization canonicalizes non-Mu hostile leaves to
   `None`/`null`.
2. Decide whether the correct structural boundary is capture-time Mu validation,
   capture-time safe copy/canonicalization, or an explicit provenance rule for
   direct Stage0 API inputs.
3. If implementation is warranted, define a later Phase B scope that updates
   Python and JavaScript Stage0 behavior together and proves parity with focused
   direct-API tests.

## Constraints

- No Stage0 runtime edits in Phase A.
- No Python-only or JS-only remediation. Any later implementation must preserve
  cross-substrate Stage0 behavior.
- Do not add host-only object semantics. The fix must narrow the direct Stage0
  bootstrap boundary by validating, copying, or tagging Mu/provenance at the
  capture boundary.
- Do not alter production callers unless Phase A proves production exploitability.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if current direct-API evidence no longer reproduces.
- Stop if the proposed fix would canonicalize arbitrary host objects into valid
  Mu by policy rather than fail-closing or preserving provenance.
- Stop if the implementation would touch seeds, scheduler, registry, or
  unrelated runtime surfaces.

## Acceptance Criteria

- Phase A records one canonical Stage0 capture advisory and does not route
  duplicate N14/N1 packets.
- Any later implementation packet states the exact Python/JS Stage0 write set,
  parity tests, and how the boundary narrows bootstrap debt without adding
  host-only semantics.
- Production exploit claims remain excluded unless reproduced.

## Grounding / Authorization

- Source advisories:
  `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md` and
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization:
  repo-truth-mu-structural-advisory-triage-2026-05-09 routing packet.
