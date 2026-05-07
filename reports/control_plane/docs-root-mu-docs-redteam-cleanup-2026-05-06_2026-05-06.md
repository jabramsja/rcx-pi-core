# Docs-Root-Mu-Docs-Redteam-Cleanup-2026-05-06

Date: 2026-05-06
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: docs-root-mu-docs-redteam-cleanup-2026-05-06
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: Produce an evidence-backed root-docs and active-mu/docs Phase A red-team packet that can either authorize a bounded Phase B docs cleanup or issue a documented NO-GO.
FOUNDER_OVERRIDE:docs-root-mu-docs-redteam-cleanup-2026-05-06

## Phase A Decision

GO for bounded Phase B docs-only cleanup, limited to the three Phase-B-eligible
DOC_ACCURACY cleanups in this packet:

1. Regenerate/update `mu/docs/README.md` so the active docs index matches the
   current active non-archive `mu/docs/**/*.md` inventory.
2. Replace `mu/docs/core/L4DecisionCard.v0.md` header
   `GROUNDING_TESTS: none` with the already-existing test evidence paths that
   ground its L4 decision/current-state claims.
3. Remove or update the stale static footer in `README.md` that still says
   `Last updated: 2026-03-05` after the file was changed on 2026-05-06.

No archive move is authorized by this packet. No Claude-related edit is
authorized. No `/mu` structural, runtime, substrate, seed, scheduler, registry,
or production implementation is authorized.

## Grounding / Authorization

Tracker grounding from targeted `TASKS.md` lines:

- `TASKS.md:425` marks `[NEXT-CODEX-POST-REDTEAM]` unparked and
  founder-authorized.
- `TASKS.md:426` identifies the parent tracked packet:
  `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- `TASKS.md:427` preserves the Phase A -> Phase B -> Phase C -> Phase D
  sequence.
- `TASKS.md:428` says the current phase remains open, with remaining structural
  reduction requiring separate bounded packets.
- `TASKS.md:429` says the Phase A structural gap sweep and
  engine-state/scheduler reduction slice landed; those seed, fixture,
  structural-test, scheduler-parity, and seed-registration items are not pending
  here.
- `TASKS.md:433` carries the founder-ordered red-team directive, requires
  control-plane packets and tracker entries for waves, orders remediation by
  category/severity, and hard-stops any `/mu` structural remediation before
  implementation.
- `TASKS.md:436` records the founder-ordered docs audit as completed/findings
  routed, with no remediation or Claude-related edit performed and `/mu`
  structural remediation still last/hard-stopped.
- `TASKS.md:442` records the docs non-blocking remediation as
  implemented/local-evidence and therefore not pending in this packet.
- `TASKS.md:445` and `TASKS.md:446` queue `/mu` structural remediation packets
  and require hard stop before implementation.
- `TASKS.md:451` is the same-wave tracker sync note for this control-plane
  packet, binding `docs-root-mu-docs-redteam-cleanup-2026-05-06` to
  `[NEXT-CODEX-POST-REDTEAM]` and
  `FOUNDER_OVERRIDE:docs-root-mu-docs-redteam-cleanup-2026-05-06`.

Routing and same-wave authorization:

- Governing packet:
  `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md`.
- Same-wave L4 authorization:
  `FOUNDER_OVERRIDE:docs-root-mu-docs-redteam-cleanup-2026-05-06`.
- Scope of override: bounded docs/control-plane Phase A plan and the Phase B
  docs cleanup explicitly authorized by this locked Phase A output only.
- Historical non-authorizing routing diagnostic: the
  `.agent_bus/meta/post_merge_routing.json` snapshot read during this wave was
  stale and was not used as proof of route authority. That historical snapshot
  at `.agent_bus/meta/post_merge_routing.json:2` through
  `.agent_bus/meta/post_merge_routing.json:4` named `ROUTE_PHASE_A`, this wave,
  and `[NEXT-CODEX-POST-REDTEAM]`, and
  `.agent_bus/meta/post_merge_routing.json:7` through
  `.agent_bus/meta/post_merge_routing.json:14` carried only a candidate/bounded
  entry plus old `head_sha`/`state_sha`, with no `tracked_packet`. Reproduced
  dispatcher evidence at the time:
  `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --json -v`
  exits `1` with `status: stale`, `record state_sha=056bc886,
  current=175aa30d`, and `Canonical routing rebind failed: no tracked_packet`.
  This matches the dispatcher freshness and rebind gates at
  `mu/tools/executors/executor_dispatch.py:312` through
  `mu/tools/executors/executor_dispatch.py:326` and
  `mu/tools/executors/executor_dispatch.py:2449` through
  `mu/tools/executors/executor_dispatch.py:2454`; the canonical builder contract
  requires `tracked_packet` at `mu/tools/executors/executor_common.py:972`
  through `mu/tools/executors/executor_common.py:976`. Therefore the routing
  record is a stop/diagnostic surface only; authority for this packet derives
  from the `FOUNDER_OVERRIDE` and tracker grounding above.
- Same-wave tracker entry: `TASKS.md:451` now carries the required
  wave-bound tracker sync note for `docs-root-mu-docs-redteam-cleanup-2026-05-06`.
  Same-wave L4 authority derives from that tracker entry plus this packet's
  `FOUNDER_OVERRIDE:docs-root-mu-docs-redteam-cleanup-2026-05-06`.

## Scope

Phase A was limited to adversarial docs readback and cleanup planning. Phase A
did not implement cleanup.

Auditable root markdown files:

- `AGENTS.md`
- `AGENT_BRIDGE.md`
- `CHANGELOG.md`
- `CLAUDE.md` read-only only, and only where bootstrap/protocol truth required it
- `FOUNDER_SESSION_BOOTSTRAP.md`
- `README.md`
- `ROADMAP.md`
- `STATUS.md`
- `TASKS.md`

Auditable `mu/docs` files:

- Active, non-archive markdown under `mu/docs/**/*.md`.
- Exclude any path under archive or archived directories.

Exclusion result:

- `find mu/docs -type d \( -name archive -o -name archived \) -print | sort`
  returned no paths, so no `mu/docs` archive/archived markdown paths were
  excluded from the active inventory.

- `reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Audit Inventory

