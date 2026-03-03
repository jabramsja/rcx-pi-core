<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-23
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py, tests/docs/test_roadmap_governance.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# North Star Semantics Lock v0

**Version:** 0.1
**Status:** REFERENCE (canonical semantic policy)
**Date:** 2026-02-23

> **Current State:** See [`STATUS.md`](../../../STATUS.md)
> **Authorization:** See [`TASKS.md`](../../../TASKS.md)
> **Scope:** This document defines SEMANTIC POLICY only — canonical decisions on undefined behavior, zero representation, non-closure outcomes, and routing tie-breaks. These policies constrain all future L4 structural waves.

## Purpose

Lock semantic decisions that must be stable before deeper bootstrap reduction (L4 Gates G6-G8). Without explicit policy, different waves could make contradictory assumptions about undefined behavior, zero canonicalization, or non-closure terminal states.

This document is the single canonical source for these policies. If a design doc or implementation contradicts this document, this document takes precedence.

## A. Undefined-as-Structure Policy

**Policy:** Undefined operations produce structural motifs (hashable Mu values), not default sink errors.

**Rationale:** In a structural substrate, "undefined" is not an error — it is a datum. Undefined results must be first-class Mu values that can be:
- Hashed (via `mu_hash_cached`)
- Compared structurally
- Stored in traces
- Pattern-matched by projections

**Constraints:**
1. Undefined operation results MUST be representable as valid Mu (pass `is_mu()` validation).
2. Undefined results MAY be reused as tools or substrate if closure/mechanism supports it — they are not inherently toxic.
3. Fail-closed still applies to **contract violations** (forged kernel fields, non-Mu input, depth/width overflow). The distinction: contract violations are structural illegality; undefined operations are structural unknowns.
4. The sentinel vocabulary for undefined motifs is not yet locked. Future waves that introduce undefined-result representations must declare their motif shapes in this document.

**v0 motif shape (Wave 22):** `{_undefined: true, op: string, lhs_hash: string|null, rhs_hash: string|null, cause: string, details: object|null}`. Implemented as `make_undefined_motif` (Python) / `makeUndefinedMotif` (JS). Wired into kernel stall meta path (`return_meta=True`, `termination_reason: "kernel_stall"`). Verified by `tests/l4_gates/test_undefined_motif_runtime_gate.py`.

**Current implementation:** Undefined operations manifest as stalls (hash-equal consecutive states in `step_kernel_mu`). The kernel stall meta path now also produces an `undefined_motif` field carrying the canonical v0 motif shape.

## B. Zero Canonicalization Policy

**Policy:** Core identity and hash operations canonicalize `+0` and `-0` to canonical `0`.

**Rationale:** IEEE 754 distinguishes `+0.0` and `-0.0`, but structural identity must be deterministic across substrates. Python and JavaScript handle signed zero differently in edge cases. Canonicalization eliminates this as a parity divergence vector.

**Constraints:**
1. `mu_hash_cached(+0.0)` MUST equal `mu_hash_cached(-0.0)`.
2. `mu_hash_cached(0)` MUST equal `mu_hash_cached(0.0)` (Python int/float unification for zero).
3. Sign-origin metadata (if ever needed) is non-identity and non-hash — it lives outside the structural equality domain.
4. JSON serialization already canonicalizes `0.0` to `0` — this policy is consistent with the existing JSON-as-Phase-0-format approach.

**Current implementation:** `mu_hash_cached()` uses `json.dumps()` for serialization, which canonicalizes `0.0` and `-0.0` to `0`. This satisfies constraints 1-2.

### B.1 Control-Channel Hash Safety Lock (Wave 24)

**Policy:** Control-flow hash paths (stall detection, convergence, recurrence trace) use dedicated `mu_hash_control`/`mu_hash_control_cached` wrappers that canonicalize integer-valued floats to int before hashing.

**Rationale:** Python `json.dumps(1.0)` produces `"1.0"` while JS `JSON.stringify(1.0)` produces `"1"`. This means `mu_hash_cached(1.0)` in Python differs from `muHashCached(1.0)` in JS, despite representing the same mathematical value. For control paths (stall detection, convergence checks, recurrence trace hashing), this divergence can cause one substrate to detect stall while the other continues iterating.

**Scope:**
- **Control paths (use `mu_hash_control*`):** stall detection in `step_kernel_mu`/`stepKernel`, `run_mu`/`run`, `run_mu_structural`/`runStructural`, `run_hemisphere_routing`, `_resolve_trace_projection_id`/`resolveTraceProjectionId`, `projection_runner`, `runSubAlgorithm`, `hash_trace_for_recurrence`/`hashTraceForRecurrence`.
- **Data paths (use `mu_hash`/`mu_hash_cached`):** observer event hashing, undefined motif output, `makeUndefinedMotif`.
- **Non-linear binding (A5→Wave 25 revert):** non-linear binding conflict checks in `match()`/`_match_inner()` use `mu_hash_cached`/`muHashCached` (content hash, NOT control hash). Wave A5 initially switched to control hash, but Wave 25 reverted: control hash canonicalizes `0.0→0`, which collapses int/float type distinction needed for correct non-linear conflict detection. See `eval_seed.py:312` comment.

