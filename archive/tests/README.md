# Archived Tests

This directory contains tests that are **NOT RUN** by pytest.

Moved from `mu/tests/archive/` to `archive/tests/` (wave15, 2026-03-12) to free
growth cap headroom. The `conftest.py` blocks collection even if explicitly targeted.

## Why Archive Instead of Delete?

1. **Historical reference** - Understanding how the codebase evolved
2. **Resurrection if needed** - Regressions may require revisiting old tests
3. **Git history preservation** - Changes are tracked, but tests don't clutter active runs

## Contents

### `legacy/test_kernel_v0.py`
- Tests for the deprecated `Kernel` class (hash/trace/dispatch scaffolding)
- Superseded by `kernel.v1.json` projections via `step_kernel_mu()`
- See `mu/docs/core/MetaCircularKernel.v0.md` for terminology clarification

### `test_bytecode_vm_v0.py`
- Tests for the bytecode VM approach
- Superseded by kernel + seeds architecture

## Running Archived Tests (Not Recommended)

If you need to run these for debugging:

```bash
# Direct invocation bypasses collect_ignore
pytest archive/tests/legacy/test_kernel_v0.py -v

# Note: Will emit DeprecationWarnings for legacy Kernel usage
```

## Adding to Archive

When deprecating tests:
1. Move to `archive/tests/` (with subdirectory if appropriate)
2. Add a header comment explaining why archived
3. Update this README
