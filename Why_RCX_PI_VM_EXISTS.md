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

6. Current State (Updated 2026-01-25)

**Completed:**
- Deterministic trace semantics (v1 frozen)
- Replayable execution (replay gates enforced)
- Entropy sealing (EntropyBudget.md contract)
- Canonical trace contracts
- Minimal Kernel (4 primitives: identity, stall, trace, dispatch)
- EVAL_SEED Phase 2 (Python implementation: match, substitute, step)
- Bytecode VM v0/v1a/v1b (replay + execution opcodes)

**In Progress:**
- EVAL_SEED Phase 3: Express EVAL_SEED as Mu projections (not Python)
- Key blocker: `deep_step` - need to traverse nested structures without host recursion
- Solution path: work-stack approach (pure structural, no Python call stack)

**Awaiting:**
- Phase 4: Self-hosting (Mu-EVAL runs Mu-EVAL)
- Application seeds (EngineeNews runs on self-hosted EVAL)

The foundation is now solid. Self-hosting is the next milestone.

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