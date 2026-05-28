#!/bin/bash
# RCX Speed Enforcer — Static Analysis for Unmarked Slow Tests
#
# Catches unmarked tests that call slow kernel functions.
# These tests leak into the CI green gate and bloat CI time.
#
# Slow function set (each takes >10s per call):
#   run_mu, run_mu_structural, run_algorithm_meta_circular,
#   run_engine_pipeline, run_hemisphere_routing
#
# A slow call is handled if it has ANY of:
#   - module/class/function pytest.mark.slow
#   - module/class/function pytest.mark.fuzzer
#   - from hypothesis (auto-marked as fuzzer by conftest.py)
#   - # SPEED_OK: reason (explicit whitelist at file or test-function scope)
#
# Whitelist with: # SPEED_OK: reason
#
# Usage:
#   bash tools/check_test_speed.sh              # scan all tests/
#   bash tools/check_test_speed.sh tests/foo.py # scan specific file(s)

set -e

TESTS_DIR="${1:-./tests}"
EXIT_CODE=0
VIOLATIONS=0

echo "Scanning $TESTS_DIR for unmarked slow test files..."
echo ""

# Two-step detection for slow function imports (handles multiline imports):
# Step 1: File must have an import from the modules that contain slow functions.
# Matches rcx_pi.selfhost.* modules, package-level imports such as
# `from rcx_pi.selfhost import engine_pipeline`, and legacy rcx_pi.* modules.
SLOW_MODULE_IMPORT='rcx_pi(\.selfhost)?(\.(step_mu|engine|engine_pipeline)([^[:alnum:]_]|$)|[[:space:]]+import[[:space:]]+(step_mu|engine|engine_pipeline)([^[:alnum:]_]|$))'
# Step 2: File must mention a slow function name (on import line or in multiline block)
SLOW_FUNC_NAME='\b(run_mu_structural|run_algorithm_meta_circular|run_engine_pipeline|run_hemisphere_routing|run_mu)\b'

# Files/dirs to skip
SKIP_PATTERN='tests/stress/|tests/conftest\.py|test_js_parity_automated\.py|tests/fuzz/|fuzzer_config\.py'

scan_slow_tests() {
    local filepath="$1"
    python3 - "$filepath" <<'PY'
from __future__ import annotations

import ast
import sys
import tokenize
from io import StringIO

path = sys.argv[1]
text = open(path, encoding="utf-8").read()

SLOW_FUNCTIONS = {
    "run_mu",
    "run_mu_structural",
    "run_algorithm_meta_circular",
    "run_engine_pipeline",
    "run_hemisphere_routing",
}
SLOW_MODULES = {
    "rcx_pi.step_mu",
    "rcx_pi.engine",
    "rcx_pi.engine_pipeline",
    "rcx_pi.selfhost.step_mu",
    "rcx_pi.selfhost.engine",
    "rcx_pi.selfhost.engine_pipeline",
}
SLOW_MODULE_BASENAMES = {"step_mu", "engine", "engine_pipeline"}


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def expr_contains_pytest_mark(node: ast.AST, mark: str) -> bool:
    suffixes = (f"pytest.mark.{mark}", f"mark.{mark}")
    for child in ast.walk(node):
        name = dotted_name(child)
        if any(name.endswith(suffix) for suffix in suffixes):
            return True
    return False


def has_decorator_mark(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, mark: str) -> bool:
    return any(expr_contains_pytest_mark(decorator, mark) for decorator in node.decorator_list)


def body_pytestmark(body: list[ast.stmt], mark: str) -> bool:
    for stmt in body:
        value: ast.AST | None = None
        if isinstance(stmt, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark"
            for target in stmt.targets
        ):
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "pytestmark":
            value = stmt.value
        if value is not None and expr_contains_pytest_mark(value, mark):
            return True
    return False


def imports_hypothesis(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module == "hypothesis" or str(node.module).startswith("hypothesis.")):
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == "hypothesis" or alias.name.startswith("hypothesis.") for alias in node.names):
                return True
    return False


def root_name(node: ast.AST) -> str:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def is_pytest_raises(node: ast.AST) -> bool:
    return dotted_name(node).endswith("pytest.raises") or dotted_name(node) == "raises"


