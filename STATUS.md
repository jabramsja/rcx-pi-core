# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

> **Document Architecture**: See [`roadmap/MANIFEST.md`](roadmap/MANIFEST.md) for reading order and linking rules across STATUS.md, TASKS.md, and roadmap docs.

---

## Current Phase

```
PHASE: 8c
NAME: Structural Selection Parity (L1-L3 COMPLETE)
```

## Projection-Based Architecture Levels

| Level | Description | Status |
|-------|-------------|--------|
| **L1: Algorithmic** | match/subst algorithms EXPRESSED as Mu projections | DONE (Python executes projections) |
| **L2: Operational** | kernel state machine EXPRESSED as Mu projections | FULL (decision: accept for-loop as bootstrap primitive) |
| **L3: Substrate Portability** | Same projections on Python and JavaScript substrates | COMPLETE |
| **L4: True Self-Hosting** | Bootstrap primitives eliminated or substrate-independent | SINK (full completion research; bounded reduction active) |

**Terminology Honesty:**
- "Projection-based" means the ALGORITHM is expressed as Mu projections (data)
- Python's `eval_step()` EXECUTES those projections (like Forth's NEXT executes threaded code)
- The "kernel" in L2 refers to `kernel.v1.json` (7 projections), NOT the deprecated `Kernel` class

## What This Means

- **L1 Algorithmic DONE**: `match_mu()` and `subst_mu()` are expressed as Mu projections. Python's `eval_step()` executes them.
- **L2 Operational FULL**: Projection SELECTION is structural (linked-list cursor in kernel.v1). Projection EXECUTION is Python (`for` loop in `step_kernel_mu`) — accepted as bootstrap primitive per Phase 8 decision.
- **Python's role**: `eval_step()` is a bootstrap primitive (like Forth's NEXT). Irreducible in current architecture.

## L2 Completion Criteria

- [x] Kernel state machine is 7 Mu projections (`kernel.v1.json`)
- [x] Match v2 with context passthrough (8 projections, `_match_ctx`)
- [x] Subst v2 with context passthrough (13 projections, `_subst_ctx`)
- [x] Projection selection uses linked-list cursor (`_remaining` field)
- [x] `step_kernel_mu()` wired to use structural kernel
- [x] Security hardening (27 reserved fields, deep validation)
- [ ] Python for-loop still drives kernel execution (accepted as bootstrap primitive)

## L3/L4 Architecture Details

**For full L3 architecture, seed categories, JS debt tracking, contraband patterns, L4 research status, P7 reduction chain, and cross-substrate testing strategy:**

See [`mu/docs/core/L3SubstrateArchitecture.v0.md`](mu/docs/core/L3SubstrateArchitecture.v0.md)

**L4 current state:** full L4 completion remains in SINK, but bounded reduction work is active. VM cutover is ACTIVE. P7 Meta-Circular Reduction Chain complete (all 33 projections via Stage0 VM). See architecture doc for full chain details.

**Key facts (summary):**
- 13 JS-loaded seed files run on both Python and JavaScript
- 4 bootstrap primitives: eval_step, max_steps, stack_guard, projection_loader (mu_equal DEMOTED)
- JS substrate: ~6,488 LOC core, 16 modules at `mu/host/js/`
- Python substrate: ~8,430 LOC, ~7,525 tests
- VM cutover ACTIVE (`_STAGE0_VM_CUTOVER = True`, all 33 projections via Stage0 VM)
- G8 PASS (classification gate, caveated, 2026-03-03)

