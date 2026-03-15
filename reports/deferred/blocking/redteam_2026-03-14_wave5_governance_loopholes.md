# Wave 5 Governance Loopholes (2026-03-14)

Verdict: ~~`NO-GO`~~ **ALL RESOLVED** (2026-03-14). B1-B4 fixed in this wave.

## Scope

- Active founder-facing docs: `README.md`, `STATUS.md`, `TASKS.md`,
  `roadmap/`, `mu/docs/`, active `reports/codex/`
- Runtime/test governance: JS parity and wiring gates, proof-class enforcement,
  docs-governance coverage
- Full-repo verification context: older blocker packets were re-checked and
  archived when their findings no longer reproduced on current `HEAD`

## Archived As Resolved Or Stale During This Sweep

- `reports/archive/deferred/redteam_2026-03-14_reaudit_blockers.md`
  - stale by construction; it records no active blockers
- `reports/archive/deferred/redteam_2026-03-14_repo_blockers.md`
  - resolved; JS `run_algorithm` allowlist defect no longer reproduces
- `reports/archive/deferred/repo_truth_blockers_2026-03-14.md`
  - stale summary packet; explicitly says no active blockers
- `reports/archive/deferred/doc_drift_2026-03-14_l4_meta_circular_truth.md`
  - stale; the pre-fix L4 doctrine contradictions and missing `[S1-SCHED]`
    object no longer reproduce on current docs

## B1 `DEFECT` — `test_evidence_walker_gate.py` is still a false green for the live JS path — **RESOLVED**
**Fix:** Renamed `TestEvidenceWalkerJsParityGate` → `TestEvidenceWalkerJsRegistryGate` with honest docstring (source-lock, not runtime parity).

The gate presents itself as JS parity/wiring evidence, but its JS half is
`source_lock` only. The live JS runtime still drains traces with host code
instead of loading `evidence_walker.v1.json`.

Evidence:

- Gate proof shape:
  - `mu/tests/l4_gates/test_evidence_walker_gate.py:46-71`
- JS live path:
  - `mu/host/js/engine/pipeline.js:767-803`
- Python structural path:
  - `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:538-613`
- JS registry note already admits the gap:
  - `mu/host/js/cli/main.js:37`
  - `mu/host/js/cli/main.js:117`

Direct repro:

```bash
PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_evidence_walker_gate.py -q
python3 - <<'PY'
import json, subprocess
out = subprocess.check_output(
    ['python3', 'tools/checks/check_gate_behavioral_pairs.py', '--json'],
    text=True,
)
j = json.loads(out)
print(json.dumps(j['files']['mu/tests/l4_gates/test_evidence_walker_gate.py'], indent=2))
PY
node - <<'JS'
const seedLoader = require('./mu/host/js/core/seed_loader');
const pipeline = require('./mu/host/js/engine/pipeline');
let called = false;
const orig = seedLoader.loadVerifiedSeed;
seedLoader.loadVerifiedSeed = function(seedName, subdir) {
  if (seedName === 'evidence_walker.v1.json') called = true;
  return orig.apply(this, arguments);
};
const trace = { head: { state: 'a', projection: 'p' }, tail: null };
const obs = pipeline.collectOntologyEvidence({ trace, stall: false }, 'run_algorithm');
console.log(JSON.stringify(obs));
console.log('called=' + called);
JS
```

Observed:

- `9 passed`
- `TestEvidenceWalkerJsParityGate` classifies as `source_lock`
- JS still returns an observation record with `called=false`

Why current gates missed it:

- `test_evidence_walker_gate.py` accepts registry-string/source proof for a live
  JS runtime claim.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py:1174-1214` locks
  the manual JS drain instead of proving seed execution.

Why this blocks:

- The repo claims a green JS parity/wiring gate for behavior it does not prove
  on the live JS substrate.

## B2 `DEFECT` — `test_observer_type_guard_gate.py` is also a false green for its JS “runtime” claim — **RESOLVED**
**Fix:** Renamed `TestJsObserverTypeGuardRuntime` → `TestJsObserverTypeGuardSourceCountLock` with honest docstring.

The JS runtime class in this gate never exercises JS runtime behavior. It only
scans concatenated JS source text for guard strings. Real JS behavioral proof
exists elsewhere, but this gate still advertises runtime proof it does not
provide.

Evidence:

- False-green class:
  - `mu/tests/l4_gates/test_observer_type_guard_gate.py:202-246`
- Real behavioral JS proof already exists in a different gate:
  - `mu/tests/l4_gates/test_js_observer_api_guard_gate.py:75-94`
  - `mu/tests/l4_gates/test_js_observer_api_guard_gate.py:147-181`
- Runtime guard sites:
  - `mu/host/js/engine/pipeline.js:836-837`
  - `mu/host/js/engine/pipeline.js:953-954`
  - `mu/host/js/engine/routing.js:153-154`

Direct repro:

```bash
PYTHONHASHSEED=0 python3 -m pytest \
  mu/tests/l4_gates/test_observer_type_guard_gate.py \
  mu/tests/l4_gates/test_js_observer_api_guard_gate.py -q