Root markdown audited:

1. `AGENTS.md`
2. `AGENT_BRIDGE.md`
3. `CHANGELOG.md`
4. `CLAUDE.md` read-only protocol check only
5. `FOUNDER_SESSION_BOOTSTRAP.md`
6. `README.md`
7. `ROADMAP.md`
8. `STATUS.md`
9. `TASKS.md`

Active non-archive `mu/docs/**/*.md` audited:

1. `mu/docs/README.md`
2. `mu/docs/agents/AgentBridgeProtocol.v0.md`
3. `mu/docs/agents/AgentGuardrails.v0.md`
4. `mu/docs/agents/AgentRig.v0.md`
5. `mu/docs/agents/AgentRunbook.v0.md`
6. `mu/docs/agents/NoOpProofTemplate.v0.md`
7. `mu/docs/agents/PipelineRecovery.v0.md`
8. `mu/docs/audit/AuditReliabilityPlan.v0.md`
9. `mu/docs/audit/CI_POLICY.md`
10. `mu/docs/audit/MetaCircularReadiness.v1.md`
11. `mu/docs/cli/Flags.md`
12. `mu/docs/cli/cli_quickstart.md`
13. `mu/docs/cli/cli_schema.md`
14. `mu/docs/cli/orbit_viz_dot.md`
15. `mu/docs/cli/orbit_viz_svg.md`
16. `mu/docs/core/Boot0Architecture.v0.md`
17. `mu/docs/core/Boot1LoopContract.v0.md`
18. `mu/docs/core/BootstrapPrimitives.v0.md`
19. `mu/docs/core/BootstrapStructuralBridge.v0.md`
20. `mu/docs/core/DebtCategories.v0.md`
21. `mu/docs/core/DocGovernance.v0.md`
22. `mu/docs/core/EVAL_SEED.v0.md`
23. `mu/docs/core/EngineNewFixContract.v0.md`
24. `mu/docs/core/EngineNewsStructural.v0.md`
25. `mu/docs/core/EntropyBudget.md`
26. `mu/docs/core/G8CpsFeasibility.v0.md`
27. `mu/docs/core/HemisphereExecutionChecklist.v0.md`
28. `mu/docs/core/L3SubstrateArchitecture.v0.md`
29. `mu/docs/core/L4DecisionCard.v0.md`
30. `mu/docs/core/L4ExitChecklist.v0.md`
31. `mu/docs/core/L4MicroAbi.v0.md`
32. `mu/docs/core/LegacySurfaceDecisionRecord.v0.md`
33. `mu/docs/core/MetaCircularKernel.v0.md`
34. `mu/docs/core/MuDagAbiSpike.v0.md`
35. `mu/docs/core/MuType.v0.md`
36. `mu/docs/core/NorthStarSemantics.v0.md`
37. `mu/docs/core/ObserverEventContract.v0.md`
38. `mu/docs/core/OntologyPromotionContract.v0.md`
39. `mu/docs/core/OperatorExhaustion.v0.md`
40. `mu/docs/core/RCXEngine.v0.md`
41. `mu/docs/core/RCXKernel.v0.md`
42. `mu/docs/core/RecursiveKernel.v0.md`
43. `mu/docs/core/SelfHosting.v0.md`
44. `mu/docs/core/StructuralPurity.v0.md`
45. `mu/docs/core/TypedNumericEnvelopes.v0.md`
46. `mu/docs/core/UniversalEval.v0.md`
47. `mu/docs/core/Why_RCX_PI_VM_EXISTS.md`
48. `mu/docs/core/recurrence_v2_design.md`
49. `mu/docs/execution/ClosureEvidence.v0.md`
50. `mu/docs/execution/DeepStep.v0.md`
51. `mu/docs/execution/DeepStep_Guards.md`
52. `mu/docs/execution/DeepStep_HandTrace.md`
53. `mu/docs/execution/EnginenewsSpecMapping.v0.md`
54. `mu/docs/execution/IndependentEncounter.v0.md`
55. `mu/docs/execution/RuleAsMotif.v0.md`
56. `mu/docs/execution/StallFixExecution.v0.md`
57. `mu/docs/execution/TraceReadingPrimer.v0.md`
58. `mu/docs/schemas/README.md`
59. `mu/docs/schemas/snapshot_json_schema.md`
60. `mu/docs/schemas/world_trace_json_schema.md`

