#!/usr/bin/env python3
"""L4 Gate Test Integrity Classifier (MAINT-M1).

Scans L4 gate test files and classifies each test method into:
  - behavioral:    Calls runtime functions, checks actual outputs
  - source_lock:   Reads source code (AST/text inspection), asserts structure
  - hybrid:        Both behavioral and source inspection
  - theater_risk:  Vacuous assertions, no meaningful checks

Usage:
    python tools/checks/check_gate_behavioral_pairs.py          # Human-readable (mismatch enforced by default)
    python tools/checks/check_gate_behavioral_pairs.py --json   # JSON output
    python tools/checks/check_gate_behavioral_pairs.py --fail-on-theater   # Exit 1 if theater found
    python tools/checks/check_gate_behavioral_pairs.py --fail-on-mismatch  # Exit 1 on proof-class mismatch (also default)
    python tools/checks/check_gate_behavioral_pairs.py --no-fail-on-mismatch  # Suppress default mismatch enforcement
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

def _find_repo_root() -> Path:
    """Find repo root by searching upward for pyproject.toml."""
    d = Path(__file__).resolve().parent
    while d != d.parent:
        if (d / "pyproject.toml").exists():
            return d
        d = d.parent
    return Path(__file__).resolve().parents[2]

REPO_ROOT = _find_repo_root()
L4_GATES_DIR = REPO_ROOT / "mu" / "tests" / "l4_gates"

# ---------------------------------------------------------------------------
# Classification heuristics
# ---------------------------------------------------------------------------

# Names that indicate source inspection (reading/parsing source code).
SOURCE_LOCK_CALLS = frozenset({
    "ast.parse", "inspect.getsource", "inspect.getsourcefile",
    "re.search", "re.findall", "re.match",
})

# Names that indicate behavioral (runtime) testing.
BEHAVIORAL_CALLS = frozenset({
    "_service_boundary_effect", "_build_ontology_promotion_candidate",
    "_collect_ontology_evidence",
    "subprocess.run", "_run_js_expr",
    "run_mu", "step_kernel_mu", "run_mu_structural",
    "_validate_ontology_promotion_record", "validateOntologyPromotionRecord",
    "validate_no_kernel_reserved_fields",
    "monkeypatch.setitem", "monkeypatch.setattr",
})

# Theater patterns: assertion nodes that are vacuous.
THEATER_PATTERNS = {"assert True", "assert 1"}

# Detector 2 — raises-on-failure validators: the call itself IS the assertion
# (no-exception-is-pass). A bare-name (or self/cls method) call to one of these
# is a meaningful runtime check, even with no surrounding assert. Seeded from the
# names in the founder-allowlist defer_reasons; keep this list small and explicit.
#
# Registry membership requires the callee to return ``None`` and raise on every
# violation, so "did not raise" is the whole verdict:
#   * ``_verify_bundle_provenance``      (step_mu.py) raises ValueError on a
#     source_digest/SEED_CHECKSUMS mismatch — N15 fail-closed provenance.
#   * ``_validate_match_bridge_ordering`` (match_mu.py) raises ValueError when
#     bridge.var.check_existing does not precede match.var.
# Names are matched exactly (no wildcard, prefix, or substring matching).
RAISES_ON_FAILURE_VALIDATORS = frozenset({
    "validate_bundle", "validateBundle", "_validate_template",
    "_verify_bundle_provenance", "_validate_match_bridge_ordering",
})

# Detector 1 — bound on how far same-module helper calls are followed when
# gathering proof-class signals (test -> helper -> helper). Cycle-guarded.
_MAX_HELPER_DEPTH = 2


def _extract_call_names(node: ast.AST) -> set[str]:
    """Extract all call target names from an AST node (function/method calls)."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name):
                    names.add(f"{func.value.id}.{func.attr}")
                else:
                    names.add(func.attr)
    return names


def _normalize_callee(func: ast.AST) -> tuple[str | None, str | None]:
    """Recover the candidate helper name + scope kind from a call's ``func`` node.

    Two — and only two — callee forms are normalized (bounds are firm):
      * bare name      ``foo(...)``        -> ("foo", "bare")   resolve in module map
      * self/cls method ``self._foo(...)`` -> ("_foo", "method") resolve in own class

    Any other shape (arbitrary attribute receiver, subscript, call-of-call, ...)
    returns ``(None, None)`` so the caller contributes no helper signal and does
    not recurse. ``cls`` is treated like ``self`` (classmethod helpers).
    """
    if isinstance(func, ast.Name):
        return func.id, "bare"
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id in ("self", "cls"):
            return func.attr, "method"
    return None, None


