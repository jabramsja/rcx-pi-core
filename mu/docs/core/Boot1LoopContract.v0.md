<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-18
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Boot1 Recursive Loop Contract v0

**Version:** 0.1
**Status:** DESIGN SPEC (NEXT — shadow-merge implementation authorized, founder D1=YES 2026-02-16)
**Date:** 2026-02-14
**VECTOR item:** Boot1 Recursive Loop Contract (TASKS.md)
**Parallel to:** GAP-10-LOOP trampoline (CLOSED, `rcx_engine.v1.json` v1.3.0)

---

## 1. Purpose and Non-Goals

### Purpose

Define the recursive kernel loop primitive that **replaces** the current trampoline path for engine re-entry. The trampoline (`engine.exhaustion_done_freeze` → `{_run_engine: ...}` → `engine.init_config`) was explicitly labeled TRANSITIONAL (founder directive, Round 16D). This contract specifies the Boot1 mechanism that supersedes it.

The core question: **Can the engine's loop-back decision be expressed as a self-re-entry primitive within the projection system, eliminating the trampoline entirely?**

### What Boot1 Loop Replaces

Currently, when `action=freeze` is detected after exhaustion:

```
engine.exhaustion_done_freeze:
  pattern: { ..., _exhaustion_result: { action: "freeze", ... } }
  body:    { _run_engine: { projections, input, max_steps, frozen } }
```

The `{_run_engine: ...}` envelope is consumed by the **host** effect handler loop (`run_engine_pipeline` in Python/JS), which re-enters the engine state machine. The loop-back decision is structural (made by the projection), but the loop-back **execution** is host code.

Boot1 Loop aims to make the loop-back execution also structural — a recursive self-application of the engine projection set, not a host-level `state = next_state` branch.

### Non-Goals

1. **Eliminate the host effect handler entirely.** The effect handler loop services `_boundary_request` operations (run_trace, hash_trace, run_algorithm). These are genuine host effects (I/O with the substrate). The host loop remains for effects; Boot1 Loop targets only the **re-entry decision**.

2. **Add new bootstrap primitives.** The current 4 primitives (eval_step, max_steps, stack_guard, projection_loader) are the ceiling. Boot1 Loop must compose from existing primitives, not introduce new ones.

3. **Change engine semantics.** The 10-step stall-fix-promote cycle, boundary request protocol, and terminal result shape are invariant. Boot1 Loop is a **mechanism** change, not a **semantic** change.

4. **Require meta-circular kernel for engine.** The engine seed runs at APPLICATION layer via bootstrap evaluator. Boot1 Loop does not promote engine projections to META-CIRCULAR.

5. **Break L3 parity.** Both substrates must implement the same mechanism.

### Control Plane vs Semantic Profiles

`_tail_call` is an **engine-local control-plane protocol**, not a general-purpose domain opcode. It is recognized only by `run_engine_pipeline` and has no meaning outside the engine effect handler loop. Domain projections never see, produce, or consume `_tail_call` — it exists solely to express the engine's re-entry decision.

**Semantic polymorphism is achieved via seed/gate profiles, not by exposing `_tail_call` globally.** Different computational models are expressed by loading different seed sets and gate configurations:

| Profile | Seeds / Gates | Loop Behavior |
|---------|--------------|---------------|
| Acyclic / classical | Standard engine + exhaustion | Terminal on first exhaustion (no freeze) |
| Cyclic-AFA | Engine + recurrence + exhaustion | Freeze on closure → re-entry via trampoline/Boot1 |
| HoTT-style | Future: path-equivalence seeds | Structural homotopy reduction |
| SKI-style rewrite | Combinator projection sets | Pure rewrite, no engine loop needed |

Each profile is **data-driven**: the projections loaded into the engine determine its behavior. The host loop (`run_engine_pipeline`) is invariant across profiles — it steps projections, services boundary requests, and handles re-entry. `_tail_call` is part of the loop's control plane, not the profile's semantic layer.

This separation preserves **substrate portability**. Any host (Python, JS, or future FPGA/verified VM) implements the same bounded control-plane loop. Profile behavior lives in seeds (JSON data), not host code. Adding a new semantic profile requires new seeds and gates, not new host branches.

---

## 2. ABI Compatibility

### Current Re-Entry Envelope

The trampoline ABI is the `{_run_engine: ...}` envelope:

```json
{
  "_run_engine": {
    "projections": [...],
    "input": <Mu>,
    "max_steps": <integer>,
    "frozen": <Mu | null>
  }
}
```

