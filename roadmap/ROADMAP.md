# RCX Roadmap (Working Draft)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document defines SEQUENCE only. It does not track current state.

Purpose: provide a clean sequencing view across normalization, meta-circular execution, and hemispheres. This file is a planning layer only. Canonical state remains `STATUS.md` and `TASKS.md`.

Read first:
1. `STATUS.md`
2. `TASKS.md`
3. `roadmap/NormalizationDecisionMemo.md`
4. `roadmap/AlgorithmNormalizationSpec.v0.md`
5. `roadmap/MetaCircular_Boot0_GatePlan.md`
6. `roadmap/MuHemispheresDesign.md`

**Now (9-agent reviewed 2026-02-04)**
1. Confirm the normalization strategy decision in `roadmap/NormalizationDecisionMemo.md`. If accepted, treat it as the official direction.
2. **Gate 1 first:** Complete the normalization spec in `roadmap/AlgorithmNormalizationSpec.v0.md`. Resolve all open questions (required for Gate 1 exit). Once approved, migrate to `docs/core/`.
3. **Gate 0 second:** Run baseline freeze immediately before Gate 2 begins (not standalone). Lock parity and checksums.
4. Explicitly block hemisphere implementation until Gate 5 completes. Design only is allowed.

**Next**
1. Execute Gates 1 → 0 → 2 → 3 → 4 → 5 per `roadmap/MetaCircular_Boot0_GatePlan.md`. This is the canonical path to true meta-circular algorithm execution.
2. Gate 3 must include 4 fuzzer edge cases (per 9-agent review): frozen list stress, multi-state cycles, quadruple var, mixed patterns.
3. Gate 2 adapter window must close explicitly before Gate 4 (hard requirement).
4. After Gate 5, hemisphere implementation may proceed.

**Vector (Design Only)**
1. Mu-only hemisphere routing design in `roadmap/MuHemispheresDesign.md`. This is blocked on completion of the normalization refactor. No implementation until Gate 5 exit criteria are met.
2. Projection indexing design (existing in `TASKS.md`). Promote only if profiling shows projection matching is the dominant runtime cost.

**Sink (Parked)**
1. Gates 6-8 (L4 Boot Chain) - per 9-agent advisor recommendation. Revisit when third substrate needed.
2. Multi-value or concurrent execution.
3. Performance-first optimizations.
4. Projection caching optimization.

Notes:
1. This roadmap is a planning view. It must not override `STATUS.md` or `TASKS.md`.
2. Any change to execution semantics must update both Python and JS substrates per L3 parity rules.
