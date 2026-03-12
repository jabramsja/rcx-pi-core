"""
L4 gate test: Wave 8 — normalize.js docstring accuracy.

Proves that the dict normalization docstring in normalize.js matches
the actual kv-pair shape produced by the code (line 216).

The docstring must show:
  Dict: {"a": 1} -> {"_type": "dict", "head": {"head": "a", "tail": {"head": 1, "tail": null}}, "tail": null}

This matches the code:
  const kv = { head: k, tail: { head: normalize(value[k], _depth + 1), tail: null } };
"""
import re
from pathlib import Path

NORMALIZE_JS = Path(__file__).resolve().parents[2] / "host" / "js" / "core" / "normalize.js"


def test_normalize_js_dict_docstring_matches_code():
    """Docstring dict example must show nested {head: value, tail: null} kv-pair tail."""
    source = NORMALIZE_JS.read_text()

    # Find the dict docstring line containing the Dict example
    for line in source.splitlines():
        if "Dict:" in line and '"_type": "dict"' in line:
            # Must contain the nested kv-pair structure, not bare tail
            assert '{"head": 1, "tail": null}' in line, (
                f"Dict docstring shows wrong kv-pair tail shape: {line!r}. "
                "Expected nested kv-pair tail matching code at line 216."
            )
            return

    raise AssertionError("Dict docstring example not found in normalize.js")


def test_normalize_js_code_produces_nested_kv_pair():
    """Code line building kv-pairs must use { head: k, tail: { head: value, tail: null } }."""
    source = NORMALIZE_JS.read_text()

    # Find the kv construction line
    kv_match = re.search(
        r'const kv\s*=\s*\{\s*head:\s*k,\s*tail:\s*\{\s*head:\s*normalize\(value\[k\]',
        source,
    )
    assert kv_match is not None, (
        "Expected kv construction pattern not found in normalize.js. "
        "Code should build kv-pairs as { head: k, tail: { head: normalize(value[k], ...), tail: null } }"
    )


def test_readme_uses_tracked_marker_wording():
    """README.md must use 'tracked @host_* markers' not 'irreducible bootstrap floor'."""
    readme = Path(__file__).resolve().parents[3] / "README.md"
    content = readme.read_text()

    assert "irreducible bootstrap floor" not in content, (
        "README.md still uses stale 'irreducible bootstrap floor' wording. "
        "Should say 'tracked @host_* markers (bootstrap substrate lower bound)'."
    )
    assert "@host_* markers" in content, (
        "README.md should reference '@host_* markers' for debt count."
    )
