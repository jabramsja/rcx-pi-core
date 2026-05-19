# N3-Engine-Pipeline-Run-Algorithm-Manifest-Authority-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19
Class: L4_STRUCTURAL successor
Phase-A-Lock: LOCKED
Packet: reports/control_plane/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19_2026-05-19.md
FOUNDER_OVERRIDE:n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19

Purpose: Document the bounded implementation package from the landed source-lock
packet for narrowing duplicated host-owned `run_algorithm` seed authority into
Mu-owned seed registry metadata. Same-wave TASKS.md tracker proof is now
present at `TASKS.md:380`, and this package stages the manifest, Python/JS
runtime, parity, focused test, pipeline-unblocker, tracker, packet, and L4
indicator changes needed for the L4_STRUCTURAL handoff.

Package status:

- Phase B has staged the runtime, manifest, tests, tracker, indicator, and
  pipeline-classifier unblocker files listed in Scope.
- The predecessor source-lock packet remains the grounding authority for the
  successor write set, exact five-seed accepted set, proof commands, and stop
  conditions.
- The same-wave pipeline unblocker is classifier-only. Runtime
  `run_algorithm` authority remains solely manifest-derived.

Same-wave pipeline unblocker: the pre-supervisor tracker-note gate must classify
non-runtime structural planning packets that explicitly deny implementation
authorization as `L4_ENABLER` packages instead of demanding runtime artifacts.
This wave additionally edits:

- `mu/tools/executors/phase_b_executor.py`, only to classify those bounded
  non-runtime planning packets as `L4_ENABLER` tracker packages.
- `mu/tests/tools/test_phase_b_executor.py`, only to lock that exact
  classifier behavior.

## Scope

This Phase B implementation package may write only the locked files named by
the source-lock packet, plus the same-wave pipeline unblocker and L4 indicator
artifacts described here:

- `TASKS.md`, only for a same-wave tracker entry for
  `n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19`.
- `reports/control_plane/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19_2026-05-19.md`, only as the successor control-plane packet.
- `mu/tools/executors/phase_b_executor.py`, only for the same-wave pipeline
  unblocker described above.
- `mu/tests/tools/test_phase_b_executor.py`, only for the same-wave pipeline
  unblocker regression described above.
- `mu/seed_registry_manifest.v1.json`, only to add explicit
  `authority.run_algorithm` metadata.
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`, only to validate/export
  manifest `authority.run_algorithm` metadata and update
  `SEED_REGISTRY_MANIFEST_SHA256` in lockstep.
- `mu/host/js/core/seed_loader.js`, only to validate/export manifest
  `authority.run_algorithm` metadata and update
  `SEED_REGISTRY_MANIFEST_SHA256` in lockstep.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`, only to replace the
  host-owned accepted set with manifest-derived authority.
