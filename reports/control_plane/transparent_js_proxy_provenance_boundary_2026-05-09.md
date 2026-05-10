# Transparent JS Proxy Provenance Boundary

Date: 2026-05-10
Status: Routed - Phase A required before implementation
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: transparent-js-proxy-provenance-boundary-2026-05-09
Class: L4_ENABLER
Category: /mu structural boundary policy
Source authorization: routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md

## Scope

- Reproduce the retained advisory from
  `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`.
- Evidence surfaces:
  - `mu/host/js/core/types.js`
  - focused JavaScript Mu validation/hash tests
  - the blocking remediation packet only for the prior host-oracle purity
    correction.

## Work Items

1. Reproduce that transparent `new Proxy({a: 1}, {})` values pass current
   structural reflection and hash like their target, while hostile/trapping
   proxies fail closed.
2. Phase A must choose one route before implementation:
   - structural provenance/normalization boundary that admits only values with
     trusted Mu-origin provenance,
   - explicit founder-authorized host oracle,
   - or documented non-action preserving transparent Proxy equivalence.
3. If implementation is warranted, define exact Python/JS parity implications,
   focused tests, and host-authority ratchet expectations.

## Constraints

- Do not add `util.types.isProxy` or any host Proxy oracle without explicit
  founder authorization in this packet or a successor packet.
- Prefer structural provenance or boundary normalization over host-only
  JavaScript object-model detection.
- Do not modify runtime, hash, validator, Stage0, seed, scheduler, registry, or
  parity code in Phase A.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if Phase A cannot distinguish structural provenance work from a host
  oracle decision.
- Stop if the proposed fix would make JavaScript host objects portable by
  serialization or canonicalization.
- Stop if host-authority inventory would increase without explicit override.

## Acceptance Criteria

- Phase A records direct current output for plain records, transparent proxies,
  and hostile/trapping proxies.
- Any later implementation packet states whether it programs in Mu/provenance or
  intentionally authorizes a host oracle, and records the host-authority impact.
- No transparent Proxy implementation occurs before Phase A is reviewed and
  locked.

## Grounding / Authorization

- Source advisory:
  `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization:
  repo-truth-mu-structural-advisory-triage-2026-05-09 routing packet.
