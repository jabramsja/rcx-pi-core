# Claude Code Instructions for RCX

This file is read by Claude Code at session start.

---

## SESSION ONBOARDING (Read This First)

**CANONICAL SOURCES - There are only TWO files that matter for current state:**

| File | Purpose | Contains |
|------|---------|----------|
| `STATUS.md` | **Current state** | Phase, debt counts, testing tiers, fuzzer config |
| `TASKS.md` | **Work items** | Ra (done), NEXT (active), VECTOR (design), SINK (parked) |

**Everything else is reference material.** Docs in `mu/docs/` are specs and historical context - they should NOT contain operational state that drifts.

**At session START:**
1. Read `STATUS.md` - know current phase (L1/L2/L3) and debt counts
2. Read `TASKS.md` - know what's in progress, what's next
3. Run `./tools/checks/check_agent_review_needed.sh` - check for uncommitted core changes needing agent review
4. Read `mu/docs/agents/AgentRunbook.v0.md` before running agents

**At session END (before signing off):**
1. Did phase or debt change? → Update `STATUS.md`
2. Did tasks complete or promote? → Update `TASKS.md`
3. Were notable changes made? → Update `CHANGELOG.md`

**If unsure:** Run `./tools/checks/check_docs_consistency.sh` to validate STATUS.md matches reality.

---

## What RCX Is (Alignment)

RCX is a native structural substrate, not a simulation on top of Python. Python exists only as scaffolding to bootstrap the kernel.

**The Goal:** Both SELF-HOSTING and META-CIRCULARITY are required.
- **Self-hosting**: RCX algorithms expressed as Mu projections
- **Meta-circular**: The evaluator runs itself - projections select projections

If Python provides the control flow, emergence might be a Python artifact. True emergence must come from structure alone.

**L3 Parity Requirement (MANDATORY):**
- Python (`rcx_pi/selfhost/`) and JavaScript (`mu/host/js/eval_step.js`) must remain in parity
- Both substrates load the SAME seed files: `kernel.v1.json`, `match.v2.json`, `subst.v2.json`, `recurrence.v1.json`, `recurrence.v2.json`, `exhaustion.v1.json`, `fix.v1.json`, `bootstrap_structural.v1.json`, `hemispheres.v1.json`, `rcx_engine.v1.json`
- Any change to projection behavior in Python MUST be mirrored in JavaScript
- Any new seed file MUST be loaded and tested in BOTH substrates
- Run `node mu/host/js/eval_step.js` to verify JS parity after Python changes
- **ACTUAL verification:** `tests/parity/test_js_parity_automated.py::test_actual_cross_substrate_comparison` runs same inputs through BOTH substrates

---

## Current Status

**Read `STATUS.md`** for current phase, self-hosting level (L1/L2/L3), and debt counts.

**Read `TASKS.md`** for work items (Ra, NEXT, VECTOR, SINK).

These are the only two files that track current state. Do not duplicate status info elsewhere.

---

## Agents

**What agents are:** RCX uses a multi-agent code review system - specialized AI agents that each check different aspects of code changes. The key agents are:
- **verifier** - Checks code against North Star invariants
- **adversary** - Red-team security review (tries to break things)
- **expert** - Complexity and simplification review
- **structural-proof** - Verifies that structural claims have actual projections

**Why agents exist:** We don't trust any single reviewer. We trust the *fight* between specialized agents that check each other's blind spots.

**Canonical docs:**
- `mu/docs/agents/AgentRunbook.v0.md` - **Start here** - Tool overview, which tool when, commands, depth levels
- `mu/docs/agents/AgentRig.v0.md` - Architecture and trust model
- `mu/docs/agents/AgentGuardrails.v0.md` - Output format requirements

**Quick start:** `./tools/agents.sh`

### When to Run Agents

**The rule:** If you touched `rcx_pi/selfhost/` or `mu/`, run agents before saying "done."

| Tier | Command | When | Time |
|------|---------|------|------|
| **Quick** | `python tools/runners/run_review.py --pr --depth quick` | Daily dev loop, most commits | ~2-3 min |
| **Full** | `python tools/runners/run_review.py --pr --depth full` | Pre-merge PR gate | ~5-8 min |
| **Rigorous** | `python tools/runners/run_review.py --pr --rigorous` | Security/runtime/core kernel changes | ~10-15 min |
| **Release** | `python tools/runners/run_review.py rcx_pi/selfhost/ mu/ --rigorous --max-turns 12 --output reports/release_review.md` | Release/hardening pass | ~15-20 min |
| **Health** | `python tools/runners/run_deep_analysis.py` | Monthly / pre-release | ~5-10 min |