def _has_meaningful_assertion(node: ast.AST, strict: bool = False) -> bool:
    """Check if a function body has meaningful assertions (not vacuous).

    ``strict=True`` is used ONLY when following a same-module *helper* body
    (detector 1, depth >= 1). In strict mode a bare ``ast.Compare`` is NOT
    treated as a meaningful assertion: a standalone comparison inside a helper is
    almost always control flow (``if n >= 20:``, ``if i < limit:``) — plumbing,
    not a delegated check — and counting it would rescue purely observational
    tests (timing/stat probes that print results with no gating assertion) by
    mistaking a helper's loop/branch comparison for the test's assertion. Real
    ``assert`` statements and ``pytest.raises`` ARE delegated checks and still
    count in strict mode; only the standalone-``Compare`` heuristic is dropped.
    ``strict=False`` (the test's OWN body) preserves the exact pre-broadening
    heuristic.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            # Check for vacuous: `assert True`, `assert 1`
            test = child.test
            if isinstance(test, ast.Constant) and test.value in (True, 1):
                continue
            return True
        # pytest.raises counts as meaningful
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "raises":
                return True
        # A bare comparison (not inside an assert) is the test's own loose check
        # only in its OWN body; a helper's standalone Compare is control flow,
        # never the test's assertion (see strict docstring).
        if not strict and isinstance(child, ast.Compare):
            return True
    return False


def _has_raise_or_subprocess(node: ast.AST) -> bool:
    """Check if a function calls subprocess, raises, or invokes a raises-on-failure validator.

    Detector 2: a call to a recognized raises-on-failure validator
    (RAISES_ON_FAILURE_VALIDATORS) is itself the assertion — the call passes
    iff it does not raise. Recognized in the bare-name and self/cls method
    forms only (same normalization as detector 1).
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Raise):
            return True
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "run":
                if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                    return True
            if isinstance(func, ast.Name) and func.id == "_run_js_expr":
                return True
            # Detector 2: no-exception-is-pass validator call.
            name, _kind = _normalize_callee(func)
            if name in RAISES_ON_FAILURE_VALIDATORS:
                return True
    return False


def _body_signals(func_node: ast.AST, strict: bool = False) -> tuple[bool, bool, bool, bool]:
    """Proof-class signals for a function's OWN body only (no recursion).

    Returns ``(has_source, has_behavioral, has_assertion, has_raise_or_subprocess)``.
    This mirrors the pre-broadening own-body computation exactly, so a function
    with no resolvable helpers classifies identically to before.

    ``strict`` is forwarded to ``_has_meaningful_assertion``: a caller analyzing a
    same-module *helper* body (depth >= 1) passes ``strict=True`` so the helper's
    control-flow ``ast.Compare`` is not mistaken for the test's assertion. The
    test's own body uses ``strict=False`` (default), matching pre-broadening.
    """
    call_names = _extract_call_names(func_node)

    has_source = bool(call_names & SOURCE_LOCK_CALLS)
    # Also check for file reads of .py/.js (common source_lock pattern)
    func_source = ast.unparse(func_node)
    if ".read_text()" in func_source or "open(" in func_source:
        has_source = True

    has_ros = _has_raise_or_subprocess(func_node)
    has_behavioral = bool(call_names & BEHAVIORAL_CALLS) or has_ros
    has_assertion = _has_meaningful_assertion(func_node, strict=strict)

    return has_source, has_behavioral, has_assertion, has_ros


