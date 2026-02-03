# Claude Code Instructions for RCX

This file is read by Claude Code at session start.

---

## SESSION ONBOARDING (Read This First)

**CANONICAL SOURCES - There are only TWO files that matter for current state:**

| File | Purpose | Contains |
|------|---------|----------|
| `STATUS.md` | **Current state** | Phase, debt counts, testing tiers, fuzzer config |
| `TASKS.md` | **Work items** | Ra (done), NEXT (active), VECTOR (design), SINK (parked) |

**Everything else is reference material.** Docs in `docs/` are specs and historical context - they should NOT contain operational state that drifts.

**At session START:**
1. Read `STATUS.md` - know current phase (L1/L2/L3) and debt counts
2. Read `TASKS.md` - know what's in progress, what's next

**At session END (before signing off):**
1. Did phase or debt change? → Update `STATUS.md`
2. Did tasks complete or promote? → Update `TASKS.md`
3. Were notable changes made? → Update `CHANGELOG.md`

**If unsure:** Run `./tools/check_docs_consistency.sh` to validate STATUS.md matches reality.

---

## What RCX Is (Alignment)

RCX is a native structural substrate, not a simulation on top of Python. Python exists only as scaffolding to bootstrap the kernel.

**The Goal:** Both SELF-HOSTING and META-CIRCULARITY are required.
- **Self-hosting**: RCX algorithms expressed as Mu projections
- **Meta-circular**: The evaluator runs itself - projections select projections

If Python provides the control flow, emergence might be a Python artifact. True emergence must come from structure alone.

**L3 Parity Requirement (MANDATORY):**
- Python (`rcx_pi/selfhost/`) and JavaScript (`mu/host/js/eval_step.js`) must remain in parity
- Both substrates load the SAME seed files: `kernel.v1.json`, `match.v2.json`, `subst.v2.json`, `recurrence.v1.json`
- Any change to projection behavior in Python MUST be mirrored in JavaScript
- Any new seed file MUST be loaded and tested in BOTH substrates
- Run `node mu/host/js/eval_step.js` to verify JS parity after Python changes
- **ACTUAL verification:** `tests/test_js_parity_automated.py::test_actual_cross_substrate_comparison` runs same inputs through BOTH substrates

---

## Current Status

**Read `STATUS.md`** for current phase, self-hosting level (L1/L2/L3), and debt counts.

**Read `TASKS.md`** for work items (Ra, NEXT, VECTOR, SINK).

These are the only two files that track current state. Do not duplicate status info elsewhere.

---

## Agents

| Agent | Model | Purpose | When to Use |
|-------|-------|---------|-------------|
| advisor | **opus** | Strategic advice, trade-offs | When stuck on design decisions |
| verifier | **opus** | North Star invariant compliance | Every PR with rcx_pi/ changes |
| adversary | **opus** | Red team attack testing | New modules, security-sensitive code |
| expert | **opus** | Code quality, simplification | Complex code, major refactors |
| structural-proof | sonnet | Verify Mu projection claims | When claiming "pure structural" |
| grounding | sonnet | Convert claims to executable tests | Core kernel/seed code |
| fuzzer | sonnet | Property-based testing (1000+ inputs) | Core kernel/seed code |
| translator | sonnet | Plain English explanation | Founder review |
| visualizer | sonnet | Mermaid diagrams of Mu structures | Founder review |

**Model selection rationale:**
- **Opus** for core agents (advisor, verifier, adversary, expert) - deeper reasoning for strategic/security analysis
- **Sonnet** for implementation agents - good balance of speed and quality

**Agent Guardrails (Anti-Hallucination):**
All 9 agents follow `docs/agents/AgentGuardrails.v0.md` requiring FILE:LINE + code evidence.
The validation hook (`.claude/hooks/validate-agent-compliance.sh`) automatically checks output format.

**Mandatory for PRs:** verifier, adversary, expert, structural-proof (4)
**For core code:** Add grounding, fuzzer (6)
**For founder review:** Add translator, visualizer (8)

See `docs/agents/AgentRig.v0.md` for full documentation.

---

## Workflow

**Audit scripts (three tiers):**

