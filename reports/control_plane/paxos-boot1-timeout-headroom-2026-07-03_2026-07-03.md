# Raise paxos boot1 node-subprocess + pytest timeouts for serial-node CPU-competition headroom

Date: 2026-07-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: paxos-boot1-timeout-headroom-2026-07-03
Phase-A-Lock: LOCKED
Purpose: FOUNDER-DIRECTED nightly follow-up (2026-07-03). The flock node-subprocess serializer (PR #1200) reduced the nightly slow_tests failures from ~95-119 to 4, but 4 paxos boot1 tests still TIME OUT (NOT AssertionError parity regressions — so this is a timeout-headroom issue, NOT the numeral cutover). VERIFIED from nightly run 28655907693 (dev 880eee71): FAILED tests are `mu/tests/parity/test_boot1_shadow_parity.py::TestBoot1CrossSubstrateParity::test_paxos_boot1_cross_substrate` and `::TestBoot1FourWayParity::test_paxos_freeze_four_way`, failing on node subprocess timeout AND the slow-lane pytest-timeout of 300s. ROOT: the serializer runs node subprocesses one-at-a-time, but the single running node still competes for CPU with the parallel python xdist workers, so the slowest paxos boot1 node runs exceed their tight per-subprocess timeouts under nightly parallel load. CRITICAL: the two failing tests reach node through TWO DIFFERENT helpers with TWO DIFFERENT timeouts (verified in current code) — the fix must raise BOTH, not just one:

- `test_paxos_boot1_cross_substrate` (`test_boot1_shadow_parity.py` L367) calls `_run_js_json_api(...)` (L66) → `_run_serialized_node(..., timeout=120)` → `subprocess.run(..., timeout=120)`. Its node ceiling is the **120s** literal local to the test file.
- `test_paxos_freeze_four_way` (L1020) calls `_run_all_four(...)` (L936), whose two node legs go through `_run_cached_js_json_api(...)` (L83-88) → `cached_js_request(action, **request)` in `mu/tests/l4_gates/engine_evidence_cache.py` → `_run_js_json_api_payload(..., timeout=timeout_s)` (L225-232), where `timeout_s` defaults to `_DEFAULT_CACHED_JS_TIMEOUT_S = 180` (L22, L249). Its node ceiling is the **180s** cached-JS default in `engine_evidence_cache.py`. It NEVER calls `_run_js_json_api`, so raising the 120s literal does NOT help it. (The four-way test's two Python legs go through `_run_cached_engine_path` → `cached_python_pipeline`, which run in-process and carry no subprocess timeout.)

FIX (headroom, no masking): (a) raise the uncached `_run_js_json_api` `subprocess.run` timeout 120 → ~600s (covers `test_paxos_boot1_cross_substrate`); (b) raise the four-way test's cached-JS node ceiling from the 180s default to ~600s by having the in-scope `_run_cached_js_json_api` helper pass an explicit `timeout_s=600` to `cached_js_request(...)` — an in-scope, per-call override that does NOT edit `engine_evidence_cache.py` and does NOT perturb caching (verified: `timeout_s` is keyword-only on `cached_js_request` at L249 and is excluded from the cache key — `request`/`payload_json` at L253/L256 and the `_cached_js_json_api` key `{"payload_json": ...}` at L215 — so it only governs the node `subprocess.run` timeout on a cache miss); (c) ensure the pytest-timeout for the two failing tests is large enough (~900s) via `@pytest.mark.timeout(900)` or the l4_expensive lane (which runs at `--timeout=900`), whichever is consistent with the existing `@pytest.mark.slow` class markers and boot1 marker-lock assertions. Document why each raise is needed per call (serial-node CPU competition under `-n auto`). Do NOT weaken any assertion, do NOT add xfail/skip/retry, do NOT change the substrate or the paxos scenario params (maxSteps/iterations/seed). This is the timeout-headroom raise anticipated by the deferred report; it completes the nightly-green fix that the serializer started.

## Scope

`mu/tests/parity/test_boot1_shadow_parity.py` and the sibling `mu/tests/parity/test_js_parity_automated.py`: raise the paxos boot1 node subprocess timeouts to ~600 and the pytest-timeout to ~900 (marker or l4_expensive lane) for the two failing paxos boot1 tests. No assertion/substrate/scenario change; no xfail/skip/retry.

Files and surfaces in scope:

- `mu/tests/parity/test_boot1_shadow_parity.py` — the uncached `_run_js_json_api` helper (`subprocess.run(..., timeout=120)`), the cached `_run_cached_js_json_api` helper (passes `timeout_s=` through to `cached_js_request`), and the per-test pytest-timeout markers/lane for the two failing tests.
- `mu/tests/parity/test_js_parity_automated.py` — the sibling paxos cross-substrate node run that shares the uncached `_run_js_json_api`-style `timeout=120` pattern (preventive raise).
- `mu/tests/l4_gates/engine_evidence_cache.py` — READ-ONLY reference only. NOT edited. Its `_DEFAULT_CACHED_JS_TIMEOUT_S = 180` default is the diagnosed four-way node ceiling; it is overridden per-call from the in-scope test helper via `timeout_s=`, so no edit to this module is required or permitted by this wave.
- TASKS.md — tracker-sync authority. The 2026-07-03 tracker sync note for wave `paxos-boot1-timeout-headroom-2026-07-03` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/paxos-boot1-timeout-headroom-2026-07-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. In `mu/tests/parity/test_boot1_shadow_parity.py`, raise the uncached node-subprocess run timeout — the `_run_js_json_api` helper's `subprocess.run(..., timeout=120)` (L66-71) — from 120s to a load-tolerant value (~600s), so a serialized node still finishing under parallel-worker CPU competition does not hit the subprocess timeout. This helper is the node path for `TestBoot1CrossSubstrateParity::test_paxos_boot1_cross_substrate` (L379); the raise fixes THAT test (and every other uncached `_run_js_json_api` caller). It does NOT affect the four-way test — see item 2. Add an inline comment stating the reason (serial-node CPU competition under `-n auto`).
2. In the same file, raise the cached-JS node-subprocess ceiling for `TestBoot1FourWayParity::test_paxos_freeze_four_way` (L1020). Its node legs run via `_run_all_four` (L936) → `_run_cached_js_json_api` (L83-88) → `cached_js_request`, whose `timeout_s` defaults to `_DEFAULT_CACHED_JS_TIMEOUT_S = 180` in `mu/tests/l4_gates/engine_evidence_cache.py`. Make `_run_cached_js_json_api` pass an explicit `timeout_s=600` (with the same reason comment) into `cached_js_request(...)`, overriding the 180s default per-call for these boot1 parity node runs. Do NOT edit `engine_evidence_cache.py`; the override stays inside the in-scope test file. This is verified safe for caching: `timeout_s` is keyword-only on `cached_js_request` (L249) and excluded from the cache key, so it governs only the node `subprocess.run` timeout on a cache miss, not the memoized result. This raise also covers the rest of the `_run_all_four` four-way family (L1017/L1024/L1032/L1043/L1049), which share the same cached-JS node path.
3. Give the two nightly-failing paxos boot1 tests — `TestBoot1CrossSubstrateParity::test_paxos_boot1_cross_substrate` and `TestBoot1FourWayParity::test_paxos_freeze_four_way` — a pytest-timeout ceiling (~900s) that exceeds their worst-case serialized runtime, either by adding `@pytest.mark.timeout(900)` per test or by placing them in the l4_expensive lane (which runs at `--timeout=900`), whichever is consistent with the existing `@pytest.mark.slow` class markers and the in-repo boot1 marker-lock assertions.
4. Apply the same uncached node-subprocess timeout headroom (120 -> ~600s, with the same reason comment) to the sibling paxos cross-substrate node run in `mu/tests/parity/test_js_parity_automated.py::TestEnginePipelineCrossSubstrateParity` (paxos routing) that shares the `_run_js_json_api`-style `timeout=120` pattern, so the identical serial-node CPU-competition failure class cannot surface there. This test is not among the 4 nightly failures; the raise is preventive because it shares the fragile uncached pattern.

## Constraints

- Not in scope: any change to substrate code (Python `rcx_pi/selfhost/` or JS `mu/host/js/`), the paxos scenario parameters (maxSteps / iterations / seed), or the cross-substrate comparison logic. This is timeout headroom only — NOT the numeral cutover and NOT a semantics change.
- Do NOT edit `mu/tests/l4_gates/engine_evidence_cache.py`. Its `_DEFAULT_CACHED_JS_TIMEOUT_S = 180` default is diagnostic reference; the four-way test's node ceiling is raised by passing `timeout_s=600` from the in-scope `_run_cached_js_json_api` helper, NOT by mutating the shared cache-module default (which would change every unrelated `cached_js_request` caller and widen blast radius).
- Do NOT weaken, delete, or relax any assertion in the covered tests.
- Do NOT add `xfail`, `skip`, `skipif`, or retry/rerun logic to any covered test.
- Do NOT drop the existing `@pytest.mark.slow` markers on the boot1 parity classes (locked by the in-file marker assertion) or move any class out of its current lane in a way that violates the boot1 marker-lock gates (`test_boot1_structural_iteration_gate.py` locks l4_expensive membership).
- Do NOT lower any timeout below its current value; this is a raise (ceiling), not a retune of fast paths.
- No edits outside the two named parity test files (`test_boot1_shadow_parity.py`, `test_js_parity_automated.py`), apart from the mechanical TASKS.md tracker-sync / L4 fields the pipeline owns.

## Stop conditions

- STOP and escalate if raising the timeouts does NOT make the two paxos boot1 tests pass under nightly `-n auto` parallel load — a persistent failure would indicate an AssertionError / real parity regression, not a timeout-headroom issue, which is outside this wave's scope.
- STOP if raising `_run_js_json_api`'s literal alone appears to "fix" the four-way test — that would mean the four-way node path is not the cached-JS `cached_js_request` path this packet diagnosed (L83-88 → `engine_evidence_cache.py`), and the diagnosis must be re-verified before landing. The four-way fix MUST land through the `_run_cached_js_json_api` `timeout_s=` override (item 2), not the L66 literal.
- STOP if the paxos boot1 node run's actual serialized runtime under CPU competition approaches or exceeds ~600s — the ceiling estimate would be wrong and the scenario cost / root cause needs re-diagnosis before landing.
- STOP if getting green would require modifying substrate code, the paxos scenario params, any assertion, or `engine_evidence_cache.py`'s shared cache default — that is out of scope and must be re-scoped, not forced.
- STOP if adding or moving markers would violate an existing boot1 marker-lock gate (`@pytest.mark.slow` / l4_expensive membership) — resolve the marker strategy before proceeding.

## Validation gates

- evidence_command (canonical, matches the TASKS.md tracker note for this wave): `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_boot1_shadow_parity.py::TestBoot1CrossSubstrateParity -p no:xdist -q`
- Because Phase B deterministically rebuilds the note's `evidence_command` to `pytest <changed test files>`, the effective gate exercises the whole `test_boot1_shadow_parity.py` file — including `TestBoot1FourWayParity::test_paxos_freeze_four_way` — proving the item-2 cached-JS override. Supplementary manual proof of the four-way surface: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_boot1_shadow_parity.py::TestBoot1CrossSubstrateParity::test_paxos_boot1_cross_substrate mu/tests/parity/test_boot1_shadow_parity.py::TestBoot1FourWayParity::test_paxos_freeze_four_way -p no:xdist -q`

## Acceptance criteria

- `mu/tests/parity/test_boot1_shadow_parity.py::TestBoot1CrossSubstrateParity::test_paxos_boot1_cross_substrate` and `::TestBoot1FourWayParity::test_paxos_freeze_four_way` both pass with no timeout under the nightly serialized-node + parallel-worker (`-n auto`) configuration.
- The uncached node `subprocess.run` timeout in `test_boot1_shadow_parity.py` (`_run_js_json_api`, L66) and in the sibling `test_js_parity_automated.py::TestEnginePipelineCrossSubstrateParity` paxos node run is raised from 120s to a load-tolerant ~600s, each with an inline comment documenting the serial-node CPU-competition reason.
- The four-way test's cached-JS node ceiling is raised from the 180s `_DEFAULT_CACHED_JS_TIMEOUT_S` default to ~600s via an explicit `timeout_s=600` passed from the in-scope `_run_cached_js_json_api` helper (L83-88) into `cached_js_request(...)`, with a reason comment. `engine_evidence_cache.py` is unmodified.
- The two failing tests have an effective pytest-timeout of ~900s (per-test `@pytest.mark.timeout(900)` or l4_expensive lane), exceeding their worst-case serialized runtime.
- No assertion weakened; no `xfail`/`skip`/retry added; substrate and paxos scenario params unchanged; `engine_evidence_cache.py` unedited; existing `@pytest.mark.slow` and lane-lock markers preserved.
- Evidence command passes: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_boot1_shadow_parity.py::TestBoot1CrossSubstrateParity -p no:xdist -q`, and the supplementary two-test command (cross-substrate + four-way) also passes.
- Nightly slow / l4_expensive lane goes green for the paxos boot1 parity tests (0 timeouts), matching the TASKS.md `progress_proof_after` for wave `paxos-boot1-timeout-headroom-2026-07-03`.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `paxos-boot1-timeout-headroom-2026-07-03`.
- Governing packet: this file, `reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md`.
- TASKS.md authority: the 2026-07-03 tracker sync note for wave `paxos-boot1-timeout-headroom-2026-07-03` is canonical for this packet's L4 fields. From that note (verified): Class `L4_ENABLER`; target_gate_id `G8`; primary_blocker_class `PERFORMANCE`; primary_invariant_id `INV_CROSS_SUBSTRATE_PARITY`; indicator_artifact_ref `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`; indicator_collection_command `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id paxos-boot1-timeout-headroom-2026-07-03 --output reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`; bootstrap_endgame_policy `SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`; boot0_track_id `V1`; boot0_progress_state `HOLD`.
- Authorization: Founder-directed nightly-green completion 2026-07-03 (the serializer #1200 fixed the bulk; this is the anticipated timeout-headroom follow-up). FOUNDER_OVERRIDE:paxos-boot1-timeout-headroom-2026-07-03.

FOUNDER_OVERRIDE:paxos-boot1-timeout-headroom-2026-07-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `paxos-boot1-timeout-headroom-2026-07-03`
- Active packet: `reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md`
- Indicator artifact: `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_boot1_shadow_parity.py`
  - `reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/paxos-boot1-timeout-headroom-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `paxos-boot1-timeout-headroom-2026-07-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/paxos-boot1-timeout-headroom-2026-07-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id paxos-boot1-timeout-headroom-2026-07-03 --output reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/parity/test_boot1_shadow_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/parity/test_boot1_shadow_parity.py`, `reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/paxos-boot1-timeout-headroom-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: paxos-boot1-timeout-headroom-2026-07-03.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `paxos-boot1-timeout-headroom-2026-07-03`
- Active packet: `reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `dbee722b137224a8b5916d412b2dd6657c7779e0fbf1b028ea97c3ff043eeb2c`
- Indicator artifact: `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/parity/test_boot1_shadow_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/parity/test_boot1_shadow_parity.py`, `reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/paxos-boot1-timeout-headroom-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_boot1_shadow_parity.py`
  - `reports/control_plane/paxos-boot1-timeout-headroom-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/paxos-boot1-timeout-headroom-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/paxos-boot1-timeout-headroom-2026-07-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
