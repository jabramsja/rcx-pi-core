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
- Bytecode VM v0 (replay-only, 10 opcodes, 47 tests in `test_bytecode_vm_v0.py`, `tools/audit_bytecode.sh`)
- Bytecode VM v1a (OP_STALL execution, v1a registers RS/RP/RH, closure detection, 61 tests)
- Bytecode VM v1b (OP_FIX/OP_FIXED execution, RF register, stall_memory clearing, 78 tests)
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

---

## Boundary Question (Answered)

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

**Answer:** The Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM).
See `docs/MinimalNativeExecutionPrimitive.v0.md` for invariants and non-goals.

---

## NOW (empty by design; only populated if an invariant is broken)

_(No active items.)_

---

## NEXT (short, bounded follow-ups: audits, stress tests, fixture hardening)

20. **RCX Kernel Phase 1: Minimal Kernel** ✅ (complete)
    - Design doc: `docs/RCXKernel.v0.md`
    - Implementation: `rcx_pi/kernel.py`
    - Tests: `tests/test_kernel_v0.py` (47 tests)
    - Done:
      - 4 primitives: `compute_identity`, `detect_stall`, `record_trace`, `gate_dispatch`
      - Kernel class with `step()` and `run()` main loop
      - All handlers wrapped with `assert_handler_pure`
      - Audit passes (17 checks)
    - **Ready for Phase 2**

21. **RCX Kernel Phase 2: EVAL_SEED (Python)** ✅ (complete)
    - Design doc: `docs/EVAL_SEED.v0.md`
    - Implementation: `rcx_pi/eval_seed.py`
    - Tests: `tests/test_eval_seed_v0.py` (71 tests)
    - Done:
      - `match(pattern, input)` - structural pattern matching
      - `substitute(body, bindings)` - variable substitution
      - `apply_projection(projection, input)` - match + substitute
      - `step(projections, input)` - select and apply first matching
      - `{"var": "x"}` is the only special form (matches anything, binds)
      - Kernel handlers: step, stall, init
      - Peano numeral countdown works (pure structural)
    - Answer: **Yes, EVAL_SEED is tractable** (~200 lines, O(n) complexity)
    - **Ready for Phase 3**

22. **RCX Kernel Phase 3: EVAL_SEED (Mu)** (in progress)
    - Scope:
      - Translate EVAL_SEED logic to Mu projections
      - Verify Python-EVAL and Mu-EVAL produce same results
      - Store as `seeds/eval.v1.json`
    - **Blocker discovered**: `deep_step` needed
      - Current `step()` only matches at root level
      - Nested reducible expressions (e.g., `{head:1, tail:{op:append,...}}`) not found
      - See `prototypes/linked_list_append.json` for concrete example
    - **Solution path**: Work-stack approach (pure structural)
      - Express tree traversal as explicit Mu state (focus + context stack)
      - No host recursion - kernel loop provides iteration
      - Design doc needed: `docs/DeepStep.v0.md`
    - **Prototype verified**: Linked list append works with 2 projections
      - Proves finite projections can handle variable-length data
      - Requires `deep_step` to find nested reducible nodes

23. **RCX Kernel Phase 4: Self-Hosting** (awaiting Phase 3)
    - Scope:
      - Mu-EVAL runs Mu-EVAL
      - Compare traces: Python→EVAL vs EVAL→EVAL
      - If identical, self-hosting achieved

