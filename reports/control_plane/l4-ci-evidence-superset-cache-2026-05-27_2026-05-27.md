# L4-Ci-Evidence-Superset-Cache-2026-05-27

Date: 2026-05-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: l4-ci-evidence-superset-cache-2026-05-27
Class: L4_STRUCTURAL
Target gate: G8
Phase-A-Lock: LOCKED
Packet: `reports/control_plane/l4-ci-evidence-superset-cache-2026-05-27_2026-05-27.md`
FOUNDER_OVERRIDE:l4-ci-evidence-superset-cache-2026-05-27

## 1. Scope: Files/Directories In Scope

Goal: reduce merge-bounded L4 CI and green-gate wall time by reusing deterministic Python engine evidence and removing a measured production-runtime continuation-hash hot path without weakening tests, skipping coverage, changing selectors, or changing Mu semantics.

Editable implementation surfaces for the downstream Phase B wave:

- `mu/tests/l4_gates/engine_evidence_cache.py`: primary test-only helper surface for a superset Python evidence cache.
- `mu/tests/l4_gates/`: only the focused deterministic engine-evidence tests that already consume or should consume `engine_evidence_cache.py`, including the currently cited slow path `tests/l4_gates/test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity`.
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`: adjacent source-lock gate for the continuation-hash boundary contract touched by the runtime hot-path change.
- `mu/host/python/rcx_pi/selfhost/step_mu.py`: production runtime continuation-binding hash hot path, limited to trusted local hashing after the existing boundary Mu validation in `step_kernel_mu`.
- `mu/tools/hooks/pre-push-fast`: same-wave CI/local enforcement recovery surface, limited to mirroring `scripts/green_gate.sh` PY 2/17 contraband validation before local pushes after PR #1028 proved the local hook did not run that check.
- `reports/control_plane/l4-ci-evidence-superset-cache-2026-05-27_2026-05-27.md`: governing packet and Phase A design record.
- `reports/deferred/non_blocking/l4-ci-evidence-superset-cache-2026-05-27_bridge_nonblockers.md`: Phase B non-blocking findings record, limited to resolving same-wave reviewer doc-accuracy findings after the waiver-path NO_GO.
- `TASKS.md`: grounding/tracker surface for same-wave strict staged L4 authority, Phase A acceptance, and downstream dispatcher/commit automation.
- `reports/l4_wave_indicators/l4-ci-evidence-superset-cache-2026-05-27.json`: required same-wave L4 indicator artifact for the `TASKS.md:444` tracker note; strict L4 requires this path to be present in the downstream changed-file set, not merely referenced by tracker metadata.

Read-only evidence surfaces for downstream implementation claims:

- `scripts/green_gate.sh:14-20` and `scripts/green_gate.sh:164-171`, which define the PY10d lane cited by the supervisor request and show that the actual xdist-enabled green-gate path runs with `-n auto --dist worksteal`.
- `.github/workflows/ci.yml:93-102` and `.github/workflows/green_gate.yml:147-153`, which are cited only to preserve the existing seven-check GitHub surface.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:1178`, cited only to verify that the helper evidence path still calls the production `run_engine_pipeline` entry point.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1515-1900` and `mu/host/python/rcx_pi/selfhost/step_mu.py:2272-2282`, cited as the measured continuation-binding and internal continuation-drive hot path.

Out-of-scope unless a bridge reviewer explicitly reroutes the wave:

- JavaScript evidence reuse beyond Phase A evaluation notes.
- Production runtime/semantic files under `mu/host/` other than the bounded `step_mu.py` continuation-hash performance path listed above.
- Workflow/check-surface edits under `.github/workflows/`.
- Green-gate selector or lane edits in `scripts/green_gate.sh`.

## 2. Work Items: Concrete Bounded Tasks From TASKS.md Current Phase

TASKS.md keeps `[NEXT-CODEX-POST-REDTEAM]` unparked and open for bounded follow-up work, while warning not to relist already landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration slices as unresolved. This wave started as a test-evidence cache slice, then was rerouted by diagnostic evidence to a bounded production-runtime performance fix because the helper-only implementation failed the numeric acceptance threshold.

1. Preserve the non-interactive dispatcher/Phase B/pre-commit/commit-executor route for this wave; do not use `run_review.py`, and preserve `executor_config.json` with `agent_review_enabled=false`.
2. In `tests/l4_gates/engine_evidence_cache.py`, evaluate and implement a Python superset evidence cache that computes each deterministic engine request once with `return_meta=True` and observer collection, then derives requested result/meta/observer views as isolated deep copies.
3. Keep the deterministic cache key bounded to real engine inputs and execution knobs: projections JSON, input JSON, `max_steps`, `max_engine_iterations`, `max_algorithm_iterations`, and `boot1_mode`. Do not let caller view flags such as `return_meta` or `observer_enabled` force duplicate production engine runs if the superset evidence can safely serve those views.
4. Add or update focused regression coverage under `tests/l4_gates/` proving result-only, meta, and observer callers can share one cached production run without mutation leaks between returned views.
5. Keep direct uncached negative/error path tests direct. Do not cache cases whose purpose is to prove failure behavior, exception shape, mutation isolation of inputs, or observer error propagation.
6. In `step_mu.py`, remove the measured redundant `assert_mu`/`mu_hash_cached` cost from continuation binding by hashing already-validated continuation-binding structures through a local trusted canonical hash path. The existing boundary validation before that hash block remains authoritative; no public resume, selector, seed, Stage0, or Mu semantic behavior is changed.
7. Preserve the original numeric performance protocol as the required proof standard for any future performance-acceptance claim, but do not treat it as satisfied by the current pipeline-repair package. Any future numeric claim must measure the whole local slow/not-l4_expensive L4 lane before and after the runtime hot-path change with the same selector, the same machine, and the actual xdist-enabled green-gate mode from `scripts/green_gate.sh:14-20` and `scripts/green_gate.sh:170-171`; serial or fixed two-worker measurements may be collected as diagnostics only and cannot satisfy performance acceptance:
   - Required green-gate-mode command for both baseline and post-change samples: `/usr/bin/time -p env PYTHONHASHSEED=0 python3 -m pytest -n auto --dist worksteal -m "slow and not l4_expensive" tests/l4_gates/ --timeout=300 -q`
   - Optional diagnostic serial command: `/usr/bin/time -p env PYTHONHASHSEED=0 python3 -m pytest -m "slow and not l4_expensive" tests/l4_gates/ --timeout=300 -q`
   - Optional diagnostic two-worker command: `/usr/bin/time -p env PYTHONHASHSEED=0 python3 -m pytest -n 2 --dist worksteal -m "slow and not l4_expensive" tests/l4_gates/ --timeout=300 -q`
   - Baseline requirement: before applying the runtime hot-path change, run the required green-gate-mode command three times on the same machine and record the `/usr/bin/time -p` `real` seconds. The supervisor-cited `143 passed in 78.99s` pytest summary is historical context only; it is not a same-clock `/usr/bin/time -p real` baseline and cannot be used by itself for the numeric pass/fail threshold.
   - Post-change requirement: after applying the runtime hot-path change, run the same required green-gate-mode command three times on the same machine and record the `/usr/bin/time -p` `real` seconds.
   - Numeric pass threshold: post-change required green-gate-mode median `real <= baseline_median_real * 0.95`, using only the same-clock `/usr/bin/time -p real` baseline median collected above. Serial, fixed two-worker, pytest-summary-form, or cross-machine timings do not satisfy this threshold even if they improve against their own baselines.
   - Variance rule: apply variance separately to the baseline and post-change required green-gate-mode samples. If either three-sample set has `(max - min) / median > 0.10`, collect two more samples for that same set and use the five-sample median. If the five-sample spread for either set still exceeds 10%, performance acceptance is inconclusive and cannot pass.
8. Before downstream closeout, collect and include the same-wave indicator artifact with `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id l4-ci-evidence-superset-cache-2026-05-27 --output reports/l4_wave_indicators/l4-ci-evidence-superset-cache-2026-05-27.json`, then run strict L4 with that artifact in the changed-file set.
9. If JS evidence reuse appears attractive, stop at a written Phase A finding unless it can be proven without API semantic risk and without production JS runtime edits.

## 3. Constraints: What Is Not In Scope

- No production Mu semantic edits; the only production runtime edit authorized in this packet is the bounded `step_mu.py` continuation-binding hash optimization after existing Mu validation.
- No selector removal, test skipping, `xfail`, `l4_expensive` marker movement, timeout masking, branch-protection edits, or GitHub check-surface changes.
- Preserve all seven GitHub checks: `test`, `green-gate`, `orbit-dot`, `orbit-provenance`, `engine-run-schema`, `orbit-svg`, and `orbit-index`.
- Do not change `.github/workflows/ci.yml`, `.github/workflows/green_gate.yml`, or `scripts/green_gate.sh` as part of this cache wave.
- The only local tooling edit admitted by same-wave CI recovery is `mu/tools/hooks/pre-push-fast`, and only to run the exact existing `tools/checks/linters/contraband.sh rcx_pi` gate that `scripts/green_gate.sh` already runs at PY 2/17.
- Do not use this wave to relist or reopen the landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work identified by `TASKS.md`.
- Do not change ratchet baselines, host-authority inventory baselines, Stage0 wiring, seed/registry data, scheduler behavior, binary/checksum/integrity surfaces, branch protection, Claude files, or unrelated executor/test changes.
- DOC_ACCURACY edits are limited to this governing packet or stale CI timing comments only if a same-wave bridge review explicitly keeps them in docs/control-plane scope.

## 4. Stop Conditions

Stop and return to Phase A/bridge review if any required fix:

- Requires a production Mu semantic edit, Stage0/seed/scheduler edit, or production runtime edit outside the bounded `step_mu.py` continuation-binding hash path.
- Requires weakening selectors, removing tests, moving `l4_expensive`, adding skips/xfails, masking timeouts, or narrowing the seven-check GitHub surface.
- Requires editing `.github/workflows/`, branch protection, or `scripts/green_gate.sh`.
- Cannot prove mutation isolation between cached result/meta/observer views.
- Cannot preserve direct execution for negative/error path tests.
- Attempts to claim numeric performance acceptance without the required same-clock green-gate-mode baseline/post-change sample sets above, or to substitute serial, fixed-worker, pytest-summary-form, or cross-machine timing as the pass proof.
- Requires JS evidence reuse with unresolved API or semantic risk.
- Requires writing outside the in-scope files/directories above, except that the required same-wave L4 indicator artifact path is explicitly in scope.
- Requires changing local pre-push behavior beyond mirroring the already-existing green-gate contraband check.
- Cannot establish same-wave L4 authorization before commit/closeout.

## 5. Acceptance Criteria

- Focused helper/regression tests prove one production Python engine run can serve result-only, meta, and observer views as isolated deep copies.
- Focused tests prove caller mutation of returned result/meta/observer data cannot leak into later cache consumers.
- Negative/error path tests that are meant to exercise direct production failure behavior remain uncached.
- The whole local slow/not-l4_expensive L4 lane remains green under the required `-n auto --dist worksteal` green-gate-mode command shape; the original same-clock median performance threshold is explicitly not claimed by this package and remains reopened for a future performance-acceptance pass.
- `python3 -m py_compile` passes for touched Python helper/test/runtime files.
- `./tools/checks/linters/contraband.sh rcx_pi` passes locally, and `mu/tools/hooks/pre-push-fast` runs the same check before semantic purity and `dev.sh`.
- `python3 tools/checks/check_bootstrap_purity_ratchet.py` passes with no increase to Python or JS `CONTRABAND_OK` baseline counts.
- `git diff --check` passes.
- `reports/l4_wave_indicators/l4-ci-evidence-superset-cache-2026-05-27.json` exists, is included in the downstream changed-file set, and was generated by the same-wave indicator collection command from Work Item 7.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id l4-ci-evidence-superset-cache-2026-05-27 --wave-class L4_STRUCTURAL` passes.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` passes with no host-semantics increase and no baseline edit.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` passes with no unaccepted authority-site increase.
- The final packet/handoff records the proof limit: this is test-evidence reuse plus a production runtime performance optimization, not a production Mu semantic change.

