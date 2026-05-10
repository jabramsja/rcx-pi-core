# JS Engine Pipeline Shape Governance

Date: 2026-05-10
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: js-engine-pipeline-shape-governance-2026-05-09
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural governance
Source authorization: routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md
## Scope

- Phase A is a governance/design packet only for the JS engine pipeline shape
  question routed by `[NEXT-CODEX-POST-REDTEAM]`.
- Files and directories in scope for inspection:
  - `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
  - `TASKS.md` line 514 for the same-wave tracker authorization
  - `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
    N5
  - `mu/host/js/engine/pipeline.js`
  - `mu/host/js/engine/`
  - `mu/host/js/tests/`
  - `mu/tests/engine/`
  - `mu/tests/l4_gates/`
  - `mu/tests/structural/`
- The Phase A question is whether the N5 observation is still a live
  governance gap, stale because sufficient shape ownership already exists, or
  a design-only non-action.

## Work Items

1. Reproduce the current `mu/host/js/engine/pipeline.js` file size and
   module-boundary facts from the scoped files/directories.
2. Check whether scoped docs or tests already define a sufficient pipeline
   shape/decomposition ownership contract.
3. Decide whether the right next step is a decomposition design, a no-cap
   rationale with explicit ownership boundaries, or a focused governance test.
4. If later implementation is warranted, split it from runtime semantics and
   state how the work preserves seed-driven boundary operations rather than
   moving Mu decisions into JavaScript module structure.

## Constraints

- No JS engine pipeline runtime behavior changes in Phase A.
- No arbitrary LOC cap without a decomposition or ownership contract.
- Do not split modules in a way that adds host bootstrap assumptions, circular
  loaders, or JS-only semantic dispatch.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if current docs/tests already define a sufficient pipeline shape contract.
- Stop if a proposed change would mix governance with coverage, Stage0, or
  Proxy provenance work.
- Stop if implementation would touch runtime behavior before a locked Phase A
  packet exists.

## Acceptance Criteria

- Phase A records whether N5 is a live governance gap, a stale observation, or
  a design-only non-action.
- Phase A names the scoped docs/tests that prove any stale-observation or
  no-action decision.
- Any later implementation packet either narrows JS bootstrap assumptions or
  preserves the current Mu-programmed semantics while adding explicit module
  ownership/governance.
- No runtime implementation occurs from this triage route.

## Grounding / Authorization

- Source advisory:
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` N5.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- TASKS.md authorization:
  `TASKS.md` line 514 routes
  `[NEXT-CODEX-POST-REDTEAM]` to
  `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
  as `Class: L4_ENABLER`, `Category: /mu structural governance`, and
  `Status: Routed - Phase A required before implementation`.
- Authorization: `FOUNDER_OVERRIDE:js-engine-pipeline-shape-governance-2026-05-09`.
- Governing packet:
  `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`.

## Phase A Decision

N5 is a live governance gap, not a stale observation and not a design-only
non-action. Current scoped tests and docs lock behavior, seed-derived boundary
dispatch, pipeline entry/return shape, and bootstrap-core budgets, but they do
not define a sufficient JS engine pipeline shape/decomposition ownership
contract.

The right next step is a focused governance-test packet, not a runtime
decomposition from this route. That packet should add an explicit ownership
contract for the existing JS engine module boundaries before any LOC cap or file
split is proposed.

No arbitrary `pipeline.js` LOC cap is authorized by this packet. No JS runtime,
Stage0, coverage, Proxy provenance, scheduler, seed, or module-split
implementation is authorized by this packet.

## Phase B Implementation Evidence

Reproduced size/module facts:

- `wc -l mu/host/js/engine/pipeline.js` exits 0 with
  `1160 mu/host/js/engine/pipeline.js`.
- `find mu/host/js/engine -maxdepth 1 -type f -print | sort` exits 0 and
  lists only:
  - `mu/host/js/engine/kernel.js`
  - `mu/host/js/engine/pipeline.js`
  - `mu/host/js/engine/routing.js`
- `mu/host/js/engine/pipeline.js:3` through `mu/host/js/engine/pipeline.js:9`
  names the file as the RCX Engine Pipeline and lists the module's public
  responsibilities/dependencies.
- `mu/host/js/engine/pipeline.js:29` through `mu/host/js/engine/pipeline.js:72`
  derives boundary operations from `rcx_engine.v1.json`; `:207` through `:299`
  contains boundary handlers and the dispatch map.
- `mu/host/js/engine/pipeline.js:780` through `mu/host/js/engine/pipeline.js:821`
  owns ontology evidence collection, while `:870` through `:876` starts the
  engine-pipeline host orchestrator boundary.
- `mu/host/js/engine/pipeline.js:1144` through `mu/host/js/engine/pipeline.js:1160`
  exports the current pipeline surface, including boundary dispatch helpers,
  recurrence hashing, ontology helpers, and both engine pipeline entry points.