This envelope is produced by `engine.exhaustion_done_freeze` and consumed by either:
- `engine.init_config` (when `max_steps` and `frozen` are present), or
- `engine.init` (when only `projections` and `input` are present)

### Boot1 Compatibility Requirement

**The re-entry envelope MUST remain `{_run_engine: ...}`.** Boot1 Loop changes HOW the envelope is consumed, not WHAT the envelope contains.

Specifically:

| Property | Trampoline (current) | Boot1 Loop (target) |
|----------|---------------------|---------------------|
| Envelope shape | `{_run_engine: {projections, input, max_steps, frozen}}` | **Same** |
| Producer | `engine.exhaustion_done_freeze` projection | **Same** |
| Consumer | Host effect handler loop (`run_engine_pipeline`) | Boot1 recursive applicator |
| Re-entry point | `engine.init_config` projection | **Same** |
| `_config` carry-through | Yes, all 8 intermediate projections | **Same** |

### Migration Path (No Flag Day)

The transition from trampoline to Boot1 Loop follows the 3-merge cutover rule (TASKS.md, Round 16D):

1. **Shadow merge**: Boot1 Loop runs in parallel, results compared but not used
2. **Default flip merge**: Boot1 Loop becomes default, trampoline is fallback
3. **Trampoline removal merge**: `engine.exhaustion_done_freeze` body simplified (no more `{_run_engine: ...}` envelope needed if Boot1 Loop handles re-entry internally)

At each merge, existing `{_run_engine: ...}` tests must pass unchanged.

---

## 3. Recursive / Tail-Call Semantics

### The Problem

The engine's freeze-loop is structurally a tail call:

```
exhaustion_done_freeze(state) → run_engine(projections, result, max_steps, frozen)
```

The result of `exhaustion_done_freeze` IS the result of the recursive `run_engine` call — there is no continuation after the re-entry. This is the textbook definition of a tail position (cf. R7RS §3.5).

### Option A: Structural Tail-Call (Preferred)

Express re-entry as a **tail-call marker** that the evaluator recognizes:

```json
{
  "_tail_call": {
    "projections": [...],
    "input": <Mu>,
    "max_steps": <integer>,
    "frozen": <Mu | null>
  }
}
```

The host effect handler loop (`run_engine_pipeline`, NOT `eval_step`) recognizes `_tail_call` as a continuation that replaces the current state rather than nesting. This is the Clojure `trampoline` pattern.

**Clarification (Round 17B adversary review):** The actual `eval_step` primitive (`eval_seed.py:step()`) is a pure first-match-wins projection applicator. It does NOT inspect `_boundary_request`, `_tail_call`, or any special fields. ALL structural inspection lives in the host wrapper `run_engine_pipeline`. Adding `_tail_call` therefore does NOT change the `eval_step` primitive — it adds a branch to the host loop that already contains 4 such branches (stall detection, `_boundary_request` dispatch, `_is_engine_terminal` detection, trampoline `_run_engine` initial wrapping).

**Implications:**
- `_tail_call` becomes a kernel-reserved field (added to `KERNEL_RESERVED_FIELDS`)
- The host loop (`run_engine_pipeline`) adds a branch: if `next_state` has `_tail_call`, extract payload, replace `state`, continue
- No stack growth — the loop is O(1) space per re-entry
- No change to `eval_step` — the actual primitive remains untouched

**Classification (Round 17B verdict: AMBIGUOUS):** Under a strict definition ("primitive = anything `eval_step` must know about"), `_tail_call` is NOT a primitive. Under a broader definition ("primitive = anything the trusted host base must recognize"), it IS one. The contract adopts the strict definition: `eval_step` is unchanged, only the host loop wrapper gains a branch. This is categorically identical to how `_boundary_request` was added.

**Honest trade-off:** The current trampoline has `engine.init_config` (a projection) recognize `{_run_engine: ...}` via pattern matching. Boot1 `_tail_call` would have the HOST recognize the re-entry signal before projections see it. This moves re-entry recognition FROM projections TO the host — the opposite direction from "making re-entry more structural." The benefit is explicit O(1) stack guarantee and clean separation of control flow from data flow. The cost is one more host-side branch.

### Option B: Self-Applying Projection Set (Pure)

Engine projections include themselves in their output, enabling self-application:

```json
{
  "engine.exhaustion_done_freeze": {
    "pattern": { ..., "action": "freeze" },
    "body": {
      "_apply_projections": {
        "projections": {"var": "projs"},
        "value": { ... re-entry state ... }
      }
    }
  }
}
```

A single `_apply_projections` primitive would let any projection set self-apply.

