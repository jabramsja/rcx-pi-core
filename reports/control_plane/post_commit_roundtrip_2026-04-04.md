# Executor Config Alignment — Timeout-Budget Truth

Date: 2026-04-05
Status: In progress
Phase-A-Lock: LOCKED
Task: [PIPELINE-RECOVERY/post-commit-roundtrip-2026-04-04]
Wave ID: post-commit-roundtrip-2026-04-04

## Problem

The executor pipeline's timeout budgets can silently shrink through two
independent mechanisms:

**Mechanism A — Dispatch hardcodes.** `executor_dispatch.py` has five
callsites that hardcode fallback timeouts disagreeing with the checked-in
`executor_config.json`. When the config merge drops a key or the JSON file is
absent, a routed wave gets a smaller budget than the live config intends.

**Mechanism B — Stale code default.** `DEFAULT_EXECUTOR_CONFIG` in
`executor_common.py` (line 52) sets `phase_b_executor` to 3600s while the
checked-in `executor_config.json` sets it to 18000s. Any code path that
falls through to `DEFAULT_EXECUTOR_CONFIG` — including `load_executor_config()`
when the JSON file is absent (line 179) — silently applies a 5x budget shrink
for Phase B.

| Executor | `executor_config.json` | `DEFAULT_EXECUTOR_CONFIG` | Dispatch fallbacks | Worst shrink from live |
|---|---|---|---|---|
| `phase_a_executor` | 3600s | 3600s | 600s (L442), 300s (L1390) | 12x (L1390) |
| `phase_b_executor` | 18000s | 3600s | 3600s (L803), 300s (L1390) | 60x (L1390) |
| `commit_executor` | 3600s | 3600s | 300s (L871, L1021, L1390) | 12x |

Additionally, `commit_executor.py` does not call `load_executor_config()` at
all — it imports only utility functions from `executor_common` (line 48-66).
All its internal timeouts (`PRE_PUSH_FAST_TIMEOUT_S=900`,
`BOT_REMEDIATION_TIMEOUT_S=600`, etc.) are hardcoded constants disconnected
from the config surface.

No enforcement test validates that `DEFAULT_EXECUTOR_CONFIG` timeouts match
the checked-in JSON, that dispatch fallback defaults match canonical values,
or that every executor loads its budget from config.

## Scope

Files in scope:
- `mu/tools/executors/executor_common.py` — align `DEFAULT_EXECUTOR_CONFIG["timeouts"]["phase_b_executor"]` with live JSON (3600 → 18000)
- `mu/tools/executors/executor_dispatch.py` — fix fallback defaults at lines 442, 803, 871, 1021, and 1390
- `mu/tools/executors/commit_executor.py` — wire `load_executor_config()` and rebind live timeout constants to config
- `mu/tools/executors/executor_config.json` — add commit-executor sub-timeout keys if needed to surface currently-hardcoded constants; existing values unchanged
- `tests/tools/` — add config-alignment enforcement test
- `reports/control_plane/post_commit_roundtrip_2026-04-04.md` — this packet
- `reports/deferred/non_blocking/post-commit-roundtrip-2026-04-04_bridge_nonblockers.md` — bridge-generated deferred report (expected output)

## Work items

1. **Align `DEFAULT_EXECUTOR_CONFIG` with live JSON.** In
   `executor_common.py` line 52, update
   `DEFAULT_EXECUTOR_CONFIG["timeouts"]["phase_b_executor"]` from 3600 to
   18000 so the code default matches the checked-in `executor_config.json`.
   This closes Mechanism B: any fallback path through `DEFAULT_EXECUTOR_CONFIG`
   (including `load_executor_config()` with missing JSON) now produces the
   correct Phase B budget.

2. **Fix all five dispatch fallback callsites.** In `executor_dispatch.py`,
   replace every hardcoded fallback value in
   `.get("timeouts", {}).get(name, N)` calls with references to
   `DEFAULT_EXECUTOR_CONFIG["timeouts"]` so dispatch can never silently shrink
   a budget below the canonical default:
   - Line 442: generic fallback 600 → `DEFAULT_EXECUTOR_CONFIG["timeouts"].get(executor_name, 600)`
   - Line 803: phase_b fallback 3600 → `DEFAULT_EXECUTOR_CONFIG["timeouts"]["phase_b_executor"]`
     (previously "no change needed" — now required because work item 1 raises the default to 18000)
   - Line 871: commit fallback 300 → `DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_executor"]`
   - Line 1021: commit fallback 300 → same as line 871
   - Line 1390: generic fallback 300 → `DEFAULT_EXECUTOR_CONFIG["timeouts"].get(executor_name, 300)`
     (main routed-dispatch entry point — worst-case 60x shrink for phase_b if unpatched)

