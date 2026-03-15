# S1-A GO/NO-GO Evidence Memo

**Date:** 2026-03-15
**Wave:** s1a-vm-evidence
**Class:** L4_ENABLER
**Target Gate:** G8 (Irreducible Primitive Consensus)
**Recommendation:** **CONDITIONAL GO** (see conditions below)

---

## 1. Performance Results

### Tier 1: Per-Projection Diagnostics (microsecond scale, N=10)

| Projection | VM Median (us) | Host Median (us) | Ratio | Notes |
|-----------|----------------|------------------|-------|-------|
| match.wrap | 228 | 20 | 11.1x | Entry point |
| match.equal | 218 | 18 | 11.9x | Literal equality |
| match.var | 228 | 25 | 9.2x | Variable bind |
| match.done | 212 | 13 | 16.4x | Terminal |
| match.fail | 233 | 25 | 9.2x | Catch-all |
| subst.wrap | 379 | 39 | 9.8x | Entry point |
| subst.primitive | 396 | 44 | 9.0x | Literal traverse |
| subst.var | 413 | 37 | 11.1x | Variable lookup |
| subst.done | 368 | 27 | 13.5x | Terminal |

**Tier 1 Summary:** VM is 9-16x slower per single-step projection execution. This is expected — Stage0 VM executes compiled opcodes (JSON-driven), while host path executes Python-native pattern matching.

### Tier 2: Integration Workloads (seconds scale, N=30/10)

| Workload | Median (s) | P95 (s) | Stdev (s) | Notes |
|----------|-----------|---------|-----------|-------|
| step_kernel_mu cycling A<->B | 0.013 | 0.013 | 0.0001 | Core kernel path |
| step_kernel_mu bridge mode | 0.016 | 0.016 | 0.0002 | Bridge + non-linear |
| run_engine_pipeline cycling | 4.48 | 4.51 | 0.018 | Full engine closure detection |

**Note:** Tier 2 timings include both host and VM paths in shadow mode (host path is primary, VM verifies). The integration timing represents the combined cost. Under cutover=True, the host path would be eliminated, so integration timing should be similar or slightly faster (no shadow comparison overhead).

## 2. Cutover=True Test Results

| Test | Result | What It Proves |
|------|--------|---------------|
| **TestCutoverTruePath** (10 tests) | **ALL PASS** | VM path works as primary on canonical vectors |
| simple rewrite | PASS | Basic a->b rewrite |
| stall | PASS | No-match stall behavior |
| dict rewrite | PASS | Dict pattern matching |
| first-match-wins | PASS | Ordering preserved |
| bridge mode | PASS | Kernel + bridge + VM |
| meta return | PASS | return_meta=True |
| stall meta | PASS | Stall with meta |
| output matches shadow | PASS | Cutover output == shadow output |
| multi-step | PASS | Multi-step convergence |
| nested dict | PASS | Deep pattern matching |
| **TestCutoverIntegration** (5 tests) | **ALL PASS** | VM fires through real API surface |
| engine pipeline | PASS | run_engine_pipeline with cycling closure |
| algorithm meta-circular | PASS | run_algorithm_meta_circular |
| no-fallback (match path) | PASS | _step_trusted NOT called (count=0) |
| no-fallback (stall path) | PASS | _step_trusted NOT called on stall |
| bridge integration | PASS | Bridge mode via run_algorithm_meta_circular |

**Total: 15 new cutover tests, all passing.**

## 3. No-Fallback Negative Control

The negative control instruments `_step_trusted` (the monolithic combined host path) with a call counter. Under `_STAGE0_VM_CUTOVER=True`:
- On the match path: `_step_trusted` call count = **0** (monolithic host path provably absent)
- On the stall path: `_step_trusted` call count = **0** (monolithic host path provably absent)

**Architectural note:** `_step_kernel_with_vm()` still calls `_apply_projection_trusted` for kernel.v1 and bridge projections — this is by design. The cutover replaces match.v2/subst.v2 execution with Stage0 VM, NOT kernel dispatch. The architectural split:
- **Kernel.v1 + bridge projections** → host execution via `_apply_projection_trusted` (unchanged)
- **match.v2 + subst.v2** → VM execution via `stage0_vm_step` (cutover target)

## 4. Parity Evidence (Python <-> JS)

### JS VM Bridge Parity (8 tests, all pass)

| Test | Result |
|------|--------|
| match.wrap parity | PASS |
| match.equal parity | PASS |
| match.var parity | PASS |
| match.stall parity | PASS |
| subst.wrap parity | PASS |
| subst.primitive parity | PASS |
| subst.var parity | PASS |
| subst.stall parity | PASS |

Both Python and JS Stage0 VM produce identical results on compiled match.v2 and subst.v2 bundles.

## 5. Recommendation

**CONDITIONAL GO** — The VM cutover is technically ready:
- Correctness: 15/15 cutover tests pass
- Parity: 8/8 JS tests pass
- No-fallback: Host path provably absent under cutover=True
- Integration: Engine pipeline and meta-circular paths work

**Conditions for flip:**
1. **Performance acceptance** — Tier 1 shows 9-16x per-step slowdown. Under shadow mode this is paid in addition to host path (double work). Under cutover=True, only VM path runs — so the question is whether ~200-400us per VM step is acceptable. For the current workload profile (3-30 step traces), this adds ~1-12ms per trace. Founder should confirm this is acceptable.
2. **Shadow mode removal plan** — After flip, shadow mode becomes dead code. S1-B should clean it up.

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Performance regression on large traces | Low | Medium | 9-16x per step; bounded by max_steps |
| JS substrate divergence | Very Low | High | 8 parity tests pass; shadow mode catches drift |
| Coverage gap (record_no_match bookkeeping) | Low | Low | Shadow mode validates coverage equivalence today |
| Rollback difficulty | Very Low | Low | Single flag flip: `_STAGE0_VM_CUTOVER = False` |

---

## Indicator Artifact Reference

This memo IS the indicator artifact for wave s1a-vm-evidence.
JSON indicator will be generated at commit time via `collect_l4_wave_indicators.py`.