**Implications:**
- Truly recursive — projections invoke themselves
- Requires bounded fuel (max_steps) to prevent infinite recursion
- `_apply_projections` IS a new primitive (violates non-goal #2)
- Stack depth proportional to re-entry count (unless TCO'd)

### Option C: CPS Transform (Deferred)

Convert the engine state machine to continuation-passing style. Each projection's body includes an explicit continuation:

```json
{
  "body": {
    "_continuation": {
      "next_projection_id": "engine.init_config",
      "args": { ... }
    }
  }
}
```

**Implications:**
- Most general — supports arbitrary control flow
- Most complex — every projection body must carry continuations
- Significant seed rewrite (all 11 engine projections)
- Deferred to L4 research

### Recommendation

**Option A (Structural Tail-Call)** is the preferred path:
- Zero new primitives (tail-call recognition is protocol, not primitive)
- O(1) space (no stack growth)
- Minimal seed change (only `engine.exhaustion_done_freeze` body changes)
- Compatible with existing `{_run_engine: ...}` ABI during shadow period
- Well-understood precedent (Scheme, Clojure, Haskell)

### Bounded Execution Model

Regardless of option chosen, Boot1 Loop MUST preserve bounded execution:

| Bound | Current (Trampoline) | Boot1 Loop |
|-------|---------------------|------------|
| Max engine iterations | `max_engine_iterations` (default 20) | **Same** — counts re-entries |
| Max steps per engine run | `max_steps` (default 100) | **Same** — per-entry budget |
| Max algorithm iterations | `max_algorithm_iterations` (default 50) | **Same** |
| Stack depth | O(1) (host loop) | O(1) (tail-call) or O(n) (Option B) |

The `max_engine_iterations` counter MUST count across re-entries. A Boot1 Loop that resets the counter on re-entry creates an unbounded execution bug.

---

## 4. Safety Invariants

### S1: No Primitive Count Increase

Boot1 Loop must not increase the bootstrap primitive count beyond the current 4 (eval_step, max_steps, stack_guard, projection_loader). If Option A adds `_tail_call` recognition to the evaluator, this must be justified as protocol (structural inspection of output), not a new primitive.

### S2: Bounded Re-Entry

The total number of re-entries across the full engine pipeline execution is bounded by `max_engine_iterations`. This bound applies whether re-entry is host-driven (trampoline) or projection-driven (Boot1 Loop). Violation → fail-closed RuntimeError.

### S3: Boundary Request Integrity

Re-entry must not bypass `_boundary_request` validation. The effect handler loop's security checks (inject_key not in KERNEL_RESERVED_FIELDS, boundary result validation) must fire on every boundary request, regardless of whether the current engine iteration is an initial entry or a re-entry.

### S4: Terminal Result Shape Preserved

The 8-key terminal result shape is invariant:

```
{ value, closure_detected, tau_step, exhaustion_detected,
  operator_frozen, frozen_set, action, stall }
```

Boot1 Loop changes the re-entry mechanism, not the terminal output. All existing terminal-shape assertions must pass unchanged.

### S5: `_config` Carry-Through Preserved

`_config: {projections, max_steps}` must be carried through all intermediate projections during re-entry, exactly as in the current trampoline. The carry-through enables the re-entry envelope to be constructed from projection-local state (no host-side stashing).

### S6: First-Match-Wins Ordering Preserved

`engine.exhaustion_done_freeze` MUST precede `engine.exhaustion_done_terminal` in projection order. This is security-critical: the literal `action: "freeze"` pattern must match before the variable `action: {"var": "action"}` catchall. Boot1 Loop must not reorder projections.

### S7: No `_config` Leak to Terminal

`_config` is an internal carry-through field. It must NOT appear in the terminal 8-key result. Boot1 Loop re-entry must consume `_config` (use it to construct the re-entry envelope) and not propagate it to the output.

---

## 5. Parity Plan (Python / JS)

### Implementation Parity

Both substrates must implement Boot1 Loop identically:

| Component | Python | JS |
|-----------|--------|-----|
| Tail-call recognition | `run_engine_pipeline()` in `step_mu.py` | `runEnginePipeline()` in `eval_step.js` |
| `_tail_call` field check | `isinstance(next_state, dict) and "_tail_call" in next_state` | `typeof nextState === 'object' && '_tail_call' in nextState` |
| Re-entry counter | Shared with `max_engine_iterations` | **Same** |
| `_tail_call` in `KERNEL_RESERVED_FIELDS` | Added to `step_mu.py` constant | Added to `eval_step.js` constant |

### Parity Test Plan

Test categories required before VECTOR → NEXT promotion:

1. **Freeze path parity** (extends `TestEngineLoopPathParity`):
   - Input triggers freeze → verify both substrates produce identical terminal result after re-entry
   - Verify re-entry count is identical

2. **Non-freeze terminal parity** (existing — must not regress):
   - Input does NOT trigger freeze → terminal produced directly
   - Verify identical 8-key result

3. **Multi-re-entry parity**:
   - Craft input that triggers freeze N times → verify both substrates produce identical result after N re-entries
   - Verify `max_engine_iterations` is respected identically

4. **Stall/fix/freeze interaction parity**:
   - Input triggers stall → fix → freeze → re-entry → terminal
   - Full pipeline parity across substrates

5. **`_config` leak regression**:
   - Verify `_config` never appears in terminal output on either substrate
   - Verify `_tail_call` never appears in terminal output on either substrate

6. **Shadow mode comparison** (cutover merge 1):
   - Run both trampoline and Boot1 Loop on same inputs, assert identical results
   - This is the acceptance gate for the default-flip merge

### Seed Parity

If `engine.exhaustion_done_freeze` body changes (e.g., `{_run_engine: ...}` → `{_tail_call: ...}`), both substrates load the same `rcx_engine.v1.json`. No seed divergence possible.

### Security Prerequisites (Round 17B Adversary Findings)

The following prerequisites were required before Boot1 implementation planning can advance:

**P1 (CRITICAL): JS boundary result validation gap — RESOLVED (Round 17D).**
~~Python `run_engine_pipeline` validates boundary results via `validate_no_kernel_reserved_fields(result, ...)`. JS `runEnginePipeline` does NOT.~~ **Fixed:** JS `runEnginePipeline` now calls `validateNoKernelReservedFields(result, 'boundary_result(' + operation + ')')` before injection, matching Python parity. 2 regression lock tests added. Merged in hemisphere hardening PR #249.

**P2 (HARDENING): `_run_engine` in `KERNEL_RESERVED_FIELDS` — RESOLVED (Round 20B).**
`_run_engine` is now reserved in both Python and JavaScript runtimes. This closes the defense-in-depth gap for trampoline envelope forgery.

**P3 (REQUIRED): `_tail_call` in `KERNEL_RESERVED_FIELDS` from day one — RESOLVED (Round 20C).**
`_tail_call` is now reserved in both Python and JavaScript runtimes ahead of Boot1 implementation, preventing control-flow forgery by domain data.

---

## 6. Cutover Mapping

### Boot1 Sunset Gates (from TASKS.md, Round 16D)

The 6 cutover gates and their Boot1 Loop mapping:

| Gate | Requirement | Boot1 Loop Status |
|------|------------|-------------------|
| **G1: ABI Compatibility** | Boot1 re-entry uses same `{_run_engine: ...}` envelope | Designed (§2) — same envelope during shadow, `_tail_call` after cutover |
| **G2: Parity** | Boot1 loop == trampoline on all canonical vectors | Test plan drafted (§5) — shadow mode comparison required |
| **G3: Security** | No new bypass paths, no primitive count increase | Invariants S1–S7 defined (§4) — requires agent review |
| **G4: Bootstrap Discipline** | No contradiction with Boot0 v0.4 | Compatible — `_tail_call` is protocol, Boot0 unchanged |
| **G5: CI Stability** | All CI gates green across 3 consecutive merges | Enforced by 3-merge cutover rule |
| **G6: Contract Preservation** | EngineNew 10/10 invariants preserved | Terminal shape, _config carry-through, first-match-wins all preserved (§4) |

### 3-Merge Cutover Rule

| Merge | What Changes | Rollback Cost |
|-------|-------------|---------------|
| **1. Shadow** | Add `_tail_call` recognition to host loop. Trampoline still default. Shadow comparison in test suite. | Delete shadow code. Zero runtime impact. |
| **2. Default Flip** | Boot1 Loop is default path. Trampoline preserved as `_legacy_trampoline=True` flag. | Flip flag back. One-line change. |
| **3. Removal** | Delete trampoline code path. `engine.exhaustion_done_freeze` body produces `_tail_call` instead of `{_run_engine: ...}`. Seed version bump. | Revert commit. Seed rollback. |

### What Blocks Cutover

Cutover from trampoline to Boot1 Loop is blocked until:

1. This contract doc is approved (you are reading it)
2. Shadow merge demonstrates parity on all canonical vectors
3. 9-agent security review of shadow merge (verifier + adversary minimum)
4. All 6 gates satisfied
5. Explicit VECTOR → NEXT promotion in TASKS.md

---

## 7. Open Questions and Promotion Criteria

### Open Questions

**Q1: Is `_tail_call` a new primitive?**

**Round 17B adversary verdict: AMBIGUOUS.**

Arguments for "no" (strict definition): The actual `eval_step` primitive (`eval_seed.py:step()`) is a pure first-match-wins projection applicator. It does NOT inspect `_boundary_request`, `_tail_call`, or any special fields. Adding `_tail_call` recognition to `run_engine_pipeline` does not change `eval_step`. Under "primitive = anything `eval_step` must know about," `_tail_call` is protocol.

Arguments for "yes" (broad definition): Under "primitive = anything the trusted host base must recognize," `_tail_call` IS a new primitive. It adds a control flow branch to code that both substrates must implement identically. Unlike `_boundary_request` (which is an EFFECT requiring host I/O), `_tail_call` is PURE CONTROL FLOW that could theoretically be expressed within projections.

**Resolution path:** The contract adopts the strict definition. If 9-agent review at shadow merge rejects this, Option C (CPS) becomes the research direction.

**Q2: Should `_tail_call` be engine-specific or general-purpose?**

**Round 17B adversary verdict: ENGINE_SPECIFIC.**

Engine-specific: `_tail_call` only recognized inside `run_engine_pipeline`, not in `run_mu` or `step_kernel_mu`. Narrower scope, easier to audit.

General-purpose: REJECTED. If `run_mu` recognized `_tail_call`, any domain projection could produce `{_tail_call: {projections: [ATTACKER_PROJS], ...}}` and redirect execution to an attacker-controlled projection set. Even with `max_steps` fuel, this is projection set injection. Domain projections are not validated for `_tail_call` in their bodies.

**Adversary caveat:** If `_tail_call` is engine-specific, this is functionally equivalent to the current trampoline — one host branch replaced by another. The structural progress is limited to cleaner separation of control flow from data flow, not elimination of host involvement. The contract acknowledges this trade-off (see §3 "Honest trade-off").

**Q3: What happens to `{_run_engine: ...}` after removal merge?**

After the trampoline is removed, `{_run_engine: ...}` is still the **initial** entry envelope (produced by the caller, consumed by `engine.init` / `engine.init_config`). Only the **re-entry** envelope changes (from `{_run_engine: ...}` to `{_tail_call: ...}`).

The initial entry path is unchanged. `run_engine_pipeline` still wraps its input in `{_run_engine: ...}` on line 1 of the function.

**Q4: How does Boot1 Loop interact with Checkpoint/Resume?**

If a checkpoint is taken mid-re-entry, the resume token must capture the re-entry count and fuel state. Boot1 Loop's bounded execution model (S2) ensures the re-entry count is always available. The `_config` carry-through (S5) provides the fuel state. These compose naturally with the Checkpoint/Resume Contract (separate VECTOR item).

### Promotion Criteria (VECTOR → NEXT)

All 6 criteria from TASKS.md must be satisfied; security prerequisites P1–P3 are resolved and must remain green:

1. **Boot1LoopContract design doc approved** — This document. Requires founder review.
2. **ABI compatibility demonstrated** — §2 defines shared envelope. Shadow merge proves compatibility.
3. **Parity test plan drafted** — §5 defines 6 test categories. Implementation deferred to NEXT.
4. **Security review: no new bypass paths or primitive count increase** — §4 defines 7 safety invariants. Agent review required at shadow merge.
5. **Security prerequisites resolved (and preserved)** — P1 (Round 17D), P2 (Round 20B), P3 (Round 20C).
6. **Explicit VECTOR → NEXT promotion in TASKS.md with rationale** — Not yet. Pending founder approval of this doc.

---

## References

- `mu/docs/core/Boot0Architecture.v0.md` — Staged bootstrap design (Boot0 → Boot1 → Boot2)
- `mu/programs/rcx_engine.v1.json` — Engine seed v1.3.0 (11 projections, trampoline)
- `rcx_pi/selfhost/step_mu.py:run_engine_pipeline()` — Python host effect handler loop
- `mu/host/js/eval_step.js:runEnginePipeline()` — JS host effect handler loop
- `mu/docs/core/EngineNewFixContract.v0.md` — Sibling contract (GAP-04-FIX, CLOSED)
- R7RS §3.5 — Scheme tail-call specification
- Clojure `trampoline` — `(trampoline f & args)` for mutual recursion without stack growth