- `mu/host/js/engine/pipeline.js`, only to replace the host-owned accepted set
  with manifest-derived authority while preserving scheduler lazy-load as a
  load path only.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`, only to prove
  exact manifest-authorized acceptance and fail-closed rejection.
- `mu/tests/structural/test_rcx_enginenew_scheduler.py`, only to preserve the
  Python scheduler boundary load path.
- `mu/tests/parity/test_rcx_engine_scheduler_parity.py`, only to preserve
  Python/JS scheduler boundary parity.
- `reports/l4_wave_indicators/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19.json`,
  only as the same-wave L4 indicator artifact collected for Gate 8 package
  scope reconciliation.

## Work items

1. Establish same-wave tracker authority before any source or implementation
   inspection for the successor. Phase B satisfied this prerequisite with:

   ```bash
   rg -n "n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19|N3-ENGINE-PIPELINE-RUN-ALGORITHM-MANIFEST-AUTHORITY" TASKS.md
   ```

2. Add Mu-owned manifest metadata
   `authority.run_algorithm=true` on exactly these five seed registry entries:
   `recurrence.v1.json`, `recurrence.v2.json`, `exhaustion.v1.json`,
   `fix.v1.json`, and `rcx_engine_scheduler.v1.json`.
3. Add Python and JavaScript manifest metadata validation/export in the named
   manifest-integrity surfaces. Both substrates must fail closed when metadata
   is unreadable, malformed, non-boolean, or yields any accepted set other than
   the preserved five-seed migration set.
4. Replace duplicated host-owned `run_algorithm` accepted-set authority in the
   named Python and JavaScript pipeline files with the manifest-derived
   authority set. Preserve `recurrence.v1.json` compatibility acceptance and
   preserve JavaScript scheduler lazy-load as a load path only.
5. Update Python and JavaScript manifest SHA constants in lockstep with the
   manifest byte change.
6. Add or update focused boundary, scheduler structural, and scheduler parity
   tests so Python and JavaScript accept exactly the manifest-authorized set and
   reject non-authorized registered seeds, rogue seed-map injection, and
   prototype-chain/non-owned authority keys.
7. Run the required tracker, accepted-set, checksum lockstep, focused pytest,
   ratchet, docs consistency, and L4 execution-contract proofs before any
   GO/NO-GO handoff.

## Constraints

- Do not inspect or edit downstream implementation files until same-wave
  tracker proof exists for this successor wave.
- Do not edit files outside the locked write set.
- Do not edit `mu/programs/*.json`, generated manifests, ratchet baselines,
  Stage0, scheduler seed projections, substrate files, production loader
  defaults, binary/TLV paths, seed checksums, checksum policy outside the two
  named manifest-integrity surfaces, dispatcher/executor/commit/push/PR
  surfaces, Claude files, hidden/local-memory surfaces, or unrelated tooling.
- Do not preserve or introduce a host exception table for algorithm authority.
- Do not infer algorithm authority from seed names, subdirectories, status,
  dependencies, projection ids, scheduler special casing, registry ordering, or
  any other host interpretation.
- Do not make Python or JavaScript smarter than the manifest authority source.
- Do not convert this into a docs-only, control-plane-only, host-only semantic,
  baseline-only, or broad repo-investigation wave.
- Do not use the same-wave pipeline unblocker as runtime authority. It only
  fixes package classification for bounded non-runtime planning packets; it
  does not implement or replace the locked Mu authority successor.

## Stop conditions

Stop with NO-GO if any condition holds:

- Same-wave TASKS.md tracker proof for
  `n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19` is absent
  before source or implementation inspection.
- The successor needs any file outside the locked write set.
- The manifest cannot encode exactly the preserved five-seed accepted set.
- Python or JavaScript keeps a host-owned allowlist or adds a host exception
  table as the source of authorization.
- Python or JavaScript infers authority from names, paths, status,
  dependencies, projection ids, scheduler logic, or any host-only interpretation
  instead of explicit manifest metadata.
- `recurrence.v1.json` compatibility acceptance is lost.
- `rcx_engine_scheduler.v1.json` acceptance or JavaScript scheduler lazy-load
  behavior is lost.
- Rogue seed-map injection, non-authorized registered seeds, prototype-chain
  keys, or malformed/non-boolean authority metadata become accepted.
- Manifest SHA constants in Python and JavaScript do not match the updated
  manifest bytes.
- Host semantics increase, host-authority inventory adds unaccepted authority,
  required parity/focused tests fail, docs consistency fails after packet/docs
  changes, or the L4_STRUCTURAL execution-contract proof fails.

## Acceptance criteria

- The packet contains Scope, Work items, Constraints, Stop conditions,
  Acceptance criteria, and Grounding / Authorization sections.
- The packet records same-wave successor TASKS.md authorization as present and
  does not preserve obsolete absent-tracker evidence as current status.
- Same-wave pipeline unblocker regression passes:

  ```bash
  PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestPhaseBWaveClassResolution --tb=short
  ```

- Same-wave successor tracker proof is present before implementation:

  ```bash
  rg -n "n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19|N3-ENGINE-PIPELINE-RUN-ALGORITHM-MANIFEST-AUTHORITY" TASKS.md
  ```

- Manifest accepted-set proof passes:

  ```bash
  python3 - <<'PY'
  import json
  from pathlib import Path
  manifest = json.loads(Path("mu/seed_registry_manifest.v1.json").read_text())
  allowed = sorted(
      name for name, meta in manifest["seeds"].items()
      if meta.get("authority", {}).get("run_algorithm") is True
  )
  expected = sorted([
      "recurrence.v1.json",
      "recurrence.v2.json",
      "exhaustion.v1.json",
      "fix.v1.json",
      "rcx_engine_scheduler.v1.json",
  ])
  assert allowed == expected, (allowed, expected)
  PY
  ```

- Manifest checksum lockstep proof passes:

  ```bash
  python3 - <<'PY'
  import hashlib
  import re
  from pathlib import Path
  manifest_hash = hashlib.sha256(Path("mu/seed_registry_manifest.v1.json").read_bytes()).hexdigest()
  py_text = Path("mu/host/python/rcx_pi/selfhost/seed_integrity.py").read_text()
  js_text = Path("mu/host/js/core/seed_loader.js").read_text()
  py_hash = re.search(r'SEED_REGISTRY_MANIFEST_SHA256 = \(\s*"([0-9a-f]+)"\s*\)', py_text, re.S).group(1)
  js_hash = re.search(r"SEED_REGISTRY_MANIFEST_SHA256 =\s*'([0-9a-f]+)'", js_text, re.S).group(1)
  assert manifest_hash == py_hash == js_hash, (manifest_hash, py_hash, js_hash)
  print(manifest_hash)
  PY
  ```

- Focused boundary and scheduler proofs pass:

  ```bash
  PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestAlgorithmSeedAllowlist --tb=short
  PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/structural/test_rcx_enginenew_scheduler.py::test_python_run_algorithm_boundary_loads_scheduler_seed_path mu/tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_seed_path_selection --tb=short
  ```

- Ratchet, docs, and L4 execution-contract proofs pass:

  ```bash
  python3 mu/tools/checks/check_host_semantics_ratchet.py --json
  python3 tools/checks/check_host_authority_inventory_ratchet.py
  ./tools/checks/check_docs_consistency.sh
  python3 tools/checks/enforce_l4_execution_contract.py --files TASKS.md mu/host/js/core/seed_loader.js mu/host/js/engine/pipeline.js mu/host/python/rcx_pi/selfhost/engine_pipeline.py mu/host/python/rcx_pi/selfhost/seed_integrity.py mu/seed_registry_manifest.v1.json mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py mu/tests/structural/test_rcx_enginenew_scheduler.py mu/tests/tools/test_phase_b_executor.py mu/tools/executors/phase_b_executor.py reports/control_plane/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19_2026-05-19.md reports/l4_wave_indicators/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19.json --wave-id n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19 --wave-class L4_STRUCTURAL
  ```

## Grounding / Authorization

- TASKS.md authorization: `TASKS.md:380` currently authorizes this successor
  wave under `[NEXT-CODEX-POST-REDTEAM]` as a Phase B pre-commit supervisor
  package with class `L4_STRUCTURAL`, target gate `G8`, workload target
  `host_debt_reduction`, same-wave indicator artifact, and
  `FOUNDER_OVERRIDE:n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19`.
- Current positive tracker evidence:

  ```bash
  rg -n "n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19|N3-ENGINE-PIPELINE-RUN-ALGORITHM-MANIFEST-AUTHORITY" TASKS.md
  # TASKS.md:380 contains the same-wave tracker note.
  ```

- Governing source-lock packet:
  `reports/control_plane/n3-engine-pipeline-run-algorithm-authority-source-prereq-2026-05-19_2026-05-19.md:206-216`
  decides that no existing Mu-owned source derives the complete accepted set and
  permits a bounded L4_STRUCTURAL successor only if explicit manifest authority
  metadata encodes exactly the preserved set without host exception tables or
  host inference.
- Governing source-lock packet:
  `reports/control_plane/n3-engine-pipeline-run-algorithm-authority-source-prereq-2026-05-19_2026-05-19.md:229-360`
  locks the successor write set, proof commands, ratchet expectations, and stop
  conditions copied into this packet.
- Packet-local control-plane authorization:
  `FOUNDER_OVERRIDE:n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19`.
  This line is a wave-bound control-plane override for packet automation; the
  same-wave TASKS.md tracker proof remains the implementation authority.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19`
- Active packet: `reports/control_plane/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19_2026-05-19.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/seed_loader.js`
  - `mu/host/js/engine/pipeline.js`
  - `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
  - `mu/seed_registry_manifest.v1.json`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/structural/test_rcx_enginenew_scheduler.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19_2026-05-19.md`
  - `reports/l4_wave_indicators/n3-engine-pipeline-run-algorithm-manifest-authority-2026-05-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
