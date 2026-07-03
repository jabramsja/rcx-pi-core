# Reduce the nightly l4_expensive lane parallelism so slow meta-circular tests do not CPU-compete to timeout

Date: 2026-07-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: l4-expensive-lane-parallelism-headroom-2026-07-03
Phase-A-Lock: LOCKED
Purpose: FOUNDER-DIRECTED nightly-green completion (2026-07-03). The paxos (PR #1202) + js_parity (PR #1204) timeout fixes took the nightly slow_tests from ~4 failures to 1. The remaining failure = test_structural_numbers_rationals.py::TestExactQuotientEngine::test_exact_quotient_results_are_canonical_n TIMEOUT -- VERIFIED the SAME parallel-load class (passes 165.99s SERIALLY, times out in the l4_expensive lane; the class is already @pytest.mark.l4_expensive + @pytest.mark.slow). ROOT: the nightly l4_expensive lane runs 'pytest -m l4_expensive -v -n auto --dist worksteal --timeout=900' (parallel) -- slow meta-circular meta-circular tests CPU-over-subscribe under -n auto and exceed even 900s. This is the SAME root as task #1's node-subprocess serializer + the paxos/js_parity timeout raises (slow tests timing out under nightly parallel CPU competition), now on meta-circular l4_gate tests. STRUCTURAL fix (not another per-test whack-a-mole): reduce the l4_expensive lane's parallelism in the nightly workflow so meta-circular tests get adequate CPU and finish within 900s. Prefer a small fixed worker count (e.g. -n 2) over -n auto to keep some parallelism while removing the over-subscription; serial (-p no:xdist) is the most robust fallback if -n 2 still times out. Do NOT change any test scenario/assertion, do NOT just raise the timeout (whack-a-mole), do NOT add xfail/skip/retry. The l4_expensive lane is nightly-only (the per-commit green-gate excludes l4_expensive), so a slower-but-reliable lane is the correct tradeoff.

## Scope

.github/workflows/slow_tests.yml: reduce the l4_expensive lane parallelism (the '-m l4_expensive ... -n auto' invocation) to a small fixed worker count (e.g. -n 2) -- or serial (-p no:xdist) if -n 2 still lets meta-circular tests time out -- so slow meta-circular tests do not CPU-over-subscribe and exceed the 900s timeout. Keep the 'slow and not l4_expensive' lane as-is. No test/scenario/assertion change; no timeout-only hack; no xfail/skip/retry.

Files and surfaces in scope:

- TASKS.md -- tracker-sync authority. The 2026-07-03 tracker sync note for wave `l4-expensive-lane-parallelism-headroom-2026-07-03` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/l4-expensive-lane-parallelism-headroom-2026-07-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. In `.github/workflows/slow_tests.yml`, reduce the parallelism of the l4_expensive lane (the `pytest -m l4_expensive -v -n auto --dist worksteal --timeout=900` invocation) from `-n auto` to a small fixed worker count `-n 2`, retaining `--dist worksteal --timeout=900`, so slow meta-circular tests get adequate CPU and finish within the 900s per-test timeout.
2. If `-n 2` still lets a meta-circular test time out, fall back to running the l4_expensive lane fully serial (`-p no:xdist`, dropping `--dist worksteal`) -- the most robust option for a nightly-only lane.
3. Make no other change: this is a single-file CI-config edit. Leave the `-m "slow and not l4_expensive"` lane (`-n auto --dist worksteal --timeout=300`) exactly as-is.

## Constraints

- No test change: do NOT edit any scenario, assertion, or fixture in `test_structural_numbers_rationals.py` or any other test file.
- No timeout hack: do NOT raise `--timeout=900` -- raising the timeout is the whack-a-mole this wave explicitly rejects.
- No `xfail`, `skip`, `@pytest.mark.flaky`, or retry/rerun logic.
- Do NOT modify the `-m "slow and not l4_expensive"` lane (`-n auto --dist worksteal --timeout=300`); it stays unchanged.
- Do NOT touch runtime/substrate dirs (`mu/host/`, `rcx_pi/selfhost/`) or any non-CI surface -- this is an L4_ENABLER (CI-config only); L4_ENABLER MUST NOT touch runtime dirs.
- No new node-subprocess serializer and no per-test edit -- the fix is lane-level worker count only.

## Stop conditions

- STOP and escalate to founder if even serial (`-p no:xdist`) still times out the meta-circular tests within 900s -- do NOT raise the timeout or add skip/xfail as a workaround.
- STOP and re-scope if the fix appears to require editing a test file, a runtime dir, or the `slow and not l4_expensive` lane -- that is out of scope.
- STOP and diagnose if the evidence command does NOT pass serially (i.e. the class fails rather than merely timing out under parallel load) -- that would invalidate the parallel-CPU-competition root cause and mean this is a real test defect, not a lane-parallelism issue.

## Validation gates

This wave is a CI-config selector edit (`-n auto` -> `-n 2` on the l4_expensive lane), so real evidence is the affected class/lane running under the new parallelism -- NOT the generic indicator collector. Two distinct commands bind this wave: the first is proof of the change; the second is mechanical L4 indicator provenance only.

- evidence_command (binds the workflow change -- real proof): `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_structural_numbers_rationals.py::TestExactQuotientEngine -p no:xdist -q` -- confirms `TestExactQuotientEngine` (incl. `test_exact_quotient_results_are_canonical_n`, the exact-quotient class that was timing out) passes on its own, proving the nightly failure is parallel-CPU over-subscription -- exactly what the `-n auto` -> `-n 2` reduction targets -- not a test defect. End-to-end, the changed nightly lane is the gate: `python -m pytest -m l4_expensive -v -n 2 --dist worksteal --timeout=900` must complete within the 900s per-test timeout under the reduced parallelism.
- indicator_collection_command (mechanical L4 indicator provenance -- NOT change evidence): `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id l4-expensive-lane-parallelism-headroom-2026-07-03 --output reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json` -- emits the required indicator JSON (debt/ratchet/timing) via a cheap `TestLegacyAliasLock` probe. It does NOT run the l4_expensive lane or `TestExactQuotientEngine`, so it is provenance, not proof of the change.

The auto-derived `evidence_command` in the "L4 fields" block below currently equals the indicator command: this CI-config wave stages no pytest module, so the commit-handoff builder's no-test-file branch (`mu/tools/executors/commit_executor.py`) defaults `evidence_command` to the indicator command. The change-exercising proof is the `evidence_command` bullet above. Durable structural follow-up: teach the handoff builder to bind a named affected test (here `mu/tests/l4_gates/test_structural_numbers_rationals.py::TestExactQuotientEngine`) as the tracker-note `evidence_command` for test-timeout CI-config waves, so the pre-commit supervisor runs the real proof rather than the mechanical collector.

## Acceptance criteria

- The l4_expensive lane in `.github/workflows/slow_tests.yml` runs at reduced parallelism -- `-n 2` (or serial `-p no:xdist` fallback) -- replacing `-n auto`; `--timeout=900` is retained, not raised.
- The `slow and not l4_expensive` lane (`-n auto --dist worksteal --timeout=300`) is unchanged.
- No test scenario/assertion/fixture changed; no `xfail`/`skip`/retry added; no new runtime code.
- evidence_command passes: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_structural_numbers_rationals.py::TestExactQuotientEngine -p no:xdist -q` -- confirming `TestExactQuotientEngine` (incl. `test_exact_quotient_results_are_canonical_n`) passes serially, i.e. the failure is parallel-load-only, not a test defect.
- The diff is CI-config-only (single workflow file; no runtime-dir touch), consistent with the L4_ENABLER class and target_gate_id G8.
- Expected nightly outcome: the l4_expensive lane completes with the structural-numbers meta-circular tests passing within 900s and the nightly slow_tests workflow goes fully green (the remaining `test_exact_quotient_results_are_canonical_n` timeout resolved).

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `l4-expensive-lane-parallelism-headroom-2026-07-03`.
- Governing packet: this file, `reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md`.
- TASKS.md authority: the 2026-07-03 tracker sync note for wave `l4-expensive-lane-parallelism-headroom-2026-07-03` is canonical for this packet's L4 fields.
- Authorization: Founder-directed nightly-green completion 2026-07-03 (the paxos + js_parity fixes cut 4->1; this addresses the l4_expensive lane parallel-load timeout structurally, per reports/deferred/non_blocking/l4-expensive-lane-parallel-load-timeout-2026-07-03.md). FOUNDER_OVERRIDE:l4-expensive-lane-parallelism-headroom-2026-07-03.

FOUNDER_OVERRIDE:l4-expensive-lane-parallelism-headroom-2026-07-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `l4-expensive-lane-parallelism-headroom-2026-07-03`
- Active packet: `reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md`
- Indicator artifact: `reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `.github/workflows/slow_tests.yml`
  - `TASKS.md`
  - `reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/l4-expensive-lane-parallelism-headroom-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `l4-expensive-lane-parallelism-headroom-2026-07-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/l4-expensive-lane-parallelism-headroom-2026-07-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id l4-expensive-lane-parallelism-headroom-2026-07-03 --output reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id l4-expensive-lane-parallelism-headroom-2026-07-03 --output reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md. (2) Commit handoff carries 5 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `.github/workflows/slow_tests.yml`, `TASKS.md`, `reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/l4-expensive-lane-parallelism-headroom-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: l4-expensive-lane-parallelism-headroom-2026-07-03.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `l4-expensive-lane-parallelism-headroom-2026-07-03`
- Active packet: `reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `202fa52f6ce25768abeaee313757214c262743843f1da9c5efba1a7602903e38`
- Indicator artifact: `reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id l4-expensive-lane-parallelism-headroom-2026-07-03 --output reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md. (2) Commit handoff carries 5 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `.github/workflows/slow_tests.yml`, `TASKS.md`, `reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/l4-expensive-lane-parallelism-headroom-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`
- Current staged files:
  - `.github/workflows/slow_tests.yml`
  - `TASKS.md`
  - `reports/control_plane/l4-expensive-lane-parallelism-headroom-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/l4-expensive-lane-parallelism-headroom-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/l4-expensive-lane-parallelism-headroom-2026-07-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
