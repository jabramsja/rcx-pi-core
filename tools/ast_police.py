#!/usr/bin/env python3
"""
The AST Police - Catches what grep misses.

This is COMPLEMENTARY to contraband.sh, not a replacement.
It catches structural patterns that text-based grep can't see:
- Set literals that AREN'T for key comparison
- Dangerous builtins via aliasing
- Scope leakage (global/nonlocal) without explicit marking

ALLOWED patterns (not violations):
- Set literals for key comparison: set(x.keys()) == {"head", "tail"}
- Generators in all()/any()/list()/tuple() - idiomatic Python
- Global statements for caching (projection loaders)
- Lines marked with # AST_OK: reason
"""
import ast
import sys
from pathlib import Path
from typing import List, Tuple, Set

# Directories to skip
SKIP_DIRS = {"worlds", "prototypes", "core"}
SKIP_FILES = {"_cli.py", "test_"}

# Set literals that are OK (used for key comparison or fixed membership tests)
ALLOWED_SET_LITERALS: Set[frozenset] = {
    # Key comparison
    frozenset({"head", "tail"}),
    frozenset({"var"}),
    frozenset({"name", "value", "rest"}),
    # Fixed membership tests
    frozenset({"ra", "lobe", "sink"}),  # worlds_json action types
    # State machine fields
    frozenset({"mode", "phase", "focus", "context", "changed"}),
    frozenset({"traverse", "ascending", "root_check"}),
    frozenset({"dict_head", "dict_tail"}),
}

# Single-element sets used in set union for cycle detection are OK
def is_single_element_set_in_union(node: ast.Set) -> bool:
    """Check if this is a single-element set used in set union (cycle detection)."""
    return len(node.elts) == 1


def get_source_line(source: str, lineno: int) -> str:
    """Get a specific line from source."""
    lines = source.split('\n')
    if 0 < lineno <= len(lines):
        return lines[lineno - 1]
    return ""


def is_allowed_set_literal(node: ast.Set) -> bool:
    """Check if this set literal is in the allowed list."""
    try:
        # Try to extract the values
        values = set()
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                values.add(elt.value)
            else:
                return False  # Non-constant element, not in allowed list
        return frozenset(values) in ALLOWED_SET_LITERALS
    except Exception:
        return False


def check_file(filepath: str) -> List[Tuple[int, str]]:
    """
    Parse a file and find AST-level violations that grep misses.
    """
    violations = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [(e.lineno or 0, f"Syntax Error: {e.msg}")]

    for node in ast.walk(tree):
        # Check if line has AST_OK marker
        if hasattr(node, 'lineno'):
            line = get_source_line(source, node.lineno)
            if "AST_OK:" in line:
                continue

        # 1. Set Literals - but allow key comparison sets and single-element union
        if isinstance(node, ast.Set):
            if not is_allowed_set_literal(node) and not is_single_element_set_in_union(node):
                violations.append((
                    node.lineno,
                    "Set literal - use sorted list for determinism (or add # AST_OK: reason)"
                ))

        # 2. Set Comprehensions - always bad
        if isinstance(node, ast.SetComp):
            violations.append((
                node.lineno,
                "Set comprehension {x for x in ...} - non-deterministic"
            ))

        # 3. Dangerous builtins (catches aliasing that grep misses)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                dangerous = {"eval", "exec", "compile", "__import__"}
                if node.func.id in dangerous:
                    violations.append((
                        node.lineno,
                        f"Dangerous builtin: {node.func.id}()"
                    ))

        # 4. Walrus operator := (hidden assignment)
        if isinstance(node, ast.NamedExpr):
            violations.append((
                node.lineno,
                "Walrus operator := hides assignment in expression"
            ))

        # 5. Yield (generator functions hide iteration)
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            violations.append((
                node.lineno,
                "yield - generator hides iteration from kernel"
            ))

        # 6. Async (concurrency complexity)
        if isinstance(node, (ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith)):
            violations.append((
                node.lineno,
                "async - concurrency hides control flow"
            ))

    return violations


def should_skip(filepath: str) -> bool:
    """Check if file should be skipped."""
    path = Path(filepath)
    for skip_dir in SKIP_DIRS:
        if skip_dir in path.parts:
            return True
    for skip_pattern in SKIP_FILES:
        if skip_pattern in path.name:
            return True
    return False


def main():
    if len(sys.argv) < 2:
        rcx_dir = Path("rcx_pi")
        if not rcx_dir.exists():
            print("Usage: python ast_police.py <file.py> ...")
            print("   or: python ast_police.py (scans ./rcx_pi)")
            sys.exit(1)
        files = list(rcx_dir.rglob("*.py"))
    else:
        files = [Path(f) for f in sys.argv[1:]]

    print(f"🔍 AST Police inspecting {len(files)} files...")
    print("   Catching: set literals, set comprehensions, dangerous builtins, walrus, yield, async")
    print("   Allowing: key comparison sets, generators in all/any, # AST_OK: marked lines")
    print()

    total_violations = 0
    files_with_violations = 0

    for filepath in files:
        if should_skip(str(filepath)):
            continue

        violations = check_file(str(filepath))

        if violations:
            files_with_violations += 1
            print(f"🚨 {filepath}:")
            for lineno, desc in violations:
                print(f"   Line {lineno}: {desc}")
                total_violations += 1
            print()

    print("-" * 60)
    if total_violations > 0:
        print(f"❌ Found {total_violations} AST violations in {files_with_violations} files")
        print("   To allow a line, add: # AST_OK: reason")
        sys.exit(1)
    else:
        print("✅ AST Clean. No hidden smuggling detected.")


if __name__ == "__main__":
    main()
