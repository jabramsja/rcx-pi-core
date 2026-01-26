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

---

## Governance (Non-Negotiable)

- Do not add new subsystems, execution models, or architectures without explicit approval.
- Do not create "new tests" to bypass a failing test; fix the failing test or the code.
- Do not leave broken files/tests behind and add replacements.
- Minimize file creation. Prefer editing existing files.
- v1 replay semantics are frozen. Any new observability must be v2 and gated.
- **Pre-commit doc review**: Before committing changes to `rcx_pi/`, `prototypes/`, or `seeds/`:
  1. Read relevant docs in `docs/` (e.g., EVAL_SEED.v0.md, DeepStep.v0.md)
  2. Update docs if implementation differs from spec
  3. Update TASKS.md status if completing/progressing items

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
- Enginenews spec stress-test harness (`tests/test_enginenews_spec_v0.py`)
- CI audit gate (`tools/audit_all.sh` + `.github/workflows/audit_all.yml`)
- Closure Evidence reporting flag + CLI test (`--print-closure-evidence`, `closure_evidence_v2()`)
- Rule Motif Observability v0 (`rcx_pi/rule_motifs_v0.py`, `rules --print-rule-motifs`, 11 CLI tests)
- Rule Motif Validation Gate v0 (`validate_rule_motifs_v0()`, `rules --check-rule-motifs`, 16 CLI tests)
- Trace canon helper v1 (`canon_jsonl()`, 7 tests in `test_trace_canon_v1.py`)
- Second Independent Encounter v0 (stall memory tracking, closure signal detection, 25 tests)
- Closure Evidence Events v0 (design complete, `--print-closure-evidence` CLI, `closure_evidence_v2()` helper)
- Enginenews Spec v0 (stress test harness, 18 tests in `test_enginenews_spec_v0.py`, 4 fixtures)
- Bytecode VM v0/v1a/v1b — **ARCHIVED** (superseded by kernel + seeds approach)
  - Code: `rcx_pi/bytecode_vm.py` (legacy, not maintained)
  - Docs: `docs/archive/bytecode/` (archived)
- Mu Type v0 (`rcx_pi/mu_type.py`, `docs/MuType.v0.md`, 58 tests)
- Structural Purity Guardrails v0 (`docs/StructuralPurity.v0.md`, 32 additional tests):
  - `has_callable()`, `assert_no_callables()`, `assert_seed_pure()`
  - `assert_handler_pure()`, `validate_kernel_boundary()`
  - `tools/audit_semantic_purity.sh` extended with checks 9-11
- RCX Kernel Phase 1 (`rcx_pi/kernel.py`, `docs/RCXKernel.v0.md`, 47 tests)
- EVAL_SEED v0 (`rcx_pi/eval_seed.py`, `docs/EVAL_SEED.v0.md`, 125 tests):
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
- RCX Kernel Phase 4-5: Self-Hosting Complete:
  - Phase 4a: `match_mu()` as Mu projections (`seeds/match.v1.json`, 23 parity tests)
  - Phase 4b: `subst_mu()` as Mu projections (`seeds/subst.v1.json`, 17 parity tests)
  - Phase 4d: Integration tests (67 total: 28 parity + 27 grounding + 12 fuzzer)
  - Phase 5: `step_mu()` uses match_mu + subst_mu (33 tests: 22 parity + 11 self-hosting)
  - `tests/structural/test_apply_mu_grounding.py` - direct `step()` execution tests
  - `tests/test_apply_mu_fuzzer.py` - Hypothesis property-based tests
- Self-Hosting Security Hardening (PR #149):
  - Thread-safe step budget: `threading.local()` for concurrent execution safety
  - Cycle detection in `normalize_for_match()` and `denormalize_from_match()`
  - Global projection step budget: `_ProjectionStepBudget` class (50,000 step limit)
  - Resource exhaustion guardrails: MAX_MU_DEPTH=200, MAX_MU_WIDTH=1000
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
- QoL Infrastructure (PRs #131+):
  - Agent reports as PR comments (verifier, adversary, expert, structural-proof)
  - Debt dashboard (`tools/debt_dashboard.sh`)
  - Pre-commit local checks (`tools/pre-commit-check.sh`)
  - Projection test coverage (`rcx_pi/projection_coverage.py`)
  - Agent memory across sessions (`tools/agent_memory.py`)
  - Trace visualization (`tools/trace_viewer.py`)

---

## Boundary Question (Answered)

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

**Answer:** The Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM).
See `docs/MinimalNativeExecutionPrimitive.v0.md` for invariants and non-goals.

---

## NOW (empty by design; only populated if an invariant is broken)

*(No active items - all invariants intact)*

---

## NEXT (short, bounded follow-ups)

*(All Phase 1-5 items complete - see Ra section)*

**Future phases (not yet promoted):**

- **Phase 6**: Self-host the kernel loop (projection selection as Mu projections)
- **Phase 7**: Self-host iteration itself (recursion as structural transformation)

These are "scaffolding debt" - the kernel for-loop is Python, but operations are pure Mu.

---

## VECTOR (design-only; semantics locked, no implementation allowed)

**Active designs:**
- Debt Categories v0 (`docs/core/DebtCategories.v0.md`) - Scaffolding vs semantic debt distinction

**Completed designs (now in Ra):**
- RCX Kernel v0 (`docs/core/RCXKernel.v0.md`)
- Structural Purity v0 (`docs/core/StructuralPurity.v0.md`)
- Self-Hosting v0 (`docs/core/SelfHosting.v0.md`)
- EVAL_SEED v0 (`docs/core/EVAL_SEED.v0.md`)
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
