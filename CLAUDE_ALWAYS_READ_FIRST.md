# Guardrail / Alignment Note (Please Acknowledge)

RCX is being built as a native structural substrate, not as a simulation on top of a host language. Python exists only as scaffolding to bootstrap the kernel; it is not the target runtime. The goal is self-hosting: RCX must run RCX to prove emergence honestly.

## Current Direction (2026-01-25)

We are building:
1. **Minimal Kernel** (Python, ~30 lines) - just plumbing: hash, stall detect, trace, dispatch
2. **EVAL_SEED** - the evaluator written AS structure (Mu projections)
3. **Application Seeds** - like EngineeNews, run on top of EVAL_SEED

Key specs:
- `docs/RCXKernel.v0.md` - Kernel architecture
- `docs/StructuralPurity.v0.md` - Guardrails for programming IN RCX
- `docs/MuType.v0.md` - The universal data type

The kernel doesn't know how to match patterns or apply projections. Seeds define all semantics. This keeps the kernel maximally general.

---

## PROCESS / HYGIENE RULES (non-negotiable)

1. **Do not proliferate files.**
   - If something fails, FIX the existing file.
   - Do NOT create "v2", "new", "alt", "fixed", "final" copies.
   - One file per concept unless explicitly approved.

2. **Do not duplicate tests.**
   - If a test fails because reality changed, update the existing test OR the implementation.
   - Never "solve" a failing test by adding a new test that passes.
   - Never leave broken/unused tests behind.

3. **Minimal change surface.**
   - Prefer the smallest patch that makes the suite green.
   - No refactors "while you're in there" unless required for the NOW deliverable.

4. **Changes must be explainable in one sentence.**
   - Every commit message should describe exactly what invariant it locks.
   - If you can't explain the change simply, you're probably expanding scope.

5. **Determinism discipline.**
   - Do not introduce new entropy sources.
   - See `EntropyBudget.md` for the full entropy sealing contract.

6. **Repo cleanliness is law.**
   - Never leave tracked diffs around during tests.
   - If a gate checks for tracked diffs, stage/commit intentionally or revert.

7. **TASKS.md is the scope boundary.**
   - Only implement items listed in TASKS.md unless explicitly told otherwise.
   - No new frameworks, subsystems, or directories without approval.

8. **PR policy.**
   - Keep PRs tight: only the files required for the deliverable.
   - Ensure `pytest` is green locally before pushing.
   - Prefer squash merge + delete branch.

---

## Structural Purity (Critical)

We must program IN RCX (using Mu/structure) not ABOUT RCX (using Python constructs).

**Guardrails enforced:**
- `assert_mu()` - validates all kernel boundary crossings
- `assert_seed_pure()` - validates seeds contain no Python functions
- `assert_handler_pure()` - wraps handlers to enforce Mu in, Mu out
- `tools/audit_semantic_purity.sh` - static analysis for violations

If we accidentally use Python features (lambda, isinstance logic, etc.), we're simulating emergence, not proving it.

---

## Verification Agents

Four agents assist with code review (available via Task tool or CI workflows):

| Agent | Purpose |
|-------|---------|
| **verifier** | Read-only audit against North Star invariants |
| **adversary** | Red team attack testing (edge cases, type confusion) |
| **expert** | Code quality review, identifies unnecessary complexity |
| **structural-proof** | Demands concrete Mu projections for structural claims |

**Usage**: These run automatically on PRs touching kernel/eval_seed files.
CI workflows: `.github/workflows/agent_*.yml`

---

## What This Is All About

RCX exists so that claims about emergence can be tested honestly, without importing structure from the host language.

Self-hosting is required because:
- If Python runs RCX, emergence might be a Python artifact
- If RCX runs RCX, emergence comes from structure alone
- The evaluator (EVAL_SEED) must itself be structure (Mu)

See `Why_RCX_PI_VM_EXISTS.md` for the full alignment document.
