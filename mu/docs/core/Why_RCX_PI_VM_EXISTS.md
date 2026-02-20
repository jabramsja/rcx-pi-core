<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-19
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

Why the RCX VM Exists

This document exists to prevent future confusion.

It explains why RCX is being built as a VM / OS / meta-circular system, what kinds of things it is meant to run, and why this work is intentionally harder than running the same ideas on Python, Rust, Lisp, or other host languages.

This is not a specification, roadmap, or promise of capability. It is an alignment document.

⸻

1. What RCX Is

RCX is a structural execution substrate.

Its defining properties are:
	•	Code = data: there is no privileged distinction between program, state, or result.
	•	Deterministic recursion: all progress is driven by stall → fix → trace.
	•	No assumed logic: logic, axioms, inference rules, and closures must emerge or remain absent.
	•	Trace-first semantics: correctness is defined by replayable structural traces, not outputs.
	•	Minimal assumptions: the system can begin from void / indistinction and introduce structure only when forced.

RCX is closer to a pressure engine than a language runtime.

⸻

2. What RCX Is Not

RCX is not:
	•	A faster or better Python
	•	A general-purpose programming language
	•	A theorem prover that guarantees results
	•	A simulator of emergence that always produces desired structures
	•	A replacement for existing host languages

RCX is not optimized for convenience or expressiveness.

It is optimized for honesty.

⸻

3. What RCX Programs Are

An RCX program is not an algorithm.

It is a structural specification consisting of:
	•	Initial seeds (possibly void)
	•	Enabled gates / closures
	•	Constraints on recursion
	•	Thresholds that trigger collapse, projection, or restart

An RCX program does not “compute” a result.

It applies pressure to the substrate and allows structure to emerge, stall, collapse, or fail.

Failure is a valid outcome.

⸻

4. EngineNews and Similar Specs

Documents like RCXEngineNews are RCX programs, not descriptions of the VM itself.

They are intended to:
	•	Be executed on top of the RCX substrate
	•	Apply structural pressure via closure and stall rules
	•	Test whether claimed emergent objects (e.g. ω, power sets, logic fragments) actually arise

These programs must not cheat by importing logic, axioms, or semantics from the host language.

If a structure does not emerge when executed, that is a truthful outcome.

⸻

5. Why Not Run This on Python / Lisp / Rust

Running these ideas directly on a host language would:
	•	Smuggle in logic, evaluation order, and control flow
	•	Collapse code/data separation implicitly
	•	Hide entropy sources behind the runtime
	•	Make emergence claims unfalsifiable

RCX exists to remove those crutches.

The VM is not an implementation convenience.

It is part of the claim.

⸻

6. Implementation Status

**See `STATUS.md` for current phase, L-level, and debt counts.**

**L-level summary (see STATUS.md for details):**
- **L1 (Algorithmic):** COMPLETE — match, subst, step expressed as Mu projections
- **L2 (Operational):** COMPLETE — kernel.v1 state machine, recurrence/exhaustion detection
- **L3 (Substrate Portability):** COMPLETE — Python and JavaScript run identical seeds with verified parity
- **L4 (True Self-Hosting):** DEFERRED — bootstrap primitives remain host-dependent; see `mu/docs/core/L4ExitChecklist.v0.md`

**Canonical L3 truth statement:**
RCX achieves L3 Substrate Portability by executing identical structural projections across Python and JavaScript. The evaluation rules are structural data, but execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics. The host language acts as physical clock/memory manager; Mu projections are the physics.

**Execution architecture:**
- **Structural kernel bridge** is the active default for algorithm execution (`step_kernel_mu(..., kernel_mode="bridge")`)
- **PureEvaluator** was a legacy host-closure evaluator (archived to `archive/rcx_pi_legacy/engine/evaluator_pure.py` in Round 24H)
- **world_trace_cli** depends on archived `worlds_bridge` (Rust bridge); graceful degradation if unavailable

⸻

7. Long-Term Intent (Non-Binding)

Eventually, the RCX VM should be capable of:
	•	Running structural programs that define their own gates and closures
	•	Supporting paradox-driven, ZFC-like, or non-classical runs
	•	Executing meta-recursive programs that operate on RCX itself

But these capabilities must be earned, not assumed.

⸻

8. One-Line Summary

RCX is being built so that claims about emergence can be tested honestly, without importing structure from the host language.

Nothing more. Nothing less.

⸻

9. Terminology Note

This project uses terms that appear similar but are distinct:
- `sink` (lowercase) = runtime hemisphere bucket (projection routing target)
- `SINK` (uppercase) = governance task lane in TASKS.md (parked work items)
- `r_a` = runtime accumulator bucket
- `Ra` = resolved-work section in TASKS.md

See STATUS.md for the canonical terminology lock.