**L3 Parity Requirement (MANDATORY — North Star #13):**
- Any change to Python projection behavior MUST be mirrored in JavaScript
- Core L3 seeds MUST be loaded in BOTH substrates
- Run `node mu/host/js/eval_step.js` after Python changes to verify JS parity
- Run `./tools/checks/check_js_debt.sh` to verify JS debt markers match Python
- Violation of parity breaks L3 and must be fixed before merge

**Related policies:**
- L4 Execution Contract: [`roadmap/L4ExecutionContract.v2.md`](roadmap/L4ExecutionContract.v2.md)
- Semantic Policy Lock: [`mu/docs/core/NorthStarSemantics.v0.md`](mu/docs/core/NorthStarSemantics.v0.md)
- Ontology Promotion Contract: [`mu/docs/core/OntologyPromotionContract.v0.md`](mu/docs/core/OntologyPromotionContract.v0.md)
- Boot0 Architecture: [`mu/docs/core/Boot0Architecture.v0.md`](mu/docs/core/Boot0Architecture.v0.md)
- Boot1 Loop Contract: [`mu/docs/core/Boot1LoopContract.v0.md`](mu/docs/core/Boot1LoopContract.v0.md)

## Debt Status

### Three-Ledger Host Debt Truth

RCX tracks host debt at three distinct granularities. Each ledger answers a different question. All three are mechanically enforced by ratchet baselines and a gate test (`tests/docs/test_debt_truth_gate.py`).

| Ledger | Count | What It Measures | Baseline Source |
|--------|-------|------------------|-----------------|
| **Tracked markers** | 8 | Narrow official `@host_*` debt marker sites (4 Py marker + 4 JS marker) | `tools/checks/host_semantics_baseline.json` |
| **Authority sites** | 217 | Named runtime sites with host-authority signals (120 Python + 97 JavaScript) | `tools/checks/host_authority_inventory_baseline.json` |
| **Total inventory sites** | 312 | Full named host-runtime surface (181 Python + 131 JavaScript) | `tools/checks/host_authority_inventory_baseline.json` |

```
THRESHOLD: 10 (dashboard/pre-commit semantic ceiling)
CURRENT: 8 (4 Py marker + 4 JS marker — per host_semantics_baseline.json)
FLOOR: 8 (see archive/status_debt_history.md for wave-by-wave explanation)
INFRA_CEILING: 135
INFRA_CURRENT: 135
```

**Direction:** Tracked markers monotonically decrease (enforced by `check_host_semantics_ratchet.py`). `THRESHOLD` carries the dashboard/pre-commit semantic ceiling; `CURRENT`/`FLOOR` carry the canonical cross-substrate tracked-marker baseline. Authority and total inventory ratcheted against baseline (enforced by `check_host_authority_inventory_ratchet.py`).

**For marker breakdown, kernel path details, site inventory, wave-by-wave history, and infrastructure classification:**

See [`archive/status_debt_history.md`](archive/status_debt_history.md)

## Testing Tiers

```
Tier 1: Fast Audit    ./tools/audit_fast.sh         ~3 min   Core tests only (local iteration)
Tier 2: Full Audit    ./tools/audit_all.sh          ~5-8 min Core + Fuzzer + Slow (before push)
Tier 3: CI Green Gate scripts/green_gate.sh          ~2 min   Core only, no fuzzers/slow (push/PR)
Tier 4: CI Nightly    scripts/green_gate.sh ci_full  ~45 min  Everything (scheduled nightly)
```

See [`.claude/rules/test-classification.md`](.claude/rules/test-classification.md) for marker rules, hook details, and enforcement. See [`mu/docs/audit/CI_POLICY.md`](mu/docs/audit/CI_POLICY.md) for full testing strategy.

## Key Files

| File | Purpose |
|------|---------|
| `STATUS.md`, `TASKS.md` | Source of truth for phase/debt and work items |
| `mu/host/python/rcx_pi/selfhost/` | Core implementation (`rcx_pi/` is symlink) |
| `mu/host/js/eval_step.js` | JavaScript substrate (L3 parity) |
| `mu/tools/executors/` | Executor scripts (Phase A/B/commit automation) |
| `mu/docs/core/` | Design specs |
| `.claude/rules/` | Conditional rules (9 files incl. learning) |
| `mu/docs/core/L3SubstrateArchitecture.v0.md` | L3/L4 architecture details (extracted from this file) |
| `archive/status_debt_history.md` | Debt marker wave-by-wave history (extracted from this file) |

---

## Grounded References (test-enforced presence)

**Terminology Lock:** `sink` (lowercase) = runtime hemisphere bucket. `SINK` (uppercase) = governance task lane. `r_a` = runtime accumulator. `Ra` = resolved-work section. See TASKS.md and `mu/docs/core/L3SubstrateArchitecture.v0.md` for full definitions.

**Post-D008 Operating Mode:** D008 GO rendered (founder, 2026-03-01; supersedes prior DEFER). G8 PASS (classification gate). VM cutover ACTIVE. All 33 projections via Stage0 VM. See architecture doc for full chain.

**Hemisphere Metabolization Contract:** COMPLETE (E1-E5 all MET, 2026-02-20). Canonical closed milestone baseline.

**Conjecture Parking:** Non-Euclidean geometry / structural linear algebra hypotheses are PARKED (not active). See TASKS.md SINK for re-evaluation trigger.

**L3 Canonical Truth:** The evaluation rules are structural data, but execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics.

---

## Gate Snapshot (Canonical)

- Gate 3: COMPLETE (2026-02-07)
- Gate 4: COMPLETE (2026-02-07 structural cutover)
- Gate 5: COMPLETE (2026-02-09 meta-circular parity verified)
- Gate 8: PASS (classification gate, caveated, 2026-03-03)

Current Recurrence Layer: META_CIRCULAR
Current Exhaustion Layer: META_CIRCULAR

**Current Algorithm Execution:**
- `run_algorithm_meta_circular()` defaults to `step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")`
- Algorithm runtime is bridge-backed meta-circular

---

## Historical Archives

- Phase history (Jan-Mar 2026): [`archive/status_history_jan_mar_2026.md`](archive/status_history_jan_mar_2026.md)
- Debt marker history: [`archive/status_debt_history.md`](archive/status_debt_history.md)
- L3/L4 architecture details: [`mu/docs/core/L3SubstrateArchitecture.v0.md`](mu/docs/core/L3SubstrateArchitecture.v0.md)

**Last updated:** 2026-05-19 (N3 Stage0 worklist recursion marker truth ratchet — tracked marker floor 12→8)
**Next milestone:** Hemisphere Metabolization Contract remains the closed milestone baseline (E1-E5 all MET). Canonical authorization remains TASKS.md.
**Active NEXT items:** See TASKS.md.
