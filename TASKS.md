# RCX Task List (Canonical)

This file is the single source of truth for authorized work.
If a task is not listed here, it is NOT to be implemented.

---

## North Star (Keep This True)

1. RCX VM is not a "runner". It is a substrate where **structure is the primitive**.
2. "Code = data" means execution is graph/mu transformation, not host-language semantics.
3. **Stall → Fix → Trace → Closure** is the native engine loop; everything else must serve it.
4. Closures/gates must be **explicit, deterministic, and measurable** (fixtures + replay).
5. Emergence must be attributable to RCX dynamics, not "Python did it".
6. Host languages are scaffolding only; their assumptions must not leak into semantics.
7. Buckets (r_null / r_inf / r_a / lobes / sink) are **native routing states**, not metaphors.
8. Seeds must be minimal (void/empty) and growth must be structurally justified.
9. Determinism is a hard invariant: same seed + rules ⇒ same trace/fixtures.
10. A "program" is a pressure vessel: seed + allowable gates + thresholds + observation outputs.
11. Enginenews-like specs are target workloads to prove: "does ω/closure actually emerge?"
12. Every task must answer: "Does this reduce host smuggling and increase native emergence?"
13. **L3 Parity: Python and JavaScript must run identical projections with identical semantics.**
    - Same seeds: kernel.v1, match.v2, subst.v2, recurrence.v1, recurrence.v2, exhaustion.v1, hemispheres.v1, rcx_engine.v1 (47+ core projections + 7 engine)
    - Same bootstrap primitives: eval_step, max_steps, stack_guard, projection_loader (mu_equal ELIMINATED — Level 1 Content-Addressed Mu)
    - Any change to Python projection behavior MUST be mirrored in JS
    - Any new seed MUST be loaded and tested in BOTH substrates
14. **Seeds must declare their execution layer.** Every seed is either:
    - **BOOTSTRAP**: Runs via eval_seed.step() only (Python/JS substrate provides non-linear pattern support)
    - **META-CIRCULAR**: Runs via step_kernel_mu (kernel.v1 + match.v2 + subst.v2)
    - If a seed claims META-CIRCULAR, tests MUST verify it through step_kernel_mu
    - Non-linear pattern seeds become META-CIRCULAR only when bridge-backed structural runtime is default
    - Current BOOTSTRAP seeds: eval.v1 (uses [] arrays, requires bootstrap match/substitute)
    - Current META-CIRCULAR seeds: kernel.v1, match.v2, subst.v2, recurrence.v1, exhaustion.v1, classify.v1
15. **True self-hosting is the path.** The goal is structural computation without host semantics:
    - **L1 (Algorithmic)**: match/subst algorithms as Mu projections ✓ DONE
    - **L2 (Operational)**: kernel loop as Mu projections ✓ DONE (with bootstrap primitive acceptance)
    - **L3 (Substrate Portability)**: same projections run on Python AND JavaScript ✓ DONE
    - **L4 (True Self-Hosting)**: eliminate bootstrap primitives OR make them substrate-independent
    - Programs must run accurately and structurally, without host semantics (except irreducible bootstrap)
    - Tests must verify the CLAIMED execution path, not just correctness
    - If tests pass via bootstrap but fail via meta-circular kernel, that's a real bug (not theater)

---

## Governance (Non-Negotiable)

- Do not add new subsystems, execution models, or architectures without explicit approval.
- Do not create "new tests" to bypass a failing test; fix the failing test or the code.
- Do not leave broken files/tests behind and add replacements.
- Minimize file creation. Prefer editing existing files.
- v1 replay semantics are frozen. Any new observability must be v2 and gated.
- **L3 Parity Rule**: Changes to `rcx_pi/selfhost/` or `mu/` MUST be mirrored in `mu/host/js/eval_step.js`.
  - Run `node mu/host/js/eval_step.js` to verify all JS tests pass
  - Run `./tools/check_js_debt.sh` to verify JS debt markers match Python
  - Run `./tools/contraband_js.sh` to verify no forbidden patterns (determinism, purity)
  - Run `./tools/ast_police_js.sh` to catch JS patterns that bypass grep
  - Run `./tools/check_test_theater_js.sh` to catch vacuous JS assertions
  - Run `./tools/seed_police.sh` to verify seed integrity and no host leakage
  - New seeds must be loaded in both Python and JavaScript
  - Parity vectors must pass on both substrates before merge
