# Mu-Only Hemispheres Design Outline (Draft)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document defines DESIGN only. Gate 5 blocker resolved (2026-02-09). Promotion to NEXT requires locked semantics.

Status: design-only. Gate 5 exit criteria met — implementation unblocked pending promotion.

## Purpose
Define native structural routing states for RCX: `r_null`, `r_inf`, `r_a`, `lobes`, and `sink`. Routing must be expressed as Mu projections, not host logic.

## Scope
1. Routing semantics and promotion rules for hemisphere placement.
2. Minimal structural data model for hemisphere entries.
3. Execution-layer requirements and tests.

## Definitions
1. `r_null`: repository for void or zero-structure outputs.
2. `r_inf`: repository for unbounded or diverging structures.
3. `r_a`: repository for closed, stable structures (post-closure).
4. `lobes`: repository for emerging structures pending closure.
5. `sink`: repository for contradictions or rejected structures that may later be re-expressed.

## Data Model (Structural)
1. Each hemisphere is a Mu linked list of entries.
2. Each entry is a Mu structure with explicit fields such as `state`, `trace_ref`, `closure_flag`, and `origin`.
3. Entries must be deterministic and free of host-only metadata.

## Routing Rules (High Level)
1. First encounter of a structure routes to `lobes`.
2. Second independent encounter with closure evidence promotes to `r_a`.
3. Contradictions or non-resolvable conflicts route to `sink`.
4. Divergence or unbounded growth routes to `r_inf`.
5. Zero-structure or void outputs route to `r_null`.

## Promotion and Re-Expression
1. `lobes` to `r_a` requires explicit closure evidence (structural, not host-derived).
2. `sink` can only re-enter the system via explicit re-expression rules defined in Mu.
3. Any promotion must be observable and traceable with deterministic events.

## Execution Layer Requirements
1. Routing projections must run in the meta-circular kernel after normalization refactor.
2. If a bootstrap path is used during transition, it must be declared and tested as such.

## Observability
1. Routing decisions must be representable as trace events without violating v2 determinism.
2. Observability must not become a new semantic channel.

## Tests Required
1. Parity vectors for routing decisions across Python and JS substrates.
2. Execution-path verification tests proving routing runs via structural projections.
3. Determinism fuzzers for routing stability.

## Open Questions
1. Minimum entry schema for each hemisphere.
2. Whether re-expression from `sink` is automatic or requires explicit triggers.
3. How `r_inf` detection is bounded without host-only heuristics.
