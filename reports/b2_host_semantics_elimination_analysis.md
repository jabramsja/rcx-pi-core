# B2: Host-Semantics Elimination Analysis

> **Created**: 2026-03-12
> **Status**: RESEARCH — categorization needed before Stage0 implementation
> **Wave target**: Future B2 wave (host-semantics inventory)

## Summary

Current host-semantic debt: **11 tracked @host_* markers** (5 Py + 6 JS), **~199 semantic-work sites** across both substrates.

### Tracked Markers (11 total)

| Marker | Substrate | Function(s) | Eliminable? | Depends on |
|--------|-----------|-------------|-------------|------------|
| @host_recursion | Python | match-related (eval_seed.py) | **YES** | Stage0 |
| @host_recursion | Python | substitute-related (eval_seed.py) | **YES** | Stage0 |
| @host_recursion | JS | stage0Match (bootstrap_core.js) | **YES** | Stage0 |
| @host_recursion | JS | stage0Substitute (bootstrap_core.js) | **YES** | Stage0 |
| @host_iteration | Python | step/run loops (step_mu.py) | **MAYBE** | Meta-circular executor design |
| @host_iteration | JS | step (eval_step.js) | **MAYBE** | Meta-circular executor design |
| @host_iteration | JS | listToLinked (eval_step.js) | **MAYBE** | Boundary normalization decision |
| @host_builtin | Python | muHash (mu_type.py) | **NO** | Irreducible (SHA-256) |
| @host_builtin | Python | isValidMu (mu_type.py) | **NO** | Boundary validation (pre-projection) |
| @host_builtin | JS | muHash (eval_step.js) | **NO** | Irreducible (SHA-256) |
| @host_builtin | JS | isValidMu (eval_step.js) | **NO** | Boundary validation (pre-projection) |

**Score: 4 clearly eliminable, 3 theoretically eliminable, 4 likely irreducible.**

### Broader Semantic-Work Sites (~199 total)

| Category | Est. sites | Eliminable? | Notes |
|----------|-----------|-------------|-------|
| Handwritten match/subst logic | ~80-90 | **YES** — Stage0's whole point | eval_seed.py, bootstrap_core.js |
| Orchestration/routing | ~50-60 | **MOSTLY** — becomes seed-expressed | step_mu.py, engine_pipeline.py, pipeline.js, routing.js |
| Boundary validation | ~30-40 | **NO** — boundary stays host | mu_type.py, seed_integrity.py, types.js |
| Resource guards + fuel | ~10-15 | **NO** — irreducible | max_steps, stack_guard, budget counters |
| Normalization | ~15-20 | **PARTIALLY** | match_mu.py, linked-list conversion |

**Score: ~130-150 clearly eliminable, ~20-30 partial, ~40-55 staying.**

### Plausible End-State

- **Best realistic floor**: ~25-35 sites across both substrates
- **4 irreducible responsibilities** (not 4 lines of code):
  1. Apply projection (tiny trusted executor)
  2. Budget/fuel enforcement
  3. Depth/resource guard
  4. Image loading + integrity
- Going from ~199 → ~30 would be a massive structural achievement

### Biggest Removable Chunks

1. **Handwritten projection semantics** in eval_seed.py and bootstrap_core.js (~80-90 sites)
2. **Host orchestration/routing** in step_mu.py, engine_pipeline.py, pipeline.js, routing.js (~50-60 sites)
3. **Host guard/validation layers** that should become image-contract or seed-path checks (~15-20 sites)

### What Probably Remains

Per Stage0 design packets:
- `vector_2026-03-12_stage0_vm_execution_contract_v0.md`
- `vector_2026-03-12_stage0_cutover_replacement_plan_v0.md`
- `vector_2026-03-12_structuralization_research_bootstrap_surface.md`

The irreducible substrate: execution/apply, bounded iteration/fuel, depth/resource guard, image loading/integrity.

## Next Steps

1. **B2 wave**: Produce categorized JSON inventory — each site tagged: `STAGE0_ELIMINABLE`, `BOUNDARY_STAYS`, `IRREDUCIBLE_EXECUTOR`, `NORMALIZATION_TBD`
2. **Refactoring waves first** (compat shims, O(N^2), match_inner dedup) — clean house for Stage0
3. **Stage0 implementation** — the actual elimination work (multiple waves)

## Dependencies

- Stage0 design packets exist but are unimplemented
- Refactoring waves (13+) reduce noise before B2 categorization
- B2 inventory informs Stage0 implementation priority