- **Pre-commit doc review**: Before committing changes to `rcx_pi/`, `prototypes/`, or `mu/`:
  1. Read relevant docs in `docs/` (e.g., EVAL_SEED.v0.md, DeepStep.v0.md)
  2. Update docs if implementation differs from spec
  3. Update TASKS.md status if completing/progressing items
  4. Verify JS parity if projection behavior changed
- **Agent runbook**: Agent usage follows `docs/agents/AgentRunbook.v0.md` (trigger map, gate rules, and evidence requirements)
- **Roadmap rule**: Documents in `roadmap/` define SEQUENCE and DESIGN only.
  - Current state lives in STATUS.md; authorization lives in TASKS.md
  - Gate completion updates TASKS.md (Ra/NEXT/VECTOR), not roadmap docs
  - Draft specs live in `roadmap/`; approved specs migrate to `docs/core/`
  - See `roadmap/MANIFEST.md` for reading order and linking rules

## Collaboration Protocol (Default Working Mode)

- **VECTOR mode (design/creation)**: Explore ontology-to-runtime mappings, propose alternatives, and identify missing mechanisms. No implementation begins in VECTOR.
- **NEXT mode (execution/verification)**: Implement bounded, testable slices only. Mirror Python/JS semantics and preserve deterministic behavior.
- **Falsifiability gate**: Every new design claim must map to a measurable runtime behavior and at least one concrete test criterion.
- **Cross-model continuity**: Inputs from Codex, Claude, or Gemini are design references, not authority. Canonical authority remains `STATUS.md` + `TASKS.md`.
- **Promotion discipline**: Creative proposals must be explicitly promoted (`VECTOR -> NEXT`) before code changes.

---

## Promotion Criteria (Non-Negotiable)

- **SINK → VECTOR**: Item must have a clear semantic question to answer. A design doc must be written before any implementation. Promotion must be explicit and documented in this file.
- **VECTOR → NEXT**: Design doc must be complete and reviewed. Semantics must be locked. Implementation scope must be bounded and testable. Observability must precede mechanics.
- Promotion is never implicit. Moving an item between sections requires updating this file with rationale.
- **PR rule**: Any PR that implements a VECTOR/SINK item without an explicit promotion note in this file must be rejected.
- No implementation work may begin on VECTOR items. VECTOR is design-only.
- No SINK item may advance without answering: "What semantic question does this resolve?"

---

## Ra (Resolved / Merged)

Items here are implemented and verified under current invariants. Changes require explicit promotion through VECTOR and new tests. Completed NOW/NEXT items are archived here.

