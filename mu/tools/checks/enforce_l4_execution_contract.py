#!/usr/bin/env python3
"""
Enforce L4 Execution Contract v2 wave classification.

3-class model: L4_STRUCTURAL, L4_ENABLER, MAINTENANCE.
Anti-stagnation: rolling structural quota, NO_OP throttling, fail-closed.

Usage:
    python tools/checks/enforce_l4_execution_contract.py --staged
    python tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD
    python tools/checks/enforce_l4_execution_contract.py --files f1 f2 ...
    python tools/checks/enforce_l4_execution_contract.py --wave-class L4_STRUCTURAL --files f1 f2 ...

Exit codes:
    0 -> compliant
    1 -> violation
    2 -> usage error
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_WAVE_CLASSES = frozenset({"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"})

# Historical alias — accepted in parse for old notes, rejected for new notes.
LEGACY_CLASS_ALIAS = {"L4_CLASS_A": "L4_STRUCTURAL"}

# Strict gate ID pattern
GATE_ID_RE = re.compile(r"^G[1-8]$")

# Runtime/substrate directories
RUNTIME_DIRS = (
    "mu/host/",
    "mu/substrate/",
    "mu/closures/",
    "mu/bridge/",
    "mu/programs/",
    "rcx_pi/selfhost/",
    "mu/tools/compilers/",
)

# Host-semantics debt categories (shared with ratchet checker).
HOST_SEMANTIC_CATEGORIES = frozenset({
    "host_iteration", "host_recursion", "host_builtin", "host_mutation",
})

# Baseline file is bookkeeping-only and cannot be changed in L4_STRUCTURAL waves.
HOST_SEMANTICS_BASELINE_CANONICAL = "tools/checks/host_semantics_baseline.json"

# Marker token matcher used for diff-level debt-movement detection.
HOST_MARKER_RE = re.compile(
    r"@(host_iteration|host_recursion|host_builtin|host_mutation)\b"
)

# Function extraction + construct detection patterns for semantic-removal proof (Rule A4).
PY_DEF_RE = re.compile(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PY_TOPLEVEL_BOUNDARY_RE = re.compile(r"^(def|class)\s+[A-Za-z_][A-Za-z0-9_]*\s*[\(:]")
PY_LOOP_RE = re.compile(r"^\s*(for|while)\b", re.MULTILINE)
PY_HOST_BUILTIN_CALL_RE = re.compile(
    r"\b(isinstance|len|zip|set|any|all|sum|min|max|sorted|dict|list|tuple)\s*\("
)

JS_DEF_RE = re.compile(r"^function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
JS_LOOP_RE = re.compile(r"\b(for|while)\s*\(|\bdo\b")
JS_HOST_BUILTIN_CALL_RE = re.compile(
    r"\b(Array\.isArray|Object\.(?:keys|values|entries|hasOwn)|JSON\.(?:stringify|parse)|Math\.[A-Za-z0-9_]+|crypto\.[A-Za-z0-9_]+)\s*\("
)
JS_COMMENT_BLOCK_LINE_RE = re.compile(r"^\s*(/\*\*?|/?\*|//)")
DIFF_HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@"
)

# Marker-to-function association tolerance: removed marker line must be close to function start.
FUNCTION_MARKER_LINE_DISTANCE = 12

# Comment-only patterns (Python and JS)
COMMENT_ONLY_PATTERNS = [
    re.compile(r"^\s*#"),       # Python comment
    re.compile(r"^\s*//"),      # JS comment
    re.compile(r"^\s*\*(?!\w)"),  # JS block comment line (not star-expr)
    re.compile(r"^\s*/\*"),     # JS block comment start
    re.compile(r"^\s*\*/"),     # JS block comment end
    re.compile(r'^\s*"""'),     # Python docstring delimiter
    re.compile(r"^\s*'''"),     # Python docstring delimiter
]

# Low-signal placeholders that should not be accepted as proof text.
LOW_SIGNAL_PROOF_TOKENS = frozenset({
    "old", "new", "before", "after", "before-state", "after-state",
    "runtime change", "runtime changes", "added function", "updated",
    "changed", "n/a", "na", "none", "todo", "tbd", "placeholder",
})

# Tracker note regex — captures header (date, wave_id) and body
_NOTE_HEADER_RE = re.compile(
    r"- Tracker sync note \(([^,]+),\s*([^)]+)\):\s*\*\*[^*]+\*\*\s*"
)
_NOTE_BODY_RE = re.compile(
    r"- Tracker sync note \([^)]+\):\s*\*\*[^*]+\*\*\s*(.*?)(?=\n- Tracker sync note |\n## |\Z)",
    re.DOTALL,
)

# Field extraction patterns
_CLASS_RE = re.compile(r"Class:\s*(L4_STRUCTURAL|L4_ENABLER|L4_CLASS_A|MAINTENANCE)")
_GATE_RE = re.compile(r"(?:Gate|target_gate_id):\s*(G[0-9]+)")
_NOP_RE = re.compile(r"(?:NO_OP_PROOF|no_op_proof):\s*(.+?)(?:\.\s|$)")
_EVIDENCE_CMD_RE = re.compile(r"evidence_command:\s*(.+?)(?:\.\s|$)")
_EVIDENCE_DELTA_RE = re.compile(r"evidence_delta:\s*(.+?)(?:\.\s|$)")
_HOST_DELTA_BEFORE_RE = re.compile(r"host_semantics_delta_before:\s*(.+?)(?:\.\s|$)")
_HOST_DELTA_AFTER_RE = re.compile(r"host_semantics_delta_after:\s*(.+?)(?:\.\s|$)")
_STRUCTURAL_ARTIFACT_RE = re.compile(r"structural_artifact_ref:\s*(.+?)(?:\.\s|$)")
_DEFER_REASON_RE = re.compile(r"defer_reason_code:\s*(.+?)(?:\.\s|$)")
_FOUNDER_OVERRIDE_RE = re.compile(r"FOUNDER_OVERRIDE:(\S+)")
_BLOCKER_CLASS_RE = re.compile(r"(?<!`)primary_blocker_class:\s*([A-Z_]+)")
_SWEEP_RE = re.compile(r"post_gate_contract_sweep:\s*(.+?)(?:\.\s|$)")
_INVARIANT_ID_RE = re.compile(r"(?<!`)primary_invariant_id:\s*([A-Z_]+)")
_PROGRESS_BEFORE_RE = re.compile(r"progress_proof_before:\s*(.+?)(?:\.\s|$)")
_PROGRESS_AFTER_RE = re.compile(r"progress_proof_after:\s*(.+?)(?:\.\s|$)")
_INDICATOR_REF_RE = re.compile(r"indicator_artifact_ref:\s*(.+?)(?:\.\s|$)")
_INDICATOR_CMD_RE = re.compile(r"indicator_collection_command:\s*(.+?)(?:\.\s|$)")
_BOOTSTRAP_POLICY_RE = re.compile(r"(?<!`)bootstrap_endgame_policy:\s*([A-Z_]+)")
_BOOT0_TRACK_RE = re.compile(r"(?<!`)boot0_track_id:\s*([A-Za-z0-9]+)")
_BOOT0_PROGRESS_RE = re.compile(r"(?<!`)boot0_progress_state:\s*([A-Z]+)")
_UNBLOCKS_WAVE_RE = re.compile(r"unblocks_wave_id:\s*([A-Za-z0-9_-]+)")
_UNBLOCKS_BLOCKER_RE = re.compile(r"unblocks_runtime_blocker:\s*(.+?)(?:\.\s|$)")
_WORKLOAD_TARGET_RE = re.compile(r"(?<!`)workload_target:\s*([A-Za-z0-9_/-]+)")
_WAVE_ID_TOKEN_RE = re.compile(r"^wave-[a-z0-9][a-z0-9_-]*$")
_RUNTIME_BLOCKER_TOKEN_RE = re.compile(r"^(RT-[A-Za-z0-9][A-Za-z0-9_-]*|INV_[A-Z0-9_]+)$")

# Rolling window size
ROLLING_WINDOW = 3

# Blocker classification (required for all class-marked waves)
VALID_BLOCKER_CLASSES = frozenset({"DESIGN", "INTEGRATION", "PERFORMANCE"})

# Non-gate test domains for post-gate contract sweep validation
NON_GATE_TEST_DOMAINS = (
    "tests/engine/", "tests/parity/", "tests/structural/", "tests/tools/", "tests/docs/",
    "mu/tests/engine/", "mu/tests/parity/", "mu/tests/structural/", "mu/tests/tools/", "mu/tests/docs/",
)

# Valid primary invariant IDs (every class-marked wave must declare one)
VALID_INVARIANT_IDS = frozenset({
    "INV_BOUND_HOST_TERMINATION",
    "INV_TERMINAL_SCHEMA_LOCK",
    "INV_CROSS_SUBSTRATE_PARITY",
    "INV_STRUCTURAL_FORWARD_MOTION",
    "INV_TYPED_FAIL_CLOSED_OUTCOMES",
})

# Canonical bootstrap endgame policy (single allowed value, resolves design split)
CANONICAL_BOOTSTRAP_POLICY = "SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP"

# Canonical indicator collector script path
CANONICAL_COLLECTOR_PATH = "tools/metrics/collect_l4_wave_indicators.py"

# Required indicator JSON keys with expected Python types
INDICATOR_REQUIRED_KEYS = {
    "repeat_run_speedup_ratio": (int, float),
    "parity_diff_count": (int,),
    "net_host_semantic_delta": (int,),
    "step_growth_slope": (int, float),
}

# Valid Boot0/Hex0 track IDs (from roadmap/Hex0_Boot0_Checklist.md)
VALID_BOOT0_TRACK_IDS = frozenset({
    "N1a", "N1b", "N2", "N3", "N4", "N5", "N6a", "N6b",
    "V1", "V2", "V3", "V4", "V5",
})

# Valid Boot0 progress states
VALID_BOOT0_PROGRESS_STATES = frozenset({"ADVANCE", "HOLD", "DEFER"})