def _build_resolution_maps(
    tree: ast.AST,
) -> tuple[dict[str, ast.AST | None], dict[ast.AST, dict[str, ast.AST | None]]]:
    """Build scope-correct helper-resolution maps for one module.

    Returns ``(module_map, class_method_map)``:
      * ``module_map``       — ``{name: FunctionDef}`` for MODULE-LEVEL
        ``FunctionDef``s only (direct module children plus those inside
        module-level control flow); functions lexically nested inside another
        function are EXCLUDED. These are the targets of bare-name
        (``ast.Name``) calls. A bare name in a test (or in a module-level
        helper) resolves through Python's local→module-global→builtin chain,
        never to a sibling function's locals, so a nested helper such as one
        defined inside a ``factory()`` is unreachable by a bare-name call from
        a different scope and must fail closed. A name defined more than once at
        module scope maps to ``None`` (ambiguous -> fail-closed, never bound to
        an arbitrary later definition).
      * ``class_method_map`` — ``{ClassDef: {method_name: FunctionDef}}``. A
        ``self``/``cls`` method call resolves ONLY against its own class's map,
        so duplicate method names across classes (e.g. five ``_js_eval`` methods
        in five classes) never collide. Duplicate method names WITHIN one class
        map to ``None`` (fail-closed).

    A single flat ``{name: FunctionDef}`` map is intentionally NOT built: it
    would collapse same-name methods to the last definition and misroute the
    proof class.
    """
    # Per-class method maps; also record which FunctionDefs are class methods
    # so they are excluded from the bare-name module map.
    method_nodes: set[ast.AST] = set()
    class_method_map: dict[ast.AST, dict[str, ast.AST | None]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods: dict[str, ast.AST | None] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_nodes.add(item)
                    # Duplicate method name within this class -> fail-closed.
                    methods[item.name] = None if item.name in methods else item
            class_method_map[node] = methods

    # FunctionDefs lexically nested inside another function are NOT reachable by
    # a bare-name call from a test's (or another helper's) scope: Python resolves
    # bare names through local -> module-global -> builtin, never into a sibling
    # function's locals. Exclude them so a bare-name call to such a name fails
    # closed instead of binding an unreachable nested helper (e.g. a helper
    # defined inside a factory()).
    nested_in_func: set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if inner is not node and isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nested_in_func.add(inner)

    # Module map: module-level FunctionDefs only — not class methods and not
    # functions nested inside another function.
    module_map: dict[str, ast.AST | None] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node not in method_nodes
            and node not in nested_in_func
        ):
            # Duplicate module-level name -> fail-closed.
            module_map[node.name] = None if node.name in module_map else node

    return module_map, class_method_map


def _resolve_helper(
    name: str,
    kind: str | None,
    module_map: dict[str, ast.AST | None],
    class_methods: dict[str, ast.AST | None] | None,
) -> ast.AST | None:
    """Resolve a normalized callee to a unique helper in its proper scope.

    Bare names resolve against ``module_map``; ``self``/``cls`` methods resolve
    against the enclosing class's ``class_methods`` ONLY. Returns ``None`` when
    the name is absent OR ambiguous (mapped to ``None``) — fail-closed, never a
    same-named helper from another class or a later shadowing definition.
    """
    if kind == "bare":
        return module_map.get(name)
    if kind == "method":
        if class_methods is None:
            return None
        return class_methods.get(name)
    return None


def _collect_signals(
    func_node: ast.AST,
    module_map: dict[str, ast.AST | None],
    class_methods: dict[str, ast.AST | None] | None,
    depth: int,
    visited: frozenset[str],
) -> tuple[bool, bool, bool, bool]:
    """OR a function's own-body signals with its same-module helpers' signals.

    Detector 1: follows bare-name and ``self``/``cls`` method calls into their
    resolved helper bodies (same module only), folding each helper's full
    proof-class signal set — source_lock signals included, so a source-reading
    helper keeps its caller classified source_lock — into the result. Bounded by
    ``_MAX_HELPER_DEPTH`` and cycle-guarded via ``visited``.

    A helper body (depth >= 1) is analyzed with ``strict=True`` assertion
    semantics: a helper's standalone ``ast.Compare`` is control flow, not a
    delegated check, so it does NOT rescue an otherwise-observational test from
    ``theater_risk``. Only real ``assert`` / ``pytest.raises`` / raise /
    subprocess / validator signals in a helper count. The test's own body
    (depth 0) keeps the full pre-broadening heuristic.

    Returns ``(has_source, has_behavioral, has_assertion, has_raise_or_subprocess)``.
    """
    # Own body uses the full heuristic at depth 0 (the test itself) but the
    # strict heuristic at depth >= 1 (a helper), so a helper's control-flow
    # Compare never counts as the test's assertion.
    has_source, has_behavioral, has_assertion, has_ros = _body_signals(
        func_node, strict=(depth > 0)
    )

    if depth >= _MAX_HELPER_DEPTH:
        return has_source, has_behavioral, has_assertion, has_ros

    for child in ast.walk(func_node):
        if not isinstance(child, ast.Call):
            continue
        name, kind = _normalize_callee(child.func)
        if name is None or name in visited:
            continue
        helper = _resolve_helper(name, kind, module_map, class_methods)
        if helper is None:
            continue
        # Scope tracks the function being entered: a self/cls method recurses
        # within its own class; a bare-name (module-level) helper has no
        # enclosing class, so its self/cls calls fail closed.
        helper_class_methods = class_methods if kind == "method" else None
        h_src, h_beh, h_assert, h_ros = _collect_signals(
            helper, module_map, helper_class_methods, depth + 1, visited | {name}
        )
        has_source = has_source or h_src
        has_behavioral = has_behavioral or h_beh
        has_assertion = has_assertion or h_assert
        has_ros = has_ros or h_ros

    return has_source, has_behavioral, has_assertion, has_ros


