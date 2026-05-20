# Host Debt History (Archived from STATUS.md)

Archived: 2026-04-08. This is the wave-by-wave narrative of how host debt markers changed over time. For CURRENT debt numbers, see STATUS.md. For debt ratchet enforcement, see `tools/checks/host_semantics_baseline.json` and `tools/checks/host_authority_inventory_baseline.json`.

---

## Current Marker Breakdown (5 = 2 Py marker + 3 JS marker)

- @host_recursion: 0 (Stage0 match/substitute traversal is explicit worklist/no-self-call in both Python and JS)
- @host_builtin: 3 (1 Py + 2 JS: match/builtin surface)
- @host_iteration: 2 (1 Py + 1 JS: step_kernel_mu + JS step — BOOTSTRAP)
- @host_mutation: 0 (eliminated in W6A)
- AST_OK bootstrap: 8 (eval_seed list/dict comprehensions: 2 integer path + 2 budget path from D009 + 2 stage0_vm template materialization from P7-a + 2 stage0_vm _mu_copy from P7-a bot review fix)

Per-category markers: Py = 0 recursion + 1 builtin + 1 iteration + 0 mutation; JS = 0 recursion + 2 builtin + 1 iteration.

## Kernel Path (post S1-C)

step_kernel_mu/step() → _step_kernel_with_vm → stage0_vm_step for ALL 33 projections (kernel.v1 + bridge + match.v2 + subst.v2). Host path (_step_trusted → _apply_projection_trusted) still used by engine_pipeline only (projection_runner retired Wave 3F). W6A eliminated AST_OK bootstrap from tracked markers (refactored as compile-time, not runtime debt).

## L2 Kernel Substrate (8 sites)

1. `_stage0_match()` in eval_seed.py — @host_builtin (Stage 0 micro-match bootstrap primitive; traversal is explicit worklist/no-self-call)
2. `_stage0_substitute()` in eval_seed.py — no tracked host-recursion marker remains; traversal is explicit worklist/no-self-call
3. `step_kernel_mu()` in step_mu.py — @host_iteration (kernel execution loop — Forth's NEXT)
4. `_step_kernel_with_vm()` in step_mu.py — unmarked Stage0 VM dispatch for ALL 4 seed groups; remaining loops are coverage bookkeeping over VM attempt traces
5. `list_to_linked()` in step_mu.py — BOUNDARY boundary-normalization evidence (called by step_kernel_mu to build _projs linked list)
6. AST_OK bootstrap: 4 (eval_seed list/dict comprehensions: 2 integer path + 2 budget path from D009)

## Utility Debt (3 sites)

7. `validate_deep_eval_state()` in deep_eval.py — @host_builtin (isinstance, set operations)
8. `run_deep_eval()` in deep_eval.py — @host_builtin + @host_mutation (range iteration, history.append)

These cannot be eliminated because Stage 0 match/substitute are the irreducible bootstrap, step_kernel_mu is Forth's NEXT, and deep_eval provides iterative projection application with state tracking.

## Why 5 Is the Floor (Lower Bound)

The 5 counts explicitly marked @host_* sites across L2 kernel, utilities, and Stage0 VM. Known untracked host work includes: bounded list-to-linked boundary-normalization loops in Python and JavaScript, JS Stage0 builtin surface (stage0Match/stage0Substitute use host isinstance/keys/get internally without host-recursion markers), lambda-calculus boundary guards (assert_not_lambda_calculus/assertNotLambdaCalculus perform unmarked host recursion/isinstance/set traversal at apply_projection boundary).

STATUS.md `CURRENT` and `FLOOR` track this 5-marker cross-substrate baseline. STATUS.md `THRESHOLD` is the dashboard/pre-commit semantic ceiling and currently matches the 9-site semantic audit floor.

## Wave-by-Wave Changes

**CP-S1A (wave 25):** Python @host_mutation on match() eliminated. Floor 12→11.

**D009 (wave F):** Structural depth budget primitives. Host semantics +2. Floor 11→13. FOUNDER_OVERRIDE:2026-03-11-d009-irreducible-bootstrap.

**D005-H (wave H):** Stage 0 micro-kernel promoted to production. Host semantics +4. Floor 13→15. FOUNDER_OVERRIDE:2026-03-11-d005h-stage0-production.

**P7 Wave 1:** @host_mutation on _stage0_substitute eliminated. Floor 17→16.

**P7 Wave 4:** Structural reduction + boundary reclassification. Total markers 31→17 (-45%). Floor 16→13.

**P7 Wave 5:** Outer loop boundary reclassification. Total markers 17→11 (-35%). Floor 13→11.

**P7-a:** Stage0 VM prototype. +2 AST_OK bootstrap. Floor 11→13, then +2 (bot review fix) → 15.

**W6A:** AST_OK bootstrap reclassified as compile-time (not runtime) debt — excluded from tracked markers.

**Phase 8b (2026-01-28):** Simplified step_kernel_mu. eval_step reclassified as BOOTSTRAP_PRIMITIVE. Security hardening (27 reserved fields). Net debt: 12.

**N3 Stage0 worklist recursion marker truth ratchet (2026-05-19):** Removed stale host-recursion markers from Python `_stage0_substitute()` and JS `stage0Match()` / `stage0Substitute()` after direct source proof showed explicit worklist traversal with no self-recursive calls. Tracked marker floor 12→8.

**N3 step-kernel VM iteration marker truth ratchet (2026-05-19):** Removed stale host-iteration marker from Python `_step_kernel_with_vm()` after direct source and gate proof showed projection execution is delegated to Stage0 VM for all seed groups and the remaining loops are coverage bookkeeping over VM attempt traces. Tracked marker floor 8→7.

**N3 list-to-linked boundary demotion (2026-05-19):** Reclassified Python `list_to_linked()` and JavaScript `listToLinked()` as bounded boundary-normalization conversion loops after direct parity coverage proved matching empty, single-item, multi-item, and nested Mu value conversion behavior. Tracked marker floor 7→5; host-authority inventory remains unchanged because the converter functions, names, call sites, and loops remain present.

**Phase 7d-2/7d-3 CLOSED:** Phase 8 decided "accept as bootstrap primitive." for-loop in step_kernel_mu accepted as irreducible.

## Infrastructure (Not Debt)

- match_mu.py:match() — boundary conversion function (AST_OK: infra)
- step_mu.py:ALGORITHM_ENTRYPOINT_KEYS — constant definition (AST_OK: security whitelist)
- AST_OK:infra ceiling: 135 (current 135). NOT debt, but capped to prevent drift.
- Boundary scaffolding (while loops in match_mu.py) is NOT counted as debt — Python API conversion at boundary, expected to remain indefinitely.

## L4 Paths

- **Boot0 Architecture v0.4** (`mu/docs/core/Boot0Architecture.v0.md`) — staged bootstrap design, 9-agent reviewed
- **L4 research questions:** Can mu_equal/eval_step become projections? CPS/trampolining?
- Implementation DEFERRED until L4 research drives it
