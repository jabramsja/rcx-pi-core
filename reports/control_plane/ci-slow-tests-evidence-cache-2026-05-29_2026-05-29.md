# Ci-Slow-Tests-Evidence-Cache-2026-05-29

Date: 2026-05-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ci-slow-tests-evidence-cache-2026-05-29
Wave class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Governing packet: `reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md`
FOUNDER_OVERRIDE:ci-slow-tests-evidence-cache-2026-05-29

Purpose: Build a bounded CI/test-harness optimization plan for slow evidence lanes without weakening behavioral proof. Route through the current Codex pipeline: dispatcher Phase A, Phase B, pre-commit supervisor, and commit executor. Do not use `run_review.py`. If a pipeline surface breaks, bounded manual recovery is allowed only when this same wave also adds a mechanical pipeline fix or emits a precise automation packet with enough evidence.

## Scope

Files and directories in scope for the implementation wave:

- `tests/parity/test_boot1_shadow_parity.py`
- `tests/parity/test_js_parity_automated.py` only if Phase B proves equivalent cached evidence is needed there
- `tests/l4_gates/test_stage0_vm_performance.py`
- `tests/l4_gates/test_boot1_structural_iteration_gate.py` only if Phase B proves cache/test coordination needs an adjustment
- `tests/l4_gates/engine_evidence_cache.py`
- `TASKS.md` for the same-wave tracker entry required by the founder directive
- `reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md`
- `reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json`
- A same-wave generated deferred non-blocking report only if Phase B emits one

The implementation target is test-harness/evidence-lane optimization, not production runtime behavior. The current functional slow-test lane is treated as passing based on the cited GitHub slow-test evidence; the remaining issue is CI time budget and redundant proof work.