def classify_method(
    func_node: ast.FunctionDef,
    module_map: dict[str, ast.AST | None] | None = None,
    class_methods: dict[str, ast.AST | None] | None = None,
) -> str:
    """Classify a test method AST node.

    ``module_map`` / ``class_methods`` (from ``_build_resolution_maps``) enable
    same-module helper following (detector 1). When omitted, only the method's
    own body is analyzed — identical to the pre-broadening behavior, so direct
    unit-test calls to ``classify_method(node)`` are unaffected.

    Helper following is a THEATER-RESCUE step, not a reclassifier: it runs ONLY
    when the test's own body has no meaningful check of its own (would otherwise
    be ``theater_risk`` — its real assertions/validators live in same-module
    helpers). A test that already makes a meaningful check in its own body is
    already correctly classified, so its proof class is NOT re-opened by helper
    following — this keeps the broadening from flipping the 100+ legitimately
    ``behavioral`` tests that merely *also* call a source-reading helper. When
    rescue does run, it folds the helper's FULL signal set (``has_source`` /
    ``has_behavioral`` / ``has_assertion``); the source/behavioral/hybrid
    decision ladder below is unchanged.
    """
    # Own-body signals first (pre-broadening computation, exact).
    has_source, has_behavioral, has_assertion, has_ros = _body_signals(func_node)

    # Theater-rescue ONLY: if the own body carries no meaningful check, follow
    # same-module helpers to recover checks (assertions / validators / source
    # reads) that live in helper bodies. The fold surfaces the helper's full
    # proof-class signal set, so a source-reading helper keeps its caller
    # source_lock.
    if not has_assertion and not has_ros:
        has_source, has_behavioral, has_assertion, has_ros = _collect_signals(
            func_node,
            module_map if module_map is not None else {},
            class_methods,
            depth=0,
            visited=frozenset({func_node.name}),
        )

    if not has_assertion and not has_ros:
        return "theater_risk"

    if has_source and has_behavioral:
        return "hybrid"
    if has_source:
        return "source_lock"
    if has_behavioral:
        return "behavioral"

    # Has meaningful assertions but no source/behavioral indicators
    # → behavioral (unit test with direct assertions)
    return "behavioral"


def scan_file(filepath: Path) -> dict:
    """Scan a test file and classify all test methods.

    Returns: {class_name: {method_name: classification}}
    """
    source = filepath.read_text()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return {}

    # Scope-correct helper-resolution maps for same-module helper following.
    module_map, class_method_map = _build_resolution_maps(tree)

    classes: dict[str, dict[str, str]] = {}

    # Scan class-level test methods
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods = class_method_map.get(node)
            methods: dict[str, str] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("test_"):
                        methods[item.name] = classify_method(item, module_map, class_methods)
            if methods:
                classes[node.name] = methods

    # Scan module-level test functions (not inside any class)
    module_funcs: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                module_funcs[node.name] = classify_method(node, module_map, None)
    if module_funcs:
        classes["<module>"] = module_funcs

    return classes


def scan_directory(gate_dir: Path) -> dict:
    """Scan all test files in the L4 gates directory."""
    results: dict[str, dict] = {}
    for filepath in sorted(gate_dir.glob("test_*.py")):
        classes = scan_file(filepath)
        if classes:
            rel_path = str(filepath.relative_to(REPO_ROOT))
            results[rel_path] = {"classes": classes}
    return results


def compute_summary(file_results: dict) -> dict:
    """Compute summary counts from file results."""
    counts = {"behavioral": 0, "source_lock": 0, "hybrid": 0, "theater_risk": 0}
    for file_data in file_results.values():
        for class_data in file_data["classes"].values():
            for classification in class_data.values():
                counts[classification] = counts.get(classification, 0) + 1
    total = sum(counts.values())
    return {"total": total, **counts}


# Keywords in class names that imply runtime/behavioral proof obligation.
# "Parity" excluded — source-level parity (constant equality, registry
# presence) is legitimate source_lock. Only "Runtime" and "Wiring" imply
# actual JS execution proof.
PROOF_CLASS_KEYWORDS = re.compile(r"runtime|wiring", re.IGNORECASE)


