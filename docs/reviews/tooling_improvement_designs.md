<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-05
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: none
-->

# Tooling Improvement Designs

Based on external reviewer assessment (Agent 8/10, Doc 8.5/10, Test 8/10, Code 6.5/10).

---

## Design 1: GOVERNED_FOLDERS Centralization

### Problem

`GOVERNED_FOLDERS` is defined in 3 places with different formats:

| File | Format | Line |
|------|--------|------|
| `tools/add_doc_headers.py` | `Path` objects | 24-33 |
| `tests/docs/test_doc_freshness.py` | `Path` objects | 29-38 |
| `tests/docs/test_doc_governance.py` | String paths | 42-51 |

If someone adds a new governed folder, they must update all 3 places. This is fragile.

### Proposed Solution

Create `tools/shared_doc_config.py` as single source of truth:

```python
"""Shared documentation configuration - single source of truth."""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Canonical list of governed folders (strings for portability)
GOVERNED_FOLDER_NAMES = [
    "docs/core",
    "docs/agents",
    "docs/audit",
    "docs/execution",
    "docs/cli",
    "docs/schemas",
    "docs/reviews",
    "tools/agents",
]

def get_governed_folders_as_paths() -> list[Path]:
    """Get governed folders as Path objects (for tools)."""
    return [REPO_ROOT / folder for folder in GOVERNED_FOLDER_NAMES]

def get_governed_folders_as_strings() -> list[str]:
    """Get governed folders as strings (for tests with string comparison)."""
    return GOVERNED_FOLDER_NAMES.copy()
```

### Migration

1. Create `tools/shared_doc_config.py`
2. Update `tools/add_doc_headers.py`:
   ```python
   from tools.shared_doc_config import get_governed_folders_as_paths
   GOVERNED_FOLDERS = get_governed_folders_as_paths()
   ```
3. Update `tests/docs/test_doc_freshness.py`:
   ```python
   from tools.shared_doc_config import get_governed_folders_as_paths
   GOVERNED_FOLDERS = get_governed_folders_as_paths()
   ```
4. Update `tests/docs/test_doc_governance.py`:
   ```python
   from tools.shared_doc_config import get_governed_folders_as_strings
   GOVERNED_FOLDERS = get_governed_folders_as_strings()
   ```

### Verification

Run after changes:
```bash
pytest tests/docs/ -v
python tools/add_doc_headers.py --check
```

### Effort

~15 minutes implementation, low risk.

---

## Design 2: mypy Integration

### Problem

No static type checking in CI. Type errors caught only at runtime.

### Options Considered

**Option A: Full mypy strict mode**
- Pros: Catches all type issues
- Cons: Requires adding type annotations to ~2,000 LOC, significant effort

**Option B: Gradual mypy (recommended)**
- Pros: Low initial effort, catches new issues
- Cons: Existing code not checked until annotated

**Option C: pyright instead of mypy**
- Pros: Faster, better defaults
- Cons: Different ecosystem, less familiar

### Recommended: Option B (Gradual mypy)

Add to `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_ignores = true
# Gradual typing - don't require annotations on existing code
ignore_missing_imports = true
check_untyped_defs = false

# Strict for new code (opt-in per file)
[[tool.mypy.overrides]]
module = "tools.shared_*"
strict = true
```

### Migration Path

1. Add mypy config to pyproject.toml (no enforcement yet)
2. Add mypy to audit_fast.sh with `--ignore-missing-imports`
3. Gradually add type annotations to new/modified files
4. After 3+ months, increase strictness

### Verification

```bash
pip install mypy
mypy rcx_pi/selfhost/ --ignore-missing-imports
```

### Effort

- Config: 10 minutes
- Full annotation: 2-4 hours (defer)

---

## Implementation Priority

| Design | Effort | Risk | Value | Priority |
|--------|--------|------|-------|----------|
| GOVERNED_FOLDERS centralization | 15 min | Low | Medium | 1 |
| mypy gradual integration | 10 min config | Low | Medium | 2 |

**Recommendation:** Implement Design 1 now, add mypy config but don't enforce until team ready.

---

## Quick Wins Already Implemented

| Fix | Status |
|-----|--------|
| agents.sh CLI (`--quick` → `--depth quick`) | Done |
| structural_lint.py in audit scripts | Done |
| ruff config in pyproject.toml | Done |
| roadmap/ in pre-commit pattern | Done |