Inventory commands:

- `rg --files -g '*.md' mu/docs | rg -v '(^|/)(archive|archived)(/|$)' | sort | wc -l`
  returned `60`.
- `rg --files -g '*.md' mu/docs | rg -v '(^|/)(archive|archived)(/|$)' | sort | nl -ba`
  returned the 60-file inventory above.

## Evidence Read Log

Root and protocol evidence:

- `nl -ba AGENTS.md | sed -n '1,120p'` read `AGENTS.md:1` through
  `AGENTS.md:51`.
- `nl -ba AGENT_BRIDGE.md | sed -n '1,180p'` read
  `AGENT_BRIDGE.md:1` through `AGENT_BRIDGE.md:134`.
- `nl -ba CHANGELOG.md | sed -n '1,140p'` read selected changelog scope and
  historical-ledger framing at `CHANGELOG.md:1` through `CHANGELOG.md:5`.
- `nl -ba CLAUDE.md | sed -n '1,90p'` read-only checked the Claude protocol
  surface at `CLAUDE.md:1` through `CLAUDE.md:56`; no Claude edit is
  authorized.
- `nl -ba FOUNDER_SESSION_BOOTSTRAP.md | sed -n '1,180p'` read the founder XML,
  volatile-state, startup-command, and attestation contract at
  `FOUNDER_SESSION_BOOTSTRAP.md:1` through
  `FOUNDER_SESSION_BOOTSTRAP.md:180`.
- `nl -ba README.md | sed -n '1,240p'` read `README.md:1` through
  `README.md:203`.
- `nl -ba ROADMAP.md | sed -n '1,80p'` read `ROADMAP.md:1` through
  `ROADMAP.md:29`.
