# Repo Red-Team Blockers (2026-03-14)

Verdict: ~~`NO-GO`~~ **RESOLVED** (2026-03-14). JS `_ALGORITHM_SEED_ALLOWLIST` added to `pipeline.js:boundaryOpRunAlgorithm`. Rogue injection test added. 56/56 boundary gate tests pass.

Founder bootstrap was followed. Claude's bridge summary was treated as untrusted input and re-checked from code and commands. The previously reported P7-d `vmConfig` routing blockers do not reproduce on current `HEAD`; the blocker below does.

## Scope

- Runtime/code: seeds, substrates, hosts, Stage0, registries, loaders, boundary dispatch, fail-closed behavior
- Tools/checkers/gates: L4 contract, host-semantics ratchet, authority inventory ratchet, docs consistency check
- Tests: L4 gates, ratchet tests, doc grounding/consistency suites
- Docs: `STATUS.md`, `TASKS.md`, `roadmap/MANIFEST.md`, active L4 packet, bootstrap doctrine

## B1 `DEFECT` — JS `run_algorithm` boundary still trusts caller-supplied `seedProjectionMap` membership instead of the Python allowlist

- JS boundary dispatch authorizes `run_algorithm` by `seedProjectionMap[algoName]` presence in [mu/host/js/engine/pipeline.js](../../../mu/host/js/engine/pipeline.js):249-263.
- Python rejects names outside `_ALGORITHM_SEED_ALLOWLIST` in [mu/host/python/rcx_pi/selfhost/engine_pipeline.py](../../../mu/host/python/rcx_pi/selfhost/engine_pipeline.py):678-702.
- Current direct repro:

```bash
node - <<'JS'
const fs = require('fs');
const { serviceBoundaryEffect } = require('./mu/host/js/engine/pipeline');
const readProjs = p => JSON.parse(fs.readFileSync(p, 'utf8')).projections;
const seedProjectionMap = Object.assign(Object.create(null), {
  'recurrence.v1.json': readProjs('mu/closures/recurrence.v1.json'),
  'recurrence.v2.json': readProjs('mu/closures/recurrence.v2.json'),
  'exhaustion.v1.json': readProjs('mu/closures/exhaustion.v1.json'),
  'fix.v1.json': readProjs('mu/closures/fix.v1.json'),
  'rogue.v1.json': readProjs('mu/closures/recurrence.v1.json'),
});
const result = serviceBoundaryEffect(
  [],
  seedProjectionMap,
  {
    operation: 'run_algorithm',
    input: { start: true },
    context: {},
    inject_key: 'algo_result',
    algorithm: 'rogue.v1.json',
  },
  0,
  () => {},
  0,
  { existing: true },
  null,
);
console.log(JSON.stringify(result));
JS
```

Observed output:

```json
{"algo_result":{"start":true}}
```

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, '.')
from rcx_pi.selfhost.engine_pipeline import _service_boundary_effect
def emit(*args, **kwargs):
    pass
request = {
    'operation': 'run_algorithm',
    'input': {'start': True},
    'context': {},
    'inject_key': 'algo_result',
    'algorithm': 'rogue.v1.json',
}
try:
    print(_service_boundary_effect(request, max_algorithm_iterations=0, emit_fn=emit, iteration=0, state={'existing': True}))
except Exception as e:
    print(type(e).__name__)
    print(str(e))
PY
```

Observed output:

```text
RcxEngineError
run_algorithm 'algorithm' must be an authorized algorithm seed, got 'rogue.v1.json'. Allowed: ['exhaustion.v1.json', 'fix.v1.json', 'recurrence.v1.json', 'recurrence.v2.json']
```

- Why existing gates missed it:
  - [mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py](../../../mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py):965-1012 only proves the production JS map keys currently match the Python allowlist and that a missing key like `kernel.v1.json` is rejected.
  - There is no negative test for an unauthorized alias injected into a caller-supplied JS `seedProjectionMap`.
- Why this is blocker-severity:
  - It breaks the repo's own Python/JS boundary-authority parity claim.
  - It lets exported JS runtime helpers execute a non-authorized algorithm name as long as the caller can provide a matching map entry.
  - The failure is at the authorization boundary, not in ancillary docs or accounting.

## Validation

- `git status --short`
  - `?? .scratch/`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged`
  - `No staged files — skipping enforcement.`
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - pass
- `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - pass, with 1 signal-shape note
- `./tools/checks/check_docs_consistency.sh`
  - pass
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py -q`
  - `54 passed`

