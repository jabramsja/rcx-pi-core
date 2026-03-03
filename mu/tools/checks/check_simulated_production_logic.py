#!/usr/bin/env python3
"""Check for simulated production logic in JS boundary tests (RT2+RT3).

Detects inline JS code within Python test files that recreates production
helper functions instead of invoking production modules via require().

Scans: mu/tests/l4_gates/**/*.py, tests/l4_gates/**/*.py (deduplicated)

Suspicious patterns (within JS snippets — triple-quoted, concatenated, f-string):
  - function validateSeedStructure  — recreating production helper
  - function loadVerifiedSeed       — recreating production helper
  - const/let validateSeedStructure = (...) => — arrow function alias
  - const/let loadVerifiedSeed = (...) =>      — arrow function alias
  - Manual projection guard loop: for (...projections.length...) with
    proj === null || typeof proj !== 'object' — recreating production guard

Rule:
  FAIL if simulated helper logic appears in a JS snippet that does NOT
  also invoke AND CALL production module entry points via require('./mu/host/js/...').
  A bare require() without a call expression using the imported symbol is NOT sufficient.

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

# RT3: Scan both paths; dedup by resolved path handles hardlinks/symlinks
SCAN_DIRS = [
    REPO_ROOT / "mu" / "tests" / "l4_gates",
    REPO_ROOT / "tests" / "l4_gates",
]

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Suspicious inline JS function definitions (RT2 originals + RT3 arrow aliases)
SIMULATED_FUNCTION_PATTERNS = [
    (re.compile(r'function\s+validateSeedStructure\b'),
     'inline function validateSeedStructure'),
    (re.compile(r'function\s+loadVerifiedSeed\b'),
     'inline function loadVerifiedSeed'),
    (re.compile(r'(?:const|let)\s+validateSeedStructure\s*=\s*\(.*?\)\s*=>'),
     'inline arrow function validateSeedStructure'),
    (re.compile(r'(?:const|let)\s+loadVerifiedSeed\s*=\s*\(.*?\)\s*=>'),
     'inline arrow function loadVerifiedSeed'),
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

# Production binding: require('./mu/host/js/...')
PRODUCTION_REQUIRE_RE = re.compile(r"""require\s*\(\s*['"]\.\/mu\/host\/js\/""")

# RT3: Production call expression — symbol imported via require must be called.
# Matches: loadVerifiedSeed( or seed_loader.loadVerifiedSeed( etc.
# We extract the symbol name from the require and check for its usage as a call.
PRODUCTION_CALL_PATTERNS = [
    # Destructured: const { loadVerifiedSeed } = require(...)  →  loadVerifiedSeed(
    re.compile(r'(?:loadVerifiedSeed|validateSeedStructure|_ensureBoundaryOps)\s*\('),
    # Module-level: const mod = require(...)  →  mod.something(
    re.compile(r'(?:seed_loader|pipeline|kernel)\s*\.\s*\w+\s*\('),
]

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
    """Extract string blocks that look like JS snippets.

    Detects:
    - Triple-quoted blocks (existing)
    - Concatenated single/double-quoted Python strings used for node -e
    - f-strings used for node -e

    Returns list of (start_pos, end_pos, block_text).
    """
    blocks = []

    # 1) Triple-quoted blocks
    for m in re.finditer(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', content, re.DOTALL):
        text = m.group(1) if m.group(1) is not None else m.group(2)
        # Only consider blocks that look like JS (have JS keywords)
        if re.search(r'\b(?:function|const|let|var|require)\b', text):
            blocks.append((m.start(), m.end(), text))

    # 2) Concatenated string blocks: lines of 'string' + 'string' or "string"
    # Look for patterns like: js_code = (\n  'line1\n'\n  'line2\n'\n)
    # or: subprocess.run([..., '-e', 'line1' + 'line2'])
    # Strategy: find node -e or similar invocations with concatenated strings
    for m in re.finditer(
        r"(?:node\s.*?-e['\",\s]+|js_code\s*=\s*\(?\s*\n)"
        r"((?:\s*['\"].*?['\"]\s*\+?\s*\n?)+)",
        content,
    ):
        # Combine the concatenated string parts
        raw = m.group(1)
        combined = ''
        for part in re.finditer(r"['\"](.+?)['\"]", raw):
            combined += part.group(1) + '\n'
        if re.search(r'\b(?:function|const|let|var|require)\b', combined):
            blocks.append((m.start(), m.end(), combined))

    # 3) f-strings with JS content (f""" or f''')
    for m in re.finditer(r'f"""(.*?)"""|f\'\'\'(.*?)\'\'\'', content, re.DOTALL):
        text = m.group(1) if m.group(1) is not None else m.group(2)
        if re.search(r'\b(?:function|const|let|var|require)\b', text):
            # Only add if not already captured by triple-quote pass
            already = any(m.start() == b[0] for b in blocks)
            if not already:
                blocks.append((m.start(), m.end(), text))

    return blocks


def line_number_at(content: str, pos: int) -> int:
    """Return 1-based line number for character position."""
    return content[:pos].count('\n') + 1


def _has_production_call(block_text: str) -> bool:
    """Check if block has both a production require AND a call using the import.

    A call expression is distinguished from a function definition:
    - `loadVerifiedSeed('test.json')` is a CALL (good)
    - `function loadVerifiedSeed(name)` is a DEFINITION (not a call)
    - `const loadVerifiedSeed = (name) =>` is a DEFINITION (not a call)
    """
    if not PRODUCTION_REQUIRE_RE.search(block_text):
        return False
    # Check for call expressions, excluding function definitions
    for line in block_text.split('\n'):
        stripped = line.strip()
        for p in PRODUCTION_CALL_PATTERNS:
            if not p.search(stripped):
                continue
            # Exclude function definitions (function foo( or const foo = (...) =>)
            if re.match(r'\s*function\s+\w+\s*\(', stripped):
                continue
            if re.match(r'\s*(?:const|let|var)\s+\w+\s*=\s*\(.*?\)\s*=>', stripped):
                continue
            return True
    return False


def _has_theater_ok_within_5_lines(content: str, block_start: int) -> bool:
    """Check for THEATER_OK marker within 5 lines before block_start."""
    block_line = line_number_at(content, block_start)
    # Search the 5 lines before the block
    search_start_line = max(1, block_line - 5)
    lines = content.split('\n')
    for i in range(search_start_line - 1, block_line - 1):
        if i < len(lines) and THEATER_OK_RE.search(lines[i]):
            return True
    return False


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

    # Extract all blocks that look like JS
    blocks = extract_js_snippets(content)

    for block_start, block_end, block_text in blocks:
        # RT3: Require production require + call (not just require)
        has_production_binding = _has_production_call(block_text)

        # RT3/Codex P2: Use line-based proximity (5 lines) not char-based
        has_theater_ok = _has_theater_ok_within_5_lines(content, block_start)

        # Check each suspicious function pattern
        for pattern, desc in SIMULATED_FUNCTION_PATTERNS:
            if pattern.search(block_text):
                if has_production_binding or has_theater_ok:
                    continue
                # RT3: If snippet has require but no call, flag specifically
                if PRODUCTION_REQUIRE_RE.search(block_text):
                    desc = f'{desc} (require present but never called)'
                violations.append({
                    'line': line_number_at(content, block_start),
                    'desc': desc,
                    'snippet_preview': block_text[:100].strip(),
                })

        # Check guard loop pattern
        if GUARD_LOOP_RE.search(block_text):
            if has_production_binding or has_theater_ok:
                continue
            desc = 'inline projection guard loop (simulated production logic)'
            if PRODUCTION_REQUIRE_RE.search(block_text):
                desc = f'{desc} (require present but never called)'
            violations.append({
                'line': line_number_at(content, block_start),
                'desc': desc,
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
        seen_inodes: set[int] = set()
        seen_dirs: set[Path] = set()
        for scan_dir in SCAN_DIRS:
            resolved = scan_dir.resolve()
            if resolved in seen_dirs:
                continue
            seen_dirs.add(resolved)
            if resolved.is_dir():
                for f in sorted(resolved.glob('**/*.py')):
                    # RT3: Deduplicate by inode (handles hardlinks)
                    try:
                        inode = f.stat().st_ino
                    except OSError:
                        continue
                    if inode in seen_inodes:
                        continue
                    seen_inodes.add(inode)
                    files.append(f)

    total_violations = 0
    scanned = 0

    print("=== Simulated Production Logic Check (RT2+RT3) ===")
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
        print("Fix: Replace inline JS helpers with require('./mu/host/js/...') + call")
        print("     or add # THEATER_OK: source-lock-only <reason> if source-lock test.")
        sys.exit(1)
    else:
        print("PASS: No simulated production logic found.")


if __name__ == '__main__':
    main()
