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

**Now (updated 2026-02-10)**
1. Gates 1-5 ALL COMPLETE. Hemispheres v0 core DONE (12 projections, cross-substrate parity verified).
2. Hemisphere adversarial hardening complete (JS seed verification parity, 63 adversarial tests).
3. Keep Gate 4/5 guarantees intact: structural default active, bootstrap explicit fallback only.

**Next**
1. Hemisphere integration with rcx_engine.v1 output (engine_result → automatic hemisphere routing) COMPLETE. Core seed is done (`mu/programs/hemispheres.v1.json`, 12 projections, cross-substrate parity verified).
2. Keep all L2/L3 invariants intact (structural execution default, cross-substrate parity).

**Vector (Design Only)**
1. ~~Mu-only hemisphere routing design~~ — **PROMOTED TO NEXT** (2026-02-09). Core v0 implemented; remaining work is engine integration.
2. Content-Addressed Mu (`roadmap/ContentAddressedMu.md`) — Hash-identity as substrate property. **Level 0 IMPLEMENTED** (boundary hashing in recurrence.v2). **Level 1 IMPLEMENTED** (mu_equal eliminated, 5→4 bootstrap primitives). Levels 2-3 DESIGN only.
3. Projection indexing design (existing in `TASKS.md`). Promote only if profiling shows projection matching is the dominant runtime cost.

**Sink (Parked)**
1. Gates 6-8 (L4 Boot Chain) - per 9-agent advisor recommendation. Revisit when third substrate needed.
2. Multi-value or concurrent execution.
3. Performance-first optimizations.
4. Projection caching optimization.

Notes:
1. This roadmap is a planning view. It must not override `STATUS.md` or `TASKS.md`.
2. Any change to execution semantics must update both Python and JS substrates per L3 parity rules.
