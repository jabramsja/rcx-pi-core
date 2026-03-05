<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-03-05
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

**Pass condition:** Python canonical substrate (`rcx_pi/selfhost/`) contains exactly 4 `BOOTSTRAP_PRIMITIVE` markers, one per primitive: eval_step, max_steps, stack_guard, projection_loader. No 5th primitive name appears in Python markers.

**Fail condition:** Any Python `BOOTSTRAP_PRIMITIVE` marker naming a 5th primitive, or any unlabeled host primitive performing equivalent work in either substrate.

**Proof command:**
```bash
# Canonical (Python) — must show exactly 4 markers:
grep -rn "BOOTSTRAP_PRIMITIVE" rcx_pi/selfhost/ | grep -v test
# Full scan (Python + JS) — for visibility:
grep -rn "BOOTSTRAP_PRIMITIVE" rcx_pi/selfhost/ mu/host/js/ | grep -v test
```

**Status:** PASS (Python). Python shows exactly 4 markers (eval_step, max_steps, stack_guard, projection_loader). **JS label discrepancy:** `constants.js:39` and `types.js:124` label `muHash()` as BOOTSTRAP_PRIMITIVE, but Python classifies the equivalent (`mu_hash_cached` in `mu_type.py`) as `@host_builtin`. All canonical docs (BootstrapPrimitives.v0.md, Boot0Architecture.v0.md, STATUS.md) define exactly 4 primitives — muHash is a host builtin for hash-accelerated closure detection, not a bootstrap primitive. JS labels should be retagged to `@host_builtin` in a future runtime wave.

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

**Pass condition:** Each of the 4 primitives has an explicit classification with executable evidence (runnable test artifact + evidence command):
- IRREDUCIBLE: Cannot be eliminated without changing the computational model
- REDUCIBLE_WITH: Can be eliminated if [specific architectural change] is made
- ELIMINATED: Already removed (e.g., mu_equal)

**Fail condition:** Any primitive lacks explicit classification, or has classification supported only by architectural reasoning without executable evidence.

**Current classification (adjudicated 2026-03-02, G8 PASS proposed 2026-03-03, founder-confirmed in TASKS.md):**

