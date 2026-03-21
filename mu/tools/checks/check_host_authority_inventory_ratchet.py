#!/usr/bin/env python3
"""Host-Authority Inventory Ratchet.

Tracks two ledgers across the live runtime tree:

1. total inventory: every named host-runtime site in scope
2. authority subset: named sites that show host-authority signals

This is intentionally broader than check_host_semantics_ratchet.py:
- host_semantics_ratchet.py counts explicit @host_* marker debt
- this checker inventories full runtime surface plus the narrower authority subset

Fail-closed on:
  - malformed baseline schema
  - unreadable/parsing failures
  - zero/underscan conditions
  - any new total-inventory or authority-subset site relative to baseline

Usage:
    python3 tools/checks/check_host_authority_inventory_ratchet.py
    python3 tools/checks/check_host_authority_inventory_ratchet.py --json
    python3 tools/checks/check_host_authority_inventory_ratchet.py --baseline path/to/baseline.json
    python3 tools/checks/check_host_authority_inventory_ratchet.py --update-baseline
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
DEFAULT_BASELINE = REPO_ROOT / "tools" / "checks" / "host_authority_inventory_baseline.json"

PY_RUNTIME_DIR = REPO_ROOT / "rcx_pi" / "selfhost"
JS_RUNTIME_DIR = REPO_ROOT / "mu" / "host" / "js"

MIN_PY_FILES = 5
MIN_JS_FILES = 5
MIN_TOTAL_SITES = 100

HOT_PY_BUILTINS = frozenset({
    "all",
    "any",
    "dict",
    "enumerate",
    "hash",
    "isinstance",
    "len",
    "list",
    "max",
    "min",
    "next",
    "reversed",
    "set",
    "sorted",
    "sum",
    "tuple",
    "zip",
})
HOST_PY_CALLS = frozenset({
    "mu_hash",
    "mu_hash_cached",
    "mu_hash_control",
    "mu_hash_control_cached",
})
PY_MUTATION_METHODS = frozenset({
    "add",
    "append",
    "clear",
    "extend",
    "pop",
    "remove",
    "setdefault",
    "sort",
    "update",
})

JS_BUILTIN_PATTERNS = (
    "Array.isArray",
    "JSON.parse",
    "JSON.stringify",
    "Math.",
    "Number.isFinite",
    "Number.isInteger",
    "Object.entries",
    "Object.freeze",
    "Object.getOwnPropertyNames",
    "Object.keys",
    "muHash(",
    "muHashCached(",
    "muHashControl(",
    "Set(",
    "Map(",
)
JS_MUTATION_PATTERNS = (
    ".add(",
    ".assign(",
    ".delete(",
    ".freeze(",
    ".push(",
    ".set(",
    ".sort(",
    ".splice(",
    ".update(",
)

REQUIRED_ENTRY_FIELDS = frozenset({"file", "line", "name", "signals", "substrate"})
VALID_SUBSTRATES = frozenset({"python", "javascript"})
REQUIRED_INVENTORY_NAMES = ("total", "authority")
REQUIRED_INVENTORY_FIELDS = frozenset({"site_counts", "entries"})
REQUIRED_SITE_COUNT_FIELDS = frozenset({"python", "javascript", "total"})


@dataclass(frozen=True)
class SiteKey:
    substrate: str
    file: str
    name: str


def validate_baseline(data: object) -> list[str]:
    """Validate baseline schema strictly. Returns list of errors."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"baseline must be a dict, got {type(data).__name__}"]
    if data.get("schema_version") != 2:
        errors.append(f"schema_version must be 2, got {data.get('schema_version')}")
    inventories = data.get("inventories")
    if not isinstance(inventories, dict):
        errors.append(f"'inventories' must be a dict, got {type(inventories).__name__}")
        return errors
    for inventory_name in REQUIRED_INVENTORY_NAMES:
        block = inventories.get(inventory_name)
        if not isinstance(block, dict):
            errors.append(f"inventories.{inventory_name} must be a dict")
            continue
        missing_inventory_fields = REQUIRED_INVENTORY_FIELDS - set(block.keys())
        if missing_inventory_fields:
            errors.append(
                f"inventories.{inventory_name} missing fields: {sorted(missing_inventory_fields)}"
            )
        site_counts = block.get("site_counts")
        entries = block.get("entries")
        if not isinstance(site_counts, dict):
            errors.append(f"inventories.{inventory_name}.site_counts must be a dict")
        else:
            missing_site_count_fields = REQUIRED_SITE_COUNT_FIELDS - set(site_counts.keys())
            if missing_site_count_fields:
                errors.append(
                    f"inventories.{inventory_name}.site_counts missing fields: "
                    f"{sorted(missing_site_count_fields)}"
                )
            else:
                for count_key in REQUIRED_SITE_COUNT_FIELDS:
                    count = site_counts.get(count_key)
                    if not isinstance(count, int) or count < 0:
                        errors.append(
                            f"inventories.{inventory_name}.site_counts.{count_key} must be "
                            f"non-negative int, got {count!r}"
                        )
                if (
                    isinstance(site_counts.get("python"), int)
                    and isinstance(site_counts.get("javascript"), int)
                    and isinstance(site_counts.get("total"), int)
                    and site_counts["total"] != site_counts["python"] + site_counts["javascript"]
                ):
                    errors.append(
                        f"inventories.{inventory_name}.site_counts.total must equal python + "
                        "javascript"
                    )
        if not isinstance(entries, list):
            errors.append(
                f"inventories.{inventory_name}.entries must be a list, got {type(entries).__name__}"
            )
            continue
        seen: set[SiteKey] = set()
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"inventories.{inventory_name}.entries[{i}] must be a dict")
                continue
            missing = REQUIRED_ENTRY_FIELDS - set(entry.keys())
            if missing:
                errors.append(
                    f"inventories.{inventory_name}.entries[{i}] missing fields: {sorted(missing)}"
                )
                continue
            substrate = entry.get("substrate")
            if substrate not in VALID_SUBSTRATES:
                errors.append(
                    f"inventories.{inventory_name}.entries[{i}] substrate must be one of "
                    f"{sorted(VALID_SUBSTRATES)}, got {substrate!r}"
                )
            line = entry.get("line")
            if not isinstance(line, int) or line <= 0:
                errors.append(
                    f"inventories.{inventory_name}.entries[{i}].line must be positive int, got {line!r}"
                )
            signals = entry.get("signals")
            if not isinstance(signals, list) or not all(isinstance(s, str) for s in signals):
                errors.append(
                    f"inventories.{inventory_name}.entries[{i}].signals must be list[str], got {signals!r}"
                )
            file_path = entry.get("file", "")
            if ".." in Path(file_path).parts:
                errors.append(
                    f"inventories.{inventory_name}.entries[{i}] path traversal in file: {file_path!r}"
                )
            key = SiteKey(substrate=str(substrate), file=str(file_path), name=str(entry.get("name")))
            if key in seen:
                errors.append(
                    f"inventories.{inventory_name}.entries[{i}] duplicate entry: "
                    f"{(key.substrate, key.file, key.name)}"
                )
            seen.add(key)
        # Cross-validate site_counts against actual entries (fail-closed on stale/inflated counts)
        if isinstance(site_counts, dict) and isinstance(entries, list):
            actual_py = sum(1 for e in entries if isinstance(e, dict) and e.get("substrate") == "python")
            actual_js = sum(1 for e in entries if isinstance(e, dict) and e.get("substrate") == "javascript")
            actual_total = actual_py + actual_js
            declared_py = site_counts.get("python", -1)
            declared_js = site_counts.get("javascript", -1)
            declared_total = site_counts.get("total", -1)
            if declared_py != actual_py:
                errors.append(
                    f"inventories.{inventory_name}.site_counts.python ({declared_py}) "
                    f"does not match actual python entries ({actual_py})"
                )
            if declared_js != actual_js:
                errors.append(
                    f"inventories.{inventory_name}.site_counts.javascript ({declared_js}) "
                    f"does not match actual javascript entries ({actual_js})"
                )
            if declared_total != actual_total:
                errors.append(
                    f"inventories.{inventory_name}.site_counts.total ({declared_total}) "
                    f"does not match actual total entries ({actual_total})"
                )
    return errors


