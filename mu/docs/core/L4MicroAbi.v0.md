<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-03-14
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_l4_current_state_truth.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
-->

# L4 Micro-ABI v0

**Purpose:** Define a concrete Application Binary Interface for L4 (True Self-Hosting) that maps directly to the existing L4 exit gates (G1-G8). The ABI specifies the minimal surface a substrate must implement, and nothing more.

**Status:** DESIGN_SPEC (full L4 completion remains SINK; bounded reduction active in NEXT). This defines the target interface. No runtime rewrite is proposed.

---

## ABI Surface

The L4 Micro-ABI defines exactly three operations. Any substrate (Python, JS, C, verified VM) that implements these three operations can run RCX projections.

### `rcx_load(image_bytes) -> state`

Load a seed image into an initial evaluation state.

```
Input:  image_bytes  — raw bytes of a JSON seed file (or future binary format)
Output: state        — { projections: [...], value: null, fuel: 0 }

Invariants:
  - DETERMINISTIC: same bytes → same state (no host entropy)
  - FAIL-CLOSED: malformed input → error, never partial state
  - CONTENT-ADDRESSED: SHA256 checksum verified against hardcoded expectation
  - NO HIDDEN CHANNELS: no network I/O, no env vars, no dynamic code gen
```

**Current implementation:** `seed_integrity.py:load_verified_seed()` + `projection_loader.py`

**Maps to L4 gate:** G1 (primitive inventory — loader is one of 4), G5 (content-addressed)

---

### `rcx_step(state) -> { status, state, error_code }`

Apply one evaluation step: try each projection in order, return on first match.

```
Input:  state  — { projections: [...], value: <Mu>, fuel: int }
Output: {
  status:     "matched" | "stalled" | "fuel_exhausted" | "error",
  state:      { projections: [...], value: <Mu'>, fuel: int },
  error_code: null | string
}

Invariants:
  - DETERMINISTIC: same state → same output
  - FAIL-CLOSED: invalid Mu → error status, never silent corruption
  - FIRST-MATCH-WINS: projection order is the only selection rule
  - NO DOMAIN BRANCHING: step never inspects _run_engine, _tail_call, etc.
  - PURE: no mutation of input state; output is a new state
  - CANONICAL MU BOUNDARY: input/output are valid Mu (depth ≤ 300, width ≤ 1000)
  - EXPLICIT FUEL: fuel decrements by 1 per step; fuel=0 → fuel_exhausted
```

**Current implementation:** `eval_seed.py:step()` (projection application) + `mu_type.py:MAX_MU_DEPTH` (stack guard) + `step_mu.py:step_kernel_mu()` (fuel accounting)

**Maps to L4 gates:** G2 (eval_step minimality), G3 (max_steps as structural data), G4 (stack_guard depth-only), G6 (match/subst bootstrap status), G7 (eval_step non-recursive)

---

### `rcx_run(state, fuel) -> state`

Apply `rcx_step` repeatedly until stall or fuel exhaustion.

```
Input:  state  — initial evaluation state
        fuel   — integer step budget
Output: state  — terminal state (stalled or fuel-exhausted)

Invariants:
  - DETERMINISTIC: same (state, fuel) → same terminal state
  - FAIL-CLOSED: fuel=0 returns input state unchanged
  - NO HIDDEN HOST CONTROL: loop is mechanical repeat of rcx_step
  - STALL = FIXED POINT: consecutive states hash-equal → stop
  - FUEL ACCOUNTING: total steps ≤ fuel (never exceeded)
```

**Current implementation:** `step_mu.py:run_mu()` (repeat-until-stall) composed with `step_kernel_mu()` (single kernel pass)

**Maps to L4 gates:** G3 (fuel is structural data), G8 (irreducible primitive consensus — `rcx_run` is the composition that G8 classifies)

---

## Gate Mapping Table

