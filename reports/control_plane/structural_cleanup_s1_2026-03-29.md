# Structural Cleanup S1

Date: 2026-03-29
Status: Implementation complete — Phase B executor ran full pipeline (implementer + agents + 2 bridge rounds)
Phase-A-Lock: LOCKED
Purpose: Bundle trivial structural fixes from post-redteam gap sweep assessment

## Scope

Three small fixes identified by the structural gap assessment:

### 1. Remove dead function: mu_hash_cache_clear (mu_type.py:550)
Defined but never called anywhere in the codebase. Zero internal or external callers.

### 2. Boot1 observer timestamp reset on re-entry (engine_pipeline.py)
Pre-existing: Boot1 resets observer timestamp counter `_obs_ts[0]` on re-entry,
violating per-run monotonicity. Step values remain monotonic (primary sort key).
Fix: preserve `_obs_ts[0]` across re-entry like `_total_iterations[0]`.
Cross-substrate: same fix needed in JS pipeline.js.

### 3. W5A gate test re-entry coverage (test_boot1_step_monotonicity_gate.py)
Gate test doesn't exercise actual re-entry (boot1_depth > 0) for step monotonicity.
Fix: add mock-injected re-entry variant (pattern exists in test_boot1_structural_iteration_gate.py).

## Files to Modify

1. `mu/host/python/rcx_pi/selfhost/mu_type.py` — delete mu_hash_cache_clear
2. `mu/host/python/rcx_pi/selfhost/engine_pipeline.py` — preserve _obs_ts across re-entry
3. `mu/host/js/engine/pipeline.js` — same fix for JS parity
4. `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py` — add re-entry variant

## Constraints

- No seed changes
- No new host capabilities (fix preserves existing counter, doesn't add new one)
- Cross-substrate parity required for fix #2
- Deterministic under PYTHONHASHSEED=0

## Evidence

- Before: 1 dead function, timestamp non-monotonic across re-entry, gate test lacks re-entry path
- After: dead code removed, timestamp monotonic across re-entry (both substrates), gate test covers re-entry
- Verify: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py mu/tests/l4_gates/test_boot1_structural_iteration_gate.py -v && node mu/host/js/eval_step.js`

## Lane

Post-redteam structural (NEXT-CODEX-POST-REDTEAM Phase A, GAP-02/03/04).
