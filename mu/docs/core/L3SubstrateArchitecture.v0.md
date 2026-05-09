<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-04-08
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md for current phase/debt. This doc is the detailed L3/L4 reference.
GROUNDING_TESTS: tests/docs/test_l4_current_state_truth.py
-->
# L3 Substrate Portability Architecture

Extracted from STATUS.md (2026-04-08) to reduce STATUS.md from 489→~120 lines. This is the detailed reference for L3 substrate portability and L4 research status.

For current phase and debt numbers, see `STATUS.md`. For L4 execution contract, see `roadmap/L4ExecutionContract.v2.md`.

---

## L3: Substrate Portability (ACHIEVED via JS POC)

L3 is defined as **projections run on minimal, auditable substrate**:

| Component | Role | Python | JS |
|-----------|------|--------|-----|
| **kernel.v1.json** | Kernel state machine (7 projections) | Yes | Yes |
| **match.v2.json** | Pattern matching (8 projections) | Yes | Yes |
| **subst.v2.json** | Substitution (13 projections) | Yes | Yes |
| **recurrence.v1.json** | Closure detection (9 projections) — v1 proof-of-concept | Yes | Yes |
| **recurrence.v2.json** | Hash-accelerated closure detection (9 projections) — production | Yes | Yes |
| **Python Substrate** | ~8,430 LOC, comprehensive test coverage, production-ready | PRIMARY | - |
| **JS Substrate** | ~6,488 LOC core + inline tests (16 JS modules), auditable, portability proof | - | COMPLETE |
| **Bootstrap Primitives** | eval_step, max_steps, stack_guard, projection_loader (mu_equal DEMOTED — Level 1 Content-Addressed Mu) | Same in both | Same in both |

**What L3 proves:**
- The SAME projections (13 JS-loaded seed files) run on Python AND JavaScript
- All semantics are in the projections (data), not the host (code)
- The host provides only mechanical execution (the 4 bootstrap primitives)
- Recurrence closure detection works identically on both substrates

**Canonical L3 truth statement:** RCX achieves L3 Substrate Portability by executing identical structural projections across Python and JavaScript. The evaluation rules are structural data, but execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics.

### L3 Seed Categories

| Category | Seeds | JS Loaded | Notes |
|----------|-------|-----------|-------|
| **Substrate (Core)** | kernel.v1, match.v1, match.v2, subst.v1, subst.v2 | v2 seeds: Yes; v1 seeds: Python-only | match.v1/subst.v1 are self-hosting POC; v2 is production |
| **Closures (Core)** | recurrence.v1, recurrence.v2, exhaustion.v1, fix.v1 | Yes | v1 is POC; v2 is hash-accelerated production; fix.v1 is edge/vertex repair |
| **Bridge** | bootstrap_structural.v1 | Yes | Non-linear pattern support |
| **Utilities** | classify.v1, eval.v1, terminal_classify.v1, evidence_walker.v1 | terminal_classify: Yes; evidence_walker: JS source-lock only; others: Python-only | terminal_classify JS-loaded via seed_loader.js; evidence_walker structural runtime remains Python-only |
| **Programs** | rcx_engine.v1, hemispheres.v1, metabolization.v1, metabolize_cycle.v1, paxos_demo.v1 | rcx_engine + hemispheres + metabolization + metabolize_cycle: Yes | paxos_demo application |

### JS Debt Tracking (AST-level host markers)

- JS DEBT SUMMARY in `constants.js` lists 6 host operations (2 iteration + 2 recursion + 2 builtin)
- Canonical counts in `tools/checks/host_semantics_baseline.json` (12 total: 6 Py decorator + 6 JS decorator)
- Functions marked with `@host_iteration`, `@host_recursion`, `@host_builtin`
- Bootstrap primitives marked with `BOOTSTRAP_PRIMITIVE` (same 4 as Python: eval_step, max_steps, stack_guard, projection_loader; mu_equal DEMOTED)
- `tools/checks/check_js_debt.sh` validates markers are present
- `tools/checks/linters/contraband_js.sh` validates no forbidden patterns

### JS Contraband Patterns (blocked by contraband_js.sh)

- `eval(`, `Function(` — Code injection breaks purity
- `setTimeout`, `setInterval` — Async breaks determinism
- `Math.random`, `Date.now`, `new Date(` — Non-determinism
- `process.env` — Environment leakage
- `child_process`, `exec(`, `spawn(` — Subprocess spawning
- `fs.write*`, `fs.append*`, `fs.unlink`, `fs.rm*` — File mutation (read-only allowed)
- `require.*http`, `fetch(` — Network access breaks determinism
- `webcrypto`, `getRandomValues`, `crypto.subtle` — WebCrypto API

### JS AST Police (blocked by ast_police_js.sh)

- Indirect eval: `window['eval']`, `globalThis.eval`, `(0,eval)`
- String concatenation bypass: `'ev'+'al'`
- Scope manipulation: `with()`, `debugger`
- Prototype pollution: `__proto__`, `Object.setPrototypeOf`
- Reflection bypass: `Reflect.construct`, `Reflect.apply`
- Async: `async function`, `await`, generators
- Hidden state: `Proxy`, `WeakMap`, `WeakSet`, `Symbol.for`, `Symbol.iterator`
- Note: `const SENTINEL = Symbol('name')` is allowed for sentinel values

