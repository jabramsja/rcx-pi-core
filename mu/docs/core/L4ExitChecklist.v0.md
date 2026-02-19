<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-18
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: none

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
-->

# L4 Exit Checklist v0

**Purpose:** Replace vague "irreducible debt" framing with measurable gates for L4 (True Self-Hosting). Each gate has a pass/fail condition, proof command, and explicit stop condition.

**Status:** SINK (research question). These gates define WHAT would need to be true, not a commitment to achieve them.

---

## Current Bootstrap Primitives (4)

| Primitive | Location (Python) | Location (JS) | Role |
|-----------|-------------------|---------------|------|
| `eval_step` | `eval_seed.py:step()` | `eval_step.js:step()` | Apply first matching projection |
| `max_steps` | `step_mu.py:step_kernel_mu()` (see `BOOTSTRAP_PRIMITIVE: max_steps` comment) | `eval_step.js` (maxSteps param) | Bound execution iterations |
| `stack_guard` | `mu_type.py:MAX_MU_DEPTH=300` | `eval_step.js:MAX_MU_DEPTH=300` | Depth limit for `is_mu()` |
| `projection_loader` | `seed_integrity.py:load_verified_seed()` | `eval_step.js:loadSeedFile()` | Load + verify seed JSON |

`mu_equal` was DEMOTED (Level 1 Content-Addressed Mu, 2026-02-10). Not counted.

---

## L4 Gates

### L4-G1: Bootstrap Primitive Inventory

**Objective:** Confirm exactly 4 bootstrap primitives exist, no more.

**Pass condition:** `BOOTSTRAP_PRIMITIVE` marker appears exactly 4 times across Python and JS.

**Fail condition:** Any additional `BOOTSTRAP_PRIMITIVE` marker, or any unlabeled host primitive performing equivalent work.

**Proof command:**
```bash
grep -rn "BOOTSTRAP_PRIMITIVE" rcx_pi/selfhost/ mu/host/js/eval_step.js | grep -v test
```

**Status:** PASS

---

### L4-G2: eval_step Minimality

**Objective:** `eval_step` (eval_seed.py:step()) is a pure first-match-wins projection applicator with no domain branching.

**Pass condition:** `step()` function body contains only: iterate projections, call `match()`, if match call `substitute()`, return result. No `if` on domain keys, no special-case routing.

**Fail condition:** `step()` inspects `_boundary_request`, `_tail_call`, `_run_engine`, or any domain-specific field.

**Proof command:**
```bash
grep -n "def step\|_boundary_request\|_tail_call\|_run_engine" rcx_pi/selfhost/eval_seed.py
```

**Status:** PASS — `step()` is ~30 LOC, pure first-match-wins.

---

### L4-G3: max_steps as Structural Data

**Objective:** `max_steps` is an integer parameter decremented per iteration, expressible as Mu data.

**Pass condition:** `max_steps` is a plain integer, decremented in the engine loop, and does not require host-specific introspection.

**Fail condition:** `max_steps` relies on host-language timer, thread state, or non-structural mechanism.

**Proof command:**
```bash
grep -n "max_steps" rcx_pi/selfhost/step_mu.py | head -10
```

**L4 reduction path:** Replace integer with linked-list length (Mu structural counter). UNPROVEN — requires CPS or explicit fuel threading.

**Status:** PASS (expressible as Mu data, not yet converted)

---

### L4-G4: stack_guard is Depth-Only

**Objective:** `stack_guard` (MAX_MU_DEPTH) is a single integer threshold checked during `is_mu()` validation, with no host-specific stack introspection.

**Pass condition:** Guard checks `depth >= MAX_MU_DEPTH` and nothing else. No `sys.getrecursionlimit()`, no OS stack probing.

**Fail condition:** Guard uses host-specific stack measurement.

**Proof command:**
```bash
grep -n "MAX_MU_DEPTH\|getrecursionlimit" rcx_pi/selfhost/mu_type.py
```

**L4 reduction path:** Express depth as Mu counter threaded through evaluation. UNPROVEN — requires eval_step to accept and decrement a depth parameter.

**Status:** PASS

---

### L4-G5: projection_loader is Content-Addressed

**Objective:** `projection_loader` loads JSON seeds, validates structure, and verifies SHA256 checksums. No I/O beyond seed directory.

**Pass condition:** `load_verified_seed()` validates `id`, `pattern`, `body` fields and checks SHA256 checksum against hardcoded expectation.

**Fail condition:** Loader performs network I/O, dynamic code generation, or skips checksum verification.