- Deterministic trace core (v1) complete
- Tracker sync note (2026-02-07): `match_mu` var-name scan cycle guard was corrected to allow shared substructures (DAG reuse) while still rejecting true active-path cycles; no phase/task promotion.
- Tracker sync note (2026-02-10): `match_mu` bridge cache defensive copy + `seed_integrity` MU_SEED_LOCATIONS moved to module level; agent verdict extraction hardened across all 9 prompts; no phase/debt/task change.
- Tracker sync note (2026-02-10): `seed_integrity` fail-closed warning on unregistered seeds + paxos_demo registration; `run_review` memory_context sanitization; translator max_turns increased; no phase/debt/task change.
- Tracker sync note (2026-02-11): `_run_sub_algorithm` budget fix — removed cross-iteration budget sharing; per-call budget in step_kernel_mu is sufficient, outer loop bounded by max_iterations. Slow test split: `test_paxos_end_to_end.py` and `test_recurrence_production.py` marked `@pytest.mark.slow`, excluded from CI fast gate, run in `audit_all.sh`; no phase/debt/task change.
- Tracker sync note (2026-02-11): Stall-detection hash caching — cache `current_hash` across loop iterations in 6 Python sites (step_kernel_mu, run_mu, run_mu_structural, _run_sub_algorithm, _resolve_trace_projection_id, projection_runner) + 4 JS sites (L3 parity). Halves hash calls per iteration. green_gate.yml: ci_fast on push (was ci_full), timeout 20→30m. 5 additional tests marked slow (3 engine pipeline, 1 hemisphere adversarial, 1 structural trace fuzzer). No phase/debt/task change.
- Tracker sync note (2026-02-11): CI green gate 28 min → 2 min — hypothesis fuzzers auto-marked via `pytest_collection_modifyitems` (452 tests deselected), 168 slow tests moved out of gate, `pytest-timeout` added to test extras, fragile grounding test fixed. Green gate runs ~2,500 core tests in ~50s CI. Nightly (ci_full) still runs everything. No phase/debt change.
- Tracker sync note (2026-02-11): Static speed enforcer — `tools/check_test_speed.sh` grep-based detection of test files importing slow kernel functions without `@pytest.mark.slow`. Integrated into `tools/pre-commit-doc-check` (section 4b). 7 existing violations fixed. No phase/debt change.
- Tracker sync note (2026-02-12): JS engine-hemisphere parity — `runEnginePipeline`, `hashTraceForRecurrence`, `runHemisphereRouting`, `runEngineWithRouting` added to `eval_step.js`. rcx_engine.v1.json + recurrence.v2.json now loaded in JS. 4 JSON API actions, 6 inline tests, 6 cross-substrate parity tests (36 total pass). `_state_hash`/`_check_hash` added to JS ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS (pre-existing parity gap). JS debt: 13→15. No phase change.
- Hemisphere hardening (2026-02-12, PR #239): caller-trust model (`_step_trusted`/`_apply_projection_trusted`), JS parity (substitute throw, isKernelIntermediate, inject_key guard, `||`→`??` numeric defaults, hard-cap 100k parity, RcxError at boundaries), boundary result validation in engine pipeline, `_walk_and_validate` shared traversal, dead code removal (eval_seed.py), test dedup (`hemisphere_helpers.py`, `EXPECTED_PROJECTION_IDS`, DummyBudget consolidation). 3 rounds of 9-agent rigorous review. No phase/debt change.
- HF2 maxSteps guard (2026-02-10): `guardMaxSteps()` enforces type (integer), range (>=0), and cap (<=10000) on all 8 maxSteps-accepting JSON API endpoints. Closes HF2 Mode-B DoS vector. Manifest: 14/18 actions now `requires_error_edges=true`. 169 parity/coverage tests green.
- N1b typed-error parity (2026-02-13): 14 JS boundary throw sites converted from untyped `Error`/`TypeError` to `RcxError` with stable `error_code` (normalize, step/run/runStructural, validateNoKernelReservedFields, validateAlgorithmRuntimeFields, runHemisphereRouting, runEngineWithRouting). Manifest ratchet: all 18 actions declare `requires_error_edges`; 10 with error edges, 8 with `success_only_reason`. 22 error_code parity tests + 8 ratchet invariant tests. No phase/debt change.
- Mu Hemispheres v0 — Engine integration COMPLETE (2026-02-11): `run_engine_with_routing()` chains `run_engine_pipeline()` → `run_hemisphere_routing()` with fail-closed input/output validation. `hash_trace_for_recurrence` cycle guard added (visited set + 10000 iteration cap). 10 integration tests (8 fast + 2 slow). Paxos livelock → closure → r_a proven end-to-end.
- Replay semantics frozen (v1)
- Entropy sealing contract in place
- Golden fixtures in place
- Replay gate + CI enforcement in place
- Rust replay acceleration bit-for-bit compatible
- v2 trace schema + observability events (RCX_TRACE_V2=1)
- Stall/Fix execution semantics v0 (RCX_EXECUTION_V0=1)
- ExecutionEngine + value_hash(); motif serialization (_motif_to_json) is test infrastructure only
- Record Mode v0 (execution → trace for stall/fix events)
- Minimal Native Execution Primitive doc (Boundary Question answered)
- v2 replay validation (validate_v2_execution_sequence)
- Anti-theater guardrails:
  - `--print-exec-summary` CLI flag + `execution_summary_v2()` pure helper
  - `test_cli_print_exec_summary_end_to_end` (subprocess CLI test)
  - `tools/audit_exec_summary.sh` (non-test reality anchor)
- Trace Reading Primer (`docs/TraceReadingPrimer.v0.md`)
- Record→Replay Gate (`test_record_replay_gate_end_to_end`)
- Flag Discipline Contract (`docs/Flags.md`)
- Consume execution.fix from trace (true cycle replay)
- Closure-as-termination fixture family (`stall_at_end.v2.jsonl`, `stall_then_fix_then_end.v2.jsonl`)
- IndependentEncounter pathological fixtures + tests
- Recurrence spec stress-test harness (`tests/test_recurrence_spec_v0.py`)
- CI audit gate (`tools/audit_all.sh` + `.github/workflows/audit_all.yml`)
- Closure Evidence reporting flag + CLI test (`--print-closure-evidence`, `closure_evidence_v2()`)
- Rule Motif Observability v0 (`rcx_pi/rule_motifs_v0.py`, `rules --print-rule-motifs`, 11 CLI tests)
- Rule Motif Validation Gate v0 (`validate_rule_motifs_v0()`, `rules --check-rule-motifs`, 16 CLI tests)
- Trace canon helper v1 (`canon_jsonl()`, 7 tests in `test_trace_canon_v1.py`)
- Second Independent Encounter v0 (stall memory tracking, closure signal detection, 25 tests)
- Closure Evidence Events v0 (design complete, `--print-closure-evidence` CLI, `closure_evidence_v2()` helper)
- Recurrence Spec v0 (stress test harness, 18 tests in `test_recurrence_spec_v0.py`, 4 fixtures)
- Bytecode VM v0/v1a/v1b — **ARCHIVED** (superseded by kernel + seeds approach)
  - Code: `rcx_pi/bytecode_vm.py` (legacy, not maintained)
  - Docs: `docs/archive/bytecode/` (archived)
- Mu Type v0 (`rcx_pi/mu_type.py`, `docs/core/MuType.v0.md`, 58 tests)
- Structural Purity Guardrails v0 (`docs/StructuralPurity.v0.md`, 32 additional tests):
  - `has_callable()`, `assert_no_callables()`, `assert_seed_pure()`
  - `assert_handler_pure()`, `validate_kernel_boundary()`
  - `tools/audit_semantic_purity.sh` extended with checks 9-11
- RCX Kernel Phase 1 (`rcx_pi/kernel.py`, `docs/RCXKernel.v0.md`, 47 tests)
- EVAL_SEED v0 (`rcx_pi/eval_seed.py`, `docs/core/EVAL_SEED.v0.md`, 125 tests):
  - Core operations: `match`, `substitute`, `apply_projection`, `step`
  - Only special form: `{"var": "x"}` (variable binding)
  - Kernel handlers: step, stall, init
  - Answer: EVAL_SEED is tractable (~200 lines)
  - Adversary tests: 43 attack tests in `test_eval_seed_adversary.py`
- Verification Agent Infrastructure (`tools/agents/`):
  - Verifier agent: read-only audit against North Star invariants
  - Adversary agent: red team attack testing
  - PR verification reminder workflow (auto-comment on sensitive file changes)
  - RATCHET debt policy: threshold can only decrease, never increase
- RCX Kernel Phase 4-5: Algorithmic Self-Hosting (L1) Done:
  - Phase 4a: `match_mu()` as Mu projections (`mu/substrate/match.v1.json`, 23 parity tests)
  - Phase 4b: `subst_mu()` as Mu projections (`mu/substrate/subst.v1.json`, 17 parity tests)
  - Phase 4d: Integration tests (67 total: 28 parity + 27 grounding + 12 fuzzer)
  - Phase 5: `step_mu()` uses match_mu + subst_mu (33 tests: 22 parity + 11 self-hosting)
  - `tests/structural/test_apply_mu_grounding.py` - direct `step()` execution tests
  - `tests/test_apply_mu_fuzzer.py` - Hypothesis property-based tests
- Self-Hosting Security Hardening (PR #149):
  - Thread-safe step budget: `threading.local()` for concurrent execution safety
  - Cycle detection in `normalize_for_match()` and `denormalize_from_match()`
  - Global projection step budget: `_ProjectionStepBudget` class (50,000 step limit)
  - Resource exhaustion guardrails: MAX_MU_DEPTH=300, MAX_MU_WIDTH=1000
  - Comprehensive fuzzer tests (`tests/test_selfhost_fuzzer.py`, 53 tests, 10,000+ examples):
    - `TestMatchMuParity`: match_mu == eval_seed.match (1,000 examples)
    - `TestSubstMuParity`: subst_mu == eval_seed.substitute (1,200 examples)
    - `TestHostileUnicodeHandling`: emoji, RTL, zero-width, homoglyphs
    - `TestNearLimitStress`: width 900-1000, depth 190-200
  - Budget exhaustion tests: nested calls, thread isolation
  - Empty variable name rejection (parity with eval_seed.py)
- Package Reorganization (PR #145):
  - Core self-hosting files moved to `rcx_pi/selfhost/` subpackage
  - Re-export stubs at original locations for backward compatibility
  - Audit script updated to support both layouts
  - Files: mu_type.py, kernel.py, eval_seed.py, match_mu.py, subst_mu.py, step_mu.py
- Comprehensive Debt Tracking (PR #155):
  - All ~289 LOC semantic debt now marked with `@host_*` decorators
  - DEBT_THRESHOLD updated: 14 → 23 (17 tracked + 5 AST_OK + 1 review)
  - Design decisions documented (empty collection normalization, head/tail collision)
  - 10 new tests for edge cases (TestMatchParityHeadTailCollision, TestMatchParityEmptyCollections)
- QoL Infrastructure (PRs #131+):
  - Agent reports as PR comments (verifier, adversary, expert, structural-proof)
  - Debt dashboard (`tools/debt_dashboard.sh`)
  - Canonical pre-commit local gate (`tools/pre-commit-doc-check`)
  - Projection test coverage (`rcx_pi/projection_coverage.py`)
  - Agent memory across sessions (`tools/agent_memory.py`)
  - Trace visualization (`tools/trace_viewer.py`)
- Seed Integrity Verification (PR #157):
  - SHA256 checksum verification for seed files (match.v1.json, subst.v1.json)
  - Structure validation (meta, projections keys, required fields)
  - Projection ID verification (expected IDs present, wrap is last)
  - 27 tests in `tests/test_seed_integrity.py`
  - Security foundation: seeds now verified on load (adversary finding closed)
- Phase 6a: Lookup as Mu Projections (PR #158):
  - Added `subst.lookup.found` and `subst.lookup.next` projections to subst.v1.json
  - Lookup is now structural: pattern matching with non-linear vars (same name binds same value)
  - Removed 2 `@host_builtin` decorators from subst_mu.py
- Phase 6b: Classification as Mu Projections:
  - Created `mu/utilities/classify.v1.json` with 6 projections for linked list classification
  - Created `rcx_pi/selfhost/classify_mu.py` for projection-based classification
  - `denormalize_from_match()` now uses `classify_linked_list()` instead of `is_dict_linked_list()`
  - Classification distinguishes dict-encoding (all kv-pairs with string keys) from list-encoding
  - Handles edge cases: nested dicts in key position, circular references, primitives
  - Removed 2 `@host_builtin` decorators from match_mu.py (is_kv_pair_linked, is_dict_linked_list)
  - DEBT_THRESHOLD: 21 → 19 (ratchet tightened)
  - 26 new tests in `tests/test_classify_mu.py`
- Boot0 Architecture v0.4 (`docs/core/Boot0Architecture.v0.md`) - 9-agent reviewed 2026-01-31:
  - Hex0-inspired staged bootstrap design: Boot0 → Boot1 → Boot2
  - 4 irreducible bootstrap primitives: eval_step, max_steps, stack_guard, projection_loader (mu_equal eliminated via Level 1 Content-Addressed Mu)
  - Boot0=structural, Boot1=none, Boot2=kernel validation boundaries
  - v0.4: Added "stable semantics, shrinking substrate", JSON as Phase 0 format, explicit handshake ABI, security invariants, L3 parity contract
  - Design COMPLETE, implementation DEFERRED per 9-agent Advisor recommendation
  - L3 is complete; Boot0 extraction can wait until L4 research drives it
- mu_equal ELIMINATED as Bootstrap Primitive (2026-02-10, Content-Addressed Mu Level 1):
  - **Level 1 IMPLEMENTED**: `mu_hash_cached()` replaces all 8 production call sites (eval_seed 2, step_mu 5, projection_runner 1)
  - Bootstrap primitives: 5 → 4. `mu_equal` retained as convenience wrapper only.
  - JS parity: `muHashCached()` added, `muEqual()` delegates. 6 JS call sites updated.
  - Paxos e2e pipeline test: `tests/test_paxos_end_to_end.py` (6 tests) validates deadlock metabolization
  - Historical: 9-agent consensus (2026-01-31) confirmed json.dumps IS structural equality for JSON data
  - Parity fuzzer: `tests/test_mu_equal_parity_fuzzer.py` (13 tests, 500+ inputs)
- Testing Tier System (2026-01-28):
  - 9-agent review resolved fuzzer hang issue (rejected circuit breaker, chose Option B)
  - Tier 1: `audit_fast.sh` (~3 min) - Core tests for local iteration
  - Tier 2: `audit_all.sh` (~5-8 min) - Core + Fuzzer for CI
  - Tier 3: `tests/stress/` (~10+ min) - Deep edge cases for comprehensive validation
  - Fuzzer settings standardized: `max_depth=3` (generators AND call sites), `deadline=5000`
  - Files standardized (6): test_bootstrap_fuzzer.py, test_selfhost_fuzzer.py, test_type_tags_fuzzer.py, test_apply_mu_fuzzer.py, test_phase8b_fuzzer.py, test_phase7_readiness_fuzzer.py
  - Call site overrides fixed: 29 instances of `max_depth=4` → `max_depth=3` across 4 files
  - Hypothesis profiles: `HYPOTHESIS_PROFILE=dev` for fast local fuzzer runs (50 examples)
  - See STATUS.md "Testing Tiers" for current config (single source of truth)
  - DEBT_THRESHOLD: 23 → 21 (ratchet tightened)
  - `resolve_lookups()` Python function deprecated (kept for backward compat)
  - 37 subst parity tests pass with structural lookup
- Phase 6c: Normalization as Iterative + Type Tags:
  - `normalize_for_match()`: recursive → iterative with explicit stack
  - `denormalize_from_match()`: recursive → iterative with explicit stack
  - Removed 2 `@host_recursion` decorators from match_mu.py
  - Removed 2 `# AST_OK: bootstrap` comments (recursive comprehensions eliminated)
  - isinstance() at Python↔Mu boundary is scaffolding, not semantic debt
  - Type tags (`_type: "list"` or `_type: "dict"`) resolve list/dict ambiguity
  - New projections: `match.typed.descend`, `subst.typed.{descend,sibling,ascend}`
  - Security: `VALID_TYPE_TAGS` whitelist + `validate_type_tag()` function
  - 24 new property-based fuzzer tests (`test_type_tags_fuzzer.py`)
  - All 1020 self-hosting tests pass
- Expert Review Cleanup (PR #163):
  - Deleted `resolve_lookups()` dead code from subst_mu.py (~47 lines)
  - Updated "Phase 3" comments to "BOOTSTRAP" in eval_seed.py
  - DEBT_THRESHOLD: 15 → 14 (ratchet tightened after dead code removal)
  - All 1038 tests pass, 53 fuzzer tests pass
- Phase 6d: Iterative Validation + Code Cleanup (PR #165):
  - `_check_empty_var_names()` converted to iterative with explicit stack
  - Reclassified `bindings_to_dict`/`dict_to_bindings` as boundary scaffolding
  - Deleted `lookup_binding()` dead code from subst_mu.py (~25 lines)
  - Removed unused `bindings` parameter from `run_subst_projections()`
  - Removed unused `from typing import Any` imports from match_mu.py, subst_mu.py
  - Removed deprecated `_seen` parameter from `normalize_for_match()`, `denormalize_from_match()`
  - Added 18 tests for empty var name rejection (parity between match_mu and subst_mu)
  - DEBT_THRESHOLD: 14 → 11 (ratchet tightened: 8 tracked + 3 AST_OK)
  - All 1036 tests pass, all 6 agents APPROVE for Phase 7 readiness
- Kernel Loop Fuzzer Tests (pre-Phase 7):
  - Added 11 property-based tests for apply_mu, step_mu, run_mu
  - TestApplyMuDeterminism: 3 tests (determinism, var pattern, literal match)
  - TestApplyMuParity: 1 test (apply_mu == apply_projection)
  - TestStepMuDeterminism: 3 tests (determinism, empty projections, stall idempotent)
  - TestStepMuParity: 2 tests (step_mu == step, first-match-wins)
  - TestRunMuDeterminism: 2 tests (determinism, immediate stall)
  - 3000+ random examples stress-test kernel loop stability
  - Closes fuzzer gap identified by agents before Phase 7
- rcx_engine.v1.json Test Coverage (2026-02-03):
  - Created `tests/fixtures/rcx_engine_vectors.json` - 7 test vectors
  - Created `tests/test_rcx_engine_parity.py` - 15 tests
  - All 6 engine projections now tested (grounding agent finding addressed)
  - Note: rcx_engine has `status: design_only` - projections tested but not in production
- 9-Agent Rigorous Tooling Hardening (2026-02-08, PR #219):
  - 5 fuzzer test files from agent findings #1017-#1021 (88 property-based tests)
  - `--rigorous` fixed: runs all 9 agents (was 6), skeptic always runs
  - Reasoning validator fixed: parses `### CHECKED` markdown format from agents
  - `==` → `mu_equal()` in fuzzer tests, shared strategies extracted to `tests/strategies.py`
  - Iteration guards in match_mu.py (bindings_to_dict, denormalize_from_match)
  - INFRA_CEILING: 37 → 38, test count: 2,846
- B-Structural Non-Linear Match (2026-02-09):
  - `match_mu()` now uses match.v2 + bridge projections directly via `projection_runner`
  - Non-linear pattern conflict detection: `apply_mu({a:{var:x}, b:{var:x}}, {a:1, b:2})` → NO_MATCH
  - `projection_runner.make_projection_runner()` extended with `terminal_field` parameter for v2 support
  - `load_match_with_bridge_projections()` loads and caches 13 combined projections (8 match.v2 + 5 bridge)
  - Fail-closed guard: `step_mu()`/`run_mu()` reject non-linear patterns with ValueError
  - Semantic split documented: `apply_mu`/`match_mu` (bridge-aware) vs `step_mu`/`run_mu` (core-only, fail-closed)
  - 18 structural invariant tests in `tests/structural/test_match_bridge_invariants.py`
  - Non-linear Hypothesis strategies + 2 fuzzer tests in `test_apply_mu_fuzzer.py`
  - All deadlines at original 5000ms (no inflation needed)
- Gate 5 Meta-Circular Parity CLOSED (2026-02-09):
  - 56 exit criteria tests pass: 9 gate5 parity + 17 execution path + 30 JS parity
  - Structural execution is default for recurrence/exhaustion on both substrates
  - Bootstrap execution is explicit fallback-only (requires `execution_mode="bootstrap", allow_bootstrap_fallback=True`)
  - Cross-substrate parity intact: all 47 core projections run identically on Python and JS
  - B-structural match_mu provides non-linear pattern support via match.v2 + bridge
  - Gates 1-5 ALL COMPLETE — hemisphere implementation unblocked
- Mu Hemispheres v0 Core (2026-02-09):
  - `mu/programs/hemispheres.v1.json`: 12 projections (init, 5 classify, 5 add, unwrap)
  - Entry schema locked: `{state, closure_flag, origin}` per hemisphere
  - Three automatic routes: null→r_null, closure→r_a, default→lobes
  - Cross-substrate parity: Python + JS produce identical results
  - 27 Python tests, 7 parity tests, 6 parity vectors
  - Semantic answer: routing decisions ARE expressible as pure Mu projections
- Hemisphere Adversarial Hardening (2026-02-10):
  - JS seed verification parity: all 7 seeds verified at load (SHA256, structure, projection IDs)
  - Python `validate_projection_ids` enforces exact ordered equality (first-match-wins security)
  - JS cycle detection activated, handler duplication factored
  - 63 hemisphere adversarial tests added
  - Deprecated `get_seeds_dir` removed

---

## Boundary Question (Answered)

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

**Answer:** The Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM).
See `docs/archive/MinimalNativeExecutionPrimitive.v0.md` for invariants and non-goals.

---

## NOW (empty by design; only populated if an invariant is broken)

*(No active items - all invariants intact)*

---

## NEXT (short, bounded follow-ups)

No active items. Promote from VECTOR when ready.

**Gate Snapshot (Canonical mirror of STATUS.md):**
- Gate 3: COMPLETE (2026-02-07)
- Gate 4: COMPLETE (2026-02-07 structural cutover)
- Gate 5: COMPLETE (2026-02-09 meta-circular parity verified)
  - 56 exit criteria tests: 9 gate5 parity + 17 execution path + 30 JS parity
  - Structural execution default; bootstrap explicit fallback only
  - Cross-substrate parity intact (Python + JS, all 47 core projections)
  - `run_algorithm_meta_circular()` defaults to `step_kernel_mu(..., kernel_mode="bridge", validation_mode="algorithm_runtime")` on production path.

Current Recurrence Layer: META_CIRCULAR
Current Exhaustion Layer: META_CIRCULAR

## VECTOR (design-only; semantics locked, no implementation allowed)


**Active designs:**
- Content-Addressed Mu (`roadmap/ContentAddressedMu.md`) - Every Mu value carries a content hash; equality becomes O(1). **Levels 0-2 IMPLEMENTED** (L0: boundary hashing, L1: mu_equal eliminated 5→4, L2: frozen hashes — state dropped from _seen, ~77% memory savings). **Level 3 (Trie) DEFERRED** — analysis shows 5x slower for production traces (<50 steps), break-even at ~100 steps. Revisit if traces routinely exceed 100 steps.
- Debt Categories v0 (`docs/core/DebtCategories.v0.md`) - Scaffolding vs semantic debt distinction
- Projection Indexing - Preprocess projections into structural trie/decision-tree for O(log N) matching instead of O(N) linear scan. Index is Mu data (structural). **Promotion criteria:** Profile real workloads first; if projection matching is >50% of runtime, promote to NEXT.
- Hemisphere Metabolization Contract (`roadmap/MuHemispheresDesign.md` § "FUTURE_TARGET: Hemisphere Metabolization Contract") - Sink re-expression cycle: sink → (r_inf | r_null) metabolization → (lobes | r_a) storage → residual → sink. Stall recovery: lobes-first, then sink. 6 projection IDs designed (pattern/body sketches). Engine exception policy dependency documented (Option A active, Option B deferred). **Promotion criteria (all required for VECTOR → NEXT):**
  - Re-expression trigger model decided (automatic + manual/debug, per founder directive) ✓ designed
  - At least 4 metabolization projection specs drafted with pattern/body ✓ 6 designed
  - Extended truth-table coverage criteria defined (≥8 metabolization transitions)
  - Engine exception policy Option B (synthesized routable terminal → sink) designed with sink-safety invariants
  - Explicit VECTOR → NEXT promotion in this file with rationale before any implementation

**EngineNew gap contracts** (locked by `tests/test_engine_cycle_mapping.py::TestGapRegistry`):
- GAP-04-FIX: Explicit Fix projection (Rule 0.6). No Fix seed exists; fix semantics implicit in engine re-application. **Promotion criteria:** (1) stall-recovery test showing implicit fix fails, (2) explicit Fix seed draft with pattern/body, (3) VECTOR → NEXT promotion with rationale. **Blocks:** structural completeness of EngineNew 10-step cycle.
- GAP-10-LOOP: Structural iteration control. Host-driven while loop in run_engine_pipeline; no loop-as-projection exists. **Promotion criteria:** (1) Boot1 recursive kernel design, (2) loop-as-projection seed draft, (3) evidence host loop can be replaced without breaking engine_result contract, (4) VECTOR → NEXT promotion with rationale. **Blocks:** full meta-circular engine (all 10 steps structural).

**Reference:**
- Corpus Status Registry (`docs/corpus_registry.csv`) - 18-artifact classification with taxonomy labels, confidence scores, and evidence refs. Ontology-to-runtime mapping reference for VECTOR design work.

**Promoted to NEXT:**
- ~~Mu Hemispheres v0~~ (`roadmap/MuHemispheresDesign.md`) - **PROMOTED TO NEXT** (2026-02-09, Gate 5 blocker resolved)

**Completed (moved to Ra):**
- ~~Operator Exhaustion v0~~ (`docs/core/OperatorExhaustion.v0.md`) - **MOVED TO Ra** (IMPLEMENTED 2026-02-02)
  - Step 6 complete: 11 projections in `mu/closures/exhaustion.v1.json`
  - 27 tests (17 parity + 10 fuzzer), cross-substrate parity verified

**Historical promotion (completed):**
- Meta-Circular Kernel v0 (`docs/core/MetaCircularKernel.v0.md`) - promoted 2026-01-27, implemented and archived in `Ra`

**Completed designs (now in Ra):**
- RCX Kernel v0 (`docs/core/RCXKernel.v0.md`)
- Structural Purity v0 (`docs/core/StructuralPurity.v0.md`)
- Self-Hosting v0 (`docs/core/SelfHosting.v0.md`)
- EVAL_SEED v0 (`docs/core/EVAL_SEED.v0.md`)
- EngineNews Structural v0 (`docs/core/EngineNewsStructural.v0.md`) - Step 5 closure detection
- Operator Exhaustion v0 (`docs/core/OperatorExhaustion.v0.md`) - Step 6 operator freeze
- Second Independent Encounter (`docs/execution/IndependentEncounter.v0.md`)
- Enginenews Spec Mapping (`docs/execution/EnginenewsSpecMapping.v0.md`)
- Closure Evidence Events (`docs/execution/ClosureEvidence.v0.md`)
- Rule-as-Motif (`docs/execution/RuleAsMotif.v0.md`)

**Archived (superseded):**
- Bytecode VM v0/v1 → `docs/archive/bytecode/`

---

## SINK (ideas parked; may not advance without explicit promotion decision)

- Multi-value/concurrent execution
- Performance-first optimizations
- ~~Full VM bootstrap / meta-circular execution~~ → Promoted to VECTOR #14 (RCX Kernel v0)
- Projection caching optimization (post-Phase 8) - cache normalized projections for repeated use; use content-based hash, NOT id(). From withdrawn KernelSeedRealignment.v0.md.