### JS Theater Check (blocked by check_test_theater_js.sh)

- Vacuous assertions: `assert(true)`, `assert(1)`, `assert(!false)`
- Self-comparison: `x === x`
- Empty test bodies, commented-out assertions, TODO/FIXME test placeholders

### Seed Police (blocked by seed_police.sh)

- Missing required fields: `id`, `pattern`, `body`
- Theater projections: empty patterns, trivial bodies, duplicate IDs
- Host leakage: `lambda`, `def `, `function(`, `=>`, `eval(` in string values
- Security: reserved field misuse in non-kernel projections
- Cross-seed ID collisions (except versioned families like v1/v2)

**JS POC location:** `mu/host/js/` (~6,488 LOC core + inline tests across 16 JS modules; `eval_step.js` is compatibility shim). Includes `--json-api` mode for machine-readable output.

---

## L4 Research: True Self-Hosting (SINK)

L4 asks: **Can bootstrap primitives be eliminated entirely?**

Current truth: full L4 completion remains in SINK, but bounded reduction work is active. P7 Stage0 meta-circular reduction landed. **VM cutover is ACTIVE** (`_STAGE0_VM_CUTOVER = True` in both Python and JS, founder GO 2026-03-15). All kernel-step projections (see test_seed_counts.py) execute via Stage0 VM.

| Primitive | L4 Question | Possible Path |
|-----------|-------------|---------------|
| `eval_step` | Can it be a projection? | Requires meta-level substrate |
| `mu_equal` | ~~Can structural equality be structural?~~ | **DEMOTED** from bootstrap primitive |
| `stack_guard` | Can depth be Mu data? | Count in Mu, not Python |
| `projection_loader` | Can Mu load Mu? | Possibly, with file I/O primitive |

**L4 Execution Contract:** See `roadmap/L4ExecutionContract.v2.md`. Enforced by `tools/checks/enforce_l4_execution_contract.py`.

**Semantic Policy Lock:** See `mu/docs/core/NorthStarSemantics.v0.md`.

**Ontology Promotion Contract:** See `mu/docs/core/OntologyPromotionContract.v0.md`.

### RCX-First Semantic Destination (Truth-Sync)

**What is real now:**
- Wave contract/gate enforcement exists and blocks many process regressions.
- EngineNew cycle is mapped to runtime evidence.
- Canonical workload references: `RCXEngineNew.pdf`, `mu/docs/core/RCXEngine.v0.md`, `mu/docs/core/UniversalEval.v0.md`.

**Core gap:** Compliance strongly enforces process shape but is weaker at enforcing semantic destination (host semantics reduction and workload-level execution truth).

**Ontology Automation Staging Policy:** Stage 1 (collect-only), Stage 2 (gated proposals), Stage 3 (conditional auto-promote). Exceeding approved stage requires founder override.

### L4 Status

G8 PASS (classification gate, caveated, 2026-03-03). All four bootstrap primitives have executable classification evidence (4/4). G8 PASS closes primitive classification evidence, not L4 completion. L4 remains blocked by stop conditions #3 (host for-loop) and #4 (L3-to-L4 gap). See `mu/docs/core/L4ExitChecklist.v0.md` for gate criteria and `mu/docs/core/L4DecisionCard.v0.md` for D001-D010 decision log.

### P7 Meta-Circular Reduction Chain (2026-03-13 → 2026-03-15)

All four P7 sub-waves + S1-A/S1-B complete. P7-a through P7-d + S1-A + S1-B (VM CUTOVER ACTIVE) + S1-C (ALL kernel-step projections via Stage0 VM). W6A: trusted path optimization. Total inventory 312 (181 Py + 131 JS), authority 217 (120 Py + 97 JS), markers 12.

### Boot1 Current Reality

Boot1 is a **host-side loop policy alternative**, not a seed-defined structural loop. Recursive (default) and trampoline (fallback) paths both consume the same `{_run_engine: ...}` envelope. The loop-back *decision* is structural; the loop-back *execution* remains host code. See `mu/docs/core/Boot1LoopContract.v0.md`.

### Cross-Substrate Testing Strategy

Cross-substrate parity tests verify L3 (substrate portability):
- Shared JSON test vectors: `tests/fixtures/parity_vectors.json` (20 parity + 3 security = 23 vectors)
- Python tests: `tests/parity/test_parity_python.py`
- JS tests: `mu/host/js/eval_step.js` (20 parity tests pass)
- Actual cross-substrate comparison: `tests/parity/test_js_parity_automated.py::test_actual_cross_substrate_comparison`
- CI workflow runs both: Python pytest + `node mu/host/js/eval_step.js`

### Terminology

- `sink` (lowercase) = runtime hemisphere bucket (e.g., `r_sink` in projection routing)
- `SINK` (uppercase) = governance task lane in TASKS.md (parked work items)
- `r_a` = runtime accumulator bucket
- `Ra` = resolved-work section in TASKS.md
