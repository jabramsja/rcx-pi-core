# Repo Red-Team Non-Blockers (2026-03-14)

This packet is the canonical active advisory packet from the 2026-03-14
repo-wide verification sweep.

The blocker lane is now governance-truth only; see
`reports/deferred/blocking/redteam_2026-03-14_wave5_governance_loopholes.md`.

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

## N2 `DEFECT` — Stage0 compiled-bundle integrity **RESOLVED** (2026-03-15)

**Fix applied:** Both runtimes now validate `source_digest` format: must be exact `str`/`string` type (no subclasses), prefix `sha256:`, exactly 64 lowercase hex chars. Malformed digests like `"bogus"` or non-hex chars are rejected.

**Remaining gap:** Format is validated but content is not verified — a
well-formed but incorrect digest (valid hex but wrong hash) still passes.

Founder direction (2026-03-14):

- if full verification is added, do it in a way that does not make the
  semantic execution core depend on host source files at runtime
- prefer compiler/loader/provenance enforcement over adding source-file access
  to the Stage0 execution path
- disposition: defer content verification to a compiler/loader provenance wave,
  not a Stage0 execution-core wave

Evidence:

- Python:
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py:458-467`
- JS:
  - `mu/host/js/core/stage0_vm.js:487-492`

Direct repro:

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, 'mu/host/python')
from rcx_pi.selfhost.stage0_vm import validate_bundle
bundle = {
    'stage0_ir_version': 1,
    'bundle_id': 'b',
    'source_seed': 's',
    'machine_profile': 'rcx.stage0.v1',
    'program_order': ['p1'],
    'programs': [{'id': 'p1', 'ops': [{'op': 'return_projection_fail'}]}],
    'lowering_version': '1.0.0',
    'source_digest': 'sha256:' + ('0' * 64),
}
validate_bundle(bundle)
print('PY_OK')
PY
node - <<'JS'
const { validateBundle } = require('./mu/host/js/core/stage0_vm');
const bundle = {
  stage0_ir_version: 1,
  bundle_id: 'b',
  source_seed: 's',
  machine_profile: 'rcx.stage0.v1',
  program_order: ['p1'],
  programs: [{ id: 'p1', ops: [{ op: 'return_projection_fail' }] }],
  lowering_version: '1.0.0',
  source_digest: 'sha256:' + '0'.repeat(64),
};
validateBundle(bundle);
console.log('JS_OK');
JS
```

Observed:

- `PY_OK`
- `JS_OK`

Why this remains advisory:

- This is a real integrity gap, but current gates only claim field-presence
  integrity and both runtimes still behave consistently.

## N3 `DOC_ACCURACY` — the canonical doctrine map is still split across startup surfaces — **RESOLVED 2026-03-15**

Fixed: added `Why_RCX_PI_VM_EXISTS.md` and `StructuralPurity.v0.md` to MANIFEST.md
canonical reading order (items 14-15). ROADMAP.md updated to reference 15-doc order.

Evidence:

- founder bootstrap requires:
  - `FOUNDER_SESSION_BOOTSTRAP.md:115`
- Claude startup depends on:
  - `CLAUDE.md:19`
  - `CLAUDE.md:37-38`
  - `CLAUDE.md:61`
- `mu/docs/README.md` presents those doctrine docs as core references:
  - `mu/docs/README.md:66`
  - `mu/docs/README.md:68`
- `roadmap/MANIFEST.md` still claims canonical reading order without including
  `StructuralPurity.v0.md` or `Why_RCX_PI_VM_EXISTS.md` in the ordered list:
  - `roadmap/MANIFEST.md:6-13`

Direct repro:

```bash
wc -l ROADMAP.md roadmap/MANIFEST.md
rg -n "StructuralPurity\\.v0\\.md|Why_RCX_PI_VM_EXISTS\\.md" \
  FOUNDER_SESSION_BOOTSTRAP.md CLAUDE.md mu/docs/README.md roadmap/MANIFEST.md
```

Observed:

- `ROADMAP.md` remains a shorter duplicate/pointer layer beside `roadmap/MANIFEST.md`
- doctrine-doc references appear in bootstrap/Claude/`mu/docs/README.md` but not
  in the manifest’s ordered list

Why this remains advisory:

- This is sync burden and onboarding ambiguity, not a reproduced runtime break.

## Validation Used

- Stage0 direct-API repros above
- metadata-only integrity repros above
- `wc -l ROADMAP.md roadmap/MANIFEST.md`
- `rg` over bootstrap/Claude/manifest/docs README doctrine references

## Classification Summary

- `DEFECT`: N1, N2
- `DOC_ACCURACY`: N3
