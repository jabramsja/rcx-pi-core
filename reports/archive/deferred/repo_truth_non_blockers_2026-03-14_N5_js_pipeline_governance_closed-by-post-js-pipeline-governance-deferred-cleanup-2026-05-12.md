# Closed Deferred Non-Blocking Finding: repo truth N5 JS pipeline governance

Source: `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
Closed by: `post-js-pipeline-governance-deferred-cleanup-2026-05-12`
Class: L4_ENABLER
Target Gate: G8
Status: CLOSED_BY_POST_JS_PIPELINE_GOVERNANCE_DEFERRED_CLEANUP

## Closure Evidence

- The predecessor wave `js-engine-pipeline-shape-governance-test-2026-05-12`
  landed the focused structural guard in
  `mu/tests/structural/test_engine_pipeline_discipline.py`.
- `TASKS.md` records the predecessor same-wave tracker note with
  `FOUNDER_OVERRIDE:js-engine-pipeline-shape-governance-test-2026-05-12` and
  the evidence command
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/structural/test_engine_pipeline_discipline.py::TestJsEnginePipelineShapeGovernance::test_dependency_direction_and_boundary_authority --tb=short`.
- This cleanup removes the N5 live advisory from the active repo-truth packet
  and leaves N1 VM coverage bookkeeping, N3 broad host-surface boundary, and
  transparent JS Proxy provenance active.
- No runtime, Stage0, seed, scheduler, registry, parity, production `/mu`,
  host-oracle, or Claude-related implementation work is authorized by this
  archive record.

## Historical N5 Text

### N5. `pipeline.js` still has no explicit size/shape governance

- **Outcome:** retained live governance advisory.
- **Governing route:** `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`.
- **Current proof gap:** the completed Phase A packet reproduced that
  `mu/host/js/engine/pipeline.js` remains a 1160-line engine pipeline and that
  scoped docs/tests do not define a sufficient module ownership or
  decomposition contract.
- **Hard stop before implementation:** no JS runtime, Stage0, coverage, Proxy
  provenance, scheduler, seed, or module-split implementation is authorized by
  this source packet or by the completed Phase A governance packet.
- **Doctrine boundary:** future governance must preserve seed-driven boundary
  operations and must not move Mu semantic decisions into JavaScript module
  structure.

- the file remains large (`wc -l` reports 1160 lines)
- there is no explicit cap or decomposition contract comparable to the JS
  bootstrap-core governance gate
**Why deferred:** pipeline.js is the JS engine pipeline - it handles boundary
dispatch, ontology promotion, algorithm routing, and evidence collection. These
are logically related functions that share state (seedProjectionMap,
kernelProjections). Splitting into smaller files would create circular
dependency issues or require a module loader. The file is well-sectioned with
clear function boundaries. A LOC cap without decomposition guidance would be
arbitrary. **Target packet:**
`reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`.
