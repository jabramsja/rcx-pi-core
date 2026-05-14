# N3-Rcx-Load-Projection-Loader-Production-Adapter-Test-Prereq-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Decision: GO for a bounded prerequisite test-surface Phase B; NO-GO for production loader implementation.
FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14
Purpose: Lock the missing production/parity test prerequisite for the existing
JSON `rcx_load` / `projection_loader` boundary before any later production
adapter implementation packet.

## Scope

This packet authorizes only a bounded test-only/control-plane Phase B for the
N3 `rcx_load` / `projection_loader` production adapter prerequisite.

Allowed Phase B write set:
- `mu/tests/engine/test_seed_integrity.py`
- `mu/tests/structural/test_projection_loader.py`
- `mu/tests/parity/test_seed_loading_parity.py`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
- `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
- `TASKS.md` same-wave tracker note for this wave
- `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`

Read-only grounding for Phase B:
- Predecessor control packets and doctrine lines cited in Grounding /
  Authorization below.
- Current production loader paths only as grounding for test binding:
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py`,
  `mu/host/python/rcx_pi/selfhost/projection_loader.py`,
  `mu/host/js/core/seed_loader.js`, and `mu/host/js/cli/main.js`.
- Existing tests named by the predecessor packet; Phase B must inspect
  assertions and production imports, not filenames only.

This rewrite turn is narrower than Phase B: it may edit this packet only.

## Work Items

1. In `mu/tests/engine/test_seed_integrity.py`, add or strengthen focused
   tests that bind Python seed integrity coverage to the production JSON loader
   boundary, including deterministic checksum / structure validation and at
   least one fail-closed malformed seed or projection control.
2. In `mu/tests/structural/test_projection_loader.py`, add or strengthen
   structural projection-loader tests that exercise the production Python
   `projection_loader` path for current JSON seed images without introducing a
   binary TLV loader, seed migration, or new production behavior.
3. In `mu/tests/parity/test_seed_loading_parity.py`, add or strengthen
   Python/JavaScript parity cases for the same valid and malformed JSON
   seed/projection images so the future adapter cannot be justified from a
   Python-only or JavaScript-only proof.
4. In `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`, add or
   strengthen the `TestJsSeedLoaderMalformedProjection` and
   `TestF2ProductionBindingLock` coverage so malformed JS projection loading
   fails closed and the future production-boundary adapter remains bound to
   production loader paths rather than a research-only D010 artifact.
5. Preserve this packet as the Phase A authority surface, add a detector-visible
   same-wave `TASKS.md` tracker note if Phase B proceeds, and collect the
   same-wave indicator artifact at
   `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`.

No blocking review evidence proves any of these work items already landed in
current code. If Phase B code truth proves an item is already covered, Phase B
must remove that item from pending implementation and record the exact
file:line proof instead of re-listing it as unresolved.

## Constraints

- Do not implement production loader behavior in this wave.
- Do not edit `mu/host/python/rcx_pi/selfhost/seed_integrity.py`,
  `mu/host/python/rcx_pi/selfhost/projection_loader.py`,
  `mu/host/js/core/seed_loader.js`, or `mu/host/js/cli/main.js`.
- Do not edit production seed files, seed-format migration tooling, binary TLV
  production loader code, ratchet baselines, host-oracle code, hidden/local
  memory, Codex-local binary/cache files, or Claude-related files.
- Do not claim N3 closure, D010 production readiness, full L4 completion, or
  production reduction of `projection_loader`.
- Do not move Mu semantic authority into Python or JavaScript host loaders.
- Do not use `mu/tests/research/test_d010_h5_projection_loader_binary.py` as
  the sole production proof.
- Do not widen this packet into broad host-surface reduction; N3 remains active
  and future reductions require separate bounded packets.

## Stop Conditions

- Stop before Phase B implementation if the required proof would need any
  forbidden production loader, production seed, binary TLV loader, migration, or
  host-oracle write.
- Stop if the candidate test surface cannot bind to production loader paths with
  explicit imports / calls and at least one fail-closed or negative-control case
  where feasible.
- Stop if parity proof would be Python-only, JavaScript-only, or would leave a
  substrate split in expected loader behavior.
- Stop if current code truth proves the candidate is already landed, obsolete,
  or narrower than this packet wording implies; rewrite the handoff as a
  no-go / narrower next-wave packet with exact evidence instead.
- Stop if focused parity checks, host-semantics ratchet, authority-inventory
  ratchet, rollback expectations, or proof limits cannot be stated before code
  changes.
- Stop if same-wave control-surface authority, tracker evidence, and indicator
  handoff cannot be made detector-visible before commit automation.
- Stop if the implementation attempts to close N3, claim D010 production
  readiness, or infer production adapter readiness from research-only D010
  evidence.

## Acceptance Criteria

- This packet contains concrete Phase A sections for Scope, Work Items,
  Constraints, Stop Conditions, Acceptance Criteria, and Grounding /
  Authorization, plus the wave-bound
  `FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14`.
- Phase B touches only the allowed write set and leaves all forbidden production
  loader, seed, migration, ratchet-baseline, host-oracle, hidden/local memory,
  Codex-local, and Claude-related files unchanged.
- The focused tests bind to current production loader paths and include
  fail-closed / negative-control coverage where feasible; passing filename-only
  assertions are not sufficient.
- The parity surface proves the same loader-boundary expectations across Python
  and JavaScript for current JSON seed/projection loading.
- Any implementation handoff runs and records:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/engine/test_seed_integrity.py \
  mu/tests/structural/test_projection_loader.py \
  mu/tests/parity/test_seed_loading_parity.py \
  mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestJsSeedLoaderMalformedProjection \
  mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestF2ProductionBindingLock
