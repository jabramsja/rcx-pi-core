# Transparent JS Proxy Provenance Boundary

Date: 2026-05-10
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: transparent-js-proxy-provenance-boundary-2026-05-09
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural boundary policy
Source authorization: routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md
## Scope

- Phase A policy/reproduction packet only. No implementation file may be edited
  under this packet.
- Files in scope for evidence, reproduction, and route definition:
  - `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
  - `TASKS.md`
  - `mu/host/js/core/types.js`
  - `mu/tests/l4_gates/test_d009_production_depth_gate.py`
  - `mu/tests/parity/test_js_parity_automated.py`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
- No directory-wide runtime, test, seed, scheduler, registry, Stage0, or parity
  scope is authorized by Phase A. Any later implementation packet must enumerate
  its own exact file list before code edits.

## Work Items

1. Reproduce that transparent `new Proxy({a: 1}, {})` values pass current
   structural reflection and hash like their target, while hostile/trapping
   proxies fail closed.
2. Phase A must choose one route before implementation:
   - structural provenance/normalization boundary that admits only values with
     trusted Mu-origin provenance,
   - explicit founder-authorized host oracle,
   - or documented non-action preserving transparent Proxy equivalence.
3. Record the Phase A route decision artifact before any implementation work:
   selected route, rationale, founder-decision state, and whether the decision
   authorizes implementation, requires founder input, or closes as non-action.
4. If implementation is warranted, define exact Python/JS parity implications,
   focused tests, host-authority ratchet expectations, and the successor
   implementation packet's file list.

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
- Phase A records the route decision, rationale, and founder-decision state:
  structural provenance/normalization, explicit founder-authorized host oracle,
  or documented non-action preserving transparent Proxy equivalence.
- Any later implementation packet cites the Phase A route decision, states
  whether it programs in Mu/provenance or intentionally authorizes a host oracle,
  records the host-authority impact, and enumerates exact implementation files.
- No transparent Proxy provenance implementation occurs before Phase A is
  reviewed and locked.

## Grounding / Authorization

- Source advisory:
  `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization:
  `TASKS.md:516` tracker sync note for
  `[NEXT-CODEX-POST-REDTEAM]`,
  `transparent-js-proxy-provenance-boundary-2026-05-09`, and
  `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`.
- Same-wave override:
  `FOUNDER_OVERRIDE:transparent-js-proxy-provenance-boundary-2026-05-09`.
- Governing routing packet:
  repo-truth-mu-structural-advisory-triage-2026-05-09 routing packet.
- Tracker evidence:
  `TASKS.md:516` records that current JS reports `plainValid:true`,
  `proxyValid:true`, and successful `muHashCached(transparentProxy)`; the packet
  must choose structural provenance, explicit host-oracle override, or documented
  non-action before code edits; no host Proxy oracle is authorized by this
  triage wave.

## Phase A Implementation Scope Note

This Phase B implementer records the locked Phase A reproduction and route
decision artifact only. The packet scope above still forbids runtime, hash,
validator, Stage0, seed, scheduler, registry, or parity edits in this wave.

## Phase A Reproduction Evidence

Focused reproducer:

```bash
node - <<'NODE'
'use strict';
const t = require('./mu/host/js/core/types');

function hashOutcome(value) {
  try {
    return { ok: true, value: t.muHashCached(value) };
  } catch (err) {
    return { ok: false, error: err.error_code || err.name || String(err) };
  }
}

function reflectionOutcome(value) {
  try {
    const descriptor = Object.getOwnPropertyDescriptor(value, 'a');
    return {
      ok: true,
      ordinaryPrototype: Object.getPrototypeOf(value) === Object.prototype,
      keys: Object.keys(value),
      ownNames: Object.getOwnPropertyNames(value),
      descriptorA: descriptor && {
        enumerable: descriptor.enumerable,
        configurable: descriptor.configurable,
        hasValue: Object.prototype.hasOwnProperty.call(descriptor, 'value'),
        value: descriptor.value,
      },
    };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

function validity(value) {
  return {
    defaultValid: t.isValidMu(value),
    budgetValid: t.isValidMu(value, 0, undefined, t._STRUCTURAL_DEPTH_BUDGET),
    cachedHash: hashOutcome(value),
    reflection: reflectionOutcome(value),
  };
}

const plain = { a: 1 };
const transparentProxy = new Proxy({ a: 1 }, {});
const hostileGetPrototype = new Proxy({ a: 1 }, {
  getPrototypeOf() { throw new Error('host trap getPrototypeOf'); },
});
const hostileOwnKeys = new Proxy({ a: 1 }, {
  ownKeys() { throw new Error('host trap ownKeys'); },
});
const hostileDescriptor = new Proxy({ a: 1 }, {
  getOwnPropertyDescriptor() { throw new Error('host trap descriptor'); },
});

const plainResult = validity(plain);
const proxyResult = validity(transparentProxy);

console.log(JSON.stringify({
  plain: plainResult,
  transparentProxy: {
    ...proxyResult,
    hashEqualsPlain: proxyResult.cachedHash.ok && plainResult.cachedHash.ok &&
      proxyResult.cachedHash.value === plainResult.cachedHash.value,
  },
  hostileGetPrototype: validity(hostileGetPrototype),
  hostileOwnKeys: validity(hostileOwnKeys),
  hostileDescriptor: validity(hostileDescriptor),
}, null, 2));
NODE
```