- `nl -ba STATUS.md | sed -n '1,180p'` read `STATUS.md:1` through
  `STATUS.md:166`.
- `nl -ba TASKS.md | sed -n '420,452p'` read the active tracker slice at
  `TASKS.md:420` through `TASKS.md:452`.
- `nl -ba reports/README.md | sed -n '1,220p'` read report-lane governance at
  `reports/README.md:1` through `reports/README.md:31`.
- `nl -ba reports/deferred/README.md | sed -n '1,220p'` read deferred-lane
  current inventory rules at `reports/deferred/README.md:1` through
  `reports/deferred/README.md:75`.

`mu/docs` and tool evidence:

- `for f in $(rg --files -g '*.md' mu/docs | rg -v '(^|/)(archive|archived)(/|$)' | sort); do ...; done`
  read and printed the `TYPE`, `LAST_VERIFIED`, `FOR_CURRENT_STATE`,
  `GROUNDING_TESTS`, and first heading for every active `mu/docs` markdown file.
- `nl -ba mu/docs/README.md | sed -n '1,220p'` read
  `mu/docs/README.md:1` through `mu/docs/README.md:142`.
- `nl -ba mu/tools/docs/generate_docs_index.py | sed -n '1,240p'` read
  `mu/tools/docs/generate_docs_index.py:1` through
  `mu/tools/docs/generate_docs_index.py:206`.
- `nl -ba mu/docs/core/DocGovernance.v0.md | sed -n '1,220p'` read
  `mu/docs/core/DocGovernance.v0.md:1` through
  `mu/docs/core/DocGovernance.v0.md:220`.
- `nl -ba mu/docs/core/L4DecisionCard.v0.md | sed -n '1,120p'` and
  `sed -n '960,1020p'` read `mu/docs/core/L4DecisionCard.v0.md:1` through
  `mu/docs/core/L4DecisionCard.v0.md:120` and
  `mu/docs/core/L4DecisionCard.v0.md:960` through
  `mu/docs/core/L4DecisionCard.v0.md:1005`.
- `nl -ba tests/docs/test_l4_current_state_truth.py | sed -n '120,160p'`
  read `tests/docs/test_l4_current_state_truth.py:131` through
  `tests/docs/test_l4_current_state_truth.py:160`.
- `nl -ba tests/docs/test_status_tasks_consistency.py | sed -n '300,328p'`
  and `sed -n '415,506p'` read
  `tests/docs/test_status_tasks_consistency.py:300` through
  `tests/docs/test_status_tasks_consistency.py:328` and
  `tests/docs/test_status_tasks_consistency.py:415` through
  `tests/docs/test_status_tasks_consistency.py:506`.
- `nl -ba tests/docs/test_doc_governance.py | sed -n '80,150p'` and
  `sed -n '350,382p'` read doc-governance parser and grounding-test rules at
  `tests/docs/test_doc_governance.py:80` through
  `tests/docs/test_doc_governance.py:150` and
  `tests/docs/test_doc_governance.py:350` through
  `tests/docs/test_doc_governance.py:382`.
- `nl -ba tests/structural/test_seed_counts.py | sed -n '20,80p'` and
  `sed -n '232,260p'` read canonical seed inventory/count enforcement at
  `tests/structural/test_seed_counts.py:25` through
  `tests/structural/test_seed_counts.py:80` and
  `tests/structural/test_seed_counts.py:232` through
  `tests/structural/test_seed_counts.py:260`.
- `nl -ba mu/host/python/rcx_pi/selfhost/step_mu.py | sed -n '1028,1040p'`
  read `_STAGE0_VM_CUTOVER = True` at
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1029` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1035`.
- `nl -ba mu/host/js/engine/kernel.js | sed -n '16,84p'` read JS Stage0 VM
  cutover truth at `mu/host/js/engine/kernel.js:18` through
  `mu/host/js/engine/kernel.js:84`.

Startup and command evidence:

- `./tools/session/founder_session_guard.sh docs --run` exited `0`. It ran the
  required startup checks and docs-mode commands, including
  `./tools/checks/check_docs_consistency.sh`, docs-mode pytest set,
  `python3 tools/docs/docs_sync_report.py --check`, and the L4 current-state
  `rg` scan.
