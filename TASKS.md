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

_(No active items.)_

---

## VECTOR (design-only; semantics locked, no implementation allowed)

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

10. **Bytecode VM mapping v1 (upgrade from v0)** ✅
   - Deliverable: `docs/BytecodeMapping.v1.md`
   - Done:
     - Register-centric model: R0 (value), RH (hash), RP (pattern), RS (status), RF (fix target)
     - Bytecode ops: OP_MATCH, OP_REDUCE, OP_STALL, OP_FIX, OP_FIXED
     - Opcode table: semantic placeholders (0x10-0x41), not ABI commitment
     - Registers authoritative during execution, trace authoritative for validation
     - Execution loop: ACTIVE → STALL → (optional FIX) → FIXED → ACTIVE

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
- Full VM bootstrap / meta-circular execution (partial: rule-as-motif promoted to VECTOR #13)
- Performance-first optimizations