| Primitive | Classification | Evidence | Executable Proof |
|-----------|---------------|----------|-----------------|
| `eval_step` | REDUCIBLE_WITH staged bootstrap | D001: analytical (pattern enumeration). D002-D003: 52-LOC Stage 0 kernel breaks circular dependency (77 tests). D005: production pilot (90 gate tests, PR #452). | `pytest tests/research/test_d002_micro_matcher.py tests/research/test_d003_staged_bootstrap.py mu/tests/l4_gates/test_stage0_production_pilot_gate.py -q` |
| `max_steps` | REDUCIBLE_WITH CPS fuel threading | D006: fuel as Mu linked-list, iteration remains host. | `pytest tests/research/test_d006_h1_fuel_threading.py -q` |
| `stack_guard` | REDUCIBLE_WITH depth parameter | D009: research-only Python analogs demonstrate depth budget as Mu linked-list; mechanism remains host; production stack_guard unchanged. 145 LOC analogs (is_mu, match, substitute) with boundary + failure-mode parity. Memoization/cycle-detection parity deferred (non-goal for D009). | `pytest tests/research/test_d009_h4_depth_threading.py -q` |
| `projection_loader` | REDUCIBLE_WITH binary format | D010: ~100 LOC custom recursive TLV encoder/decoder handles all 6 Mu types. Round-trip fidelity on 2 canonical seeds. 17 golden byte fixtures (decode-only). Engine-level behavioral parity (step_kernel_mu stall + match paths identical). Research-only; production projection_loader unchanged; I/O, integrity, validation out of scope. | `pytest mu/tests/research/test_d010_h5_projection_loader_binary.py -q` |

**Verdict: G8 PASS (classification gate, caveated).** Proposed adjudication packet (2026-03-03); founder confirmation recorded in TASKS.md tracker wording.

All four bootstrap primitives have executable classification evidence meeting the pass condition (explicit classification + runnable test artifact + evidence command). Evidence base: D001-D010 (see L4DecisionCard.v0.md for per-decision test counts). D008 GO (founder-rendered 2026-03-01) authorized D005 production pilot, completing the eval_step evidence chain.

**Aggregate evidence command:**
```bash
pytest tests/research/test_d002_micro_matcher.py tests/research/test_d003_staged_bootstrap.py mu/tests/l4_gates/test_stage0_production_pilot_gate.py tests/research/test_d006_h1_fuel_threading.py tests/research/test_d007_h3_negative_control.py tests/research/test_d009_h4_depth_threading.py mu/tests/research/test_d010_h5_projection_loader_binary.py -q
```

**Not implied by G8 PASS:**
- No production reduction claim. All four primitives remain in production code unchanged.
- No production elimination claim. REDUCIBLE_WITH means "can be reduced IF [specific change] is made" — no such change has been made.
- No L4-complete claim. L4 remains blocked by stop conditions #3 (host for-loop in effect handler) and #4 (L3-to-L4 gap). G8 PASS closes primitive classification evidence, not L4 completion.

**Research-evidence precedent (locked):** Research analog evidence is sufficient for classification gates (G8). Production claims (primitives actually reduced or eliminated in production) require separate productionization gates with cross-substrate parity, performance profiling, and migration tooling.

**Productionization Gate Lock:**

Any claim that a primitive is "reduced in production" (not merely classified as REDUCIBLE_WITH) requires ALL of the following for that primitive. Failing these blocks any production reduction claim.

| Primitive | Productionization Prerequisites |
|-----------|-------------------------------|
| `eval_step` | D005 pilot already in production (PR #452). Further reduction requires: Stage 0 as default (not pilot-flagged), JS Stage 0 parity, performance profiling under production workloads. |
| `max_steps` | D006 is research-only. Requires: JS fuel threading parity, performance profiling (O(fuel) space vs O(1) integer), production integration with fuel parameter threading. |
| `stack_guard` | D009 is research-only. Requires: memoization parity (production is_mu uses per-call memo), cycle-detection parity (production is_mu uses _seen set with backtracking), cross-substrate (JS) implementation, node-count vs per-level budget semantics reconciliation (D009 research analog threads budget sequentially through siblings as node-count; production is_mu passes _depth+1 independently per sibling as depth-only; productionization requires budget forking at sibling boundaries), performance profiling. |
| `projection_loader` | D010 is research-only. Requires: int-range policy (D010 uses int64 via struct.pack(">q"), not full unbounded Python int), NaN/Inf round-trip policy (D010 explicitly allows NaN/Inf), cross-substrate (JS) TLV decoder, seed migration tooling (JSON-to-binary converter + validation), integrity-chain policy (SHA256 of binary format vs current JSON checksums). |

---

## Stop Conditions (L4 Blocked)

L4 is blocked under current architecture when:

1. ~~**Circular dependency:**~~ **RESOLVED** (D001-D003, D005). Staged bootstrap breaks the cycle: 52-LOC Stage 0 kernel bootstraps match.v2 + subst.v2 without eval_step. Production pilot integrated (PR #452). Evidence: `pytest tests/research/test_d003_staged_bootstrap.py mu/tests/l4_gates/test_stage0_production_pilot_gate.py -q`.

2. ~~**JSON format dependency:**~~ **REDUCIBLE** (D010). Seeds are JSON, but D010 demonstrates that JSON parsing can be replaced with ~100 LOC custom recursive TLV decoder handling all 6 Mu types. Research-only — production seeds remain JSON, no migration planned. Evidence: `pytest mu/tests/research/test_d010_h5_projection_loader_binary.py -q`.

3. **Host for-loop in effect handler:** `run_engine_pipeline()` iterative loop is host code. Boot1 recursive shadow offers alternative form but does not eliminate host involvement. Making iteration control fully structural requires projections to produce continuation envelopes WITHOUT a host consumer — feasible only with meta-level VM.

4. **L3-to-L4 gap:** L3 proves projections are substrate-portable. L4 requires bootstrap primitives to be eliminated or substrate-independent. The gap cannot be closed by porting alone — it requires reducing or eliminating the primitives themselves.

**RESOLVED (circular dependency):** D001-D003 proved the circular dependency is breakable via staged bootstrap. D005 pilot confirmed in production. **RESOLVED (JSON format):** D010 proved JSON parsing replaceable with ~100 LOC TLV decoder. **ALL FOUR PRIMITIVES** now have executable reducibility evidence (D001-D010). **G8 PASS** (classification gate, caveated, 2026-03-03). L4 remains blocked by stop conditions #3/#4.

---

## Anti-Theater Test Guardrail (RT2+RT3, 2026-03-03)

L4 gate evidence depends on JS boundary tests invoking production code paths. RT2 introduced `tools/checks/check_simulated_production_logic.py` to detect inline JS helper simulation in `l4_gates/` test files. RT3 hardened the checker against 5 bypass vectors: arrow function aliases, concatenated/f-string snippets, require-without-call, expanded scan targets with inode dedup, and line-based THEATER_OK proximity. 18 checker tests. Wired into `tools/audits/audit_fast.sh` and `tools/audits/audit_all.sh`. See `mu/docs/core/L4DecisionCard.v0.md` Anti-Theater Testing Precedent for canonical policy.

---

## References

- `STATUS.md` L4 section — Current L4 status and primitive table
- `mu/docs/core/L4MicroAbi.v0.md` — L4 ABI surface (rcx_load/rcx_step/rcx_run) mapped to gates
- `mu/docs/core/L4DecisionCard.v0.md` — L4 decision record template and log
- `mu/docs/core/G8CpsFeasibility.v0.md` — CPS feasibility study for G8 circular dependency
- `mu/docs/core/Boot0Architecture.v0.md` — Staged bootstrap design (Boot0/Boot1/Boot2)
- `mu/docs/core/BootstrapPrimitives.v0.md` — Primitive specification
- `mu/docs/core/Boot1LoopContract.v0.md` — Boot1 recursive loop design spec