**Practical rules:**
1. Default habit: `quick` for iteration, then `full` once before merge
2. Reserve `--rigorous` for high-risk PRs (`rcx_pi/selfhost/`, `mu/`, gating tooling)
3. Docs/tooling only: skip agents, just run tests

### Key Commands

```bash
# Quick feedback (4 agents)
python tools/runners/run_review.py --pr --depth quick

# Full review (5-6 agents, pre-merge gate)
python tools/runners/run_review.py --pr --depth full

# Rigorous mode (all 9 agents + skeptic challenge)
python tools/runners/run_review.py --pr --rigorous

# Interactive session
python tools/runners/run_interactive.py verifier rcx_pi/selfhost/

# Full-stack health analysis (monthly/pre-release)
python tools/runners/run_deep_analysis.py
```

See `mu/docs/agents/AgentRunbook.v0.md` for all runners, depth levels, rigorous mode details, agent memory, and CI integration.

---

## Workflow

**Branching model:** `dev` is the primary branch. There is no `main` branch in active use. All PRs target `dev`. CI workflows (green gate, fixture gates) trigger on push/PR to `dev`.

**Audit scripts (four tiers):**

| Tier | Script | Time | Purpose | When |
|------|--------|------|---------|------|
| 1 | `./tools/audit_fast.sh` | ~3 min | Core tests only | Local iteration |
| 2 | `./tools/audit_all.sh` | ~5-8 min | Core + Fuzzer + Slow | Before push |
| 3 | CI green gate | ~2 min | Core only (no fuzzer, no slow) | Push/PR to dev |
| 4 | CI nightly | ~45 min | Everything (200 examples, ci_full) | Nightly schedule |
| 5 | CI weekly deep fuzz | ~60 min | Deep fuzz (500 examples) | Weekly schedule |

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

### Test Classification (IMPORTANT — Read Before Adding Tests)

Every test must be classifiable into one of three categories. The CI green gate excludes `slow` and `fuzzer` tests to maintain sub-2-minute runs. **Misclassified tests break CI timing.**

| Category | Marker | Rule | Where It Runs |
|----------|--------|------|---------------|
| **Core** | *(none)* | Completes in <10s. Deterministic. No hypothesis. | All tiers (green gate, audit_fast, audit_all, nightly) |
| **Slow** | `@pytest.mark.slow` | Takes >10s OR uses meta-circular kernel (`run_mu`, `run_algorithm_meta_circular`, `run_engine_pipeline`, `run_hemisphere_routing`). No exceptions. | audit_all, nightly only |
| **Fuzzer** | *(auto-marked)* | Uses `@given` / `@hypothesis.settings`. Auto-detected by `conftest.py` via `item.obj.is_hypothesis_test`. Do NOT manually mark. | audit_all, nightly only |

**When creating new tests:**

1. **Default is core** — no marker needed. Must complete in <10s locally.
2. **If it calls `run_mu()`, `run_algorithm_meta_circular()`, `run_engine_pipeline()`, or `run_hemisphere_routing()`** — mark `@pytest.mark.slow` (class-level or function-level).
3. **If it uses Hypothesis `@given`** — do nothing. `conftest.py` auto-marks it as `fuzzer` at collection time.
4. **If a non-hypothesis test takes >10s** — mark `@pytest.mark.slow`. Profile with `pytest --durations=10` to verify.
5. **File-level marking** (`pytestmark = pytest.mark.slow`) is fine when ALL tests in a file are slow (e.g., `test_engine_orchestration.py`).
6. **Never blanket-mark a file as `fuzzer`** — use auto-marking only. Mixed files contain both hypothesis and deterministic tests.

**How auto-marking works:**
```python
# In tests/conftest.py — pytest_collection_modifyitems hook
# Detects hypothesis tests via item.obj.is_hypothesis_test attribute
# Applies fuzzer marker automatically — no manual action needed
```