- `mu/host/js/engine/kernel.js:3` through `mu/host/js/engine/kernel.js:8`
  defines the JS engine kernel module as kernel orchestration, not bootstrap
  primitives; `:23` through `:27` states the Stage0 VM kernel step is pure JS
  execution with no JS coverage system.
- `mu/host/js/engine/routing.js:3` through `mu/host/js/engine/routing.js:12`
  defines routing as the hemisphere/metabolization chain and depends on
  `engine/pipeline.js` plus `engine/kernel.js`.

Scoped docs/tests checked:

- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:43`
  through `:46` preserves N5 as active because `pipeline.js` remains a large
  single engine pipeline file with no decomposition contract. The detailed N5
  section at `:99` through `:110` says the file handles boundary dispatch,
  ontology promotion, algorithm routing, and evidence collection, and warns
  that a LOC cap without decomposition guidance would be arbitrary.
- `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md:115`
  routes N5 because `wc -l` reports 1160 and the active packet has no
  decomposition contract.
- `mu/tests/l4_gates/test_bootstrap_core_carveout_gate.py:4` through `:10`,
  `:59` through `:69`, and `:193` through `:201` prove explicit LOC budgets for
  `bootstrap_core.js` and the `eval_step.js` shim, plus inline-test discipline
  for runtime modules. They do not define a `pipeline.js` cap or ownership
  contract.
- `mu/tests/structural/test_engine_pipeline_discipline.py:1` through `:20`
  states the checker proves pipeline callsite inventory, observer schema,
  defaults, and cross-substrate result keys, and explicitly does not prove
  semantic correctness. Later sections lock Python pipeline signatures and
  return shapes, not JS module decomposition ownership.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py:7` through `:9`
  proves boundary-operation dispatch is seed-derived; `:160` through `:220`
  locks handler-map dispatch/source shape for `serviceBoundaryEffect`. This is
  boundary authority evidence, not module-size or decomposition governance.
- `mu/tests/l4_gates/test_intermediate_validation_lock_gate.py:82` through
  `:125`, `mu/tests/l4_gates/test_engine_transition_gate.py:192` through `:215`,
  and `mu/tests/l4_gates/test_w1_gate_blindness_gate.py:78` through `:96` lock
  focused behavioral/source invariants inside `pipeline.js`; they do not assign
  ownership boundaries for splitting or retaining the module.
- `mu/host/js/tests/self_tests.js:10` through `:17` imports only
  `hashTraceForRecurrence` from `engine/pipeline.js`, which is an API usage fact
  rather than a shape/decomposition contract.

## Required Follow-Up Boundary

A later implementation packet, if authorized, must be governance-only unless a
separate runtime packet is explicitly locked. The focused governance test should
preserve the current dependency direction:

- `routing.js` may depend on `pipeline.js` and `kernel.js`.
- `pipeline.js` may depend on `kernel.js` and `core/*`.
- `kernel.js` must not depend on `pipeline.js` or `routing.js`.
- Any extracted helper module must not add a host bootstrap loader, circular
  dependency, or JS-only semantic dispatch.

The ownership contract should record that Mu-programmed semantics remain in the
seed/projection layer. JavaScript module structure may own host boundary
servicing, validation, orchestration, and evidence collection only as explicit
bootstrap boundaries; it must not become the authority for operation selection,
terminal semantics, ontology promotion semantics, or Stage0 behavior.

Later decomposition is acceptable only if it is mechanically semantics-neutral
and keeps boundary operations seed-derived from `rcx_engine.v1.json`. Otherwise,
the current single-file pipeline should remain with an explicit no-cap rationale
and named ownership sections rather than an arbitrary size limit.

## Validation Used

- `wc -l mu/host/js/engine/pipeline.js`
- `find mu/host/js/engine -maxdepth 1 -type f -print | sort`
- `rg -n "pipeline|pipeline\\.js|decompos|shape|ownership|module|seed-driven|seed driven" mu/host/js/tests mu/tests/engine mu/tests/l4_gates mu/tests/structural reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `js-engine-pipeline-shape-governance-2026-05-09`
- Active packet: `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
- Indicator artifact: `reports/l4_wave_indicators/js-engine-pipeline-shape-governance-2026-05-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
  - `reports/l4_wave_indicators/js-engine-pipeline-shape-governance-2026-05-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `js-engine-pipeline-shape-governance-2026-05-09`
- Active packet: `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `593f21c355e7a2f0ee8903ec4e3c600f3802d7e4f81fab8bbc72c5aa2af598c7`
- Indicator artifact: `reports/l4_wave_indicators/js-engine-pipeline-shape-governance-2026-05-09.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id js-engine-pipeline-shape-governance-2026-05-09 --output reports/l4_wave_indicators/js-engine-pipeline-shape-governance-2026-05-09.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/js-engine-pipeline-shape-governance-2026-05-09.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
  - `reports/l4_wave_indicators/js-engine-pipeline-shape-governance-2026-05-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
