# Repo Red-Team Non-Blockers (2026-03-14)

This packet is the canonical active advisory packet from the 2026-03-14
repo-wide verification sweep.

The blocker lane is now governance-truth only; see
`reports/archive/deferred/redteam_2026-03-14_wave5_governance_loopholes.md`.

Cleanup note (2026-05-06): resolved section N2 was moved to
`reports/archive/deferred/redteam_2026-03-14_repo_non_blockers_partial-closed-by-deferred-non-blocking-cleanup-2026-05-06.md`.
Truth-sweep note (2026-05-07): resolved Claude-referencing section N3 was moved
to
`reports/archive/deferred/redteam_2026-03-14_repo_non_blockers_partial_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`.
The active packet now retains only N1 as `/mu` structural hard-stop advisory
status. This wave does not authorize `/mu` structural implementation.

Cleanup note (2026-05-09): current code still stores `capture_path` values in
the per-attempt capture table before materialization:
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:794` through
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:805` and
`mu/host/js/core/stage0_vm.js:831` through
`mu/host/js/core/stage0_vm.js:841`. Current materialization then deep-copies
`capture_ref` through `_safe_mu_copy` / `safeMuCopy` at
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:372` through
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:381` and
`mu/host/js/core/stage0_vm.js:369` through
`mu/host/js/core/stage0_vm.js:380`. The advisory remains open only as a
separate `/mu` structural hardening question. Next-wave task required before
implementation: `stage0-capture-path-provenance-boundary-2026-05-09` as a
separate bounded packet.

## N1 `DEFECT` — Stage0 direct APIs still retain raw hostile leaves in capture slots before materialization **PARTIALLY RESOLVED** (2026-03-14)

**Fix applied:** `capture_ref` now deep-copies via `_safe_mu_copy`/`safeMuCopy`. Python `_mu_copy` rejects non-Mu types (returns None). JS `muCopy` uses `_isPlainArray`/`_isPlainObject` and rejects non-Mu types (returns null).

**Remaining gap:** Hostile leaves captured at `capture_path` are stored as raw
references before copy. The deep copy at `capture_ref` materialization
canonicalizes them to `null`/`None`, so the *output* is now safe, but the
captured reference itself is still raw until materialization. This is a design
gap, not a production exploit path (JSON-parsed inputs never produce
subclasses).

Evidence:

- Python:
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py:364-371`
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py:781-813`
- JS:
  - `mu/host/js/core/stage0_vm.js:362-371`
  - `mu/host/js/core/stage0_vm.js:807-837`

Direct repro:

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, 'mu/host/python')
from rcx_pi.selfhost.stage0_vm import stage0_vm_step
class EvilStr(str):
    pass
bundle = {
    'stage0_ir_version': 1,
    'bundle_id': 'capture-echo',
    'source_seed': 'test',
    'machine_profile': 'rcx.stage0.v1',
    'hand_authored': True,
    'program_order': ['p1'],
    'programs': [{
        'id': 'p1',
        'ops': [
            {'op': 'capture_path', 'path': ['focus', 'root', 'x'], 'name': 'cap'},
            {'op': 'write_path', 'template': {'kind': 'capture_ref', 'name': 'cap'}},
            {'op': 'return_projection_success'},
        ],
    }],
}
value = {'x': EvilStr('tainted')}
result = stage0_vm_step(bundle, value)
print(result['status'])
print(type(result['root']).__name__)
print(isinstance(result['root'], EvilStr))
print(repr(result['root']))
PY
node - <<'JS'
const { stage0VmStep } = require('./mu/host/js/core/stage0_vm');
const bundle = {
  stage0_ir_version: 1,
  bundle_id: 'capture-echo',
  source_seed: 'test',
  machine_profile: 'rcx.stage0.v1',
  hand_authored: true,
  program_order: ['p1'],
  programs: [{
    id: 'p1',
    ops: [
      { op: 'capture_path', path: ['focus', 'root', 'x'], name: 'cap' },
      { op: 'write_path', template: { kind: 'capture_ref', name: 'cap' } },
      { op: 'return_projection_success' },
    ],
  }],
};
const value = { x: new String('tainted') };
const result = stage0VmStep(bundle, value);
console.log(result.status);
console.log(result.root instanceof String);
console.log(result.root === null);
console.log(String(result.root));
JS
```

Observed:

- Python: `match / NoneType / False / None`
- JS: `match / false / true / null`

Why this remains advisory:

- Current production callers validate Mu before entering the VM-backed kernel
  path, so this is still a direct-API hardening gap rather than a reproduced
  production exploit.

## Validation Used

- Stage0 direct-API repros above

## Classification Summary

- `DEFECT`: N1
