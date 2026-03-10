# Red-Team Wave 3: Tests Audit — Deferred Non-Blockers

**Wave ID:** redteam-2026-03-09-wave3-tests
**Wave Class:** MAINTENANCE
**Scope:** `mu/tests/` (~261 test files)
**Date:** 2026-03-09
**Plan iterations:** 11 bridge rounds (R1-R11, GO on R11)

---

## Blocker Findings (FIXED)

### B1. Speed classification violations — 4 test files
**Files:**
- `mu/tests/l4_gates/test_parity_hardening_gate.py` — `run_engine_pipeline` call, added `@pytest.mark.slow` on class
- `mu/tests/research/test_d006_h1_fuel_threading.py` — `run_mu` call, added `pytestmark = [pytest.mark.slow]`
- `mu/tests/research/test_d007_h3_negative_control.py` — `run_mu` + `run_engine_pipeline`, added `pytestmark = [pytest.mark.slow]`
- `mu/tests/tools/test_check_underscore_imports.py` — `run_mu` in string literal only, added `# SPEED_OK`

**Evidence:** `check_test_speed.sh` now passes (0 violations).

### B2. Stale theater-risk allowlist entries — 3 removed
Tests `test_classification_parity_gate_importable`, `test_engine_exit_reason_gate_importable`, `test_engine_terminal_event_gate_importable` no longer exist in `test_terminal_classifier_integration_gate.py`. Removed from `theater_allowlist.json`, count updated 11→8.

**Evidence:** `check_theater_risk_ratchet.py` passes with 8/8, no removals.

---

## Non-Blocker Findings (DEFERRED)

### NB1. Parity test seed coverage gaps (Category C)
**Severity:** low
**Finding:** 3 seeds listed in CLAUDE.md L3 parity list (`fix.v1.json`, `metabolize_cycle.v1.json`, `terminal_classify.v1.json`) are not referenced in `mu/tests/parity/` specifically, but ARE referenced in other test directories (`structural/`, `l4_gates/`). Coverage exists, just not through the parity test mechanism.
**Recommended action:** Add these seeds to `test_seed_loading_parity.py` for explicit cross-substrate comparison.

### NB2. `pytest.skip()` usage — 42 sites across test suite
**Severity:** low
**Finding:** Many `pytest.skip()` calls are legitimate (missing optional dependencies like `graphviz`, `jsonschema`, `claude_agent_sdk`; missing fixture files). Most are conditional skips for environment-dependent tests.
**Risk:** Some could mask real failures if the skip condition becomes permanently true.
**Recommended action:** Periodic review; no action needed now.

### NB3. `pytest.importorskip("hypothesis")` — 12 fuzzer files
**Severity:** low
**Finding:** Fuzzer tests use `pytest.importorskip("hypothesis")` which silently skips the entire module if hypothesis is not installed. This is by design (hypothesis is optional in minimal installs) but means fuzzers silently disappear in some CI configurations.
**Risk:** If CI image loses hypothesis, all 498 fuzzer tests silently skip.
**Recommended action:** CI nightly should assert `hypothesis` is importable before running fuzzer suite.

### NB4. Hypothesis `suppress_health_check=[HealthCheck.too_slow]` — widespread
**Severity:** low
**Finding:** 12 parity tests + 8 recurrence v2 fuzz tests + 10 deep fuzz tests + `conftest.py` profiles all suppress `HealthCheck.too_slow`. One fuzzer suppresses `HealthCheck.filter_too_much`.
**Risk:** Suppressing health checks can mask genuine performance regressions.
**Recommended action:** Review whether `too_slow` suppression is still needed after performance improvements. Low priority.

### NB5. `@settings` overrides — 101 of 498 fuzzers (20%) bypass profile defaults
**Severity:** low
**Finding:** 101 `@given` tests have explicit `max_examples` in `@settings`, bypassing Hypothesis profile-driven example counts. Heaviest files: `test_js_parity_automated.py` (12), `test_selfhost_fuzzer.py` (11), `test_normalization_roundtrip_fuzzer.py` (8).
**Risk:** Profile changes (dev→ci_full) won't affect these tests.
**Recommended action:** Audit top-override files to determine if overrides are necessary or can use profile defaults.

### NB6. Tool test coverage ratio — 28 test files for 67 tools
**Severity:** low
**Finding:** Category F automated checks show 28 tool test files for 67 tool scripts. Exact coverage mapping requires manual review due to compositional path-building in tests.
**Recommended action:** Manual spot-check of untested tools. Not a blocker for Wave 3.
