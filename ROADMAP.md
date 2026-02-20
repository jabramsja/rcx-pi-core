# RCX Roadmap (Working Draft)

> **Current State**: See [`STATUS.md`](STATUS.md)
> **Authorization**: See [`TASKS.md`](TASKS.md)
> **Scope**: This document defines SEQUENCE only. It does not track current state.

Purpose: provide a clean sequencing view across normalization, meta-circular execution, and hemispheres. This file is a planning layer only. Canonical state remains `STATUS.md` and `TASKS.md`.

Read first (canonical order defined in `roadmap/MANIFEST.md`):
1. `STATUS.md`
2. `TASKS.md`
3. `roadmap/MANIFEST.md`
4. `ROADMAP.md` (this file)
5. `mu/docs/core/Boot0Architecture.v0.md`
6. `mu/docs/core/BootstrapPrimitives.v0.md`
7. `mu/docs/core/SelfHosting.v0.md`
8. `mu/docs/core/Boot1LoopContract.v0.md`
9. `roadmap/ContentAddressedMu.md`
10. `mu/docs/audit/MetaCircularReadiness.v1.md`
11. `mu/docs/core/UniversalEval.v0.md` (SINK/research)

**Now**
See `TASKS.md` NOW section for active items.

**Next**
1. Boot1 Recursive Loop Contract — Shadow-merge recursive kernel loop alongside trampoline. See `TASKS.md` NEXT.

**Vector (Design Only)**
1. Content-Addressed Mu (`roadmap/ContentAddressedMu.md`) — Hash-identity as substrate property. Levels 2-3 design only.
2. Projection indexing design (existing in `TASKS.md`). Promote only if profiling shows projection matching is the dominant runtime cost.

**Sink (Parked)**
1. Gates 6-8 (L4 Boot Chain) - per 9-agent advisor recommendation. Revisit when third substrate needed.
2. Multi-value or concurrent execution.
3. Performance-first optimizations.
4. Projection caching optimization.

**Execution Contracts**
- [`roadmap/L4ExecutionContract.v1.md`](roadmap/L4ExecutionContract.v1.md) — Wave classification policy (L4_CLASS_A / MAINTENANCE)
- [`roadmap/CodexClaudeAuditContract.v1.md`](roadmap/CodexClaudeAuditContract.v1.md) — Prompt quality and audit discipline

Notes:
1. This roadmap is a planning view. It must not override `STATUS.md` or `TASKS.md`.
2. Any change to execution semantics must update both Python and JS substrates per L3 parity rules.
