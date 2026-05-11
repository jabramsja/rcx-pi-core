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

Triage note (2026-05-10): current code still stores `capture_path` values in
the per-attempt capture table before materialization:
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:796` through
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:807` and
`mu/host/js/core/stage0_vm.js:831` through
`mu/host/js/core/stage0_vm.js:841`. Current materialization then deep-copies
`capture_ref` through `_safe_mu_copy` / `safeMuCopy` at
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:374` through
`mu/host/python/rcx_pi/selfhost/stage0_vm.py:383` and
`mu/host/js/core/stage0_vm.js:369` through
`mu/host/js/core/stage0_vm.js:380`. The advisory remains open only as a
separate `/mu` structural hardening question. Direct repro commands exited 0
with Python `match / NoneType / False / None` and JS
`match / false / true / null`. Next-wave packet required before implementation:
`reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`.
The overlapping N14 in `repo_truth_non_blockers_2026-03-14.md` is deduplicated
to this canonical Stage0 route.

2026-05-11 reconciliation:

- **Outcome:** retained live Stage0 capture advisory.
- **Governing route:** `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`.
- **Current proof gap:** the routed packet reproduced that `capture_path`
  stores raw direct-API host leaves before later `capture_ref` materialization
  canonicalizes them to `None` / `null`; no production exploit path was
  reproduced.
- **Hard stop before implementation:** this advisory authorizes no Stage0,
  seed, scheduler, registry, parity, or production `/mu` edits. Any later
  implementation must use a locked successor packet with the exact Python/JS
  Stage0 write set and focused parity proof.
- **Doctrine boundary:** future work must narrow the direct Stage0 bootstrap
  boundary by validating, copying, or tagging Mu/provenance at capture time;
  it must update Python and JavaScript together and must not add host-only
  object semantics.
- **Deduplication:** `repo_truth_non_blockers_2026-03-14.md` N14 remains only a
  duplicate pointer to this route and must not open a second Stage0 packet.

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
- Governing route:
  `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`.

## Validation Used

- Stage0 direct-API repros above
- 2026-05-10 direct Python and JS repros above re-run successfully with the
  same output.

## Classification Summary

- `DEFECT`: N1
