# RCX-Ω Governance & Rails

This document defines the operational guardrails for RCX-Ω work.
It exists to prevent drift, accidental scope expansion, and false claims.

This is not a philosophy document. It is binding process.

------------------------------------------------------------

1) System Zones

Frozen
- Externally visible contracts and invariants:
  - CLI output markers
  - Default JSON shapes
  - Analyze behavior guarantees
- Changes require:
  - Explicit contract revision
  - Updated tests
  - Green gate

Staging
- Docs, schemas, and opt-in behavior
- May evolve without changing default runtime output
- Promotion to Frozen requires checklist completion

Vector
- Aspirational, exploratory, non-binding
- No execution tasks by default
- No implied guarantees

------------------------------------------------------------

2) Work Queues

NOW
- Bounded, testable execution work
- Must state explicitly:
  - What changes
  - What must NOT change
  - Verification command
- Must end with running the test suite

NEXT
- Clarification only:
  - Docs
  - Contracts
  - Schemas
  - Governance
- No runtime behavior changes

VECTOR
- Ideas and future possibilities
- No tasks unless readiness is detected

------------------------------------------------------------

3) Tests Are Truth

- Tests override documentation
- Documentation must be updated to match passing behavior
- No claim of "done" or "green" without a green test run

------------------------------------------------------------

4) Self-Hosting / Meta-Circularity

Self-hosting and meta-circularity are latent by default.

Default State
- Lives in VECTOR
- Not actively pursued
- Not claimed

Readiness-Detected Promotion Rule

Promotion may occur only if ALL criteria are satisfied:

1. A minimal execution surface exists, frozen and tested
2. RCX programs are represented, executed, and analyzed using the same Ω machinery as non-RCX programs
3. Analysis derives signals from motifs or patterns, not privileged interpreter hooks
4. No RCX-only code paths are required
5. No frozen CLI markers or JSON contracts are changed
6. Tests demonstrate equivalence between:
   - RCX analyzing X
   - RCX analyzing RCX(X)

When criteria appear satisfied:
- Stop
- Present evidence
- Ask for explicit permission
- Do NOT implement automatically
- Do NOT imply readiness already exists

------------------------------------------------------------

5) Session & Execution Discipline

- Repo state is authoritative
- Conversation state is advisory
- Never say "we already decided" unless it exists in-repo
- Default to describing work, not executing it
- Never create or modify files without explicit approval
- When executing:
  - Provide one copy/paste-ready block
  - State what changes and what must not change

------------------------------------------------------------

6) Conflict Resolution

- If tests and docs disagree: tests win
- If governance and enthusiasm disagree: governance wins
- If ambiguity exists: prefer NEXT over NOW

------------------------------------------------------------

7) Scope Boundaries

This document does NOT:
- Claim self-hosting or emergent execution
- Define roadmaps or promises
- Tighten runtime requirements
- Override frozen contracts

It exists solely to keep RCX-Ω on rails.
