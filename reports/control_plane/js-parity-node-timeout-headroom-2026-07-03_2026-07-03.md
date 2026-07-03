# Raise test_js_parity_automated node-subprocess timeouts for parallel-load CPU-competition headroom

Date: 2026-07-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: js-parity-node-timeout-headroom-2026-07-03
Phase-A-Lock: LOCKED
Purpose: FOUNDER-DIRECTED root-blocker fix (2026-07-03). test_js_parity_automated.py node-subprocess parity tests FLAKE/TIME OUT under parallel load, which is blocking THREE things simultaneously: the nightly slow_tests (FAILURE on test_engine_pipeline_paxos_parity, test_full_pipeline_with_routing_parity, test_trace_hash_hardcap_clamp_parity, test_generated_hemisphere_replay), the pre-push audit_fast gate (test_max_steps_at_cap_accepted failed pre-push on an unrelated wave), and any wave whose pre-push runs the parallel suite. VERIFIED flaky-not-broken: test_max_steps_at_cap_accepted PASSES isolated/serial (8 passed in 20.84s) but FAILS under `-n auto`. ROOT: task #1's serializer (PR #1200) serializes the node subprocesses but did NOT raise their per-call timeouts, so a single serialized node run still CPU-competes with the parallel python xdist workers and exceeds the tight 30s/60s/120s subprocess.run timeouts. This completes task #1 + the trimmed item-4 of task #15's paxos fix: raise the too-tight node-subprocess timeouts -- the three `_run_serialized_node`/`subprocess.run(..., timeout=…)` guards that gate the parity node runs in the failing classes (currently 30s in `TestAPIMaxStepsGuard._run_js_json_api`, 120s in `TestEnginePipelineCrossSubstrateParity._run_js_json_api`, and 60s in the shared module-level `_module_run_js_json_api`) -- to a load-tolerant ~600s, mirroring EXACTLY the task #15 test_boot1_shadow_parity.py fix that already landed (PR #1202). (Code truth 2026-07-03: this test file has NO cached-JS leg -- `cached_js_request`/`timeout_s`/`_DEFAULT_CACHED_JS_TIMEOUT_S` do not appear in the file -- so `engine_evidence_cache.py` is NOT edited and no `timeout_s=` override is added.) No assertion weakened, no xfail/skip/retry, no substrate/scenario change.

## Scope

`mu/tests/parity/test_js_parity_automated.py`: raise the three node `subprocess.run` timeouts (each routed through the `_run_serialized_node` cross-worker lock) that gate the parity node runs in the flaking classes to a load-tolerant ~600s --
(1) `TestAPIMaxStepsGuard._run_js_json_api` (currently `timeout=30`),
(2) `TestEnginePipelineCrossSubstrateParity._run_js_json_api` (currently `timeout=120`), and
(3) the module-level `_module_run_js_json_api` helper (currently `timeout=60`), shared by `TestTraceHashParityFuzzer` and `TestDifferentialReplayAuditR3`.
No cached-JS leg exists in this file (`cached_js_request`/`timeout_s`/`_DEFAULT_CACHED_JS_TIMEOUT_S` do not appear), so `engine_evidence_cache.py` is NOT edited and no `timeout_s=` override is added. No assertion/substrate/scenario change; no xfail/skip/retry.

Files and surfaces in scope:

- `mu/tests/parity/test_js_parity_automated.py` -- the ONLY edited source; changes are limited to the three `timeout=` literals named above.
- TASKS.md -- tracker-sync authority. The 2026-07-03 tracker sync note for wave `js-parity-node-timeout-headroom-2026-07-03` is the single source of truth for this packet's L4 fields; the packet derives from it (evidence_command excepted -- see Validation gates).

