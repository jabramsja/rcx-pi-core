# Transparent JS Live Container Provenance - Pre-Push Broad Audit Repair

Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13
Class: L4_ENABLER
Target gate: G8
Parent wave: transparent-js-live-container-provenance-implementation-2026-05-13

## Scope

This is a bounded pre-push repair for the parent transparent JS live container
provenance implementation. It does not change runtime behavior. It updates only
test/control surfaces that the broad pre-push audit proved were stale against
the strengthened JS Mu compound provenance boundary:

- `mu/tests/engine/test_normalization_roundtrip.py`
- `mu/tests/l4_gates/test_redteam_hardening_gate.py`
- `mu/tests/l4_gates/test_terminal_classification_parity_gate.py`
- `mu/tests/structural/test_engine_pipeline_discipline.py`
- `reports/control_plane/transparent_js_live_container_provenance_implement_2026-05-13.md`
- `tools/checks/derive_wave_id.sh`
- `mu/tests/tools/test_wave_id_derivation.py`
- `TASKS.md`
- `reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json`

## Failure Evidence

After local parent repair commit `b36f18d3`, `pre-push-fast` ran
`audit_fast.sh` and failed with:

`8 failed, 6890 passed, 18 skipped in 348.19s`

Representative root-cause evidence:

- `tests/engine/test_normalization_roundtrip.py::TestF43JsNormalizeParity` raw
  JS compound fixtures hit `normalize.js:165`:
  `normalize: compound value lacks trusted Mu provenance`.
- `tests/l4_gates/test_terminal_classification_parity_gate.py::TestJSCacheHardening`
  raw JS terminal-shape fixtures hit `bootstrap_core.js:297`:
  `Invalid Mu input to step()`.
- `tests/l4_gates/test_redteam_hardening_gate.py::TestMatchSubstituteEntryValidation`
  raw JS compound fixtures hit `bootstrap_core.js:99`:
  `Invalid Mu pattern in match()`.
- `tests/structural/test_engine_pipeline_discipline.py::TestJsEnginePipelineShapeGovernance`
  still had the pre-provenance engine dependency inventory and did not include
  the intentional `container_factory` producer dependency.

## Repair

- Convert only the affected JS test fixtures to existing Stage0 `muCopy(...,
  true, ...)` Mu-origin values.
- Keep the strengthened public JS boundary intact; do not add a public raw
  object admission path.
- Update the structural engine dependency inventory to include the intentional
  `../core/container_factory` dependency in `kernel.js`, `pipeline.js`, and
  `routing.js`.
- Record the parent packet evidence append so the pre-push failure is not hidden
  behind generic recovery output.
- Mechanically repair `tools/checks/derive_wave_id.sh` so full-range L4 checks
  on an L4_ENABLER continuation branch with runtime files bind to the packet's
  `Parent wave:` structural wave instead of incorrectly binding the range to
  the enabler note.

## Evidence

- Exact 8-failure repro set:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/engine/test_normalization_roundtrip.py::TestF43JsNormalizeParity::test_js_invalid_type_tag_roundtrips tests/engine/test_normalization_roundtrip.py::TestF43JsNormalizeParity::test_js_valid_type_tags_still_work tests/structural/test_engine_pipeline_discipline.py::TestJsEnginePipelineShapeGovernance::test_dependency_direction_and_boundary_authority tests/l4_gates/test_terminal_classification_parity_gate.py::TestJSCacheHardening::test_mutating_exported_set_does_not_affect_classification tests/l4_gates/test_terminal_classification_parity_gate.py::TestJSCacheHardening::test_clear_tc_cache_rebuilds_correctly tests/l4_gates/test_redteam_hardening_gate.py::TestDenormalizeTypedPathGuard::test_list_typed_path_primitive_tail tests/l4_gates/test_redteam_hardening_gate.py::TestDenormalizeTypedPathGuard::test_dict_typed_path_primitive_tail tests/l4_gates/test_redteam_hardening_gate.py::TestMatchSubstituteEntryValidation::test_match_accepts_valid_mu --tb=short -p no:cacheprovider`
  exits 0 with `8 passed in 0.68s`.
- Affected file suite:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/engine/test_normalization_roundtrip.py tests/structural/test_engine_pipeline_discipline.py tests/l4_gates/test_terminal_classification_parity_gate.py tests/l4_gates/test_redteam_hardening_gate.py --tb=short -p no:cacheprovider`
  exits 0 with `211 passed in 22.69s`.