- `python3 mu/tools/docs/generate_docs_index.py --check` exited `1` with
  `mu/docs/README.md is OUT OF DATE`.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_root_files.py`
  exited `0` with `74 passed, 1 warning`.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_doc_governance.py`
  exited `0` with `18 passed, 1 warning`.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_l4_current_state_truth.py`
  exited `0` with `8 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/structural/test_seed_counts.py`
  exited `0` with `181 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_cutover.py`
  exited `0` with `39 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_status_tasks_consistency.py tests/research/test_d002_micro_matcher.py tests/research/test_d003_staged_bootstrap.py tests/research/test_d006_h1_fuel_threading.py tests/research/test_d007_h3_negative_control.py tests/research/test_d009_h4_depth_threading.py mu/tests/research/test_d010_h5_projection_loader_binary.py mu/tests/l4_gates/test_stage0_production_pilot_gate.py`
  exited `0` with `341 passed, 2 skipped`.
- The targeted seed-count command using `tests/structural/test_seed_counts.py`
  AST literals returned `MU_SEEDS_total 21`,
  `EXPECTED_COUNTS_total_files 21`, and
  `EXPECTED_COUNTS_projection_total 194`.
- Bridge Round 1 routing diagnostic: `nl -ba .agent_bus/meta/post_merge_routing.json | sed -n '1,80p'`
  read `.agent_bus/meta/post_merge_routing.json:1` through
  `.agent_bus/meta/post_merge_routing.json:15` and showed candidate/bounded
  routing fields but no `tracked_packet`; `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --json -v`
  exited `1` with `status: stale`, `record state_sha=056bc886,
  current=175aa30d`, and `Canonical routing rebind failed: no tracked_packet`.
- `nl -ba mu/tools/executors/executor_dispatch.py | sed -n '312,332p;428,432p;2446,2455p;2608,2668p'`
  read the stale-state rejection and no-`tracked_packet` rebind path at
  `mu/tools/executors/executor_dispatch.py:312` through
  `mu/tools/executors/executor_dispatch.py:326`,
  `mu/tools/executors/executor_dispatch.py:428` through
  `mu/tools/executors/executor_dispatch.py:432`, and
  `mu/tools/executors/executor_dispatch.py:2449` through
  `mu/tools/executors/executor_dispatch.py:2454`.
- `nl -ba mu/tools/executors/executor_common.py | sed -n '950,1020p'`
  read the canonical routing-record builder contract requiring
  `tracked_packet` at `mu/tools/executors/executor_common.py:972` through
  `mu/tools/executors/executor_common.py:976`.

## Red-Team Readback

Root docs:

- Startup/protocol claims in `AGENTS.md` and `FOUNDER_SESSION_BOOTSTRAP.md` are
  supported by existing executable surfaces: `tools/session/founder_session_guard.sh`,
  `tools/session/founder_session_attest.sh`, `tools/session/founder_session_heartbeat.sh`,
  `tools/checks/check_docs_consistency.sh`,
  `tools/checks/enforce_l4_execution_contract.py`,
  `mu/tools/checks/check_host_semantics_ratchet.py`, and
  `tools/checks/check_host_authority_inventory_ratchet.py` all exist.
- Shared-learning surface claims in `AGENTS.md:38` through `AGENTS.md:42` were
  reproduced by file existence checks for `.claude/hooks/capture-learning.sh`,
  `.agent_bus/recovery/learned_patterns.json`, and `.claude/rules/learning.md`.
- `AGENT_BRIDGE.md:29` through `AGENT_BRIDGE.md:36` names tracked bridge files;
  existence checks confirmed `tools/agents/bridge_supervisor.py`,
  `tools/agents/bridge_schema.sql`, `tools/agents/bridge_adapters.py`,
  `tools/agents/templates`, and `tools/agents/bridge_config.example.json`.
- `CHANGELOG.md:3` through `CHANGELOG.md:5` correctly scopes the changelog as a
  selected historical ledger, not the live merge ledger.
- `ROADMAP.md:3` through `ROADMAP.md:7` correctly defers current state and
  authorization to `STATUS.md` and `TASKS.md`.
- `STATUS.md:52` through `STATUS.md:60` preserves the L4 boundary: full L4
  completion remains in SINK while bounded reduction is active and VM cutover is
  active. This is supported by Python cutover code at
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1029` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1035`, JS cutover code at
  `mu/host/js/engine/kernel.js:18` through
  `mu/host/js/engine/kernel.js:84`, and `39 passed` from
  `mu/tests/l4_gates/test_stage0_vm_cutover.py`.
- `README.md` current-state content is mostly consistent after the prior
  docs-non-blocking remediation, but its static footer is stale. See finding F3.
- `CLAUDE.md` was read only for protocol comparison. No Claude-related edit is
  authorized.

`mu/docs`:

- `mu/docs/README.md` is not current with the active inventory even though it
  says it is generated by `mu/tools/docs/generate_docs_index.py`. See finding F1.
- `mu/docs/core/DocGovernance.v0.md:111` through
  `mu/docs/core/DocGovernance.v0.md:135` correctly describes governed folders
  and registry validation; `python3 tools/docs/docs_sync_report.py --check`
  passed during startup.
- `mu/docs/core/L4DecisionCard.v0.md` carries live decision/current-state claims
  but its header says `GROUNDING_TESTS: none`. Existing tests already ground
  part of that doc. See finding F2.
- `mu/docs` contains active stale-verification warnings that are not safe to
  mass-update without per-doc proof. See finding F4.
- No `/mu` structural cleanup is authorized. Existing structural remediation
  boundaries remain the queued, hard-stopped packets at `TASKS.md:445` and
  `TASKS.md:446`.

## Findings Table

| ID | Class | Severity / Blocking | Category | Evidence | Proposed disposition | Phase B eligibility |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | DOC_ACCURACY | Non-blocking | `mu/docs` governance/indexes | `mu/docs/README.md:20` through `mu/docs/README.md:21` says the file is generated by `mu/tools/docs/generate_docs_index.py`; `mu/tools/docs/generate_docs_index.py:132` through `mu/tools/docs/generate_docs_index.py:140` indexes direct markdown files inside each first-level docs directory, not every recursive active `mu/docs/**/*.md`; `python3 mu/tools/docs/generate_docs_index.py --check` exited `1` with `mu/docs/README.md is OUT OF DATE`; the active generated-index target set was the generator's first-level directory output. | Regenerate/update `mu/docs/README.md` for the generator-owned target set; update its `LAST_VERIFIED` header to 2026-05-06 if the generated content is accepted. | Yes |
| F2 | DOC_ACCURACY | Non-blocking | `mu/docs` architecture/current-state | `mu/docs/core/L4DecisionCard.v0.md:6` points current state to `STATUS.md` and `TASKS.md`; `mu/docs/core/L4DecisionCard.v0.md:7` says `GROUNDING_TESTS: none`; the same doc carries G8/current-state and production-boundary claims at `mu/docs/core/L4DecisionCard.v0.md:894` through `mu/docs/core/L4DecisionCard.v0.md:946` and `mu/docs/core/L4DecisionCard.v0.md:984` through `mu/docs/core/L4DecisionCard.v0.md:992`; `tests/docs/test_status_tasks_consistency.py:420` through `tests/docs/test_status_tasks_consistency.py:506` directly checks L4DecisionCard D008 and hypothesis matrix truth; research/gate tests cite the decision card and the targeted run exited `0` with `341 passed, 2 skipped`. | Replace `GROUNDING_TESTS: none` with a concrete one-line list of the existing grounding tests for the L4 decision card. | Yes |
| F3 | DOC_ACCURACY | Non-blocking | root docs | `README.md:203` says `Last updated: 2026-03-05`; `git log -1 --format='%ad %h %s' --date=short -- README.md` returned `2026-05-06 4272dd27 feat: Phase B implementation for founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`; `TASKS.md:442` says that wave reconciled root README Stage0 wording and seed/projection counts; `README.md:16` and `README.md:23` now carry those current claims. | Remove the stale footer or update it to 2026-05-06. Prefer removal if Phase B wants to avoid future static-date drift. | Yes |
| F4 | DOC_ACCURACY | Non-blocking | `mu/docs` governance/indexes, CLI/schema/execution, and architecture/current-state | `tests/docs/test_doc_governance.py:93` through `tests/docs/test_doc_governance.py:94` defines the 90-day stale verification warning; `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_doc_governance.py` exited `0` with one warning listing `MetaCircularReadiness.v1.md`, `Flags.md`, `cli_quickstart.md`, `cli_schema.md`, `orbit_viz_dot.md`, `orbit_viz_svg.md`, `DebtCategories.v0.md`, `EngineNewsStructural.v0.md`, `EntropyBudget.md`, and `MuType.v0.md` as 92 days old. | Finding only. Do not mass-update `LAST_VERIFIED` for these docs without per-doc claim verification and doc-specific evidence. | No |

## Proposed Edits / Archive Moves

Authorized Phase B edits:

1. `mu/docs/README.md`
   - Edit: regenerate/update the active index so it matches the generator-owned
     target set: direct markdown files inside each first-level docs directory.
   - Required evidence already present: `mu/docs/README.md:20` through
     `mu/docs/README.md:21`, `mu/tools/docs/generate_docs_index.py:132` through
     `mu/tools/docs/generate_docs_index.py:140`, and the failing
     `python3 mu/tools/docs/generate_docs_index.py --check` output.
   - Validation must include `python3 mu/tools/docs/generate_docs_index.py --check`
     after the edit.

2. `mu/docs/core/L4DecisionCard.v0.md`
   - Edit: replace line `GROUNDING_TESTS: none` with:
     `GROUNDING_TESTS: tests/docs/test_status_tasks_consistency.py; tests/research/test_d002_micro_matcher.py; tests/research/test_d003_staged_bootstrap.py; tests/research/test_d006_h1_fuel_threading.py; tests/research/test_d007_h3_negative_control.py; tests/research/test_d009_h4_depth_threading.py; mu/tests/research/test_d010_h5_projection_loader_binary.py; mu/tests/l4_gates/test_stage0_production_pilot_gate.py`
   - Required evidence already present: `mu/docs/core/L4DecisionCard.v0.md:7`,
     `tests/docs/test_status_tasks_consistency.py:420` through
     `tests/docs/test_status_tasks_consistency.py:506`, and the targeted
     `341 passed, 2 skipped` pytest run.

3. `README.md`
   - Edit: remove `README.md:203` or update the date to 2026-05-06.
   - Required evidence already present: `README.md:203`, `TASKS.md:442`, and
     `git log -1 --format='%ad %h %s' --date=short -- README.md` output.
   - Preferred cleanup: remove the static footer to avoid repeating this drift.

Archive moves:

- None authorized. Phase A did not prove any whole in-scope document is closed,
  stale, or redundant.

Findings-only items:

- F4 stale verification warnings require per-doc verification before any
  `LAST_VERIFIED` changes.
- Any cleanup touching `CLAUDE.md`, `.claude/*`, or `/mu` structural/runtime
  implementation remains a stop condition, not an authorized edit.

## Phase B Validation Expectations

If Phase B implements the authorized docs cleanup above, run only docs-local and
targeted truth validation:

1. `python3 mu/tools/docs/generate_docs_index.py --check`
2. `./tools/checks/check_docs_consistency.sh`
3. `python3 tools/docs/docs_sync_report.py --check`
4. `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_root_files.py tests/docs/test_doc_governance.py tests/docs/test_status_tasks_consistency.py tests/docs/test_l4_current_state_truth.py tests/structural/test_seed_counts.py`
5. `PYTHONHASHSEED=0 python3 -m pytest -q tests/research/test_d002_micro_matcher.py tests/research/test_d003_staged_bootstrap.py tests/research/test_d006_h1_fuel_threading.py tests/research/test_d007_h3_negative_control.py tests/research/test_d009_h4_depth_threading.py mu/tests/research/test_d010_h5_projection_loader_binary.py mu/tests/l4_gates/test_stage0_production_pilot_gate.py`
6. `python3 - <<'PY'` targeted AST seed-count command over
   `tests/structural/test_seed_counts.py`, expecting
   `MU_SEEDS_total 21`, `EXPECTED_COUNTS_total_files 21`, and
   `EXPECTED_COUNTS_projection_total 194`.
7. `rg -n "_STAGE0_VM_CUTOVER = True|const _STAGE0_VM_CUTOVER = true" mu/host/python/rcx_pi/selfhost/step_mu.py mu/host/js/engine/kernel.js`
8. `git status --short --branch`

Do not run commit/push governance commands as Phase B-local validation:
`./tools/pre-push-fast`, `./tools/audit_fast.sh`, `./dev.sh`, `git push`,
`gh pr`, and merge scripts remain executor-owned.

## Stop Conditions

- Stop before any Claude-related edit is needed.
- Stop before any `/mu` structural, runtime, substrate, seed, scheduler,
  registry, or production implementation is needed.
- Stop before authorizing cleanup that lacks both doc file:line evidence and
  reproduced code/test/tool/command evidence.
- Stop if pipeline routing selects a completed packet, stale packet, or stale
  routing record; diagnose the routing defect and create a precise automation
  packet or same-wave mechanical fix before continuing.
- Stop if commit or Phase B automation cannot derive the same-wave authorization
  from this packet's `FOUNDER_OVERRIDE` plus the `[NEXT-CODEX-POST-REDTEAM]`
  tracker grounding.
- Stop if the only available evidence is stale packet wording, stale plan
  wording, or a non-reproduced current-state claim.

## Acceptance Criteria Status

- This packet, the same-wave `TASKS.md` tracker sync note, and the three
  explicitly authorized Phase B docs cleanup files were the original docs
  cleanup edit set; the later same-wave deferred bridge packet and indicator
  artifact are recorded below as implementation/provenance outputs.
- Header contains `Phase-A-Lock: LOCKED`.
- Header contains `FOUNDER_OVERRIDE:docs-root-mu-docs-redteam-cleanup-2026-05-06`.
- The Phase A output replaces supervisor request echo with bounded work items,
  constraints, stop conditions, acceptance criteria, findings, and grounding.
- Phase A audit output lists every audited root markdown file and every audited
  active non-archive `mu/docs/**/*.md` file.
- Findings table includes class, severity/blocking status, category, evidence,
  proposed disposition, and Phase B eligibility.
- Every proposed edit cites both doc line evidence and reproduced
  command/code/test evidence.
- Phase B is authorized only for the specific docs cleanup edits listed in this
  packet plus the same-wave provenance outputs recorded below.
- No archive move was authorized by this packet; later deferred-lane sweeps may
  archive generated source advisories after routing their findings.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `docs-root-mu-docs-redteam-cleanup-2026-05-06`
- Active packet: `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/docs-root-mu-docs-redteam-cleanup-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Historical staged files:
  - `README.md`
  - `TASKS.md`
  - `mu/docs/README.md`
  - `mu/docs/core/L4DecisionCard.v0.md`
  - `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md`
  - `reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-root-mu-docs-redteam-cleanup-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `docs-root-mu-docs-redteam-cleanup-2026-05-06`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `docs-root-mu-docs-redteam-cleanup-2026-05-06`
- Active packet: `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f41da79622ed1b2d1144451defe56c7ff3ad1517a8a32f9c4b67859936006299`
- Indicator artifact: `reports/l4_wave_indicators/docs-root-mu-docs-redteam-cleanup-2026-05-06.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id docs-root-mu-docs-redteam-cleanup-2026-05-06 --output reports/l4_wave_indicators/docs-root-mu-docs-redteam-cleanup-2026-05-06.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md. (2) Commit handoff carries 7 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/docs-root-mu-docs-redteam-cleanup-2026-05-06.json`
- Historical staged files:
  - `README.md`
  - `TASKS.md`
  - `mu/docs/README.md`
  - `mu/docs/core/L4DecisionCard.v0.md`
  - `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md`
  - `reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-root-mu-docs-redteam-cleanup-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
