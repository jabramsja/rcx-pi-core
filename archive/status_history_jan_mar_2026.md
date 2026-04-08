# STATUS.md Historical Archive (January–March 2026)

Archived 2026-04-07 during STATUS.md consolidation.
These sections were removed from STATUS.md because all work items are COMPLETE.
The current truth lives in code, tests, and git history.

---

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
- [x] Consolidate runner pattern → retired Wave 3F (match_mu uses staged `stage0_vm_step`; classify/subst use `stage0_vm_run_bounded`)
- [x] Move test-only helpers out of match_mu.py - CLOSED (expert review found NO test-only code, all is production)

**Structural-proof agent:**
- [x] L1 claims PROVEN (match_mu, subst_mu, classify use projections)
- [x] L2 design verified structurally sound (linked-list cursor, context passthrough, meta-circularity confirmed 2026-01-27)

**Additional tests (2026-01-28):**
- [x] `tests/structural/test_projection_loader.py` - Factory loader tests (13 tests)
- [x] Projection runner tests — retired Wave 3F (replaced by `tests/helpers/test_projection_stepper.py`)
- [x] `tests/fuzz/test_kernel_loop_fuzzer.py` - L2 kernel iteration fuzz tests (16 tests)
- [x] `tests/fuzz/test_context_passthrough_fuzzer.py` - Context preservation fuzz tests (12 tests)
- [x] `tests/structural/test_step_mu_kernel_integration.py` - Kernel integration tests (30 tests)

**Security fix (2026-01-28 - Adversary review):**
- [x] Implemented `KERNEL_RESERVED_FIELDS` boundary validation in `step_mu.py`
- [x] `validate_no_kernel_reserved_fields()` rejects domain inputs with kernel fields
- [x] Fields protected: `_mode`, `_phase`, `_input`, `_remaining`, `_match_ctx`, `_subst_ctx`, `_kernel_ctx`, `_status`, `_result`, `_stall`, `_step`, `_projs`
- [x] Deep validation: recursive check prevents nested smuggling attacks (e.g., `{"outer": {"_mode": "done"}}`)
- [x] Fail closed: Depth limit (100) raises ValueError, doesn't silently trust remaining structure

---

## L3 Substrate Portability Progress (2026-01-30)

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

## Legacy Records (February–March 2026)

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
- **Path 1: match_mu direct** (2026-02-09) — `match_mu()` loads match.v2 + bridge projections via staged `stage0_vm_step` dispatch (originally `projection_runner`, retired Wave 3F). Provides non-linear pattern conflict detection for `apply_mu()` without kernel overhead.
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