| Tier | Script | Time | Purpose | When |
|------|--------|------|---------|------|
| 1 | `./tools/audit_fast.sh` | ~3 min | Core tests only | Local iteration |
| 2 | `./tools/audit_all.sh` | ~5-8 min | Core + Fuzzer | Before push, CI |
| 3 | `pytest tests/stress/` | ~10+ min | Deep edge cases | Comprehensive validation |

Both audit scripts use parallel execution if `pytest-xdist` is installed: `pip install pytest-xdist`

**Hypothesis profiles for fast local fuzzer runs:**
```bash
HYPOTHESIS_PROFILE=dev pytest tests/test_bootstrap_fuzzer.py  # 50 examples, ~30s
```

**Development workflow:**
```bash
# Iterate locally (fast feedback)
./tools/audit_fast.sh

# REQUIRED: Before pushing, run full validation locally
./tools/audit_all.sh

# Only push after local tests pass
git push
```

**IMPORTANT: Always run `./tools/audit_all.sh` locally before pushing.**
- Local runs are faster (~5 min) than waiting for CI (~10 min)
- Tests are deterministic (PYTHONHASHSEED=0) so same inputs run locally and on CI
- CI runners are slower, so deadline issues may only surface there - but running locally first catches most problems faster

---

## Test Execution (IMPORTANT - READ THIS)

**Default is SERIAL (fast for single files).** Parallel is used via audit scripts or explicit flag.

| Scenario | Command | Time |
|----------|---------|------|
| Single file | `pytest tests/foo.py` | Fast (no overhead) |
| Specific test | `pytest tests/foo.py::TestClass::test_name` | Fastest |
| Full suite | `pytest -n auto` | ~44s (6x faster than serial) |
| Full suite | `./tools/audit_fast.sh` | ~3 min (auto-parallel) |

**Quick reference:**
```bash
# Single file (default serial, fast)
pytest tests/test_match_parity.py

# Full suite with parallel (6x speedup)
pytest -n auto --dist worksteal

# Or use audit scripts (auto-detect parallel)
./tools/audit_fast.sh   # Core tests
./tools/audit_all.sh    # Full suite + fuzzer
```

**Why this setup:**
- Single-file runs: Serial is faster (avoids 3s worker spawn overhead)
- Full suite (1000+ tests): Parallel is 6x faster (44s vs 255s)
- Audit scripts auto-detect xdist and enable parallel when available

**Pre-commit scripts:**

| Script | Purpose | When |
|--------|---------|------|
| `tools/pre-commit-check.sh` | Syntax, contraband, AST, docs | Run manually |
| `tools/pre-commit-doc-check` | Doc consistency, debt ceiling | Auto git hook |

**Consistency tools:**
- `./tools/check_docs_consistency.sh` - Validate STATUS.md matches reality
- `./tools/debt_dashboard.sh` - Show current debt counts and locations
- Verifier agent (Section F) - Checks doc consistency as part of verification

**Cost model:**
- Local agents (Claude Code): FREE (Max subscription)
- CI agents (GitHub Actions): COSTS MONEY (manual trigger only)

**Setup (one-time):**
```bash
pip install pytest-xdist  # 2-3x faster test execution
ln -sf ../../tools/pre-commit-doc-check .git/hooks/pre-commit
```

---

## Phase Transitions

When advancing phases:
1. Update `STATUS.md` (change L1 → L2 → L3)
2. Update `TASKS.md` (move item to Ra)
3. Agents automatically enforce new standards

Do NOT update individual agent files - they read STATUS.md.

---

## Key Files

| File | Purpose |
|------|---------|
| `STATUS.md` | Current phase/debt (source of truth) |
| `TASKS.md` | Work items (source of truth) |
| `docs/core/` | Design specs |
| `docs/agents/AgentRig.v0.md` | Agent rig docs |
| `rcx_pi/selfhost/` | Core implementation |
| `seeds/*.json` | Mu projection definitions (including recurrence.v1.json) |

---

## Governance & Invariants

**See `TASKS.md`** for:
- North Star invariants (13 items)
- Governance rules (non-negotiable)
- Promotion criteria (SINK → VECTOR → NEXT)

TASKS.md is the authority. Do not duplicate rules here.
