from __future__ import annotations

import pytest

from rcx_pi.cli_schema import (
    SchemaTriplet,
    parse_schema_triplet,
    parse_schema_triplet_tuple,
)


def test_parse_schema_triplet_happy_path_no_newline():
    line = "tag.v1 docs/a.md docs/schemas/a.json"
    t = parse_schema_triplet(line)
    assert isinstance(t, SchemaTriplet)
    assert (t.tag, t.doc_md, t.schema_json) == (
        "tag.v1",
        "docs/a.md",
        "docs/schemas/a.json",
    )


def test_parse_schema_triplet_happy_path_with_newline():
    line = "tag.v1 docs/a.md docs/schemas/a.json\n"
    t = parse_schema_triplet(line)
    assert (t.tag, t.doc_md, t.schema_json) == (
        "tag.v1",
        "docs/a.md",
        "docs/schemas/a.json",
    )


def test_parse_schema_triplet_tuple_back_compat():
    line = "tag.v1 docs/a.md docs/schemas/a.json\n"
    assert parse_schema_triplet_tuple(line) == (
        "tag.v1",
        "docs/a.md",
        "docs/schemas/a.json",
    )


@pytest.mark.parametrize(
    "bad",
    [
        "",  # empty
        "\n",  # empty newline
        " tag.v1 docs/a.md docs/schemas/a.json",  # leading space
        "tag.v1 docs/a.md docs/schemas/a.json ",  # trailing space
        "tag.v1  docs/a.md docs/schemas/a.json",  # double space
        "tag.v1\tdocs/a.md docs/schemas/a.json",  # tab
        "tag.v1 docs/a.md docs/schemas/a.json\n\n",  # extra newline
        "tag.v1 docs/a.md",  # too few fields
        "tag.v1 docs/a.md docs/schemas/a.json EXTRA",  # too many fields
        "tag.v1 docs/a.md docs/schemas/a.json\nEXTRA",  # extra non-empty line
        "tag.v1 docs/a.md docs/schemas/a.json\r\n",  # CRLF (should be rejected by token rules)
        "tag.v1 docs/a md docs/schemas/a.json",  # whitespace inside token
        "tag.v1 docs/a.md docs/schemas/a json",  # whitespace inside token
    ],
)
def test_parse_schema_triplet_rejects_invalid_inputs(bad: str):
    with pytest.raises((TypeError, ValueError)):
        parse_schema_triplet(bad)