**Canonicalization rules:**
1. Integer-valued floats → int: `1.0` → `1`, `-3.0` → `-3`
2. ±0.0 → 0 (consistent with §B above)
3. Non-integer floats (3.14) pass through unchanged (serialize identically in both substrates)
4. Non-numeric types pass through unchanged

**Constraints:**
1. Global `mu_hash`/`mu_hash_cached`/`muHash`/`muHashCached` MUST NOT be modified.
2. Control wrappers MUST call `assert_mu`/`isValidMu` before canonicalization.
3. `mu_hash_control(1.0)` MUST equal `mu_hash_control(1)` in both substrates.
4. `muHashControl(1)` (JS) MUST equal `mu_hash_control(1.0)` (Python) — cross-substrate parity.
5. Large integral floats at `>= 1e21` are not int-cast in Python control wrappers (to match JS scientific notation behavior); this boundary remains documented and explicit.

**Gate test:** `tests/l4_gates/test_numeric_hash_safety_lock_gate.py` (policy-lock gate test; see test file for current case count)

## C. Bounded Non-Closure Policy

**Policy:** Non-repeating outcomes that exhaust budget without closure detection must produce explicit terminal classifications, not silent hangs.

**Rationale:** The engine pipeline has a bounded iteration budget (`max_engine_iterations`). When the budget is exhausted without closure or stall, the outcome must be classifiable and observable — not an implicit "I stopped running."

**Constraints:**
1. Every engine pipeline termination MUST produce one of the terminal classifications in `classify_terminal_kind()`: `kernel_done`, `recurrence_terminal`, `exhaustion_terminal`, `engine_terminal`, `non_terminal`.
2. Budget exhaustion without closure MUST raise `RcxEngineError` with error code `engine.exhausted` (Python) or `RcxError` with matching code (JS).
3. Observer events MUST include `engine_terminal` event with `engine_exit_reason` for successful terminations.
4. The classification vocabulary (`TERMINAL_KINDS`, `ENGINE_EXIT_REASONS`) is locked by Wave 17 source-lock tests. Future extensions require updating both substrates and their gate tests.

**Current implementation:** `run_engine_pipeline()` / `runEnginePipeline()` enforce these constraints. `classify_terminal_kind()` / `classifyTerminalKind()` provide the canonical classifier (integrated into runtime predicates by Wave 19).

## D. Routing Tie-Break Policy

**Status:** DEFERRED SEMANTIC DECISION.

**What this covers:** When hemisphere routing encounters equal-priority candidates, the tie-break mechanism is currently undefined. The current implementation uses insertion order (Python dict ordering / JS object key ordering), which is deterministic per-substrate but not structurally principled.

**Evidence required before promotion:**
1. Tie-break mechanism must be **structural** (expressible as Mu projections, not host-language dict ordering).
2. Tie-break must be **deterministic** (same inputs produce same routing on any substrate).
3. Tie-break must be **parity-testable** (Python and JS produce identical routing for identical inputs).
4. Tie-break must not introduce new bootstrap primitives.

**Promotion path:** This becomes a VECTOR item in TASKS.md when evidence for constraints 1-4 is available. Until then, hemisphere routing tests assert only non-tie cases.

## E. Relationship to Boot0/Hex0

**Parity is bridge evidence, not endpoint.** Python/JS parity (L3) proves that semantics live in projections, not in host code. But L3 does not close L4 — it opens it by making the bootstrap surface explicit and measurable.

**Bootstrap endgame lock:** `SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`. This is the canonical policy locked by L4ExecutionContract.v2.md (anti-stagnation rule 13). The design split between "eliminate all bootstrap" and "irreducible bootstrap forever" is resolved: the goal is minimal bootstrap that is substrate-independent (can run on Python, JS, C, or any future host).

**Boot track mapping:**
- **N2 (Trusted-Core Freeze):** Semantic policies in this document constrain what "trusted core" means — the core must respect these policies.
- **N3 (Deterministic Replay):** Zero canonicalization and bounded non-closure directly affect replay determinism.
- **N6b (Observer Isomorphism):** Terminal classification and observer event contracts define what "isomorphic events" means.

See `roadmap/Hex0_Boot0_Checklist.md` for the full Boot0 execution and research track definitions.

## References

- [`STATUS.md`](../../../STATUS.md) — Current phase and L4 status
- [`TASKS.md`](../../../TASKS.md) — North Star invariants and work authorization
- [`roadmap/L4ExecutionContract.v2.md`](../../../roadmap/L4ExecutionContract.v2.md) — Wave classification and anti-stagnation enforcement
- [`mu/docs/core/Boot0Architecture.v0.md`](Boot0Architecture.v0.md) — Staged bootstrap architecture
- [`mu/docs/core/BootstrapStructuralBridge.v0.md`](BootstrapStructuralBridge.v0.md) — Bridge execution paths
- [`roadmap/Hex0_Boot0_Checklist.md`](../../../roadmap/Hex0_Boot0_Checklist.md) — Boot ladder acceptance criteria
