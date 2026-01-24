Guardrail / Alignment Note (Please Acknowledge)

RCX is being built as a native structural substrate, not as a simulation on top of a host language. Python and Rust exist only as scaffolding to seal determinism, entropy, and trace semantics; they are not the target runtime. RCX programs (e.g. RCXEngineNew / EngineNews-like specs) are VECTOR workloads that must eventually run honestly on the RCX VM and may legitimately fail to produce claimed structures. Do not implement VM semantics, bytecode, μ-rewrite execution, or EngineNews logic unless explicitly instructed. Do not introduce new subsystems, execution models, abstractions, files, tests, or documentation beyond what is listed in TASKS.md. All work must stay within the current NOW scope, preserve existing invariants, keep CI green, and refine or tighten what exists rather than replacing it. When intent is ambiguous, stop and ask before acting.



Add these process guardrails and follow them strictly:



PROCESS / HYGIENE RULES (non-negotiable)



1\) Do not proliferate files.

&nbsp;  - If something fails, FIX the existing file.

&nbsp;  - Do NOT create “v2”, “new”, “alt”, “fixed”, “final”, “really\_final” copies.

&nbsp;  - One file per concept unless explicitly approved.



2\) Do not duplicate tests.

&nbsp;  - If a test fails because reality changed, update the existing test OR the implementation.

&nbsp;  - Never “solve” a failing test by adding a new test that passes.

&nbsp;  - Never leave broken/unused tests behind.



3\) Minimal change surface.

&nbsp;  - Prefer the smallest patch that makes the suite green.

&nbsp;  - No refactors “while you’re in there” unless required for the NOW deliverable.



4\) Changes must be explainable in one sentence.

&nbsp;  - Every commit message should describe exactly what invariant it locks.

&nbsp;  - If you can’t explain the change simply, you’re probably expanding scope.



5\) Determinism discipline.

&nbsp;  - Do not introduce new entropy sources.

&nbsp;  - If you must touch anything related to ordering, time, randomness, hashing, filesystem traversal, or floating point behavior, call it out explicitly.



6\) Repo cleanliness is law.

&nbsp;  - Never leave tracked diffs around during tests.

&nbsp;  - If a gate checks for tracked diffs, stage/commit intentionally or revert; don’t “work around” the gate.



7\) TASKS.md is the scope boundary.

&nbsp;  - Only implement NOW items unless explicitly told otherwise.

&nbsp;  - No new frameworks, subsystems, CLIs, docs trees, or directories without approval.



8\) PR policy.

&nbsp;  - Keep PRs tight: only the files required for the deliverable.

&nbsp;  - Ensure `pytest` is green locally before pushing.

&nbsp;  - Prefer squash merge + delete branch (same as we’ve been doing).



If you accept these, proceed with NOW #1: draft docs/EntropyBudget.md as a contract (SEALED / FORBIDDEN / ALLOWED WITH justification), with no new code/tests yet.

### Entropy Source Policy (Canonical)

**Randomness (RNG)**
Use of ambient randomness (`random`, unseeded RNGs) is **FORBIDDEN** in all deterministic execution paths, including trace generation, replay, golden fixtures, and CI gates. Randomness may be **EXPLICITLY ALLOWED** only in sandbox or experimental worlds that are clearly labeled and never exercised by determinism gates. Any future deterministic use of randomness must be fully sealed by explicit seeding from declared inputs and recorded in trace metadata so replay is exact.

**Timestamps / Wall-Clock Time**
Wall-clock time (e.g. `datetime.now()`) is **NON-DETERMINISTIC** and must not influence replay-sensitive outputs. Timestamp fields may exist for human inspection, but they must be **STRIPPED or NORMALIZED** during canonicalization before comparison, replay gates, or golden fixture validation. Time is informational only, never semantic.

**Hash Ordering (PYTHONHASHSEED)**
CI runs must enforce `PYTHONHASHSEED=0` to eliminate environment-dependent hash ordering. This is a **SEALED REQUIREMENT**. Additionally, all iteration over unordered collections (dicts, sets) that affect trace output must use explicit, deterministic ordering (e.g. `sorted(...)`). Determinism must not rely solely on environment configuration.

**General Rule**
If an entropy source cannot be sealed, normalized, or made replayable, it is not permitted in deterministic RCX execution paths. Any exception must be explicitly documented and scoped outside the trace/replay contract.