try:
    tree = ast.parse(text, filename=path)
except SyntaxError as exc:
    print(f"  ✗ SPEED: {path}:{exc.lineno or 0} could not be parsed for speed enforcement")
    sys.exit(0)

if imports_hypothesis(tree):
    sys.exit(0)

parent: dict[ast.AST, ast.AST] = {}
for node in ast.walk(tree):
    for child in ast.iter_child_nodes(node):
        parent[child] = node

test_functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = [
    node for node in ast.walk(tree)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
]

speed_ok_lines: set[int] = set()
for token in tokenize.generate_tokens(StringIO(text).readline):
    if token.type == tokenize.COMMENT and "SPEED_OK" in token.string:
        speed_ok_lines.add(token.start[0])


def line_in_node(line: int, node: ast.AST) -> bool:
    return getattr(node, "lineno", 0) <= line <= getattr(node, "end_lineno", getattr(node, "lineno", 0))


def has_speed_ok(node: ast.AST) -> bool:
    return any(line_in_node(line, node) for line in speed_ok_lines)


# A SPEED_OK comment outside a test function is a file-level source-inspection
# or intentionally-small-input whitelist. A SPEED_OK comment inside a test
# function exempts only that test function.
if any(not any(line_in_node(line, func) for func in test_functions) for line in speed_ok_lines):
    sys.exit(0)

if body_pytestmark(tree.body, "slow") or body_pytestmark(tree.body, "fuzzer"):
    sys.exit(0)

imported_slow_names: dict[str, str] = {}
imported_module_aliases: set[str] = set()
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module in SLOW_MODULES:
        for alias in node.names:
            if alias.name == "*":
                for name in SLOW_FUNCTIONS:
                    imported_slow_names[name] = name
            elif alias.name in SLOW_FUNCTIONS:
                imported_slow_names[alias.asname or alias.name] = alias.name
    elif isinstance(node, ast.ImportFrom) and node.module in {"rcx_pi", "rcx_pi.selfhost"}:
        for alias in node.names:
            if alias.name in SLOW_MODULE_BASENAMES:
                imported_module_aliases.add(alias.asname or alias.name)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in SLOW_MODULES:
                if alias.asname:
                    imported_module_aliases.add(alias.asname)
                else:
                    imported_module_aliases.add(alias.name.split(".", 1)[0])
                    imported_module_aliases.add(alias.name.rsplit(".", 1)[-1])

if not imported_slow_names and not imported_module_aliases:
    sys.exit(0)


def enclosing_class(func: ast.AST) -> ast.ClassDef | None:
    node = parent.get(func)
    while node is not None:
        if isinstance(node, ast.ClassDef):
            return node
        node = parent.get(node)
    return None


