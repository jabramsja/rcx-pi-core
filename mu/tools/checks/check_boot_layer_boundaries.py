#!/usr/bin/env python3
"""Boot layer boundary enforcer: prevent upward imports in the 3-layer bootstrap.

The bootstrap has three layers with a strict dependency direction:

    Boot2 (engine_pipeline.py) → Boot1 (step_mu.py) → Boot0 (eval_seed.py)

Rules:
1. Boot0 MUST NOT import from Boot1 or Boot2
2. Boot1 MUST NOT import from Boot2
3. Boot2 may import from Boot0 and Boot1
4. No import cycles in the semantic dependency graph

Shared modules (mu_type, kernel, seed_integrity, projection_loader, match_mu,
subst_mu) are not layered — any boot layer may import from them.

Implementation: AST-based import graph analysis. Parses `from . X import ...`
statements and checks for upward edges. Does NOT use subprocess import probing
(unsound for detecting cycles when names are defined before the back-edge import).

Integration:
  - pre-commit-doc-check
  - audit_fast.sh
  - audit_all.sh
  - green_gate.sh

Usage:
  python3 tools/checks/check_boot_layer_boundaries.py
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(
    subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
)

PY_SELFHOST = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"

# Boot layer file mapping
BOOT0_FILES = {"eval_seed.py"}
BOOT1_FILES = {"step_mu.py"}
BOOT2_FILES = {"engine_pipeline.py"}

# Shared modules (not layered — any boot layer may import from these)
SHARED_MODULES = {
    "mu_type", "kernel", "seed_integrity", "projection_loader",
    "match_mu", "subst_mu", "recurrence_mu", "host_types",
}


def _get_relative_imports(filepath: Path) -> list[tuple[int, str]]:
    """Parse AST and return (lineno, module_name) for relative imports."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, str(filepath))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            if node.module:
                # from .module import name
                imports.append((node.lineno, node.module))
            else:
                # from . import name1, name2 — module is None
                for alias in (node.names or []):
                    imports.append((node.lineno, alias.name))
    return imports



def check_boundaries() -> list[str]:
    """Return list of violation messages (empty = pass)."""
    violations = []

    # --- Rule 1: Boot0 must not import from Boot1 or Boot2 ---
    for boot0_file in BOOT0_FILES:
        path = PY_SELFHOST / boot0_file
        if not path.exists():
            violations.append(f"Boot0 file missing: {boot0_file}")
            continue
        for lineno, module in _get_relative_imports(path):
            # Check if it imports from Boot1 or Boot2 files
            base = module.split(".")[0]
            boot1_bases = {f.removesuffix(".py") for f in BOOT1_FILES}
            boot2_bases = {f.removesuffix(".py") for f in BOOT2_FILES}
            if base in boot1_bases:
                violations.append(
                    f"Boot0 → Boot1 violation: {boot0_file}:{lineno} imports from {module}"
                )
            elif base in boot2_bases:
                violations.append(
                    f"Boot0 → Boot2 violation: {boot0_file}:{lineno} imports from {module}"
                )

    # --- Rule 2: Boot1 must not import from Boot2 ---
    for boot1_file in BOOT1_FILES:
        path = PY_SELFHOST / boot1_file
        if not path.exists():
            violations.append(f"Boot1 file missing: {boot1_file}")
            continue
        boot2_bases = {f.removesuffix(".py") for f in BOOT2_FILES}

        for lineno, module in _get_relative_imports(path):
            base = module.split(".")[0]
            if base in boot2_bases:
                violations.append(
                    f"Boot1 → Boot2 violation: {boot1_file}:{lineno} imports from {module}"
                )

    # --- Rule 3: Boot2 may import from Boot0 and Boot1 (no violations possible) ---
    # Just verify the file exists
    for boot2_file in BOOT2_FILES:
        path = PY_SELFHOST / boot2_file
        if not path.exists():
            violations.append(f"Boot2 file missing: {boot2_file}")

    # --- Rule 4: No import cycles ---
    # Build directed graph: file → set of imported boot-layer files
    graph: dict[str, set[str]] = {}
    all_boot_files = BOOT0_FILES | BOOT1_FILES | BOOT2_FILES
    all_boot_bases = {f.removesuffix(".py"): f for f in all_boot_files}

    for boot_file in all_boot_files:
        path = PY_SELFHOST / boot_file
        if not path.exists():
            continue
        deps: set[str] = set()
        for lineno, module in _get_relative_imports(path):
            base = module.split(".")[0]
            if base in all_boot_bases:
                deps.add(all_boot_bases[base])
        graph[boot_file] = deps

    # Simple DFS cycle detection
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _dfs(node: str, path_: list[str]) -> str | None:
        if node in in_stack:
            cycle_start = path_.index(node)
            return " → ".join(path_[cycle_start:] + [node])
        if node in visited:
            return None
        visited.add(node)
        in_stack.add(node)
        path_.append(node)
        for dep in graph.get(node, set()):
            result = _dfs(dep, path_)
            if result:
                return result
        path_.pop()
        in_stack.discard(node)
        return None

    for start in all_boot_files:
        cycle = _dfs(start, [])
        if cycle:
            violations.append(f"Import cycle detected: {cycle}")
            break  # One cycle is enough

    return violations


def main() -> int:
    violations = check_boundaries()
    if violations:
        print("FAIL: Boot layer boundary violations found:")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    else:
        print("PASS: Boot layer boundaries clean (Boot0 → Boot1 → Boot2, no upward imports)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
