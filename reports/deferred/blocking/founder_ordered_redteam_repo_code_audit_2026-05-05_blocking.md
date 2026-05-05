# Founder Ordered Redteam Repo Code Audit - Blocking Findings

Date: 2026-05-05
Status: CLASSIFIED - BLOCKING
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-repo-code-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_repo_code_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-repo-code-audit-2026-05-05

This packet records blocking repo-code findings only. The audit wave did not
implement remediation.

## Scope Executed

- Python/JavaScript substrate sync under `mu/host/python/` and `mu/host/js/`.
- Stage0, lowering, runtime, and execution-boundary paths under `mu/`.
- Structural `/mu` seed, registry, bridge, program, projection, and runtime
  wiring that carries current production, parity, Stage0, or L4 claims.
- Narrow tests/docs/tooling reads only where needed to prove or disprove the
  code claim.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## B1 - JavaScript Mu Validation Admits Host Objects

Classification: BLOCKING DEFECT

Surfaces: Python/JavaScript substrate sync, host-authority drift, Mu boundary
validation, content-addressed hashing.

Evidence:

- `mu/host/js/core/types.js:87` documents `isValidMu` as checking a valid Mu
  type, with rejection for NaN, Infinity, functions, undefined, symbols, width,
  depth, symbol keys, and cycles.
- `mu/host/js/core/types.js:122` and `mu/host/js/core/types.js:161` accept any
  JavaScript value whose `typeof` is `object`, then validate only enumerable
  string keys and recursively valid values at `mu/host/js/core/types.js:162`
  through `mu/host/js/core/types.js:171`. There is no plain-object or prototype
  restriction.
- `mu/host/python/rcx_pi/selfhost/mu_type.py:95` defines Mu as
  JSON-compatible. `mu/host/python/rcx_pi/selfhost/mu_type.py:203` through
  `mu/host/python/rcx_pi/selfhost/mu_type.py:207` require exact compound types
  specifically to reject object subclasses with host behavior, and
  `mu/host/python/rcx_pi/selfhost/mu_type.py:209`,
  `mu/host/python/rcx_pi/selfhost/mu_type.py:238`, and
  `mu/host/python/rcx_pi/selfhost/mu_type.py:251` reject anything other than an
  exact `list` or exact `dict` after primitive checks.

Direct output:

```text
$ node - <<'NODE'
const { isValidMu, muHash } = require('./mu/host/js/core/types');
const values = {
  date: new Date(0),
  map: new Map(),
  class_empty: new (class X {})(),
};
const classWithKey = new (class X {})();
classWithKey.a = 1;
values.class_with_key = classWithKey;
values.plain_object = {};
for (const [name, value] of Object.entries(values)) {
  console.log(`${name} valid=${isValidMu(value)} hash=${muHash(value)}`);
}
NODE
date valid=true hash=44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
map valid=true hash=44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
class_empty valid=true hash=44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
class_with_key valid=true hash=f9d86028c6e0d64e225186f96acb69338b2c59764df79162107f5c4bb34d1310
plain_object valid=true hash=44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
```

```text
$ PYTHONPATH=mu/host/python python3 - <<'PY'
from rcx_pi.selfhost.mu_type import is_mu, mu_hash
class X: pass
class D(dict): pass
values = {
    'object': X(),
    'dict_subclass': D({'a': 1}),
    'plain_dict': {'a': 1},
}
for name, value in values.items():
    print(f"{name} valid={is_mu(value)}", end='')
    try:
        print(f" hash={mu_hash(value)}")
    except Exception as exc:
        print(f" hash_error={type(exc).__name__}:{exc}")
PY
object valid=False hash_error=TypeError:mu_hash must be a Mu (JSON-compatible value), got X: <__main__.X object at 0x10d2d4830>
dict_subclass valid=False hash_error=TypeError:mu_hash must be a Mu (JSON-compatible value), got D: {'a': 1}
plain_dict valid=True hash=f9d86028c6e0d64e225186f96acb69338b2c59764df79162107f5c4bb34d1310
```

Why this blocks:

- JavaScript module/runtime callers can pass host objects that cannot be
  represented by portable Mu JSON and that Python rejects at the equivalent
  substrate boundary.
- Empty `Date`, `Map`, and class instances are accepted as valid Mu and receive
  the same hash as `{}`, while class instances with enumerable fields receive
  the same structural hash as plain Mu objects with those fields.
- This violates Python/JavaScript substrate parity and host-authority
  containment for the Mu validator/hash boundary. JSON API callers may still be
  constrained by JSON parsing, but current repo-code claims cannot honestly
  treat the JS substrate validator as equivalent to the Python JSON-compatible
  Mu boundary.

Remediation is not authorized in this audit wave. Follow-up remediation must be
ordered by the founder remediation rule after all four audit waves classify
findings, with `/mu` structural remediation ordered last and hard-stopped before
implementation.