def is_marked_handled(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if has_speed_ok(func):
        return True
    if has_decorator_mark(func, "slow") or has_decorator_mark(func, "fuzzer"):
        return True
    cls = enclosing_class(func)
    if cls is None:
        return False
    return (
        has_decorator_mark(cls, "slow")
        or has_decorator_mark(cls, "fuzzer")
        or body_pytestmark(cls.body, "slow")
        or body_pytestmark(cls.body, "fuzzer")
    )


def call_slow_function(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return imported_slow_names.get(func.id)
    if isinstance(func, ast.Attribute):
        if func.attr in SLOW_FUNCTIONS and root_name(func) in imported_module_aliases:
            return func.attr
    return None


function_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = [
    node for node in ast.walk(tree)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
]
module_functions_by_name: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
class_functions_by_key: dict[tuple[ast.ClassDef, str], ast.FunctionDef | ast.AsyncFunctionDef] = {}
for candidate in function_nodes:
    cls = enclosing_class(candidate)
    if cls is None:
        module_functions_by_name.setdefault(candidate.name, []).append(candidate)
    else:
        class_functions_by_key[(cls, candidate.name)] = candidate


def local_callees(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[ast.FunctionDef | ast.AsyncFunctionDef]:
    callees: set[ast.FunctionDef | ast.AsyncFunctionDef] = set()
    cls = enclosing_class(func)
    for call in ast.walk(func):
        if not isinstance(call, ast.Call):
            continue
        call_func = call.func
        if isinstance(call_func, ast.Name):
            callees.update(module_functions_by_name.get(call_func.id, []))
        elif (
            isinstance(call_func, ast.Attribute)
            and isinstance(call_func.value, ast.Name)
            and call_func.value.id in {"self", "cls"}
            and cls is not None
        ):
            callee = class_functions_by_key.get((cls, call_func.attr))
            if callee is not None:
                callees.add(callee)
    callees.discard(func)
    return callees


def under_pytest_raises(call: ast.Call, func: ast.AST) -> bool:
    node = parent.get(call)
    while node is not None and node is not func:
        if isinstance(node, ast.With):
            if any(is_pytest_raises(item.context_expr) for item in node.items):
                return True
        node = parent.get(node)
    return False


def qualname(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    cls = enclosing_class(func)
    return f"{cls.name}.{func.name}" if cls else func.name


direct_slow_calls_by_func: dict[ast.FunctionDef | ast.AsyncFunctionDef, set[str]] = {
    func: {
        slow_name
        for call in ast.walk(func)
        if isinstance(call, ast.Call)
        for slow_name in [call_slow_function(call)]
        if slow_name is not None and not under_pytest_raises(call, func)
    }
    for func in function_nodes
}
transitive_slow_calls_by_func: dict[ast.FunctionDef | ast.AsyncFunctionDef, set[str]] = {
    func: set(slow_calls)
    for func, slow_calls in direct_slow_calls_by_func.items()
}
changed = True
while changed:
    changed = False
    for func in function_nodes:
        before = set(transitive_slow_calls_by_func[func])
        for callee in local_callees(func):
            transitive_slow_calls_by_func[func].update(transitive_slow_calls_by_func[callee])
        if transitive_slow_calls_by_func[func] != before:
            changed = True


for func in test_functions:
    if is_marked_handled(func):
        continue
    slow_calls = sorted(transitive_slow_calls_by_func[func])
    if slow_calls:
        funcs = ", ".join(slow_calls)
        print(
            f"  ✗ SPEED: {path}:{func.lineno} {qualname(func)} "
            f"calls {funcs} without @pytest.mark.slow"
        )
PY
}

check_file() {
    local filepath="$1"

    # Skip non-test files
    case "$filepath" in
        *conftest.py|*fuzzer_config.py) return ;;
    esac

    # Skip stress/fuzz dirs
    if echo "$filepath" | grep -qE "$SKIP_PATTERN" 2>/dev/null; then
        return
    fi

    # Two-step check: file must import from a slow module AND mention a slow function
    # This handles both single-line and multiline imports without false positives
    if ! grep -qE "$SLOW_MODULE_IMPORT" "$filepath" 2>/dev/null; then
        return
    fi
    if ! grep -qE "$SLOW_FUNC_NAME" "$filepath" 2>/dev/null; then
        return
    fi

    local violations
    violations="$(scan_slow_tests "$filepath")"
    if [ -n "$violations" ]; then
        echo "$violations"
        local count
        count=$(printf "%s\n" "$violations" | grep -c '^  ✗ SPEED:')
        VIOLATIONS=$((VIOLATIONS + count))
    fi
}

# If a specific file was passed, check just that file
if [ -f "$TESTS_DIR" ]; then
    check_file "$TESTS_DIR"
else
    # Scan all Python test files recursively
    while IFS= read -r filepath; do
        check_file "$filepath"
    done < <(find "$TESTS_DIR" -name "*.py" -type f 2>/dev/null | sort)
fi

echo ""

if [ $VIOLATIONS -gt 0 ]; then
    echo "------------------------------------------------------------"
    echo "❌ Speed violations found: $VIOLATIONS test(s)"
    echo ""
    echo "These tests call slow kernel functions without @pytest.mark.slow,"
    echo "so they leak into the CI green gate."
    echo ""
    echo "Fix: Add @pytest.mark.slow to the specific slow test or class."
    echo "For whole-file slow suites, use:"
    echo "    pytestmark = [pytest.mark.slow]"
    echo ""
    echo "If the import/call is intentionally fast or stubbed in a test:"
    echo "    # SPEED_OK: explain the bounded proof"
    echo ""
    EXIT_CODE=1
else
    echo "✅ No speed violations found."
fi

exit $EXIT_CODE
