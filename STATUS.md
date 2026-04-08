# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

> **Document Architecture**: See [`roadmap/MANIFEST.md`](roadmap/MANIFEST.md) for reading order and linking rules across STATUS.md, TASKS.md, and roadmap docs.

---

## Current Phase

```
PHASE: 8c
NAME: Structural Selection Parity (L1-L3 COMPLETE)
```

## Projection-Based Architecture Levels

| Level | Description | Status |
|-------|-------------|--------|
| **L1: Algorithmic** | match/subst algorithms EXPRESSED as Mu projections | DONE (Python executes projections) |
| **L2: Operational** | kernel state machine EXPRESSED as Mu projections | FULL (decision: accept for-loop as bootstrap primitive) |
| **L3: Substrate Portability** | Same projections on Python and JavaScript substrates | COMPLETE |
| **L4: True Self-Hosting** | Bootstrap primitives eliminated or substrate-independent | SINK (full completion research; bounded reduction active) |

**Terminology Honesty:**
- "Projection-based" means the ALGORITHM is expressed as Mu projections (data)
- Python's `eval_step()` EXECUTES those projections (like Forth's NEXT executes threaded code)
- This is NOT "self-hosting" in the traditional sense - Python is the execution engine
- The "kernel" in L2 refers to `kernel.v1.json` (7 projections), NOT the deprecated `Kernel` class

## What This Means

- **L1 Algorithmic DONE**: `match_mu()` and `subst_mu()` algorithms are expressed as Mu projections in seeds. Python's `eval_step()` executes them.
- **L2 Operational FULL**: Projection SELECTION is structural (linked-list cursor in kernel.v1). Projection EXECUTION is Python (`for` loop in `step_kernel_mu`) - accepted as bootstrap primitive per Phase 8 decision.
- **Python's role**: `eval_step()` is a bootstrap primitive (like Forth's NEXT). It applies projections using Python pattern matching. This is irreducible in current architecture.

## L2 Completion Criteria (Explicit)

**L2 FULL (current status - PARTIAL + explicit acceptance):**
- [x] Kernel state machine is 7 Mu projections (`kernel.v1.json`)
- [x] Match v2 with context passthrough (8 projections, `_match_ctx`) - used by kernel
- [x] Subst v2 with context passthrough (13 projections, `_subst_ctx`) - used by kernel
- [x] Projection selection uses linked-list cursor (`_remaining` field, no index arithmetic)
- [x] `step_kernel_mu()` wired to use structural kernel
- [x] Security hardening complete (27 reserved fields: 25 KERNEL_RESERVED_FIELDS + 2 ALGORITHM_ENTRYPOINT_KEYS, deep validation)
- [ ] Python for-loop still drives kernel execution (`step_mu.py` `step_kernel_mu`, see `@host_iteration` decorator)

**Seed version note:** `match_mu()` now uses match.v2 + bridge projections directly for non-linear pattern conflict detection (B-structural approach, 2026-02-09). `subst_mu()` standalone function uses subst.v2 + Stage0 VM runner (Wave 3B, 2026-03-16). The kernel (`step_kernel_mu`) uses v2 seeds which add context passthrough (`_match_ctx`, `_subst_ctx`) for kernel integration. `classify_mu()` still uses classify.v1 + host runner (no compiled bundle yet).

**L2 FULL (target - requires decision):**
The gap from PARTIAL to FULL is the Python for-loop in `step_kernel_mu()`. Options:
1. **Accept as bootstrap primitive** (Forth precedent) - Loop is like Forth's NEXT, irreducible
2. **CPS/Trampolining** - Convert loop to continuation-passing, projections chain via Mu data
3. **Structural fuel counter** - `max_steps` becomes Mu data that decrements structurally

**Current decision:** Option 1 (accept as bootstrap primitive). The for-loop is marked with `@host_iteration` and documented as irreducible. L2 FULL = L2 PARTIAL + explicit acceptance.

**L2 EXCLUDED (by design):**
- `eval_step()` is bootstrap primitive (irreducible)
- `run_mu()` outer loop is L3 boundary (repeat-until-stall scaffolding)
- `stage0_vm_run_bounded` iteration (composition pattern, not execution)

## L3/L4 Definition (Bootstrap Architecture)

### L3: Substrate Portability (ACHIEVED via JS POC)

L3 is defined as **projections run on minimal, auditable substrate**:

| Component | Role | Python | JS |
|-----------|------|--------|-----|
| **kernel.v1.json** | Kernel state machine (7 projections) | ✅ | ✅ |
| **match.v2.json** | Pattern matching (8 projections) | ✅ | ✅ |
| **subst.v2.json** | Substitution (13 projections) | ✅ | ✅ |
| **recurrence.v1.json** | Closure detection (9 projections) — v1 proof-of-concept | ✅ | ✅ |
| **recurrence.v2.json** | Hash-accelerated closure detection (9 projections) — production | ✅ | ✅ |
| **Python Substrate** | ~8,430 LOC, ~7,525 tests, production-ready | ✅ PRIMARY | - |
| **JS Substrate** | ~6,488 LOC core + inline tests (16 JS modules), auditable, portability proof | - | ✅ COMPLETE |
| **Bootstrap Primitives** | eval_step, max_steps, stack_guard, projection_loader (mu_equal DEMOTED — Level 1 Content-Addressed Mu) | Same in both | Same in both |

**What L3 proves:**
- The SAME projections (13 JS-loaded seed files) run on Python AND JavaScript
- All semantics are in the projections (data), not the host (code)
- The host provides only mechanical execution (the 4 bootstrap primitives)
- Recurrence closure detection works identically on both substrates

**Canonical L3 truth statement:** RCX achieves L3 Substrate Portability by executing identical structural projections across Python and JavaScript. The evaluation rules are structural data, but execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics. The host language acts as physical clock/memory manager; Mu projections are the physics.