## 6. Grounding / Authorization

- TASKS.md grounding: `TASKS.md:640-648` marks `[NEXT-CODEX-POST-REDTEAM]` as founder-authorized and unparked, keeps the current phase open for separate bounded packets, says old control-surface packets using this task id are not substantive closure evidence, and requires every wave to carry a control-plane packet plus a `TASKS.md` tracker entry.
- Do-not-relist grounding: `TASKS.md:644` says the landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and seed-registration slice must not be relisted as unresolved.
- Source authorization: `TASKS.md:648` carries `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05` for autonomous non-interactive dispatcher/pipeline routing.
- Same-wave authorization: `FOUNDER_OVERRIDE:l4-ci-evidence-superset-cache-2026-05-27`.
- Governing packet: `reports/control_plane/l4-ci-evidence-superset-cache-2026-05-27_2026-05-27.md`.
- Detector-visible same-wave tracker status: `TASKS.md:444` carries `Tracker sync note (2026-05-27, l4-ci-evidence-superset-cache-2026-05-27)` with `Class: L4_STRUCTURAL`, this packet path, the strict staged L4 evidence command, progress proofs, `FOUNDER_OVERRIDE:l4-ci-evidence-superset-cache-2026-05-27`, indicator artifact metadata, and invariant/Boot0 metadata before downstream Phase B implementation can proceed.

