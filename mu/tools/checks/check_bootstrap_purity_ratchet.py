#!/usr/bin/env python3
"""Bootstrap purity ratchet: prevent new host capabilities from entering the kernel.

THE HOST MUST BE A DUMB BOOTSTRAP. Nothing smart gets added. Ever.
See mu/docs/core/Why_RCX_PI_VM_EXISTS.md for why.

This check enforces two ratchets:

1. CONTRABAND_OK count — baselines how many CONTRABAND_OK bypasses exist in
   kernel files. If someone adds a new bypass (i.e., rationalizes a new host
   capability), this check FAILS. The count can only go DOWN (debt reduction).

2. Stdlib module set — baselines which host stdlib modules are imported in
   kernel files. If someone adds a new import (e.g., `import os`, `import socket`),
   this check FAILS. The set can only SHRINK (debt reduction).

Both ratchets are fail-closed: if the baseline can't be loaded, FAIL.
If the scan produces unexpected results, FAIL.

Integration:
  - Pre-commit hook (staged files)
  - audit_fast.sh (full scan)
  - CI green gate

Usage:
  python3 tools/checks/check_bootstrap_purity_ratchet.py          # Full scan (gate check)
  python3 tools/checks/check_bootstrap_purity_ratchet.py --audit   # Debt audit (list every host capability with severity)
  python3 tools/checks/check_bootstrap_purity_ratchet.py --update  # Regenerate baseline (debt reduction only)
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

# Resolve repo root
REPO_ROOT = Path(
    subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
)

BASELINE_PATH = REPO_ROOT / "tools" / "checks" / "bootstrap_purity_baseline.json"

# Kernel directories (where host capabilities are tracked debt)
PY_KERNEL_DIR = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"
JS_KERNEL_DIR = REPO_ROOT / "mu" / "host" / "js"

# Files/dirs to exclude from JS scan (tests, not kernel)
JS_EXCLUDE = {"tests", "node_modules"}

# Python stdlib top-level modules that constitute "host capabilities"
# We track ANY stdlib import — even "harmless" ones like typing.
# The principle: if it's not a relative import, it's a host dependency.
# __future__ is excluded (it's a language directive, not a capability).
PYTHON_INTERNAL_PREFIXES = (".", "__future__")

# Project's own package — not a host capability
PYTHON_OWN_PACKAGES = {"rcx_pi"}

# JS: require() calls that are local modules (start with ./ or ../)
JS_LOCAL_RE = re.compile(r"""require\s*\(\s*['"]\.{1,2}/""")

# CONTRABAND_OK pattern
CONTRABAND_OK_RE = re.compile(r"CONTRABAND_OK")


def load_baseline() -> dict:
    """Load baseline, fail-closed if missing or malformed."""
    if not BASELINE_PATH.is_file():
        print(f"FAIL: Baseline not found: {BASELINE_PATH}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(BASELINE_PATH.read_text())
    except Exception as exc:
        print(f"FAIL: Cannot parse baseline: {exc}", file=sys.stderr)
        sys.exit(1)
    if data.get("schema_version") != 1:
        print(f"FAIL: Unexpected schema_version: {data.get('schema_version')}", file=sys.stderr)
        sys.exit(1)
    return data


def scan_contraband_ok_python() -> int:
    """Count CONTRABAND_OK markers in Python kernel files."""
    count = 0
    for pyfile in PY_KERNEL_DIR.rglob("*.py"):
        for line in pyfile.read_text(encoding="utf-8").splitlines():
            if CONTRABAND_OK_RE.search(line):
                count += 1
    return count


def scan_contraband_ok_javascript() -> int:
    """Count CONTRABAND_OK markers in JavaScript kernel files."""
    count = 0
    for jsfile in JS_KERNEL_DIR.rglob("*.js"):
        # Skip excluded dirs
        rel = jsfile.relative_to(JS_KERNEL_DIR)
        if any(part in JS_EXCLUDE for part in rel.parts):
            continue
        for line in jsfile.read_text(encoding="utf-8").splitlines():
            if CONTRABAND_OK_RE.search(line):
                count += 1
    return count


def scan_stdlib_imports_python() -> set[str]:
    """Extract unique stdlib module names from Python kernel files via AST."""
    modules: set[str] = set()
    for pyfile in PY_KERNEL_DIR.rglob("*.py"):
        try:
            tree = ast.parse(pyfile.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in PYTHON_OWN_PACKAGES:
                        continue
                    if not any(alias.name.startswith(p) for p in PYTHON_INTERNAL_PREFIXES):
                        modules.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module and not any(
                    node.module.startswith(p) for p in PYTHON_INTERNAL_PREFIXES
                ):
                    if node.level == 0:  # absolute import only
                        top = node.module.split(".")[0]
                        if top not in PYTHON_OWN_PACKAGES:
                            modules.add(top)
    return modules


def scan_stdlib_imports_javascript() -> set[str]:
    """Extract unique Node.js stdlib module names from JS kernel files."""
    modules: set[str] = set()
    require_re = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")
    for jsfile in JS_KERNEL_DIR.rglob("*.js"):
        rel = jsfile.relative_to(JS_KERNEL_DIR)
        if any(part in JS_EXCLUDE for part in rel.parts):
            continue
        for line in jsfile.read_text(encoding="utf-8").splitlines():
            for m in require_re.finditer(line):
                mod = m.group(1)
                # Skip local requires (./foo, ../foo)
                if not mod.startswith("."):
                    modules.add(mod)
    return modules


def check_ratchet(baseline: dict) -> list[str]:
    """Run all ratchet checks. Returns list of violation strings (empty = pass)."""
    errors: list[str] = []

    # --- CONTRABAND_OK count ratchet ---
    bl_py = baseline["contraband_ok_count"]["python_kernel"]
    bl_js = baseline["contraband_ok_count"]["javascript_kernel"]
    bl_total = baseline["contraband_ok_count"]["total"]

    actual_py = scan_contraband_ok_python()
    actual_js = scan_contraband_ok_javascript()
    actual_total = actual_py + actual_js

    if actual_py > bl_py:
        errors.append(
            f"CONTRABAND_OK count INCREASED in Python kernel: "
            f"{actual_py} > baseline {bl_py}. "
            f"NEW HOST CAPABILITIES ARE FORBIDDEN. "
            f"The host is a DUMB bootstrap. Remove the new CONTRABAND_OK marker."
        )
    if actual_js > bl_js:
        errors.append(
            f"CONTRABAND_OK count INCREASED in JavaScript kernel: "
            f"{actual_js} > baseline {bl_js}. "
            f"NEW HOST CAPABILITIES ARE FORBIDDEN. "
            f"The host is a DUMB bootstrap. Remove the new CONTRABAND_OK marker."
        )

    # --- Stdlib module set ratchet ---
    bl_py_mods = set(baseline["stdlib_modules"]["python_kernel"])
    bl_js_mods = set(baseline["stdlib_modules"]["javascript_kernel"])

    actual_py_mods = scan_stdlib_imports_python()
    actual_js_mods = scan_stdlib_imports_javascript()

    new_py = actual_py_mods - bl_py_mods
    new_js = actual_js_mods - bl_js_mods

    if new_py:
        errors.append(
            f"NEW stdlib imports in Python kernel: {sorted(new_py)}. "
            f"NEW HOST CAPABILITIES ARE FORBIDDEN. "
            f"The host is a DUMB bootstrap — see mu/docs/core/Why_RCX_PI_VM_EXISTS.md. "
            f"Remove these imports or get FOUNDER_OVERRIDE."
        )
    if new_js:
        errors.append(
            f"NEW stdlib/Node.js imports in JavaScript kernel: {sorted(new_js)}. "
            f"NEW HOST CAPABILITIES ARE FORBIDDEN. "
            f"The host is a DUMB bootstrap — see mu/docs/core/Why_RCX_PI_VM_EXISTS.md. "
            f"Remove these imports or get FOUNDER_OVERRIDE."
        )

    # --- Print summary ---
    print("=== Bootstrap Purity Ratchet ===")
    print(f"  CONTRABAND_OK: Python {actual_py}/{bl_py}, JS {actual_js}/{bl_js}, "
          f"Total {actual_total}/{bl_total}")
    print(f"  Stdlib modules: Python {sorted(actual_py_mods)}")
    print(f"  Stdlib modules: JS {sorted(actual_js_mods)}")

    if actual_py < bl_py or actual_js < bl_js:
        print(f"  NOTE: CONTRABAND_OK count decreased — update baseline with --update")
    if actual_py_mods < bl_py_mods or actual_js_mods < bl_js_mods:
        removed_py = bl_py_mods - actual_py_mods
        removed_js = bl_js_mods - actual_js_mods
        if removed_py:
            print(f"  NOTE: Python stdlib imports removed: {sorted(removed_py)} — update baseline with --update")
        if removed_js:
            print(f"  NOTE: JS stdlib imports removed: {sorted(removed_js)} — update baseline with --update")

    return errors


def update_baseline():
    """Regenerate baseline from current state (debt reduction only)."""
    old = load_baseline()

    actual_py = scan_contraband_ok_python()
    actual_js = scan_contraband_ok_javascript()
    actual_py_mods = sorted(scan_stdlib_imports_python())
    actual_js_mods = sorted(scan_stdlib_imports_javascript())

    old_total = old["contraband_ok_count"]["total"]
    new_total = actual_py + actual_js

    if new_total > old_total:
        print(f"FAIL: Cannot update baseline — CONTRABAND_OK count increased "
              f"({new_total} > {old_total}). Fix the regression first.", file=sys.stderr)
        sys.exit(1)

    old_py_mods = set(old["stdlib_modules"]["python_kernel"])
    old_js_mods = set(old["stdlib_modules"]["javascript_kernel"])
    new_py_set = set(actual_py_mods)
    new_js_set = set(actual_js_mods)

    if new_py_set - old_py_mods or new_js_set - old_js_mods:
        additions = (new_py_set - old_py_mods) | (new_js_set - old_js_mods)
        print(f"FAIL: Cannot update baseline — new stdlib imports detected: "
              f"{sorted(additions)}. Fix the regression first.", file=sys.stderr)
        sys.exit(1)

    old["contraband_ok_count"]["python_kernel"] = actual_py
    old["contraband_ok_count"]["javascript_kernel"] = actual_js
    old["contraband_ok_count"]["total"] = new_total
    old["stdlib_modules"]["python_kernel"] = actual_py_mods
    old["stdlib_modules"]["javascript_kernel"] = actual_js_mods

    # Update notes: remove notes for removed modules
    removed = (old_py_mods - new_py_set) | (old_js_mods - new_js_set)
    for mod in removed:
        old.get("notes", {}).pop(mod, None)

    BASELINE_PATH.write_text(json.dumps(old, indent=2, sort_keys=False) + "\n")
    print(f"Baseline updated: {BASELINE_PATH}")
    print(f"  CONTRABAND_OK: {new_total} (was {old_total})")
    print(f"  Python stdlib: {actual_py_mods}")
    print(f"  JS stdlib: {actual_js_mods}")


# ---------------------------------------------------------------------------
# Debt audit mode: list every host capability with file, line, severity,
# classification, and elimination status.
# ---------------------------------------------------------------------------

# Severity levels for host capabilities
SEVERITY_HIGH = "HIGH"      # Active host semantic leak (non-determinism, env access, wall-clock)
SEVERITY_MEDIUM = "MEDIUM"  # Host capability that could be structural but isn't yet
SEVERITY_LOW = "LOW"        # Minimal footprint or type-hint-only (no runtime host effect)
SEVERITY_OK = "OK"          # Marker exists for scanner reasons but code is actually structural

# Classification of host capabilities
CLASS_LEAK = "HOST_LEAK"              # Active semantic leak (changes behavior based on host state)
CLASS_BOOTSTRAP = "BOOTSTRAP_NECESSITY"  # Required to load/parse seeds (fs, json, path)
CLASS_DEBT = "TRACKED_DEBT"           # Known debt, tracked by @host_* markers
CLASS_META = "META_TRACKING"          # Host capability used to track other host capabilities
CLASS_TYPEHINT = "TYPE_HINT_ONLY"     # No runtime effect (typing, annotations)
CLASS_FALSE_POS = "FALSE_POSITIVE"    # CONTRABAND_OK protects comment text, not actual code


def scan_contraband_ok_details_python() -> list[dict]:
    """Return detailed info for each CONTRABAND_OK in Python kernel."""
    results = []
    for pyfile in PY_KERNEL_DIR.rglob("*.py"):
        rel = pyfile.relative_to(REPO_ROOT)
        text = pyfile.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if CONTRABAND_OK_RE.search(line):
                reason = ""
                m = re.search(r"CONTRABAND_OK:\s*(.+?)(?:\s*$)", line)
                if m:
                    reason = m.group(1).strip()
                results.append({
                    "file": str(rel),
                    "line": i,
                    "code": line.strip(),
                    "reason": reason,
                    "substrate": "python",
                })
    return results


def scan_contraband_ok_details_javascript() -> list[dict]:
    """Return detailed info for each CONTRABAND_OK in JS kernel."""
    results = []
    for jsfile in JS_KERNEL_DIR.rglob("*.js"):
        rel = jsfile.relative_to(REPO_ROOT)
        if any(part in JS_EXCLUDE for part in rel.relative_to(Path("mu/host/js")).parts):
            continue
        text = jsfile.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if CONTRABAND_OK_RE.search(line):
                reason = ""
                m = re.search(r"CONTRABAND_OK:\s*(.+?)(?:\s*$)", line)
                if m:
                    reason = m.group(1).strip()
                results.append({
                    "file": str(rel),
                    "line": i,
                    "code": line.strip(),
                    "reason": reason,
                    "substrate": "javascript",
                })
    return results


def scan_stdlib_import_details_python() -> list[dict]:
    """Return detailed info for each stdlib import in Python kernel."""
    results = []
    for pyfile in PY_KERNEL_DIR.rglob("*.py"):
        rel = pyfile.relative_to(REPO_ROOT)
        text = pyfile.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in PYTHON_OWN_PACKAGES:
                        continue
                    if any(alias.name.startswith(p) for p in PYTHON_INTERNAL_PREFIXES):
                        continue
                    results.append({
                        "file": str(rel),
                        "line": node.lineno,
                        "module": alias.name,
                        "top_module": top,
                        "substrate": "python",
                    })
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split(".")[0]
                    if top in PYTHON_OWN_PACKAGES:
                        continue
                    if any(node.module.startswith(p) for p in PYTHON_INTERNAL_PREFIXES):
                        continue
                    names = [a.name for a in node.names] if node.names else []
                    results.append({
                        "file": str(rel),
                        "line": node.lineno,
                        "module": node.module,
                        "top_module": top,
                        "names": names,
                        "substrate": "python",
                    })
    return results


def scan_stdlib_import_details_javascript() -> list[dict]:
    """Return detailed info for each Node.js stdlib import in JS kernel."""
    results = []
    require_re = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")
    for jsfile in JS_KERNEL_DIR.rglob("*.js"):
        rel = jsfile.relative_to(REPO_ROOT)
        if any(part in JS_EXCLUDE for part in rel.relative_to(Path("mu/host/js")).parts):
            continue
        text = jsfile.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for m in require_re.finditer(line):
                mod = m.group(1)
                if not mod.startswith("."):
                    results.append({
                        "file": str(rel),
                        "line": i,
                        "module": mod,
                        "substrate": "javascript",
                    })
    return results


def classify_contraband_ok(entry: dict) -> tuple[str, str, str]:
    """Classify a CONTRABAND_OK entry. Returns (severity, classification, note)."""
    code = entry["code"].lower()
    reason = entry["reason"].lower()

    # import time — wall-clock host leak
    if "import time" in code:
        return SEVERITY_HIGH, CLASS_LEAK, "Wall-clock timestamps (time.strftime). Must be replaced with derived:<hash>."

    # process.env — host environment variable access
    if "process.env" in code:
        return SEVERITY_HIGH, CLASS_LEAK, "Kernel behavior depends on host environment variable. Must be eliminated."

    # setattr for debt tracking decorators
    if "setattr" in code and "host_" in code:
        return SEVERITY_LOW, CLASS_META, "Host setattr used to attach debt-tracking metadata to functions."

    # import threading — host concurrency
    if "import threading" in code or "threading" in reason:
        return SEVERITY_MEDIUM, CLASS_DEBT, "Thread-local storage for step budget. Accepted bootstrap debt."

    # derived: hash — actually structural, marker protects comment text
    if "derived:" in code and ("deterministic" in reason or "replaces" in reason):
        return SEVERITY_OK, CLASS_FALSE_POS, "Code is deterministic (derived:<hash>). CONTRABAND_OK protects comment mentioning old pattern."

    # coverage infra
    if "coverage" in reason or "infra" in reason:
        return SEVERITY_LOW, CLASS_META, "Infrastructure/coverage tracking."

    # Default
    return SEVERITY_MEDIUM, CLASS_DEBT, "Unclassified CONTRABAND_OK — review needed."


def classify_stdlib_import(entry: dict) -> tuple[str, str, str]:
    """Classify a stdlib import. Returns (severity, classification, note)."""
    mod = entry.get("top_module") or entry.get("module", "")

    if mod == "time":
        return SEVERITY_HIGH, CLASS_LEAK, "Wall-clock access. Must be eliminated (collected_at fix)."
    if mod == "threading":
        return SEVERITY_MEDIUM, CLASS_DEBT, "Thread-local storage for step budget. Accepted bootstrap debt."
    if mod == "math":
        return SEVERITY_MEDIUM, CLASS_DEBT, "Used for math.isnan/isinf on max_steps. Could use structural bounds."
    if mod in ("json", "hashlib", "pathlib"):
        return SEVERITY_LOW, CLASS_BOOTSTRAP, f"Bootstrap necessity: {'seed JSON parsing' if mod == 'json' else 'content-addressing' if mod == 'hashlib' else 'seed file paths'}."
    if mod == "collections":
        names = entry.get("names", [])
        if "OrderedDict" in names:
            return SEVERITY_LOW, CLASS_DEBT, "OrderedDict for LRU hash cache. Host data structure."
        if "Callable" in names:
            return SEVERITY_LOW, CLASS_TYPEHINT, "Type hint only (no runtime host effect)."
        return SEVERITY_LOW, CLASS_DEBT, "Host collections module."
    if mod == "typing":
        return SEVERITY_LOW, CLASS_TYPEHINT, "Type hints only (no runtime host effect)."
    if mod in ("fs", "path"):
        return SEVERITY_LOW, CLASS_BOOTSTRAP, f"Bootstrap necessity: {'read-only seed loading' if mod == 'fs' else 'seed file path resolution'}."
    if mod == "crypto":
        return SEVERITY_LOW, CLASS_BOOTSTRAP, "Deterministic hashing for seed integrity (NOT randomness)."

    return SEVERITY_MEDIUM, CLASS_DEBT, "Unclassified stdlib import — review needed."


def run_audit():
    """Run full debt audit — list every host capability with classification."""
    baseline = load_baseline()

    print("=" * 72)
    print("BOOTSTRAP PURITY DEBT AUDIT")
    print("The host is a DUMB bootstrap. Every item below is tracked debt.")
    print("See mu/docs/core/Why_RCX_PI_VM_EXISTS.md")
    print("=" * 72)
    print()

    # --- CONTRABAND_OK entries ---
    py_entries = scan_contraband_ok_details_python()
    js_entries = scan_contraband_ok_details_javascript()
    all_contraband = py_entries + js_entries

    high_count = 0
    medium_count = 0
    low_count = 0
    ok_count = 0

    print(f"## CONTRABAND_OK Bypasses ({len(all_contraband)} total)")
    print()
    for entry in all_contraband:
        severity, classification, note = classify_contraband_ok(entry)
        if severity == SEVERITY_HIGH:
            high_count += 1
        elif severity == SEVERITY_MEDIUM:
            medium_count += 1
        elif severity == SEVERITY_LOW:
            low_count += 1
        else:
            ok_count += 1
        marker = {"HIGH": "!!!", "MEDIUM": " ! ", "LOW": " . ", "OK": " ~ "}[severity]
        print(f"  [{marker}] {entry['file']}:{entry['line']}")
        print(f"        Severity: {severity} | Class: {classification}")
        print(f"        Code: {entry['code'][:100]}")
        print(f"        Note: {note}")
        print()

    # --- Stdlib imports ---
    py_imports = scan_stdlib_import_details_python()
    js_imports = scan_stdlib_import_details_javascript()
    all_imports = py_imports + js_imports

    # Deduplicate by (file, module) for readability
    seen = set()
    unique_imports = []
    for entry in all_imports:
        key = (entry["file"], entry.get("top_module") or entry.get("module"))
        if key not in seen:
            seen.add(key)
            unique_imports.append(entry)

    print(f"## Stdlib Imports ({len(unique_imports)} unique file-module pairs)")
    print()
    for entry in unique_imports:
        severity, classification, note = classify_stdlib_import(entry)
        if severity == SEVERITY_HIGH:
            high_count += 1
        elif severity == SEVERITY_MEDIUM:
            medium_count += 1
        elif severity == SEVERITY_LOW:
            low_count += 1
        else:
            ok_count += 1
        marker = {"HIGH": "!!!", "MEDIUM": " ! ", "LOW": " . ", "OK": " ~ "}[severity]
        mod = entry.get("top_module") or entry.get("module")
        names = entry.get("names", [])
        name_str = f" (imports: {', '.join(names)})" if names else ""
        print(f"  [{marker}] {entry['file']}:{entry['line']} — {mod}{name_str}")
        print(f"        Severity: {severity} | Class: {classification}")
        print(f"        Note: {note}")
        print()

    # --- Summary ---
    print("=" * 72)
    print("SUMMARY")
    print(f"  HIGH severity (must fix):    {high_count}")
    print(f"  MEDIUM severity (should fix): {medium_count}")
    print(f"  LOW severity (acceptable):    {low_count}")
    print(f"  OK (false positive/clean):    {ok_count}")
    print()
    total_debt = high_count + medium_count + low_count
    print(f"  Total host debt items: {total_debt}")
    print(f"  CONTRABAND_OK bypasses: {len(all_contraband)} "
          f"(baseline: {baseline['contraband_ok_count']['total']})")
    print(f"  Stdlib modules: Python {sorted(scan_stdlib_imports_python())}, "
          f"JS {sorted(scan_stdlib_imports_javascript())}")
    print()
    if high_count > 0:
        print(f"  ACTION REQUIRED: {high_count} HIGH severity items need elimination.")
    print("=" * 72)


def main():
    if "--update" in sys.argv:
        update_baseline()
        return
    if "--audit" in sys.argv:
        run_audit()
        return

    baseline = load_baseline()
    errors = check_ratchet(baseline)

    if errors:
        print()
        for e in errors:
            print(f"FAIL: {e}")
        print()
        print("The host is a DUMB bootstrap. It does not get smarter.")
        print("See mu/docs/core/Why_RCX_PI_VM_EXISTS.md")
        sys.exit(1)
    else:
        print("PASS: Bootstrap purity ratchet OK — no new host capabilities")


if __name__ == "__main__":
    main()