**L3 Parity Requirement (MANDATORY - North Star #13):**
- Any change to Python projection behavior MUST be mirrored in JavaScript
- **Core L3 seeds** (kernel, match, subst, recurrence, exhaustion, bootstrap_structural) MUST be loaded in BOTH substrates
- **Utility seeds** (classify.v1, eval.v1, evidence_walker.v1) are Python-only; terminal_classify.v1 is JS-loaded
- Parity vectors in `tests/fixtures/` are shared by both implementations
- Run `node mu/host/js/eval_step.js` after Python changes to verify JS parity
- Run `./tools/checks/check_js_debt.sh` to verify JS debt markers match Python
- Violation of parity breaks L3 and must be fixed before merge

**L3 Seed Categories:**
| Category | Seeds | JS Loaded | Notes |
|----------|-------|-----------|-------|
| **Substrate (Core)** | kernel.v1, match.v1, match.v2, subst.v1, subst.v2 | v2 seeds: ✅; v1 seeds: Python-only | match.v1/subst.v1 are self-hosting POC; v2 is production |
| **Closures (Core)** | recurrence.v1, recurrence.v2, exhaustion.v1, fix.v1 | ✅ | v1 is POC; v2 is hash-accelerated production; fix.v1 is edge/vertex repair |
| **Bridge** | bootstrap_structural.v1 | ✅ | Non-linear pattern support |
| **Utilities** | classify.v1, eval.v1, terminal_classify.v1, evidence_walker.v1 | terminal_classify: ✅; others: Python-only | terminal_classify JS-loaded via seed_loader.js; evidence_walker Python-only |
| **Programs** | rcx_engine.v1, hemispheres.v1, metabolization.v1, metabolize_cycle.v1, paxos_demo.v1 | rcx_engine + hemispheres + metabolization + metabolize_cycle: ✅ | Engine orchestration + hemisphere routing + metabolization + metabolize cycle L3 parity; paxos_demo application |

**JS Debt Tracking (AST-level host markers — distinct from Python bootstrap debt):**
- JS DEBT SUMMARY in `constants.js` lists 6 host operations (2 iteration + 2 recursion + 2 builtin). Canonical counts in `tools/checks/host_semantics_baseline.json` (12 total: 6 Py decorator + 6 JS decorator). See `mu/docs/core/Why_RCX_PI_VM_EXISTS.md` for why every host operation is tracked debt.
- Functions marked with `@host_iteration`, `@host_recursion`, `@host_builtin`
- These are AST-level host loop markers, analogous to Python's AST_OK:infra (65), NOT bootstrap primitives. There are 4 bootstrap primitives (eval_step, max_steps, stack_guard, projection_loader) and 5 Python host-debt marker sites — these are distinct concepts.
- Bootstrap primitives marked with `BOOTSTRAP_PRIMITIVE` (same 4 as Python: eval_step, max_steps, stack_guard, projection_loader; mu_equal DEMOTED)
- `tools/checks/check_js_debt.sh` validates markers are present
- `tools/checks/linters/contraband_js.sh` validates no forbidden patterns (determinism, purity)
- Both audit scripts (fast/all) run JS debt check and contraband check
- All semantics are in the projections (data), not the host (code)
- The host provides only mechanical execution (the 4 bootstrap primitives)
- This is the Hex0/Forth precedent: meaning in data, mechanics in minimal runner

**JS Contraband Patterns (blocked by contraband_js.sh):**
- `eval(`, `Function(` - Code injection breaks purity
- `setTimeout`, `setInterval` - Async breaks determinism
- `Math.random`, `Date.now`, `new Date(` - Non-determinism
- `process.env` - Environment leakage
- `child_process`, `exec(`, `spawn(` - Subprocess spawning
- `fs.write*`, `fs.append*`, `fs.unlink`, `fs.rm*` - File mutation (read-only allowed)
- `require.*http`, `fetch(` - Network access breaks determinism
- `webcrypto`, `getRandomValues`, `crypto.subtle` - WebCrypto API (non-determinism)

**JS AST Police (blocked by ast_police_js.sh):**
- Indirect eval: `window['eval']`, `globalThis.eval`, `(0,eval)`
- String concatenation bypass: `'ev'+'al'`
- Scope manipulation: `with()`, `debugger`
- Prototype pollution: `__proto__`, `Object.setPrototypeOf`
- Reflection bypass: `Reflect.construct`, `Reflect.apply`
- Async: `async function`, `await`, generators (`function*`, `yield`)
- Hidden state: `Proxy`, `WeakMap`, `WeakSet`, `Symbol.for`, `Symbol.iterator`
- Note: `const SENTINEL = Symbol('name')` is allowed for sentinel values

**JS Theater Check (blocked by check_test_theater_js.sh):**
- Vacuous assertions: `assert(true)`, `assert(1)`, `assert(!false)`
- Self-comparison: `x === x`
- Empty test bodies
- Commented-out assertions
- TODO/FIXME test placeholders

**Seed Police (blocked by seed_police.sh):**
- Missing required fields: `id`, `pattern`, `body`
- Theater projections: empty patterns, trivial bodies, duplicate IDs
- Host leakage: `lambda`, `def `, `function(`, `=>`, `eval(` in string values
- Security: reserved field misuse in non-kernel projections
- Cross-seed ID collisions (except versioned families like v1/v2)

**JS POC location:** `mu/host/js/` (~6,488 LOC core + inline tests across 16 JS modules; `eval_step.js` is compatibility shim)
- Now tracked in git (required for CI)
- Includes `--json-api` mode for machine-readable output (cross-substrate verification)

### L4 Research: True Self-Hosting (SINK)

L4 asks: **Can bootstrap primitives be eliminated entirely?**

Current truth: full L4 completion remains in SINK, but bounded reduction work is active. P7 Stage0 meta-circular reduction landed. **VM cutover is ACTIVE** (`_STAGE0_VM_CUTOVER = True` in both Python and JS, founder GO 2026-03-15). All 33 kernel-step projections execute via Stage0 VM.

| Primitive | L4 Question | Possible Path |
|-----------|-------------|---------------|
| `eval_step` | Can it be a projection? | Requires meta-level substrate |
| `mu_equal` | ~~Can structural equality be structural?~~ | **DEMOTED** from bootstrap primitive (Level 1 Content-Addressed Mu). All production call sites use `mu_hash_cached()` directly. Convenience wrapper retained in mu_type.py for ~30 test call sites + JS parity. |
| `stack_guard` | Can depth be Mu data? | Count in Mu, not Python |
| `projection_loader` | Can Mu load Mu? | Possibly, with file I/O primitive |

**L4 Execution Contract:** See [`roadmap/L4ExecutionContract.v2.md`](roadmap/L4ExecutionContract.v2.md) for 3-class wave classification policy (L4_STRUCTURAL / L4_ENABLER / MAINTENANCE). Enforced by `tools/checks/enforce_l4_execution_contract.py`.

**Semantic Policy Lock:** See [`mu/docs/core/NorthStarSemantics.v0.md`](mu/docs/core/NorthStarSemantics.v0.md) for canonical policies on undefined-as-structure, zero canonicalization, bounded non-closure, and routing tie-break deferral.

**Ontology Promotion Contract:** See [`mu/docs/core/OntologyPromotionContract.v0.md`](mu/docs/core/OntologyPromotionContract.v0.md) for invariants governing ontology promotion (INV_OPROMO_1 through INV_OPROMO_4). Runtime enforcement active since A12 (PR #436, merged 2026-02-26). A13 displaced hardcoded lock-set authority to registry-derived rule. A14 added producer-side candidate emission with opt-in flag, typed fail-closed guards, and overwrite protection (PR #438, merged 2026-02-27). A15/T1 hardened boundary parity (HF2 max_steps clamp, `_has_nonlinear_vars` bounded guard) and completed full L4 gate theater sweep (PR #440, merged 2026-02-27). A16 gated the JS test-dispatch seam behind `RCX_TEST_MODE` with typed override validation (PR #442, merged 2026-02-27). A17 added opt-in boundary evidence collection with strict one-shot semantics and no-overwrite guard (PR #443, merged 2026-02-27). A18-P0 closed P0 JS parity/stall-proof gaps (typed denormalize guard, `isValidMu` entry checks, `mu_equal` stall checks) (PR #445, merged 2026-02-27).

### RCX-First Semantic Destination (Truth-Sync)

**What is real right now:**
- Wave contract/gate enforcement exists (`tools/checks/enforce_l4_execution_contract.py`) and blocks many process regressions.
- EngineNew cycle is mapped to runtime evidence (`mu/tests/structural/test_engine_cycle_mapping.py`), with explicit note that host loop primitive handling remains for step 10.
- Canonical workload/program references exist: `RCXEngineNew.pdf`, `mu/docs/core/RCXEngine.v0.md`, `mu/docs/core/UniversalEval.v0.md`.

**Core gap to close:**
- Current compliance strongly enforces process shape; it is weaker at enforcing semantic destination (host semantics reduction and workload-level execution truth).
- Structural waves can report deltas without proving a monotonic host-semantics reduction trend.
- UniversalEval is design/symbolic and must remain VECTOR-only unless explicitly promoted with runtime evidence.

**Ontology Automation Staging Policy (research safety lock):**
- Stage 1 (active baseline): collect-only evidence/candidate emission; no automatic ontology commit side effects.
- Stage 2 (gated proposals): candidate proposals require typed invariant checks + explicit review gate.
- Stage 3 (conditional auto-promote): allowlist-only classes with rollback/quarantine and measured false-lock threshold.
- Any wave that exceeds the currently approved stage must fail L4 contract unless founder override is explicitly declared.

**L4 Status:** G8 PASS (classification gate, caveated, 2026-03-03). All four bootstrap primitives have executable classification evidence (4/4). `eval_step` REDUCIBLE_WITH staged bootstrap (D001 analytical + D002-D003 + D005 executable). `max_steps` REDUCIBLE_WITH CPS fuel threading (D006). `stack_guard` REDUCIBLE_WITH depth parameter (D009). `projection_loader` REDUCIBLE_WITH binary format (D010). G8 PASS closes primitive classification evidence, not L4 completion. L4 remains blocked by stop conditions #3 (host for-loop) and #4 (L3-to-L4 gap). No production reduction or elimination claims — all primitives remain in production unchanged. Research-evidence precedent locked: research analog evidence is sufficient for classification gates; production claims require separate productionization gates. See `mu/docs/core/L4ExitChecklist.v0.md` for gate criteria, productionization gate lock, and "not implied" section. See `mu/docs/core/L4DecisionCard.v0.md` for D001-D010 decision log and G8-ADJ verdict.

**Post-D008 Operating Mode:** D008 GO rendered (founder, 2026-03-01; supersedes prior DEFER). D005 production pilot COMPLETE (PR #452 merged, 2026-03-01). **G8 PASS (classification gate, caveated, 2026-03-03):** All four primitives classified with executable evidence (D001-D010). G8 PASS closes classification evidence, not L4 completion. L4 remains blocked by stop conditions #3/#4. No production reduction claims. Research-evidence precedent locked: research analogs sufficient for classification gates, production claims require productionization gates. Productionization gate lock documented in L4ExitChecklist.v0.md (D009: memoization/cycle-detection + cross-substrate + node-count vs per-level; D010: int-range + NaN/Inf + JS decoder + migration + integrity-chain). Hemisphere Metabolization Contract COMPLETE (E1-E5 all MET, 2026-02-20). Boot1 shadow-merge COMPLETE (2026-02-19). All prior NEXT contracts closed. Wave 25 JS perf fix merged (PR #453, 42x speedup + non-linear hash fix + policy lock). P4 hotspot measured and DEFERRED (2026-03-02, PR #458). **RT1+RT2+RT3 anti-theater hardening COMPLETE (2026-03-03):** RT1 closes cross-substrate seed parsing parity (NaN/Inf rejection) and JS type guards. RT2 introduces `tools/checks/check_simulated_production_logic.py` (9 tests). RT3 hardens the checker: arrow function aliases, concatenated/f-string detection, require+call proof (not just require), inode-based scan dedup, 5-line THEATER_OK proximity. 18 checker tests total. Wired into `tools/audits/audit_fast.sh` and `tools/audits/audit_all.sh`. This is process hardening, not runtime behavior change — host semantics and debt unchanged.

**P7 Meta-Circular Reduction Chain (2026-03-13 → 2026-03-15):** All four P7 sub-waves + S1-A/S1-B complete. P7-a: Stage0 VM executor seed (9 opcodes, 125 gate tests, Python+JS parity, PR #568). P7-b: Lowering compiler (`lower_stage0.py` + `json_to_dag.py`, 41 gate tests, compiled match_v2 + subst_v2 bundles, PR #577). P7-c: Three-way parity harness (host Stage0 vs compiled Python vs compiled JS, corpus replay, PR #579). P7-d: Shadow-mode cutover (`_step_kernel_with_vm()`, 17 gate tests, PR #581). S1-A: Cutover evidence package (37 tests, performance profiling, CONDITIONAL GO memo, PR #598). **S1-B: VM CUTOVER ACTIVE (PR #603, founder GO 2026-03-15).** `_STAGE0_VM_CUTOVER = True`, `_STAGE0_SHADOW_ENABLED = False` in both Python and JS. **S1-C: ALL 33 projections via Stage0 VM (PR #606).** kernel.v1 (7) + bridge (5) compiled into Stage0 bundles; `_step_kernel_with_vm()` now executes all 4 seed groups via `stage0_vm_step`; `_apply_projection_trusted` eliminated from step_kernel_mu path. Host path (`_step_trusted`) still used by engine_pipeline only (projection_runner retired Wave 3F; classify + subst migrated to VM via Waves 3B-3E). **W6A: trusted path optimization (PR #635 merged, 2026-03-19).** Total inventory 312 (181 Py + 131 JS), authority 217 (120 Py + 97 JS), markers 12. JS substrate: 16 modules, ~6,488 LOC.

**Conjecture Parking:** Non-Euclidean geometry / structural linear algebra hypotheses are PARKED (not active). See TASKS.md SINK "Conjecture Parking (NOT ACTIVE)" for re-evaluation trigger and promotion rules.

**Terminology Lock:** `sink` (lowercase) = runtime hemisphere bucket (e.g., `r_sink` in projection routing). `SINK` (uppercase) = governance task lane in TASKS.md (parked work items). `r_a` = runtime accumulator bucket. `Ra` = resolved-work section in TASKS.md. These are distinct concepts; never conflate them.

**Boot1 Current Reality (truth-sync 2026-03-11):**
Boot1 is a **host-side loop policy alternative**, not a seed-defined structural loop. Two host paths exist:
- **Recursive (default):** `_run_engine_recursive()` recursive call stack (`step_mu.py:_run_engine_recursive()`, `eval_step.js:runEnginePipelineRecursive()`) — `use_boot1_recursive=True` default in `run_engine_pipeline()`
- **Trampoline (fallback):** `run_engine_pipeline()` iterative for-loop (`step_mu.py:run_engine_pipeline()`, `eval_step.js:runEnginePipeline()`)
Both are host code consuming the same `{_run_engine: ...}` envelope. The loop-back *decision* is structural (made by projections); the loop-back *execution* remains host code. Shadow-merge authorized (founder D1=YES 2026-02-16); Boot1 recursive promoted to default. See `mu/docs/core/Boot1LoopContract.v0.md` for design spec. Note: Boot1 is NOT meta-circular progress — it changes the host execution strategy, not the structural execution model (see `Boot1LoopContract.v0.md` "does not promote to META-CIRCULAR").

**Key Insight:** L3 doesn't close L4 - it opens it. By making bootstrap primitives explicit and minimal (~6,488 LOC core in JS across 16 modules), we know exactly what would need to change.

**The Honest Answer:** Forth has NEXT. Lisp has EVAL. Some primitive always exists. The question is: what's the minimal primitive? The JS substrate at ~6,488 LOC core is our current answer - auditable, portable, mechanical.

### Cross-Substrate Testing Strategy

**Status:** GROUNDED (Steps 1-5 complete, 2026-01-31)

Cross-substrate parity tests verify L3 (substrate portability):
- [x] Shared JSON test vectors: `tests/fixtures/parity_vectors.json` (20 parity + 3 security = 23 vectors)
- [x] Python tests: `tests/parity/test_parity_python.py` (20 parity tests + 3 security tests)
- [x] JS tests: `mu/host/js/eval_step.js` (20 parity tests pass)
- [x] Structural trace tests: `tests/engine/test_structural_trace.py` (14 tests)
- [x] **ACTUAL cross-substrate comparison** (9-agent Round 3 fix, 2026-01-31):
  - `tests/parity/test_js_parity_automated.py::test_actual_cross_substrate_comparison`
  - Runs SAME 20 vectors through BOTH Python and JS kernels via JSON API
  - Compares actual outputs (not just string parsing)
  - Handles int/float normalization (JS doesn't distinguish)
- [x] CI workflow runs both: Python pytest + `node mu/host/js/eval_step.js`

**Security gaps in JS POC (adversary finding - FIXED 2026-01-30):**
- [x] `KERNEL_RESERVED_FIELDS` validation (added v4)
- [x] `validate_type_tag()` in denormalize (added v4 fix)
- [x] Dict kv-pair normalization parity fix (v4)
- [ ] Lambda calculus guard (future - not critical for L3)

## Development Workflow

**Before committing, run:**
```bash
./tools/pre-commit-doc-check      # Canonical commit gate (docs, debt, tracker, staged checks)
./tools/checks/check_docs_consistency.sh # Verify STATUS.md matches reality
./tools/debt_dashboard.sh         # Check debt doesn't exceed ceiling
```

**Git hook (auto-runs on commit):**
```bash
# Install once:
ln -sf ../../tools/pre-commit-doc-check .git/hooks/pre-commit
```

The pre-commit hook checks doc consistency, debt ceiling, targeted staged-file checks, and tracker sync. See `CLAUDE.md` for full workflow details.

### Anti-Theater Protocol

**Definition:** Theater-risk tests have no meaningful assertions — import-only checks, vacuous assertions, tautologies. The AST classifier (`check_gate_behavioral_pairs.py`) identifies these; the ratchet (`check_theater_risk_ratchet.py`) prevents regressions.

**Ratchet pass criteria:**
- No new theater_risk methods outside allowlist
- No expired allowlist entries
- No `real`-classified entries in allowlist (must be fixed)

**Allowlist governance:**
- Location: `tools/checks/theater_allowlist.json`
- Every entry requires: `classification`, `defer_reason`, `owner`, `expires_on`, `target_wave`
- `heuristic_false_positive` and `uncertain` may be allowlisted with expiry
- `real` must be fixed, never allowlisted

**How to triage theater_risk:**
1. Read the flagged test method source
2. Classify: **Real** (no production call, no assertion), **Heuristic false-positive** (classifier limitation — test actually validates via implicit exception, subprocess exit code, mock assertion), or **Uncertain**
3. Real → fix now (convert to behavioral test calling production entrypoint)
4. Uncertain → fix now or defer with explicit `defer_reason` + `target_wave`
5. False-positive → allowlist with justification

### Manifest Discoverability Ratchet

Every `mu/docs/core/*.md` with DOC_STATUS TYPE = DESIGN_SPEC or IMPLEMENTATION must appear in `roadmap/MANIFEST.md`. Enforced fail-closed by `tests/docs/test_manifest_discoverability.py`. Adding a new active core spec without a MANIFEST entry will fail the test suite.

## Testing Tiers

```
Tier 1: Fast Audit    ./tools/audit_fast.sh         ~3 min   Core tests only (local iteration)
Tier 2: Full Audit    ./tools/audit_all.sh          ~5-8 min Core + Fuzzer + Slow (before push)
Tier 3: CI Green Gate scripts/green_gate.sh          ~2 min   Core only, no fuzzers/slow (push/PR)
Tier 4: CI Nightly    scripts/green_gate.sh ci_full  ~45 min  Everything (200 examples, scheduled nightly)
Tier 5: CI Weekly     weekly_deep_fuzz.yml          ~60 min  Deep fuzz (500 examples, scheduled weekly)
```

| Tier | What It Tests | When to Run |
|------|---------------|-------------|
| Tier 1 | Core algorithms, syntax, contraband, security tool grounding | Local iteration |
| Tier 2 | All tests including ~498 hypothesis fuzzers + 658 slow tests | Before push (local) |
| Tier 3 | ~4,250 core tests (no fuzzers, no slow, excludes stress + full JS parity) | CI push/PR gate (~2 min) |
| Tier 4 | Everything including fuzzers + slow (ci_full profile) | Nightly CI schedule |

**CI Green Gate Optimization (2026-02-11):**
- Hypothesis fuzzers auto-marked via `pytest_collection_modifyitems` in `conftest.py` (498 tests)
- Slow tests (meta-circular, paxos e2e, hemispheres, engine pipeline) deselected (658 tests)
- Green gate `-m "not slow and not fuzzer" --ignore=tests/stress/ --ignore=tests/parity/test_js_parity_automated.py` runs ~4,250 core tests + 1 parity canary in ~50s on CI (marker-only deselection yields ~4,400; green gate additionally excludes stress and full JS parity suite)
- Total green gate wall time: **~2 min** (down from ~28 min)
- Nightly (`HYPOTHESIS_PROFILE=ci_full`) runs everything including fuzzers and slow

**Tier 1 includes (2026-02-01):**
- `tests/structural/` (45 files) - structural claims grounding
- `tests/tools/` (27 files) - security tool grounding tests (including validator)
- 20 core test files including adversarial and self-hosting tests
- 44 CRITICAL_TEST_FILES protected from silent skipping

**Fuzzer Settings (standardized 2026-01-28):**
- `max_depth=3` in ALL test generators (prevents pathological nesting after normalization)
- `deadline=5000` on ALL fuzzer tests (5 second timeout per example)
- Stress tests use `deadline=10000-30000` for deep edge cases
- Files standardized: test_bootstrap_fuzzer.py, test_selfhost_fuzzer.py, test_type_tags_fuzzer.py, test_apply_mu_fuzzer.py, test_phase8b_fuzzer.py, test_phase7_readiness_fuzzer.py

**For fast local iteration:**
```bash
HYPOTHESIS_PROFILE=dev pytest tests/fuzz/test_bootstrap_fuzzer.py  # ~30 seconds
```

See `mu/docs/audit/CI_POLICY.md` for full context on testing strategy.

## Debt Status

### Three-Ledger Host Debt Truth

RCX tracks host debt at three distinct granularities. Each ledger answers a different question. All three are mechanically enforced by ratchet baselines and a gate test (`tests/docs/test_debt_truth_gate.py`).

| Ledger | Count | What It Measures | Baseline Source |
|--------|-------|------------------|-----------------|
| **Tracked markers** | 12 | Narrow official `@host_*` debt marker sites (6 Py decorator + 6 JS decorator). The semantic debt the project explicitly categorizes (host_builtin, host_iteration, host_recursion). W6A eliminated mutation category. | `tools/checks/host_semantics_baseline.json` |
| **Authority sites** | 217 | Named runtime sites currently flagged by the broader authority inventory ratchet. Functions with host-authority signals (isinstance, loops, builtins, recursion) across the runtime tree. Per-substrate: 120 Python + 97 JavaScript. | `tools/checks/host_authority_inventory_baseline.json` (authority inventory) |
| **Total inventory sites** | 312 | Full named host-runtime surface in scope. Every function in the runtime tree that touches any host-language construct. Per-substrate: 181 Python + 131 JavaScript. | `tools/checks/host_authority_inventory_baseline.json` (total inventory) |

**Why three ledgers:** The 12 tracked markers are the narrow debt the project has categorized and accepted. The 217 authority sites are the broader surface the ratchet prevents from growing. The 312 total inventory sites are the full host-runtime footprint — the upper bound on what "self-hosting" must eventually eliminate or accept as irreducible bootstrap.

**Direction:** Tracked markers monotonically decrease (enforced by `check_host_semantics_ratchet.py`). Authority and total inventory sites are ratcheted against baseline (enforced by `check_host_authority_inventory_ratchet.py`). The gap between 12 and 312 is the honest measure of how much host work remains uncategorized.

```
THRESHOLD: 12
CURRENT: 12 (6 Py decorator + 6 JS decorator — per host_semantics_baseline.json)
FLOOR: 12 (see explanation below)
INFRA_CEILING: 135
INFRA_CURRENT: 135
```

**Tracked marker count (12 — 6 Py decorator + 6 JS decorator):**
- @host_recursion: 4 (2 Py + 2 JS: _stage0_match + _stage0_substitute — BOOTSTRAP)
- @host_builtin: 3 (1 Py + 2 JS: match/builtin surface)
- @host_iteration: 5 (3 Py + 2 JS: step_kernel_mu + list_to_linked + _step_kernel_with_vm — BOOTSTRAP)
- @host_mutation: 0 (eliminated in W6A)
- AST_OK bootstrap: 8 (eval_seed list/dict comprehensions: 2 integer path + 2 budget path from D009 + 2 stage0_vm template materialization from P7-a + 2 stage0_vm _mu_copy from P7-a bot review fix)

**Total host semantics markers (12 = 6 Py decorator + 6 JS decorator):** P7W5 outer loop boundary reclassification: run_mu, run_mu_structural (Py), run, runStructural, runAlgorithmWithBridge, runEnginePipelineRecursive (JS) reclassified as BOUNDARY — all provably off kernel execution path. list_to_linked/listToLinked stay @host_iteration (on kernel path — called by step_kernel_mu/step). Kernel path (post S1-C): step_kernel_mu/step()→_step_kernel_with_vm→stage0_vm_step for ALL 33 projections (kernel.v1 + bridge + match.v2 + subst.v2). Host path (_step_trusted→_apply_projection_trusted) still used by engine_pipeline only (projection_runner retired Wave 3F). W6A eliminated AST_OK bootstrap from tracked markers (refactored as compile-time, not runtime debt). Canonical counts in `tools/checks/host_semantics_baseline.json`. Per-category decorators: Py = 2 recursion + 1 builtin + 3 iteration + 0 mutation; JS = 2 recursion + 2 builtin + 2 iteration.

**Gate 6 note (2026-02-02):**
- run_algorithm_meta_circular: Delegates to eval_step (no new iteration debt)
- load_combined_kernel_v3_projections: Available for future use (no debt)
- No debt increase - Gate 6 uses existing bootstrap layer

**Why 12 is the tracked marker count (lower bound, not comprehensive inventory):**
The 12 counts explicitly marked @host_* sites (6 Py decorator + 6 JS decorator) across L2 kernel, utilities, and Stage0 VM (list_to_linked is inline marker, counted by ratchet but not debt_dashboard). W6A: AST_OK bootstrap reclassified as compile-time (not runtime) debt — excluded from tracked markers. Known untracked host work includes: JS Stage0 builtin surface (stage0Match/stage0Substitute use host isinstance/keys/get internally beyond their @host_recursion markers), lambda-calculus boundary guards (assert_not_lambda_calculus/assertNotLambdaCalculus perform unmarked host recursion/isinstance/set traversal at apply_projection boundary):

*L2 kernel substrate (9 sites):*
1. `_stage0_match()` in eval_seed.py — @host_recursion + @host_builtin (Stage 0 micro-match bootstrap primitive; P7W4: list branch removed, builtin surface reduced to isinstance/.keys()/.get()/in)
2. `_stage0_substitute()` in eval_seed.py — @host_recursion (Stage 0 micro-substitute bootstrap primitive)
3. `step_kernel_mu()` in step_mu.py — @host_iteration (kernel execution loop — Forth's NEXT)
4. `_step_kernel_with_vm()` in step_mu.py — @host_iteration (P7-d/S1-C: kernel step using VM for ALL 4 seed groups — kernel.v1, bridge, match.v2, subst.v2)
5. `list_to_linked()` in step_mu.py — @host_iteration (inline; called by step_kernel_mu to build _projs linked list)
6. AST_OK bootstrap: 4 (eval_seed list/dict comprehensions: 2 integer path + 2 budget path from D009)
- NOTE: `match()` and `substitute()` reclassified as BOUNDARY (P7W4) — off kernel path since Stage 0 is production default (Wave H; pilot flag removed wave4-simplification)
- NOTE: `run_mu()`, `run_mu_structural()` reclassified as BOUNDARY (P7W5) — outer loop scaffolding, off kernel path
- NOTE: `list_to_linked()` stays @host_iteration (P7W5) — on kernel path, called by step_kernel_mu

*Utility debt (3 sites):*
7. `validate_deep_eval_state()` in deep_eval.py — @host_builtin (isinstance, set operations)
8. `run_deep_eval()` in deep_eval.py — @host_builtin + @host_mutation (range iteration, history.append)

These cannot be eliminated because:
- Stage 0 match/substitute are the irreducible bootstrap (break circular kernel → match → kernel dependency)
- step_kernel_mu is Forth's NEXT (irreducible evaluation loop)
- deep_eval provides iterative projection application with state tracking
- Circular dependency: eliminating them would require eval_step to not exist

**CP-S1A (wave 25):** Python `@host_mutation` on `match()` eliminated by converting `_match_inner`'s dict-key mutation (`bindings[k] = v`) to pure dict merge (`{**bindings, **sub_bindings}`). Construct genuinely removed from trusted runtime path. Floor reduced from 12→11. Remaining debt: 2 recursion, 3 builtin, 3 iteration, 1 mutation (deep_eval only), 2 AST_OK bootstrap.

**D009 (wave F):** Structural depth budget primitives added to mu_type.py (make_depth_budget, consume_budget) and eval_seed.py (_match_inner, substitute budget paths). Host semantics +2: @host_iteration (linked-list construction loop), @host_builtin (isinstance for budget validation). Both are infra-level irreducible bootstrap, not primitive debt. +2 AST_OK bootstrap (substitute budget path list/dict comprehensions). Floor increased 11→13. FOUNDER_OVERRIDE:2026-03-11-d009-irreducible-bootstrap for L4 rules 19/20 deadlock.

**D005-H (wave H):** Stage 0 micro-kernel promoted to production (_STAGE0_PILOT flipped True). Host semantics +4: @host_recursion on _stage0_match and _stage0_substitute (Python, 2 markers) + @host_recursion on stage0Match and stage0Substitute (JS, 2 markers). Both are infra-level irreducible bootstrap — Stage 0 breaks the circular dependency (kernel → match → kernel) that would otherwise prevent meta-circular evaluation. Floor increased 13→15. FOUNDER_OVERRIDE:2026-03-11-d005h-stage0-production for L4 rules 19/20 deadlock.

**P7 Wave 1:** Python `@host_mutation` on `_stage0_substitute` eliminated by converting `.append()` loops to generator expressions (`dict(genexpr)` / `list(genexpr)`). Construct genuinely removed. Floor reduced 17→16. Remaining debt: 4 recursion, 4 builtin, 3 iteration, 0 mutation, 4 AST_OK bootstrap.

**P7 Wave 4 (structural reduction + boundary reclassification):** Total host markers 31→17 (-14, -45%). Structural changes: (1) Stage 0 match list branch removed from Python + JS (dead code — all kernel inputs normalized to head/tail, verified zero seed arrays). Eliminates len/zip/set from kernel hot path. (2) set() wrappers on dict.keys() replaced with direct dict_keys view comparison. (3) match()/substitute() reclassified as BOUNDARY (off kernel path since _STAGE0_PILOT=True, Wave H). Boundary reclassification: normalize_for_match, denormalize_from_match, make_depth_budget, classify_linked_list (Py), normalize, denormalize, runEnginePipeline (JS) — all provably off kernel execution path. Floor reduced 16→13.

**P7 Wave 5 (outer loop boundary reclassification):** Total host markers 17→11 (-6, -35%). Reclassified 6 functions as BOUNDARY: run_mu, run_mu_structural (Py 2), run, runStructural, runAlgorithmWithBridge, runEnginePipelineRecursive (JS 4). list_to_linked/listToLinked stay @host_iteration — on kernel path (called by step_kernel_mu/step). Floor reduced 13→11.

**P7-a (Stage0 VM prototype):** +2 AST_OK bootstrap markers in stage0_vm.py (dict comprehension for template object materialization, list comprehension for template list materialization). These are irreducible bootstrap — the VM must construct output values from template fields/items. +1 AST_OK infra marker (program_map dict comprehension for dispatch indexing). Floor increased 11→13, then +2 AST_OK (_mu_copy comprehensions from P7-a bot review fix) raised floor to 15. Infra ceiling 75→76.

The 12 represents the current tracked marker count (6 Py decorator + 6 JS decorator — lower bound on total host work; L2 kernel + utilities). W6A: AST_OK bootstrap reclassified as compile-time (not runtime) debt — excluded from tracked markers. L4 paths are documented:
- **Boot0 Architecture v0.4** (`mu/docs/core/Boot0Architecture.v0.md`) - staged bootstrap design, 9-agent reviewed
- **L4 research questions**: Can mu_equal/eval_step become projections? CPS/trampolining?
- Implementation DEFERRED until L4 research drives it (L3 complete first)

**Reclassified as infrastructure (not debt):**
- match_mu.py:match() - boundary conversion function (AST_OK: infra)
- step_mu.py:ALGORITHM_ENTRYPOINT_KEYS - constant definition (AST_OK: security whitelist)

**Scaffolding ceiling (prevents unbounded accumulation):**
- AST_OK:infra ceiling: 135 (current 135)
- AST_OK:infra is NOT debt, but capped to prevent drift
- Keep line-level infra markers minimal; prefer function-level debt classification for runtime loops

Note: projection_runner retired in Wave 3F. Its @host_iteration was reclassified as BOUNDARY in P7 Wave 3 before retirement.

**Note on boundary scaffolding:**
The `while` loops in `match_mu.py` (normalize_for_match, denormalize_from_match, bindings_to_dict, etc.) are NOT counted as debt. These are Python API conversion functions that convert between Python types and Mu linked lists at the boundary. They are explicitly documented as "boundary scaffolding" in their docstrings. Boundary scaffolding is expected to remain indefinitely as part of the Python API layer - it's not a target for structural replacement.

**Phase 8b outcome (2026-01-28):**
- Simplified step_kernel_mu to MECHANICAL operation (no semantic branching)
- Added `is_kernel_terminal()` - simple structural marker detection
- Added `extract_kernel_result()` - mechanical unpacking
- Loop body: ~35 lines → ~15 lines
- eval_step reclassified as BOOTSTRAP_PRIMITIVE (not debt)
- **Security hardening (9-agent reviewed):**
  - Deep validation: recursive check prevents nested smuggling
  - KERNEL_RESERVED_FIELDS: 25 fields (12 base + 2 Engine/Boot1 + 3 Recurrence + 3 Exhaustion + 4 Bridge + 1 Boundary) + 2 ALGORITHM_ENTRYPOINT_KEYS = 27 total
  - Depth guard fails CLOSED (raises ValueError at depth > 100)
- Net debt: 12 (6 Py decorator + 6 JS decorator — per host_semantics_baseline.json)

**Phase 7d-2/7d-3 CLOSED (per Phase 8 decision):**
- Phase 8 decided: "Option 1 (accept as bootstrap primitive)"
- The for-loop in step_kernel_mu is accepted as irreducible (like Forth's NEXT)
- L2 FULL = L2 PARTIAL + explicit acceptance - this is ACHIEVED
- 7d-2/7d-3 are no longer needed; they assumed we'd eliminate the loop
- If L4 pursues CPS/trampolining, new tasks will be created

Note: run_mu outer loop is scaffolding (L3 boundary), not removed in Phase 7.

## Agent Enforcement Guide

Use this to determine what standards apply NOW vs LATER:

| Condition | Status | Agent Action |
|-----------|--------|--------------|
| Match/subst must be Mu projections | L1 DONE | REQUIRED - enforce now |
| Kernel loop must be Mu projections | L2 FULL | `step_mu` uses structural kernel; for-loop accepted as bootstrap |
| Python iteration in `step_mu` | FIXED (7d-1) | No longer debt - uses structural kernel |
| Python iteration in `run_mu` | L3 boundary | ACCEPTABLE - outer loop scaffolding |
| Python recursion in algorithms | Semantic debt | FAIL - must use projections |
| Unmarked host operations | Debt violation | FAIL - must mark with `@host_*` |

## Key Files

- Design doc: `mu/docs/core/MetaCircularKernel.v0.md`
- Self-hosting: `mu/host/python/rcx_pi/selfhost/` (match_mu, subst_mu, step_mu) — `rcx_pi/` is backward-compat symlink
- **mu/ folder (5-directory seed layout + host):**
  - Substrate: `mu/substrate/` (kernel.v1, match.v1, match.v2, subst.v1, subst.v2)
  - Closures: `mu/closures/` (recurrence.v1, recurrence.v2, exhaustion.v1, fix.v1)
  - Bridge: `mu/bridge/` (bootstrap_structural.v1)
  - Programs: `mu/programs/` (rcx_engine.v1, hemispheres.v1, metabolization.v1, metabolize_cycle.v1, paxos_demo.v1)
  - Utilities: `mu/utilities/` (classify.v1, eval.v1, terminal_classify.v1, evidence_walker.v1)
  - Host: `mu/host/js/` (15 modules, ~4800 LOC core), `mu/host/python/rcx_pi/selfhost/`
- Task list: `TASKS.md`
- **Agent bridge:** `mu/docs/agents/AgentBridgeProtocol.v0.md` (Claude ↔ Codex collaboration, hybrid review, design deliberation)
- **Documentation governance:** `mu/docs/core/DocGovernance.v0.md` (Three Laws, tiered governance)
- **Doc tests:** `tests/docs/` (296 tests: contracts, freshness, governance, root files)
- Grounding tests: `tests/structural/` (status, seeds, type tags, projection order, audit claims)

---

## Historical Archive

Phase 7 blockers, Phase 8a/8b implementation details, L3 progress steps, Jan–Mar 2026 agent reviews, bug fixes, and test creation records have been archived to [`archive/status_history_jan_mar_2026.md`](archive/status_history_jan_mar_2026.md).


---

**Gate Snapshot (Canonical):**
- Gate 3: COMPLETE (2026-02-07)
- Gate 4: COMPLETE (2026-02-07 structural cutover)
- Gate 5: COMPLETE (2026-02-09 meta-circular parity verified)

Current Recurrence Layer: META_CIRCULAR
Current Exhaustion Layer: META_CIRCULAR

**Current Algorithm Execution:**
- `run_algorithm_meta_circular()` defaults to `step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")`
- Algorithm runtime is bridge-backed meta-circular: the kernel loop runs structurally via `step_kernel_mu`, but non-linear matching delegates to host code via bridge projections

**Last updated:** 2026-04-07 (STATUS.md consolidation — archived ~400 lines of Jan–Mar history)
**Next milestone:** Hemisphere Metabolization Contract remains the closed milestone baseline (E1-E5 all MET). Canonical authorization remains TASKS.md. Active NEXT items: META-BRIDGE-BOUNDED-REVIEW-FIX, PIPELINE-RECOVERY (learning store remaining), DEFERRED-CONSOLIDATION, NEXT-CODEX-POST-REDTEAM, PARALLEL-PIPELINE.
