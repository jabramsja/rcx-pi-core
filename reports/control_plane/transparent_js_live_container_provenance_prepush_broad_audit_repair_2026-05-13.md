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

## Evidence

- Exact 8-failure repro set:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/engine/test_normalization_roundtrip.py::TestF43JsNormalizeParity::test_js_invalid_type_tag_roundtrips tests/engine/test_normalization_roundtrip.py::TestF43JsNormalizeParity::test_js_valid_type_tags_still_work tests/structural/test_engine_pipeline_discipline.py::TestJsEnginePipelineShapeGovernance::test_dependency_direction_and_boundary_authority tests/l4_gates/test_terminal_classification_parity_gate.py::TestJSCacheHardening::test_mutating_exported_set_does_not_affect_classification tests/l4_gates/test_terminal_classification_parity_gate.py::TestJSCacheHardening::test_clear_tc_cache_rebuilds_correctly tests/l4_gates/test_redteam_hardening_gate.py::TestDenormalizeTypedPathGuard::test_list_typed_path_primitive_tail tests/l4_gates/test_redteam_hardening_gate.py::TestDenormalizeTypedPathGuard::test_dict_typed_path_primitive_tail tests/l4_gates/test_redteam_hardening_gate.py::TestMatchSubstituteEntryValidation::test_match_accepts_valid_mu --tb=short -p no:cacheprovider`
  exits 0 with `8 passed in 0.68s`.
- Affected file suite:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/engine/test_normalization_roundtrip.py tests/structural/test_engine_pipeline_discipline.py tests/l4_gates/test_terminal_classification_parity_gate.py tests/l4_gates/test_redteam_hardening_gate.py --tb=short -p no:cacheprovider`
  exits 0 with `211 passed in 22.69s`.

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
- Tracker note sha256: `8ed0c475a5d91fabd36f9f002422c910680eeec183ce311ee078e71504a49c95`
- Indicator artifact: `reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q tests/engine/test_normalization_roundtrip.py::TestF43JsNormalizeParity::test_js_invalid_type_tag_roundtrips tests/engine/test_normalization_roundtrip.py::TestF43JsNormalizeParity::test_js_valid_type_tags_still_work tests/structural/test_engine_pipeline_discipline.py::TestJsEnginePipelineShapeGovernance::test_dependency_direction_and_boundary_authority tests/l4_gates/test_terminal_classification_parity_gate.py::TestJSCacheHardening::test_mutating_exported_set_does_not_affect_classification tests/l4_gates/test_terminal_classification_parity_gate.py::TestJSCacheHardening::test_clear_tc_cache_rebuilds_correctly tests/l4_gates/test_redteam_hardening_gate.py::TestDenormalizeTypedPathGuard::test_list_typed_path_primitive_tail tests/l4_gates/test_redteam_hardening_gate.py::TestDenormalizeTypedPathGuard::test_dict_typed_path_primitive_tail tests/l4_gates/test_redteam_hardening_gate.py::TestMatchSubstituteEntryValidation::test_match_accepts_valid_mu --tb=short -p no:cacheprovider && PYTHONHASHSEED=0 python3 -m pytest -q tests/engine/test_normalization_roundtrip.py tests/structural/test_engine_pipeline_discipline.py tests/l4_gates/test_terminal_classification_parity_gate.py tests/l4_gates/test_redteam_hardening_gate.py --tb=short -p no:cacheprovider && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13`.
- Evidence delta: (1) Broad pre-push failed after local parent commit `b36f18d3` with `8 failed, 6890 passed, 18 skipped in 348.19s`. (2) Raw JS compound fixtures were converted to existing Stage0 `muCopy` Mu-origin fixtures without weakening the public JS Mu boundary. (3) JS engine dependency inventory now records the intentional `container_factory` producer dependency.
- Evidence handles:
  - `affected_suite`: `exit=0; four affected files 211 passed in 22.69s`
  - `authority`: `exit=0; 311 total / 217 authority; no new sites`
  - `docs`: `exit=0; check_docs_consistency.sh all checks passed`
  - `focused_repro`: `exit=0; exact 8-failure repro set 8 passed in 0.68s`
  - `host_semantics`: `exit=0; passed=true; no increases/decreases`
  - `indicator`: `reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json`
  - `l4_staged`: `exit=0; L4_ENABLER compliant; 8 changed files; 0 runtime files`
  - `prepush_failure`: `pre-push-fast audit_fast failed after b36f18d3 with 8 failed, 6890 passed, 18 skipped in 348.19s`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/engine/test_normalization_roundtrip.py`
  - `mu/tests/l4_gates/test_redteam_hardening_gate.py`
  - `mu/tests/l4_gates/test_terminal_classification_parity_gate.py`
  - `mu/tests/structural/test_engine_pipeline_discipline.py`
  - `reports/control_plane/transparent_js_live_container_provenance_implement_2026-05-13.md`
  - `reports/control_plane/transparent_js_live_container_provenance_prepush_broad_audit_repair_2026-05-13.md`
  - `reports/l4_wave_indicators/transparent-js-live-container-provenance-prepush-broad-audit-repair-2026-05-13.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