# Required workload target for L4_STRUCTURAL notes (RCX-first semantic destination).
VALID_WORKLOAD_TARGETS = frozenset({
    "ontology_promotion",
    "rcx_engine_cycle",
    "seed_auto_execution",
    "execution_layer_truth",
    "recurrence_exhaustion",
    "host_debt_reduction",
})

# Proof binding: workload target → required contract test files.
# If a file list is non-empty, enforce() checks:
#   1. Files exist on disk (hard fail if missing)
#   2. At least one is in changed scope OR referenced in gate scripts
#   3. evidence_command references at least one test module name
WORKLOAD_TARGET_EVIDENCE = {
    "seed_auto_execution": [
        "mu/tests/structural/test_seed_auto_execution_contract.py",
        "mu/tests/tools/test_check_seed_auto_execution_contract.py",
    ],
    "rcx_engine_cycle": [
        "mu/tests/structural/test_rcx_engine_workload_contract.py",
    ],
    "execution_layer_truth": [
        "mu/tests/structural/test_execution_layer_truth_contract.py",
    ],
    "ontology_promotion": [],
    "recurrence_exhaustion": [],
    "host_debt_reduction": [],
}

# Gate scripts that run contract tests (proof binding alternative to changed scope).
GATE_SCRIPTS = (
    "tools/audits/audit_fast.sh",
    "tools/audits/audit_all.sh",
    "scripts/green_gate.sh",
)

# Required provenance keys in indicator JSON (Wave 18+)
INDICATOR_PROVENANCE_KEYS = {
    "repeat_run_raw_seconds": list,
    "step_growth_points": list,
    "parity_diff_source": str,
    "collection_timestamp_utc": str,
    "collector_version": str,
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def is_comment_line(line: str) -> bool:
    """Check if a diff line (after +/- prefix) is comment-only."""
    content = line.lstrip("+").lstrip("-")
    if not content.strip():
        return True
    return any(p.match(content) for p in COMMENT_ONLY_PATTERNS)


def _get_docstring_lines(source: str) -> set[int]:
    """Return 1-based line numbers that fall inside docstrings (ast.Expr string nodes)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()  # fail-closed: can't parse → no docstring detection
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str) and node.end_lineno is not None:
                for n in range(node.lineno, node.end_lineno + 1):
                    lines.add(n)
    return lines


def _strip_inline_comment(line: str) -> str:
    """Return the executable portion of a Python line (before inline #).

    Handles string literals containing '#' by tracking quote state.
    """
    in_single = False
    in_double = False
    escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == '#' and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def is_comment_only_runtime_diff(
    diff_text: str,
    runtime_files: list[str],
    old_ref: str = "HEAD",
) -> tuple[bool, list[str]]:
    """Check if ALL changes to runtime files are comment/docstring/marker-only.

    Enhanced beyond is_comment_line(): handles docstring interiors (via AST),
    inline comment additions (executable portion unchanged), and JS block
    comment content.

    Args:
        old_ref: Git ref for the diff preimage (old version). Must be derived
            from invocation mode: --staged => "HEAD", --range A...B =>
            merge-base(A,B). Hardcoding HEAD is WRONG for --range mode.

    Returns (is_comment_only, violations) where violations list executable changes.
    Fail-closed: if preimage cannot be resolved, removed non-comment Python
    lines are treated as violations.
    """
    violations: list[str] = []

    # Parse diff into per-file sections
    file_sections: dict[str, list[str]] = {}
    current_file: str | None = None
    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) >= 2 else None
        elif current_file and current_file in runtime_files:
            file_sections.setdefault(current_file, []).append(line)

    for filepath in runtime_files:
        lines = file_sections.get(filepath, [])
        if not lines:
            continue

        # For Python: build docstring line sets for old and new versions
        new_docstring_lines: set[int] = set()
        old_docstring_lines: set[int] = set()
        if filepath.endswith(".py"):
            # Current (new) file
            fpath = Path(filepath)
            if fpath.exists():
                new_docstring_lines = _get_docstring_lines(fpath.read_text(encoding="utf-8"))
            # Old file from diff preimage (old_ref, NOT hardcoded HEAD)
            old_preimage_resolved = False
            try:
                old_src = subprocess.check_output(
                    ["git", "show", f"{old_ref}:{filepath}"],
                    text=True, stderr=subprocess.DEVNULL,
                )
                old_docstring_lines = _get_docstring_lines(old_src)
                old_preimage_resolved = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Preimage unresolvable (new file or ref error).
                # Fail-closed: old_docstring_lines stays empty, so ALL removed
                # non-comment Python lines will be flagged as violations.
                old_preimage_resolved = False

        # Collect added and removed lines with their line numbers
        added_lines: list[tuple[int, str]] = []
        removed_lines: list[tuple[int, str]] = []
        new_lineno = 0
        old_lineno = 0
        for line in lines:
            if line.startswith("@@"):
                # Parse hunk header: @@ -old_start,count +new_start,count @@
                m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if m:
                    old_lineno = int(m.group(1)) - 1
                    new_lineno = int(m.group(2)) - 1
            elif line.startswith("+") and not line.startswith("+++"):
                new_lineno += 1
                added_lines.append((new_lineno, line[1:]))  # strip +
            elif line.startswith("-") and not line.startswith("---"):
                old_lineno += 1
                removed_lines.append((old_lineno, line[1:]))  # strip -
            else:
                # Context line
                new_lineno += 1
                old_lineno += 1

        # Check each added line
        for lineno, content in added_lines:
            if not content.strip():
                continue
            # Standard comment patterns
            if is_comment_line("+" + content):
                continue
            # Python docstring interior
            if filepath.endswith(".py") and lineno in new_docstring_lines:
                continue
            # Inline comment-only change: executable portion matches a removed line
            if filepath.endswith(".py"):
                exec_part = _strip_inline_comment(content)
                if any(_strip_inline_comment(rc) == exec_part for _, rc in removed_lines):
                    continue
            violations.append(f"{filepath}:{lineno}: added executable: {content.rstrip()[:80]}")

        # Check each removed line
        for lineno, content in removed_lines:
            if not content.strip():
                continue
            if is_comment_line("-" + content):
                continue
            if filepath.endswith(".py") and lineno in old_docstring_lines:
                continue
            # Inline comment-only change: executable portion matches an added line
            if filepath.endswith(".py"):
                exec_part = _strip_inline_comment(content)
                if any(_strip_inline_comment(ac) == exec_part for _, ac in added_lines):
                    continue
            violations.append(f"{filepath}:{lineno}: removed executable: {content.rstrip()[:80]}")

    return len(violations) == 0, violations


def is_runtime_file(filepath: str) -> bool:
    """Check if a file is in a runtime/substrate directory."""
    return any(filepath.startswith(d) for d in RUNTIME_DIRS)


def is_l4_gate_test(filepath: str) -> bool:
    """Check if a file is under tests/l4_gates/ (canonical or physical mu/ path)."""
    return filepath.startswith("tests/l4_gates/") or filepath.startswith("mu/tests/l4_gates/")


def _extract_python_functions(source: str) -> list[dict[str, object]]:
    """Extract top-level Python function metadata (name, lines, markers, body)."""
    lines = source.splitlines()
    funcs: list[dict[str, object]] = []

    for idx, line in enumerate(lines):
        m = PY_DEF_RE.match(line)
        if not m:
            continue

        name = m.group(1)
        start = idx + 1  # 1-based

        # Decorator stack immediately above function declaration.
        markers: set[str] = set()
        j = idx - 1
        while j >= 0 and lines[j].strip().startswith("@"):
            for cat in HOST_MARKER_RE.findall(lines[j]):
                markers.add(cat)
            j -= 1

        end_idx = len(lines)
        k = idx + 1
        while k < len(lines):
            if PY_TOPLEVEL_BOUNDARY_RE.match(lines[k]):
                end_idx = k
                break
            k += 1
        end = end_idx  # 1-based end-exclusive already converted by indexing usage below
        body = "\n".join(lines[idx + 1:end_idx])

        funcs.append({
            "name": name,
            "start_line": start,
            "end_line": end,
            "markers": markers,
            "body": body,
            "language": "python",
        })

    return funcs


def _extract_js_functions(source: str) -> list[dict[str, object]]:
    """Extract top-level JS function metadata (name, lines, markers, body)."""
    lines = source.splitlines()
    funcs: list[dict[str, object]] = []
    fn_indices = [i for i, ln in enumerate(lines) if JS_DEF_RE.match(ln)]

    for pos, idx in enumerate(fn_indices):
        line = lines[idx]
        m = JS_DEF_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        start = idx + 1

        markers: set[str] = set()
        j = idx - 1
        while j >= 0:
            prev = lines[j].strip()
            if not prev:
                break
            if not JS_COMMENT_BLOCK_LINE_RE.match(prev):
                break
            for cat in HOST_MARKER_RE.findall(lines[j]):
                markers.add(cat)
            j -= 1

        next_idx = fn_indices[pos + 1] if pos + 1 < len(fn_indices) else len(lines)
        end = next_idx
        body = "\n".join(lines[idx + 1:next_idx])

        funcs.append({
            "name": name,
            "start_line": start,
            "end_line": end,
            "markers": markers,
            "body": body,
            "language": "javascript",
        })

    return funcs


def _extract_functions_for_file(filepath: str, source: str) -> list[dict[str, object]]:
    """Extract function metadata for supported runtime languages."""
    if filepath.endswith(".py"):
        return _extract_python_functions(source)
    if filepath.endswith(".js"):
        return _extract_js_functions(source)
    return []


def _find_function_for_marker_anchor(
    functions: list[dict[str, object]],
    anchor_line: int,
) -> dict[str, object] | None:
    """Map a removed marker event to nearest function declaration in current file."""
    if not functions:
        return None

    nearest_forward = None
    nearest_delta = None
    for fn in functions:
        start = int(fn["start_line"])
        delta = start - anchor_line
        if delta < 0:
            continue
        if nearest_delta is None or delta < nearest_delta:
            nearest_delta = delta
            nearest_forward = fn

    if nearest_forward is not None and nearest_delta is not None and nearest_delta <= FUNCTION_MARKER_LINE_DISTANCE:
        return nearest_forward

    # Fallback: if anchor falls within function span, use containing function.
    for fn in functions:
        start = int(fn["start_line"])
        end = int(fn["end_line"])
        if start <= anchor_line <= end:
            return fn

    return None


def _function_has_self_call(function_meta: dict[str, object]) -> bool:
    """Detect recursive self-call inside function body (declaration line excluded)."""
    name = str(function_meta["name"])
    body = str(function_meta["body"])
    return bool(re.search(rf"\b{re.escape(name)}\s*\(", body))


def _function_has_loop_construct(function_meta: dict[str, object]) -> bool:
    """Detect host loop constructs in function body."""
    body = str(function_meta["body"])
    lang = str(function_meta["language"])
    if lang == "python":
        return bool(PY_LOOP_RE.search(body))
    return bool(JS_LOOP_RE.search(body))


def _function_has_host_builtin_calls(function_meta: dict[str, object]) -> bool:
    """Detect host builtin calls in function body (textual heuristic)."""
    body = str(function_meta["body"])
    lang = str(function_meta["language"])
    if lang == "python":
        return bool(PY_HOST_BUILTIN_CALL_RE.search(body))
    return bool(JS_HOST_BUILTIN_CALL_RE.search(body))


def collect_runtime_marker_events(
    diff_text: str,
    runtime_files: list[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Collect added/removed @host_* marker events with file + anchor line."""
    removed: list[dict[str, object]] = []
    added: list[dict[str, object]] = []

    current_file = None
    new_line = 0

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) >= 2 else None
            new_line = 0
            continue

        if not current_file or current_file not in runtime_files:
            continue

        hunk = DIFF_HUNK_RE.match(line)
        if hunk:
            new_line = int(hunk.group(2))
            continue

        if line.startswith("+") and not line.startswith("+++"):
            cats = HOST_MARKER_RE.findall(line)
            for cat in cats:
                added.append({
                    "file": current_file,
                    "category": cat,
                    "anchor_line": new_line,
                })
            new_line += 1
            continue

        if line.startswith("-") and not line.startswith("---"):
            cats = HOST_MARKER_RE.findall(line)
            for cat in cats:
                removed.append({
                    "file": current_file,
                    "category": cat,
                    "anchor_line": new_line,
                })
            continue

        if line.startswith(" "):
            new_line += 1

    return removed, added


def _marker_event_has_added_counterpart(
    removed_event: dict[str, object],
    added_events: list[dict[str, object]],
) -> bool:
    """Return True if a removed marker is likely a same-category marker rewrite.

    Checks both same-file rewrites (line distance within tolerance) and
    cross-file moves (same category in a different file — covers module
    extraction where functions move between files without semantic change).
    """
    rc = str(removed_event["category"])
    rf = str(removed_event["file"])
    ra = int(removed_event["anchor_line"])
    for ev in added_events:
        if str(ev["category"]) != rc:
            continue
        ef = str(ev["file"])
        if ef == rf:
            # Same-file rewrite: check line distance
            aa = int(ev["anchor_line"])
            if abs(aa - ra) <= FUNCTION_MARKER_LINE_DISTANCE:
                return True
        else:
            # Cross-file move: same category in different file is sufficient
            return True
    return False


def _is_evidence_in_gate_scripts(evidence_files: list[str]) -> bool:
    """Check if any evidence file path/module appears in gate scripts."""
    for script_rel in GATE_SCRIPTS:
        script_path = Path(script_rel)
        if not script_path.exists():
            continue
        try:
            content = script_path.read_text()
        except OSError:
            continue
        for ef in evidence_files:
            module_name = Path(ef).stem
            if module_name in content or ef in content:
                return True
    return False


def _check_proof_binding(
    workload_target: str,
    evidence_command: str | None,
    changed_files: list[str],
) -> list[str]:
    """Check proof binding for a workload target.

    Returns list of errors (empty = valid).
    """
    evidence_files = WORKLOAD_TARGET_EVIDENCE.get(workload_target, [])
    if not evidence_files:
        return []

    errors: list[str] = []

    # 1. Contract test files must exist on disk
    for ef in evidence_files:
        if not Path(ef).exists():
            errors.append(
                f"Workload target '{workload_target}' proof binding: "
                f"contract test file missing on disk: {ef}"
            )

    # 2. At least one evidence file in changed scope OR in gate scripts
    # Normalize paths: changed_files may use mu/ prefix or not
    in_scope = any(
        ef in changed_files or ef.replace("mu/", "", 1) in changed_files
        for ef in evidence_files
    )
    gate_bound = _is_evidence_in_gate_scripts(evidence_files)
    if not in_scope and not gate_bound:
        errors.append(
            f"Workload target '{workload_target}' proof binding: "
            f"none of {evidence_files} appear in changed files or gate scripts"
        )

    # 3. evidence_command must reference at least one test module name
    if evidence_command:
        module_names = [Path(ef).stem for ef in evidence_files]
        if not any(mn in evidence_command for mn in module_names):
            errors.append(
                f"Workload target '{workload_target}' proof binding: "
                f"evidence_command must reference one of {module_names}. "
                f"Got: {evidence_command!r}"
            )

    return errors


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def filter_to_tracked_files(files: list[str]) -> list[str]:
    """Filter file list to only git-tracked files (defense against untracked leaks).

    Scope policy: the L4 checker operates on tracked changes only.
    Untracked files are not part of any wave scope and must be excluded.
    """
    if not files:
        return files
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--"] + files,
            capture_output=True, text=True,
        )
        tracked = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
        untracked = [f for f in files if f not in tracked]
        if untracked:
            print(f"NOTE: Stripping {len(untracked)} untracked file(s) from scope: "
                  f"{untracked[:5]}")
        return [f for f in files if f in tracked]
    except Exception:
        return files  # If git fails, pass through unchanged