python3 - <<'PY'
import json, subprocess
out = subprocess.check_output(
    ['python3', 'tools/checks/check_gate_behavioral_pairs.py', '--json'],
    text=True,
)
j = json.loads(out)
print(json.dumps(j['files']['mu/tests/l4_gates/test_observer_type_guard_gate.py'], indent=2))
PY
node mu/host/js/eval_step.js --json-api '{"action":"run_engine_pipeline","input":"api_guard_test","projections":[],"maxSteps":10,"maxEngineIterations":20,"maxAlgorithmIterations":50,"observer_strict":"bad"}'
```

Observed:

- both test files pass (`38 passed`)
- `TestJsObserverTypeGuardRuntime` classifies as `source_lock`
- the JSON API returns `{"success":false,"error_code":"observer.invalid_type",...}`

Why current gates missed it:

- `test_observer_type_guard_gate.py` names the class `Runtime` but only performs
  source scans.
- `check_gate_behavioral_pairs.py` reports the weak proof class but does not
  fail the gate.

Why this blocks:

- The repo still allows a live runtime claim to pass green on proof that is not
  runtime proof.

## B3 `DEFECT` — proof-class governance remains fail-open — **RESOLVED**
**Fix:** `check_gate_behavioral_pairs.py` now fails by default when "Runtime"/"Wiring" class names are backed only by `source_lock`. Mismatch enforcement is on by default.

The classifier can correctly identify `source_lock` proof, but the enforcement
layer only fails on `theater_risk`. Proof-class mismatch for JS/runtime/parity
claims is still advisory to the tooling, not normative.

Evidence:

- classifier categories:
  - `tools/checks/check_gate_behavioral_pairs.py:4-13`
  - `tools/checks/check_gate_behavioral_pairs.py:110-139`
- fail condition only on `theater_risk`:
  - `tools/checks/check_gate_behavioral_pairs.py:217-246`
- current attestation failure:
  - `./tools/session/founder_session_attest.sh redteam`

Direct repro:

```bash
./tools/session/founder_session_attest.sh redteam
python3 tools/checks/check_gate_behavioral_pairs.py --root mu/tests/l4_gates
```

Observed:

- attestation fails on the evidence-walker and observer proof-class violations
- `check_gate_behavioral_pairs.py` still exits clean while classifying those
  same claims as `source_lock`

Why this blocks:

- This is the loophole that lets gates stay green while proving the wrong thing.

## B4 `DOC_ACCURACY` — docs governance produced a false-green current-state signal — **RESOLVED**
**Fix:** root `README.md` drift was corrected. Founder policy also confirmed that
`reports/codex/` remains intentionally exempt because it is a working vector
lane rather than a canonical current-state surface.

`check_docs_consistency.sh` reports success even though:

1. root `README.md` was materially stale for current state
2. `reports/codex/` exemption required explicit founder-policy clarification

Evidence:

- corrected README current-state claims:
  - `README.md`
- docs consistency script:
  - `tools/checks/check_docs_consistency.sh:83-151`
- founder-approved `reports/codex/` exemption:
  - `tools/docs/docs_registry.json:34-53`
  - `tools/docs/shared_doc_config.py:78-112`

Direct repro:

```bash
./tools/checks/check_docs_consistency.sh
./tools/session/founder_session_attest.sh redteam
python3 - <<'PY'
from pathlib import Path
from tools.docs.shared_doc_config import classify_md_path, REPO_ROOT
for rel in [
    Path('README.md'),
    Path('reports/codex/README.md'),
]:
    print(f'{rel}: {classify_md_path(REPO_ROOT / rel)}')
PY
```

Observed:

- docs consistency reports `All checks passed. Docs are consistent.`
- docs attestation now passes, reporting the `reports/codex/` exemption as a
  founder-approved advisory rather than a blocker
- classification result:
  - `README.md: root_canonical`
  - `reports/codex/README.md: exempt`

Why this blocks:

- historical false-green risk was real, but the root README drift is fixed and
  the Codex-lane exemption is now explicitly documented as founder-approved.

## Rectification Plan

1. Make proof-class contracts normative for gates that claim JS/runtime/parity/wiring truth.
2. Fail `check_gate_behavioral_pairs.py` when those gates are backed only by `source_lock`.
3. Require at least one negative control for claimed live-path/wiring gates.
4. Split inventory/source-lock tests from runtime-parity tests instead of letting one satisfy the other.
5. Keep attestation and blocker wording aligned with the founder-approved
   `reports/codex/` exemption instead of re-opening that policy choice.
6. Keep root `README.md` current-state truth assertions in the docs-governance suite.

## Validation Used

- `./tools/session/founder_session_attest.sh redteam`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_evidence_walker_gate.py -q`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_observer_type_guard_gate.py mu/tests/l4_gates/test_js_observer_api_guard_gate.py -q`
- `python3 tools/checks/check_gate_behavioral_pairs.py --json`
- `node` loader-intercept repro for `collectOntologyEvidence`
- `node mu/host/js/eval_step.js --json-api ...observer_strict...`
- `./tools/checks/check_docs_consistency.sh`

## Classification Summary

- `DEFECT`: B1, B2, B3
- `DOC_ACCURACY`: B4
