from __future__ import annotations

from rcx_pi.cli_schema import schema_triplet


def test_schema_triplet_is_space_delimited_triplet():
    out = schema_triplet("tag.v1", "docs/a.md", "docs/schemas/a.json")
    assert out == "tag.v1 docs/a.md docs/schemas/a.json"
    assert out.count(" ") == 2


def test_schema_triplet_preserves_inputs_verbatim():
    out = schema_triplet("x", "y", "z")
    assert out == "x y z"
