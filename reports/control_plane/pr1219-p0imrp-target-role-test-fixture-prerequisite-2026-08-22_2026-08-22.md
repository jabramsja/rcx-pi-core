# PR 1219 P0IMRP Target Role Test Fixture Prerequisite 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMRP-TARGET-ROLE-TEST-FIXTURE-PREREQUISITE-2026-08-22]
Wave ID: pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22
Phase-A-Lock: LOCKED
Purpose: From exact merged PR #1234 authority 3944a786d75709ee16433f0db785ba5a49160e11, prepare only the two existing Step-15 test fixtures that the preserved target-role-authority attempt proved must carry an explicit target executor configuration. Make the fixtures valid under both current dev behavior and the queued fail-closed target-role contract, preserve the stopped committed attempt unchanged, and release only a fresh target-role-authority activation after this prerequisite merges.

## Scope

Modify only the two pre-push regressions that invoke Step-15 against synthetic target roots lacking target executor configuration. In each fixture, materialize the minimum valid partial executor config with explicit role_agents implementer/reviewer and backends.bot_remediation values before the existing call. Do not change assertions, production code, global defaults, bridge config, recovery, or preserved lanes.

Files and surfaces in scope:

- mu/tests/tools/test_agent_bus_namespacing.py (MODIFY) -- in test_commit_bot_remediation_adapter_receives_active_bus_dir, create repo/mu/tools/executors/executor_config.json with explicit Codex implementer/reviewer role_agents and backends.bot_remediation authority before invoking Step 15; preserve every bus-path/run_adapter assertion and fake bridge behavior.
- mu/tests/tools/test_commit_executor_step14_autoresolve.py (MODIFY) -- in TestStep15RemediationMidPollSurfaceConflictRecheck.test_remediation_ci_wait_rechecks_conflict_and_does_not_strand, create tmp_path/mu/tools/executors/executor_config.json with the same explicit target authority before invocation; preserve all conflict, repush, refreshed-head, review-freshness, and return assertions.
- TASKS.md (MODIFY THROUGH PIPELINE) -- record PR #1234 exact merge and fresh P0IMRP activation LANDED; preserve the stopped target-role-authority attempt with exact worktree, branch, bus, local commit 2550e2c18b65edd1c4aa24c0edcaf1b9bff0b933, two-test pre-push failure, no push, and three-attempt recovery exhaustion; make this test-fixture prerequisite CURRENT; serialize a fresh pr1219-p0imrp-commit-target-role-authority-activation-2026-08-22 successor, then recovery stdout provenance, then P0IM; preserve every unrelated TODO, queue row, and legacy delta obligation.
- reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json (GENERATED BEFORE REVIEW) -- same-wave current-candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblockers only; they cannot widen or delay landing.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from a fresh target branch, worktree, namespaced bus, and detached trusted source all at exact PR #1234 merge 3944a786d75709ee16433f0db785ba5a49160e11.
2. Add the minimum partial target executor-config fixture to each of the two exact tests. Use only pytest temporary roots; do not add a shared production helper, repository config file, or persistent artifact.
3. Keep every pre-existing assertion and fake adapter/CI/conflict behavior unchanged. The fixture is prerequisite authority only, not a rewrite or weakening of either regression.
4. Prove the two exact nodes pass against current dev before the target-role production change exists; normal pre-push must then exercise the broader fast surface.
5. Update canonical queue/preservation truth without closing or deleting any lane. Route implementation, review, providerless commit, pre-push, CI, merge, exact dev proof, and cleanup only through the pipeline.

## Constraints

- Exact PR #1234 merge 3944a786d75709ee16433f0db785ba5a49160e11 is the hard dependency and must equal source HEAD, target HEAD before implementation, comparison_commit, and origin/dev immediately before launch.
- The comparison-relative candidate allowlist is only TASKS.md, the two exact canonical test files, the same-wave packet/indicator, and only if generated the same-wave deferred report. This external WaveConfig and all bus-local receipts are excluded from candidate content.
- Do not modify commit_executor.py, executor_common.py, executor_config.json, recovery_gate.py, launch_wave.py, dispatcher, Phase A/B, bridge adapter/client/config, candidate authority, hooks, runtime, substrate, seed, registry, or any other test/doc.
- Do not relax or remove an existing assertion, mock away the future target-config lookup, change adapter/CI/conflict semantics, or make missing target configuration acceptable. Each fixture must positively supply valid target authority.
- Do not resume, amend, rebase, push, copy from, or otherwise mutate the preserved target-role attempt, its local commit, worktree, branch, bus, staged retry-demotion state, or exhausted recovery evidence.
- All model-bearing roles and pager use Codex; commit remains providerless. Nonblockers and unrelated failures cannot widen or delay this test-only landing.

## Stop conditions

- Halt before launch unless origin/dev, clean detached source, fresh target HEAD, and comparison_commit all equal exact 3944a786d75709ee16433f0db785ba5a49160e11; target identities are unique; roles/pager are Codex; and commit is providerless.
- Halt as NEEDS_RESCOPING if either failing regression cannot be prepared solely inside its existing test function, if any production/default/config file must change, or if a third test file is required.
- Halt as DEFECT if either exact test fails against unchanged PR #1234 production code after the fixture addition, or if any original behavioral assertion is removed/weakened.
- Halt if TASKS treats the local target-role commit as landed/pushed, omits its failed pre-push/recovery evidence, removes unrelated TODOs, releases fresh activation before exact prerequisite merge, or treats preservation as closure authority.
- Do not claim prerequisite completion or launch fresh target-role activation until deterministic PR merge, exact merge SHA, origin/dev equality, and pipeline cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bus_namespacing.py mu/tests/tools/test_commit_executor_step14_autoresolve.py`

## Acceptance criteria

- The bus-namespacing regression creates a valid target executor config under its synthetic repo root, still reaches run_adapter, and preserves exact active namespaced bus/config-path assertions.
- The Step-15 mid-poll conflict regression creates the same target authority under tmp_path, still performs exactly one auto-resolve, observes two CI summaries, refreshes the moved PR head, and returns clean rather than stranded.
- Both exact test nodes pass on unchanged PR #1234 production code; all production/config/default bytes remain identical to comparison commit and no third functional path enters the candidate.
- TASKS records PR #1234 landed, the failed target-role attempt preserved-not-complete with exact evidence, this prerequisite current while in flight, fresh target-role activation next, recovery provenance after it, and P0IM behind all exact merges.
- Exact live candidate receipt verification, staged L4 enforcement, cached diff check, independent review, providerless commit, normal pre-push, required CI, merge, exact dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMRP-TARGET-ROLE-TEST-FIXTURE-PREREQUISITE-2026-08-22]; wave id `pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous narrower packets when a wave does not converge and prioritized landing over edge cases. The exact 8,492-test pre-push result proves these two fixture gaps actively block target-role authority; preparing them on unchanged dev is the smallest independently landable predecessor and preserves the failed production candidate without widening it.

FOUNDER_OVERRIDE:pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bus_namespacing.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bus_namespacing.py mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bus_namespacing.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `74eb5d7038b3e5f0fed540ea41902807d829d1ff597e79520374c13775717ea2`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bus_namespacing.py mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bus_namespacing.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bus_namespacing.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `reports/control_plane/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrp-target-role-test-fixture-prerequisite-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