- `reports/deferred/non_blocking/js-parity-node-timeout-headroom-2026-07-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. In `TestAPIMaxStepsGuard._run_js_json_api`, raise the node subprocess timeout from `timeout=30` to `timeout=600`. This guard fronts `test_max_steps_at_cap_accepted` (the pre-push audit_fast blocker) and the other `_MAX_STEPS_GUARDED_ACTIONS` tests in the class.
2. In `TestEnginePipelineCrossSubstrateParity._run_js_json_api`, raise the node subprocess timeout from `timeout=120` to `timeout=600`. This guard fronts `test_engine_pipeline_paxos_parity` and `test_full_pipeline_with_routing_parity` (2 of the 4 failing nightly tests).
3. In the module-level `_module_run_js_json_api` helper, raise the node subprocess timeout from `timeout=60` to `timeout=600`. This helper is shared by `TestTraceHashParityFuzzer` (fronts `test_trace_hash_hardcap_clamp_parity`) and `TestDifferentialReplayAuditR3` (fronts `test_generated_hemisphere_replay`) -- the remaining 2 of the 4 failing nightly tests.

(All three edits are `timeout=` literal changes in `mu/tests/parity/test_js_parity_automated.py`; target ~600s mirrors the landed task #15 `test_boot1_shadow_parity.py` fix, PR #1202.)

## Constraints

- Do NOT edit `mu/host/python/rcx_pi/selfhost/engine_evidence_cache.py` or its `_DEFAULT_CACHED_JS_TIMEOUT_S`. No node-run leg in this test file reaches the cached-JS path; the four in-scope classes drive Node only through `_run_serialized_node` -> `subprocess.run(..., timeout=…)`, so no `timeout_s=` override is required or added.
- Do NOT weaken any assertion, and do NOT add `xfail`/`skip`/`retry`/`@pytest.mark.flaky`. The tests PASS isolated/serial; only the per-call subprocess wall is too tight under `-n auto` CPU competition.
- Do NOT change substrate, scenario, projection corpus, seed inputs, `maxSteps`/`maxEngineIterations`/`maxAlgorithmIterations`, or Hypothesis `settings`/`deadline`/`max_examples`.
- Do NOT touch the cross-worker node serializer (`_serialized_node_subprocess`/`_run_serialized_node`) landed in PR #1200 -- only the three per-call `timeout=` literals change.
- Do NOT edit any runtime/substrate source (`rcx_pi/selfhost/`, `mu/host/js/`). This is an L4_ENABLER wave: it MUST NOT touch runtime dirs.
- Do NOT alter the pre-existing `@pytest.mark.timeout(600)` pytest-timeout wall on `test_generated_hemisphere_replay`; it is a separate outer wall and is not a substitute for the inner subprocess timeout.

## Stop conditions

- STOP if raising the timeouts does NOT make the four in-scope classes pass under `-n auto --dist worksteal`. That would prove a real parity break, not a timeout, and would falsify the wave premise ("flaky-not-broken"); escalate as a DEFECT rather than raising timeouts further.
- STOP if any target test requires an assertion change, `xfail`, `skip`, or retry to go green -- that violates the no-masking constraint; escalate to founder.
- STOP if closing the failure appears to require touching `engine_evidence_cache.py` or any runtime/substrate source -- that would convert the wave from L4_ENABLER to L4_STRUCTURAL and requires re-classification before proceeding.
- STOP if any of the three guards is already at ~600s in current code (already landed); drop that item instead of re-applying it.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/parity/test_js_parity_automated.py`
- Rationale: the gate now runs all four in-scope classes under the parallel-load repro condition (`-n auto --dist worksteal`), so all four failing nightly tests AND the pre-push blocker are directly exercised. This corrects the prior 2-class command (`TestAPIMaxStepsGuard` + `TestEnginePipelineCrossSubstrateParity` only), which left `TestTraceHashParityFuzzer`/`test_trace_hash_hardcap_clamp_parity` and `TestDifferentialReplayAuditR3`/`test_generated_hemisphere_replay` unverified -- a false-green on the plan's central claim.
- Tracker-sync note: the TASKS.md 2026-07-03 note for this wave still carries the stale 2-class evidence_command and MUST be re-synced to this four-class command as a downstream tracker-sync step (out of scope for this packet edit, which writes only to this file).

## Acceptance criteria

- All three node subprocess timeout guards read `timeout=600` in `mu/tests/parity/test_js_parity_automated.py`: `TestAPIMaxStepsGuard._run_js_json_api`, `TestEnginePipelineCrossSubstrateParity._run_js_json_api`, and the module-level `_module_run_js_json_api`.
- The evidence_command above passes green under `-n auto --dist worksteal`, exercising all four in-scope classes, so the four failing nightly tests (`test_engine_pipeline_paxos_parity`, `test_full_pipeline_with_routing_parity`, `test_trace_hash_hardcap_clamp_parity`, `test_generated_hemisphere_replay`) and the pre-push blocker (`test_max_steps_at_cap_accepted`) are all directly verified -- no false-green.
- `git diff` shows ONLY `timeout=` literal changes in the one test file: no assertion weakened, no `xfail`/`skip`/`retry` added, no runtime/substrate source touched.
- L3 parity unaffected: no Python or JS projection semantics change (timeout-only edit), so `node mu/host/js/eval_step.js` behavior is unchanged.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `js-parity-node-timeout-headroom-2026-07-03`.
- Governing packet: this file, `reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md`.
- TASKS.md authority: the 2026-07-03 tracker sync note for wave `js-parity-node-timeout-headroom-2026-07-03` is canonical for this packet's L4 fields, EXCEPT the evidence_command, which this packet corrects to cover all four in-scope classes per bridge-reviewer Finding 2 (the TASKS.md note requires a matching re-sync downstream).
- Authorization: Founder-directed root-blocker fix 2026-07-03: test_js_parity parallel-load flakiness blocks the nightly + pre-push merges + stranded wave #13. Completes task #1 (serializer) + task #15 item-4. FOUNDER_OVERRIDE:js-parity-node-timeout-headroom-2026-07-03.

FOUNDER_OVERRIDE:js-parity-node-timeout-headroom-2026-07-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `js-parity-node-timeout-headroom-2026-07-03`
- Active packet: `reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md`
- Indicator artifact: `reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_js_parity_automated.py`
  - `reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/js-parity-node-timeout-headroom-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `js-parity-node-timeout-headroom-2026-07-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/js-parity-node-timeout-headroom-2026-07-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id js-parity-node-timeout-headroom-2026-07-03 --output reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/parity/test_js_parity_automated.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/parity/test_js_parity_automated.py`, `reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/js-parity-node-timeout-headroom-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: js-parity-node-timeout-headroom-2026-07-03.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `js-parity-node-timeout-headroom-2026-07-03`
- Active packet: `reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `65c099a54bc15fc0bd392ee9f6b03511b105aaa1e86ded2e42896c15992276c4`
- Indicator artifact: `reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/parity/test_js_parity_automated.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/parity/test_js_parity_automated.py`, `reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/js-parity-node-timeout-headroom-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_js_parity_automated.py`
  - `reports/control_plane/js-parity-node-timeout-headroom-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/js-parity-node-timeout-headroom-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/js-parity-node-timeout-headroom-2026-07-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
