# Claude Code Instructions for RCX

This file is read by Claude Code at session start.

---

## Session Discipline

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

---

## Current Status

**Read `STATUS.md`** for current phase, self-hosting level (L1/L2/L3), and debt counts.

**Read `TASKS.md`** for work items (Ra, NEXT, VECTOR, SINK).

These are the only two files that track current state. Do not duplicate status info elsewhere.

---

## Agents

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| verifier | North Star invariant compliance | Every PR with rcx_pi/ changes |
| adversary | Red team attack testing | New modules, security-sensitive code |
| expert | Code quality, simplification | Complex code, major refactors |
| structural-proof | Verify Mu projection claims | When claiming "pure structural" |
| grounding | Convert claims to executable tests | Core kernel/seed code |
| fuzzer | Property-based testing (1000+ inputs) | Core kernel/seed code |
| translator | Plain English explanation | Founder review |
| visualizer | Mermaid diagrams of Mu structures | Founder review |
| advisor | Strategic advice, trade-offs | When stuck on design decisions |

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

# Before pushing (full validation)
./tools/audit_all.sh

# Or let CI catch it (slower feedback but thorough)
git push
```

---

## Test Execution (IMPORTANT - READ THIS)

**Default is SERIAL (fast for single files).** Parallel is used via audit scripts or explicit flag.

| Scenario | Command | Time |
|----------|---------|------|
| Single file | `pytest tests/foo.py` | Fast (no overhead) |
| Specific test | `pytest tests/foo.py::TestClass::test_name` | Fastest |
| Full suite | `pytest -n auto` | ~44s (6x faster than serial) |
| Full suite | `./tools/audit_fast.sh` | ~2 min (auto-parallel) |

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
| `seeds/*.json` | Mu projection definitions |

---

## Governance & Invariants

**See `TASKS.md`** for:
- North Star invariants (12 items)
- Governance rules (non-negotiable)
- Promotion criteria (SINK → VECTOR → NEXT)

TASKS.md is the authority. Do not duplicate rules here.
