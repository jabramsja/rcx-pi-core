---
description: "Test markers, speed enforcement, and git hook rules"
globs: ["**/test_*", "**/tests/*", "conftest.py", "tools/checks/check_test_speed.sh"]
---

| Category | Marker | Rule | Runs on |
|----------|--------|------|---------|
| **Core** | *(none)* | <10s, deterministic, no hypothesis | All tiers |
| **Slow** | `@pytest.mark.slow` | >10s OR uses `run_mu`/`run_algorithm_meta_circular`/`run_engine_pipeline`/`run_hemisphere_routing` | audit_all, nightly |
| **Fuzzer** | *(auto)* | Uses `@given`. Auto-detected by conftest.py. Do NOT manually mark. | audit_all, nightly |

**Enforcement:** `tools/checks/check_test_speed.sh` catches imports without `@pytest.mark.slow`. Whitelist: `# SPEED_OK: reason`.

**Git hooks:**

| Hook | Script | Purpose |
|------|--------|---------|
| pre-commit | `tools/pre-commit-doc-check` | Doc consistency, receipt verification |
| pre-push | `tools/pre-push-fast` | audit_fast.sh + L4 contract |
