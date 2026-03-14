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
| **L4: True Self-Hosting** | Bootstrap primitives eliminated or substrate-independent | SINK (research question) |

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

**Seed version note:** `match_mu()` now uses match.v2 + bridge projections directly for non-linear pattern conflict detection (B-structural approach, 2026-02-09). `subst_mu()` standalone function uses v1 seeds. The kernel (`step_kernel_mu`) uses v2 seeds which add context passthrough (`_match_ctx`, `_subst_ctx`) for kernel integration.

**L2 FULL (target - requires decision):**
The gap from PARTIAL to FULL is the Python for-loop in `step_kernel_mu()`. Options:
1. **Accept as bootstrap primitive** (Forth precedent) - Loop is like Forth's NEXT, irreducible
2. **CPS/Trampolining** - Convert loop to continuation-passing, projections chain via Mu data
3. **Structural fuel counter** - `max_steps` becomes Mu data that decrements structurally

**Current decision:** Option 1 (accept as bootstrap primitive). The for-loop is marked with `@host_iteration` and documented as irreducible. L2 FULL = L2 PARTIAL + explicit acceptance.

**L2 EXCLUDED (by design):**
- `eval_step()` is bootstrap primitive (irreducible)
- `run_mu()` outer loop is L3 boundary (repeat-until-stall scaffolding)
- `projection_runner.py` iteration (composition pattern, not execution)

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
| **Python Substrate** | ~6,274 LOC, ~5,556 tests, production-ready | ✅ PRIMARY | - |
| **JS Substrate** | ~4800 LOC core + ~480 LOC inline tests (15 JS modules), auditable, portability proof | - | ✅ COMPLETE |
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
- JS DEBT SUMMARY in `constants.js` lists 6 host operations (2 iteration + 2 recursion + 2 builtin). Canonical counts in `tools/checks/host_semantics_baseline.json` (16 total: 6 Py decorator + 6 JS decorator + 4 AST_OK bootstrap). See `mu/docs/core/Why_RCX_PI_VM_EXISTS.md` for why every host operation is tracked debt.
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

**JS POC location:** `mu/host/js/` (~4800 LOC core + ~480 LOC inline tests across 15 JS modules; `eval_step.js` is compatibility shim)
- Now tracked in git (required for CI)
- Includes `--json-api` mode for machine-readable output (cross-substrate verification)

### L4 Research: True Self-Hosting (SINK)

L4 asks: **Can bootstrap primitives be eliminated entirely?**

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