| Gate | ABI Element(s) | Pass/Fail Criteria | Proof Command |
|------|----------------|-------------------|---------------|
| **G1** | `rcx_load` | Exactly 4 `BOOTSTRAP_PRIMITIVE` markers (no unlabeled primitives) | `grep -rn "BOOTSTRAP_PRIMITIVE" rcx_pi/selfhost/ mu/host/js/eval_step.js \| grep -v test` |
| **G2** | `rcx_step` | `step()` is pure first-match-wins, no domain key inspection | `grep -n "def step\|_boundary_request\|_tail_call\|_run_engine" rcx_pi/selfhost/eval_seed.py` |
| **G3** | `rcx_step`, `rcx_run` | `max_steps` is plain integer decremented per iteration | `grep -n "max_steps" rcx_pi/selfhost/step_mu.py \| head -10` |
| **G4** | `rcx_step` | `MAX_MU_DEPTH` is integer threshold, no `sys.getrecursionlimit()` | `grep -n "MAX_MU_DEPTH\|getrecursionlimit" rcx_pi/selfhost/mu_type.py` |
| **G5** | `rcx_load` | `load_verified_seed()` validates structure + SHA256, no network I/O | `grep -n "load_verified_seed\|sha256" rcx_pi/selfhost/seed_integrity.py \| head -10` |
| **G6** | `rcx_step` | `match()`/`substitute()` are bootstrap code, marked `BOOTSTRAP`, called only from `apply_projection()` | `grep -n "def match\|def substitute\|BOOTSTRAP" rcx_pi/selfhost/eval_seed.py \| head -10` |
| **G7** | `rcx_step` | `step()` is non-recursive single-pass loop | `grep -n "def step\|step(" rcx_pi/selfhost/eval_seed.py` |
| **G8** | All three | Each primitive classified IRREDUCIBLE/REDUCIBLE_WITH/ELIMINATED with evidence | See `L4ExitChecklist.v0.md` G8 classification table |

---

## ABI-to-Boot Layer Mapping

The L4 Micro-ABI maps cleanly onto the Boot0 Architecture (Boot0Architecture.v0.md):

| ABI Operation | Boot Layer | Components |
|---------------|-----------|------------|
| `rcx_load` | Boot0 | `projection_loader` primitive + JSON parsing |
| `rcx_step` | Boot0 + Boot1 | `eval_step` primitive + bootstrap or structural match/subst |
| `rcx_run` | Derived | Composed from `eval_step` + `max_steps` + hash comparison |

**Key insight:** `rcx_run` is NOT a new primitive. It is a mechanical composition:

```
rcx_run(state, fuel) =
  for i in range(fuel):
    next = rcx_step(state)
    if hash(next.value) == hash(state.value): return next  # stall
    state = next
  return state  # fuel exhausted
```

The iteration host loop (`for`) is the irreducible substrate. This is the Boot0/Forth NEXT equivalent.

---

## What the ABI Excludes (by design)

These are NOT part of the L4 Micro-ABI. They are programs that run ON TOP of it:

| Excluded | Why | Where It Lives |
|----------|-----|---------------|
| Kernel state machine | Program, not substrate | `kernel.v1.json` (Boot2) |
| Recurrence detection | Program, not substrate | `recurrence.v1.json` (Boot2) |
| Hemisphere routing | Program, not substrate | `hemispheres.v1.json` (application) |
| Engine pipeline | Orchestration scaffold | `step_mu.py:run_engine_pipeline()` |
| Observer events | Debugging convenience | Not part of evaluation semantics |

**The ABI is the hardware. Everything else is software.**

---

## L4 Reduction Paths (from L4ExitChecklist.v0.md)

| ABI Op | Current Substrate | L4 Reduction Path | Status |
|--------|------------------|--------------------|--------|
| `rcx_load` | JSON + Python `json.load` | Binary format (Hex0 Stage 0) | REDUCIBLE_WITH binary format (classification proved; production path unchanged) |
| `rcx_step` | Python `for` + `match()` + `substitute()` | Meta-circular staged bootstrap / Stage0 reduction | REDUCIBLE_WITH staged bootstrap (G8 PASS; production reduction in progress, not complete) |
| `rcx_run` | Python `for` loop | CPS fuel threading / structural counter | REDUCIBLE_WITH / PARTIALLY CONFIRMED (fuel data can be structural; host iteration remains) |

These are classification statuses, not production-completion claims. All three rows still require separate productionization evidence before any "reduced in production" claim is honest.

---

## References

- `mu/docs/core/L4ExitChecklist.v0.md` - Gate definitions and current pass/fail status
- `mu/docs/core/Boot0Architecture.v0.md` - Staged bootstrap design
- `mu/docs/core/BootstrapPrimitives.v0.md` - Primitive specification