def load_baseline(path: Path) -> dict:
    """Load and validate baseline. Exits non-zero on schema errors."""
    if not path.is_file():
        print(f"ERROR: Baseline not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text())
    errors = validate_baseline(data)
    if errors:
        print("ERROR: Baseline schema validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        sys.exit(1)
    return data


def _collect_files() -> tuple[list[Path], list[Path]]:
    """Collect runtime files on both substrates."""
    py_files = sorted(PY_RUNTIME_DIR.glob("*.py")) if PY_RUNTIME_DIR.is_dir() else []
    js_files = sorted(JS_RUNTIME_DIR.rglob("*.js")) if JS_RUNTIME_DIR.is_dir() else []
    js_files = [f for f in js_files if "/tests/" not in str(f)]
    return py_files, js_files


class _PySiteVisitor(ast.NodeVisitor):
    """Collect Python named sites for total inventory and authority subset."""

    def __init__(self) -> None:
        self.stack: list[str] = []
        self.all_sites: list[dict[str, object]] = []
        self.authority_sites: list[dict[str, object]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_fn(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_fn(node)

    def _visit_fn(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        dotted = ".".join(self.stack + [node.name]) if self.stack else node.name
        signals: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.AsyncFor, ast.While, ast.comprehension)):
                signals.add("loop")
            elif isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    if func.id == node.name:
                        signals.add("recursion")
                    if func.id in HOT_PY_BUILTINS:
                        signals.add(f"builtin:{func.id}")
                    if func.id in HOST_PY_CALLS:
                        signals.add(f"authority_call:{func.id}")
                elif isinstance(func, ast.Attribute):
                    if func.attr in PY_MUTATION_METHODS:
                        signals.add(f"mutation:{func.attr}")
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, (ast.Subscript, ast.Attribute)):
                        signals.add("mutation:assignment")
            elif isinstance(child, ast.AugAssign):
                if isinstance(child.target, (ast.Subscript, ast.Attribute)):
                    signals.add("mutation:augassign")
        self.all_sites.append(
            {
                "name": dotted,
                "line": node.lineno,
                "signals": sorted(signals),
            }
        )
        if signals:
            self.authority_sites.append(
                {
                    "name": dotted,
                    "line": node.lineno,
                    "signals": sorted(signals),
                }
            )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def _scan_python_file(fpath: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """AST-based Python site scan. Fail-closed on read/parse errors."""
    try:
        rel = str(fpath.relative_to(REPO_ROOT))
    except ValueError:
        rel = str(fpath)
    try:
        source = fpath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        error_site = {
            "file": rel,
            "line": 1,
            "name": "__READ_ERROR__",
            "signals": [f"parse_error:{type(exc).__name__}"],
            "substrate": "python",
        }
        return [error_site], [error_site]
    try:
        tree = ast.parse(source, filename=str(fpath))
    except SyntaxError as exc:
        error_site = {
            "file": rel,
            "line": exc.lineno or 1,
            "name": "__PARSE_ERROR__",
            "signals": [f"parse_error:{exc.msg}"],
            "substrate": "python",
        }
        return [error_site], [error_site]
    visitor = _PySiteVisitor()
    visitor.visit(tree)
    all_sites = [
        {
            "file": rel,
            "line": int(site["line"]),
            "name": str(site["name"]),
            "signals": list(site["signals"]),
            "substrate": "python",
        }
        for site in visitor.all_sites
    ]
    authority_sites = [
        {
            "file": rel,
            "line": int(site["line"]),
            "name": str(site["name"]),
            "signals": list(site["signals"]),
            "substrate": "python",
        }
        for site in visitor.authority_sites
    ]
    return all_sites, authority_sites


def _mask_js_noncode(text: str) -> str:
    """Return a same-length string with comments/strings blanked out."""
    chars = list(text)
    i = 0
    n = len(chars)
    while i < n:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            while i < n and chars[i] != "\n":
                chars[i] = " "
                i += 1
            continue
        if ch == "/" and nxt == "*":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            while i + 1 < n and not (chars[i] == "*" and chars[i + 1] == "/"):
                if chars[i] != "\n":
                    chars[i] = " "
                i += 1
            if i + 1 < n:
                chars[i] = " "
                chars[i + 1] = " "
                i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            chars[i] = " "
            i += 1
            while i < n:
                cur = chars[i]
                if cur == "\\":
                    chars[i] = " "
                    if i + 1 < n and chars[i + 1] != "\n":
                        chars[i + 1] = " "
                    i += 2
                    continue
                if cur == quote:
                    chars[i] = " "
                    i += 1
                    break
                if cur != "\n":
                    chars[i] = " "
                i += 1
            continue
        i += 1
    return "".join(chars)


def _find_matching_brace(masked_text: str, start_brace: int) -> int | None:
    """Return index of matching closing brace in masked text."""
    depth = 0
    for idx in range(start_brace, len(masked_text)):
        ch = masked_text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx
    return None


JS_FUNCTION_PATTERNS = (
    re.compile(
        r"(?m)^\s*(?:export\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{"
    ),
    re.compile(
        r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*=>\s*\{"
    ),
    re.compile(
        r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*function(?:\s+[A-Za-z_$][A-Za-z0-9_$]*)?\s*\([^)]*\)\s*\{"
    ),
)


def _js_signals(name: str, masked_body: str) -> list[str]:
    """Infer JS host-authority signals from a masked function body."""
    signals: set[str] = set()
    if re.search(r"\b(?:for|while)\b", masked_body):
        signals.add("loop")
    if any(token in masked_body for token in (".forEach(", ".map(", ".filter(", ".reduce(")):
        signals.add("loop")
    if re.search(rf"\b{re.escape(name)}\s*\(", masked_body):
        signals.add("recursion")
    for token in JS_BUILTIN_PATTERNS:
        if token in masked_body:
            signals.add(f"builtin:{token}")
    for token in JS_MUTATION_PATTERNS:
        if token in masked_body:
            signals.add(f"mutation:{token}")
    return sorted(signals)


def _scan_js_file(fpath: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Regex/brace-based JS site scan. Fail-closed on read/parsing failures."""
    try:
        rel = str(fpath.relative_to(REPO_ROOT))
    except ValueError:
        rel = str(fpath)
    try:
        source = fpath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        error_site = {
            "file": rel,
            "line": 1,
            "name": "__READ_ERROR__",
            "signals": [f"parse_error:{type(exc).__name__}"],
            "substrate": "javascript",
        }
        return [error_site], [error_site]
    masked = _mask_js_noncode(source)
    all_sites: list[dict[str, object]] = []
    authority_sites: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for pattern in JS_FUNCTION_PATTERNS:
        for match in pattern.finditer(masked):
            name = match.group(1)
            if not name:
                continue
            brace_pos = masked.find("{", match.start())
            if brace_pos == -1:
                error_site = {
                    "file": rel,
                    "line": source.count("\n", 0, match.start()) + 1,
                    "name": f"{name}.__PARSE_ERROR__",
                    "signals": ["parse_error:missing_open_brace"],
                    "substrate": "javascript",
                }
                all_sites.append(error_site)
                authority_sites.append(error_site)
                continue
            key = (name, brace_pos)
            if key in seen:
                continue
            seen.add(key)
            end = _find_matching_brace(masked, brace_pos)
            if end is None:
                error_site = {
                    "file": rel,
                    "line": source.count("\n", 0, match.start()) + 1,
                    "name": f"{name}.__PARSE_ERROR__",
                    "signals": ["parse_error:unmatched_brace"],
                    "substrate": "javascript",
                }
                all_sites.append(error_site)
                authority_sites.append(error_site)
                continue
            body_masked = masked[brace_pos + 1:end]
            signals = _js_signals(name, body_masked)
            site = {
                "file": rel,
                "line": source.count("\n", 0, match.start()) + 1,
                "name": name,
                "signals": signals,
                "substrate": "javascript",
            }
            all_sites.append(site)
            if signals:
                authority_sites.append(site)
    all_sites.sort(key=lambda s: (str(s["file"]), int(s["line"]), str(s["name"])))
    authority_sites.sort(key=lambda s: (str(s["file"]), int(s["line"]), str(s["name"])))
    return all_sites, authority_sites


def _merge_sites(sites: list[dict[str, object]]) -> list[dict[str, object]]:
    """Deduplicate sites by substrate/file/name and merge line/signals."""
    merged: dict[SiteKey, dict[str, object]] = {}
    for site in sites:
        key = _site_key(site)
        if key not in merged:
            merged[key] = {
                "substrate": site["substrate"],
                "file": site["file"],
                "name": site["name"],
                "line": int(site["line"]),
                "signals": sorted(set(site["signals"])),
            }
            continue
        merged[key]["line"] = min(int(merged[key]["line"]), int(site["line"]))
        merged[key]["signals"] = sorted(
            set(merged[key]["signals"]) | set(site["signals"])
        )
    result = list(merged.values())
    result.sort(key=lambda s: (str(s["substrate"]), str(s["file"]), str(s["name"]), int(s["line"])))
    return result


def scan_inventories(py_files: list[Path], js_files: list[Path]) -> dict[str, list[dict[str, object]]]:
    """Scan runtime files and return total inventory plus authority subset."""
    total_sites: list[dict[str, object]] = []
    authority_sites: list[dict[str, object]] = []
    for fpath in py_files:
        py_total, py_authority = _scan_python_file(fpath)
        total_sites.extend(py_total)
        authority_sites.extend(py_authority)
    for fpath in js_files:
        js_total, js_authority = _scan_js_file(fpath)
        total_sites.extend(js_total)
        authority_sites.extend(js_authority)
    return {
        "total_sites": _merge_sites(total_sites),
        "authority_sites": _merge_sites(authority_sites),
    }


def _site_key(site: dict[str, object]) -> SiteKey:
    return SiteKey(
        substrate=str(site["substrate"]),
        file=str(site["file"]),
        name=str(site["name"]),
    )


def _compare_entry_sets(
    current_sites: list[dict[str, object]],
    baseline_entries: list[dict[str, object]],
) -> dict[str, object]:
    """Compare one inventory ledger vs its baseline entries."""
    baseline_map = {_site_key(entry): entry for entry in baseline_entries}
    current_map = {_site_key(entry): entry for entry in current_sites}

    new_keys = sorted(current_map.keys() - baseline_map.keys(), key=lambda k: (k.substrate, k.file, k.name))
    removed_keys = sorted(baseline_map.keys() - current_map.keys(), key=lambda k: (k.substrate, k.file, k.name))

    signal_changes: list[dict[str, object]] = []
    for key in sorted(current_map.keys() & baseline_map.keys(), key=lambda k: (k.substrate, k.file, k.name)):
        old_signals = list(baseline_map[key].get("signals", []))
        new_signals = list(current_map[key].get("signals", []))
        if old_signals != new_signals:
            signal_changes.append(
                {
                    "substrate": key.substrate,
                    "file": key.file,
                    "name": key.name,
                    "baseline_signals": old_signals,
                    "current_signals": new_signals,
                }
            )

    current_counts = {
        "python": sum(1 for s in current_sites if s["substrate"] == "python"),
        "javascript": sum(1 for s in current_sites if s["substrate"] == "javascript"),
    }
    current_counts["total"] = current_counts["python"] + current_counts["javascript"]

    baseline_counts = {
        "python": sum(1 for s in baseline_entries if s["substrate"] == "python"),
        "javascript": sum(1 for s in baseline_entries if s["substrate"] == "javascript"),
    }
    baseline_counts["total"] = baseline_counts["python"] + baseline_counts["javascript"]

    return {
        "current_counts": current_counts,
        "baseline_counts": baseline_counts,
        "current_sites": current_sites,
        "new_sites": [current_map[key] for key in new_keys],
        "removed_sites": [baseline_map[key] for key in removed_keys],
        "signal_changes": signal_changes,
    }


def compare_inventories(current_inventories: dict[str, list[dict[str, object]]], baseline: dict) -> dict[str, object]:
    """Compare total inventory plus authority subset vs baseline."""
    inventories = baseline.get("inventories", {})
    total_result = _compare_entry_sets(
        current_inventories["total_sites"],
        inventories.get("total", {}).get("entries", []),
    )
    authority_result = _compare_entry_sets(
        current_inventories["authority_sites"],
        inventories.get("authority", {}).get("entries", []),
    )
    return {
        "current_total_counts": total_result["current_counts"],
        "baseline_total_counts": total_result["baseline_counts"],
        "current_authority_counts": authority_result["current_counts"],
        "baseline_authority_counts": authority_result["baseline_counts"],
        "current_total_sites": total_result["current_sites"],
        "current_authority_sites": authority_result["current_sites"],
        "new_total_sites": total_result["new_sites"],
        "new_authority_sites": authority_result["new_sites"],
        "removed_total_sites": total_result["removed_sites"],
        "removed_authority_sites": authority_result["removed_sites"],
        "total_signal_changes": total_result["signal_changes"],
        "authority_signal_changes": authority_result["signal_changes"],
        "passed": len(total_result["new_sites"]) == 0 and len(authority_result["new_sites"]) == 0,
    }


def format_human(result: dict[str, object], py_files: int, js_files: int) -> str:
    """Format result for human output."""
    current_total_counts = result["current_total_counts"]
    baseline_total_counts = result["baseline_total_counts"]
    current_authority_counts = result["current_authority_counts"]
    baseline_authority_counts = result["baseline_authority_counts"]
    lines = [
        f"Scanned: {py_files} Python runtime files + {js_files} JS runtime files",
        (
            "Current total inventory: "
            f"{current_total_counts['total']} total "
            f"({current_total_counts['python']} Python + {current_total_counts['javascript']} JS)"
        ),
        (
            "Baseline total inventory: "
            f"{baseline_total_counts['total']} total "
            f"({baseline_total_counts['python']} Python + {baseline_total_counts['javascript']} JS)"
        ),
        (
            "Current authority subset: "
            f"{current_authority_counts['total']} total "
            f"({current_authority_counts['python']} Python + {current_authority_counts['javascript']} JS)"
        ),
        (
            "Baseline authority subset: "
            f"{baseline_authority_counts['total']} total "
            f"({baseline_authority_counts['python']} Python + {baseline_authority_counts['javascript']} JS)"
        ),
    ]
    if result["passed"]:
        lines.append("PASS: No new total-inventory or authority-subset sites detected.")
    else:
        if result["new_total_sites"]:
            lines.append(
                f"FAIL: {len(result['new_total_sites'])} new total-inventory site(s) not in baseline:"
            )
            for site in result["new_total_sites"][:20]:
                lines.append(
                    f"  TOTAL {site['substrate']} {site['file']}::{site['name']} (L{site['line']})"
                )
            if len(result["new_total_sites"]) > 20:
                lines.append(f"  ... and {len(result['new_total_sites']) - 20} more")
        if result["new_authority_sites"]:
            lines.append(
                f"FAIL: {len(result['new_authority_sites'])} new authority-subset site(s) not in baseline:"
            )
            for site in result["new_authority_sites"][:20]:
                lines.append(
                    f"  AUTH {site['substrate']} {site['file']}::{site['name']} "
                    f"(L{site['line']}; signals={','.join(site['signals'])})"
                )
            if len(result["new_authority_sites"]) > 20:
                lines.append(f"  ... and {len(result['new_authority_sites']) - 20} more")
    if result["removed_total_sites"] or result["removed_authority_sites"]:
        lines.append(
            "NOTE: baseline site removals detected — "
            "baseline can be updated after review."
        )
    if result["authority_signal_changes"]:
        lines.append(
            f"NOTE: {len(result['authority_signal_changes'])} existing authority site(s) changed signal shape."
        )
    return "\n".join(lines)


def _count_sites(entries: list[dict[str, object]]) -> dict[str, int]:
    """Return per-substrate and total counts for a site list."""
    py_count = sum(1 for s in entries if s["substrate"] == "python")
    js_count = sum(1 for s in entries if s["substrate"] == "javascript")
    return {
        "python": py_count,
        "javascript": js_count,
        "total": py_count + js_count,
    }


def write_baseline(path: Path, current_inventories: dict[str, list[dict[str, object]]]) -> None:
    """Write baseline file from current inventories."""
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inventories": {
            "total": {
                "site_counts": _count_sites(current_inventories["total_sites"]),
                "entries": current_inventories["total_sites"],
            },
            "authority": {
                "site_counts": _count_sites(current_inventories["authority_sites"]),
                "entries": current_inventories["authority_sites"],
            },
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Host-authority inventory ratchet")
    parser.add_argument("--baseline", type=str, default=None, help="Custom baseline path")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--update-baseline", action="store_true", help="Write current inventory as baseline")
    args = parser.parse_args(argv)

    if args.update_baseline and os.environ.get("RCX_CI") == "1":
        print("ERROR: --update-baseline is forbidden in CI", file=sys.stderr)
        return 1

    py_files, js_files = _collect_files()
    if len(py_files) < MIN_PY_FILES:
        print(
            f"ERROR: zero-scan guard: found {len(py_files)} Python files (minimum {MIN_PY_FILES})",
            file=sys.stderr,
        )
        return 1
    if len(js_files) < MIN_JS_FILES:
        print(
            f"ERROR: zero-scan guard: found {len(js_files)} JS files (minimum {MIN_JS_FILES})",
            file=sys.stderr,
        )
        return 1

    current_inventories = scan_inventories(py_files, js_files)
    if len(current_inventories["total_sites"]) < MIN_TOTAL_SITES:
        print(
            f"ERROR: zero-scan guard: found {len(current_inventories['total_sites'])} total sites "
            f"(minimum {MIN_TOTAL_SITES})",
            file=sys.stderr,
        )
        return 1

    baseline_path = Path(args.baseline) if args.baseline else DEFAULT_BASELINE
    if args.update_baseline:
        if baseline_path.exists():
            baseline = load_baseline(baseline_path)
            result = compare_inventories(current_inventories, baseline)
            if result["new_total_sites"] or result["new_authority_sites"]:
                print(
                    "ERROR: Cannot update baseline while new total-inventory or authority-subset "
                    "sites exist. Review them first.",
                    file=sys.stderr,
                )
                return 1
        write_baseline(baseline_path, current_inventories)
        print(f"Wrote baseline: {baseline_path}")
        return 0

    baseline = load_baseline(baseline_path)
    result = compare_inventories(current_inventories, baseline)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(format_human(result, len(py_files), len(js_files)))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