- Wave-id derivation regression:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_wave_id_derivation.py --tb=short -p no:cacheprovider`
  exits 0 with `5 passed in 1.81s`.
- Current branch full-range derivation:
  `source tools/checks/derive_wave_id.sh "$(git rev-parse --abbrev-ref HEAD)" --range origin/dev...HEAD; printf '%s\n' "$WAVE_ID_FLAG"`
  prints `--wave-id=transparent-js-live-container-provenance-implementation-2026-05-13`.
- Full-range L4 after derivation repair:
  `python3 tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD --wave-id=transparent-js-live-container-provenance-implementation-2026-05-13`
  exits 0 with `L4_STRUCTURAL compliant`.

## PR CI Repair Append

After local commit `003253b5` pushed PR #943, required CI failed with four
checks:

- `orbit-svg` and `orbit-index` failed before repo checks at the Graphviz
  install step with exit code `124`; both logs show `timeout 120s sudo apt-get
  install -y graphviz`.
- `test` and `green-gate` failed the same seven JS parity tests. The scheduler
  failures hit `mu/host/js/core/types.js:374` from
  `mu/host/js/engine/pipeline.js:158` with `runSubAlgorithm: value is not
  valid Mu`.
- The VM-ordering probe failed because `mu/host/js/tests/self_tests.js` now
  wraps the shared fixture constants in `trustTestMu(...)`, while the probe
  parser still expected a raw object or list literal.
- The JS re-entry validation positive fixture still passed a raw `{}` input to
  `validateReentryPayload`, which now correctly requires trusted Mu compound
  provenance.

Repair:

- Keep runtime JS Mu provenance strict; do not add a public raw-object
  admission path.
- Convert the affected direct JS parity probes to construct trusted fixtures via
  existing Stage0 `muCopy(..., true, ...)`.
- Teach the VM-ordering probe parser to read the existing `trustTestMu(...)`
  wrapper in `self_tests.js` while still feeding a trusted local probe fixture.
- Keep the Graphviz install bounded, but widen the bound to
  `timeout-minutes: 8`, add `Acquire::Retries=3`, and use `timeout 300s` for
  each apt command.

Evidence:

- Exact PR CI failure set:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_seed_path_selection tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_negative_order_rejection tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_fail_closed_pair_rejection tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_longer_pool_rejection tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_malformed_tail_rejection tests/parity/test_js_vm_bridge_parity.py::TestJsBridgeVmOrderingE2E::test_live_vm_kernel_path_depends_on_kernel_bridge_match_subst_order tests/parity/test_boot1_shadow_parity.py::TestJsReentryPayloadValidation::test_js_accepts_valid_payload --tb=short -p no:cacheprovider`
  exits 0 with `7 passed in 10.37s`.
- Affected parity surfaces:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/parity/test_rcx_engine_scheduler_parity.py tests/parity/test_js_vm_bridge_parity.py::TestJsBridgeVmOrderingE2E tests/parity/test_boot1_shadow_parity.py::TestJsReentryPayloadValidation --tb=short -p no:cacheprovider`
  exits 0 with `14 passed in 10.70s`.
- Workflow parse/readback:
  `python3 - <<'PY' ... PY` parsed `.github/workflows/fixture_gates.yml` and
  printed `fixture_gates.yml graphviz install bounds parsed OK`.
- Whitespace check: `git diff --check` exits 0.

## Pre-Push Range Binding Fallback Repair Append

After local commit `5816d918`, commit executor pre-push failed before push at
the L4 range gate. Root-cause evidence:

- `pre-push-fast` ran `tools/checks/enforce_l4_execution_contract.py --range
  origin/dev...HEAD` and reported `Wave class: L4_ENABLER`, `Changed files:
  44`, `Runtime files: 13`, then rejected runtime files under the enabler
  class.
- `TASKS.md` held the canonical enabler tracker note without `Packet:` while
  the later same-wave PR CI append held `Packet:
  reports/control_plane/transparent_js_live_container_provenance_prepush_broad_audit_repair_2026-05-13.md`.
- Reproducing `source tools/checks/derive_wave_id.sh "$BRANCH" --range
  origin/dev...HEAD` before this repair printed
  `--wave-id=transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13`
  instead of the packet-declared parent structural wave.

Mechanical repair:

- `derive_wave_id.sh` now falls back from the canonical tracker-note line to a
  same-wave `Packet:` append line before reading `Parent wave:`.
- Commit handoff default tracker-note generation now includes `Packet:` when
  `tracked_packet` is present, preventing future routed follow-up notes from
  dropping the packet reference.
- Regression coverage locks both behaviors.

Evidence:

- `PYTHONHASHSEED=0 python3 -m pytest -q
  mu/tests/tools/test_wave_id_derivation.py
  mu/tests/tools/test_commit_executor_receipt.py::test_build_commit_handoff_default_tracker_note_includes_tracked_packet
  --tb=short -p no:cacheprovider` exits 0 with `7 passed in 2.43s`.
- `python3 -m py_compile mu/tools/executors/commit_executor.py
  mu/tools/executors/tracker_sync_note.py` exits 0.
- `git diff --check` exits 0.
- Reproducing the full L4 range gate now exits 0 with `Wave class:
  L4_STRUCTURAL`, `Changed files: 44`, `Runtime files: 13`, and
  `L4_STRUCTURAL compliant`.

## Stop Conditions

- Stop if any runtime/substrate file enters this enabler wave.
- Stop if any repair adds a public JS host-object admission path or a
  `CONTRABAND_OK` bypass.
- Stop if staged L4 does not classify this package as `L4_ENABLER`.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13`
- Active packet: `reports/control_plane/transparent_js_live_container_provenance_prepush_broad_audit_repair_2026-05-13.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2246738fe7fce159886ff8639fd9fd376b10a94c59cb8a3b448392464d3bfa28`
- Indicator artifact: `reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_wave_id_derivation.py`.
- Evidence delta: (1) Routed commit handoff scopes 8 wave-owned file(s). (2) Evidence gate exercises 2 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_wave_id_derivation.py`
  - `mu/tools/checks/derive_wave_id.sh`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/tracker_sync_note.py`
  - `reports/control_plane/transparent_js_live_container_provenance_prepush_broad_audit_repair_2026-05-13.md`
  - `reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
