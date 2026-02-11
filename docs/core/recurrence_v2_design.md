<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-02-10
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/test_recurrence_production.py
-->
# Recurrence v2 Design — Hash-Accelerated Closure Detection

## Problem Statement

The `recurrence.v1.json` seed detects closures in small test cases but **fails on production programs**. When running through the meta-circular kernel, it stalls in `_phase: "check_seen"` because each state comparison requires deep structural pattern matching (~15-60 kernel steps per comparison), and the O(N²) total comparisons exhaust the kernel step budget.

## Root Cause Analysis

**recurrence.v1.json:**
- `_seen` is a flat linked-list: `{head: state, tail: ...}`
- For each new trace state, scans the entire `_seen` list linearly
- Each comparison uses non-linear pattern matching on arbitrarily nested Mu states
- **Cost:** O(N²) comparisons × O(depth) per comparison via kernel
- 15-step Paxos trace: ~210 comparisons × ~30 kernel steps = ~6,300 steps → exceeds budget

## Solution: Hash-Equality Acceleration

**Key insight:** The bottleneck is *comparison cost*, not scan count. Pre-computing `mu_hash` (SHA-256) at the Python boundary and comparing 64-char hash strings (O(1) literal match) eliminates expensive structural comparisons.

**Design decisions:**
1. **Keep flat linked-list** for `_seen` — simple and sufficient for production traces
2. **Pre-hash at boundary** via `hash_trace_for_recurrence()` — adds `state_hash` to trace entries before feeding to the meta-circular kernel
3. **Non-linear pattern matching** for hash comparison — the `hash_match` projection binds `hash` to both `_state_hash` and `_check_list.head.state_hash`; the bridge enforces string equality
4. **No new bootstrap primitives** — uses existing `mu_hash` (boundary primitive in `rcx_pi/selfhost/mu_type.py`)

**`_seen` structure change:**
```
v1:      {head: state,                           tail: ...}
v2 init: {head: {state_hash: "abc...", state: S}, tail: ...}  (Level 1)
v2 now:  {head: {state_hash: "abc..."},           tail: ...}  (Level 2: state dropped)
```

**Level 2 optimization:** The `state` field in `_seen` entries was never used after storage — `hash_match` and `hash_no_match` bind `_seen_state` but neither reference it in their bodies. Dropping `state` saves ~77% memory per seen entry with zero behavioral change.

**Cost comparison (15-step trace, ~210 comparisons):**
- v1: 210 × ~30 kernel steps (structural) = ~6,300 → EXCEEDS BUDGET
- v2: 210 × ~2 kernel steps (string match) = ~420 → FITS

## Projections (recurrence.v2.json)

| Projection | Purpose |
|-----------|---------|
| `recurrence.init` | Entry: extract trace + result from `_detect_closure` |
| `recurrence.end_of_trace` | Terminal: no closure found |
| `recurrence.check_state_stall` | Extract state + hash from stall entries |
| `recurrence.check_state_maxsteps` | Extract state + hash from max_steps entries |
| `recurrence.check_state` | Extract state + hash from normal entries |
| `recurrence.hash_match` | Non-linear: hash equality → closure detected |
| `recurrence.hash_no_match` | Hash differs → advance `_check_list` |
| `recurrence.not_found` | Store `{state_hash}` in `_seen` (Level 2: state dropped) |
| `recurrence.unwrap` | Extract final result |

See `tests/structural/test_seed_counts.py` for count (9 projections).

## Boundary Function

`hash_trace_for_recurrence(trace)` in `step_mu.py` walks a Mu linked-list trace and adds `state_hash = mu_hash(state)` to each entry. Called at the Python/JS boundary before feeding to the meta-circular kernel. This keeps `run_mu_structural` trace format unchanged (v1 backward compatible).

## L3 Parity

`muHash()` in `mu/host/js/eval_step.js` mirrors Python's `mu_hash`: SHA-256 of canonical JSON with sorted keys and Python-compatible separators (`, ` and `: `).

## Files

| File | Role |
|------|------|
| `mu/closures/recurrence.v2.json` | Hash-accelerated seed (9 projections) |
| `mu/closures/recurrence.v1.json` | Proof-of-concept (superseded) |
| `rcx_pi/selfhost/step_mu.py` | `hash_trace_for_recurrence()`, allowed fields |
| `rcx_pi/selfhost/seed_integrity.py` | Checksum + registration |
| `mu/host/js/eval_step.js` | `muHash()` for JS parity |
| `tests/test_recurrence_production.py` | 8 production tests (all pass) |