Current output, exit `0`:

```json
{
  "plain": {
    "defaultValid": true,
    "budgetValid": true,
    "cachedHash": {
      "ok": true,
      "value": "f9d86028c6e0d64e225186f96acb69338b2c59764df79162107f5c4bb34d1310"
    },
    "reflection": {
      "ok": true,
      "ordinaryPrototype": true,
      "keys": ["a"],
      "ownNames": ["a"],
      "descriptorA": {
        "enumerable": true,
        "configurable": true,
        "hasValue": true,
        "value": 1
      }
    }
  },
  "transparentProxy": {
    "defaultValid": true,
    "budgetValid": true,
    "cachedHash": {
      "ok": true,
      "value": "f9d86028c6e0d64e225186f96acb69338b2c59764df79162107f5c4bb34d1310"
    },
    "reflection": {
      "ok": true,
      "ordinaryPrototype": true,
      "keys": ["a"],
      "ownNames": ["a"],
      "descriptorA": {
        "enumerable": true,
        "configurable": true,
        "hasValue": true,
        "value": 1
      }
    },
    "hashEqualsPlain": true
  },
  "hostileGetPrototype": {
    "defaultValid": false,
    "budgetValid": false,
    "cachedHash": { "ok": false, "error": "input.invalid_type" },
    "reflection": { "ok": false, "error": "host trap getPrototypeOf" }
  },
  "hostileOwnKeys": {
    "defaultValid": false,
    "budgetValid": false,
    "cachedHash": { "ok": false, "error": "input.invalid_type" },
    "reflection": { "ok": false, "error": "host trap ownKeys" }
  },
  "hostileDescriptor": {
    "defaultValid": false,
    "budgetValid": false,
    "cachedHash": { "ok": false, "error": "input.invalid_type" },
    "reflection": { "ok": false, "error": "host trap descriptor" }
  }
}
```

Direct code truth:

- `mu/host/js/core/types.js:116` through `:158` and `:176` through `:220`
  use host prototype/key/descriptor reflection under fail-closed `try` blocks.
- `mu/host/js/core/types.js:281` through `:317` validates before hashing and
  hashes the canonical Mu string after validation.
- The prior blocking packet records the rejected host-oracle attempt at
  `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md:267`
  through `:288`: `util.types.isProxy` was removed after the purity gate rejected
  the new Node `util` import, leaving transparent Proxy rejection deferred.
- Existing focused tests cover hostile/trapping proxies but intentionally do not
  close transparent Proxy equivalence:
  `mu/tests/l4_gates/test_d009_production_depth_gate.py:406` through `:419` and
  `mu/tests/parity/test_js_parity_automated.py:959` through `:961`.

## Phase A Route Decision

Selected route: **structural provenance / boundary normalization**.

Rejected route: **explicit host Proxy oracle**. No founder authorization in this
packet permits `util.types.isProxy`, a new Node host oracle, or broader
JavaScript object-model detection. The prior purity correction already proved
that the `util` import increases the kernel's host authority surface.

Rejected route: **documented non-action preserving transparent Proxy
equivalence**. The current output proves transparent Proxies remain
observationally equivalent to plain records under the validator's host
reflection. Preserving that equivalence would leave raw JavaScript object
identity as an implicit Mu boundary and would not shrink the bootstrap
assumption.

