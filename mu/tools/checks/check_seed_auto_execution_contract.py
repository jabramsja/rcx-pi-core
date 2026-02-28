#!/usr/bin/env python3
"""Seed-Auto Execution Contract Checker (A19).

Statically scans the full runtime surface for program-specific seed branching.
Violations: conditional branches on seed-filename string literals.
Genuine generic uses (loader registration, seed maps) are allowlisted.

Fails (exit 1) if:
  - Any seed-filename literal appears in a conditional branch outside the allowlist
  - Allowlist schema is invalid
  - Zero files scanned (path failure)
  - Scan surface is below minimum line count (truncation guard)

Usage:
    python3 tools/checks/check_seed_auto_execution_contract.py
    python3 tools/checks/check_seed_auto_execution_contract.py --json
    python3 tools/checks/check_seed_auto_execution_contract.py --allowlist path/to/allowlist.json
    python3 tools/checks/check_seed_auto_execution_contract.py --update-allowlist
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    """Find repo root by searching upward for pyproject.toml."""
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "pyproject.toml").is_file():
            return d
        d = d.parent
    raise RuntimeError("Cannot find repo root (no pyproject.toml)")


REPO_ROOT = _find_repo_root()
DEFAULT_ALLOWLIST = REPO_ROOT / "tools" / "checks" / "seed_auto_allowlist.json"

# Scan surface: full runtime (Python + JS)
PY_RUNTIME_DIR = REPO_ROOT / "rcx_pi" / "selfhost"
JS_RUNTIME_DIR = REPO_ROOT / "mu" / "host" / "js"

# Anchored seed filename pattern — fullmatch only, no substring matching.
# Matches: kernel.v1.json, match.v2.json, recurrence.v1.json
# Rejects: foo.json (no version), something.v1.jsonl (wrong ext)
SEED_FILENAME_ANCHORED = re.compile(r"^[A-Za-z0-9_]+\.v[0-9]+\.json$")

# Quoted seed filename for JS regex scanner (legacy line-based).
SEED_FILENAME_RE = re.compile(r"""["'](\w+\.v\d+\.json)["']""")

# JS conditional context (line-based, for JS scanner only).
CONDITIONAL_RE = re.compile(
    r"""^\s*(?:if|elif|else\s+if)\s+.*(?:==|!=|===|!==)""",
    re.IGNORECASE,
)

# Minimum scan thresholds (fail-closed on truncated/missing surface)
MIN_PY_FILES = 5
MIN_JS_FILES = 5
MIN_TOTAL_LINES = 1000

REQUIRED_ENTRY_FIELDS = frozenset({
    "file", "line_pattern", "seed_filename",
    "classification", "rationale", "owner", "expires_on",
})
VALID_CLASSIFICATIONS = frozenset({"generic_loader", "seed_registry", "generic_dispatch"})


# ---------------------------------------------------------------------------
# Allowlist loading + validation
# ---------------------------------------------------------------------------

def validate_allowlist(data: object) -> list[str]:
    """Validate allowlist schema strictly. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"allowlist must be a dict, got {type(data).__name__}"]
    if data.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, got {data.get('schema_version')}")
    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append(f"'entries' must be a list, got {type(entries).__name__}")
        return errors

    seen = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry[{i}] must be a dict")
            continue
        missing = REQUIRED_ENTRY_FIELDS - set(entry.keys())
        if missing:
            errors.append(f"entry[{i}] missing fields: {sorted(missing)}")
            continue
        classification = entry.get("classification")
        if classification not in VALID_CLASSIFICATIONS:
            errors.append(
                f"entry[{i}] classification must be one of "
                f"{sorted(VALID_CLASSIFICATIONS)}, got '{classification}'"
            )
        # Validate line_pattern is a valid regex (fail-closed on bad regex)
        line_pat = entry.get("line_pattern", "")
        try:
            re.compile(line_pat)
        except re.error as e:
            errors.append(
                f"entry[{i}] invalid line_pattern regex '{line_pat}': {e}"
            )
        key = (entry["file"], entry["line_pattern"], entry["seed_filename"])
        if key in seen:
            errors.append(f"entry[{i}] duplicate: {key}")
        seen.add(key)
        # Path safety
        fpath = entry["file"]
        if ".." in Path(fpath).parts:
            errors.append(f"entry[{i}] path traversal in file: {fpath}")
    return errors


def load_allowlist(path: Path) -> dict:
    """Load and validate allowlist. Exits on schema errors."""
    if not path.is_file():
        print(f"ERROR: Allowlist not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text())
    errors = validate_allowlist(data)
    if errors:
        print("ERROR: Allowlist schema validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    return data


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _collect_files() -> tuple[list[Path], list[Path]]:
    """Collect Python and JS runtime files."""
    py_files = sorted(PY_RUNTIME_DIR.glob("*.py")) if PY_RUNTIME_DIR.is_dir() else []
    js_files = sorted(JS_RUNTIME_DIR.rglob("*.js")) if JS_RUNTIME_DIR.is_dir() else []
    # Exclude JS test files
    js_files = [f for f in js_files if "/tests/" not in str(f)]
    return py_files, js_files


# ---------------------------------------------------------------------------
# Allowlist suppression (triple-match: file + seed_filename + line_pattern)
# ---------------------------------------------------------------------------

def _is_allowlisted(
    rel_path: str, seed_name: str, context: str,
    al_lookup: dict[tuple[str, str], list[dict]],
) -> bool:
    """Check if a violation is suppressed by the allowlist.

    Requires ALL of: file match, seed_filename match, AND line_pattern
    regex matches the violation context. A broad (file, seed) entry
    cannot suppress unrelated lines.
    """
    entries = al_lookup.get((rel_path, seed_name), [])
    for entry in entries:
        if re.search(entry["line_pattern"], context):
            return True
    return False


# ---------------------------------------------------------------------------
# Python AST-based scanner
# ---------------------------------------------------------------------------

def _is_seed_filename(s: object) -> bool:
    """Check if a value is a seed filename using anchored fullmatch."""
    return isinstance(s, str) and bool(SEED_FILENAME_ANCHORED.fullmatch(s))


def _collect_scope_aliases(stmts: list) -> dict[str, str]:
    """Collect seed-filename aliases from direct assignments in a scope body.

    Only inspects direct children of the statement list (not nested inside
    if/for/etc). This is conservative — avoids conditional assignments.
    """
    aliases: dict[str, str] = {}
    for stmt in stmts:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Constant):
                if _is_seed_filename(stmt.value.value):
                    aliases[target.id] = stmt.value.value
    return aliases


def _check_if_test_for_seeds(
    test: ast.expr, aliases: dict[str, str],
) -> list[tuple[str, int]]:
    """Check an If test expression for seed-filename comparisons.

    Catches: direct literals, alias references, membership in set/list/tuple.
    Returns list of (seed_filename, lineno) hits.
    """
    hits: list[tuple[str, int]] = []
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        all_operands = [node.left] + list(node.comparators)
        for op in all_operands:
            lineno = getattr(op, "lineno", getattr(node, "lineno", 0))
            if isinstance(op, ast.Constant) and _is_seed_filename(op.value):
                hits.append((op.value, lineno))
            elif isinstance(op, ast.Name) and op.id in aliases:
                hits.append((aliases[op.id], lineno))
            elif isinstance(op, (ast.Set, ast.List, ast.Tuple)):
                for elt in op.elts:
                    elt_lineno = getattr(elt, "lineno", lineno)
                    if isinstance(elt, ast.Constant) and _is_seed_filename(elt.value):
                        hits.append((elt.value, elt_lineno))
                    elif isinstance(elt, ast.Name) and elt.id in aliases:
                        hits.append((aliases[elt.id], elt_lineno))
    return hits


def _walk_scope(
    stmts: list,
    scope_aliases: dict[str, str],
    rel_path: str,
    al_lookup: dict,
    source_lines: list[str],
    violations: list[dict],
) -> None:
    """Walk statements in a scope, checking If tests.

    Scope-aware: each FunctionDef/AsyncFunctionDef/ClassDef starts a new
    scope. Child scopes inherit parent aliases (visible via closure) but
    child-local assignments shadow parent names. No cross-file propagation.
    """
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            hits = _check_if_test_for_seeds(stmt.test, scope_aliases)
            for seed_name, lineno in hits:
                ctx = source_lines[lineno - 1].strip()[:120] if 0 < lineno <= len(source_lines) else ""
                if not _is_allowlisted(rel_path, seed_name, ctx, al_lookup):
                    violations.append({
                        "file": rel_path, "line": lineno,
                        "seed_filename": seed_name, "context": ctx,
                    })
            # Recurse into body/orelse (same scope — not a new function)
            _walk_scope(stmt.body, scope_aliases, rel_path, al_lookup, source_lines, violations)
            _walk_scope(stmt.orelse, scope_aliases, rel_path, al_lookup, source_lines, violations)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Child scope inherits parent aliases; local assignments shadow
            child_local = _collect_scope_aliases(stmt.body)
            effective = {**scope_aliases, **child_local}
            _walk_scope(stmt.body, effective, rel_path, al_lookup, source_lines, violations)
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            _walk_scope(stmt.body, scope_aliases, rel_path, al_lookup, source_lines, violations)
            _walk_scope(stmt.orelse, scope_aliases, rel_path, al_lookup, source_lines, violations)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            _walk_scope(stmt.body, scope_aliases, rel_path, al_lookup, source_lines, violations)
        elif isinstance(stmt, ast.Try):
            _walk_scope(stmt.body, scope_aliases, rel_path, al_lookup, source_lines, violations)
            for handler in stmt.handlers:
                _walk_scope(handler.body, scope_aliases, rel_path, al_lookup, source_lines, violations)
            _walk_scope(stmt.orelse, scope_aliases, rel_path, al_lookup, source_lines, violations)
            _walk_scope(stmt.finalbody, scope_aliases, rel_path, al_lookup, source_lines, violations)


def _scan_python_file(
    fpath: Path, rel_path: str, al_lookup: dict,
) -> tuple[list[dict], int]:
    """AST-based scan of a Python file.

    Fail-closed: parse errors become violations (not silent skips).
    Returns (violations, line_count).
    """
    try:
        source = fpath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return ([{
            "file": rel_path, "line": 0, "seed_filename": "",
            "context": f"Parse error: cannot read file: {e}",
        }], 0)

    source_lines = source.splitlines()
    line_count = len(source_lines)

    try:
        tree = ast.parse(source, filename=str(fpath))
    except SyntaxError as e:
        return ([{
            "file": rel_path, "line": e.lineno or 0, "seed_filename": "",
            "context": f"Parse error: SyntaxError: {e.msg}",
        }], line_count)

    module_aliases = _collect_scope_aliases(tree.body)
    violations: list[dict] = []
    _walk_scope(tree.body, module_aliases, rel_path, al_lookup, source_lines, violations)
    return violations, line_count


# ---------------------------------------------------------------------------
# JavaScript regex-based scanner (unchanged logic)
# ---------------------------------------------------------------------------

def _scan_js_file(
    fpath: Path, rel_path: str, al_lookup: dict,
) -> tuple[list[dict], int]:
    """Regex-based scan of a JS file. Returns (violations, line_count)."""
    try:
        lines = fpath.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ([], 0)

    violations: list[dict] = []
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        matches = SEED_FILENAME_RE.findall(line)
        if not matches:
            continue
        if not CONDITIONAL_RE.search(line):
            continue
        for seed_name in matches:
            ctx = stripped[:120]
            if _is_allowlisted(rel_path, seed_name, ctx, al_lookup):
                continue
            violations.append({
                "file": rel_path, "line": lineno,
                "seed_filename": seed_name, "context": ctx,
            })
    return violations, len(lines)


# ---------------------------------------------------------------------------
# Unified scanner
# ---------------------------------------------------------------------------

def scan_for_violations(
    py_files: list[Path],
    js_files: list[Path],
    allowlist: dict,
) -> tuple[list[dict], int]:
    """Scan runtime files for conditional seed-filename branching.

    Python: AST-based (catches multiline, indirect alias, membership).
    JavaScript: regex-based (line-level, unchanged).
    Fail-closed: parse errors on Python files become violations.

    Returns (violations, total_lines_scanned).
    Violations are deduped and sorted by (file, line, seed_filename).
    """
    al_lookup: dict[tuple[str, str], list[dict]] = {}
    for entry in allowlist.get("entries", []):
        key = (entry["file"], entry["seed_filename"])
        al_lookup.setdefault(key, []).append(entry)

    violations: list[dict] = []
    total_lines = 0

    for fpath in py_files:
        try:
            rel_path = str(fpath.relative_to(REPO_ROOT))
        except ValueError:
            rel_path = str(fpath)
        file_violations, line_count = _scan_python_file(fpath, rel_path, al_lookup)
        violations.extend(file_violations)
        total_lines += line_count

    for fpath in js_files:
        try:
            rel_path = str(fpath.relative_to(REPO_ROOT))
        except ValueError:
            rel_path = str(fpath)
        file_violations, line_count = _scan_js_file(fpath, rel_path, al_lookup)
        violations.extend(file_violations)
        total_lines += line_count

    # Dedup by (file, line, seed_filename) and stable-sort
    seen: set[tuple[str, int, str]] = set()
    deduped: list[dict] = []
    for v in violations:
        key = (v["file"], v["line"], v["seed_filename"])
        if key not in seen:
            seen.add(key)
            deduped.append(v)
    deduped.sort(key=lambda v: (v["file"], v["line"], v["seed_filename"]))

    return deduped, total_lines


# ---------------------------------------------------------------------------
# Ratchet logic
# ---------------------------------------------------------------------------

def check_contract(
    py_files: list[Path],
    js_files: list[Path],
    allowlist: dict,
) -> dict:
    """Run the seed-auto execution contract check.

    Returns dict with: violations, py_files, js_files, total_lines, passed.
    """
    violations, total_lines = scan_for_violations(py_files, js_files, allowlist)
    return {
        "violations": sorted(violations, key=lambda v: (v["file"], v["line"])),
        "py_file_count": len(py_files),
        "js_file_count": len(js_files),
        "total_lines_scanned": total_lines,
        "passed": len(violations) == 0,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_human(result: dict) -> str:
    """Format result for human output."""
    lines = []
    lines.append(f"Scanned: {result['py_file_count']} Python + {result['js_file_count']} JS files "
                 f"({result['total_lines_scanned']} lines)")
    if result["passed"]:
        lines.append("PASS: No program-specific seed branching detected.")
    else:
        lines.append(f"FAIL: {len(result['violations'])} seed-branching violation(s) found:")
        for v in result["violations"]:
            lines.append(f"  {v['file']}:{v['line']} — {v['seed_filename']}")
            lines.append(f"    {v['context']}")
    return "\n".join(lines)


def format_json(result: dict) -> str:
    """Format result as JSON."""
    return json.dumps(result, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Update mode
# ---------------------------------------------------------------------------

def update_allowlist(violations: list[dict], allowlist: dict, output_path: Path) -> None:
    """Normalize and write allowlist (does NOT auto-add new violations)."""
    entries = allowlist.get("entries", [])
    entries.sort(key=lambda e: (e["file"], e["seed_filename"]))
    out = {
        "schema_version": 1,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total_entries": len(entries),
        "entries": entries,
    }
    output_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"Allowlist written to {output_path} ({len(entries)} entries)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed-auto execution contract checker")
    parser.add_argument("--json", action="store_true", help="JSON output mode")
    parser.add_argument("--allowlist", type=str, default=None, help="Custom allowlist path")
    parser.add_argument("--update-allowlist", action="store_true", help="Normalize allowlist")
    args = parser.parse_args()

    # Block --update-allowlist in CI
    if args.update_allowlist and os.environ.get("RCX_CI") == "1":
        print("ERROR: --update-allowlist is forbidden in CI", file=sys.stderr)
        sys.exit(1)

    al_path = Path(args.allowlist) if args.allowlist else DEFAULT_ALLOWLIST
    allowlist = load_allowlist(al_path)

    # Collect files
    py_files, js_files = _collect_files()

    # Zero-scan guard
    if len(py_files) < MIN_PY_FILES:
        print(
            f"ERROR: zero-scan guard: found {len(py_files)} Python runtime files "
            f"(expected >= {MIN_PY_FILES}). Path failure?",
            file=sys.stderr,
        )
        sys.exit(1)
    if len(js_files) < MIN_JS_FILES:
        print(
            f"ERROR: zero-scan guard: found {len(js_files)} JS runtime files "
            f"(expected >= {MIN_JS_FILES}). Path failure?",
            file=sys.stderr,
        )
        sys.exit(1)

    result = check_contract(py_files, js_files, allowlist)

    # Minimum line count guard
    if result["total_lines_scanned"] < MIN_TOTAL_LINES:
        print(
            f"ERROR: minimum scan guard: scanned {result['total_lines_scanned']} lines "
            f"(expected >= {MIN_TOTAL_LINES}). Truncation?",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.update_allowlist:
        update_allowlist(result["violations"], allowlist, al_path)
        return

    if args.json:
        print(format_json(result))
    else:
        print(format_human(result))

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
