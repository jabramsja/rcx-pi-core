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
    - Same seeds: kernel.v1, match.v2, subst.v2, recurrence.v1, recurrence.v2, exhaustion.v1, fix.v1, hemispheres.v1, rcx_engine.v1 (47+ core projections + 11 engine + 6 fix)
    - Same bootstrap primitives: eval_step, max_steps, stack_guard, projection_loader (mu_equal DEMOTED — Level 1 Content-Addressed Mu)
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
- **L3 Parity Rule**: Changes to `mu/host/python/rcx_pi/selfhost/` (or via symlink `rcx_pi/selfhost/`) or `mu/` MUST be mirrored in `mu/host/js/eval_step.js`.
  - Run `node mu/host/js/eval_step.js` to verify all JS tests pass
  - Run `./tools/checks/check_js_debt.sh` to verify JS debt markers match Python
  - Run `./tools/checks/linters/contraband_js.sh` to verify no forbidden patterns (determinism, purity)
  - Run `./tools/checks/linters/ast_police_js.sh` to catch JS patterns that bypass grep
  - Run `./tools/checks/check_test_theater_js.sh` to catch vacuous JS assertions
  - Run `./tools/checks/linters/seed_police.sh` to verify seed integrity and no host leakage
  - New seeds must be loaded in both Python and JavaScript
  - Parity vectors must pass on both substrates before merge
- **Pre-commit doc review**: Before committing changes to `rcx_pi/` or `mu/`:
  1. Read relevant docs in `mu/docs/` (e.g., EVAL_SEED.v0.md, DeepStep.v0.md)
  2. Update docs if implementation differs from spec
  3. Update TASKS.md status if completing/progressing items
  4. Verify JS parity if projection behavior changed
- **Agent runbook**: Agent usage follows `mu/docs/agents/AgentRunbook.v0.md` (trigger map, gate rules, and evidence requirements)
- **Roadmap rule**: `ROADMAP.md` and docs in `roadmap/` define SEQUENCE and DESIGN only.
  - Current state lives in STATUS.md; authorization lives in TASKS.md
  - Gate completion updates TASKS.md (Ra/NEXT/VECTOR), not roadmap docs
  - Draft specs live in `roadmap/`; approved specs migrate to `mu/docs/core/`
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