```

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/parity/test_parity_python.py \
  mu/tests/parity/test_js_parity_automated.py::TestJSTestSuitePasses \
  mu/tests/parity/test_js_parity_automated.py::TestCrossSubstrateParity
```

```bash
node mu/host/js/eval_step.js
```

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14
```

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
```

```bash
python3 tools/checks/check_host_authority_inventory_ratchet.py
```

```bash
./tools/checks/check_docs_consistency.sh
```

- Phase B adds a detector-visible same-wave `TASKS.md` tracker note and
  same-wave indicator artifact before commit automation if it stages an
  implementation package.
- Acceptance does not authorize production loader behavior, does not close N3,
  and does not convert D010 research evidence into production readiness.

## Grounding / Authorization

- `TASKS.md:342` authorizes the predecessor
  `n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14`
  control packet as `NEXT-CODEX-POST-REDTEAM` / `L4_ENABLER` with same-wave
  override and indicator metadata.
- `TASKS.md:343` authorizes the predecessor
  `n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14`
  control packet as `NEXT-CODEX-POST-REDTEAM` / `L4_ENABLER` with same-wave
  override and indicator metadata.
- Exact current-wave lookup
  `rg -n "n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14" TASKS.md`
  returned no match, so this packet carries the wave-bound
  `FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14`
  and Phase B must add the same-wave tracker note before commit automation.
- `reports/control_plane/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14_2026-05-14.md:62-78`
  names the future test-only write set and forbids production loader files;
  `:161-175` preserves no-production and no-D010-production-readiness
  constraints; `:187-200` records production implementation stop conditions and
  the future prerequisite route; `:203-242` records validation and handoff
  expectations; `:262-301` records proof limits and acceptance boundaries.
- `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md:55-70`
  requires a bounded test-surface lock before any production adapter slice;
  `:118-134` stops implementation when exact production/test write sets and
  proof limits are missing; `:154-162` requires exact write set, focused tests,
  parity checks, ratchets, rollback path, proof limits, and D010 boundaries;
  `:255-263` records the missing production/parity test surface as the no-go
  gap for production implementation.
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175`
  keeps N3 active as broad host-surface boundary work and requires separate
  bounded packets that narrow bootstrap assumptions rather than moving semantic
  authority into Python or JavaScript host code.
- `mu/docs/core/L4MicroAbi.v0.md:29-45` defines `rcx_load(image_bytes)` and
  maps the current implementation to `seed_integrity.py` plus
  `projection_loader.py`; `:105-109` binds `rcx_load` to loader integrity
  proof; `:120-123` places `projection_loader` in Boot0; `:159-162` records
  `rcx_load` as JSON/Python `json.load` with binary-format reduction classified
  but production path unchanged.
- `mu/docs/core/L4ExitChecklist.v0.md:32` lists `projection_loader` as the
  load-and-verify seed JSON primitive; `:188` records D010 as research-only with
  production `projection_loader` unchanged; `:205-216` requires separate
  productionization gates for any production reduction claim, including
  int-range policy, NaN/Inf policy, JS TLV decoder parity, seed migration
  tooling, and integrity-chain policy; `:226-232` keeps JSON replacement
  reducible but research-only for production.
- `mu/docs/core/Boot0Architecture.v0.md:67-74` lists `projection_loader` as a
  Boot0 primitive that loads JSON seeds through
  `seed_integrity.py:load_verified_seed()` and notes that alternative formats
  may evolve later without changing semantics.

## Phase B Implementation Handoff

Phase B implementation is test-only/control-plane only.

Changed-file scope:
- `mu/tests/engine/test_seed_integrity.py`
- `mu/tests/structural/test_projection_loader.py`
- `mu/tests/parity/test_seed_loading_parity.py`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
- `TASKS.md`
- `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
- `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`

Implementation summary:
- Python integrity tests now bind the current JSON `kernel.v1.json` load path to
  deterministic checksum and ordered projection-ID validation, with tampered and
  malformed projection fail-closed controls through `load_verified_seed()`.
- Projection-loader structural tests now compare `make_projection_loader()`
  output against `load_verified_seed(get_seed_path(...))` for current JSON seed
  images and prove the factory fails closed when the verified seed structure is
  malformed.
- Parity tests now exercise production Python and JS loader calls for the same
  valid `rcx_engine.v1.json` seed and the same tampered / unknown malformed
  JSON seed controls.
- L4 gate tests now strengthen JS malformed projection source/behavior locks
  and assert the coverage remains bound to production `seed_loader.js` and
  `cli/main.js`, not research-only D010 artifacts.

Proof limits:
- No production loader, production seed, migration, binary TLV loader,
  ratchet-baseline, host-oracle, hidden/local memory, Codex-local, or
  Claude-related file is authorized or changed.
- This packet does not close N3, does not claim D010 production readiness, and
  does not implement or prove a production adapter.

Pipeline rule: use dispatcher-owned Phase A -> Phase B -> pre-commit supervisor
-> commit executor flow. If a manual pipeline repair is required, pair it with
same-wave mechanical automation in dispatcher, builder, recovery, commit, or
pre-commit, or leave a precise next-wave automation packet. End visible
summaries with: Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/engine/test_seed_integrity.py`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `mu/tests/structural/test_projection_loader.py`
  - `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2d3f2c0de10da19a4b3bf9d652ff892fb85d47ca501f98444dbfbd2d2bb91ee6`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/engine/test_seed_integrity.py mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py mu/tests/parity/test_seed_loading_parity.py mu/tests/structural/test_projection_loader.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/engine/test_seed_integrity.py`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `mu/tests/structural/test_projection_loader.py`
  - `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
