#!/usr/bin/env python3
"""Check for simulated production logic in JS boundary tests (RT2).

Detects inline JS code within Python test files that recreates production
helper functions instead of invoking production modules via require().

Scans: mu/tests/l4_gates/**/*.py

Suspicious patterns (within triple-quoted JS snippets):
  - function validateSeedStructure  — recreating production helper
  - function loadVerifiedSeed       — recreating production helper
  - Manual projection guard loop: for (...projections.length...) with
    proj === null || typeof proj !== 'object' — recreating production guard

Rule:
  FAIL if simulated helper logic appears in a JS snippet that does NOT
  also invoke production module entry points via require('./mu/host/js/...').

Exception marker (on a line within 5 lines before the snippet):
  # THEATER_OK: source-lock-only <reason text>

Usage:
    python3 tools/checks/check_simulated_production_logic.py
    python3 tools/checks/check_simulated_production_logic.py --check-file <path>
"""
from __future__ import annotations

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

SCAN_DIRS = [
    REPO_ROOT / "mu" / "tests" / "l4_gates",
]

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Suspicious inline JS function definitions
SIMULATED_FUNCTION_PATTERNS = [
    (re.compile(r'function\s+validateSeedStructure\b'),
     'inline function validateSeedStructure'),
    (re.compile(r'function\s+loadVerifiedSeed\b'),
     'inline function loadVerifiedSeed'),
]

# Manual projection guard loop (multi-line pattern within a JS snippet).
# Matches: for (...projections.length...) { ... proj === null || typeof proj !== 'object'
GUARD_LOOP_RE = re.compile(
    r'for\s*\(.*?projections\s*\.\s*length'   # for (...projections.length...)
    r'.*?'                                      # anything between
    r'(?:proj|p)\s*===\s*null\s*\|\|'          # proj === null ||
    r'\s*typeof\s+(?:proj|p)\s*!==\s*'         # typeof proj !==
    r"""['"]\s*object\s*['"]""",               # 'object'
    re.DOTALL,
)

# Production binding (exempts a snippet from simulation detection)
PRODUCTION_BINDING_RE = re.compile(r"""require\s*\(\s*['"]\.\/mu\/host\/js\/""")

# Exception marker: must have reason text on the SAME LINE after the marker
# Uses [ \t] (horizontal whitespace) to avoid matching across newlines
THEATER_OK_RE = re.compile(r'#\s*THEATER_OK:\s*source-lock-only[ \t]+\S')
THEATER_OK_MALFORMED_RE = re.compile(
    r'#\s*THEATER_OK:\s*source-lock-only[ \t]*$', re.MULTILINE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_js_snippets(content: str) -> list[tuple[int, int, str]]:
    """Extract triple-quoted string blocks that look like JS snippets.

    Returns list of (start_pos, end_pos, block_text).
    """
    blocks = []
    for m in re.finditer(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', content, re.DOTALL):
        text = m.group(1) if m.group(1) is not None else m.group(2)
        # Only consider blocks that look like JS (have JS keywords)
        if re.search(r'\b(?:function|const|let|var|require)\b', text):
            blocks.append((m.start(), m.end(), text))
    return blocks


def line_number_at(content: str, pos: int) -> int:
    """Return 1-based line number for character position."""
    return content[:pos].count('\n') + 1


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def check_file(filepath: Path) -> list[dict]:
    """Check a single file for simulated production logic.

    Returns list of violation dicts: {line, desc, snippet_preview}
    """
    content = filepath.read_text()
    violations = []

    # Check for malformed THEATER_OK markers (missing reason text)
    for m in THEATER_OK_MALFORMED_RE.finditer(content):
        line_start = content.rfind('\n', 0, m.start()) + 1
        line_end = content.find('\n', m.end())
        if line_end == -1:
            line_end = len(content)
        line_text = content[line_start:line_end].strip()
        if not THEATER_OK_RE.search(line_text):
            violations.append({
                'line': line_number_at(content, m.start()),
                'desc': 'THEATER_OK marker missing reason text',
                'snippet_preview': line_text[:80],
            })

    # Extract all triple-quoted blocks that look like JS
    blocks = extract_js_snippets(content)

    for block_start, block_end, block_text in blocks:
        # Check for production binding in this block
        has_production_binding = bool(PRODUCTION_BINDING_RE.search(block_text))

        # Check for THEATER_OK near the block start (within 200 chars before)
        context_before_start = max(0, block_start - 200)
        context_before = content[context_before_start:block_start]
        has_theater_ok = bool(THEATER_OK_RE.search(context_before))

        # Check each suspicious function pattern
        for pattern, desc in SIMULATED_FUNCTION_PATTERNS:
            if pattern.search(block_text):
                if has_production_binding or has_theater_ok:
                    continue
                violations.append({
                    'line': line_number_at(content, block_start),
                    'desc': desc,
                    'snippet_preview': block_text[:100].strip(),
                })

        # Check guard loop pattern
        if GUARD_LOOP_RE.search(block_text):
            if has_production_binding or has_theater_ok:
                continue
            violations.append({
                'line': line_number_at(content, block_start),
                'desc': 'inline projection guard loop (simulated production logic)',
                'snippet_preview': block_text[:100].strip(),
            })

    return violations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    # Optional: check specific file
    if '--check-file' in args:
        idx = args.index('--check-file')
        if idx + 1 >= len(args):
            print("ERROR: --check-file requires a path argument", file=sys.stderr)
            sys.exit(2)
        files = [Path(args[idx + 1])]
    else:
        files = []
        seen_dirs: set[Path] = set()
        for scan_dir in SCAN_DIRS:
            resolved = scan_dir.resolve()
            if resolved in seen_dirs:
                continue
            seen_dirs.add(resolved)
            if resolved.is_dir():
                files.extend(sorted(resolved.glob('**/*.py')))

    total_violations = 0
    scanned = 0

    print("=== Simulated Production Logic Check (RT2) ===")
    print()

    for filepath in files:
        scanned += 1
        file_violations = check_file(filepath)
        if file_violations:
            try:
                rel = filepath.relative_to(REPO_ROOT)
            except ValueError:
                rel = filepath
            for v in file_violations:
                print(f"  FAIL: {rel}:{v['line']}: {v['desc']}")
                print(f"        {v['snippet_preview']}")
                print()
            total_violations += len(file_violations)

    print(f"Scanned: {scanned} file(s)")

    if total_violations > 0:
        print(f"\nFAIL: {total_violations} simulated production logic violation(s) found.")
        print("Fix: Replace inline JS helpers with require('./mu/host/js/...') calls")
        print("     or add # THEATER_OK: source-lock-only <reason> if source-lock test.")
        sys.exit(1)
    else:
        print("PASS: No simulated production logic found.")


if __name__ == '__main__':
    main()
