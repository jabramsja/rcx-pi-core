# Changelog

All notable changes to RCX are documented in this file.

## 2026-03-26

### Pipeline Continuation Hardening

- `commit_executor.py` now persists a bounded post-commit continuation record keyed to the exact handoff, target branch, and local commit, so reruns after step-11+ failures continue honestly without a separate resume flag
- Final merge clearance now waits for a current-head `chatgpt-codex-connector` review before evaluating `reviewDecision` and unresolved review threads
- `meta_bridge_supervisor.py` now rejects stderr-only authoritative envelopes during recovery parsing
- `mu/tools/executors/executor_dispatch.py` now also acts as the thin modular entrypoint for `phase-a`, `phase-b`, `pre-commit-supervisor`, `commit`, and `post-merge-supervisor`
- Control-plane packets and TASKS tracker truth updated to reflect bounded continuation, the modular operator surface, and the remaining simple-route pipeline smoke target
- **L4_ENABLER** wave targeting G8. No runtime/substrate or host-semantics delta.

## 2026-03-19

### Wave W6A: Stage0 VM Trusted Path Optimization

- **Two-function trusted path pattern:** `_stage0_vm_step_trusted` (dispatch body) + `stage0_vm_step` (validate + delegate) in Python; mirrored in JS with `_stage0VmStepTrusted` export
- **Parameterized bounded helper:** `_run_bounded_impl` eliminates loop duplication across match/subst/step dispatch
- **Source-lock gate tests:** 12 tests in `tests/l4_gates/test_stage0_vm_trusted_path_gate.py` — exhaustive grep for trusted function call sites
- **Bundle validation contract:** Callers constructing custom vmConfig MUST call `validateBundle()` before passing to `_stepKernelWithVM`
- Host-semantics delta: 0 (refactor-only, no new host capabilities)
- Total inventory: 309 -> 313 (+4: 2 Python trusted functions, 2 JS trusted path helpers)
- **L4_STRUCTURAL** wave targeting G8. PR #635 merged. Bridge: 2 rounds GO.

## 2026-03-15

### Wave 1: Internal Canonical Step Record

- Retired `_stepKernelCoreNonMeta` from JS kernel.js (deleted)
- `runAlgorithmWithBridge` migrated to `_stepKernelCore` — uses `canonical.output` (already denormalized), removed redundant `denormalize()` call
- `stepKernel(returnMeta=false)` now compatibility shim over `_stepKernelCore` — re-normalizes output for legacy `denormalize()` round-trip, preserves `stalled:false` on max-steps (NB4 public debt deferred)
- NB4/NB7 contained internally: canonical `_stepKernelCore` has correct stall semantics and terminal extraction. Public non-meta adapter preserves legacy behavior.
- Source-lock tests updated for new pipeline.js structure
- **L4_STRUCTURAL** wave. Founder canonical machine direction. Bridge: 1 round GO.

### JS Kernel Cleanup (NB10)

- `_assertVmMatchResult()` added to `_stepKernelWithVM` in kernel.js — fail-closed on undefined `.root` from VM match result (parity with Python KeyError). `null` accepted (valid Mu).
- NB4 (max-steps stall) and NB7 (terminal extraction) documented as DESIGN-GATED — attempted fixes broke 27 parity tests due to caller dependency on current non-meta semantics.
- Total inventory: 310 -> 311 (+1 JS assertion function).
- **L4_STRUCTURAL** wave. Bridge: 2 rounds.

### Agent Execution Capability

- Updated 5 agent prompts (adversary, verifier, expert, structural-proof, grounding) with "Execution Verification" sections
- Added `Bash` to `tools` in all prompt frontmatter
- Updated SDK orchestrator (`run_review.py`) + all individual runners + `agent_runner_common.py`: all agents now consistently have `Bash` tool (infrastructure already granted it; declarations now match reality). Execution behavior guided by prompt instructions, not tool restrictions
- Updated all individual runners and `agent_runner_common.py` defaults
- Regenerated all 9 native subagents via `sync_native_agents.sh`
- Added "Execution-Aware Review" section to `AgentRunbook.v0.md`
- **L4_ENABLER** wave. Agents can now run targeted repro commands during review.

### S1-C: Kernel + Bridge Execution via Stage0 VM

- **Compiled:** kernel.v1 (7 projections) and bootstrap_structural.v1 (5 projections) into Stage0 bundles
- **Wired:** `_step_kernel_with_vm()` now executes ALL 33 projections via Stage0 VM
- **Eliminated:** `_apply_projection_trusted` removed from step_kernel_mu path
- **JS parity:** kernel.js updated with same all-VM execution
- Total inventory: 308 -> 310 (+2 new bundle loaders)
- **L4_STRUCTURAL** wave targeting G8.

### S1-B: VM Cutover Flip (Founder GO)

- **Python:** `_STAGE0_VM_CUTOVER = True`, `_STAGE0_SHADOW_ENABLED = False` in step_mu.py
- **JavaScript:** `_STAGE0_VM_CUTOVER = true`, `_STAGE0_SHADOW_ENABLED = false` in kernel.js
- VM path is now primary for match.v2/subst.v2 in step_kernel_mu; host path (_step_trusted) still used by engine_pipeline and projection_runner
- Shadow mode disabled (dead code under cutover=True, retained for rollback)
- Updated: test_stage0_vm_cutover.py source-lock, test_l4_current_state_truth.py flag assertions, test_performance_canary_gate.py hash_stall monkeypatch, stage0_vm.js header
- P7-d deferred items #1-6 all RESOLVED
- **L4_STRUCTURAL** wave targeting G8. Founder GO 2026-03-15.

### N15: Compiler/Loader Provenance Verification

- `_verify_bundle_provenance()` in `step_mu.py`: verifies compiled bundle source_digest against SEED_CHECKSUMS registry at load time
- `verifyBundleProvenance()` in `main.js`: JS parity implementation
- 5 gate tests in `test_stage0_vm_cutover.py::TestBundleProvenance` (pass, reject wrong digest, missing, unknown)
- Theater allowlist: 4 new entries for no-raise provenance tests
- Total inventory: 306 → 308 (+2 provenance functions), INFRA_CEILING: 123 → 125
- N2/N15 deferred items marked RESOLVED
- **L4_STRUCTURAL** wave targeting G8. Python + JS parity. Fail-closed on mismatch.

### MT2: isinstance Marker-Truth

- 29 unmarked `isinstance` calls in `step_mu.py` annotated with `# AST_OK:infra — type guard`
- INFRA_CEILING/INFRA_CURRENT: 94 → 123 in STATUS.md
- `test_debt_enforcement.py` infra count assertion: 94 → 123
- D4 wave4b (step_mu.py isinstance) + D2 wave4c (projection_runner.py isinstance) marked RESOLVED
- **L4_STRUCTURAL** (annotation-only, FOUNDER_OVERRIDE). No behavioral changes. No phase/debt change.

### S1-A VM Cutover Evidence Package

- **D1:** Performance profiling suite (`test_stage0_vm_performance.py`) — 9 Tier 1 diagnostic + 5 Tier 2 integration workloads (including cutover-mode benchmarks)
- **D2:** Cutover=True path tests (`test_stage0_vm_cutover.py`) — 15 new tests: 10 branch-level (TestCutoverTruePath) + 5 integration-level (TestCutoverIntegration) with no-monolithic-host-path negative control
- **D3:** JS VM bridge parity (`test_js_vm_bridge_parity.py`) — 8 cross-substrate tests (match.v2 + subst.v2 compiled bundle parity)
- **D4:** CONDITIONAL GO memo (`reports/l4_wave_indicators/s1a-vm-evidence-go-nogo.md`) — founder-grade evidence for cutover decision
- Theater allowlist: 5 new entries for observational performance tests
- **L4_ENABLER** wave targeting G8 (Irreducible Primitive Consensus). No runtime changes. No phase/debt change.

## 2026-03-05

### Docs Truth Sync (PR #480)

- README.md: test counts (~5,500+ across 260+), CRITICAL_TEST_FILES (44), projections (143 across 17 seeds), seed table (+5 missing seeds), metabolization status → COMPLETE
- STATUS.md: Python test count (~5,556), Tier 2/3 counts corrected, green gate selection semantics documented, tests/structural (45) and tests/tools (27) counts, CRITICAL_TEST_FILES (44)
- L4ExitChecklist.v0.md: G1 pass condition scoped to Python canonical substrate, G1 proof command fixed, muHash JS label discrepancy documented
- Boot1LoopContract.v0.md: status → COMPLETE (shadow-merge implemented 2026-02-19)
- HemisphereExecutionChecklist.v0.md: KERNEL_RESERVED_FIELDS 24→25 (_boundary_request)
- MAINTENANCE wave. No phase/debt change. Merge commit `3d19180`.

### W3-CRASH Runtime Crash Guards + Collector Hardening (PR #477)

