# Hex0/Boot0 Checklist (One Page)

> **Current State**: See [`STATUS.md`](../STATUS.md)  
> **Authorization**: See [`TASKS.md`](../TASKS.md)  
> **Scope**: This document defines SEQUENCE and EXIT CRITERIA for operational merge gates only; canonical status remains in `STATUS.md` and `TASKS.md`.
> **Purpose**: Define merge gates and acceptance criteria for a tiny self-hosting kernel path.

## Boot Ladder

1. **Boot-0 (target-minimized)**: Trusted core reduced to the smallest defensible semantic kernel (with explicit bootstrap primitives).
2. **Boot-1**: Deterministic seed replay from Boot-0.
3. **Boot-2**: Rebuild current kernel behavior from seed plus gate loading only.
4. **Boot-3**: Python and JS reproducibility (same outputs, same typed errors, plus observer-isomorphic event stream).

## Explicit Non-Goal (Until Boot-3)

1. VM or REPL productization is out of scope until Boot-3 proof is green.

## CI Gate Matrix (C* Operational Gates)

These `C*` gates are CI/merge gates.  
Conceptual Gates `0-8` remain defined in `archive/roadmap/MetaCircular_Boot0_GatePlan.md`.

| Gate | Trigger | Command | Fail Build If |
|---|---|---|---|
| C1 Fast Integrity | PR + push + local | `./tools/audit_fast.sh` | Any lint, anti-cheat, or test phase fails |
| C2 Green Gate | CI `green_gate.yml` | `scripts/green_gate.sh python-only` | Any of 11 green-gate checks fail |
| C3 JS L3 Parity | In green gate and local | `node mu/host/js/eval_step.js` | JS parity suite not fully green |
| C4 Seed Integrity | In green gate and local | `./tools/seed_police.sh` | Seed checksum, shape, or projection-id checks fail |
| C5 Slow Kernel Path | Nightly `slow_tests.yml` | `python -m pytest -m slow -v -n auto --dist worksteal --timeout=300` | Any slow test fails or job times out |
| C6 Deep Fuzz | Weekly `weekly_deep_fuzz.yml` | `python -m pytest -m fuzzer -v -n auto --dist worksteal --timeout=600` | Any fuzzer fails or job times out |
| C7 Stress Suite | Weekly `weekly_deep_fuzz.yml` | `python -m pytest tests/stress/ -v -n auto --dist worksteal --timeout=600` | Any stress test fails or job times out |
| C8 Full Audit | Manual release gate | `./tools/audit_all.sh` | Any test, purity, anti-cheat, fixture, CLI, or parity phase fails |

## Execution Track (Boot Ladder Acceptance Criteria)

> Items below define acceptance criteria only. Activation requires explicit promotion to `TASKS.md` NEXT.

1. **N1a Parity Floor**
Acceptance: Python and JS parity is green on success paths and failure class for covered actions; typed JS errors exist at implemented throw sites.
2. **N1b Full Typed-Error Parity**  
Acceptance: every public action has Python and JS parity on success and failure class with typed `error_code` coverage.
3. **N2 Trusted-Core Freeze (Boot-0 Target)**  
Acceptance: core semantics are host-independent and documented; host-only branches are either explicitly accepted bootstrap primitives or eliminated.
4. **N3 Deterministic Replay (Boot-1)**  
Acceptance: replay from seeds is deterministic with `PYTHONHASHSEED=0`; checkpoints are reproducible.
5. **N4 Routing and Engine Priority Lock**  
Acceptance: truth-table coverage for hemisphere priority and engine handoff is green in both substrates.
6. **N5 Trust-Boundary Fail-Closed**  
Acceptance: forged kernel-like payloads fail via boundary checks; no bypass path in tests.
7. **N6a Observer Event Contract**  
Acceptance: event schema and canonicalization contract are explicitly defined for both substrates (fields, ordering, serialization rules).
8. **N6b Observer Isomorphism (Boot-3 Prerequisite)**  
Acceptance: Python and JS emit the same canonical event stream for canonical vectors, using RFC 8785 JSON canonicalization (or an equivalent canonical hash-chain over the same event payload).  
**Fail gate**: build fails if any event diverges on `event_name`, `step`, `state_hash`, `error_code`, or ordering.
Dependency: `N6a` must be complete before `N6b`.

## Research Track (Evidence Required)

1. **V1 Boot Ladder to Boot-2**  
Promotion rule: show end-to-end rebuild of current behavior from tiny boot kernel plus gate loading.
2. **V2 Content-Addressed Mu (Status)**  
L0-L2 are achieved (see `TASKS.md`). Remaining research delta is L3 evidence-gated indexing only.
3. **V3 Projection Indexing (L3 Delta)**  
Promotion rule: profile evidence that matching is `>50%` runtime and end-to-end gain is `>20%`.
4. **V4 Parity Manifest and Coverage Automation**  
Promotion rule: manifest-driven action coverage catches Python or JS action drift automatically.
5. **V5 Dual-Substrate Boot Proof (Boot-3)**  
Promotion rule: canonical vectors produce identical outputs and typed errors across Python and JS.

## Parked Track (Deferred)

1. **S1 Multi-value or concurrent execution**
2. **S2 Performance-first speculative rewrites**
3. **S3 Large caching or trie-first rollout**

Promotion rule for all SINK items: no promotion until NEXT is fully green and CI remains stable for 30 consecutive daily runs.

## Merge Policy

1. If a change touches `rcx_pi/selfhost/`, `mu/host/js/`, or seed files under `mu/`, **C1-C4 must be green**.
2. If a change touches recurrence, exhaustion, engine, or hemisphere semantics, **C1-C5 must be green**.
3. If a change touches fuzzer profiles, trust boundaries, or parity harnesses, **C1-C8 plus weekly C6-C7 must stay green**.
4. A red gate is a hard stop; docs-only follow-ups are allowed only after code gates recover.
