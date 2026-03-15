# Wave 3 (Tests Audit) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-09_wave3.md`

Archived from the source snapshot as resolved:

- blocker section B1/B2

## Open Items

### NB1. Parity test seed coverage gaps
**Why deferred:** Parity tests cover all 13 loaded seeds for checksum and projection-ID
parity. Coverage "gaps" here refer to per-projection behavioral parity (running each
projection through both substrates), which is partially covered by
`test_js_parity_automated.py::test_actual_cross_substrate_comparison`. Full
per-projection coverage would require 100+ cross-substrate tests — a dedicated parity
wave, not a quick fix. **Target wave:** Parity expansion wave.

### NB2. `pytest.skip()` residue across the suite
**Why deferred:** Assessed 2026-03-14 — most skips are legitimate guards for optional
dependencies (`jsonschema`, `claude_agent_sdk`) or missing fixture files (`/tmp/cp_s1a_before.json`).
`RCX_CI=1` already converts skips to test failures in CI, so CI coverage is not affected.
Removing these guards would make local runs fail on environments that don't have all
optional dependencies installed. **Not a code quality issue — this is correct defensive coding.**

### NB3. `pytest.importorskip("hypothesis")` residue in fuzzer files — RESOLVED (2026-03-14)

### NB4. Widespread Hypothesis health-check suppression
**Why deferred:** 312 instances of `suppress_health_check` across 46 test files.
Most suppress `HealthCheck.too_slow` because RCX projections are structurally
recursive (pattern matching + substitution + engine pipeline) and inherently
slower than typical hypothesis targets. Removing suppressions would cause CI
timeout failures. Each suppression needs individual assessment of whether the
underlying performance issue can be fixed. **Target wave:** Fuzzer hygiene wave
(large scope — dedicated session needed).

### NB5. Large volume of per-test `@settings` overrides
**Why deferred:** 1006 `@settings` decorators across 82 test files. These override
`max_examples`, `deadline`, and `suppress_health_check` individually because different
tests have different performance profiles (some projections terminate in 1 step, others
need 50+). A global profile would either be too loose (missing real issues) or too
strict (CI timeouts). Consolidation requires profiling each test to find safe shared
settings. **Target wave:** Fuzzer hygiene wave (same scope as NB4).

### NB6. Tool-test coverage remains thin relative to tool count
**Why deferred:** 81 tool scripts under mu/tools/, with tests covering ~30% directly.
Many tools are shell scripts (audit_fast.sh, debt_dashboard.sh, check_*.sh) that are
tested implicitly through CI pipeline integration. Adding explicit unit tests for each
shell script is high-effort / low-signal — the CI green gate IS their test. Python
tools under tools/checks/ have better coverage (check_gate_behavioral_pairs.py,
check_host_semantics_ratchet.py, etc. all have dedicated tests).
**What would help:** Add tests for the 5-10 highest-risk tools that aren't yet
tested (bridge_supervisor.py, run_review.py, enforce_l4_execution_contract.py).
**Target wave:** Tool-test coverage wave.
