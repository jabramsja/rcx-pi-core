# RCX Roadmap (Working Draft)

> **Current State**: See [`STATUS.md`](STATUS.md)
> **Authorization**: See [`TASKS.md`](TASKS.md)
> **Scope**: This document defines SEQUENCE only. It does not track current state.

Purpose: provide a clean sequencing view across normalization, meta-circular execution, and hemispheres. This file is a planning layer only. Canonical state remains `STATUS.md` and `TASKS.md`.

Read first:
1. `STATUS.md`
2. `TASKS.md`
3. `roadmap/MANIFEST.md`
4. `roadmap/Hex0_Boot0_Checklist.md`
5. `roadmap/ContentAddressedMu.md`
6. `roadmap/MuHemispheresDesign.md`
7. `archive/roadmap/MetaCircular_Boot0_GatePlan.md` (archived reference for boot-gate constraints)

**Now**
See `TASKS.md` NOW section for active items.

**Next**
No active items — see `TASKS.md` NEXT.

**Vector (Design Only)**
1. Content-Addressed Mu (`roadmap/ContentAddressedMu.md`) — Hash-identity as substrate property. Levels 2-3 design only.
2. Projection indexing design (existing in `TASKS.md`). Promote only if profiling shows projection matching is the dominant runtime cost.

**Sink (Parked)**
1. Gates 6-8 (L4 Boot Chain) - per 9-agent advisor recommendation. Revisit when third substrate needed.
2. Multi-value or concurrent execution.
3. Performance-first optimizations.
4. Projection caching optimization.

Notes:
1. This roadmap is a planning view. It must not override `STATUS.md` or `TASKS.md`.
2. Any change to execution semantics must update both Python and JS substrates per L3 parity rules.
