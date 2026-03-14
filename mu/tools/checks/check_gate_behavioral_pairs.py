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


def _has_meaningful_assertion(node: ast.AST) -> bool:
    """Check if a function body has meaningful assertions (not vacuous)."""
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
        # subprocess.run or _run_js_expr with assertion on result
        if isinstance(child, ast.Compare):
            return True
    return False


def _has_raise_or_subprocess(node: ast.AST) -> bool:
    """Check if a function calls subprocess or raises."""
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
    return False


def classify_method(func_node: ast.FunctionDef) -> str:
    """Classify a test method AST node."""
    call_names = _extract_call_names(func_node)

    has_source = bool(call_names & SOURCE_LOCK_CALLS)
    # Also check for file reads of .py/.js (common source_lock pattern)
    source_text = ast.dump(func_node)
    if ".read_text()" in ast.unparse(func_node) or "open(" in ast.unparse(func_node):
        has_source = True

    has_behavioral = bool(call_names & BEHAVIORAL_CALLS)
    # subprocess.run and _run_js_expr are behavioral
    if _has_raise_or_subprocess(func_node):
        has_behavioral = True

    has_assertion = _has_meaningful_assertion(func_node)

    if not has_assertion and not _has_raise_or_subprocess(func_node):
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

    classes: dict[str, dict[str, str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods: dict[str, str] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("test_"):
                        methods[item.name] = classify_method(item)
            if methods:
                classes[node.name] = methods

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