**Verification after adding tests:**
```bash
# Check your test is in the right bucket
pytest --collect-only -m "not slow and not fuzzer" tests/your_test.py -q  # Should appear here if core
pytest --collect-only -m "slow" tests/your_test.py -q                     # Should appear here if slow
pytest --collect-only -m "fuzzer" tests/your_test.py -q                   # Should appear here if hypothesis

# Verify green gate count hasn't regressed
pytest --collect-only -m "not slow and not fuzzer" --ignore=tests/stress/ -q 2>&1 | tail -3
```

**Enforcement:** `tools/checks/check_test_speed.sh` statically catches test files that import slow kernel functions without `@pytest.mark.slow`. Runs automatically in the pre-commit hook on staged test files. Whitelist with `# SPEED_OK: reason` if a file imports but doesn't actually call them.

```bash
bash tools/checks/check_test_speed.sh          # Scan all tests/
bash tools/checks/check_test_speed.sh tests/foo.py  # Scan specific file
```

**Git hooks:**

| Script | Purpose | When |
|--------|---------|------|
| `tools/pre-commit-doc-check` | Doc consistency, debt ceiling | Auto on `git commit` (~5s) |
| `tools/pre-push-fast` | Fast audit (audit_fast.sh) | Auto on `git push` (~2-3 min) |

**Consistency tools:**
- `./tools/checks/check_docs_consistency.sh` - Validate STATUS.md matches reality
- `./tools/debt_dashboard.sh` - Show current debt counts and locations
- Verifier agent (Section F) - Checks doc consistency as part of verification
- `./tools/pre-commit-doc-check` - Canonical local commit gate (manual or via git hook)

**Cost model:**
- Local agents (Claude Code): FREE (Max subscription)
- CI agents (GitHub Actions): COSTS MONEY (manual trigger only)

**Setup (one-time):**
```bash
pip install pytest-xdist  # 2-3x faster test execution
ln -sf ../../tools/pre-commit-doc-check .git/hooks/pre-commit
ln -sf ../../tools/pre-push-fast .git/hooks/pre-push
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
| `mu/docs/core/` | Design specs |
| `mu/docs/agents/AgentRig.v0.md` | Agent rig docs |
| `mu/host/python/rcx_pi/selfhost/` | Core implementation (canonical; `rcx_pi/` is backward-compat symlink) |
| `mu/` | Mu projections: substrate/, closures/, bridge/, programs/, utilities/, host/ |
| `mu/host/js/eval_step.js` | JavaScript substrate (L3 parity) |
| `mu/substrate/`, `mu/closures/`, `mu/programs/` | Seed files (JSON projections) |

---

## Documentation Governance (IMPORTANT)

**Full policy:** `mu/docs/core/DocGovernance.v0.md`

**The Three Laws:**
1. Two files own current state (STATUS.md, TASKS.md only)
2. Every doc has a lifecycle (DOC_STATUS header)
3. Design docs describe WHAT, not progress

**Four-layer test defense (118 tests):**
- `tests/docs/test_doc_contracts.py` - Verify code references exist
- `tests/docs/test_doc_freshness.py` - Detect semantic drift
- `tests/docs/test_doc_governance.py` - Enforce Three Laws
- `tests/docs/test_root_files.py` - Govern source-of-truth files

**Doc types (from DOC_STATUS header):**
- **REFERENCE** - Stable definitions (MuType, DebtCategories)
- **DESIGN_SPEC** - Architectural intent, may diverge from implementation
- **IMPLEMENTATION** - Active development, should match current code

**Projection count convention:**
- Estimates use `~`: "~6 projections"
- Claims reference tests: "see `test_seed_counts.py` for count"

**When modifying code:**
1. If you change a function name → update DOC_CONTRACTS
2. If you change projection count → update grounding tests
3. If you add a doc → add DOC_STATUS header

**Verification:**
```bash
pytest tests/docs/test_doc_contracts.py -v  # Verify all doc claims
python tools/docs/add_doc_headers.py --check     # Verify all docs have headers
```

**DO NOT:**
- Use line number references in docs (fragile, use function names instead)
- Hardcode counts in docs (use "see DOC_CONTRACTS" or "verified by tests/...")
- Duplicate operational state in design docs (that belongs in STATUS.md)

---

## Governance & Invariants

**See `TASKS.md`** for:
- North Star invariants (15 items)
- Governance rules (non-negotiable)
- Promotion criteria (SINK → VECTOR → NEXT)

TASKS.md is the authority. Do not duplicate rules here.
