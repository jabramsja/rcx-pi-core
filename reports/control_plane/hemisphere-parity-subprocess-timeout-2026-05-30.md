# Hemisphere Parity Subprocess Timeout

Date: 2026-05-30
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: `[NEXT-CODEX-POST-REDTEAM]`
Wave ID: `hemisphere-parity-subprocess-timeout-2026-05-30`
Class: L4_ENABLER
Target Gate: G8
Lane: ci-reliability
Authorization: founder-directed (2026-05-30) — fix the failed scheduled nightly green-gate (#18)
Phase-A-Lock: BOOTSTRAP_PHASE_B_EXCEPTION
FOUNDER_OVERRIDE:hemisphere-parity-subprocess-timeout-2026-05-30

## Problem
The scheduled rcx-green-gate run 26687250989 (dev sha 120bb305, 2026-05-30) failed at
`test_hemisphere_parity.py::test_route_default_parity` with `subprocess.TimeoutExpired` — a
`node eval_step.js --json-api {run_hemisphere}` call exceeded its 60s subprocess timeout ~42min
into the full scheduled suite. Confirmed FLAKE, not a regression: the same test passed in the
push/PR CI of PR #1046 and #1047 and in the "Slow Tests (Nightly)" run on the same 120bb305, and
the role-switch touched no JS/hemisphere code. Root cause: under the scheduled full suite's high
parallelism (xdist -n auto), the node subprocess is CPU-starved past a tight 60s budget.

## Goal
Eliminate the flake by widening the JS-parity node-subprocess timeout to a value with real
headroom under heavy CI load. No parity-logic change.

## Scope (allowed product writes)
- `mu/tests/structural/test_hemisphere_parity.py`   (add _JS_PARITY_TIMEOUT=180; replace 3 literal node-subprocess timeouts)
- `reports/control_plane/hemisphere-parity-subprocess-timeout-2026-05-30.md`  (this packet)

No runtime, substrate, seed, scheduler, registry, projection, parity-LOGIC, or Mu-semantic changes
(only the test's subprocess timeout budget; the parity assertions are unchanged).

## Changes
1. `test_hemisphere_parity.py`: added module-level `_JS_PARITY_TIMEOUT = 180` (one tunable budget)
   and replaced the three hardcoded `node eval_step.js` subprocess timeouts (60/30/60) with it.
   180s is ~90x the <2s normal call, giving headroom for xdist-induced CPU starvation in the full
   scheduled suite, per learning.md 2026-04-11 (timeout budgets should be >=10x expected wall time).

## Broader class (OUT OF SCOPE — noted follow-up per the global-grep discipline)
A repo-wide grep found ~30 `node eval_step.js` subprocess calls with 30/60s timeouts across ~10
parity/structural test files (test_gate5_meta_circular_parity, test_match_bridge_invariants,
test_js_parity_automated, test_exhaustion_parity, test_bridge_ordering_parity,
test_hemisphere_metabolization_parity, test_gate3_security_fix, test_hemisphere_e4_security_invariants,
test_hash_parity, ...). They share the same flaky class. This wave fixes ONLY the file that actually
failed (#18); a follow-up structural wave should hoist a shared parity-timeout constant (e.g. in a
parity helper / tests.repo_root) and adopt it across all sites. Scoped out to keep this fix bounded.

## Local Evidence
- `python3 -m py_compile mu/tests/structural/test_hemisphere_parity.py` -> OK
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/structural/test_hemisphere_parity.py` -> 13 passed (74.85s), incl. test_route_default_parity
- `grep -nE 'timeout=' mu/tests/structural/test_hemisphere_parity.py` -> all 3 use _JS_PARITY_TIMEOUT; 0 bare 60/30
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id hemisphere-parity-subprocess-timeout-2026-05-30 --wave-class L4_ENABLER`
- `git diff --check`