Rationale:

- A transparent Proxy cannot be separated from its target by the current
  structural reflection path; the direct output records matching reflection,
  validation, and hash behavior for `{a: 1}` and `new Proxy({a: 1}, {})`.
- Hostile/trapping Proxies already fail closed, so the remaining issue is not
  error handling. It is provenance: the validator currently accepts any value
  that behaves like an ordinary record under reflection, even when its identity
  did not originate at a trusted Mu boundary.
- RCX direction favors shrinking bootstrap assumptions and preserving L3
  semantics over making JavaScript smarter with host-only object detectors.
  Structural provenance or explicit boundary normalization is the route aligned
  with that direction.

Founder-decision state:

- Phase A decision: **recorded**.
- Implementation authorization in this packet: **not authorized**. This packet
  remains Phase A policy/reproduction scope only.
- Required next state: a successor implementation packet must be reviewed and
  locked before code edits. That packet must cite this route decision and state
  whether it implements trusted Mu-origin provenance or a founder-authorized
  host oracle override.

Stop-condition check:

- Structural provenance is distinguished from a host Proxy oracle: this route
  rejects `util.types.isProxy` and any equivalent host-only detector.
- The proposed route must not make JavaScript host objects portable by
  serialization or canonicalization. A successor packet must reject raw host
  objects at the boundary unless they enter through the trusted Mu provenance
  path it defines.
- This packet performs no runtime edit and therefore does not increase
  host-authority inventory. Any successor packet must run the host-authority
  ratchet and must carry explicit founder authorization if its chosen
  provenance mechanism increases host-authority inventory.

## Successor Implementation Packet Requirements

Implementation is warranted, but only under a successor packet with an exact
file list and explicit proof contract.

Required parity implications:

- Python remains the semantic parity reference for exact built-in `dict` and
  `list` acceptance plus subclass rejection; JavaScript must not make raw host
  objects portable merely because they serialize like Mu.
- JavaScript external-boundary behavior must be specified explicitly: either
  values are admitted because they carry trusted Mu-origin provenance, or they
  are rejected before validation/hash semantics observe them as portable Mu.
- Existing seed, Stage0, scheduler, registry, and projection semantics must not
  change. The implementation must be a JS boundary/provenance tightening, not a
  Mu semantic rewrite.

Focused tests required:

- `mu/tests/l4_gates/test_d009_production_depth_gate.py` must add a transparent
  Proxy negative control proving `new Proxy({a: 1}, {})` rejects through default
  validation, structural-budget validation, and all hash entry points after the
  new provenance boundary is in force.
- `mu/tests/parity/test_js_parity_automated.py` must add the matching automated
  JS parity probe while preserving valid portable plain record/list behavior
  through the trusted boundary defined by the implementation packet.
- Tests must retain hostile/trapping Proxy fail-closed coverage so the new
  provenance rule does not regress the existing safety boundary.

Host-authority ratchet expectations:

- `python3 tools/checks/check_host_authority_inventory_ratchet.py` must pass.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` must pass.
- No `util`, `util.types.isProxy`, or equivalent host Proxy oracle may be added
  unless the successor packet carries explicit founder override text and records
  the inventory impact.

Exact successor implementation file list:

- `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
  as the Phase A decision source.
- `TASKS.md` for tracker synchronization.
- `mu/host/js/core/types.js` for the JS validation/hash boundary.
- `mu/tests/l4_gates/test_d009_production_depth_gate.py` for focused L4 boundary
  evidence.
- `mu/tests/parity/test_js_parity_automated.py` for JS parity evidence.
- One successor control-plane packet under `reports/control_plane/`, with a
  distinct implementation wave ID, exact validation commands, and explicit
  host-authority impact.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `transparent-js-proxy-provenance-boundary-2026-05-09`
- Active packet: `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
- Indicator artifact: `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
  - `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `transparent-js-proxy-provenance-boundary-2026-05-09`
- Active packet: `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `90a3ebaf7190680938de69a74730cb2a8d1d3fe7ee87d9169acfd8920580a18e`
- Indicator artifact: `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id transparent-js-proxy-provenance-boundary-2026-05-09 --output reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
  - `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