def find_proof_class_mismatches(file_results: dict) -> list[str]:
    """Detect proof-class governance loophole.

    A class whose name contains "Runtime" or "Wiring" (case-insensitive)
    claims to provide runtime/behavioral evidence. If ALL of its test methods are
    classified as ``source_lock``, the class is making a structural claim it cannot
    back — that's a proof-class mismatch.

    Returns a list of ``"filepath::ClassName"`` strings for every mismatched class.
    """
    mismatches: list[str] = []
    for filepath, file_data in file_results.items():
        for class_name, methods in file_data["classes"].items():
            if not PROOF_CLASS_KEYWORDS.search(class_name):
                continue
            classifications = set(methods.values())
            # A class claiming Runtime/Wiring must have at least one behavioral
            # method (not source_lock, not theater_risk). Mixed source_lock +
            # theater_risk still fails — theater_risk is not behavioral proof.
            behavioral = classifications - {"source_lock", "theater_risk"}
            if not behavioral:
                mismatches.append(f"  {filepath}::{class_name}")
    return mismatches


def format_human(file_results: dict, summary: dict) -> str:
    """Format results for human-readable output."""
    lines = ["=== L4 Gate Test Integrity Report ===", ""]

    for filepath, file_data in file_results.items():
        lines.append(filepath)
        for class_name, methods in file_data["classes"].items():
            lines.append(f"  {class_name} ({len(methods)} methods)")
            class_counts = {"behavioral": 0, "source_lock": 0, "hybrid": 0, "theater_risk": 0}
            for classification in methods.values():
                class_counts[classification] += 1
            for cat, count in class_counts.items():
                if count > 0:
                    lines.append(f"    {cat}: {count}")
        lines.append("")

    lines.append("Summary:")
    total = summary["total"]
    for cat in ["behavioral", "source_lock", "hybrid", "theater_risk"]:
        count = summary[cat]
        pct = f"{100 * count / total:.1f}%" if total > 0 else "0.0%"
        lines.append(f"  {cat}: {count}  ({pct})")
    lines.append(f"  Total: {total}")
    lines.append("")
    return "\n".join(lines)


def main():
    KNOWN_FLAGS = {"--json", "--fail-on-theater", "--fail-on-mismatch", "--no-fail-on-mismatch"}
    args = sys.argv[1:]
    # Fail-closed: reject positional args (no positional args accepted)
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        print(f"ERROR: Unexpected positional arg(s): {', '.join(positional)}", file=sys.stderr)
        print(f"  This tool accepts only flags: {', '.join(sorted(KNOWN_FLAGS))}", file=sys.stderr)
        sys.exit(2)
    # Fail-closed: reject unknown flags
    unknown = [a for a in args if a.startswith("--") and a not in KNOWN_FLAGS]
    if unknown:
        print(f"ERROR: Unknown flag(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"  Known flags: {', '.join(sorted(KNOWN_FLAGS))}", file=sys.stderr)
        sys.exit(2)
    json_mode = "--json" in args
    fail_on_theater = "--fail-on-theater" in args
    # Mismatch enforcement is ON by default; --no-fail-on-mismatch suppresses it.
    fail_on_mismatch = "--no-fail-on-mismatch" not in args

    gate_dir = L4_GATES_DIR
    if not gate_dir.is_dir():
        print(f"ERROR: Gate test directory not found: {gate_dir}", file=sys.stderr)
        sys.exit(1)

    file_results = scan_directory(gate_dir)
    summary = compute_summary(file_results)

    if json_mode:
        output = {"files": file_results, "summary": summary}
        print(json.dumps(output, indent=2))
    else:
        print(format_human(file_results, summary))

    exit_code = 0

    if fail_on_theater and summary.get("theater_risk", 0) > 0:
        theater_methods = []
        for filepath, file_data in file_results.items():
            for class_name, methods in file_data["classes"].items():
                for method_name, classification in methods.items():
                    if classification == "theater_risk":
                        theater_methods.append(f"  {filepath}::{class_name}::{method_name}")
        print(f"FAIL: {len(theater_methods)} theater_risk method(s) found:", file=sys.stderr)
        for m in theater_methods:
            print(m, file=sys.stderr)
        exit_code = 1

    if fail_on_mismatch:
        mismatches = find_proof_class_mismatches(file_results)
        if mismatches:
            print(
                f"FAIL: {len(mismatches)} proof-class mismatch(es) found "
                f"(class name implies runtime proof but all methods are source_lock):",
                file=sys.stderr,
            )
            for m in mismatches:
                print(m, file=sys.stderr)
            exit_code = 1

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