- F-10: `denormalize_from_match` typed-dict and legacy-dict loops now have 3-layer guards (structural, kv shape, kv_tail shape); malformed kv nodes skipped instead of crashing (JS parity)
- F-11: `_match_inner` and `_stage0_match` return NO_MATCH for empty var-name `{"var": ""}` instead of raising ValueError
- F-12: `bindings_to_dict` rejects non-string binding names with diagnostic ValueError (type + repr)
- F-13: `_iter_normalized_dict_pairs` cap raised from hardcoded 100 to `MAX_MU_WIDTH` (1000); JS `iterNormalizedDictPairs` updated to match
- Enforcer: `net_host_semantic_delta` aligned to ratchet-derived delta (runs `check_host_semantics_ratchet.py --json`)
- Collector hardening (#1-6): zero-division guard on speedup ratio, `subprocess.TimeoutExpired` fail-closed on 3 probe functions, `get_changed_files` raises `CollectorError` on git failure, dead code removed (`RUNTIME_DIRS`, `COMMENT_ONLY_PATTERNS`, `get_diff_text`, `is_comment_line`), top-level `import os` replaces inline `__import__("os")`, docstring corrected (timing metrics are environment-dependent, not deterministic)
- 25 gate tests in `test_w3_crash_guards_gate.py` + 6 collector regression tests in `test_l4_governance_contract.py`
- Merge commit `735dfea`. No phase/debt change.

## 2026-03-04

### W2 Enforcer/Theater Hardening (PRs #472, #473)

- PR #472: `is_comment_only_runtime_diff` now accepts `old_ref` parameter (was hardcoded `HEAD`, broke range-based enforcement)
- PR #472: founder override bypass requires explicit wave binding (`override_wave_bound=True`); unbound stale overrides fail-closed
- PR #472: `L4ExecutionContract.v2.md` updated with condition 6 (wave-binding requirement)
- PR #472: `check_test_theater_js.sh` default target changed from single file to `mu/host/js/` directory scan with THEATER_OK suppression
- PR #473: boundary gate malformed-seed tests relocated temp files from `mu/utilities/` to `os.tmpdir()` (eliminates parallel race with `test_seed_counts.py`)
- PR #473: `_derive_old_ref_from_range` normalizes empty endpoints to HEAD (`rev...` → `rev...HEAD`, `..rev` → `HEAD..rev`)
- PR #473: 3 regression tests for empty-endpoint normalization

## 2026-03-03

### W1-GATE: Gate Blindness Remediation (PR #468)

- Green gate now includes parity canary (`test_parity_canary`) for cross-substrate coverage
- JS linters (`contraband_js.sh`, `ast_police_js.sh`) scan full `mu/host/js/` directory by default
- `pytest.fail` replaces `pytest.skip` for missing parity vectors (fail-closed)
- `new Date()` removed from `pipeline.js` (determinism fix)
- Governance fix: root canonical files counted as governed (coverage 28%→31%)
- `FOUNDER_SESSION_BOOTSTRAP.md` tracked and registered

### W2 Docs Truth Alignment (unbound patch)

- NorthStarSemantics.v0.md §B.1: corrected non-linear binding hash from `mu_hash_control_cached` to `mu_hash_cached` (Wave 25 revert was undocumented)
- STATUS.md: JS debt count corrected 19→16 (dashboard grep-token inflation documented)
- STATUS.md: AST_OK:infra references corrected 42→65, ceiling 64→65
- STATUS.md: all LOC/test counts updated (Py ~6250 LOC / ~5458 tests, JS ~4200 core + ~470 tests)
- NorthStarSemantics.v0.md: removed hardcoded "37 tests" gate count (actual is 43; now non-numeric)
- 5 runtime-file findings (F-06, F-31, F-32, F-33, F-34) deferred as POLICY_BOUND (require L4_STRUCTURAL wave)

## 2026-02-17

### Denormalization KeyError Hardening (PR #315)

- Fixed legacy linked-list denormalization paths in `match_mu.py` that used `current["tail"]` (crashes with KeyError on malformed inner nodes missing "tail" key)
- Changed to `.get("tail")` matching the type-tagged paths and JS behavior (2 lines, lines 699 and 726)
- Added 2 regression tests in `test_normalization_roundtrip.py`
- Red-team finding; classify_mu already protects the dict path, but the list path was directly exploitable

### Canonical Docs Drift Sync

- STATUS.md: INFRA_CURRENT 45→42 (reduced by PR #314 archival work)
- STATUS.md: Infra ceiling line corrected (was "38 (current 38)", now "48 (current 42)")
- STATUS.md + README.md: Test count 3,235→3,690
- README.md: Test files 90+→180+
- CHANGELOG.md: Added missing PR #315 entry

## 2026-02-16

### Roadmap Relocation (Visibility + Governance Sync)

- Moved `ROADMAP.md` from `roadmap/ROADMAP.md` to repo root `ROADMAP.md`
- Moved roadmap spec folder from `roadmap/` to root `roadmap/`
- Updated roadmap links across canonical docs (`STATUS.md`, `TASKS.md`, `README.md`) and active specs/tests
- Updated doc governance config:
  - `ROADMAP.md` added to root canonical docs
  - roadmap special-folder path changed to `roadmap/`
  - `docs_registered_subfolders` no longer lists `roadmap`
- Updated pre-commit docs-change detection to include `roadmap/` and `ROADMAP.md`
- Fixed stale archived bytecode doc path references (`archive/archive/docs/bytecode` → `archive/docs/bytecode`)

## 2026-02-15

### Round 24D: Convergence Execution (tools/scripts/tests -> mu/)

- **Physical move**: `tools/`, `scripts/`, `tests/` moved under `mu/` via `git mv` (~340 files)
- **Root symlinks**: `tools -> mu/tools`, `scripts -> mu/scripts`, `tests -> mu/tests` for backward compat (removal planned for 24E)
- **Shell scripts**: 8 scripts converted from `dirname`-based repo root to `git rev-parse --show-toplevel`
- **Python paths**: `.resolve()` removed from 25 REPO_ROOT computations (prevents symlink resolution from breaking parent chains)
- **Git-path configs updated**: `enforce_tracker_sync.sh`, `pre-commit-doc-check`, `docs_registry.json`, `run_review.py`, `run_ci_review.py` — all now use `mu/` prefix for git-reported paths
- **Root layout guard**: Made index-aware (reads staging area, not just HEAD); `tests`/`tools`/`scripts` removed from ALLOWED_ROOT_DIRS
- **Symlink `..` traversal**: Fixed `os.path.join` + `..` patterns that break with symlinks (normalize before use)
- **Tracker sync exclusions**: `mu/tools/`, `mu/scripts/`, `mu/tests/` excluded from core-change detection
- No phase/debt/runtime change

## 2026-02-14

### Documentation Drift Sync (Governance + Schemas)

- Synced Boot1 prerequisite status in governance docs:
  - `_run_engine` reservation (P2) marked resolved (Round 20B)
  - `_tail_call` reservation (P3) marked resolved (Round 20C)
- Updated schema-doc path references to canonical `mu/docs/schemas/*` locations:
  - CLI schema contract examples
  - CLI quickstart schema links
  - world_trace schema markdown/json `schema_doc` alignment
- Corrected stale `rcx_engine.v1.json` projection count in root README (7 → 11)
- Updated STATUS proof block to use `seed_police` authoritative totals (15 seeds, 102 projection IDs, 0 collisions)
- Regenerated `mu/docs/README.md` index to remove stale listing drift

## 2026-02-12

### JS Engine-Hemisphere Parity (L3 Mandatory)

- **4 core functions ported to JS** — `runEnginePipeline()`, `hashTraceForRecurrence()`, `runHemisphereRouting()`, `runEngineWithRouting()` mirror Python implementations in `eval_step.js`
- **rcx_engine.v1.json + recurrence.v2.json loaded in JS** — 9 seeds now verified at startup (was 8); `seedProjectionMap` for boundary `run_algorithm` operations
- **4 JSON API actions added** — `run_engine_pipeline`, `hash_trace`, `run_hemisphere_routing`, `run_engine_with_routing` for cross-substrate testing
- **6 cross-substrate parity tests** — 3 fast (hash_trace, overcap, routing validation) + 3 slow (engine pipeline, hemisphere routing, full pipeline E2E); 36 total parity tests pass
- **Pre-existing parity gap fixed** — `_state_hash` and `_check_hash` added to JS `ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS` (recurrence.v2 fields present in Python but missing from JS)
- **JS debt 13→15** — `runAlgorithmWithBridge` + `runEnginePipeline` added to `@host_iteration` tracking
- **Constants and helpers** — `isTerminalShape()`, `isEngineTerminal()`, `runSubAlgorithm()`, `setsEqual()`, `defaultHemispheres()`, hemisphere/terminal key sets
- **Inline JS tests** — `isEngineTerminal`, `isTerminalShape`, `hashTraceForRecurrence` (simple, cycle, overcap), `defaultHemispheres`/`setsEqual`

## 2026-02-11

### Engine → Hemisphere Integration

- **`run_engine_with_routing()`** — Chains `run_engine_pipeline()` → `run_hemisphere_routing()` with fail-closed input/output validation
- **`hash_trace_for_recurrence` cycle guard** — `id(current)` visited set + 10000 iteration cap, `raise ValueError` (fail-closed)
- **`_default_hemispheres()`** — Canonical empty hemisphere state, single source of truth
- **10 integration tests** — 8 fast (wiring, input/output validation, cycle guard, default consistency) + 2 slow (manual chain equivalence, Paxos closure → r_a E2E proof)
- **Paxos livelock → closure → r_a** proven end-to-end through the full engine + hemisphere pipeline

### CI Green Gate Optimization (28 min → 2 min)

- **Hypothesis fuzzers auto-marked** — `pytest_collection_modifyitems` in `conftest.py` detects `item.obj.is_hypothesis_test` and applies `fuzzer` marker (452 tests deselected from green gate)
- **Slow tests excluded from green gate** — 168 meta-circular, hemisphere, paxos e2e, and engine pipeline tests marked `@pytest.mark.slow`
- **Green gate runs ~2,500 core tests in ~50s on CI** — Total wall time ~2 min (down from ~28 min)
- **4-tier test structure:** audit_fast (local), audit_all (pre-push), CI green gate (push/PR), CI nightly (ci_full)
- **Nightly branch** — `HYPOTHESIS_PROFILE=ci_full` runs everything including fuzzers and slow tests
- **pytest-timeout added to test extras** — `pyproject.toml` now declares `pytest-timeout` for `--timeout=300` in nightly/audit_all
- **Fragile grounding test fixed** — `test_green_gate_check_order` used `}` boundary detection that broke on `${VAR:-}` parameter expansions

### Static Speed Enforcer

- **Created `tools/check_test_speed.sh`** — grep-based static analysis catches test files importing slow kernel functions without `@pytest.mark.slow`
- **Pre-commit integration** — `tools/pre-commit-doc-check` section 4b enforces speed marking on staged test files (~instant)
- **7 unmarked test files fixed** — `test_structural_trace`, `test_self_hosting_v0`, `test_gate4_runtime_hardening`, `test_bootstrap_primitives`, `test_recurrence_parity`, `test_execution_path_verification`, `test_match_bridge_invariants`
- **Slow function set** — `run_mu`, `run_mu_structural`, `run_algorithm_meta_circular`, `run_engine_pipeline`, `run_hemisphere_routing`
- **Whitelist** — `# SPEED_OK: reason` for files that import but don't call slow functions

## 2026-02-10

### Content-Addressed Mu Level 1 IMPLEMENTED: mu_equal Eliminated (5→4 Bootstrap Primitives)

- **`mu_hash_cached()` added to `mu_type.py`** — SHA-256 with canonical-JSON-keyed cache for O(1) amortized equality
- **`mu_equal` eliminated as bootstrap primitive** — All 8 production call sites replaced with `mu_hash_cached()`:
  - `eval_seed.py`: 2 binding conflict detection sites
  - `step_mu.py`: 5 stall detection sites
  - `projection_runner.py`: 1 stall detection site
- **JS parity: `muHashCached()` added to `eval_step.js`** — Map-based cache, 6 JS call sites updated, `muEqual()` delegates to hash comparison
- **`mu_equal` retained as convenience wrapper** — Delegates to `mu_hash_cached(a) == mu_hash_cached(b)`. Marked DEMOTED PRIMITIVE (kept for ~30 test call sites + JS parity).
- **Bootstrap primitive count: 5 → 4** — eval_step, max_steps, stack_guard, projection_loader
- **Paxos end-to-end pipeline test created** — `tests/test_paxos_end_to_end.py` (6 tests): paxos livelock → trace → hash → recurrence.v2 → healer → consensus
- **Design docs updated**: BootstrapPrimitives.v0.md, ContentAddressedMu.md (Level 1 IMPLEMENTED), STATUS.md
- All 1991+ tests pass, JS tests pass, L3 parity intact

### Content-Addressed Mu Design + Recurrence v2 Hash Acceleration

- **Created `roadmap/ContentAddressedMu.md`** — Design doc for Content-Addressed Mu values (hash-identity as substrate property)
- **Key insight: mu_equal elimination (5→4 bootstrap primitives)** — With content-addressing, `mu_equal` is subsumed by non-linear pattern matching on hash strings. `mu_hash` moves from runtime infrastructure to boundary scaffolding (like JSON parsing)
- **Created `mu/closures/recurrence.v2.json`** — 9 hash-accelerated projections for closure detection
  - Pre-computes SHA-256 hashes at boundary; compares 64-char hash strings (O(1)) instead of deep structural match (O(depth))
  - Reduces Paxos 15-step trace from ~6,300 kernel steps to ~420 (theoretical estimate)
- **Created `mu/docs/core/recurrence_v2_design.md`** — Design spec for hash-accelerated closure detection
- **Converted `hash_trace_for_recurrence()` to iterative** — Avoids Python recursion limit on long traces (max_steps=10,000 > Python limit ~1,000)
- **Updated `mu/programs/paxos_demo.v1.json`** — Dependency changed from recurrence.v1 to recurrence.v2
- **Added Content-Addressed Mu to TASKS.md VECTOR** — Promotion criteria: Level 1 promotes to NEXT when recurrence.v2 production tests validate Level 0
- **INFRA_CURRENT: 37→38** — New AST_OK:infra marker for iterative hash_trace_for_recurrence
- Agent review: 3 iterative cycles (8, 12, 16 turns). Final: verifier APPROVE, structural-proof PROVEN

### Seed Integrity Verification Parity + Adversarial Hardening

- **JS substrate now verifies all 7 seeds at load time** — SHA256 checksum, structure validation, projection ID ordering
- Closes L3 parity gap where Python verified seeds but JS loaded blindly
- Python `validate_projection_ids` now enforces exact ordered equality (security-critical for first-match-wins routing)
- JS `classifyLegacyLinkedList` cycle detection activated
- Handler duplication factored in JS substrate
- Deprecated `get_seeds_dir` removed from Python
- 63 hemisphere adversarial tests added

## 2026-02-09

### Mu Hemispheres v0: Native Structural Routing

- **Created `mu/programs/hemispheres.v1.json`** — 8 projections for hemisphere routing (North Star #7)
- Routing state machine: init → classify → add → unwrap (4 kernel steps per decision)
- Three automatic routes: null→r_null, closure→r_a, default→lobes
- Entry schema: `{state: <value>, closure_flag: <bool>, origin: "engine"}`
- Linear-only patterns — runs through core kernel, no bridge needed
- All intermediate state uses `hemi_*` prefix (no underscore fields, passes domain validation)
- **Cross-substrate parity verified**: Python and JS produce identical results
- 27 Python tests in `tests/test_hemisphere_routing.py`
- 7 parity tests in `tests/structural/test_hemisphere_parity.py`
- 6 parity vectors in `tests/fixtures/hemisphere_vectors.json`
- JS JSON API: `run_hemisphere` action in `mu/host/js/eval_step.js`
- Seed registered in `seed_integrity.py` (checksum, projection IDs, location)
- **Answers semantic question**: Yes, routing decisions CAN be expressed purely as Mu projections

### Gate 5 CLOSED: Meta-Circular Parity Verified

- **Gates 1-5 ALL COMPLETE** — hemisphere implementation unblocked
- 56 exit criteria tests pass: 9 gate5 parity + 17 execution path + 30 JS parity
- Structural execution is default; bootstrap is explicit fallback only
- Cross-substrate parity intact (Python + JS, all 47 core projections)
- Updated consistency tests to handle all-gates-complete state

### B-Structural Non-Linear Match

- `match_mu()` now uses match.v2 + bridge projections directly via `projection_runner`
- Non-linear pattern conflict detection: `apply_mu({a:{var:x}, b:{var:x}}, {a:1, b:2})` → NO_MATCH
- `projection_runner.make_projection_runner()` extended with `terminal_field` parameter
- `load_match_with_bridge_projections()` loads and caches 13 combined projections (8 match.v2 + 5 bridge)
- Fail-closed guard: `step_mu()`/`run_mu()` reject non-linear patterns with ValueError
- 18 structural invariant tests + non-linear Hypothesis strategies

### 9-Agent Rigorous Tooling Hardening (PR #219)

- `--rigorous` now overrides depth to "all" (runs all 9 agents, was only running 6)
- Reasoning validation + skeptic always run, even on compliance failures
- `validate_agent_reasoning.py` regex fixed for `### CHECKED` markdown format
- 5 fuzzer test files from agent findings #1017-#1021 (88 property-based tests)
- Shared Hypothesis strategies extracted to `tests/strategies.py`
- Iteration guards in `match_mu.py` (bindings_to_dict, denormalize_from_match)

### Gate 5 Compliance/Severity Split (PR #221)

- JS Gate 5 parity: `runStructural()` routes through `stepKernel(allProjectionsWithBridge)`
- Prototype pollution hardened in JS substrate
- Compliance severity split for agent validation tooling

## 2026-02-08

### Gate 5 Runtime Parity Fix (PR #221)

- `run_mu_structural()` now executes through `step_kernel_mu(..., kernel_mode="bridge")`
- JS parity fix: `runStructural()` routes through `stepKernel(allProjectionsWithBridge)`

## 2026-02-07

### Gate 4: Structural Runtime Cutover + Doc/Parity Sync

- `run_algorithm_meta_circular()` now defaults to structural execution (`step_kernel_mu(..., kernel_mode="bridge", validation_mode="algorithm_runtime")`)
- Bootstrap algorithm execution remains explicit fallback only (`execution_mode="bootstrap"`)
- Promoted recurrence/exhaustion seed metadata to `execution_layer: META_CIRCULAR`
- Updated seed integrity checksums for `recurrence.v1.json` and `exhaustion.v1.json`
- Fixed JS bridge JSON API runtime loop to unwrap kernel result correctly and preserve Python/JS parity
- Synced canonical tracker docs and roadmap timeline to Gate 4 COMPLETE / Gate 5 IN_PROGRESS
- Hardened docs consistency test to use canonical layer lines and tolerate markdown-format marker variants

## 2026-02-06

### Tooling: Canonical Pre-Commit Gate Consolidated

- Removed legacy script: `tools/pre-commit-check.sh`
- Standardized on `tools/pre-commit-doc-check` as the single pre-commit gate
- Added targeted staged-file checks to `tools/pre-commit-doc-check`:
  - `py_compile` for staged Python files
  - bare `except:` detection in staged `rcx_pi/*` files
  - `ast_police.py` on staged `rcx_pi/*` files
  - `seed_police.sh` when staged `mu/*.json` files are present
- Updated docs and grounding tests to reference only the canonical hook path

## 2026-02-03

### rcx_engine.v1.json Test Coverage: 6 Projections Now Tested

**Addressed grounding agent finding:** rcx_engine.v1.json had 6 untested projections.

**Created:**
- `tests/fixtures/rcx_engine_vectors.json` - 7 test vectors covering all engine phases
- `tests/test_rcx_engine_parity.py` - 15 tests verifying engine projection behavior

**Tests cover:**
- `engine.init` - Initialize with default config
- `engine.init_config` - Initialize with custom config
- `engine.trace_done` - Trace complete triggers recurrence
- `engine.recurrence_done` - Recurrence result triggers exhaustion
- `engine.exhaustion_done` - Exhaustion result produces final output
- `engine.unwrap` - Extract final engine result

**Note:** rcx_engine.v1.json has `status: "design_only"` - projections are tested but not yet integrated into production execution.

---

### Agent Validator: Now Verifies TRUTH, Not Just FORMAT

**Problem discovered:** The agent validator only checked FORMAT (FINDING/FILE/LINES/CODE blocks exist) but never verified if cited code actually appears at the claimed location. Agents could produce perfectly formatted fabrications.

**Fix applied:**
- `tools/validate_agent_compliance.py` now reads actual files and compares CODE
- New `--verify-code` flag checks if CODE matches FILE:LINE (anti-fabrication)
- New `--strict` flag enables all verifications (recommended for CI)
- Similarity matching with 80% threshold for formatting differences
- Clear "FABRICATION DETECTED" errors with details

**Agent prompts updated:**
- All 9 agents now warned: "Your citations will be MACHINE-VERIFIED"
- Agents must use Read tool and paste EXACTLY from output
- structural-proof agent must write tests to `tests/agent_verification/`
- grounding agent must write tests to `tests/structural/`

**Hook updated:**
- `.claude/hooks/validate-agent-compliance.sh` now runs with `--strict`
- Fabricated citations are blocked with clear error message

---

### Bootstrap-Structural Bridge: Wiring Verified

**Structural matching with bridge WORKS.** Execution path tests prove bridge projections fire:
- `bridge.var.check_existing` intercepts variable patterns
- `bridge.lookup.not_found` adds new bindings
- `bridge.lookup.found_same` handles non-linear match (same value)
- `bridge.lookup.found_different` detects binding conflicts

**Algorithm execution wiring clarified:**
- `run_algorithm_meta_circular()` uses Python match/substitute for practical execution
- Python match/substitute ALREADY handle non-linear patterns correctly
- The bridge PROVES this CAN be structural (capability demonstration)
- For TRUE meta-circular algorithm execution, algorithm projections would need to work with normalized format

**What's needed for TRUE meta-circular algorithm execution:**
1. Algorithm projections (recurrence.v1, exhaustion.v1) work with linked-list format internally
2. Structural match/subst normalizes everything to linked-list format
3. To wire algorithms through structural match/subst, either:
   - Rewrite algorithm projections to expect fully normalized state, OR
   - Create a normalization-free structural matcher for algorithm use

---

### Execution Path Verification: Tests Verify What Actually Runs (FIXED)

**Problem identified and FIXED:** Tests had verified BEHAVIOR but not EXECUTION PATH. All tests passed because Python's `eval_seed.match()` provides binding conflict detection, but we claimed bootstrap_structural projections were providing it. This was "test theater."

**Solution implemented:**
- Created `tests/test_execution_path_verification.py` with 9 tests
- Tests use tracing to prove WHICH projections fire
- Tests FAIL if bridge projections don't execute (even if behavior is correct)
- Fixed wiring: bridge projections now come BEFORE match.v2 in combined kernel

**Agent guardrails updated:**
- Added "Execution Path Verification" section to `mu/docs/agents/AgentGuardrails.v0.md`
- Agents must now verify execution path, not just behavior
- Claims like "runs through X" require tests that fail if X isn't used

**match.v3 cleanup:**
- Removed all references to match.v3.json (file was incorrectly created)
- We use match.v2.json + bootstrap_structural.v1.json directly
- Updated all tests, docs, and seed_integrity.py

---

### Cleanup: Removed Stale substrates/js/ Directory

**Removed:** `substrates/js/eval_step.js` (stale duplicate)

The canonical JS substrate location is now `mu/host/js/eval_step.js`. The old `substrates/js/eval_step.js` was left behind after the mu/ folder reorganization (2026-02-02) and was 478 bytes behind the canonical version. All tests and documentation already reference the correct path.

---

## 2026-02-02

### Step 7: Bootstrap-Structural Bridge IMPLEMENTED

**Core implementation complete.** Non-linear pattern support via binding conflict detection as structural projections.

**Files created:**
- `mu/bridge/bootstrap_structural.v1.json` - 5 bridge projections for binding lookup
- `tests/test_bootstrap_structural_bridge.py` - 31 tests covering all 22 design vectors

**Architecture note:** We use match.v2 + bootstrap_structural.v1 directly (loaded at runtime)
rather than a combined match.v3 file. This keeps the bridge modular.

**How it works:**
- When pattern has `{"var": "x"}`, bridge checks if `x` is already bound
- If not bound: add new binding (same as match.v2)
- If bound with same value: continue (non-linear pattern OK)
- If bound with different value: NO_MATCH (binding conflict detected)

**Test coverage:**
- Linear parity tests (5): verify bridge matches match.v2 for linear patterns
- Non-linear detection tests (8): verify binding conflict detection works
- Edge cases (4): null values, empty collections, type mismatches
- Security vectors (3): reserved field handling, ordering verification
- Cross-substrate parity (3): unicode, float, deep nesting

**Still pending (Gates 6-7):**
- Update recurrence.v1/exhaustion.v1 to declare META_CIRCULAR
- Port bridge to JavaScript for L3 parity

**Files updated:**
- `rcx_pi/selfhost/seed_integrity.py` - Added checksums for new seeds
- `tools/seed_police.sh` - Added bridge.* to allowed prefixes, v3 version handling
- `mu/docs/core/BootstrapStructuralBridge.v0.md` - Updated status to IMPLEMENTED

---

### Bootstrap-Structural Bridge: Promoted to NEXT (Step 7)

**Promoted from VECTOR** after 9-agent verification review confirmed all fixes applied correctly.

**Final verdicts (verification round):**
| Agent | Verdict |
|-------|---------|
| Verifier | APPROVE |
| Adversary | SECURE |
| Expert | MINIMAL |
| Structural-proof | STRUCTURALLY_SOUND |
| Grounding | ADEQUATELY_GROUNDED |
| Fuzzer | NEEDS_MORE (non-blocking) |
| Translator | MATCHES_INTENT |
| Visualizer | ARCHITECTURALLY_ALIGNED |
| Advisor | READY_FOR_PROMOTION |

**Files updated:**
- `TASKS.md` - Added Step 7 to NEXT section with full implementation plan
- `STATUS.md` - Updated next milestone to Step 7 implementation

**Implementation plan:** 7 gates defined by Advisor agent, ~12 projections total.
See `TASKS.md` Step 7 for details.

---

### Bootstrap-Structural Bridge: 9-Agent Review Complete

**Review completed** for `mu/docs/core/BootstrapStructuralBridge.v0.md` with all 9 agents:
- Verifier: APPROVE (all 15 North Star invariants pass)
- Adversary: NEEDS HARDENING → FIXED
- Expert: MINIMAL
- Structural-proof: DESIGN SOUND
- Grounding: PARTIALLY_GROUNDED → FIXED
- Fuzzer: DESIGN COMPLETE
- Translator: MATCHES_INTENT
- Visualizer: 3 DIAGRAMS
- Advisor: PROMOTE TO NEXT

**Security hardening applied:**
- KERNEL_RESERVED_FIELDS updated from 20 to 24 fields (both Python and JS)
- Added: `_lookup_name`, `_lookup_value`, `_lookup_bindings`, `_original_bindings`
- Test vector table expanded from 6 to 22 vectors

**Files changed:**
- `rcx_pi/selfhost/step_mu.py` - Added 4 bridge reserved fields
- `mu/host/js/eval_step.js` - Added 4 bridge reserved fields (L3 parity)
- `substrates/js/eval_step.js` - Added 4 bridge reserved fields (L3 parity)
- `tests/test_security_boundary_fuzzer.py` - Updated reserved field count (20→24)
- `tests/test_kernel_security_fuzzer.py` - Updated reserved field count (20→24)
- `tests/test_js_parity_automated.py` - Updated reserved field count (20→24)
- `tests/structural/test_step_mu_kernel_integration.py` - Updated expected reserved fields set
- `mu/docs/core/BootstrapStructuralBridge.v0.md` - Expanded test vectors, updated checklist
- `TASKS.md` - Marked 9-agent review complete, design ready for NEXT

---

### mu/ Folder Reorganization

**Problem:** Seeds were all in flat `seeds/` folder. Architecture wasn't visible from file structure. Closure detection seeds (enginenews, exhaust) had confusing names.

**Solution:** Created `mu/` folder structure that makes architecture visible:
- `mu/substrate/` - The VM: kernel.v1, match.v1, match.v2, subst.v1, subst.v2
- `mu/closures/` - Closure detection: recurrence.v1 (renamed from enginenews), exhaustion.v1 (renamed from exhaust)
- `mu/programs/` - Applications: rcx_engine.v1 (new, orchestrates closures)
- `mu/utilities/` - Helpers: classify.v1, eval.v1
- `mu/host/js/` - JavaScript bootstrap: eval_step.js (moved from substrates/js/)
- `mu/host/python/` - Python bootstrap (symlink to rcx_pi/selfhost/)

**Files Changed:**
- All seeds copied to appropriate mu/ subfolders
- `mu/closures/recurrence.v1.json` - renamed from enginenews, projection IDs updated (recurrence.*)
- `mu/closures/exhaustion.v1.json` - renamed from exhaust, projection IDs updated (exhaustion.*)
- `mu/programs/rcx_engine.v1.json` - new main program (6 projections)
- `mu/host/js/eval_step.js` - updated to use mu/ paths, renamed to use recurrence/exhaustion
- `rcx_pi/selfhost/seed_integrity.py` - added new checksums and get_seed_path() helper
- `tests/fixtures/recurrence_vectors.json` - renamed from enginenews_vectors.json
- `STATUS.md` - updated key files section

**Backwards Compatibility:**
- Legacy `seeds/` folder still works
- Python imports unchanged (rcx_pi.selfhost via symlink)
- `get_seed_path()` helper finds seeds in mu/ or falls back to seeds/

---

### Architectural Gap: match.v2 / Non-Linear Pattern Incompatibility

**Problem (discovered in 9-agent review):** match.v2.json states "Linear patterns only (no conflict detection)", but enginenews.v1.json and exhaust.v1.json rely on non-linear patterns (same variable twice for equality). These seeds work via bootstrap (eval_seed) but CANNOT run through the meta-circular kernel.

**Impact:** Seeds could not be declared META_CIRCULAR. Tests passed via bootstrap, hiding architectural incompatibility.

**Solution:**
- Added North Star #14 (execution layer declaration) and #15 (true self-hosting path)
- Added Cross-Seed Compatibility Check to AgentGuardrails.v0.md
- Updated enginenews.v1.json and exhaust.v1.json with `"execution_layer": "BOOTSTRAP"`
- Created VECTOR item for bootstrap_structural bridge (non-linear pattern support)
- Created design doc `mu/docs/core/BootstrapStructuralBridge.v0.md`

**Files:**
- `TASKS.md` - Added North Star #14, #15; added bootstrap_structural to VECTOR
- `mu/docs/agents/AgentGuardrails.v0.md` - Added Cross-Seed Compatibility Check section
- `seeds/enginenews.v1.json` - Added execution_layer, requires_patterns, incompatible_with
- `seeds/exhaust.v1.json` - Added execution_layer, requires_patterns, incompatible_with
- `mu/docs/core/BootstrapStructuralBridge.v0.md` - Design doc for non-linear pattern support

**Lesson Learned:** 9-agent review verified correctness but not architectural fit. New guardrails require verifying execution path matches claims, not just that tests pass.

---

### Step 6: Operator Exhaustion (Rule 3.1) - COMPLETE

**Problem:** Need to detect when an operator has been applied continuously since τ was logged without making progress (Rule 3.1 from RCXEngineNew.pdf).

**Solution:**
- Created `seeds/exhaust.v1.json` with 11 projections
- Three-phase state machine: find_tau → scan → check_frozen → terminal
- Non-linear patterns for equality detection (binding conflict detection)
- First-match-wins ordering (scan_same before scan_different)
- Frozen list as Mu linked-list, NOT Python set

**Projections (exhaust.v1.json):**
- `exhaust.init_null`, `exhaust.init` - Entry points
- `exhaust.find_match`, `exhaust.find_continue`, `exhaust.find_not_found` - Find τ phase
- `exhaust.scan_same`, `exhaust.scan_different`, `exhaust.scan_end` - Scan phase
- `exhaust.frozen_found`, `exhaust.frozen_check_tail`, `exhaust.do_freeze` - Freeze phase

**Testing:**
- 17 parity tests in `tests/test_exhaustion_parity.py`
- 10 fuzzer tests in `tests/test_exhaustion_fuzzer.py`
- 6 test vectors in `tests/fixtures/exhaustion_vectors.json`
- 6 cross-substrate tests (Python and JS produce identical results)

**Security:**
- KERNEL_RESERVED_FIELDS updated to 20 (12 kernel + 4 EngineNews + 4 exhaustion)
- Both Python and JavaScript have identical reserved fields
- Automated parity test at `test_js_parity_automated.py::test_python_js_constants_match`

**Files:**
- `seeds/exhaust.v1.json` - 11 projections
- `tests/test_exhaustion_parity.py` - 17 tests
- `tests/test_exhaustion_fuzzer.py` - 10 tests
- `tests/fixtures/exhaustion_vectors.json` - 6 vectors
- `substrates/js/eval_step.js` - Updated with exhaust.v1.json loading
- `rcx_pi/selfhost/seed_integrity.py` - Added exhaust.v1.json checksum
- `mu/docs/core/OperatorExhaustion.v0.md` - Design doc updated to IMPLEMENTED

## 2026-02-01

### Agent Guardrails (Anti-Hallucination Infrastructure)

**Problem:** LLMs can hallucinate plausible-sounding file paths and code snippets. Previous agent outputs weren't verified for evidence.

**Solution:**
- Created `mu/docs/agents/AgentGuardrails.v0.md` - spec requiring FILE:LINE + code evidence
- Created `tools/validate_agent_compliance.py` - regex-based output validator
- Created `tests/tools/test_validate_agent_compliance.py` - 43 tests for validator
- Created `.claude/hooks/validate-agent-compliance.sh` - automatic SubagentStop hook
- Updated all 9 agent prompts with MANDATORY verification protocol section

**Evidence Format (required for all findings):**
```
FINDING: [description]
FILE: /absolute/path
LINES: start-end
CODE:
    [paste from Read tool output]
VERIFIED: Yes
```

**Validator Features:**
- Line ending normalization (handles Windows/Mac/Unix)
- CODE block validation (accepts tabs OR 2+ spaces)
- Hallucination word detection (13 words blocked)
- STATUS.md check (must be read in first 50 lines)

**Files:**
- `mu/docs/agents/AgentGuardrails.v0.md` - specification
- `tools/validate_agent_compliance.py` - validator script
- `tests/tools/test_validate_agent_compliance.py` - 43 tests
- `.claude/hooks/validate-agent-compliance.sh` - automatic hook
- `.claude/settings.json` - hook configuration
- `tools/agents/archive_pre_guardrails/` - archived old prompts

**Agent Model Updates:**
- Expert upgraded from Sonnet to Opus
- Visualizer upgraded from Haiku to Sonnet
- All agents now use Opus (4) or Sonnet (5) - no Haiku

### Additional Fuzzer Tests (9-agent findings)

- Created `tests/structural/test_entropy_budget_enforcement.py` - EntropyBudget.md grounding
- Created `tests/test_denormalize_type_confusion_fuzzer.py` - type confusion attacks
- Created `tests/test_normalize_malformed_fuzzer.py` - malformed structure handling

### Git Tracking

- `.claude/` directory now tracked (agents, hooks, settings.json) - was previously gitignored
- Enables reproducible agent setup across machines

## 2026-01-31

### Cross-Substrate Parity Verification (9-agent Round 3 Fix)

**Problem (Grounding finding):** Previous JS parity tests were "theater" - they just
parsed strings like "0 failed" from stdout. No test actually ran the same input through
both Python and JavaScript and compared the outputs.

**Fixes:**

- **JS JSON API Mode** (`substrates/js/eval_step.js`)
  - Added `--json-api` command line option for machine-readable output
  - Actions: `run_vector`, `run_all_vectors`, `run_enginenews`, `get_constants`
  - Outputs JSON on single line for easy parsing by Python tests
  - Fixed EngineNews e2e test expectations: stall IS a closure (fixed point)

- **Actual Cross-Substrate Comparison** (`tests/test_js_parity_automated.py`)
  - Added `_normalize_for_cross_substrate()` - handles int/float equivalence (JS doesn't distinguish)
  - Added `_cross_substrate_equal()` - compares normalized outputs
  - New `test_actual_cross_substrate_comparison` - runs SAME 20 parity vectors through BOTH substrates
  - New `test_python_js_constants_match` - verifies MAX_DEPTH=300 and KERNEL_RESERVED_FIELDS match

- **Git Tracking** (`.gitignore`)
  - `substrates/js/eval_step.js` now tracked in git (was previously gitignored)
  - Required for CI to run JS parity tests

**Test Results:**
- 13 JS parity tests: PASSED (including actual comparison)
- 2025 functional tests: PASSED
- Cross-substrate parity is now ACTUALLY VERIFIED, not just claimed

**Known Limitation (documented, not a bug):**
- JavaScript doesn't distinguish between integers and floats (0 === 0.0)
- Cross-substrate comparison normalizes all numbers to float for comparison
- Semantically equivalent; only representation differs

## 2026-01-30

### Step 5: EngineNews Structural Closure Detection (COMPLETE)

**Implementation:**
- Created `seeds/enginenews.v1.json` with 9 projections for Rule 2.2 (Closure-on-Second-Demand)
- Projections: init, end_of_trace, check_state_stall, check_state_maxsteps, check_state,
  found_in_seen, not_in_head, not_found, unwrap
- Non-linear patterns for state equality (same variable `{"var": "state"}` twice)
- Seen-set is Mu linked-list, NOT Python set
- All closure detection logic is in projections (DATA), not Python code

**Key Design Decision: Non-linear Patterns**
- `enginenews.found_in_seen` uses `{"var": "state"}` in both `_state` and `_check_list.head`
- eval_seed.match() binding conflict detection (lines 331-336, 351-355) enforces equality
- This is bootstrap primitive (like Forth's NEXT), not semantic debt
- Both Python and JS substrates handle binding conflicts identically

**Tests:**
- `tests/test_recurrence_parity.py` - 24 parity tests including:
  - TestRecurrenceProjections: seed structure validation
  - TestRecurrenceParity: parity vector tests
  - TestRecurrenceIntegration: integration with run_mu_structural
  - TestRecurrenceSpecCompliance: Rule 2.2 grounding tests
  - TestRecurrenceClosureObjectStructure: exact Omega(tau) structure
  - TestRecurrenceExactProjectionCount: 9 projections exactly
- `tests/test_recurrence_fuzzer.py` - Property-based fuzzer tests:
  - TestRecurrenceDeterminism: same input -> same output
  - TestRecurrenceClosureSemantics: Rule 2.2 semantics
  - TestRecurrenceEdgeCases: numeric, string, null states
  - TestRecurrenceTypeDistinctness: 0 vs false vs null
  - TestRecurrenceTraceFormats: stall, max_steps entries
  - TestRecurrenceComplexStates: nested state equality
- `tests/fixtures/recurrence_vectors.json` - 22 parity vectors

**7-Agent Review (Second Pass):**
| Agent | Verdict | Summary |
|-------|---------|---------|
| Verifier | APPROVE | All 12 North Star invariants maintained |
| Adversary | SECURE | Non-linear pattern concern RESOLVED |
| Expert | MINIMAL | Code appropriately sized |
| Structural-proof | PROVEN | All 4 structural claims verified |
| Grounding | GROUNDED | All claims have executable tests |
| Fuzzer | DESIGN COMPLETE | Comprehensive fuzzer code provided |
| Advisor | RESOLVED | Architecture is sound |

**Documentation:**
- Updated `mu/docs/core/EngineNewsStructural.v0.md` - marked IMPLEMENTED
- Updated `mu/docs/core/SelfHosting.v0.md` - added EngineNews section
- Updated `mu/docs/core/BootstrapPrimitives.v0.md` - added binding conflict note
- Updated `STATUS.md` - Step 5 DONE
- Updated `TASKS.md` - all checkboxes marked complete

### Second 7-Agent Adversarial Review (Complete)

**Verdicts:**
- Verifier: CONDITIONAL_APPROVE (all 12 invariants maintained)
- Adversary: SECURE (11/11 attacks blocked, defensive cache copy verified)
- Expert: COULD_SIMPLIFY (2 trivial import issues in conftest.py)
- Structural-proof: CLAIMS_HONEST (L2 PARTIAL proven with concrete evidence)
- Grounding: GROUNDED (all 4 claims have executable tests)
- Fuzzer: GAPS_EXIST (4 boundary gaps: depth=100, width=900-1000, cache at scale, mixed)
- Advisor: ON_TRACK (Step 5 needs concrete success criteria)

### Security Fixes
- **Cache Mutation Vulnerability** (Adversary finding - CLOSED)
  - `projection_loader.py`: Returns `list(cache[0])` defensive copy
  - `step_mu.py`: Returns `list(_combined_kernel_cache)` defensive copy
  - New test: `test_mutation_does_not_affect_cache()` in test_projection_loader.py
  - Updated caching tests to verify content equality, not object identity

### Code Quality
- **Duplicate Code Consolidated** (Expert finding - CLOSED)
  - `run_until_done()` moved to `tests/conftest.py` as shared utility
  - `test_phase7c_integration.py` now imports from conftest
  - `test_parity_python.py` now imports from conftest
  - Removed ~70 lines of duplicate code

### Testing
- **Dict kv-pair Regression Tests** (Grounding finding - CLOSED)
  - Added `TestDictKvPairFormat` class (4 tests)
  - Tests exact structural format: `{"head": key, "tail": {"head": value, "tail": null}}`
  - Tests sorted key order, nested preservation

- **Malformed Linked List Tests** (Fuzzer finding - CLOSED)
  - Added `TestMalformedLinkedListEdgeCases` class (9 tests)
  - Tests head-only, tail-only, malformed tail types
  - Tests circular reference detection
  - Tests deeply nested and wide dict handling

### Documentation
- **CRITICAL: EngineNews Must Be Structural**
  - Updated TASKS.md Step 5 with concrete success criteria
  - EngineNews rules MUST be Mu projections, NOT Python code
  - Closure detection must be pattern matching on traces
  - This ensures emergence is structural, not "Python did it"
  - Added `enginenews.v1.json` requirements (≥4 projections)

- **STATUS.md**: Added second 7-agent review verdicts table
- **TASKS.md**: Updated Step 5 with structural requirements and success criteria

### Test Count
- 913 tests pass in fast audit
- 1669 tests pass in full suite (2 expected idempotency failures from uncommitted changes)

## 2026-01-29

### Security Hardening (7-agent review)
- **Deprecation Enforcement** (HIGH priority fix)
  - Added `filterwarnings = ["error::DeprecationWarning:rcx_pi.*"]` to pyproject.toml
  - New code using deprecated Kernel class will now FAIL tests (not just warn)
  - Removed `TestKernelIntegration` class (4 tests) - used deprecated Kernel
  - Coverage already exists via test_step_mu_parity.py, test_kernel_projections.py

- **Step Budget Test Coverage** (coverage gap fix)
  - Created `tests/structural/test_step_budget.py` (18 tests)
  - Tests: basics, limits, reset, thread safety, no-deprecation verification
  - Grounds the claim that step budget functions are ACTIVE (not deprecated)

- **Archive Protection** (MEDIUM priority fix)
  - Added `tests/archive/conftest.py` with `pytest_ignore_collect` hook
  - `pytest tests/archive/` now collects 0 tests (was 134)
  - Prevents accidental execution of deprecated tests

- **CI Contraband/AST Police** (MEDIUM priority fix)
  - Added contraband.sh and ast_police.py to `scripts/green_gate.sh`
  - CI now runs [PY 1/4] syntax, [PY 2/4] contraband, [PY 3/4] AST, [PY 4/4] tests
  - Catches host smuggling before merge (was only in local audit_all.sh)

- **Audit Claims Grounding Tests** (grounding agent recommendation)
  - Created `tests/structural/test_audit_claims_grounding.py` (18 tests)
  - Tests verify: archive blocking, deprecation enforcement, audit script structure
  - Tests verify: lambda guardrails exist, step budget coverage exists
  - Fully grounds all audit infrastructure claims

### Architecture Cleanup
- **kernel.py Clarification** (7-agent review)
  - Added architecture comment block explaining two distinct concerns:
    1. ACTIVE: Step budget functions (get_step_budget, etc.) - used by self-hosting
    2. LEGACY: Kernel class - NOT used by self-hosting, only for testing
  - Added deprecation warning to `Kernel` class and `create_kernel()` factory
  - Moved `test_kernel_v0.py` to `tests/archive/legacy/`
  - Created `tests/structural/test_lambda_calculus_guardrails.py` with 11 guardrail tests
  - Updated mu/docs/core/MetaCircularKernel.v0.md with deprecation note and max_steps clarification

- **Documentation: kernel.v1.json as Canonical Kernel**
  - Updated README.md: Core modules table now lists kernel.v1.json as "THE canonical kernel"
  - Updated mu/docs/core/SelfHosting.v0.md: kernel.py noted as "not canonical; see kernel.v1.json"
  - Updated mu/docs/core/RCXKernel.v0.md: Added status column marking kernel.v1.json as canonical
  - Updated mu/docs/audit/MetaCircularReadiness.v1.md: Current status references kernel.v1.json

- **Audit Stack Cleanup**
  - Updated tools/audit_fast.sh: Removed archived test_kernel_v0.py from explicit test list
  - tests/conftest.py already has `"archive"` in collect_ignore (no change needed)
  - Lambda calculus guardrails auto-included via tests/structural/ in audit_fast.sh

### Testing
- **Lambda Calculus Guardrail Tests Migrated** (11 tests)
  - Migrated from test_eval_seed_v0.py to dedicated structural test file
  - Tests prove: no closures, no self-application, no Y-combinator, no higher-order matching
  - These are NORTH STAR invariant enforcement tests

### Documentation
- **STATUS.md**: Fixed @host_recursion count (3 → 2)
- **Added tests for `is_kernel_intermediate()`** (12 tests)
  - Documents key finding: `{"mode": "subst"}` (value) vs `{"subst": ...}` (key)
  - Proves mu_equal stall detection works correctly for unbound variables

### L2 Grounding & Boundary Validation
- **Docstring False Positive Fix**
  - Fixed eval_seed.py:70 docstring being counted as debt by debt_dashboard.sh
  - Was matching `@host_` pattern in docstring text

- **L2 Cursor Grounding Tests** (7 tests)
  - Created `tests/structural/test_l2_cursor_grounding.py`
  - Proves `_remaining` is structural (head/tail), not arithmetic index
  - Tests kernel.wrap creates _remaining from _projs linked list
  - Tests kernel.try consumes head, kernel.match_fail advances to tail

- **Boundary Validation Fuzzer** (27 tests)
  - Created `tests/test_boundary_validation_fuzzer.py`
  - Tests assert_seed_pure with valid/invalid inputs (lambdas, functions, builtins)
  - Tests validate_type_tag whitelist enforcement (list/dict only)
  - Tests get_var_name validation (empty names, non-var sites)

- **Kernel Bridge Fuzzer** (26 tests)
  - Created `tests/test_kernel_bridge_fuzzer.py`
  - Tests list_to_linked (preserves length, order, produces valid Mu)
  - Tests normalize_projection (pattern/body normalization)
  - Integration tests for projection list conversion

- **SelfHosting.v0.md Update**
  - Documented legacy Kernel class deletion (~350 lines removed)
  - Clarified kernel.py now only contains step budget infrastructure

## 2026-01-28

### Testing
- **Fuzzer Configuration Fully Standardized** (3x 9-agent review)
  - Fixed `deadline=None` in test_apply_mu_fuzzer.py (10 tests → `deadline=5000` or `deadline=10000`)
  - Standardized `max_depth=3` default across ALL 6 fuzzer generators:
    - test_bootstrap_fuzzer.py, test_selfhost_fuzzer.py, test_type_tags_fuzzer.py
    - test_apply_mu_fuzzer.py, test_phase8b_fuzzer.py, test_phase7_readiness_fuzzer.py
  - Fixed 29 call site overrides: `max_depth=4` → `max_depth=3` across 4 files
  - Fixed docstring bug in test_apply_mu_fuzzer.py ("default 5" → "default 3")
  - Documentation claims now match reality (STATUS.md is single source of truth)
  - Prevents tests from hanging on pathological inputs
  - All 772 core tests pass

### Self-Hosting
- **Phase 7d-1: Wire step_mu to Structural Kernel** (L2 PARTIAL)
  - `step_mu()` delegates to `step_kernel_mu()` which uses structural kernel
  - Added helpers: `list_to_linked()`, `normalize_projection()`, `load_combined_kernel_projections()`
  - Kernel uses linked-list cursor for projection SELECTION (structural)
  - Projection EXECUTION still uses Python for-loop in `step_kernel_mu`
  - Behavioral change: unbound variables now stall instead of raising KeyError

- **Honest Assessment (7-agent review)**
  - structural-proof agent found: execution loop still Python (lines 229-261)
  - Added `@host_iteration` decorator to `step_kernel_mu()` (honest debt tracking)
  - Debt: 15 → 15 (moved location, not eliminated)
  - L2 PARTIAL: selection structural, execution Python
  - True L2 requires Phase 8 recursive kernel design
  - 7d-2/7d-3 PAUSED pending Phase 8

- **Phase 7a: Kernel Projections Seed**
  - Created `seeds/kernel.v1.json` with 7 kernel projections
  - Projections: kernel.wrap, kernel.stall, kernel.try, kernel.match_success, kernel.match_fail, kernel.subst_success, kernel.unwrap
  - 30 manual trace tests pass (success, failure, empty, fallthrough)
  - Tests in `tests/test_kernel_projections.py`

- **Phase 7b: Match/Subst Context Passthrough**
  - Created `seeds/match.v2.json` with `_match_ctx` passthrough + match.fail catch-all
  - Created `seeds/subst.v2.json` with `_subst_ctx` passthrough
  - Context enables kernel to preserve state across mode transitions

- **Phase 7c: Integration Testing**
  - 20 integration tests: kernel → match → subst → kernel cycles
  - Tests in `tests/test_phase7c_integration.py`
  - Context preservation verified through full cycles
  - Security: domain data can't forge `_mode` (underscore prefix)

### Tests
- **v2 Parity Tests**
  - Created `tests/test_match_v2_parity.py` (19 tests)
  - Created `tests/test_subst_v2_parity.py` (18 tests)
  - 37 tests verify v2 seeds preserve v1 behavior
  - Tests: seed structure compatibility, functional parity, context design

### Debt Tracking
- **Comprehensive Debt Audit**
  - Found and marked 4 @host_iteration markers (step_mu, run_mu, eval_seed.step, projection_runner)
  - Added `# @host_iteration` comment marker for nested function debt
  - Updated `debt_dashboard.sh` to count both decorator and comment markers
  - Debt: 15 (12 tracked + 3 AST_OK)

- **Debt Target Revision**
  - Original target was 9, revised to 12 per structural-proof agent
  - run_mu outer loop stays as L3 boundary (scaffolding, not semantic debt)
  - 7d-1 moved debt from step_mu to step_kernel_mu (net: 15 → 15)
  - True debt reduction (15 → 12) deferred to Phase 8

### Docs
- **Doc Consistency Fixes**
  - All design docs now reference STATUS.md for debt numbers (no hardcoded values)
  - `mu/docs/core/SelfHosting.v0.md`: Removed hardcoded debt breakdown
  - `mu/docs/core/MetaCircularKernel.v0.md`: Updated status VECTOR → NEXT
  - `mu/docs/core/DebtCategories.v0.md`: Removed outdated DEBT_THRESHOLD values

### Security
- **Kernel Projection Order Validation**
  - Added `validate_kernel_projections_first()` call in step_mu() production path
  - Domain projections can no longer run before kernel projections
  - Tests in `tests/structural/test_projection_order_security.py`

### Process
- **7 Agent Review Complete**
  - verifier: APPROVE WITH DOC FIXES
  - adversary: AT_RISK (security concerns documented)
  - expert: MINIMAL (code is clean)
  - structural-proof: PARTIALLY PROVEN (debt 15→9 unrealistic, revised to 15→12)
  - grounding: GROUNDED (all claims backed by tests)
  - fuzzer: GAPS (3 property tests recommended before 7d)
  - advisor: PROCEED NOW (foundation strong)

### Tooling
- **Pre-commit Hook Improvements**
  - Added debt ceiling check to `tools/pre-commit-doc-check`
  - Hook now warns if debt exceeds THRESHOLD from STATUS.md
  - Updated `CLAUDE.md` with clearer workflow documentation
  - Added "Development Workflow" section to `STATUS.md`
  - Two pre-commit scripts documented: `pre-commit-check.sh` (full) vs `pre-commit-doc-check` (hook)

## 2026-01-27

### Agents
- **Advisor Agent** - New strategic advisor for when stuck on design decisions
  - Created `tools/agents/advisor_prompt.md` and `.claude/agents/advisor.md`
  - Provides options, trade-off analysis, creative solutions
  - Verdict types: OPTIONS_PROVIDED / RECOMMENDATION / NEEDS_MORE_CONTEXT
  - Advisor PROPOSES, other agents VALIDATE

- **Agent Documentation Completion**
  - Created 4 missing prompt files in `tools/agents/` (now all 10 agents tracked in git):
    - `grounding_prompt.md`, `fuzzer_prompt.md`, `translator_prompt.md`, `visualizer_prompt.md`
  - All agents now have "STATUS.md wins" override rule
  - structural-proof has exec/non-exec modes (Mode A: run, Mode B: CI verification)

- **Archived**: `tools/verification_checklist.md` → `archive/docs/verification_checklist_v0.md`
  - Superseded by `tools/agents/verifier_prompt.md` (verifier agent)

### Design
- **Phase 7 Design: Meta-Circular Kernel** (PR #168)
  - Created `mu/docs/core/MetaCircularKernel.v0.md` (VECTOR status)
  - Defines how kernel loop becomes structural (projections select projections)
  - Key design: linked-list cursor eliminates arithmetic (head/tail destructuring)
  - Structural-proof agent verified cursor approach is SOUND and STRUCTURAL
  - v0.2 revision addresses agent-identified gaps:
    - Context preservation via `_match_ctx` / `_subst_ctx` fields
    - Structural NO_MATCH: `{"_mode": "match_done", "_status": "no_match"}`
    - Namespace protection: `_` prefix for kernel-internal fields
    - Simplified from 11 to 7 kernel projections
  - Total projections: 7 kernel + 32 existing = 39 for fully self-hosted kernel

### Tooling
- **STATUS.md: Single Source of Truth for Project Phase**
  - Created `STATUS.md` as canonical source for current phase and self-hosting level
  - All agents now read STATUS.md before assessments (MANDATORY)
  - Self-hosting levels: L1 (Algorithmic), L2 (Operational), L3 (Full Bootstrap)
  - Agent Enforcement Guide table: what applies NOW vs LATER
  - When advancing phases: update ONE file, not 8+ agent files

- **Agent Semantic Phase Scope**
  - Updated all 8 agent `.md` files with semantic scope (L1/L2/L3, not phase numbers)
  - Agents reference STATUS.md for current level, not hardcoded version
  - Distinguishes scaffolding debt (acceptable at current L) from semantic debt (must fix)
  - Updated `mu/docs/agents/AgentRig.v0.md` with semantic Phase Scope table
  - Prevents phase drift: agents adapt automatically when STATUS.md updates

### Tests
- **Kernel Loop Fuzzer Tests** (PR #167)
  - 11 property-based tests for apply_mu, step_mu, run_mu
  - TestApplyMuDeterminism: 3 tests (determinism, var pattern, literal match)
  - TestApplyMuParity: 1 test (apply_mu == apply_projection)
  - TestStepMuDeterminism: 3 tests (determinism, empty projections, stall idempotent)
  - TestStepMuParity: 2 tests (step_mu == step, first-match-wins)
  - TestRunMuDeterminism: 2 tests (determinism, immediate stall)
  - 3000+ random examples stress-test kernel loop stability
  - Closes fuzzer gap identified by agents before Phase 7

### Tooling
- **Comprehensive Debt Tracking** (PR #155)
  - Marked ~289 LOC of previously unmarked semantic debt with `@host_*` decorators
  - match_mu.py: 7 decorators (3 `@host_recursion`, 4 `@host_builtin`)
  - subst_mu.py: 2 decorators (`@host_builtin`)
  - Updated DEBT_THRESHOLD: 14 → 23 (17 tracked + 5 AST_OK + 1 review)
  - Updated dashboard ceiling: 9 → 17
  - All semantic debt now fully tracked (was ~289 LOC unmarked)

### Tests
- **Head/Tail Collision Tests** (PR #155)
  - `TestMatchParityHeadTailCollision`: 5 tests verifying dicts with head/tail keys
  - Ensures user data like `{"head": "x", "tail": "y"}` isn't misclassified as linked list

- **Empty Collection Tests** (PR #155)
  - `TestMatchParityEmptyCollections`: 5 tests documenting known difference
  - Documents: `{}` and `[]` both normalize to `null` (intentional structural equivalence)
  - Tests explicitly mark this as "DOCUMENTED DIFFERENCE" vs parity

### Docs
- **Design Decisions Documented** (PR #155)
  - `mu/docs/core/DebtCategories.v0.md`: Added "Known Design Decisions" section
  - Empty collection normalization explained with rationale
  - Head/tail collision handling documented

### Process
- All 6 agents reviewed: verifier, adversary, expert, structural-proof, grounding, fuzzer
- Debt now at ceiling (23/23) with clear path to L2

### Security
- **Seed Integrity Verification** (PR #157)
  - `rcx_pi/selfhost/seed_integrity.py`: SHA256 checksum verification
  - Validates seed structure on load (meta, projections keys required)
  - Verifies expected projection IDs present and wrap is last
  - `match_mu.py` and `subst_mu.py` now use `load_verified_seed()`
  - 27 tests in `tests/test_seed_integrity.py`
  - Closes adversary finding: seeds were loaded without integrity verification

### Self-Hosting
- **Phase 6a: Lookup as Mu Projections** (PR #158)
  - Added `subst.lookup.found` and `subst.lookup.next` projections to subst.v1.json
  - Lookup is now structural: pattern matching with non-linear vars
  - `subst.var` now transitions to `phase: lookup` instead of creating marker
  - `subst.lookup.found`: name matches current binding → return value
  - `subst.lookup.next`: name doesn't match → continue with rest
  - Unbound variables stall (lookup_bindings becomes null, no projection matches)
  - Removed 2 `@host_builtin` decorators from subst_mu.py
  - DEBT_THRESHOLD: 23 → 21 (ratchet tightened)
  - 37 subst parity tests pass

- **Phase 6b: Classification as Mu Projections**
  - Created `seeds/classify.v1.json` with 6 projections for linked list classification
  - Created `rcx_pi/selfhost/classify_mu.py` for projection-based classification
  - `denormalize_from_match()` now uses `classify_linked_list()` instead of `is_dict_linked_list()`
  - `classify.nested_not_kv`: detects when "key" position has head/tail (not a string)
  - `classify.kv_continue`: element is valid kv-pair → continue scanning
  - `classify.not_kv`: element is not kv-pair → classify as list
  - Python pre-check validates: no cycles, all keys are strings (projections can't verify types)
  - Removed 2 `@host_builtin` decorators from match_mu.py
  - DEBT_THRESHOLD: 21 → 19 (ratchet tightened)
  - 26 tests in `tests/test_classify_mu.py`

- **Phase 6c: Normalization as Iterative + Type Tags**
  - `normalize_for_match()`: converted from recursive to iterative using explicit stack
  - `denormalize_from_match()`: converted from recursive to iterative using explicit stack
  - Removed 2 `@host_recursion` decorators from match_mu.py
  - Removed 2 `# AST_OK: bootstrap` comments (recursive comprehensions eliminated)
  - isinstance() checks at Python↔Mu boundary remain as scaffolding (not semantic debt)
  - **Type Tags** resolve list/dict ambiguity (previously `[["a", 1]]` and `{"a": 1}` normalized identically):
    - Lists get `_type: "list"`, dicts get `_type: "dict"` at root node
    - `VALID_TYPE_TAGS` whitelist + `validate_type_tag()` for security
    - New projections: `match.typed.descend`, `subst.typed.{descend,sibling,ascend}`
    - `classify_linked_list()` fast-path for type-tagged structures
  - 24 new property-based fuzzer tests (`tests/test_type_tags_fuzzer.py`)
  - All 1020 self-hosting tests pass
  - Agent review: verifier=APPROVE, adversary=HARDENED, structural-proof=PROVEN

## 2026-01-26

### Runtime
- **Thread-Safe Step Budget** (PR #149)
  - `_ProjectionStepBudget` uses `threading.local()` for thread isolation
  - Each thread gets independent budget tracking for concurrent execution
  - `get_step_budget()` and `reset_step_budget()` API

- **Cycle Detection** (PR #149)
  - `normalize_for_match()` detects circular references (raises ValueError)
  - `denormalize_from_match()` detects circular references (raises ValueError)
  - `is_dict_linked_list()` returns False on cycles instead of infinite loop

- **Resource Exhaustion Guardrails** (PR #149)
  - Global projection step budget: MAX_PROJECTION_STEPS = 50,000
  - Mu depth limit: MAX_MU_DEPTH = 300
  - Mu width limit: MAX_MU_WIDTH = 1,000
  - Empty variable name rejection in match_mu/subst_mu

### Tests
- **Comprehensive Fuzzer Tests** (PR #149)
  - `tests/test_selfhost_fuzzer.py`: 53 tests, 10,000+ random examples
  - `TestMatchMuParity`: match_mu == eval_seed.match (1,000 examples)
  - `TestSubstMuParity`: subst_mu == eval_seed.substitute (1,200 examples)
  - `TestHostileUnicodeHandling`: emoji, RTL, zero-width, homoglyphs
  - `TestNearLimitStress`: width 900-1000, depth 190-200
  - All Hypothesis tests use deadline=5000 (prevents infinite hangs)

- **Adversary Tests** (PR #149)
  - `test_nested_calls_exhaust_budget`: verifies budget limits cascading calls
  - `test_budget_thread_isolation`: verifies no cross-thread contamination
  - `test_circular_in_is_dict_linked_list_returns_false`: cycle safety
  - `test_nested_circular_in_normalize_raises`: nested cycle detection

### Process
- All 6 agents approved: verifier, adversary, expert, structural-proof, grounding, fuzzer
- Coverage rated ROBUST by fuzzer agent

## 2026-01-25

### Tooling
- **Rule Motif Observability v0** (PR #108)
  - `rules --print-rule-motifs` CLI command
  - `rule_motifs_v0()` pure helper returning all 8 rule motifs
  - `emit_rule_loaded_events()` generates v2 JSONL (`rule.loaded` events)
  - `RULE_IDS` canonical list for anti-drift testing
  - 11 subprocess CLI tests

- **Rule Motif Validation Gate v0** (PR #111)
  - `rules --check-rule-motifs` CLI command
  - `rules --check-rule-motifs-from <path>` for custom validation
  - `validate_rule_motifs_v0()` pure helper with validation rules:
    - Structure, id uniqueness, variable binding, host leakage, canonicalization
  - 16 subprocess CLI tests (positive + negative cases)

- **Trace Canon Helper v1** (PR #66)
  - `canon_jsonl()` function for JSONL serialization
  - 7 tests in `test_trace_canon_v1.py`
  - v2 event support (accepts both v1 and v2 events)

### Runtime
- **Second Independent Encounter v0** (NEXT #16)
  - Stall memory tracking: `_stall_memory` maps pattern_id → value_hash
  - Closure signal detection: `_check_second_independent_encounter()`
  - Memory clearing on `execution.fixed`: `_clear_stall_memory_for_value()`
  - Public API: `closure_evidence`, `has_closure` properties
  - `stall()` and `consume_stall()` now return bool (closure detected)
  - 15 tests in `test_second_independent_encounter.py`
  - All 8 pathological scenarios from IndependentEncounter.v0.md tested

### Docs
- Updated `docs/RuleAsMotif.v0.md` to reflect implementation status
- Updated `docs/cli_quickstart.md` with rules commands
- Updated `mu/docs/execution/IndependentEncounter.v0.md` to IMPLEMENTED status

## Unreleased

- Schema-triplet canonicalization: added `rcx_pi/cli_schema_run.py` as the single source of truth and updated CLI smoke + tests to route schema checks through the canonical runner (PRs #59–#62).

## 2026-01-24

### Runtime
- **v2 Execution Semantics (RCX_EXECUTION_V0=1)**
  - ExecutionEngine with stall/fix/fixed state machine
  - Public consume API: `consume_stall`, `consume_fix`, `consume_fixed`
  - Public getter: `current_value_hash` for post-condition assertions
  - `value_hash()` for deterministic value references
  - Record Mode v0: execution → trace for stall/fix events

### Tooling
- **Anti-theater guardrails**
  - `--print-exec-summary` CLI flag for v2 execution summary
  - `execution_summary_v2()` pure helper (derives state from events only)
  - `tools/audit_exec_summary.sh` non-test reality anchor
  - `test_cli_print_exec_summary_end_to_end` subprocess CLI test

### Docs
- `docs/TraceReadingPrimer.v0.md` - Human-readable trace guide
- `docs/Flags.md` - Flag discipline contract
- `archive/docs/MinimalNativeExecutionPrimitive.v0.md` - Boundary question answered
- Removed `NEXT_STEPS.md` (redundant with TASKS.md)

### Tests
- v2 replay validation (`validate_v2_execution_sequence`)
- Record→Replay gate end-to-end determinism test
- Closure-as-termination fixture family (stall_at_end, stall_then_fix_then_end)

### Process
- TASKS.md is now the single canonical task tracker
- All v2 work gated by feature flags (default OFF)

Format:
- Date (YYYY-MM-DD)
- Category: Docs / Schemas / Runtime / Tests / Tooling
- Notes: Must distinguish "frozen contract" vs "future target"

## 2026-01-12

### Tooling
- Kernel step-003/004: stabilize world_trace_cli invocation (script + module); tests now 216 passed, 1 skipped.
- Verified repo green gate (212 passed, 1 skipped).
- Freeze tag created on dev: `rcx-freeze-verified-2026-01-12` → `18c2dad`.
- Quarantine cleanup / ignore rules for accidental CLI-arg files.
- Added world trace CLI (Python).
- Added core MU freezer utility (`rcx_pi_rust/scripts/freeze_core_mu.py`).

## 2026-01-03

### Docs
- Frozen external CLI + JSON contracts in `docs/RCX_OMEGA_CONTRACTS.md`.
  - Notes: This freeze reflects CURRENT runtime behavior. Any future targets (e.g., `kind=omega_summary`) are explicitly marked as future and are NOT required today.

### Schemas
- Published optional JSON Schemas under `schemas/rcx-omega/`:
  - `trace.v1.schema.json`
  - `omega_summary.v1.schema.json`
- Policy: `kind` and `schema_version` are OPTIONAL and MUST remain opt-in + environment-gated. Default runtime output remains byte-for-byte identical.

### Process
- Added staging → stable promotion checklist in `docs/STAGING_TO_STABLE.md`.

### Runtime
- No runtime changes in this entry.

## 2026-01-03

### Runtime
- Added env-gated OPTIONAL schema fields to JSON producers:
  - Set `RCX_OMEGA_ADD_SCHEMA_FIELDS=1` to inject `schema_version` (and `kind` if absent).
  - Default output remains unchanged when the env var is not set.

### Docs
- Updated `docs/RCX_OMEGA_CONTRACTS.md` with a “Runtime Reality Notes” section to reflect current behavior:
  - `kind` may be omitted or may use legacy values (e.g., `omega`).
  - `kind=omega_summary` remains a FUTURE target, not a frozen requirement.
  - `schema_version` is OPTIONAL and opt-in only.

### Tests
- Verified green gate: `python3 -m pytest -q`

## 2026-01-23

### Tests
- Enforced **orbit artifact idempotence** for tracked files.
  - Re-running `scripts/build_orbit_artifacts.sh` no longer dirties the working tree.
- Formalized **orbit provenance semantics**:
  - Provenance entries validated against emitted state transitions.
  - Supports both legacy (`from` / `to`) and current (`pattern` / `template`) schemas.
  - State entries may be strings or structured objects (e.g. `{"i": 0, "mu": "ping"}`).

### Tooling
- Added Graphviz SVG normalization to strip version-specific metadata.
  - SVG fixtures are now stable across Graphviz versions.
- Added `scripts/merge_pr_clean.sh` helper for repositories with auto-merge disabled.
  - Rebase head onto base, safe force-push, gate wait, manual merge, post-merge sync.
  - Convenience script only; repository policy unchanged.

### Process
- Confirmed layered-growth rule enforcement:
  - Kernel remains frozen.
  - All new behavior implemented via tools, fixtures, or validation layers.
- Green gate verified after each change sequence.

Notes:
- No kernel or runtime semantics were modified.
- All changes live strictly outside the frozen RCX-π core.