- `reports/deferred/non_blocking/ci-slow-tests-evidence-cache-2026-05-29_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

Concrete bounded work under the open `[NEXT-CODEX-POST-REDTEAM]` current phase:

1. Keep this wave as a separate bounded packet under the open post-redteam queue, with a same-wave `TASKS.md` tracker entry before implementation proceeds.
2. Reuse or extend `tests/l4_gates/engine_evidence_cache.py` for deterministic Boot1/JS parity evidence in `tests/parity/test_boot1_shadow_parity.py`, preserving the same comparison assertions and fail-closed checks.
3. Preserve negative/error-path tests that intentionally need fresh execution, subprocess behavior, timeout behavior, mutation isolation, nondeterminism checks, or exception behavior.
4. Evaluate whether `tests/parity/test_js_parity_automated.py` has equivalent redundant deterministic evidence that should share the same cache pattern; edit it only if Phase B proves the need.
5. For `tests/l4_gates/test_stage0_vm_performance.py`, reduce CI-only repeated observational sampling through a clearly named helper while preserving full profiling behind an explicit opt-in environment variable, or emit a follow-up packet if Phase B proves full statistical profiling must remain in nightly.
6. Keep `tests/l4_gates/test_boot1_structural_iteration_gate.py` aligned with the shared cache only if Phase B finds a coordination issue.
7. Record direct timing evidence before and after the focused hotspot selectors so the optimization shows measurable improvement without weakening proof.

Direct evidence to carry into Phase B:

- Manual GitHub Slow Tests workflow_dispatch run `26643685170` on dev SHA `27eec35622dc66f97221a97d80f4b6b15f60529d` completed SUCCESS. Job `slow-tests` `78523339632` ran `2026-05-29T14:40:16Z` through `2026-05-29T15:15:40Z`. The combined slow-test step ran `2026-05-29T14:40:27Z` through `2026-05-29T15:15:38Z`.
- Completed log `/tmp/rcx-slow-26643685170.log` shows `python -m pytest -m "slow and not l4_expensive" -v -n auto --dist worksteal --timeout=300` completed `817 passed in 1718.90s (0:28:38)` at line 1886.
- The same log shows `python -m pytest -m l4_expensive -v -n auto --dist worksteal --timeout=900` completed `26 passed in 390.24s (0:06:30)` at line 1956.
- Timestamp reconstruction identifies concentrated hotspots: `tests/l4_gates/test_stage0_vm_performance.py::TestTier2IntegrationWorkloads::test_workload_engine_pipeline` 270.72s; `tests/parity/test_js_parity_automated.py::TestHemisphereRoutingPropertyFuzzer::test_valid_engine_result_routing_parity` 203.79s; `tests/parity/test_js_parity_automated.py::TestDifferentialReplayAuditR3::test_generated_hemisphere_replay` 200.08s; `tests/parity/test_boot1_shadow_parity.py::TestBoot1FourWayParity::test_paxos_freeze_four_way` 186.34s; `tests/l4_gates/test_boot1_structural_iteration_gate.py::TestRealReentryProof::test_trampoline_mode_freeze_parity` 168.27s; `tests/parity/test_boot1_shadow_parity.py::TestBoot1ParityProperty::test_parity_various_inputs` 166.57s.
- Reconstructed file totals from log timestamps show `tests/parity/test_boot1_shadow_parity.py` at 2182.12s summed per-test duration across 67 tests, `tests/parity/test_js_parity_automated.py` at 952.71s across 148 tests, `tests/l4_gates/test_stage0_vm_performance.py` at 497.06s across 5 tests, and `tests/l4_gates/test_boot1_structural_iteration_gate.py` at 439.10s across 17 tests. Treat these as per-test timestamp sums under xdist, not lane wall time.
- Source evidence: `tests/parity/test_boot1_shadow_parity.py:42-47` defines `_run_js_json_api()` as an uncached Node subprocess call with `timeout=120`; `tests/parity/test_boot1_shadow_parity.py:893-930` `_run_all_four()` runs two Python engine paths and two JS JSON API subprocess paths for each input; `tests/parity/test_boot1_shadow_parity.py:977-1001` repeats this for Paxos, stall, and multi-projection cases. This is redundant evidence work and a direct test-harness hotspot.
- Source evidence: `tests/l4_gates/engine_evidence_cache.py:93-127` already provides xdist shared file-cache locking for expensive evidence, and `tests/l4_gates/engine_evidence_cache.py:211-257` already wraps cached JS JSON API requests with isolated deep copies.
- Source evidence: `tests/l4_gates/test_boot1_structural_iteration_gate.py:44-63` already uses cached evidence helpers, making this cache an accepted local pattern for expensive L4 engine evidence.
- Source evidence: `tests/l4_gates/test_stage0_vm_performance.py:251-280` runs 3 warmups plus 10 measured full `run_engine_pipeline` calls for one observational performance test, `tests/l4_gates/test_stage0_vm_performance.py:303-335` repeats that pattern for cutover engine pipeline, and `tests/l4_gates/test_stage0_vm_performance.py:194-205` plus `tests/l4_gates/test_stage0_vm_performance.py:282-295` runs 5 warmups plus 30 measured `step_kernel_mu` calls. Those tests state at `tests/l4_gates/test_stage0_vm_performance.py:7-9` and `tests/l4_gates/test_stage0_vm_performance.py:212-215` that data is observational and has no wall-clock CI gating assertion.

## Constraints

Do not skip, xfail, delete, marker-move, or weaken behavioral assertions.

Do not edit production `/mu` runtime, seeds, scheduler, registry, ratchet baselines, GitHub workflows, branch protection, or Claude surfaces in this wave.

Do not convert this L4_ENABLER into a production runtime or substrate change. If direct profile evidence says runtime code must change, stop and emit a separate L4_STRUCTURAL packet instead of bundling that work here.

Do not use stale post-redteam packet wording to relist already landed engine-state/scheduler seed, fixture, structural-test, or scheduler-parity work as unresolved. `TASKS.md:663` says those items are already landed and the queue remains open only for future bounded work not proven by that landed slice.

Do not perform broad repo investigation for Phase A packet repair. The Phase B implementer may inspect only the scoped test/harness files needed to prove and implement this optimization.

## Stop Conditions

- Stop if the only valid fix requires production runtime, substrate, seed, scheduler, registry, ratchet-baseline, workflow, branch-protection, or Claude-surface changes.
- Stop if caching would hide a test that intentionally checks nondeterminism, mutation, fresh process behavior, timeout behavior, or fail-closed exception behavior.
- Stop if host-semantics or authority ratchets increase.
- Stop if the optimization cannot show measurable focused timing improvement on the selected hotspots.
- Stop if Phase B cannot preserve the same behavioral comparisons and fail-closed checks while reducing redundant evidence work.
- Stop if the same-wave `TASKS.md` tracker entry and packet linkage are not present before implementation proceeds.

## Acceptance Criteria

- This packet remains the governing Phase A control-plane packet for `ci-slow-tests-evidence-cache-2026-05-29`.
- A same-wave `TASKS.md` tracker entry exists for this wave before code changes are dispatched.
- The L4 execution contract can mechanically derive same-wave authorization from `FOUNDER_OVERRIDE:ci-slow-tests-evidence-cache-2026-05-29` plus the parent founder directive in `TASKS.md:659-667`.
- Deterministic redundant Boot1/JS evidence is cached or consolidated through the existing evidence-cache pattern while preserving comparison assertions, deep-copy isolation, and fail-closed behavior.
- CI-only observational sampling in Stage0 VM performance tests is bounded without silently removing the full profiling purpose; full profiling remains available through an explicit opt-in path or is deferred by a follow-up packet with evidence.
- Focused hotspot selectors run with `--durations=40`, including the Paxos four-way, Boot1 parity/property, Stage0 VM performance, and the two JS parity Hypothesis/replay selectors named in this packet.
- If runtime budget allows, run `PYTHONHASHSEED=0 RCX_CI=1 python3 -m pytest -q -n auto --dist worksteal tests/parity/test_boot1_shadow_parity.py tests/l4_gates/test_stage0_vm_performance.py tests/l4_gates/test_boot1_structural_iteration_gate.py --tb=short --durations=40`; otherwise run the narrowest selector set and record why the broader command was not run.
- Run `PYTHONHASHSEED=0 RCX_CI=1 python3 -m pytest -q tests/l4_gates/test_stage0_vm_performance.py::test_stage0_vm_performance_tier2_remains_l4_expensive_marked --tb=short`.
- Run `node mu/host/js/eval_step.js`.
- Run `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`.
- Run `python3 tools/checks/check_host_authority_inventory_ratchet.py`.
- Run `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id ci-slow-tests-evidence-cache-2026-05-29 --wave-class L4_ENABLER`.
- Run `./tools/checks/check_docs_consistency.sh`.
- Run `git diff --check`.
- Route final validation through commit executor pre-push-fast and the GitHub PR check surface before merge.

## Grounding / Authorization

Authorization source:

- `TASKS.md:659` lists `[NEXT-CODEX-POST-REDTEAM]` as `UNPARKED` and founder-authorized.
- `TASKS.md:660` identifies the tracked parent packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- `TASKS.md:661-662` keeps the sequence open in Phase A through Phase D, with the current phase open for remaining bounded structural reduction packets.
- `TASKS.md:663` says landed PR #701 and the follow-on engine-state/scheduler reduction already delivered the listed seed, fixture, structural-test, and scheduler-parity items; this wave must not relist those as unresolved.
- `TASKS.md:667` carries the active founder-ordered redteam wave directive and requires every wave to have a control-plane packet plus a `TASKS.md` tracker entry. It also authorizes pipeline-bound manual repair only as an unblocker paired with same-wave mechanical automation or a precise follow-up automation packet.

Governing references:

- Parent tracked packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- Parent founder directive / override token: `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05` from `TASKS.md:667`.
- This wave governing packet: `reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md`.
- Same-wave authorization: `FOUNDER_OVERRIDE:ci-slow-tests-evidence-cache-2026-05-29`.

## Phase B Implementation Evidence

Implementation status: same-wave Phase B local implementation complete.

Changed test-harness surfaces:

- `tests/parity/test_boot1_shadow_parity.py` now reuses `cached_python_pipeline()` and `cached_js_request()` for deterministic Boot1 parity-property and four-way evidence. Fresh subprocess/error-path behavior remains on the uncached `_run_js_json_api()` path for negative, type-rejection, observer, low-budget, and subprocess-shape tests.
- `tests/l4_gates/test_stage0_vm_performance.py` now bounds CI observational sampling through `_stage0_profile_counts()`. Under `RCX_CI=1`, repeated Tier 2 sampling uses a smaller observational sample. Full profiling remains available with `RCX_STAGE0_VM_FULL_PROFILING=1`.
- `tests/parity/test_js_parity_automated.py` was evaluated and left unchanged: the two named hotspots are Hypothesis-generated replay/property checks rather than a fixed duplicate evidence corpus, so caching them would risk hiding generated-case freshness.
- `tests/l4_gates/test_boot1_structural_iteration_gate.py` was left unchanged because it already uses the shared evidence-cache helpers and no coordination issue was found.

Before timing evidence carried from the GitHub slow-test reconstruction:

- `tests/l4_gates/test_stage0_vm_performance.py::TestTier2IntegrationWorkloads::test_workload_engine_pipeline`: 270.72s.
- `tests/parity/test_js_parity_automated.py::TestHemisphereRoutingPropertyFuzzer::test_valid_engine_result_routing_parity`: 203.79s.
- `tests/parity/test_js_parity_automated.py::TestDifferentialReplayAuditR3::test_generated_hemisphere_replay`: 200.08s.
- `tests/parity/test_boot1_shadow_parity.py::TestBoot1FourWayParity::test_paxos_freeze_four_way`: 186.34s.
- `tests/l4_gates/test_boot1_structural_iteration_gate.py::TestRealReentryProof::test_trampoline_mode_freeze_parity`: 168.27s.
- `tests/parity/test_boot1_shadow_parity.py::TestBoot1ParityProperty::test_parity_various_inputs`: 166.57s.

After focused selector evidence:

- Command: `PYTHONHASHSEED=0 RCX_CI=1 python3 -m pytest -q tests/parity/test_boot1_shadow_parity.py::TestBoot1FourWayParity::test_paxos_freeze_four_way tests/parity/test_boot1_shadow_parity.py::TestBoot1ParityProperty::test_parity_various_inputs tests/l4_gates/test_stage0_vm_performance.py tests/parity/test_js_parity_automated.py::TestHemisphereRoutingPropertyFuzzer::test_valid_engine_result_routing_parity tests/parity/test_js_parity_automated.py::TestDifferentialReplayAuditR3::test_generated_hemisphere_replay --tb=short --durations=40`
- Result: `19 passed in 206.48s (0:03:26)`.
- Slowest focused durations: generated hemisphere replay 45.05s; hemisphere routing property 44.73s; Paxos four-way 43.06s; Boot1 parity various inputs 34.42s; Stage0 engine pipeline 19.56s; Stage0 cutover engine pipeline 19.50s.

After broader selector evidence:

- Command: `PYTHONHASHSEED=0 RCX_CI=1 python3 -m pytest -q -n auto --dist worksteal tests/parity/test_boot1_shadow_parity.py tests/l4_gates/test_stage0_vm_performance.py tests/l4_gates/test_boot1_structural_iteration_gate.py --tb=short --durations=40`
- Result: `152 passed in 85.94s (0:01:25)`.
- Slowest broader durations: Paxos four-way 60.76s; structural trampoline freeze parity 41.59s; Boot1 parity various inputs 38.41s; Stage0 cutover engine pipeline 26.68s; Stage0 engine pipeline 26.07s.

Same-wave indicator artifact:

- `reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json` generated by `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id ci-slow-tests-evidence-cache-2026-05-29 --output reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json`.

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `ci-slow-tests-evidence-cache-2026-05-29`
- Active packet: `reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md`
- Indicator artifact: `reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_stage0_vm_performance.py`
  - `mu/tests/parity/test_boot1_shadow_parity.py`
  - `reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md`
  - `reports/deferred/non_blocking/ci-slow-tests-evidence-cache-2026-05-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `ci-slow-tests-evidence-cache-2026-05-29`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/ci-slow-tests-evidence-cache-2026-05-29_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `ci-slow-tests-evidence-cache-2026-05-29`
- Active packet: `reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6745c25ce1b6562ac8306656ee4c63a7ba1c168f0bb286e9b55645cd45cda0ed`
- Indicator artifact: `reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_stage0_vm_performance.py mu/tests/parity/test_boot1_shadow_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_stage0_vm_performance.py`
  - `mu/tests/parity/test_boot1_shadow_parity.py`
  - `reports/control_plane/ci-slow-tests-evidence-cache-2026-05-29_2026-05-29.md`
  - `reports/deferred/non_blocking/ci-slow-tests-evidence-cache-2026-05-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/ci-slow-tests-evidence-cache-2026-05-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