**Proof command:**
```bash
grep -n "load_verified_seed\|sha256\|SHA256" rcx_pi/selfhost/seed_integrity.py | head -10
```

**L4 reduction path:** Replace JSON parsing with minimal binary format (Hex0-style Stage 0). UNPROVEN — requires seed format redesign.

**Status:** PASS

---

### L4-G6: Match/Subst Bootstrap Status

**Objective:** `match()` and `substitute()` in eval_seed.py are bootstrap implementations used by `eval_step`. Production algorithms use match.v2/subst.v2 seed projections.

**Pass condition:** eval_seed.py `match()` and `substitute()` are marked `# BOOTSTRAP` and called only from `apply_projection()` within eval_step flow.

**Fail condition:** Production code paths bypass seed-based match/subst and use eval_seed versions directly (outside bootstrap context).

**Proof command:**
```bash
grep -n "def match\|def substitute\|BOOTSTRAP" rcx_pi/selfhost/eval_seed.py | head -10
```

**L4 reduction path:** Make eval_step's own match/substitute structural (meta-circular). BLOCKED — circular dependency: eval_step needs match/subst to apply projections, but structural match/subst ARE projections that need eval_step.

**Status:** PASS (conditional — bootstrap versions remain as irreducible substrate)

---

### L4-G7: eval_step Non-Recursive

**Objective:** `eval_step` (`step()`) does not use recursion. Single-pass through projection list.

**Pass condition:** `step()` is a `for proj in projections` loop with early return on match. No recursive calls.

**Fail condition:** `step()` calls itself or any function that transitively calls `step()`.

**Proof command:**
```bash
grep -n "def step\|step(" rcx_pi/selfhost/eval_seed.py
```

**Status:** PASS

---

### L4-G8: Irreducible Primitive Consensus

**Objective:** Formal determination of which primitives are truly irreducible under current architecture vs. which could be eliminated with architectural changes.

**Pass condition:** Each of the 4 primitives has an explicit classification:
- IRREDUCIBLE: Cannot be eliminated without changing the computational model
- REDUCIBLE_WITH: Can be eliminated if [specific architectural change] is made
- ELIMINATED: Already removed (e.g., mu_equal)

**Fail condition:** Any primitive lacks explicit classification with evidence.

**Current classification:**

| Primitive | Classification | Evidence |
|-----------|---------------|----------|
| `eval_step` | IRREDUCIBLE | Circular dependency: projections need eval_step to run, eval_step needs match/subst which are projections |
| `max_steps` | REDUCIBLE_WITH CPS fuel threading | Integer could become Mu linked-list, but requires CPS transform of engine loop |
| `stack_guard` | REDUCIBLE_WITH depth parameter | Depth counter could be Mu data threaded through eval_step, but changes eval_step signature |
| `projection_loader` | REDUCIBLE_WITH binary format | JSON parsing could be replaced by minimal binary loader, but requires seed format redesign |

**Status:** UNPROVEN — classifications are design analysis, not formal proof. Circular dependency claim for eval_step requires CPS feasibility study.

---

## Stop Conditions (L4 Blocked)

L4 is blocked under current architecture when:

1. **Circular dependency:** eval_step must apply projections using match/subst; structural match/subst ARE projections requiring eval_step. No known resolution without meta-level substrate or staged bootstrap (Boot0 v0.4 §Stage 0).

2. **JSON format dependency:** Seeds are JSON. projection_loader must parse JSON. Binary/minimal format is a prerequisite for Hex0-style bootstrap. No implementation planned.

3. **Host for-loop in effect handler:** `run_engine_pipeline()` iterative loop is host code. Boot1 recursive shadow offers alternative form but does not eliminate host involvement. Making iteration control fully structural requires projections to produce continuation envelopes WITHOUT a host consumer — feasible only with meta-level VM.

4. **L3-to-L4 gap:** L3 proves projections are substrate-portable. L4 requires bootstrap primitives to be eliminated or substrate-independent. The gap cannot be closed by porting alone — it requires reducing or eliminating the primitives themselves.

**UNPROVEN:** Whether the circular dependency is truly irreducible or whether CPS transformation could break it. This is the core L4 research question.

---

## References

- `STATUS.md` L4 section — Current L4 status and primitive table
- `mu/docs/core/Boot0Architecture.v0.md` — Staged bootstrap design (Boot0/Boot1/Boot2)
- `mu/docs/core/BootstrapPrimitives.v0.md` — Primitive specification
- `mu/docs/core/Boot1LoopContract.v0.md` — Boot1 recursive loop design spec