19. **Bytecode VM v1b: OP_FIX/OP_FIXED execution** ✅ (promoted from VECTOR #10 v1)
    - Design doc: `docs/BytecodeMapping.v1.md`
    - **Archived to Ra**: Implementation complete (78 tests, RF register, stall_memory clearing)

18. **Bytecode VM v1a: OP_STALL execution** ✅ (promoted from VECTOR #10 v1)
    - Design doc: `docs/BytecodeMapping.v1.md`
    - **Archived to Ra**: Implementation complete (61 tests, v1a registers, closure detection)

17. **Bytecode VM v0 Implementation** ✅ (promoted from VECTOR #10)
    - Design doc: `docs/BytecodeMapping.v0.md`
    - **Archived to Ra**: Implementation complete (47 tests, `tools/audit_bytecode.sh`)

---

## VECTOR (design-only; semantics locked, no implementation allowed)

14. **RCX Kernel v0** ✅ (design complete)
    - Deliverable: `docs/RCXKernel.v0.md`
    - Semantic question: "What is the minimal kernel that supports self-hosting?"
    - Done:
      - 4 kernel primitives: compute_identity, detect_stall, record_trace, gate_dispatch
      - apply_projection is NOT kernel - seeds define matching semantics
      - Seed hierarchy: EVAL_SEED (evaluator) → Application Seeds (EngineeNews, etc.)
      - Bootstrap sequence: Python → Kernel → EVAL_SEED → EVAL_SEED runs itself
      - Self-hosting required to prove emergence (not simulate it)
    - Ready for promotion to NEXT

15. **Structural Purity v0** ✅ (design + implementation complete)
    - Deliverable: `docs/StructuralPurity.v0.md`
    - Semantic question: "How do we ensure we program IN RCX, not ABOUT RCX?"
    - Done:
      - Guardrail functions: `assert_seed_pure()`, `assert_handler_pure()`, etc.
      - Boundary definition: Python only at 4 kernel primitives
      - Audit script extended with checks 9-11
      - 32 tests for guardrail functions
    - **Archived to Ra**: Implementation complete

9. **"Second independent encounter" semantics** ✅
   - Deliverable: `docs/IndependentEncounter.v0.md`
   - Done:
     - "Independent" defined: same (value_hash, pattern_id) with no intervening reduction
     - Tracking: stall_memory map, cleared on any value transition
     - Closure signal: second stall at same (v, p) implies normal form
     - Minimal state: last_stall[(pattern_id)] = value_hash
     - Conservative reset on execution.fixed
     - Key invariant: detected inevitability, not policy (VM observes, doesn't decide)
   - **Promoted to NEXT #16**: Second Independent Encounter Implementation

10. **Bytecode VM mapping v0/v1** ✅
    - Deliverables: `docs/BytecodeMapping.v0.md` (replay-only), `docs/BytecodeMapping.v1.md` (execution)
    - v0 Done (replay-only) - **IMPLEMENTED**:
      - Minimal instruction set: 10 opcodes (INIT, LOAD_EVENT, CANON_EVENT, etc.)
      - Event → opcode mapping (trace.start, step, trace.end)
      - Fail-loud on unmappable events
      - Implementation: `rcx_pi/bytecode_vm.py`, 47 tests, `tools/audit_bytecode.sh`
    - v1 Partial (execution opcodes) - **IMPLEMENTED v1a/v1b**:
      - v1a: OP_STALL (stall declaration, closure detection)
      - v1b: OP_FIX/OP_FIXED (stall resolution, value transition)
      - Registers: RS (status), RP (pattern), RH (hash), RF (fix target)
      - Reserved: ROUTE/CLOSE remain blocked
    - v1 Remaining (execution loop) - **NOT IMPLEMENTED**:
      - OP_MATCH, OP_REDUCE (pattern matching, rule application)
      - Execution loop orchestration
      - R0 (actual value storage)
    - **Archived to Ra**: v0 (NEXT #17), v1a (NEXT #18), v1b (NEXT #19)

11. **Enginenews spec mapping v0** ✅
    - Deliverable: `docs/EnginenewsSpecMapping.v0.md`
    - Done:
      - Minimal motif set (news.pending, news.refined, news.cycling, news.terminal)
      - Metrics defined from events only: counts, stall_density, fix_efficacy, closure_evidence
      - Explicit non-goal: no ROUTE/CLOSE, no termination policy
      - CLI contract documented (--check-canon, --print-exec-summary)
    - **Archived to Ra**: Stress test harness implemented (`test_enginenews_spec_v0.py`, 18 tests, 4 fixtures)

12. **Closure Evidence Events v0** ✅ (promoted from SINK: "ROUTE/CLOSE opcodes")
    - Deliverable: `docs/ClosureEvidence.v0.md`
    - Done:
      - Event vocabulary: `evidence.closure` with value_hash, pattern_id, reason
      - Alignment with IndependentEncounter.v0.md detection rule
      - 5 normative examples (SHOULD/SHOULD NOT emit)
      - Future promotion checklist
    - Non-goal: no engine termination directive, no ROUTE opcode, no implementation
    - **Archived to Ra**: Design complete, reporting tool implemented (`--print-closure-evidence`, `closure_evidence_v2()`)

13. **Rule-as-Motif representation v0** ✅ (promoted from SINK: "Full VM bootstrap / meta-circular execution")
    - Deliverable: `docs/RuleAsMotif.v0.md`
    - Semantic question: "What is the minimal representation of an RCX reduction rule as a motif, such that rules become first-class structural data?"
    - Promotion rationale:
      - MetaCircularReadiness.v1.md Gate 5 is blocked; this unblocks M4 (Organism extraction)
      - code=data principle requires rules to be structural, not host closures
      - Advances self-hosting without requiring execution semantics changes
      - Pure design work: defines representation, not matching or application
      - Follows "observability precedes mechanics": define shape before behavior
    - Scope:
      - Rule motif structure: `{"rule": {"id": ..., "pattern": ..., "body": ...}}`
      - Variable site representation: `{"var": "<name>"}`
      - Canonical examples (add.zero, add.succ)
      - Invariants: determinism, structural equality, no host leakage
      - Promotion gates for VECTOR → NEXT
    - Non-goals:
      - No execution semantics (how VM applies rule motifs)
      - No pattern matching algorithm
      - No rule compilation to bytecode
      - No rule ordering/priority
      - No implementation
    - **Promoted to NEXT #14**: Rule Motif Observability v0

---

## SINK (ideas parked; may not advance without explicit promotion decision)

- Multi-value/concurrent execution
- Performance-first optimizations
- ~~Full VM bootstrap / meta-circular execution~~ → Promoted to VECTOR #14 (RCX Kernel v0)