**P7 Meta-Circular Reduction Chain (2026-03-13 → 2026-03-14):** All four P7 sub-waves complete. P7-a: Stage0 VM executor seed (9 opcodes, 125 gate tests, Python+JS parity, PR #568). P7-b: Lowering compiler (`lower_stage0.py` + `json_to_dag.py`, 41 gate tests, compiled match_v2 + subst_v2 bundles, PR #577). P7-c: Three-way parity harness (host Stage0 vs compiled Python vs compiled JS, corpus replay, PR #579). P7-d: Shadow-mode cutover (`_step_kernel_with_vm()`, `_STAGE0_SHADOW_ENABLED = True`, `_STAGE0_VM_CUTOVER = False`, 17 gate tests, PR #581). Shadow verification active — cutover flag awaits performance evidence + founder GO. +1 tracked marker (`@host_iteration: _step_kernel_with_vm`), debt now 16/16.

**Conjecture Parking:** Non-Euclidean geometry / structural linear algebra hypotheses are PARKED (not active). See TASKS.md SINK "Conjecture Parking (NOT ACTIVE)" for re-evaluation trigger and promotion rules.

**Terminology Lock:** `sink` (lowercase) = runtime hemisphere bucket (e.g., `r_sink` in projection routing). `SINK` (uppercase) = governance task lane in TASKS.md (parked work items). `r_a` = runtime accumulator bucket. `Ra` = resolved-work section in TASKS.md. These are distinct concepts; never conflate them.

**Boot1 Current Reality (truth-sync 2026-03-11):**
Boot1 is a **host-side loop policy alternative**, not a seed-defined structural loop. Two host paths exist:
- **Recursive (default):** `_run_engine_recursive()` recursive call stack (`step_mu.py:_run_engine_recursive()`, `eval_step.js:runEnginePipelineRecursive()`) — `use_boot1_recursive=True` default in `run_engine_pipeline()`
- **Trampoline (fallback):** `run_engine_pipeline()` iterative for-loop (`step_mu.py:run_engine_pipeline()`, `eval_step.js:runEnginePipeline()`)
Both are host code consuming the same `{_run_engine: ...}` envelope. The loop-back *decision* is structural (made by projections); the loop-back *execution* remains host code. Shadow-merge authorized (founder D1=YES 2026-02-16); Boot1 recursive promoted to default. See `mu/docs/core/Boot1LoopContract.v0.md` for design spec. Note: Boot1 is NOT meta-circular progress — it changes the host execution strategy, not the structural execution model (see `Boot1LoopContract.v0.md` "does not promote to META-CIRCULAR").

**Key Insight:** L3 doesn't close L4 - it opens it. By making bootstrap primitives explicit and minimal (~4800 LOC core in JS across 15 modules), we know exactly what would need to change.

**The Honest Answer:** Forth has NEXT. Lisp has EVAL. Some primitive always exists. The question is: what's the minimal primitive? The JS substrate at ~4800 LOC core is our current answer - auditable, portable, mechanical.

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
| **Tracked markers** | 16 | Narrow official `@host_*` debt marker sites (6 Py decorator + 6 JS decorator + 4 AST_OK bootstrap). The semantic debt the project explicitly categorizes (host_builtin, host_iteration, host_mutation, host_recursion, AST_OK bootstrap). | `tools/checks/host_semantics_baseline.json` |
| **Authority sites** | 218 | Named runtime sites currently flagged by the broader authority inventory ratchet. Functions with host-authority signals (isinstance, loops, builtins, recursion) across the runtime tree. Per-substrate: 120 Python + 98 JavaScript. | `tools/checks/host_authority_inventory_baseline.json` (authority inventory) |
| **Total inventory sites** | 305 | Full named host-runtime surface in scope. Every function in the runtime tree that touches any host-language construct. Per-substrate: 177 Python + 128 JavaScript. | `tools/checks/host_authority_inventory_baseline.json` (total inventory) |

**Why three ledgers:** The 16 tracked markers are the narrow debt the project has categorized and accepted. The 218 authority sites are the broader surface the ratchet prevents from growing. The 305 total inventory sites are the full host-runtime footprint — the upper bound on what "self-hosting" must eventually eliminate or accept as irreducible bootstrap.

**Direction:** Tracked markers monotonically decrease (enforced by `check_host_semantics_ratchet.py`). Authority and total inventory sites are ratcheted against baseline (enforced by `check_host_authority_inventory_ratchet.py`). The gap between 16 and 305 is the honest measure of how much host work remains uncategorized.

```
THRESHOLD: 16
CURRENT: 16 (6 Py decorator + 6 JS decorator + 4 AST_OK bootstrap — per host_semantics_baseline.json)
FLOOR: 16 (see explanation below)
INFRA_CEILING: 78
INFRA_CURRENT: 78
```

**Tracked marker count (16 — 6 Py decorator + 6 JS decorator + 4 AST_OK bootstrap — see enumeration below for all 8 AST_OK bootstrap):**
- @host_recursion: 2 (_stage0_match + _stage0_substitute — BOOTSTRAP. match/substitute reclassified as BOUNDARY P7W4)
- @host_builtin: 3 (_stage0_match x1, deep_eval x2 — match() reclassified P7W4, builtin surface reduced: len/zip/set eliminated)
- @host_iteration: 3 (step_kernel_mu + list_to_linked + _step_kernel_with_vm — BOOTSTRAP. _step_kernel_with_vm added P7-d: VM dispatch for match.v2/subst.v2)
- @host_mutation: 1 (deep_eval history.append only)
- AST_OK bootstrap: 8 (eval_seed list/dict comprehensions: 2 integer path + 2 budget path from D009 + 2 stage0_vm template materialization from P7-a + 2 stage0_vm _mu_copy from P7-a bot review fix)

**Total host semantics markers (16 = 6 Py decorator + 6 JS decorator + 4 AST_OK bootstrap):** P7W5 outer loop boundary reclassification: run_mu, run_mu_structural (Py), run, runStructural, runAlgorithmWithBridge, runEnginePipelineRecursive (JS) reclassified as BOUNDARY — all provably off kernel execution path. list_to_linked/listToLinked stay @host_iteration (on kernel path — called by step_kernel_mu/step). Kernel path: step_kernel_mu/step()→_step_trusted→_apply_projection_trusted→_stage0_match/_stage0_substitute. P7-d adds _step_kernel_with_vm @host_iteration on Py (kernel-step VM dispatch for match.v2/subst.v2). P7-a Stage0 VM adds 4 AST_OK bootstrap (2 template materialization + 2 _mu_copy comprehensions in stage0_vm.py). Net from P7W5: -6 markers (17→11, -35%); P7-a: +4 AST_OK bootstrap (11→15); P7-d: +1 host_iteration (15→16). Canonical counts in `tools/checks/host_semantics_baseline.json`. Per-category decorators: Py = 2 recursion + 1 builtin + 3 iteration + 0 mutation; JS = 2 recursion + 2 builtin + 2 iteration.

**Gate 6 note (2026-02-02):**
- run_algorithm_meta_circular: Delegates to eval_step (no new iteration debt)
- load_combined_kernel_v3_projections: Available for future use (no debt)
- No debt increase - Gate 6 uses existing bootstrap layer

**Why 16 is the tracked marker count (lower bound, not comprehensive inventory):**
The 16 counts explicitly marked @host_* sites (6 Py decorator + 6 JS decorator + 4 AST_OK bootstrap) across L2 kernel, utilities, and Stage0 VM (list_to_linked is inline marker, counted by ratchet but not debt_dashboard). Known untracked host work includes: JS Stage0 builtin surface (stage0Match/stage0Substitute use host isinstance/keys/get internally beyond their @host_recursion markers), lambda-calculus boundary guards (assert_not_lambda_calculus/assertNotLambdaCalculus perform unmarked host recursion/isinstance/set traversal at apply_projection boundary):

*L2 kernel substrate (9 sites):*
1. `_stage0_match()` in eval_seed.py — @host_recursion + @host_builtin (Stage 0 micro-match bootstrap primitive; P7W4: list branch removed, builtin surface reduced to isinstance/.keys()/.get()/in)
2. `_stage0_substitute()` in eval_seed.py — @host_recursion (Stage 0 micro-substitute bootstrap primitive)
3. `step_kernel_mu()` in step_mu.py — @host_iteration (kernel execution loop — Forth's NEXT)
4. `_step_kernel_with_vm()` in step_mu.py — @host_iteration (P7-d: kernel step using VM for match.v2/subst.v2, host for kernel.v1/bridge)
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

The 16 represents the current tracked marker count (6 Py decorator + 6 JS decorator + 4 AST_OK bootstrap — lower bound on total host work; 4 additional AST_OK bootstrap in eval_seed pre-date threshold tracking; L2 kernel + utilities + Stage0 VM). P7-d adds _step_kernel_with_vm @host_iteration on Py (VM dispatch for match.v2/subst.v2 in step_kernel_mu). L4 paths are documented:
- **Boot0 Architecture v0.4** (`mu/docs/core/Boot0Architecture.v0.md`) - staged bootstrap design, 9-agent reviewed
- **L4 research questions**: Can mu_equal/eval_step become projections? CPS/trampolining?
- Implementation DEFERRED until L4 research drives it (L3 complete first)

**Reclassified as infrastructure (not debt):**
- match_mu.py:match() - boundary conversion function (AST_OK: infra)
- step_mu.py:ALGORITHM_ENTRYPOINT_KEYS - constant definition (AST_OK: security whitelist)

**Scaffolding ceiling (prevents unbounded accumulation):**
- AST_OK:infra ceiling: 78 (current 78)
- AST_OK:infra is NOT debt, but capped to prevent drift
- Keep line-level infra markers minimal; prefer function-level debt classification for runtime loops

Note: projection_runner had @host_iteration comment reclassified as BOUNDARY in P7 Wave 3 (off kernel path, via match_mu/subst_mu → apply_mu only).

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
- Net debt: 12 (10 tracked decorators + 2 AST_OK bootstrap)

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

## Phase 7 Blockers (Agent Findings - 2026-01-27)

These were resolved before promoting Phase 7 from VECTOR to NEXT (promoted 2026-01-27):

**Fuzzer agent (Phase 7 readiness VERIFIED):**
- [x] Create `tests/fuzz/test_phase7_readiness_fuzzer.py` (32 tests, ~700 lines):
  - [x] Seed projection coverage (no unintended stalls)
  - [x] Kernel trace integrity (traces are replay-complete)
  - [x] Kernel state injection resistance (domain data can't forge `_mode`/`_phase`)
- [x] Non-linear pattern fuzzer tests (documents current first-occurrence-wins behavior)

**Grounding agent (13 claims UNGROUNDED):**
- [x] Seed projection count tests (match=7, subst=12, classify=6, eval=7)
- [x] Seed schema validation tests (id, pattern, body required)
- [x] Type tag security tests (whitelist enforcement)

**Adversary agent (SECURE, recommendations):**
- [x] Add projection order regression test (first-match-wins is security-critical)
- [x] Seed checksum update tool - CLOSED (existing test workflow sufficient, see adversary report 2026-01-27)
- [x] Document classify_mu.py string key assumption as known limitation (see DebtCategories.v0.md)

**Expert agent (SIMPLIFIED):**
- [x] Consolidate projection loader pattern → `projection_loader.py` (factory)
- [x] Consolidate runner pattern → `projection_runner.py` (factory)
- [x] Move test-only helpers out of match_mu.py - CLOSED (expert review found NO test-only code, all is production)

**Structural-proof agent:**
- [x] L1 claims PROVEN (match_mu, subst_mu, classify use projections)
- [x] L2 design verified structurally sound (linked-list cursor, context passthrough, meta-circularity confirmed 2026-01-27)

**Additional tests (2026-01-28):**
- [x] `tests/structural/test_projection_loader.py` - Factory loader tests (13 tests)
- [x] `tests/structural/test_projection_runner.py` - Factory runner tests (33 tests)
- [x] `tests/fuzz/test_kernel_loop_fuzzer.py` - L2 kernel iteration fuzz tests (16 tests)
- [x] `tests/fuzz/test_context_passthrough_fuzzer.py` - Context preservation fuzz tests (12 tests)
- [x] `tests/structural/test_step_mu_kernel_integration.py` - Kernel integration tests (30 tests)

**Security fix (2026-01-28 - Adversary review):**
- [x] Implemented `KERNEL_RESERVED_FIELDS` boundary validation in `step_mu.py`
- [x] `validate_no_kernel_reserved_fields()` rejects domain inputs with kernel fields
- [x] Fields protected: `_mode`, `_phase`, `_input`, `_remaining`, `_match_ctx`, `_subst_ctx`, `_kernel_ctx`, `_status`, `_result`, `_stall`, `_step`, `_projs`
- [x] Deep validation: recursive check prevents nested smuggling attacks (e.g., `{"outer": {"_mode": "done"}}`)
- [x] Fail closed: Depth limit (100) raises ValueError, doesn't silently trust remaining structure

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
- **Doc tests:** `tests/docs/` (279 tests: contracts, freshness, governance, root files)
- Grounding tests: `tests/structural/` (status, seeds, type tags, projection order, audit claims)

---

## Recommended Next Action

**Historical milestone:** Phase 8b COMPLETE (2026-01-28). 9-agent review SHIP verdict. 2,846 tests passing.

**L3 Substrate Portability Progress (2026-01-30):**
- Step 1 DONE: JS POC security hardened (v4) - KERNEL_RESERVED_FIELDS validation, dict kv-pair fix
- Step 2 DONE: Cross-substrate parity tests - 20 vectors pass on both Python and JS
- Step 3 DONE: Phase 8d trace model in Python - run_mu_structural() + 14 tests
- Step 4 DONE: Port trace to JS POC - runStructural() + 5 tests
- Step 5 DONE: Recurrence structural closure detection (mu/closures/recurrence.v1.json, 9 projections)

**Step 5 Recurrence Implementation (2026-01-30):**
- Created `mu/closures/recurrence.v1.json` with 9 projections for structural closure detection
- Implements Rule 2.2 (Closure-on-Second-Demand) via pattern matching on traces
- Closure detection uses non-linear patterns (same var twice) for state equality
- Non-linear pattern enforcement provided by eval_seed.match() binding conflict detection
- 24 parity tests in `tests/parity/test_recurrence_parity.py`
- 22 parity vectors in `tests/fixtures/recurrence_vectors.json`
- Property-based fuzzer tests in `tests/fuzz/test_recurrence_fuzzer.py`
- 7-agent review: All agents APPROVE (adversary concern RESOLVED)

**Test files (must be tracked in git):**
- `tests/parity/test_parity_python.py` - 20 parity + 3 security tests
- `tests/engine/test_structural_trace.py` - 14 structural trace tests
- `tests/fuzz/test_structural_trace_fuzzer.py` - 23 property-based fuzzer tests (7-agent critical gap closed)
- `tests/fixtures/parity_vectors.json` - 23 shared test vectors

**Critical Bug Fix (2026-01-30 - Adversarial Review):**
- Fixed Python/JS dict kv-pair normalization parity bug
- Python: `{"head": key, "tail": {"head": value, "tail": null}}`
- JS was wrong: `{"head": key, "tail": value}` (now fixed to match Python)
- Added type tag validation to JS denormalize() for security parity

**7-Agent Review Implementation (2026-01-30):**
Addressed findings from comprehensive 7-agent adversarial peer review:
- **Expert finding (consolidated):** Removed duplicate `run_until_done()` - now shared via `conftest.py`
- **Grounding finding (closed):** Added `TestDictKvPairFormat` - exact kv-pair structure regression tests
- **Fuzzer finding (closed):** Added `TestMalformedLinkedListEdgeCases` - edge case handling tests
- **Adversary finding (closed):** Added defensive cache copy to projection_loader.py and step_mu.py
- **Tests added:** 13 new tests in `tests/engine/test_normalization_roundtrip.py`, 1 new cache mutation test
- **Test updates:** `test_phase7c_integration.py` and `test_parity_python.py` now use shared `run_until_done()`
- **Test updates:** `test_projection_loader.py` and `test_classify_mu.py` updated for defensive copy behavior

**Second 7-Agent Review Verdicts (2026-01-30):**
| Agent | Verdict | Summary |
|-------|---------|---------|
| Verifier | CONDITIONAL_APPROVE | All 12 invariants maintained |
| Adversary | SECURE | 11/11 attacks blocked |
| Expert | COULD_SIMPLIFY | 2 trivial import issues |
| Structural-proof | CLAIMS_HONEST | L2 PARTIAL proven, gaps documented |
| Grounding | GROUNDED | All claims have tests |
| Fuzzer | GAPS_EXIST | 4 boundary gaps identified |
| Advisor | ON_TRACK | Step 5 needs concrete criteria |

**Fuzzer Gap Resolution (2026-01-30):**
- Gap 1 (CRITICAL) CLOSED: `tests/fuzz/test_structural_trace_fuzzer.py` (23 property-based tests)
- Tests run_mu_structural() for: termination, structure validity, trace format, stall detection, determinism, oscillation detection
- Added to CRITICAL_TEST_FILES (cannot be silently skipped)

**CRITICAL: Recurrence Must Be Structural (2026-01-30):**
Step 5 (Recurrence Demo) requires that Recurrence rules are expressed as Mu projections,
NOT Python code. Closure detection must be pattern matching on traces, not Python loops.
This is essential for structural honesty - emergence must be attributable to RCX dynamics,
not "Python did it". See TASKS.md Step 5 for concrete success criteria.

**Security Hardening (2026-01-29, 7-agent review):**
- Added `filterwarnings = ["error::DeprecationWarning:rcx_pi.*"]` to pyproject.toml
- New code using deprecated Kernel will FAIL tests (not just warn)
- Removed `TestKernelIntegration` (4 tests) - used deprecated Kernel
- Created `tests/structural/test_step_budget.py` (18 tests) for ACTIVE infrastructure
- Created `tests/structural/test_audit_claims_grounding.py` (18 tests) for audit verification
- Added `archive/tests/README.md` documenting archive purpose (moved from tests/archive/ in wave15)

**CI/Audit Infrastructure Hardening (2026-01-30, 9-agent review):**
- Created `tests/tools/` directory with grounding tests for security tools (65+ tests):
  - `test_contraband_detection.py` (65 tests) - verifies contraband.sh patterns work
  - `test_contraband_js_detection.py` (34 tests) - verifies contraband_js.sh patterns
  - `test_ast_police_detection.py` (23 tests) - verifies ast_police.py detection
  - `test_ast_police_js_detection.py` (32 tests) - verifies AST patterns in JS
  - `test_check_test_theater_detection.py` (7 tests) - verifies theater check
  - `test_check_test_theater_js_detection.py` (16 tests) - verifies JS theater check
  - `test_seed_police_detection.py` (16 tests) - verifies seed_police.sh
- Added `import builtins` detection to contraband.sh (closes eval/exec bypass)
- Added `base64/codecs` detection to contraband.sh (encoding bypass defense-in-depth)
- Added AST_OK category validation (8 approved categories prevent bypass abuse)
- Added CRITICAL_TEST_FILES protection (43 files cannot be silently skipped):
  - Debt/security enforcement, core parity tests, tool grounding tests
  - Adversarial tests, self-hosting tests, grounding verification
- Updated audit_fast.sh to include security-critical tests in Tier 1
- Single source of truth: THRESHOLD and INFRA_CEILING read from STATUS.md

**Agent Guardrails (Anti-Hallucination, 2026-02-01):**
- Created `mu/docs/agents/AgentGuardrails.v0.md` - requires FILE:LINE + code evidence
- Created `tools/runners/validate_agent_compliance.py` - validates agent output format
- Created `tests/tools/test_validate_agent_compliance.py` (43 tests)
- Created `.claude/hooks/validate-agent-compliance.sh` - automatic SubagentStop hook
- Updated all 9 agent prompts with MANDATORY verification protocol
- Agent models: Opus (verifier, adversary, expert, advisor), Sonnet (others) - no Haiku

**Known Security Limitations (9-agent consensus, 2026-01-30):**
These were reviewed by all 9 agents and deemed NOT_RELEVANT or DEFENSE_IN_DEPTH:
1. **Unicode homoglyphs** (Cyrillic/Greek lookalikes): NOT_RELEVANT - Attack defeats itself.
   Homoglyphs in patterns won't match ASCII in real seeds; attacker would need to
   modify BOTH pattern AND target, which gains nothing. Seeds are audited.
2. **Test theater gaps** (vacuous assertions): FIX_LATER - Quality issue, not security.
   Current tests verify real behavior; theater detection is for new code.
3. **JS inline comment exclusion**: ALREADY_DONE - contraband_js.sh patterns work correctly.

**Architecture Cleanup (2026-01-29):**
- kernel.py: DELETED legacy Kernel class (~350 lines removed)
  - KEPT: Step budget infrastructure (get_step_budget, reset_step_budget, MAX_PROJECTION_STEPS)
  - DELETED: Kernel class, create_kernel(), compute_identity(), detect_stall(), gate_dispatch(), record_trace()
- Archived: `test_kernel_v0.py` moved to `archive/tests/legacy/` (moved from tests/archive/ in wave15)
- Created: `tests/structural/test_lambda_calculus_guardrails.py` (11 tests)
- Added: Tests for `is_kernel_intermediate()` (12 tests)
- Note: `MAX_PROJECTION_STEPS=50000` (kernel.py) is NOT used by step_kernel_mu which uses `max_steps=10000`

**Security Fuzzers (2026-01-29):**
- Created `tests/fuzz/test_security_boundary_fuzzer.py` (24 tests) - validate_no_kernel_reserved_fields
  - Tests depth guards, nested smuggling, unicode homoglyphs, list traversal
- Created `tests/fuzz/test_seed_integrity_fuzzer.py` (21 tests) - seed validation functions
  - Tests checksum tampering, structure validation, projection order security, injection attacks

**L2 Grounding & Boundary Validation (2026-01-29):**
- Fixed docstring false positive at eval_seed.py:70 (was being counted as debt)
- Updated SelfHosting.v0.md re: kernel.py cleanup (legacy Kernel class deleted)
- Created `tests/structural/test_l2_cursor_grounding.py` (7 tests) - proves linked-list cursor:
  - Verifies `_remaining` is structural (head/tail), not arithmetic index
  - Tests kernel.wrap creates _remaining from _projs linked list
  - Tests kernel.try consumes head, kernel.match_fail advances to tail
- Created `tests/fuzz/test_boundary_validation_fuzzer.py` (27 tests) - boundary guards:
  - Tests assert_seed_pure with valid/invalid inputs (lambdas, functions, builtins)
  - Tests validate_type_tag whitelist enforcement (list/dict only)
  - Tests get_var_name validation (empty names, non-var sites)
- Created `tests/fuzz/test_kernel_bridge_fuzzer.py` (26 tests) - kernel bridge functions:
  - Tests list_to_linked (preserves length, order, produces valid Mu)
  - Tests normalize_projection (pattern/body normalization)
  - Integration tests for projection list conversion

**Phase 8a IMPLEMENTED (2026-01-28):**

4 bootstrap primitives marked with `# BOOTSTRAP_PRIMITIVE` (+ 1 eliminated):
1. `eval_step` - `rcx_pi/selfhost/eval_seed.py:step()`
2. `max_steps` - `rcx_pi/selfhost/step_mu.py:step_kernel_mu()` (see `BOOTSTRAP_PRIMITIVE: max_steps` comment)
3. `stack_guard` - `rcx_pi/selfhost/mu_type.py:MAX_MU_DEPTH`
4. `projection_loader` - `rcx_pi/selfhost/seed_integrity.py:load_verified_seed()`
- ~~`mu_equal`~~ - DEMOTED from bootstrap primitive (Level 1 Content-Addressed Mu). All production call sites use `mu_hash_cached()` directly. Convenience wrapper retained for ~30 test call sites + JS parity.

**mu_equal DEMOTED from Bootstrap Primitive (2026-02-10, Content-Addressed Mu Level 1):**
- **Level 1 IMPLEMENTED**: `mu_hash_cached()` replaces all production `mu_equal` call sites
- `mu_equal` retained as convenience wrapper delegating to `mu_hash_cached(a) == mu_hash_cached(b)`
- Bootstrap primitive count: 5 → 4 (eval_step, max_steps, stack_guard, projection_loader)
- JS parity: `muHashCached()` added, `muEqual()` delegates to hash comparison
- **Paxos e2e pipeline test**: `tests/integration/test_paxos_end_to_end.py` (6 tests) validates full deadlock metabolization
- **Parity fuzzer**: `tests/fuzz/test_mu_equal_parity_fuzzer.py` proves equivalence (13 tests, 500+ inputs)
- **Historical context (2026-01-31):** 9-agent consensus confirmed json.dumps IS structural equality for JSON data

**Document updated with:**
- Scope and Self-Hosting Levels section
- Recurrence Compatibility section
- Hidden/Implicit Primitives section
- Known Limitations section

**Tests created:**
- `tests/structural/test_bootstrap_primitives.py` (36 tests)
- `tests/fuzz/test_bootstrap_fuzzer.py` (18 property-based tests)

**See `mu/docs/core/BootstrapPrimitives.v0.md`** for full specification.

**Phase 8b IMPLEMENTED (2026-01-28):**

Simplified step_kernel_mu to MECHANICAL operation:
1. Added `is_kernel_terminal()` - simple structural marker detection
2. Added `extract_kernel_result()` - mechanical unpacking
3. Removed ~20 lines of semantic branching from loop
4. Loop body now only checks structural markers + stall detection
5. Fixed empty container type preservation (KNOWN LIMITATION resolved):
   - `[]` now normalizes to `{"_type": "list"}` (was `None`)
   - `{}` now normalizes to `{"_type": "dict"}` (was `None`)
   - Denormalization correctly reverses typed sentinels
   - Normalization is now idempotent
6. All 2,846 tests pass

**Tests created:**
- `tests/engine/test_phase8b_mechanical_kernel.py` (31 tests)
- `tests/engine/test_phase8b_grounding_gaps.py` (12 tests)

**Debt:** 11 (9 tracked decorators + 2 AST_OK bootstrap = tracked marker count; was 12 before CP-S1A wave 25)

---

**Completed (Phase 7c):**
- [x] Created `mu/substrate/kernel.v1.json` with 7 kernel projections
- [x] 30 manual trace tests pass (success, failure, empty, fallthrough)
- [x] Created `match.v2.json` with context passthrough + match.fail catch-all
- [x] Created `subst.v2.json` with context passthrough
- [x] 20 integration tests pass (kernel → match → subst → kernel)
- [x] 7 agent review complete (2026-01-28)

**Completed (Phase 7d-1):**
- [x] Wired step_mu to structural kernel (kernel.v1 + match.v2 + subst.v2)
- [x] Added helpers: list_to_linked, normalize_projection, load_combined_kernel_projections
- [x] Updated test_step_mu_parity.py for behavioral difference (unbound vars stall instead of error)
- [x] All 106 core tests pass
- [x] 7-agent review identified execution loop still Python (honest assessment)
- [x] Added @host_iteration to step_kernel_mu (honest debt tracking)
- [x] 9-agent review of Phase 8 design completed (2026-01-28)

**Behavioral Change (7d-1):**
- **Before:** Unbound variables raised `KeyError`
- **After:** Unbound variables cause stall (return original input)
- This is more consistent with pure Mu semantics where errors become stalls

**Historical closure (resolved by Phase 8 decision):**
- Phase 7d-2: Migrate projection_runner to step_mu (closed)
- Phase 7d-3: Eliminate projection_runner iteration (closed)
- Reason: 7d-1 moved the loop; Phase 8 accepted irreducible iteration as bootstrap primitive.

---

**Last updated:** 2026-03-14 (P7-bcd chain landed, TASKS.md NEXT sync, STATUS.md L4 status refresh, .claude/commands/ duplicate removed)
**Next milestone:** Hemisphere Metabolization Contract remains the closed milestone baseline (E1-E5 all MET, 2026-02-20); post-closure execution continues on L4_STRUCTURAL promotion-path work (post A18-P0), with explicit workload targets `rcx_engine.v1` (RCXEngineNew cycle) and UniversalEval/UniversalRecursion path evidence. Canonical authorization remains TASKS.md.

**Legacy Surface Decision Record (2026-02-14, Round 19D):**
- rcx_pi_rust → ARCHIVED, rcx_omega → ARCHIVED, worlds_json → MAINTAIN (at `mu/worlds_json/`)
- Decision record: `mu/docs/core/LegacySurfaceDecisionRecord.v0.md`
- No code changes; governance-only round

**Hemisphere Hardening (2026-02-10):**
- JS substrate now verifies all 7 seeds at load time (SHA256 checksum, structure validation, projection ID ordering)
- L3 parity gap closed: Python verified seeds, JS now does too
- Python `validate_projection_ids` enforces exact ordered equality (first-match-wins security)
- JS `classifyLegacyLinkedList` cycle detection activated
- Deprecated `get_seeds_dir` removed
- 63 hemisphere adversarial tests added

**Gate Snapshot (Canonical):**
- Gate 3: COMPLETE (2026-02-07)
- Gate 4: COMPLETE (2026-02-07 structural cutover)
- Gate 5: COMPLETE (2026-02-09 meta-circular parity verified)
  - 56 exit criteria tests pass: 9 gate5 parity + 17 execution path + 30 JS parity
  - Structural execution is default; bootstrap is explicit fallback only
  - Cross-substrate parity intact (Python + JS, all L3 seed projections — see `test_seed_counts.py`)
  - B-structural match_mu (match.v2 + bridge) provides non-linear pattern support

Current Recurrence Layer: META_CIRCULAR
Current Exhaustion Layer: META_CIRCULAR

**Known Architectural Constraints:** See "Known Architectural Constraints" section in [`archive/roadmap/MetaCircular_Boot0_GatePlan.md`](archive/roadmap/MetaCircular_Boot0_GatePlan.md) for authoritative documentation of:
- Why kernel reserved fields block algorithm entry
- Why kernel-internal bypass exists for hybrid execution
- Historical trace matcher split and its Gate 5 parity resolution
- Resolution path through Gates 3-5

**mu/ Folder Reorganization (2026-02-02):**
New organized structure makes architecture visible:
- `mu/substrate/` - Kernel VM: kernel.v1, match.v1, match.v2, subst.v1, subst.v2
- `mu/closures/` - Closure detection: recurrence.v1 (was enginenews), exhaustion.v1 (was exhaust)
- `mu/programs/` - Applications: rcx_engine.v1 (orchestrates recurrence + exhaustion)
- `mu/utilities/` - Helpers: classify.v1, eval.v1
- `mu/host/js/` - JavaScript bootstrap: eval_step.js
- `mu/host/python/rcx_pi/` - Python bootstrap (canonical; `rcx_pi/` is backward-compat symlink)

**Architectural Gap Discovery (2026-02-02):**
9-agent review of Step 6 revealed: match.v2.json is "linear only" but enginenews.v1 and exhaust.v1 require non-linear patterns. These seeds work via bootstrap (eval_seed) but CANNOT run through the meta-circular kernel. This was documented but not caught because tests passed.

**Response:**
- Added North Star #14 (execution layer declaration) and #15 (true self-hosting path)
- Added Cross-Seed Compatibility Check to AgentGuardrails.v0.md
- Created VECTOR item for Bootstrap-Structural Bridge (non-linear pattern support)
- Updated seed meta sections with `"execution_layer": "BOOTSTRAP"` (at the time)
- **Resolved by Gate 4 cutover (2026-02-07):** recurrence/exhaustion now run structurally by default via kernel bridge path

**Completed (Steps 1-6):**
1. ✅ Fixed JS security gaps (KERNEL_RESERVED_FIELDS, type tag validation, dict kv-pair fix)
2. ✅ Cross-substrate parity tests (20 vectors, tests/parity/test_parity_python.py)
3. ✅ Phase 8d trace model in Python (run_mu_structural, tests/engine/test_structural_trace.py)
4. ✅ Ported trace to JS (runStructural in mu/host/js/eval_step.js)
5. ✅ Recurrence structural closure detection (mu/closures/recurrence.v1.json, 9 projections)
6. ✅ Operator Exhaustion (mu/closures/exhaustion.v1.json, 13 projections)

**L3 COMPLETE:** All projections run on both Python and JavaScript with identical semantics.

**Proof:**
- [x] kernel.v1.json: 7 projections (Python ✓, JS ✓) - META_CIRCULAR
- [x] match.v2.json: 8 projections (Python ✓, JS ✓) - META_CIRCULAR (linear only)
- [x] subst.v2.json: 13 projections (Python ✓, JS ✓) - META_CIRCULAR
- [x] recurrence.v1.json: 9 projections (Python ✓, JS ✓) - META_CIRCULAR (bridge-backed)
- [x] exhaustion.v1.json: 13 projections (Python ✓, JS ✓) - META_CIRCULAR (bridge-backed)
- [x] hemispheres.v1.json: 12 projections (Python ✓, JS ✓) - APPLICATION (linear-only, no bridge needed)
- [x] Total: 61 projections across 6 listed seeds (see `mu/tests/structural/test_seed_counts.py::EXPECTED_COUNTS` for per-seed counts)
- [x] Seed integrity: 19 seeds, 162 projection IDs, 0 intra-seed collisions (verified by `mu/tests/structural/test_seed_counts.py`)
- [x] 5 Recurrence + 6 Exhaust parity vectors pass on both substrates

**Bootstrap-Structural Bridge: IMPLEMENTED (Two Execution Paths)**
- Location: `mu/bridge/bootstrap_structural.v1.json` (5 projections)
- Design doc: `mu/docs/core/BootstrapStructuralBridge.v0.md`
- Execution path verified: bridge projections DO fire for non-linear patterns
- **Path 1: match_mu direct** (2026-02-09) — `match_mu()` loads match.v2 + bridge projections via `projection_runner`. Provides non-linear pattern conflict detection for `apply_mu()` without kernel overhead.
- **Path 2: kernel bridge mode** — `run_algorithm_meta_circular()` dispatches to `step_kernel_mu(kernel_mode="bridge")` for recurrence/exhaustion.
- **Fail-closed guard:** `step_mu()`/`run_mu()` reject non-linear patterns with ValueError, directing callers to bridge-aware paths.
- JS substrate loads bridge projections (`mu/host/js/eval_step.js`) for structural parity paths.

**Current Algorithm Execution:**
- `run_algorithm_meta_circular()` defaults to `step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")`
- Bootstrap fallback exists only as explicit debug mode (`execution_mode="bootstrap", allow_bootstrap_fallback=True`)
- Algorithm runtime is bridge-backed meta-circular: the kernel loop runs structurally via `step_kernel_mu`, but non-linear matching delegates to host code via bridge projections

**Meta-Circular Execution Evidence (Wave I Phase 2, verified 2026-03-12):**
- kernel.v1 + match.v2 + subst.v2 execute STRUCTURALLY in the kernel loop (28 combined projections, 10+ steps per match+subst)
- `_step_trusted` is a projection loop (iterates projections via `_apply_projection_trusted`, plus coverage hooks) → Stage0 bootstrap (irreducible ~80 LOC)
- Stage0 (`_stage0_match` + `_stage0_substitute`) is the irreducible bootstrap: applies projections mechanically with minimal host-level branching (var binding, type dispatch, dict traversal)
- Cross-substrate parity confirmed for linear projections: Python and JS produce identical step counts and results (nonlinear projections are correctly rejected by JS `step_kernel_meta` per existing parity policy — see `rejectNonlinearProjections` guard)
- Evidence: `mu/tests/l4_gates/test_meta_circular_evidence_gate.py` (24 gate tests, including Stage0 routing lock)

**Remaining host dependency:** Stage0 breaks the circular dependency (kernel → match → kernel). This is the irreducible bootstrap — not a deficiency but an architectural necessity.

**Bridge-backed algorithm execution:** recurrence.v1 and exhaustion.v1 use bridge mode (`kernel_mode="bridge"`) which adds 5 bridge projections for non-linear pattern support. The kernel loop is structural, but bridge projections delegate non-linear matching to host `_match_inner`. True non-linear structural matching is a future L4 gate target.

**Agent Validator Enhancement (2026-02-03):**
- `tools/runners/validate_agent_compliance.py` now verifies CODE matches FILE:LINE
- `--strict` mode (used by hook) catches fabricated citations
- All 9 agent prompts updated with fabrication warning

**9-Agent Rigorous Tooling Hardening (2026-02-08):**
- `--rigorous` now overrides depth to "all" (runs all 9 agents, was only running 6)
- Reasoning validation + skeptic always run, even on compliance failures (was skipped)
- `validate_agent_reasoning.py` regex fixed: now parses `### CHECKED` markdown headers and numbered items
- 5 fuzzer test files from agent findings #1017-#1021 (88 tests):
  - `test_cross_seed_boundary_fuzzer.py` (#1017) - kernel state machine boundary fuzzing
  - `test_algorithm_oscillation_fuzzer.py` (#1018) - algorithm runtime stability
  - `test_nonlinear_bridge_fuzzer.py` (#1019) - non-linear pattern binding conflicts
  - `test_normalized_injection_fuzzer.py` (#1020) - normalized dict security bypass
  - `test_trace_malformation_fuzzer.py` (#1021) - trace format robustness
- Shared Hypothesis strategies extracted to `tests/strategies.py`
- Iteration guards added to `match_mu.py` (bindings_to_dict, denormalize_from_match)
- INFRA_CEILING: 37 → 38 (5 new AST_OK:infra markers for iteration guards)
