<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-18
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: none

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
-->

# Audit Reliability Plan v0

**Problem:** Schema validation tests (`test_snapshot_merge_schema_lock.py`, `test_world_trace_jsonschema_smoke.py`, `test_trace_event_schema_v1.py`) are environment-sensitive. They depend on `jsonschema` and/or `check-jsonschema` CLI, which have ABI fragility through the `rpds-py` C extension.

**Scope:** Planning and writeup. Runtime hardening (importorskip, health checks) was applied in `codex/redteam-docs-tooling-wave1` (merged 2026-02-18).

---

## Root Cause: jsonschema / rpds ABI Fragility

### Failure Chain

1. `jsonschema >= 4.16.0` introduced optional `rpds-py` dependency for faster ref resolution
2. `rpds-py` is a Rust-compiled C extension (OS/arch-specific binary wheel)
3. If the installed `rpds-py` wheel doesn't match the Python version or architecture:
   - `Draft7Validator` or `Draft202012Validator` calls crash with `AttributeError` or segfault
   - `check-jsonschema` CLI (which uses `jsonschema` internally) returns non-zero exit code
4. This is NOT a code bug — it's an environment/packaging mismatch

### Affected Test Files

| File | Dependency | Failure mode |
|------|-----------|-------------|
| `mu/tests/scripts/test_snapshot_merge_schema_lock.py` | `jsonschema.Draft7Validator` | ImportError or AttributeError at validate() |
| `mu/tests/scripts/test_world_trace_jsonschema_smoke.py` | `check-jsonschema` CLI binary | Non-zero returncode from CLI |
| `mu/tests/integration/test_trace_event_schema_v1.py` | `jsonschema.Draft202012Validator` | ImportError or AttributeError |

### Why This Isn't Caught by pip

- `pip install jsonschema` may install a cached `rpds-py` wheel from a different Python minor version
- Arm64 ↔ x86_64 Rosetta mismatches on macOS produce valid installs that crash at runtime
- CI runners may have different Python/OS combinations than local dev machines

---

## Stabilization Tiers

### Tier 1: Immediate Mitigation (DONE)

**Applied in `codex/redteam-docs-tooling-wave1` (merged 2026-02-18).**

| Fix | File | Effect |
|-----|------|--------|
| `pytest.importorskip("jsonschema", exc_type=ImportError)` | `test_snapshot_merge_schema_lock.py` | Graceful skip if jsonschema unavailable |
| `_check_jsonschema_healthy()` with returncode check | `test_world_trace_jsonschema_smoke.py` | Skip if CLI binary broken |
| `pytest.importorskip` with `exc_type=ImportError` | `test_trace_event_schema_v1.py` | Graceful skip if jsonschema unavailable |

**Trade-off:** Tests skip rather than crash. Schema validation is not enforced when the tool is broken. Acceptable because schema validation is defense-in-depth (the JSON structures are also tested by unit tests).

### Tier 2: Version Pinning (RECOMMENDED NEXT)

**Not yet applied.** Add explicit `jsonschema` version pin to `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "jsonschema>=4.17.0,<5.0.0",  # Pin major version for ABI stability
    "hypothesis",
    "pytest-xdist",
    "pytest-timeout",
]
```

**Trade-off:** Prevents accidental upgrade to incompatible major version. Minor version drift still possible. Low risk.

### Tier 3: CI Preflight Check (RECOMMENDED)

Add a preflight step to CI workflows that verifies jsonschema imports cleanly before running tests:

```yaml
# In .github/workflows/green_gate.yml and slow_tests.yml
- name: Verify schema tools
  run: |
    python3 -c "
    import jsonschema
    from jsonschema import Draft7Validator, Draft202012Validator
    print(f'jsonschema {jsonschema.__version__} OK')
    " || echo "WARNING: jsonschema not fully functional"
```

**Trade-off:** Makes environment issues visible in CI logs. Does not block the gate (schema tests already skip gracefully via Tier 1).

### Tier 4: Strict Reproducible (FUTURE)

Full lockfile (`pip freeze > requirements-test.txt`) with exact versions for all test dependencies including transitive deps. Rebuild CI image when lockfile changes.

**Trade-off:** Maximum reproducibility but high maintenance burden. Not recommended until CI flakiness becomes a recurring problem.

---

## Recommended Path

1. **Tier 1:** DONE (merged 2026-02-18)
2. **Tier 2:** Apply version pin in next routine dependency update
3. **Tier 3:** Add CI preflight in next CI workflow update
4. **Tier 4:** Defer unless recurring CI failures

---

## Local Preflight Command

Developers can verify their environment before running the full test suite:

```bash
# Quick schema tool check (add to personal workflow, not gated)
python3 -c "
import jsonschema
from jsonschema import Draft7Validator
print(f'jsonschema {jsonschema.__version__} OK')
" && echo 'Schema tools healthy' || echo 'WARNING: jsonschema not available — schema tests will skip'
```

If this fails, fix with:
```bash
pip install --force-reinstall jsonschema
```

---

## UNPROVEN Claims

1. **UNPROVEN:** "rpds-py ABI mismatch is the root cause of all schema test failures." This is the most likely cause based on library architecture analysis, but no specific failure log has been captured to confirm. If a failure is observed, capture the full traceback and update this section.

2. **UNPROVEN:** "Tier 2 version pinning prevents all ABI issues." Minor version bumps within the pinned range could still introduce rpds incompatibilities. The pin reduces but does not eliminate risk.

---

## References

- `mu/tests/scripts/test_snapshot_merge_schema_lock.py` — Tier 1 importorskip applied
- `mu/tests/scripts/test_world_trace_jsonschema_smoke.py` — Tier 1 health check applied
- `mu/tests/integration/test_trace_event_schema_v1.py` — Tier 1 importorskip applied
- `pyproject.toml` — Test dependency declarations
- `mu/docs/audit/CI_POLICY.md` — CI testing strategy