- Tracker sync note (2026-02-18, boot1-truth-sync-wave1): Boot1 truth-sync — added exact current-reality statement to STATUS.md L4 section with file:line refs (step_mu.py:1411, step_mu.py:1578, eval_step.js:2014). Boot1LoopContract.v0.md LAST_VERIFIED updated. No phase/debt/task change.
- Tracker sync note (2026-02-18, audit-reliability-wave1): Created AuditReliabilityPlan.v0.md — root-cause writeup for jsonschema/rpds ABI fragility, 4-tier stabilization plan, preflight guidance. Tier 1 (importorskip) already applied. No phase/debt/task change.
- Tracker sync note (2026-02-18, redteam-runtime-wave1): Fix P1 kwarg collision in run_engine_with_routing — use_boot1_recursive hardcoded AND forwarded via **engine_kwargs caused TypeError. Pop from kwargs with default False. 3 regression tests added. No phase/debt/task change.
- Tracker sync note (2026-02-18, redteam-docs-tooling-wave1): Docs/tooling hardening — stale generate_docs_index.py path refs fixed, DocGovernance tree updated to mu/docs/, jsonschema test imports hardened (importorskip, health checks), world_trace_cli.py unreachable branch removed, check_boot1_merge2_readiness.sh stale symlink ref removed, trace event schema path bug fixed. No phase/debt/task change.
- Tracker sync note (2026-02-18, rigorous-review-findings-5): CONTRABAND_OK added to _apply_host_debt setattr calls (CI contraband gate failure). No phase/debt/task change.
- Tracker sync note (2026-02-18, rigorous-review-findings-4): Doc accuracy fixes from 4-phase agent review. eval_seed.py: removed stale Phase 3 goal comment, dead imports (json, Any, is_mu), fixed _match_inner isinstance count/caller claims, indentation anomaly. mu_type.py: fixed ungrounded ~4x multiplier, added MAX_MU_WIDTH to is_mu docstring, added allow_nan=False to mu_hash. deep_eval.py: fixed projection count (8→7+N), removed unused NO_MATCH import, honest DONE_MARKER security comment. shared_agent_utils.py: VT/FF/NEL sanitization, module-level json import, accurate docstring. run_review.py: structural-proof max_turns 20→30, removed 6 redundant GROUNDING_HIGH_RISK_PATTERNS. No phase/debt/task change.
- Tracker sync note (2026-02-18, rigorous-review-findings-3): Agent review iteration. Fixed validate=False depth guard bug in deep_eval.py — was traversing dict-style context but context is list [frame, outer], guard was a no-op. Now walks ctx[1]. Last Python == on Mu in test_bootstrap_primitives fixed. Stale line refs in substitute() docstring removed. No phase/debt/task change.
- Tracker sync note (2026-02-17, rigorous-review-findings-2): Design-level agent findings. Unified 4 host-debt decorators via _apply_host_debt() helper (~30 LOC reduction, all public names preserved). Deduplicated _get_base_branch() into shared_agent_utils. Bridge fuzzer now tests all 5 projections via _validate_combined_bridge_ordering. Tampered seed test rewritten: direct verify_checksum() call, no file rename fragility. No phase/debt/task change.
- Tracker sync note (2026-02-17, rigorous-review-findings): Address 9-agent review findings. Core: substitute() host debt docstring, _apply_projection_trusted lambda calculus skip documented, deep_eval lazy import→module-level, MAX_CONTEXT_DEPTH enforced even with validate=False, test_bootstrap_primitives Python==→mu_equal (8 assertions). Agent infra: sanitize_for_prompt VERDICT: redaction, CWD-relative→absolute _REPO_ROOT paths, skeptic last-match, deep_analysis always-validate, format compliance dynamic AGENT_VERDICTS, stale runner path refs fixed, CLAUDECODE auto-strip, SDK rate_limit_event patch. No phase/debt/task change.
- Tracker sync note (2026-02-17, denorm-keyerror-hardening): Red-team finding — legacy denormalization paths in match_mu.py used current["tail"] (KeyError crash on malformed inner nodes missing "tail" key). Fixed to .get("tail") matching type-tagged paths and JS behavior. 2 lines changed, 2 regression tests added. No phase/debt/runtime change.
- Tracker sync note (2026-02-17, Round 24H-legacy-deep-clean): Deep-scan cleanup after archival. Archived 6 orphaned fixtures (3 golden traces, orbit_pingpong, observer.v2.jsonl, rcx-trace-stream schema) to archive/mu_legacy_fixtures/. Removed ~130 lines of dead bytecode_vm checks from audit_semantic_purity.sh. Removed dead rcx_omega CLI probes from mutation_leaderboard_clean.sh. Fixed stale refs in 6 files (README.md, 2 design docs, conftest.py, test_doc_freshness.py, index.html). Deleted 4 empty __pycache__ dirs (core/, engine/, reduction/, utils/). 2217 tests pass. No phase/debt/runtime change.
- Tracker sync note (2026-02-16, Round 24H-legacy-archival): Archive entire pre-L3 Motif evaluator stack + legacy CLI chain (~2,500 LOC). 19 production modules, 4 schemas, 8 tests moved to archive/rcx_pi_legacy/. __init__.py now L3-only package marker. rcx_cli.py: removed program subcommand. pyproject.toml: removed 2 legacy CLI entry points. Updated 5 mixed test files, cli_smoke.py, 3 docs. infra count 44→42. 2733 tests pass, 0 new failures. No phase/debt/runtime change.
- Tracker sync note (2026-02-16, Round 24H-merge2-prep): Boot1 merge-2 caller explicitness — all 31 implicit `run_engine_pipeline()` call sites (1 production + 30 test) now pass `use_boot1_recursive=False` explicitly. Zero implicit callers remain. This is a zero-behavior-change preparation for the future default flip (merge-2). Mock-based wiring test updated to expect explicit parameter. 7 files, 45 insertions, 25 deletions. No phase/debt/runtime change.
- Tracker sync note (2026-02-16): Boot1 Wave 8 readiness hardening — G1 now verifies actual `KERNEL_RESERVED_FIELDS` definition membership (not string grep). G3 verifies exact 4 bootstrap primitives by identity. G5 checks both canonical and symlink conftest paths. G6 uses Python regex instead of brittle sed. 6 new tests: S3 boundary request security (3), primitive count invariant (3). Ratchet 52→58 fast tests, 65→71 total. No phase/debt/runtime change.
- Deterministic trace core (v1) complete
- Tracker sync note (2026-02-07): `match_mu` var-name scan cycle guard was corrected to allow shared substructures (DAG reuse) while still rejecting true active-path cycles; no phase/task promotion.
- Tracker sync note (2026-02-10): `match_mu` bridge cache defensive copy + `seed_integrity` MU_SEED_LOCATIONS moved to module level; agent verdict extraction hardened across all 9 prompts; no phase/debt/task change.
- Tracker sync note (2026-02-10): `seed_integrity` fail-closed warning on unregistered seeds + paxos_demo registration; `run_review` memory_context sanitization; translator max_turns increased; no phase/debt/task change.
- Tracker sync note (2026-02-11): `_run_sub_algorithm` budget fix — removed cross-iteration budget sharing; per-call budget in step_kernel_mu is sufficient, outer loop bounded by max_iterations. Slow test split: `test_paxos_end_to_end.py` and `test_recurrence_production.py` marked `@pytest.mark.slow`, excluded from CI fast gate, run in `audit_all.sh`; no phase/debt/task change.
- Tracker sync note (2026-02-15): `is_mu()` cycle detection changed from set-copy O(depth²) to backtracking O(depth); fuzzer max_steps reduced 100→20 for non-convergent eval.v1 inputs. Fixes 5 weekly deep fuzz timeouts. No phase/debt/task change.
- Tracker sync note (2026-02-11): Stall-detection hash caching — cache `current_hash` across loop iterations in 6 Python sites (step_kernel_mu, run_mu, run_mu_structural, _run_sub_algorithm, _resolve_trace_projection_id, projection_runner) + 4 JS sites (L3 parity). Halves hash calls per iteration. green_gate.yml: ci_fast on push (was ci_full), timeout 20→30m. 5 additional tests marked slow (3 engine pipeline, 1 hemisphere adversarial, 1 structural trace fuzzer). No phase/debt/task change.
- Tracker sync note (2026-02-11): CI green gate 28 min → 2 min — hypothesis fuzzers auto-marked via `pytest_collection_modifyitems` (452 tests deselected), 168 slow tests moved out of gate, `pytest-timeout` added to test extras, fragile grounding test fixed. Green gate runs ~2,500 core tests in ~50s CI. Nightly (ci_full) still runs everything. No phase/debt change.
- Tracker sync note (2026-02-11): Static speed enforcer — `tools/checks/check_test_speed.sh` grep-based detection of test files importing slow kernel functions without `@pytest.mark.slow`. Integrated into `tools/pre-commit-doc-check` (section 4b). 7 existing violations fixed. No phase/debt change.
- Tracker sync note (2026-02-16, Round 24H-boot1-wave2): Boot1 budget accounting fix — `_run_engine_recursive` (Python + JS) was passing full `max_engine_iterations` to recursive calls instead of remaining budget. Contract §3/S2 violation: total budget could reach 20*20=400 iterations. Fix: pass `max_engine_iterations - iteration - 1` (remaining budget after current step). Also fixed pre-existing ROOT path bug in `test_boot1_shadow_parity.py` (2 dirnames → 3, unblocking 4 cross-substrate tests). 4 new budget accounting tests (S2 shared budget, monotonically decreasing, low-budget fail-closed, trampoline equivalence). 24/24 Boot1 tests pass. No phase/debt change.
- Tracker sync note (2026-02-12): JS engine-hemisphere parity — `runEnginePipeline`, `hashTraceForRecurrence`, `runHemisphereRouting`, `runEngineWithRouting` added to `eval_step.js`. rcx_engine.v1.json + recurrence.v2.json now loaded in JS. 4 JSON API actions, 6 inline tests, 6 cross-substrate parity tests (36 total pass). `_state_hash`/`_check_hash` added to JS ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS (pre-existing parity gap). JS debt: 13→15. No phase change.
- Hemisphere hardening (2026-02-12, PR #239): caller-trust model (`_step_trusted`/`_apply_projection_trusted`), JS parity (substitute throw, isKernelIntermediate, inject_key guard, `||`→`??` numeric defaults, hard-cap 100k parity, RcxError at boundaries), boundary result validation in engine pipeline, `_walk_and_validate` shared traversal, dead code removal (eval_seed.py), test dedup (`hemisphere_helpers.py`, `EXPECTED_PROJECTION_IDS`, DummyBudget consolidation). 3 rounds of 9-agent rigorous review. No phase/debt change.
- HF2 maxSteps guard (2026-02-10): `guardMaxSteps()` enforces type (integer), range (>=0), and cap (<=10000) on all 8 maxSteps-accepting JSON API endpoints. Closes HF2 Mode-B DoS vector. Manifest: 14/18 actions now `requires_error_edges=true`. 169 parity/coverage tests green.
- N1b typed-error parity (2026-02-13): 14 JS boundary throw sites converted from untyped `Error`/`TypeError` to `RcxError` with stable `error_code` (normalize, step/run/runStructural, validateNoKernelReservedFields, validateAlgorithmRuntimeFields, runHemisphereRouting, runEngineWithRouting). Manifest ratchet: all 18 actions declare `requires_error_edges`; 10 with error edges, 8 with `success_only_reason`. 22 error_code parity tests + 8 ratchet invariant tests. No phase/debt change.
- Mu Hemispheres v0 — Engine integration COMPLETE (2026-02-11): `run_engine_with_routing()` chains `run_engine_pipeline()` → `run_hemisphere_routing()` with fail-closed input/output validation. `hash_trace_for_recurrence` cycle guard added (visited set + 10000 iteration cap). 10 integration tests (8 fast + 2 slow). Paxos livelock → closure → r_a proven end-to-end.
- Tracker sync note (2026-02-15, Round 24D): Convergence Execution — `tools/`, `scripts/`, `tests/` physically moved under `mu/` via `git mv`. Root symlinks (`tools -> mu/tools`, `scripts -> mu/scripts`, `tests -> mu/tests`) created as backward-compat shims (removal in 24E). Shell scripts converted to `git rev-parse --show-toplevel` for repo-root navigation. `.resolve()` removed from 25 Python REPO_ROOT computations (symlink-safe). Git-path-dependent configs updated: `enforce_tracker_sync.sh`, `pre-commit-doc-check`, `docs_registry.json`, `run_review.py`, `run_ci_review.py` (mu/ prefix for git paths). Root layout guard made index-aware. `pyproject.toml`/mypy kept on symlink namespace (`tools.shared_*`). ~340 files moved, 3 symlinks, ~40 targeted fixes. No phase/debt/runtime change.
- Tracker sync note (2026-02-14, Round 24C): Root Noise Collapse — `docs/` and `roadmap/` directories fully emptied, contents moved to `mu/docs/` (96 active files) and `archive/docs/` + `archive/roadmap/` (41 archived files). 231 path rewrites across 161 files. All 14 seed checksums updated (meta.doc path changes). `enforce_tracker_sync.sh` updated to exclude `mu/docs/` from core-change detection. No phase/debt/runtime change.
- Tracker sync note (2026-02-16): Roadmap visibility relocation — `ROADMAP.md` moved to repo root and roadmap specs moved to root `roadmap/`. Governance/tooling/tests updated (docs registry special folder, root canonical docs, pre-commit docs trigger, roadmap governance paths). No phase/debt/runtime change.
- Tracker sync note (2026-02-16, Round 24H-wave3): Mu/tests root-level ratchet Wave 3 — moved 6 test files to subdirectories: test_closure_evidence_cli.py → cli/, test_replay_cli_skeleton_v1.py → cli/, test_world_doc_tool.py → scripts/, test_world_score_tool.py → scripts/, test_fix_invariants.py → structural/, test_debt_enforcement.py → tools/. Path fixes (parents[N] adjustments, 4 files). Reference updates: audit_fast.sh, test_engine_cycle_mapping.py, EngineNewFixContract.v0.md, TASKS.md. Ratchet ceiling lowered 24 → 18. BLOCKED_REVIEW: test_agent_tooling_smoke.py (namespace collision with tests/tools/__init__.py shadows repo root tools/ package). No phase/debt/runtime change.
- Tracker sync note (2026-02-16): Subtree governance — 22 test files moved from `mu/scripts/tests/` to `mu/tests/scripts/` (taxonomy rule: tests never live in mu/scripts or mu/tools). `enginenews_vectors.json` archived (0 test references). Structural guard added (`test_subtree_taxonomy_guard.py`) preventing future drift. Path fixes: `parents[2]→parents[3]` (18 sites) + `docs/→mu/docs/` (6 sites). Net: 41 pass (was 40), 7 pre-existing failures unchanged. No phase/debt/runtime change.
- Tracker sync note (2026-02-16): Boot1 Loop Contract promoted VECTOR → NEXT. Founder decision D1=YES (shadow-merge scope only: no default flip, no trampoline removal). All 6 promotion criteria satisfied: (1) design doc complete and adversary-reviewed, (2) ABI compatibility demonstrated (shared `{_run_engine: ...}` envelope), (3) parity test plan drafted (6 test categories in contract doc), (4) security review: no new bypass paths or primitive count increase, (5) P1-P3 prerequisites all RESOLVED (Rounds 17D, 20B, 20C), (6) explicit promotion in TASKS.md with rationale. Deferred decisions recorded: D2 Checkpoint/Resume DEFER, D4 L4 DEFER, D5 Import rewrite DEFER. No phase/debt/runtime change.
- Hemisphere hardening Phases 1–4 CLOSED (2026-02-13, no runtime changes): P1 routing priority confirmed correct across all 4 layers (seed, Python, JS, tests — 130 hemisphere + 28 JS parity tests); P4 JS falsy-default `??` already correct for all 14 numeric caps, regression lock added (`TestNoOrBarBarNumericDefaults`); P2a `import ast` confirmed absent from `rcx_pi/`, structural guard added (`test_ast_import_guard.py`); P3a hemisphere output validation already exact-keyset + typed RcxError + cross-substrate parity. Commits: `d2a7cac` (PR #245 GAP-04-FIX contract), `c73d68b` (PR #246 test hardening). No phase/debt change.
- Hemisphere hardening Phase 6 already complete (2026-02-13): Parity manifest (`tests/fixtures/js_api_parity_manifest.json`, 18 actions, 10 error codes, 3 types), `RcxError` + `classifyError()` in JS (16 catch sites), `list_actions` API action, `classify_python_error()` in test layer, `TestActionSetSync`/`TestParityCoverageGate`/`TestManifestEdgeCaseParity` test classes, `@pytest.mark.slow` tier split. 169 parity tests pass. Hemisphere hardening stream CLOSED (all 6 phases).
- Tracker sync note (2026-02-16, Round 24H-turbo2): Repo curation turbo wave 2 — archived check_orbit_all.sh (CI calls individual gates), CI_PING.md (one-time trigger artifact). Tightened Why_RCX_PI_VM_EXISTS.md: removed hardcoded Phase 8b (drifted), added STATUS.md deference, clarified L3 complete / L4 not started, PureEvaluator as legacy, bridge kernel as active default, world_trace_cli bridge dependency. No phase/debt/runtime change.
- Tracker sync note (2026-02-16, Round 24H-turbo1): Repo curation turbo wave — archived 7 Tier A files (0 imports, 0 CI usage): manifest cluster (rcx_manifest.py, .sh, _minimal.py, rcx_packlist.py), merge_pr_clean.sh, open_fixtures.sh, worlds_mutate_engine.py (broken import). Docstring-only edit to worlds/__init__.py. No phase/debt/runtime change.
- Tracker sync note (2026-02-13, Round 15I): GAP-04-FIX E1–E5 execution CLOSED. E1: gap proven pre-integration in Round 15D (`TestImplicitFixFailure`, since renamed to `TestFixIntegrationEvidence` after E4 closed the gap). E2: `mu/closures/fix.v1.json` v1.1.0 (6 projections, idempotence guards). E3: 19 invariant tests (`tests/structural/test_fix_invariants.py`, I1–I5). E4: `mu/programs/rcx_engine.v1.json` v1.2.0 (10 projections, 3 fix-dispatch). E5: TASKS closure + contract update. Cross-substrate parity locked (4 fix-path tests). EngineNew tally: 9/10 structural, 1/10 gap (GAP-10-LOOP only). No phase/debt change.
- Tracker sync note (2026-02-14, Round 17A): Boot1 Recursive Loop Contract design doc created (`mu/docs/core/Boot1LoopContract.v0.md`). 7 sections: purpose/non-goals, ABI compatibility (`{_run_engine: ...}` envelope preserved), recursive/tail-call semantics (Option A: structural `_tail_call` preferred), 7 safety invariants (S1–S7), parity plan (6 test categories), cutover mapping (6 gates + 3-merge rule), open questions (4). Still VECTOR — awaiting founder review before any VECTOR → NEXT promotion. No phase/debt/runtime change.
- Tracker sync note (2026-02-14, Round 17B): Boot1 contract adversary review — **R1: keep in VECTOR** (not promotable yet). Findings: (a) `_tail_call` classification AMBIGUOUS — `eval_step` primitive unchanged, but host loop gains new branch; contract corrected to accurately attribute structural inspection to `run_engine_pipeline` not `eval_step`. (b) Engine-specific scope CONFIRMED — general-purpose `_tail_call` enables projection set injection. (c) Security verdict REQUIRES_HARDENING — 3 prerequisites: P1 (JS boundary result validation gap at `eval_step.js:1954`, existing parity gap), P2 (`_run_engine` not in KERNEL_RESERVED_FIELDS, existing gap), P3 (`_tail_call` must be reserved from day one). Contract doc updated with all corrections. No phase/debt/runtime change.
- Tracker sync note (2026-02-14, Round 17D): P1 parity hardening — JS `runEnginePipeline` boundary result validation added (`validateNoKernelReservedFields` before injection, parity with Python). 2 regression lock tests. No phase/debt change.
- Tracker sync note (2026-02-14, Round 17P): Unicode key-order parity fix — JS `muHash`, `muHashCached`, and `normalize` now use `compareMuStringKeysByCodepoint()` (full code-point comparison) instead of default UTF-16 sort. Fixes divergence for mixed BMP/non-BMP keys (e.g. U+F900 vs U+10000). Regression test added. Boot1 P2 wording updated (stale P1-unfixed reference removed). No phase/debt change.
- Tracker sync note (2026-02-14, Round 21D): Archive move execution — removed all LEGACY_GUARDED rcx_pi_rust fallbacks (program_descriptor.py, world_score.sh, mutation_sandbox.sh, green_examples.sh, green_gate.sh). Archived 3 worlds modules (worlds_bridge, worlds_mutate_demo, worlds_mutate_loop) to rcx_pi/worlds/archive/. Archived 2 rcx_omega tests to tests/archive/legacy/. Cleaned configs: rcx_manifest.py, rcx_packlist.py, rcx_manifest_minimal.py, CODEOWNERS, RCX_MINIMAL_SPINE_MANIFEST.json. Deleted rust_examples.yml workflow. Emptied both grandfathered allowlists. No phase/debt change.
- Tracker sync note (2026-02-14, Round 21C): Move-readiness decoupling — `mu/mu_programs/` created as active `.mu` fixture home (4 world files). 7 files repointed from `rcx_pi_rust/mu_programs/` → `mu/mu_programs/`. Guardrail tightened: `GRANDFATHERED_RCX_PI_RUST_PATHS` emptied, `test_no_rcx_pi_rust_in_new_scripts` added. 3 previously-skipped tests now executing. Archive move plan updated with 21C status and remaining 21D blockers. No phase/debt change.
- Tracker sync note (2026-02-14, Round 17O): Red-team R0–R4 cycle CLOSED. R0: P1 hemisphere routing priority confirmed correct, merged via PR #249. R1: no blocking runtime boundary findings. R2b: property-based cross-substrate fuzzers (1000 Hypothesis examples across 9 test methods), merged via PR #250. R3: differential replay audit (300+ cases, 84 pass, no success/failure mismatches). R3-F1: classify_python_error gap remediated in test-layer (hemisphere RuntimeError → input.shape_mismatch). R4: governance/docs closure (this note). Boot1 blocker status at that time: P1 = RESOLVED (Round 17D), P2/P3 open (later resolved in Rounds 20B/20C). No phase/debt/runtime change.
- Tracker sync note (2026-02-14, Rounds 20B/20C): Boot1 security prerequisites P2/P3 resolved — `_run_engine` and `_tail_call` added to `KERNEL_RESERVED_FIELDS` in both Python and JS. Reserved-field counts and parity tests updated. No phase/debt change.
- Tracker sync note (2026-02-16): mu/mu_programs sandbox hygiene — deleted 205 untracked `__sandbox_run_*` temp files, created `mu/mu_programs/sandbox/` directory for future sandbox output, `.gitignore` updated. 5 canonical `.mu` files untouched. No phase/debt/runtime change.
- Tracker sync note (2026-02-16, Round 24E): Boot1 shadow merge (merge 1 of 3-merge cutover). Python: `_run_engine_recursive()` + `use_boot1_recursive` flag + `_tail_call` recognition in `run_engine_pipeline()`. JS: `runEnginePipelineRecursive()` + `boot1LoopMode` JSON API + `_tail_call` recognition. 20 parity/safety/security tests. JS debt 15→16. AST_OK:infra 41→44. No phase/debt change (Boot1 is shadow-only, trampoline remains default).
- Tracker sync note (2026-02-14, Round 17C): Founder clarification accepted — general-purpose semantics via seed/gate profiles (acyclic, cyclic-AFA, HoTT-style, SKI-style rewrite); engine-local `_tail_call` remains scoped as control-plane protocol, not domain opcode. "Control Plane vs Semantic Profiles" subsection added to Boot1LoopContract.v0.md. Red-team staging policy recorded: R0 (P1 critical parity hardening) → R1 (runtime security parity review) → R2 (fuzz/property sweep) → R3 (differential cross-substrate replay) → R4 (governance/docs/contract consistency closure). Immediate: targeted red-team on P1 parity gap. Full-stack phased red-team only after P1 + contract blockers green. No phase/debt/runtime change.
- GAP-10-LOOP founder GO-CONDITIONAL (2026-02-14, Round 16D governance): Trampoline labeled TRANSITIONAL (not terminal L4). Boot1 Sunset Policy + 6 Cutover Gates + 3-merge Cutover Rule added to NEXT. Boot1 Recursive Loop Contract opened as parallel VECTOR item with 5 promotion criteria. Mandatory constraints: no new host semantics, re-entry ABI Boot1-compatible from day 1, explicit sunset trigger. Staged bootstrap precedent: GCC 3-stage, Rust stage0→stage2, Hex0/Stage0. No phase/debt change.
- GAP-10-LOOP E5 CLOSED (2026-02-14, Round 16E): EngineNew 10/10 structural, 0 gaps. E1–E4 evidence: rcx_engine.v1.json v1.3.0 (11 projections, _config carry-through, trampoline split), 8 invariant tests + 1 pipeline test + 3 cross-substrate parity tests. Acceptance battery: seed_police (15/15), cycle_mapping (17/17), integration (33/33), parity (16/16), loop parity (3/3), seed_counts (139/139), JS inline (all pass). Checkpoint/Resume Contract opened as new VECTOR item. No phase/debt change.
- GAP-10-LOOP promoted VECTOR → NEXT (2026-02-13, Round 16C): Trampoline architecture (Option B) chosen over Boot1 recursive kernel (Option A). Boot1 evaluated and deferred — effect handler loop is accepted irreducible bootstrap primitive (Boot0 v0.4); gap is the loop-back decision, not the handler. Trampoline: `engine.exhaustion_done` splits into `freeze` (re-enters engine.init_config) + `terminal` (produces engine_result). `_config: {projections, max_steps}` threaded through all intermediate projections. 10→11 projections. Zero host code changes. E1-E5 evidence plan approved. No phase/debt change.
- GAP-04-FIX promoted VECTOR → NEXT (2026-02-13, Round 15C): E1–E5 plan approved (Round 15B). Design contract test-locked, all prerequisites satisfied. Execution authorized under NEXT; E1 starts next. No phase/debt change.
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
  - audit_exec_summary.sh (removed — dead code; subprocess CLI test is the reality anchor)
- Trace Reading Primer (`mu/docs/execution/TraceReadingPrimer.v0.md`)
- Record→Replay Gate (`test_record_replay_gate_end_to_end`)
- Flag Discipline Contract (`mu/docs/cli/Flags.md`)
- Consume execution.fix from trace (true cycle replay)
- Closure-as-termination fixture family (`stall_at_end.v2.jsonl`, `stall_then_fix_then_end.v2.jsonl`)
- IndependentEncounter pathological fixtures + tests
- Recurrence spec stress-test harness (`tests/integration/test_recurrence_spec_v0.py`)
- CI audit gate (`tools/audit_all.sh` + `.github/workflows/audit_all.yml`)
- Closure Evidence reporting flag + CLI test (`--print-closure-evidence`, `closure_evidence_v2()`)
- Rule Motif Observability v0 (`rcx_pi/rule_motifs_v0.py`, `rules --print-rule-motifs`, 11 CLI tests)
- Rule Motif Validation Gate v0 (`validate_rule_motifs_v0()`, `rules --check-rule-motifs`, 16 CLI tests)
- Trace canon helper v1 (`canon_jsonl()`, 7 tests in `test_trace_canon_v1.py`)
- Second Independent Encounter v0 (stall memory tracking, closure signal detection, 25 tests)
- Closure Evidence Events v0 (design complete, `--print-closure-evidence` CLI, `closure_evidence_v2()` helper)
- Recurrence Spec v0 (stress test harness, 18 tests in `test_recurrence_spec_v0.py`, 4 fixtures)
- Bytecode VM v0/v1a/v1b — **ARCHIVED** (superseded by kernel + seeds approach)
  - Code: `archive/mu_legacy/host/python/rcx_pi/bytecode_vm.py` (archived)
  - Docs: `archive/docs/bytecode/` (archived)
- Mu Type v0 (`rcx_pi/mu_type.py`, `mu/docs/core/MuType.v0.md`, 58 tests)
- Structural Purity Guardrails v0 (`mu/docs/core/StructuralPurity.v0.md`, 32 additional tests):
  - `has_callable()`, `assert_no_callables()`, `assert_seed_pure()`
  - `assert_handler_pure()`, `validate_kernel_boundary()`
  - `tools/audit_semantic_purity.sh` extended with checks 9-11
- RCX Kernel Phase 1 (`rcx_pi/kernel.py`, `mu/docs/core/RCXKernel.v0.md`, 47 tests)
- EVAL_SEED v0 (`rcx_pi/eval_seed.py`, `mu/docs/core/EVAL_SEED.v0.md`, 125 tests):
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
  - `tests/fuzz/test_apply_mu_fuzzer.py` - Hypothesis property-based tests
- Self-Hosting Security Hardening (PR #149):
  - Thread-safe step budget: `threading.local()` for concurrent execution safety
  - Cycle detection in `normalize_for_match()` and `denormalize_from_match()`
  - Global projection step budget: `_ProjectionStepBudget` class (50,000 step limit)
  - Resource exhaustion guardrails: MAX_MU_DEPTH=300, MAX_MU_WIDTH=1000
  - Comprehensive fuzzer tests (`tests/fuzz/test_selfhost_fuzzer.py`, 53 tests, 10,000+ examples):
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
  - Agent memory across sessions (`tools/runners/agent_memory.py`)
  - Trace visualization (removed — dead code; no callers)
- Seed Integrity Verification (PR #157):
  - SHA256 checksum verification for seed files (match.v1.json, subst.v1.json)
  - Structure validation (meta, projections keys, required fields)
  - Projection ID verification (expected IDs present, wrap is last)
  - 27 tests in `tests/engine/test_seed_integrity.py`
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
  - 26 new tests in `tests/engine/test_classify_mu.py`
- Boot0 Architecture v0.4 (`mu/docs/core/Boot0Architecture.v0.md`) - 9-agent reviewed 2026-01-31:
  - Hex0-inspired staged bootstrap design: Boot0 → Boot1 → Boot2
  - 4 irreducible bootstrap primitives: eval_step, max_steps, stack_guard, projection_loader (mu_equal eliminated via Level 1 Content-Addressed Mu)
  - Boot0=structural, Boot1=none, Boot2=kernel validation boundaries
  - v0.4: Added "stable semantics, shrinking substrate", JSON as Phase 0 format, explicit handshake ABI, security invariants, L3 parity contract
  - Design COMPLETE, implementation DEFERRED per 9-agent Advisor recommendation
  - L3 is complete; Boot0 extraction can wait until L4 research drives it
- mu_equal DEMOTED from Bootstrap Primitive (2026-02-10, Content-Addressed Mu Level 1):
  - **Level 1 IMPLEMENTED**: `mu_hash_cached()` replaces all 8 production call sites (eval_seed 2, step_mu 5, projection_runner 1)
  - Bootstrap primitives: 5 → 4. `mu_equal` retained as convenience wrapper only.
  - JS parity: `muHashCached()` added, `muEqual()` delegates. 6 JS call sites updated.
  - Paxos e2e pipeline test: `tests/integration/test_paxos_end_to_end.py` (6 tests) validates deadlock metabolization
  - Historical: 9-agent consensus (2026-01-31) confirmed json.dumps IS structural equality for JSON data
  - Parity fuzzer: `tests/fuzz/test_mu_equal_parity_fuzzer.py` (13 tests, 500+ inputs)
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
  - Created `tests/parity/test_rcx_engine_parity.py` - 15 tests
  - All 6 engine projections now tested (grounding agent finding addressed)
  - Note (historical, superseded by Round 16E): at this stage rcx_engine was `design_only`; engine projections are now in production via `run_engine_pipeline()`.
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
See `archive/docs/MinimalNativeExecutionPrimitive.v0.md` for invariants and non-goals.

---

## NOW (empty by design; only populated if an invariant is broken)

*(No active items - all invariants intact)*

---

## NEXT (short, bounded follow-ups)

- [ ] **Boot1 Recursive Loop Contract** — Shadow-merge implementation of recursive kernel loop primitive alongside existing trampoline. Authorized (2026-02-16, founder decision D1=YES). **Scope (shadow-merge only):** (a) Implement Boot1 recursive self-re-entry path as alternate code path, (b) parity tests proving Boot1 loop == trampoline on canonical vectors, (c) NO default flip (trampoline remains default), (d) NO trampoline removal. **Design doc:** `mu/docs/core/Boot1LoopContract.v0.md` (adversary-reviewed, P1-P3 resolved). **Security prerequisites (all green):** P1 JS boundary result validation (Round 17D), P2 `_run_engine` reserved (Round 20B), P3 `_tail_call` reserved (Round 20C). **Evidence plan:** E1 shadow implementation (Python), E2 JS parity, E3 canonical vector parity tests (freeze/non-freeze/stall/fix paths, both substrates), E4 security regression tests, E5 TASKS closure.

- ~~**GAP-10-LOOP**~~ — Structural iteration control. **CLOSED** (2026-02-14, Round 16E). EngineNew 10/10 structural, 0 gaps.
  - **Summary**: TRANSITIONAL trampoline via `_config` carry-through. `engine.exhaustion_done` split into `exhaustion_done_freeze` (action="freeze" → `{_run_engine: ...}`, re-enters `engine.init_config`) and `exhaustion_done_terminal` (any other action → `{engine_result: ...}`, terminal). `_config: {projections, max_steps}` threaded through all 8 intermediate projections. Zero host code changes. 10 → 11 projections. Boot1 sunset policy in effect (see VECTOR: Boot1 Recursive Loop Contract).
  - **Evidence (E1–E4, Round 16D runtime)**:
    - E2: `rcx_engine.v1.json` v1.3.0 (11 projections, `_config` carry-through, trampoline split). Checksums + projection IDs updated in seed_integrity.py + eval_step.js.
    - E1/E3: 8 projection-level invariant tests (`TestLoopTrampolineProjectionLevel`) + 1 pipeline-level test. All existing tests updated (seed_counts, parity, cycle_mapping, vectors, integration).
    - E4: 3 cross-substrate parity tests (`TestEngineLoopPathParity`) — freeze pipeline, non-freeze terminal, no config leak.
    - Acceptance battery: seed_police (15/15), cycle_mapping (17/17), integration (33/33), parity (16/16), loop parity (3/3), seed_counts (139/139), JS inline (all pass).
  - **Mandatory constraints** (founder directive, Round 16D): Trampoline is TRANSITIONAL (not terminal L4). No new host semantics. Re-entry ABI Boot1-compatible. Boot1 sunset trigger active (see VECTOR). Parallel VECTOR item: Boot1 Recursive Loop Contract.

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
- Checkpoint/Resume Contract (bounded continuation semantics) — Explicit pause/resume semantics when engine or algorithm limits are hit. **Opened** (2026-02-14, Round 16E). **Founder decision D2=DEFER** (2026-02-16): not promoted; remains in VECTOR for future consideration. **Invariants**: (1) Limit hit is explicit (no silent truncation), (2) Hash verifies state integrity; hash alone is not resumable state, (3) Resume token carries full continuation state (or validated pointer), state_hash, seed/version checksums, and budget metadata, (4) Resume path preserves Python/JS parity, (5) Resume path reuses existing validation/security guards, (6) No bootstrap primitive count increase without explicit approval. **Promotion criteria (all required for VECTOR → NEXT):** (1) Contract doc drafted and approved, (2) Canonical token schema defined, (3) Cross-substrate parity test plan defined, (4) Security review complete, (5) Explicit VECTOR → NEXT promotion in this file with rationale.
- Content-Addressed Mu (`roadmap/ContentAddressedMu.md`) - Every Mu value carries a content hash; equality becomes O(1). **Levels 0-2 IMPLEMENTED** (L0: boundary hashing, L1: mu_equal eliminated 5→4, L2: frozen hashes — state dropped from _seen, ~77% memory savings). **Level 3 (Trie) DEFERRED** — analysis shows 5x slower for production traces (<50 steps), break-even at ~100 steps. Revisit if traces routinely exceed 100 steps.
- Debt Categories v0 (`mu/docs/core/DebtCategories.v0.md`) - Scaffolding vs semantic debt distinction
- Projection Indexing - Preprocess projections into structural trie/decision-tree for O(log N) matching instead of O(N) linear scan. Index is Mu data (structural). **Promotion criteria:** Profile real workloads first; if projection matching is >50% of runtime, promote to NEXT.
- Hemisphere Metabolization Contract (`roadmap/MuHemispheresDesign.md` § "FUTURE_TARGET: Hemisphere Metabolization Contract") - Sink re-expression cycle: sink → (r_inf | r_null) metabolization → (lobes | r_a) storage → residual → sink. Stall recovery: lobes-first, then sink. 6 projection IDs designed (pattern/body sketches). Engine exception policy dependency documented (Option A active, Option B designed). **Promotion criteria (all required for VECTOR → NEXT):**
  - Re-expression trigger model decided (automatic + manual/debug, per founder directive) ✓ designed
  - At least 4 metabolization projection specs drafted with pattern/body ✓ 6 designed
  - Extended truth-table coverage criteria defined (≥8 metabolization transitions) ✓ 10 transitions (T1-T10), 3 adversarial, all 5 buckets covered
  - Engine exception policy Option B (synthesized routable terminal → sink) designed with sink-safety invariants ✓ 8-field synthesized shape, 5 sink-safety invariants (S1-S5), 6 adversarial test specs (ADV-B1 to ADV-B6), 4 code touchpoints verified, enablement guard defined
  - Explicit VECTOR → NEXT promotion in this file with rationale before any implementation

**EngineNew gap contracts** (locked by `tests/structural/test_engine_cycle_mapping.py::TestGapRegistry`):
- ~~GAP-04-FIX~~ — **CLOSED** (2026-02-13, Round 15I). E1–E5 complete. `fix.v1.json` (6 projections) + `rcx_engine.v1.json` (10 projections, 3 fix-dispatch). 19 invariant tests, 4 cross-substrate parity tests. EngineNew 9/10 structural.
- ~~GAP-10-LOOP~~ — **CLOSED** (2026-02-14, Round 16E). E1–E4 complete. Trampoline makes loop-back decision structural (11 projections). 10/10 EngineNew steps structural. Boot1 Recursive Loop Contract remains open as parallel VECTOR item for L4 path.

**Reference:**
- Corpus Status Registry (`mu/docs/corpus_registry.csv`) - 18-artifact classification with taxonomy labels, confidence scores, and evidence refs. Ontology-to-runtime mapping reference for VECTOR design work.

**Promoted to NEXT:**
- ~~Mu Hemispheres v0~~ (`roadmap/MuHemispheresDesign.md`) - **PROMOTED TO NEXT** (2026-02-09, Gate 5 blocker resolved)
- ~~Boot1 Recursive Loop Contract~~ (`mu/docs/core/Boot1LoopContract.v0.md`) - **PROMOTED TO NEXT** (2026-02-16, founder D1=YES). Shadow-merge scope: no default flip, no trampoline removal. All 6 promotion criteria satisfied. P1-P3 resolved.

**Completed (moved to Ra):**
- ~~Operator Exhaustion v0~~ (`mu/docs/core/OperatorExhaustion.v0.md`) - **MOVED TO Ra** (IMPLEMENTED 2026-02-02)
  - Step 6 complete: 11 projections in `mu/closures/exhaustion.v1.json`
  - 27 tests (17 parity + 10 fuzzer), cross-substrate parity verified

**Historical promotion (completed):**
- Meta-Circular Kernel v0 (`mu/docs/core/MetaCircularKernel.v0.md`) - promoted 2026-01-27, implemented and archived in `Ra`

**Completed designs (now in Ra):**
- RCX Kernel v0 (`mu/docs/core/RCXKernel.v0.md`)
- Structural Purity v0 (`mu/docs/core/StructuralPurity.v0.md`)
- Self-Hosting v0 (`mu/docs/core/SelfHosting.v0.md`)
- EVAL_SEED v0 (`mu/docs/core/EVAL_SEED.v0.md`)
- EngineNews Structural v0 (`mu/docs/core/EngineNewsStructural.v0.md`) - Step 5 closure detection
- Operator Exhaustion v0 (`mu/docs/core/OperatorExhaustion.v0.md`) - Step 6 operator freeze
- Second Independent Encounter (`mu/docs/execution/IndependentEncounter.v0.md`)
- Enginenews Spec Mapping (`mu/docs/execution/EnginenewsSpecMapping.v0.md`)
- Closure Evidence Events (`mu/docs/execution/ClosureEvidence.v0.md`)
- Rule-as-Motif (`mu/docs/execution/RuleAsMotif.v0.md`)

**Archived (superseded):**
- Bytecode VM v0/v1 → `archive/docs/bytecode/`

---

## SINK (ideas parked; may not advance without explicit promotion decision)

- Multi-value/concurrent execution
- Performance-first optimizations
- ~~Full VM bootstrap / meta-circular execution~~ → Promoted to VECTOR #14 (RCX Kernel v0)
- Projection caching optimization (post-Phase 8) - cache normalized projections for repeated use; use content-based hash, NOT id(). From withdrawn KernelSeedRealignment.v0.md.

**Legacy Surface Tracker (Round 19D, 2026-02-14):**
Decision record: `mu/docs/core/LegacySurfaceDecisionRecord.v0.md`
- `rcx_pi_rust/` — ARCHIVED Round 23A (moved to `archive/rcx_pi_rust/`)
- `rcx_omega/` — ARCHIVED Round 23A (moved to `archive/rcx_omega/`)
- `mu/worlds_json/` — MAINTAIN as test fixtures (moved from root Round 23B); `rcx_core_mut4.json` removed Round 22J (was byte-identical to mut3)
- `Makefile` — ARCHIVED Round 23E (moved to `archive/root_legacy/`)
- `rcx_runtime.py` — ARCHIVED Round 23E (moved to `archive/root_legacy/`)
- `rcx_start.py` — ARCHIVED Round 23E (moved to `archive/root_legacy/`)
- `.rcx_manifest.json` — UNTRACKED Round 23F (generated artifact, stays on disk)
- `archive/rcx_pi_rust/sanity_test/target/` — UNTRACKED Round 23F (23 Rust build artifacts)
- `archive/docs/latex/rcx-pi-paper.pdf` — UNTRACKED Round 23F (gitignored by `*.pdf`)
- Round 24A: Deleted 5 dead archive files (corpus/, normalized_prototype/, prototypes/); archived 6 deprecated scripts to `archive/scripts_deprecated/`; archived 3 stale roadmap gate docs to `archive/docs/`
- Round 24B: Recursive subfolder sweep — fixed DeepStep.v0.md stale refs; deleted moves_22b_specs.json (stale); deleted archive/scripts_deprecated/ (6 files); deleted 31 agent archive files (tools/, docs/, .claude/); deleted 16 zero-ref archive/docs/ files; cleaned governance exclusion patterns
- Round 24C: docs/ + roadmap/ → mu/docs/ convergence — 96 active files moved to `mu/docs/` (core, agents, cli, schemas, fixtures, execution, audit, reviews, roadmap), 41 files archived to `archive/docs/` + `archive/roadmap/`. Both `docs/` and `roadmap/` directories fully emptied. 231 path rewrites across 161 files. All 14 seed checksums updated (Python + JS). `enforce_tracker_sync.sh` updated to exclude `mu/docs/` from core-change detection. 5 test files with hardcoded `docs/` Path() references fixed. Reclassification guard enforced: zero-ref proof required for every ARCHIVE candidate

Tracker sync note (2026-02-17, doc-drift-sync-deprecation): Comment-only changes — added DEPRECATED annotations to rcx_cli.py (archived program subcommand), worlds_probe.py, world_trace_cli.py, worlds/__init__.py (Rust bridge paths). Removed dead _rcx_dispatch function. Deleted 5 orphaned .pyc files. Added "Deprecated & Archived Code" section to rcx_pi/README.md explaining why Rust bridge paths remain and what was archived in Round 24H. No behavior/phase/debt change.