def get_changed_files_staged() -> list[str]:
    """Get staged file paths."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_changed_files_range(git_range: str) -> list[str]:
    """Get changed file paths in a git range."""
    result = subprocess.run(
        ["git", "diff", "--name-only", git_range],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_diff_staged() -> str:
    """Get staged diff content."""
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def get_diff_range(git_range: str) -> str:
    """Get diff content for a range."""
    result = subprocess.run(
        ["git", "diff", "-U0", git_range],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def has_non_comment_runtime_delta(diff_text: str, runtime_files: list[str]) -> bool:
    """Check if any runtime file has non-comment changes."""
    added, deleted, _ = compute_runtime_exec_delta(diff_text, runtime_files)
    return (added + deleted) > 0


def compute_runtime_exec_delta(diff_text: str, runtime_files: list[str]) -> tuple[int, int, int]:
    """Compute runtime executable delta from diff text.

    Returns:
        (added_lines, deleted_lines, net_delta)
    """
    added = 0
    deleted = 0
    current_file = None
    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) >= 2 else None
        elif current_file and current_file in runtime_files:
            if line.startswith("+") and not line.startswith("+++"):
                if not is_comment_line(line):
                    added += 1
            elif line.startswith("-") and not line.startswith("---"):
                if not is_comment_line(line):
                    deleted += 1
    return added, deleted, (added - deleted)


def _canonical_repo_path(filepath: str) -> str:
    """Canonicalize path for policy checks across root/mu symlink layouts."""
    p = filepath.lstrip("./")
    if p.startswith("mu/"):
        p = p[3:]
    return p


def _touches_host_semantics_baseline(changed_files: list[str]) -> bool:
    """Return True if host-semantics baseline file is modified."""
    return any(
        _canonical_repo_path(f) == HOST_SEMANTICS_BASELINE_CANONICAL
        for f in changed_files
    )


def compute_runtime_host_marker_delta(
    diff_text: str,
    runtime_files: list[str],
) -> tuple[dict[str, int], dict[str, int], int, int]:
    """Compute added/removed @host_* markers in runtime files from a diff."""
    added = {cat: 0 for cat in sorted(HOST_SEMANTIC_CATEGORIES)}
    removed = {cat: 0 for cat in sorted(HOST_SEMANTIC_CATEGORIES)}

    current_file = None
    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) >= 2 else None
            continue
        if not current_file or current_file not in runtime_files:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            matches = HOST_MARKER_RE.findall(line)
            for cat in matches:
                if cat in added:
                    added[cat] += 1
        elif line.startswith("-") and not line.startswith("---"):
            matches = HOST_MARKER_RE.findall(line)
            for cat in matches:
                if cat in removed:
                    removed[cat] += 1

    total_added = sum(added.values())
    total_removed = sum(removed.values())
    return added, removed, total_added, total_removed


def probe_host_semantics_ratchet() -> tuple[dict | None, list[str]]:
    """Run host-semantics ratchet checker in JSON mode (fail-closed helper)."""
    checker = Path(__file__).resolve().with_name("check_host_semantics_ratchet.py")
    if not checker.exists():
        return None, [
            f"Host-semantics ratchet probe unavailable: missing script at '{checker}'"
        ]

    proc = subprocess.run(
        [sys.executable, str(checker), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        stderr = proc.stderr.strip() or "(no stderr)"
        return None, [
            "Host-semantics ratchet probe failed unexpectedly "
            f"(exit {proc.returncode}): {stderr}"
        ]

    stdout = proc.stdout.strip()
    if not stdout:
        return None, ["Host-semantics ratchet probe returned empty JSON output"]

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        snippet = stdout[:220].replace("\n", " ")
        return None, [
            f"Host-semantics ratchet probe JSON parse failed: {exc}. Output: {snippet!r}"
        ]

    if not isinstance(data, dict):
        return None, ["Host-semantics ratchet probe output must be a JSON object"]
    if "current" not in data or "baseline_counts" not in data:
        return None, [
            "Host-semantics ratchet probe missing required keys: "
            "'current' and/or 'baseline_counts'"
        ]

    return data, []


def summarize_host_semantics_delta(ratchet_json: dict) -> tuple[int, int, list[dict[str, int | str]]]:
    """Summarize baseline/current host debt totals and per-category increases."""
    current = ratchet_json.get("current", {})
    baseline = ratchet_json.get("baseline_counts", {})
    increases: list[dict[str, int | str]] = []

    baseline_total = 0
    current_total = 0

    for substrate in ("python", "javascript"):
        base_sub = baseline.get(substrate, {}) if isinstance(baseline, dict) else {}
        curr_sub = current.get(substrate, {}) if isinstance(current, dict) else {}
        for cat in sorted(HOST_SEMANTIC_CATEGORIES):
            b_raw = base_sub.get(cat, 0) if isinstance(base_sub, dict) else 0
            c_raw = curr_sub.get(cat, 0) if isinstance(curr_sub, dict) else 0
            try:
                b_val = int(b_raw)
                c_val = int(c_raw)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Non-integer host-semantics value for {substrate}.{cat}: "
                    f"baseline={b_raw!r}, current={c_raw!r}"
                ) from None

            baseline_total += b_val
            current_total += c_val
            if c_val > b_val:
                increases.append({
                    "substrate": substrate,
                    "category": cat,
                    "baseline": b_val,
                    "current": c_val,
                    "delta": c_val - b_val,
                })

    return baseline_total, current_total, increases


# ---------------------------------------------------------------------------
# Tracker note parsing
# ---------------------------------------------------------------------------

def parse_tracker_notes(text: str) -> list[dict[str, str | None]]:
    """
    Parse ordered tracker sync notes from TASKS.md Ra section.

    Returns list of dicts in document order (first = most recent).
    Only includes notes that have a Class: marker.
    Historical L4_CLASS_A is aliased to L4_STRUCTURAL.
    """
    notes: list[dict[str, str | None]] = []

    for header_m in _NOTE_HEADER_RE.finditer(text):
        date_str = header_m.group(1).strip()
        wave_id = header_m.group(2).strip()

        # Find body for this note
        body_m = _NOTE_BODY_RE.match(text, header_m.start())
        if not body_m:
            continue
        body_text = body_m.group(1)  # body after **title**, not full match
        body = body_m.group(0)      # full match for raw storage

        cls_match = _CLASS_RE.search(body_text)
        override_present = _FOUNDER_OVERRIDE_RE.search(body_text)
        if not cls_match and not override_present:
            continue

        raw_class = cls_match.group(1) if cls_match else None
        wave_class = LEGACY_CLASS_ALIAS.get(raw_class, raw_class)

        gate_match = _GATE_RE.search(body_text)
        nop_match = _NOP_RE.search(body_text)
        ev_cmd_match = _EVIDENCE_CMD_RE.search(body_text)
        ev_delta_match = _EVIDENCE_DELTA_RE.search(body_text)
        hd_before_match = _HOST_DELTA_BEFORE_RE.search(body_text)
        hd_after_match = _HOST_DELTA_AFTER_RE.search(body_text)
        sa_match = _STRUCTURAL_ARTIFACT_RE.search(body_text)
        defer_match = _DEFER_REASON_RE.search(body_text)
        override_match = _FOUNDER_OVERRIDE_RE.search(body_text)
        blocker_match = _BLOCKER_CLASS_RE.search(body_text)
        sweep_match = _SWEEP_RE.search(body_text)
        invariant_match = _INVARIANT_ID_RE.search(body_text)
        progress_before_match = _PROGRESS_BEFORE_RE.search(body_text)
        progress_after_match = _PROGRESS_AFTER_RE.search(body_text)
        indicator_ref_match = _INDICATOR_REF_RE.search(body_text)
        indicator_cmd_match = _INDICATOR_CMD_RE.search(body_text)
        bootstrap_policy_match = _BOOTSTRAP_POLICY_RE.search(body_text)
        boot0_track_match = _BOOT0_TRACK_RE.search(body_text)
        boot0_progress_match = _BOOT0_PROGRESS_RE.search(body_text)
        unblocks_wave_match = _UNBLOCKS_WAVE_RE.search(body_text)
        unblocks_blocker_match = _UNBLOCKS_BLOCKER_RE.search(body_text)
        workload_target_match = _WORKLOAD_TARGET_RE.search(body_text)

        notes.append({
            "wave_id": wave_id,
            "raw_class": raw_class,
            "wave_class": wave_class,
            "gate": gate_match.group(1) if gate_match else None,
            "no_op_proof": nop_match.group(1).strip() if nop_match else None,
            "evidence_command": ev_cmd_match.group(1).strip() if ev_cmd_match else None,
            "evidence_delta": ev_delta_match.group(1).strip() if ev_delta_match else None,
            "host_semantics_delta_before": hd_before_match.group(1).strip() if hd_before_match else None,
            "host_semantics_delta_after": hd_after_match.group(1).strip() if hd_after_match else None,
            "structural_artifact_ref": sa_match.group(1).strip() if sa_match else None,
            "defer_reason_code": defer_match.group(1).strip() if defer_match else None,
            "founder_override": override_match.group(1).strip().rstrip(".,;") if override_match else None,
            "primary_blocker_class": blocker_match.group(1).strip() if blocker_match else None,
            "post_gate_contract_sweep": sweep_match.group(1).strip() if sweep_match else None,
            "primary_invariant_id": invariant_match.group(1).strip() if invariant_match else None,
            "progress_proof_before": progress_before_match.group(1).strip() if progress_before_match else None,
            "progress_proof_after": progress_after_match.group(1).strip() if progress_after_match else None,
            "indicator_artifact_ref": indicator_ref_match.group(1).strip() if indicator_ref_match else None,
            "indicator_collection_command": indicator_cmd_match.group(1).strip() if indicator_cmd_match else None,
            "bootstrap_endgame_policy": bootstrap_policy_match.group(1).strip() if bootstrap_policy_match else None,
            "boot0_track_id": boot0_track_match.group(1).strip() if boot0_track_match else None,
            "boot0_progress_state": boot0_progress_match.group(1).strip() if boot0_progress_match else None,
            "unblocks_wave_id": unblocks_wave_match.group(1).strip() if unblocks_wave_match else None,
            "unblocks_runtime_blocker": unblocks_blocker_match.group(1).strip() if unblocks_blocker_match else None,
            "workload_target": workload_target_match.group(1).strip() if workload_target_match else None,
            "date": date_str,
            "raw": body,
        })

    return notes


# ---------------------------------------------------------------------------
# Anti-stagnation checks
# ---------------------------------------------------------------------------

def check_consecutive_maintenance(notes: list[dict]) -> tuple[bool, list[str]]:
    """Check consecutive MAINTENANCE cadence rule.

    Two consecutive MAINTENANCE waves are allowed ONLY if the current wave
    provides both:
      - unblocks_wave_id: <id>
      - unblocks_runtime_blocker: <finding-id or invariant>

    Returns (passed, errors).
    """
    if len(notes) < 2:
        return True, []
    if not (notes[0]["wave_class"] == "MAINTENANCE" and notes[1]["wave_class"] == "MAINTENANCE"):
        return True, []

    # Consecutive MAINTENANCE detected — check for bypass fields
    current = notes[0]
    has_unblocks_wave = current.get("unblocks_wave_id") is not None
    has_unblocks_blocker = current.get("unblocks_runtime_blocker") is not None

    if not (has_unblocks_wave and has_unblocks_blocker):
        missing = []
        if not has_unblocks_wave:
            missing.append("unblocks_wave_id")
        if not has_unblocks_blocker:
            missing.append("unblocks_runtime_blocker")
        return False, [
            "Consecutive MAINTENANCE cap exceeded. "
            "Max 1 consecutive MAINTENANCE without L4_STRUCTURAL or L4_ENABLER. "
            f"To bypass, add: {', '.join(missing)} to the tracker note."
        ]

    # Bypass fields are present; enforce runtime-blocker quality and linkage.
    errors: list[str] = []
    unblocks_wave_id = str(current.get("unblocks_wave_id") or "").strip()
    runtime_blocker = str(current.get("unblocks_runtime_blocker") or "").strip()

    if not _WAVE_ID_TOKEN_RE.match(unblocks_wave_id):
        errors.append(
            "Consecutive MAINTENANCE bypass requires unblocks_wave_id in canonical form "
            "'wave-<id>'."
        )
    if unblocks_wave_id == current.get("wave_id"):
        errors.append(
            "Consecutive MAINTENANCE bypass cannot self-reference unblocks_wave_id."
        )

    # If referenced wave is already present in tracker history, it must not be MAINTENANCE.
    referenced = next((n for n in notes[1:] if n.get("wave_id") == unblocks_wave_id), None)
    if referenced and referenced.get("wave_class") == "MAINTENANCE":
        errors.append(
            "Consecutive MAINTENANCE bypass requires unblocks_wave_id to reference a non-"
            "MAINTENANCE wave when the target wave exists in tracker history."
        )

    blocker_class = current.get("primary_blocker_class")
    if blocker_class not in {"INTEGRATION", "PERFORMANCE"}:
        errors.append(
            "Consecutive MAINTENANCE bypass requires primary_blocker_class to be "
            "INTEGRATION or PERFORMANCE (runtime blocker), not DESIGN."
        )

    blocker_token_valid = bool(_RUNTIME_BLOCKER_TOKEN_RE.match(runtime_blocker))
    if not blocker_token_valid and _is_low_signal_proof(runtime_blocker):
        errors.append(
            "Consecutive MAINTENANCE bypass requires a non-placeholder "
            "unblocks_runtime_blocker token."
        )
    elif not blocker_token_valid:
        errors.append(
            "Consecutive MAINTENANCE bypass requires unblocks_runtime_blocker to use "
            "runtime/invariant token form (e.g., RT-005 or INV_CROSS_SUBSTRATE_PARITY)."
        )

    if errors:
        return False, errors
    return True, []


def check_rolling_window(notes: list[dict]) -> tuple[bool, list[str]]:
    """
    Rolling structural quota: in last ROLLING_WINDOW class-marked waves,
    at least 1 must be L4_STRUCTURAL.

    Skips if fewer than ROLLING_WINDOW notes exist (bootstrap grace).
    """
    if len(notes) < ROLLING_WINDOW:
        return True, []

    window = notes[:ROLLING_WINDOW]
    has_structural = any(n["wave_class"] == "L4_STRUCTURAL" for n in window)
    if not has_structural:
        if notes[0].get("founder_override"):
            print(f"  FOUNDER_OVERRIDE active — allowing rolling window without STRUCTURAL")
            return True, []
        classes = [n["wave_class"] for n in window]
        return False, [
            f"Rolling structural quota violated: last {ROLLING_WINDOW} waves "
            f"have no L4_STRUCTURAL. Classes: {classes}"
        ]
    return True, []


def check_noop_throttle(notes: list[dict]) -> tuple[bool, list[str]]:
    """
    NO_OP throttling: same target_gate_id cannot use no_op_proof twice
    in the last ROLLING_WINDOW class-marked waves.

    Founder override grants exactly one exception per gate:
    - count <= 1: pass (no throttle)
    - count == 2: pass only if exactly one valid override for that same gate
    - count > 2: fail even with override (one exception only)
    """
    window = notes[:ROLLING_WINDOW]
    gate_noop_count: dict[str, int] = {}
    gate_override_count: dict[str, int] = {}

    for n in window:
        if n["no_op_proof"] and n["gate"]:
            gate_noop_count[n["gate"]] = gate_noop_count.get(n["gate"], 0) + 1
        if n["founder_override"] and n["gate"]:
            gate_override_count[n["gate"]] = gate_override_count.get(n["gate"], 0) + 1

    errors = []
    for gate_id, count in gate_noop_count.items():
        if count == 2 and gate_override_count.get(gate_id, 0) == 1:
            print(f"  FOUNDER_OVERRIDE active for {gate_id} — "
                  f"allowing one NO_OP repeat")
        elif count >= 2:
            if gate_override_count.get(gate_id, 0) == 0:
                errors.append(
                    f"NO_OP throttle violated: gate {gate_id} has {count} "
                    f"NO_OP_PROOF entries in last {ROLLING_WINDOW} waves. "
                    f"Requires FOUNDER_OVERRIDE:<id> on the same gate to bypass."
                )
            else:
                errors.append(
                    f"NO_OP throttle violated: gate {gate_id} has {count} "
                    f"NO_OP_PROOF entries in last {ROLLING_WINDOW} waves. "
                    f"Override grants one exception only (count <= 2)."
                )

    return len(errors) == 0, errors


def check_founder_override_replay(notes: list[dict]) -> tuple[bool, list[str]]:
    """Founder override replay protection: duplicate IDs in window must fail."""
    window = notes[:ROLLING_WINDOW]
    seen: dict[str, int] = {}
    for n in window:
        oid = n["founder_override"]
        if oid:
            seen[oid] = seen.get(oid, 0) + 1

    errors = []
    for oid, count in seen.items():
        if count > 1:
            errors.append(
                f"FOUNDER_OVERRIDE replay detected: '{oid}' used {count} times "
                f"in last {ROLLING_WINDOW} waves. Each override ID is single-use."
            )
    return len(errors) == 0, errors


def check_non_structural_adjacency(notes: list[dict]) -> tuple[bool, list[str]]:
    """Non-structural adjacency cap: last 2 class-marked waves cannot both be non-STRUCTURAL.

    Founder override on current wave grants bypass.
    """
    if len(notes) < 2:
        return True, []
    if notes[0]["wave_class"] != "L4_STRUCTURAL" and notes[1]["wave_class"] != "L4_STRUCTURAL":
        if notes[0].get("founder_override"):
            print(f"  FOUNDER_OVERRIDE active — allowing non-structural adjacency")
            return True, []
        return False, [
            f"Non-structural adjacency cap violated: last 2 waves are "
            f"{notes[0]['wave_class']} and {notes[1]['wave_class']}. "
            f"At least 1 must be L4_STRUCTURAL. Use FOUNDER_OVERRIDE:<id> to bypass."
        ]
    return True, []


def check_maintenance_metadata(notes: list[dict]) -> tuple[bool, list[str]]:
    """Check if the most recent MAINTENANCE wave note has required metadata."""
    if not notes:
        return True, []
    current = notes[0]
    if current["wave_class"] != "MAINTENANCE":
        return True, []
    errors = []
    if current["no_op_proof"] is None:
        errors.append("MAINTENANCE wave missing no_op_proof in tracker sync note")
    if current["gate"] is None:
        errors.append("MAINTENANCE wave missing target_gate_id in tracker sync note")
    if current["defer_reason_code"] is None:
        errors.append("MAINTENANCE wave missing defer_reason_code in tracker sync note")
    return len(errors) == 0, errors


def check_legacy_alias_in_new_notes(notes: list[dict]) -> tuple[bool, list[str]]:
    """New notes using L4_CLASS_A must fail. Only historical parsing allowed."""
    if not notes:
        return True, []
    current = notes[0]
    if current["raw_class"] == "L4_CLASS_A":
        return False, [
            "New tracker note uses legacy class L4_CLASS_A. "
            "Use L4_STRUCTURAL, L4_ENABLER, or MAINTENANCE instead."
        ]
    return True, []


# ---------------------------------------------------------------------------
# Indicator artifact validation
# ---------------------------------------------------------------------------

def _is_numeric_not_bool(val: object) -> bool:
    """Check if value is numeric (int or float) but not bool."""
    return not isinstance(val, bool) and isinstance(val, (int, float))


def _is_low_signal_proof(text: str | None) -> bool:
    """Detect placeholder/theater proof text."""
    if text is None:
        return True
    normalized = " ".join(text.strip().lower().split())
    if len(normalized) < 12:
        return True
    return normalized in LOW_SIGNAL_PROOF_TOKENS


def _compute_slope(points: list[dict]) -> float:
    """Compute step_growth_slope from step_growth_points via linear fit.

    Formula: slope = (elapsed_last - elapsed_first) / (step_last - step_first)
    """
    first, last = points[0], points[-1]
    dx = last["step"] - first["step"]
    if dx == 0:
        return 0.0
    return (last["elapsed_seconds"] - first["elapsed_seconds"]) / dx


def validate_indicator_artifact_json(
    artifact_path: str,
    *,
    expected_net_host_delta: int | None = None,
) -> tuple[bool, list[str]]:
    """Validate indicator artifact JSON: required keys, types, provenance, derivation."""
    import json as _json
    errors: list[str] = []
    path = Path(artifact_path)
    if not path.exists():
        return False, [f"Indicator artifact '{artifact_path}' does not exist on disk."]
    try:
        data = _json.loads(path.read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, OSError) as exc:
        return False, [f"Indicator artifact '{artifact_path}' invalid JSON: {exc}"]

    # --- Core metric keys ---
    for key, types in INDICATOR_REQUIRED_KEYS.items():
        if key not in data:
            errors.append(f"Indicator artifact missing required key: '{key}'")
        else:
            val = data[key]
            if isinstance(val, bool) or not isinstance(val, types):
                errors.append(
                    f"Indicator key '{key}': got {type(val).__name__}, "
                    f"expected {'/'.join(t.__name__ for t in types)}"
                )

    # --- Provenance keys ---
    for key, expected_type in INDICATOR_PROVENANCE_KEYS.items():
        if key not in data:
            errors.append(f"Indicator artifact missing provenance key: '{key}'")
        else:
            val = data[key]
            if not isinstance(val, expected_type):
                errors.append(
                    f"Provenance key '{key}': got {type(val).__name__}, "
                    f"expected {expected_type.__name__}"
                )

    # --- repeat_run_raw_seconds shape ---
    raw_secs = data.get("repeat_run_raw_seconds")
    if isinstance(raw_secs, list):
        if len(raw_secs) != 2:
            errors.append(
                f"repeat_run_raw_seconds must have exactly 2 elements, got {len(raw_secs)}"
            )
        else:
            for i, v in enumerate(raw_secs):
                if not _is_numeric_not_bool(v):
                    errors.append(
                        f"repeat_run_raw_seconds[{i}]: got {type(v).__name__}, "
                        f"expected numeric (not bool)"
                    )
                elif v <= 0:
                    errors.append(f"repeat_run_raw_seconds[{i}]: must be > 0, got {v}")

    # --- step_growth_points shape ---
    sgp = data.get("step_growth_points")
    sgp_valid = False
    if isinstance(sgp, list):
        if len(sgp) < 2:
            errors.append(
                f"step_growth_points must have >= 2 elements, got {len(sgp)}"
            )
        else:
            sgp_valid = True
            prev_step = None
            for i, pt in enumerate(sgp):
                if not isinstance(pt, dict):
                    errors.append(f"step_growth_points[{i}]: must be object, got {type(pt).__name__}")
                    sgp_valid = False
                    continue
                for fld in ("step", "elapsed_seconds"):
                    fv = pt.get(fld)
                    if fv is None:
                        errors.append(f"step_growth_points[{i}] missing '{fld}'")
                        sgp_valid = False
                    elif not _is_numeric_not_bool(fv):
                        errors.append(
                            f"step_growth_points[{i}].{fld}: got {type(fv).__name__}, "
                            f"expected numeric (not bool)"
                        )
                        sgp_valid = False
                if sgp_valid and prev_step is not None:
                    if pt["step"] <= prev_step:
                        errors.append(
                            f"step_growth_points[{i}].step ({pt['step']}) must be "
                            f"strictly greater than previous ({prev_step})"
                        )
                        sgp_valid = False
                if sgp_valid:
                    prev_step = pt["step"]

    # --- String provenance: non-empty ---
    for skey in ("parity_diff_source", "collection_timestamp_utc", "collector_version"):
        sv = data.get(skey)
        if isinstance(sv, str) and not sv.strip():
            errors.append(f"Provenance key '{skey}' must be non-empty string")

    # --- Derivation check: repeat_run_speedup_ratio ---
    if (isinstance(raw_secs, list) and len(raw_secs) == 2
            and all(_is_numeric_not_bool(v) and v > 0 for v in raw_secs)):
        expected_ratio = round(raw_secs[0] / raw_secs[1], 6)
        actual_ratio = data.get("repeat_run_speedup_ratio")
        if _is_numeric_not_bool(actual_ratio) and round(actual_ratio, 6) != expected_ratio:
            errors.append(
                f"Derivation mismatch: repeat_run_speedup_ratio={actual_ratio} "
                f"but round(raw[0]/raw[1], 6)={expected_ratio}"
            )

    # --- Derivation check: step_growth_slope ---
    if sgp_valid and isinstance(sgp, list) and len(sgp) >= 2:
        expected_slope = round(_compute_slope(sgp), 6)
        actual_slope = data.get("step_growth_slope")
        if _is_numeric_not_bool(actual_slope) and round(actual_slope, 6) != expected_slope:
            errors.append(
                f"Derivation mismatch: step_growth_slope={actual_slope} "
                f"but computed from points={expected_slope}"
            )

    # --- Scope consistency check: net_host_semantic_delta ---
    if expected_net_host_delta is not None:
        actual_net = data.get("net_host_semantic_delta")
        if _is_numeric_not_bool(actual_net):
            if int(actual_net) != int(expected_net_host_delta):
                errors.append(
                    "Indicator mismatch: net_host_semantic_delta="
                    f"{actual_net} but host-semantics ratchet net delta={expected_net_host_delta}"
                )

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Core enforcement
# ---------------------------------------------------------------------------

def enforce(
    wave_class: str | None,
    changed_files: list[str],
    diff_text: str | None = None,
    notes: list[dict] | None = None,
    old_ref: str = "HEAD",
    override_wave_bound: bool = False,
) -> tuple[bool, list[str]]:
    """
    Enforce L4 execution contract v2.

    Args:
        old_ref: Git ref for diff preimage (threaded to comment-only classifier).
        override_wave_bound: True only when notes[0] was explicitly bound via
            --wave-id. Stale top-note overrides are rejected when False.

    Returns (passed, errors).
    """
    errors: list[str] = []
    runtime_files = [f for f in changed_files if is_runtime_file(f)]

    # Fail-closed: runtime changes without class marker
    if not wave_class:
        if runtime_files:
            # FOUNDER_OVERRIDE bypass for comment/docstring-only runtime edits.
            # Conditions (ALL must hold, fail-closed):
            #   a) FOUNDER_OVERRIDE:<id> in tracker note
            #   b) Runtime diff is comment/docstring/marker-only (zero executable delta)
            #   c) Tracker note has no_op_proof + target_gate_id
            #   d) Override ID not replayed (existing replay protection)
            #   e) Override must be wave-bound (--wave-id), not stale top-note
            override_id = None
            if notes and override_wave_bound:
                for n in notes[:1]:  # only check bound note (position 0)
                    oid = n.get("founder_override")
                    if oid:
                        override_id = oid
                        break

            if override_id and diff_text:
                comment_only, violations = is_comment_only_runtime_diff(
                    diff_text, runtime_files, old_ref=old_ref,
                )
                if not comment_only:
                    errors.append(
                        f"FOUNDER_OVERRIDE:{override_id} rejected — "
                        f"runtime diff contains executable changes: "
                        f"{violations[:3]}"
                    )
                    return False, errors
                # Require no_op_proof and target_gate_id in the note
                note = notes[0]
                missing_meta: list[str] = []
                if not note.get("no_op_proof"):
                    missing_meta.append("no_op_proof")
                if not note.get("gate"):
                    missing_meta.append("target_gate_id")
                if missing_meta:
                    errors.append(
                        f"FOUNDER_OVERRIDE:{override_id} rejected — "
                        f"missing required metadata: {', '.join(missing_meta)}"
                    )
                    return False, errors
                # Replay protection — must run BEFORE early return
                replay_ok, replay_errors = check_founder_override_replay(notes)
                if not replay_ok:
                    errors.extend(replay_errors)
                    return False, errors
                print(
                    f"  FOUNDER_OVERRIDE:{override_id} active — "
                    f"allowing comment-only runtime edit "
                    f"({len(runtime_files)} runtime file(s))"
                )
                return True, []

            errors.append(
                f"FAIL-CLOSED: Runtime/core files changed but no wave class marker found. "
                f"Runtime files: {runtime_files[:5]}"
            )
            return False, errors
        return True, []

    # Validate class is in strict enum
    if wave_class not in VALID_WAVE_CLASSES:
        errors.append(f"Unknown wave class: {wave_class}")
        return False, errors

    # --- L4_STRUCTURAL ---
    if wave_class == "L4_STRUCTURAL":
        if not runtime_files:
            errors.append(
                f"L4_STRUCTURAL wave has no runtime/substrate files. "
                f"Changed: {changed_files[:5]}"
            )
        elif diff_text and not has_non_comment_runtime_delta(diff_text, runtime_files):
            errors.append(
                "L4_STRUCTURAL wave touches runtime files but all changes are "
                "comment-only. Must have executable runtime delta."
            )

        # Gate test evidence AND rule
        gate_test_files = [f for f in changed_files if is_l4_gate_test(f)]
        if not gate_test_files:
            errors.append(
                "L4_STRUCTURAL wave missing changed file under tests/l4_gates/ "
                "(or mu/tests/l4_gates/). Must include gate-linked test evidence."
            )

        # Host semantics delta fields (checked via notes if available)
        if notes:
            current = notes[0]
            if current["evidence_delta"] is None:
                errors.append("L4_STRUCTURAL missing evidence_delta in tracker note")
            if current["host_semantics_delta_before"] is None:
                errors.append("L4_STRUCTURAL missing host_semantics_delta_before in tracker note")
            if current["host_semantics_delta_after"] is None:
                errors.append("L4_STRUCTURAL missing host_semantics_delta_after in tracker note")
            if _is_low_signal_proof(current["host_semantics_delta_before"]):
                errors.append(
                    "L4_STRUCTURAL host_semantics_delta_before is low-signal/placeholder text"
                )
            if _is_low_signal_proof(current["host_semantics_delta_after"]):
                errors.append(
                    "L4_STRUCTURAL host_semantics_delta_after is low-signal/placeholder text"
                )
            if current["structural_artifact_ref"] is None:
                errors.append("L4_STRUCTURAL missing structural_artifact_ref in tracker note")
            if current["evidence_command"] is None:
                errors.append("L4_STRUCTURAL missing evidence_command in tracker note")
            elif ("tests/l4_gates/" not in current["evidence_command"]
                  and "mu/tests/l4_gates/" not in current["evidence_command"]):
                errors.append(
                    "L4_STRUCTURAL evidence_command must reference tests/l4_gates/ "
                    f"(or mu/tests/l4_gates/) target. Got: {current['evidence_command']!r}"
                )
            # Post-gate contract sweep (must reference non-gate test domains)
            if current.get("post_gate_contract_sweep") is None:
                errors.append("L4_STRUCTURAL missing post_gate_contract_sweep in tracker note")
            else:
                sweep_cmd = current["post_gate_contract_sweep"]
                if not any(d in sweep_cmd for d in NON_GATE_TEST_DOMAINS):
                    errors.append(
                        "L4_STRUCTURAL post_gate_contract_sweep must reference at least one "
                        "non-gate test domain (tests/engine/, tests/structural/, etc.). "
                        f"Got: {sweep_cmd!r}"
                    )

        # Debt-removal integrity checks (marker-touch path):
        # If a structural wave touches @host_* markers in runtime files,
        # it must prove strict debt reduction without category movement.
        if diff_text and runtime_files:
            _, _, added_total, removed_total = compute_runtime_host_marker_delta(
                diff_text,
                runtime_files,
            )
            marker_touched = (added_total + removed_total) > 0
            # Detect cross-file marker moves: if every removed marker has a
            # same-category counterpart in a DIFFERENT file, the markers were
            # moved (not changed) and strict-reduction rules don't apply.
            is_pure_cross_file_move = False
            marker_touch_override = None  # initialized here; assigned in marker-touched block
            if marker_touched and added_total == removed_total:
                removed_events_pre, added_events_pre = collect_runtime_marker_events(
                    diff_text, runtime_files,
                )
                if removed_events_pre and all(
                    _marker_event_has_added_counterpart(ev, added_events_pre)
                    and any(
                        str(a["category"]) == str(ev["category"])
                        and str(a["file"]) != str(ev["file"])
                        for a in added_events_pre
                    )
                    for ev in removed_events_pre
                ):
                    is_pure_cross_file_move = True
            if marker_touched and not is_pure_cross_file_move:
                # FOUNDER_OVERRIDE bypass for marker-touch rules 19/20.
                # Structural waves that add *new* irreducible bootstrap host
                # operations (not reducing existing debt) can use FOUNDER_OVERRIDE
                # to bypass strict-decrease and baseline-split requirements.
                marker_touch_override = None
                if notes and override_wave_bound:
                    oid = notes[0].get("founder_override")
                    if oid:
                        marker_touch_override = oid

                if marker_touch_override:
                    print(
                        f"  FOUNDER_OVERRIDE:{marker_touch_override} active — "
                        f"bypassing marker-touch rules 19/20 "
                        f"(added={added_total}, removed={removed_total})"
                    )
                else:
                    if _touches_host_semantics_baseline(changed_files):
                        errors.append(
                            "L4_STRUCTURAL with runtime @host_* marker changes cannot modify "
                            "tools/checks/host_semantics_baseline.json in the same wave. "
                            "Baseline ratchet updates must be a separate MAINTENANCE wave."
                        )

                    if removed_total <= 0:
                        errors.append(
                            "L4_STRUCTURAL touched runtime @host_* markers but removed none. "
                            "Debt movement/addition without removals is forbidden."
                        )

                    ratchet_json, probe_errors = probe_host_semantics_ratchet()
                    if probe_errors:
                        errors.extend(
                            "FAIL-CLOSED debt-removal integrity: " + e for e in probe_errors
                        )
                    elif ratchet_json is not None:
                        try:
                            baseline_total, current_total, increases = summarize_host_semantics_delta(
                                ratchet_json
                            )
                        except ValueError as exc:
                            errors.append(
                                "FAIL-CLOSED debt-removal integrity: "
                                f"invalid host-semantics probe data ({exc})"
                            )
                        else:
                            if current_total >= baseline_total:
                                errors.append(
                                    "L4_STRUCTURAL runtime @host_* marker change requires strict "
                                    f"debt reduction. Current total={current_total}, "
                                    f"baseline total={baseline_total}."
                                )
                            for inc in increases:
                                errors.append(
                                    "L4_STRUCTURAL runtime @host_* marker change cannot increase "
                                    "any host category (no debt-category movement). "
                                    f"Found increase: {inc['substrate']}.{inc['category']} "
                                    f"{inc['baseline']}→{inc['current']} (+{inc['delta']})."
                                )

            if marker_touched:
                # Rule A4 semantic-removal proof:
                # marker removal must correspond to construct removal in function body.
                # FOUNDER_OVERRIDE bypass: boundary reclassification waves may remove
                # markers from functions that retain loop constructs if the functions
                # are provably off the kernel execution path (gate tests required).
                if marker_touch_override:
                    print(
                        f"  FOUNDER_OVERRIDE:{marker_touch_override} active — "
                        f"bypassing Rule A4 semantic-removal proof "
                        f"(boundary reclassification with gate tests)"
                    )
                else:
                    removed_events, added_events = collect_runtime_marker_events(
                        diff_text,
                        runtime_files,
                    )
                    semantic_categories = {"host_recursion", "host_iteration", "host_builtin"}
                    function_cache: dict[str, list[dict[str, object]]] = {}
                    checked_pairs: set[tuple[str, str, str]] = set()

                    for ev in removed_events:
                        category = str(ev["category"])
                        if category not in semantic_categories:
                            continue
                        if _marker_event_has_added_counterpart(ev, added_events):
                            continue  # marker text rewrite, not semantic removal

                        filepath = str(ev["file"])
                        if filepath not in function_cache:
                            path = Path(filepath)
                            if not path.exists():
                                errors.append(
                                    "FAIL-CLOSED semantic removal proof: changed runtime file "
                                    f"missing on disk: {filepath}"
                                )
                                function_cache[filepath] = []
                            else:
                                try:
                                    source = path.read_text(encoding="utf-8")
                                except OSError as exc:
                                    errors.append(
                                        "FAIL-CLOSED semantic removal proof: cannot read runtime file "
                                        f"{filepath}: {exc}"
                                    )
                                    function_cache[filepath] = []
                                else:
                                    function_cache[filepath] = _extract_functions_for_file(filepath, source)

                        functions = function_cache.get(filepath, [])
                        if not functions:
                            continue

                        fn = _find_function_for_marker_anchor(functions, int(ev["anchor_line"]))
                        if fn is None:
                            # Marker likely from non-function summary comments (e.g., debt summary blocks).
                            continue

                        fn_name = str(fn["name"])
                        pair_key = (filepath, fn_name, category)
                        if pair_key in checked_pairs:
                            continue
                        checked_pairs.add(pair_key)

                        # If marker still present for this function in current file, skip.
                        fn_markers = fn.get("markers", set())
                        if isinstance(fn_markers, set) and category in fn_markers:
                            continue

                        if category == "host_recursion" and _function_has_self_call(fn):
                            errors.append(
                                "Rule A4.1 violation: @host_recursion removed but function still "
                                f"contains self-call ({filepath}:{fn_name})."
                            )
                        elif category == "host_iteration" and _function_has_loop_construct(fn):
                            errors.append(
                                "Rule A4.2 violation: @host_iteration removed but function still "
                                f"contains loop constructs ({filepath}:{fn_name})."
                            )
                        elif category == "host_builtin" and _function_has_host_builtin_calls(fn):
                            errors.append(
                                "Rule A4.3/A4.4 violation: @host_builtin removed but function still "
                                f"contains host builtin calls ({filepath}:{fn_name})."
                            )

    # --- L4_ENABLER ---
    elif wave_class == "L4_ENABLER":
        if runtime_files:
            errors.append(
                f"L4_ENABLER wave touches runtime/substrate files (forbidden). "
                f"Runtime files: {runtime_files[:5]}. Use L4_STRUCTURAL instead."
            )
        if notes:
            current = notes[0]
            if current["gate"] is None:
                errors.append("L4_ENABLER missing target_gate_id in tracker note")
            if current["evidence_command"] is None:
                errors.append("L4_ENABLER missing evidence_command in tracker note")
            if current["evidence_delta"] is None:
                errors.append("L4_ENABLER missing evidence_delta in tracker note")
            if current.get("host_semantics_delta_before") is not None or current.get("host_semantics_delta_after") is not None:
                errors.append(
                    "L4_ENABLER cannot claim host_semantics_delta without runtime file changes."
                )

    # --- MAINTENANCE ---
    elif wave_class == "MAINTENANCE":
        if runtime_files:
            errors.append(
                f"MAINTENANCE wave touches runtime/substrate files: "
                f"{runtime_files[:5]}"
            )

    # --- Cross-class checks using notes ---
    if notes:
        current = notes[0]

        # Strict gate ID validation
        if current["gate"] and not GATE_ID_RE.match(current["gate"]):
            errors.append(
                f"Invalid target_gate_id: '{current['gate']}'. Must match G1-G8."
            )

        # Legacy alias lock
        alias_ok, alias_errors = check_legacy_alias_in_new_notes(notes)
        if not alias_ok:
            errors.extend(alias_errors)

        # Consecutive maintenance cadence rule
        if wave_class == "MAINTENANCE":
            cm_ok, cm_errors = check_consecutive_maintenance(notes)
            if not cm_ok:
                errors.extend(cm_errors)

        # MAINTENANCE metadata
        if wave_class == "MAINTENANCE":
            meta_ok, meta_errors = check_maintenance_metadata(notes)
            if not meta_ok:
                errors.extend(meta_errors)

        # Primary blocker classification (all classes)
        blocker = current.get("primary_blocker_class")
        if blocker is None:
            errors.append(
                "Missing primary_blocker_class in tracker note "
                "(required: DESIGN, INTEGRATION, or PERFORMANCE)"
            )
        elif blocker not in VALID_BLOCKER_CLASSES:
            errors.append(
                f"Invalid primary_blocker_class: '{blocker}'. "
                f"Must be one of: {sorted(VALID_BLOCKER_CLASSES)}"
            )

        # Primary invariant ID (all classes)
        invariant_id = current.get("primary_invariant_id")
        if invariant_id is None:
            errors.append(
                "Missing primary_invariant_id in tracker note "
                "(required: one of " + ", ".join(sorted(VALID_INVARIANT_IDS)) + ")"
            )
        elif invariant_id not in VALID_INVARIANT_IDS:
            errors.append(
                f"Invalid primary_invariant_id: '{invariant_id}'. "
                f"Must be one of: {sorted(VALID_INVARIANT_IDS)}"
            )

        # Workload target (STRUCTURAL only): bind wave to RCX semantic destination.
        if wave_class == "L4_STRUCTURAL":
            workload_target = current.get("workload_target")
            if workload_target is None:
                errors.append(
                    "L4_STRUCTURAL missing workload_target in tracker note "
                    "(required for RCX-first semantic destination binding)"
                )
            elif workload_target not in VALID_WORKLOAD_TARGETS:
                errors.append(
                    f"Invalid workload_target: '{workload_target}'. "
                    f"Must be one of: {sorted(VALID_WORKLOAD_TARGETS)}"
                )
            else:
                # Proof binding: workload target evidence files
                pb_errors = _check_proof_binding(
                    workload_target,
                    current.get("evidence_command"),
                    changed_files,
                )
                errors.extend(pb_errors)

        # Progress proof (required for STRUCTURAL + ENABLER)
        if wave_class in ("L4_STRUCTURAL", "L4_ENABLER"):
            pp_before = current.get("progress_proof_before")
            pp_after = current.get("progress_proof_after")
            if pp_before is None:
                errors.append(
                    f"{wave_class} missing progress_proof_before in tracker note"
                )
            if pp_after is None:
                errors.append(
                    f"{wave_class} missing progress_proof_after in tracker note"
                )
            if pp_before and pp_after and pp_before == pp_after:
                errors.append(
                    f"{wave_class} progress_proof_before and progress_proof_after "
                    f"must not be identical (anti-theater)"
                )

        # Indicator artifact and collection command (all classes)
        indicator_ref = current.get("indicator_artifact_ref")
        indicator_cmd = current.get("indicator_collection_command")
        if indicator_ref is None:
            errors.append("Missing indicator_artifact_ref in tracker note")
        if indicator_cmd is None:
            errors.append("Missing indicator_collection_command in tracker note")
        elif CANONICAL_COLLECTOR_PATH not in indicator_cmd:
            errors.append(
                f"indicator_collection_command must reference canonical collector "
                f"'{CANONICAL_COLLECTOR_PATH}'. Got: {indicator_cmd!r}"
            )

        # Bootstrap endgame policy (all classes)
        policy = current.get("bootstrap_endgame_policy")
        if policy is None:
            errors.append(
                "Missing bootstrap_endgame_policy in tracker note "
                f"(required: {CANONICAL_BOOTSTRAP_POLICY})"
            )
        elif policy != CANONICAL_BOOTSTRAP_POLICY:
            errors.append(
                f"Invalid bootstrap_endgame_policy: '{policy}'. "
                f"Must be exactly: {CANONICAL_BOOTSTRAP_POLICY}"
            )

        # Boot0 track ID (all classes)
        boot0_track = current.get("boot0_track_id")
        if boot0_track is None:
            errors.append(
                "Missing boot0_track_id in tracker note "
                f"(required: one of {sorted(VALID_BOOT0_TRACK_IDS)})"
            )
        elif boot0_track not in VALID_BOOT0_TRACK_IDS:
            errors.append(
                f"Invalid boot0_track_id: '{boot0_track}'. "
                f"Must be one of: {sorted(VALID_BOOT0_TRACK_IDS)}"
            )

        # Boot0 progress state (all classes)
        boot0_progress = current.get("boot0_progress_state")
        if boot0_progress is None:
            errors.append(
                "Missing boot0_progress_state in tracker note "
                f"(required: one of {sorted(VALID_BOOT0_PROGRESS_STATES)})"
            )
        elif boot0_progress not in VALID_BOOT0_PROGRESS_STATES:
            errors.append(
                f"Invalid boot0_progress_state: '{boot0_progress}'. "
                f"Must be one of: {sorted(VALID_BOOT0_PROGRESS_STATES)}"
            )

        # Non-structural adjacency cap
        adj_ok, adj_errors = check_non_structural_adjacency(notes)
        if not adj_ok:
            errors.extend(adj_errors)

        # Rolling structural quota
        rw_ok, rw_errors = check_rolling_window(notes)
        if not rw_ok:
            errors.extend(rw_errors)

        # NO_OP throttle
        nt_ok, nt_errors = check_noop_throttle(notes)
        if not nt_ok:
            errors.extend(nt_errors)

        # Founder override replay protection
        or_ok, or_errors = check_founder_override_replay(notes)
        if not or_ok:
            errors.extend(or_errors)

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _derive_old_ref_from_range(git_range: str) -> str:
    """Derive the diff preimage ref from a git range string.

    --range A...B (3 dots, symmetric) => merge-base(A, B)
    --range A..B  (2 dots, linear)    => A

    Fail-closed: if merge-base cannot be resolved, raises ValueError.
    Empty/whitespace-only input raises ValueError (fail-closed).
    """
    if not git_range or not git_range.strip():
        raise ValueError("Empty git range is invalid")
    git_range = git_range.strip()
    if "..." in git_range:
        # Symmetric diff: A...B => preimage is merge-base(A, B)
        parts = git_range.split("...", 1)
        left, right = parts[0] or "HEAD", parts[1] or "HEAD"
        try:
            result = subprocess.run(
                ["git", "merge-base", left, right],
                capture_output=True, text=True, check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise ValueError(
                f"Cannot resolve merge-base({left}, {right}) "
                f"for range '{git_range}': {e}"
            ) from e
    elif ".." in git_range:
        # Linear diff: A..B => preimage is A (empty left => HEAD)
        left = git_range.split("..", 1)[0]
        return left or "HEAD"
    else:
        # Single ref (e.g. "HEAD~1") — preimage IS that ref
        return git_range


def validate_indicator_with_ratchet(
    indicator_ref: str,
    changed_files: list[str],
) -> tuple[bool, list[str]]:
    """Validate indicator artifact using ratchet-derived host-semantics delta.

    Derives expected net_host_semantic_delta from probe_host_semantics_ratchet()
    (marker footprint delta), not raw executable line diff.
    Fail-closed on probe errors.
    """
    errors: list[str] = []
    passed = True

    if indicator_ref not in changed_files:
        passed = False
        errors.append(
            f"indicator_artifact_ref '{indicator_ref}' not in changed files. "
            f"Artifact must be committed as part of the wave."
        )

    expected_net_delta = None
    ratchet_json, ratchet_errors = probe_host_semantics_ratchet()
    if ratchet_errors:
        passed = False
        errors.extend(
            "FAIL-CLOSED indicator delta: " + e for e in ratchet_errors
        )
    elif ratchet_json is not None:
        try:
            baseline_total, current_total, _ = summarize_host_semantics_delta(
                ratchet_json
            )
            expected_net_delta = current_total - baseline_total
        except ValueError as exc:
            passed = False
            errors.append(
                f"FAIL-CLOSED indicator delta: invalid ratchet data ({exc})"
            )

    art_ok, art_errors = validate_indicator_artifact_json(
        indicator_ref,
        expected_net_host_delta=expected_net_delta,
    )
    if not art_ok:
        passed = False
        errors.extend(art_errors)

    return passed, errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce L4 Execution Contract v2 wave classification"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="Check staged files")
    group.add_argument("--range", type=str, help="Git range (e.g., origin/dev...HEAD)")
    group.add_argument("--files", nargs="+", help="Explicit file list")
    parser.add_argument(
        "--wave-class", type=str,
        choices=sorted(VALID_WAVE_CLASSES),
        help="Override wave class (for testing). If not set, auto-detects from TASKS.md."
    )
    parser.add_argument(
        "--wave-id", type=str,
        help="Bind to specific wave_id in tracker notes (not global latest)."
    )
    args = parser.parse_args()

    # Get changed files
    if args.staged:
        changed_files = get_changed_files_staged()
        diff_text = get_diff_staged() if changed_files else None
    elif args.range:
        changed_files = get_changed_files_range(args.range)
        diff_text = get_diff_range(args.range) if changed_files else None
    else:
        changed_files = filter_to_tracked_files(args.files or [])
        diff_text = None

    # Empty-scope policy — applies AFTER untracked filtering
    if not changed_files:
        if args.wave_id:
            # wave-id provided but no tracked files to verify — cannot certify
            scope_desc = (
                f"--files (all untracked)" if args.files
                else f"--range={args.range!r}" if args.range
                else "--staged" if args.staged
                else "(no scope)"
            )
            print(f"ERROR: --wave-id '{args.wave_id}' provided but no tracked files "
                  f"found ({scope_desc}). "
                  f"Cannot verify wave against empty change set.")
            return 1
        if args.files:
            print("No tracked files after filtering — skipping enforcement.")
            return 0
        if args.range:
            print(f"No changed files in range '{args.range}' — skipping enforcement.")
            return 0
        if args.staged:
            print("No staged files — skipping enforcement.")
            return 0
        # Truly unknown scope — fall back to HEAD~1...HEAD
        print("WARNING: Empty scope detected. Falling back to HEAD~1...HEAD.")
        try:
            changed_files = get_changed_files_range("HEAD~1...HEAD")
            diff_text = get_diff_range("HEAD~1...HEAD") if changed_files else None
        except subprocess.CalledProcessError:
            print("WARNING: HEAD~1...HEAD fallback failed (new repo?). "
                  "Cannot verify — treating as non-blocking.")
            return 0
        if not changed_files:
            print("No changed files even after fallback — skipping enforcement.")
            return 0

    # Parse tracker notes
    tasks_path = Path("TASKS.md")
    all_notes: list[dict] = []
    if tasks_path.exists():
        text = tasks_path.read_text(encoding="utf-8")
        all_notes = parse_tracker_notes(text)

    # Wave binding: select note for this wave_id
    bound_note: dict | None = None
    if args.wave_id:
        for n in all_notes:
            if n["wave_id"] == args.wave_id:
                bound_note = n
                break
        if bound_note is None:
            print(f"ERROR: --wave-id '{args.wave_id}' not found in any tracker sync note.")
            print(f"  Available wave_ids: {[n['wave_id'] for n in all_notes[:10]]}")
            return 1

    # Build notes list with bound note at position 0 (for cross-class checks)
    notes: list[dict] | None = None
    if bound_note:
        # Put the bound note first, keep the rest for window checks
        notes = [bound_note] + [n for n in all_notes if n["wave_id"] != args.wave_id]
    elif all_notes:
        notes = all_notes

    # Determine wave class
    # Only auto-detect from notes if the diff actually adds/edits a tracker
    # sync note (not merely touches TASKS.md) or --wave-id was explicitly given.
    # Planning commits that add NEXT/VECTOR items without tracker notes must
    # not inherit the latest wave's class — that causes false positives.
    tracker_note_touched = False
    if "TASKS.md" in changed_files:
        # Scope check to TASKS.md diff only — the full diff_text includes all
        # files and would false-positive on code that mentions the string
        # "Tracker sync note" (including this very file).
        try:
            if args.staged:
                tasks_diff = subprocess.run(
                    ["git", "diff", "--cached", "-U0", "--", "TASKS.md"],
                    capture_output=True, text=True, check=True,
                ).stdout
            elif args.range:
                tasks_diff = subprocess.run(
                    ["git", "diff", "-U0", args.range, "--", "TASKS.md"],
                    capture_output=True, text=True, check=True,
                ).stdout
            else:
                tasks_diff = ""
        except subprocess.CalledProcessError:
            tasks_diff = ""
        for line in tasks_diff.splitlines():
            if line.startswith("+") and "Tracker sync note" in line:
                tracker_note_touched = True
                break
    wave_class = args.wave_class
    if not wave_class and notes and (bound_note or tracker_note_touched):
        wave_class = notes[0]["wave_class"] if notes else None

    runtime_count = sum(1 for f in changed_files if is_runtime_file(f))

    # Derive old_ref for preimage resolution (P1 #1 fix).
    # Context-driven: --staged => HEAD, --range => parsed, --files => HEAD.
    if args.staged:
        old_ref = "HEAD"
    elif args.range:
        try:
            old_ref = _derive_old_ref_from_range(args.range)
        except ValueError as e:
            print(f"ERROR: {e}")
            return 1
    else:
        old_ref = "HEAD"  # --files mode, no diff context

    # Override wave binding (P1 #2 fix).
    # Stale top-note overrides are rejected unless --wave-id resolved.
    override_wave_bound = bound_note is not None

    print(f"Wave class: {wave_class or '(none)'}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Runtime files: {runtime_count}")

    passed, errors = enforce(
        wave_class, changed_files, diff_text, notes,
        old_ref=old_ref, override_wave_bound=override_wave_bound,
    )

    # Indicator artifact file-level validation (CLI only)
    # Only validate when wave_class is active (skip for non-wave PRs)
    if notes and wave_class:
        indicator_ref = notes[0].get("indicator_artifact_ref")
        if indicator_ref:
            ind_ok, ind_errors = validate_indicator_with_ratchet(
                indicator_ref, changed_files,
            )
            if not ind_ok:
                passed = False
                errors.extend(ind_errors)

    if passed:
        print(f"✅ L4 Execution Contract v2: {wave_class or 'no-class'} compliant")
        return 0
    else:
        print(f"❌ L4 Execution Contract v2 VIOLATION ({wave_class or 'no-class'}):")
        for e in errors:
            print(f"   - {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