## 7. Diagnostic Evidence And Implementation Results

- GitHub CI evidence for PR #1027 showed both `test` and `green-gate` running the same PY10d L4 slow lane for about 22 minutes each; the lane log entries were `143 passed in 661.26s (0:11:01)` and `143 passed in 675.34s (0:11:15)`.
- Workflow source evidence shows both `.github/workflows/ci.yml:93-102` and `.github/workflows/green_gate.yml:147-153` invoke `scripts/green_gate.sh python-only`; `scripts/green_gate.sh:164-171` defines PY10d as `pytest $PARALLEL_FLAG -m "slow and not l4_expensive" tests/l4_gates/ --timeout=...`.
- Helper-only cache evidence did not satisfy acceptance. The exact post-helper/pre-runtime samples were `real 77.82`, `78.28`, and `76.34`, with median `77.82`; the durations run still showed `tests/l4_gates/test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity` at `58.93s`.
- cProfile evidence on that focused test recorded `896,370,590` function calls in `165.000s`, with `engine_pipeline.py:1178(run_engine_pipeline)` at `164.677s`, `step_mu.py:1256(step_kernel_mu)` at `164.657s`, and `mu_type.py:275(assert_mu)` / `mu_type.py:91(is_mu)` at `112.846s` cumulative.
- Direct `assert_mu` instrumentation on the same focused test before the final runtime fix recorded `mu_hash_cached` at `14.355s` across `333,106` calls, plus `step_kernel_mu.continuation_state` at `4.615s` and `step_kernel_mu` at `4.407s`.
- The implemented runtime fix keeps the existing boundary validation, then hashes already-validated continuation-binding structures through a local trusted canonical hash path in `step_kernel_mu`.
- Prior packet timing entries that claimed focused `real 30.48s`, green-gate-mode samples `54.59`/`55.24`/`54.05`, and `145 passed in 58.77s` are not accepted as current follow-up proof because the same session follow-up did not reproduce them after the PR #1028 contraband repair.
- Rejected waiver-path timing evidence: the whitelisted lambda fast path focused `test_simple_terminal_parity` passed with `real 53.97s` and pytest call duration `53.70s`; one full slow/not-l4_expensive lane sample passed with `145 passed in 88.27s`, `/usr/bin/time -p real 88.55s`, and top duration `test_simple_terminal_parity` at `64.10s`. Phase B rejected that path because `python3 tools/checks/check_bootstrap_purity_ratchet.py` reported `CONTRABAND_OK: Python 3/2, JS 4/4, Total 7/6`.
- Current no-lambda repair evidence: the inline no-lambda canonical hash branch passed authority and correctness checks and measured `real 53.44s` focused and `real 87.98s` for one full slow-lane sample; the named-helper no-lambda form was rejected because authority inventory reported a new `rcx_pi/selfhost/step_mu.py::step_kernel_mu.continuation_hash` authority site.
- Current test-bound diagnostic evidence: a direct sweep of `TestObserverEventParity._collect_events` showed `max_algorithm_iterations` values 10, 20, 40, and 100 all produced boot1/trampoline parity with 8 observer events and the same terminal result, but the sweep took `real 214.88s`; a single behavior-equivalent max-10 pair then measured `real 51.90s`, so lowering this test bound is not treated as a proven CI-speed repair in this pass.
- Performance acceptance remains reopened for Phase B/adversarial review. This follow-up repairs the proven CI/local-gate mismatch and preserves the bounded continuation-hash fast path without a new bootstrap-purity waiver; it does not claim the packet's numeric green-gate-mode performance threshold is satisfied by the current session evidence.
- Bridge Round 2 policy repair: the original same-clock median performance protocol remains recorded as the future proof standard, but it is no longer listed as a satisfied or commit-blocking acceptance criterion for this pipeline-repair package. The current package accepts only the bounded runtime repair, local contraband enforcement repair, ratchet/authority checks, strict staged L4 governance, and an explicitly recorded proof limit.
- Bridge Round 2 green-only revalidation after the policy repair: `/usr/bin/time -p env PYTHONHASHSEED=0 python3 -m pytest -n auto --dist worksteal -m "slow and not l4_expensive" tests/l4_gates/ --timeout=300 -q` passed with `145 passed in 83.27s`, `real 83.53`. This is not a baseline/post-change median performance acceptance proof.
- PR #1028 CI repair evidence: both `test` run `26529860243` and `green-gate` run `26529862582` failed at `scripts/green_gate.sh python-only` PY 2/17 with `CRITICAL: Found lambda expression (not in sort key): rcx_pi/selfhost/step_mu.py:1533: continuation_hash = lambda value: _compute_mu_hash(...)`. The PR still showed all seven expected checks: five fixture-gate jobs passed, while `test` and `green-gate` failed on the same contraband gate.
- Same-wave runtime repair after Phase B no-go: `step_kernel_mu` uses explicit `trusted_continuation_hash = validation_mode == "algorithm_runtime"` branches to call `_compute_mu_hash(json.dumps(..., sort_keys=True, ensure_ascii=False, allow_nan=False))` only on the already-validated algorithm-runtime continuation path, with `else mu_hash(...)` preserving the public/domain hash boundary. This avoids lambda contraband, avoids a new `CONTRABAND_OK` marker, and avoids the named-helper authority-inventory site.
- Same-wave local enforcement repair: `mu/tools/hooks/pre-push-fast` now runs `tools/checks/linters/contraband.sh rcx_pi` before semantic purity and `dev.sh`, so the green-gate PY 2/17 lambda failure cannot bypass local pre-push again.
- Same-wave re-entry validation evidence after the no-waiver repair: `python3 tools/checks/check_bootstrap_purity_ratchet.py` passed with `CONTRABAND_OK: Python 2/2, JS 4/4, Total 6/6`; the focused Phase B pytest bundle passed with `39 passed in 64.30s`.

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `l4-ci-evidence-superset-cache-2026-05-27`
- Active packet: `reports/control_plane/l4-ci-evidence-superset-cache-2026-05-27_2026-05-27.md`
- Indicator artifact: `reports/l4_wave_indicators/l4-ci-evidence-superset-cache-2026-05-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tools/hooks/pre-push-fast`
  - `reports/control_plane/l4-ci-evidence-superset-cache-2026-05-27_2026-05-27.md`
  - `reports/deferred/non_blocking/l4-ci-evidence-superset-cache-2026-05-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/l4-ci-evidence-superset-cache-2026-05-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