3. **Wire `commit_executor.py` to config with live timeout binding.** Import
   `load_executor_config` and load the config at startup. Rebind the two
   primary internal timeout constants to config-derived values:
   - `PRE_PUSH_FAST_TIMEOUT_S` (currently hardcoded 900 at line 159): read
     from config with 900 as the fallback default.
   - `BOT_REMEDIATION_TIMEOUT_S` (currently hardcoded 600 at line 174): read
     from config with 600 as the fallback default.
   Additionally, read `config["timeouts"]["commit_executor"]` (currently 3600)
   as the effective outer budget and validate at startup that internal
   sub-timeouts fit within it. This closes the gap where
   `load_executor_config()` could be called without any returned value
   governing actual execution behavior.

4. **Add config-alignment enforcement test.** A new test in `tests/tools/`
   that verifies:
   - `executor_config.json` exists and is valid JSON.
   - Every key in `DEFAULT_EXECUTOR_CONFIG["timeouts"]` has a value ≤ the
     corresponding key in `executor_config.json["timeouts"]` (DEFAULT can never
     silently shrink below the live config).
   - Every key in `executor_config.json["timeouts"]` is present in
     `DEFAULT_EXECUTOR_CONFIG["timeouts"]` (no orphan keys without a fallback).
   - All dispatch `.get("timeouts", ...)` fallbacks reference
     `DEFAULT_EXECUTOR_CONFIG` (no hardcoded numeric fallbacks that could
     diverge). Verified by AST scan or grep of dispatch source.
   - `commit_executor.py` derives `PRE_PUSH_FAST_TIMEOUT_S` and
     `BOT_REMEDIATION_TIMEOUT_S` from config lookups, not hardcoded integer
     literals. Verified by AST scan: each constant's assignment must reference
     a config dict access (not a bare `int` node). This closes the
     commit-executor invariant gap identified in the problem statement
     (lines 38–40).
   - Catches future regressions of Mechanisms A, B, and the commit-executor
     config-binding invariant.

## Constraints

- No runtime or substrate changes. Scope is control-surface (pipeline hardening) only.
- Do not change existing timeout *values* in `executor_config.json` — the current values are intentional. Adding new keys to surface currently-hardcoded commit-executor sub-timeouts (initialized to current hardcoded defaults) is in scope; changing existing key values is not.
- Do not modify Phase A or Phase B executor internals — they already call `load_executor_config()`.
- The `DEFAULT_EXECUTOR_CONFIG` change (work item 1) only aligns the default with the already-checked-in JSON value. It does not change any live timeout budget when the JSON is present.

## Stop conditions

- Stop if enforcement test is green and dispatch no longer has fallback-to-smaller-default paths.
- Stop if max_rounds is reached.

## Acceptance criteria

- `DEFAULT_EXECUTOR_CONFIG["timeouts"]["phase_b_executor"]` == `executor_config.json["timeouts"]["phase_b_executor"]` (both 18000).
- All five `executor_dispatch.py` fallback callsites (lines 442, 803, 871, 1021, 1390) reference `DEFAULT_EXECUTOR_CONFIG` (no hardcoded numeric disagreement).
- `commit_executor.py` loads config via `load_executor_config()` and derives
  `PRE_PUSH_FAST_TIMEOUT_S` and `BOT_REMEDIATION_TIMEOUT_S` from the loaded
  config (not hardcoded integer literals). The outer
  `config["timeouts"]["commit_executor"]` budget is read and validated to
  bound internal sub-timeouts.
- Config-alignment enforcement test passes in `audit_fast.sh`.
- End-to-end dispatch → commit round-trip uses the checked-in timeout budgets, verified by inspection or test.

## Grounding / Authorization

- TASKS.md line 562: `[PIPELINE-RECOVERY/post-commit-roundtrip-2026-04-04]` is authorized as NEXT (2026-04-04, founder-authorized).
- Authorization text: "Keep routed commit/post-commit waves aligned with the checked-in live executor config so missing or partial local config cannot silently shrink the real Phase A, Phase B, or commit timeout budget before the end-to-end round-trip proof runs."
- Lane: control-surface (pipeline hardening).
- Tracked packet: this file.
