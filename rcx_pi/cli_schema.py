from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True, slots=True)
class SchemaTriplet:
    tag: str
    doc_md: str
    schema_json: str


def _validate_token(name: str, s: str) -> str:
    """
    Enforce "single token" contract:
    - no leading/trailing whitespace
    - no embedded whitespace
    - no newlines
    - non-empty
    """
    if not isinstance(s, str):
        raise TypeError(f"{name} must be str, got {type(s).__name__}")
    if s == "":
        raise ValueError(f"{name} must be non-empty")
    if s != s.strip():
        raise ValueError(f"{name} must not have leading/trailing whitespace: {s!r}")
    if any(ch.isspace() for ch in s):
        # catches spaces, tabs, newlines, etc.
        raise ValueError(f"{name} must not contain whitespace: {s!r}")
    return s


def schema_triplet(tag: str, doc_md: str, schema_json: str) -> str:
    """
    Canonical formatter for --schema output.

    Returns a single-line, three-field, space-delimited triplet WITHOUT a trailing newline.
    """
    tag = _validate_token("tag", tag)
    doc_md = _validate_token("doc_md", doc_md)
    schema_json = _validate_token("schema_json", schema_json)
    return f"{tag} {doc_md} {schema_json}"


def print_schema_triplet(tag: str, doc_md: str, schema_json: str) -> None:
    """
    Prints the canonical triplet WITH a single trailing newline.
    """
    print(schema_triplet(tag, doc_md, schema_json), flush=True)


def parse_schema_triplet(line: str) -> SchemaTriplet:
    """
    Strict parser for a schema triplet line.

    Accepts either:
    - a raw line without newline, or
    - a line ending in a single newline

    Rejects:
    - extra whitespace
    - extra fields
    - empty fields
    """
    if not isinstance(line, str):
        raise TypeError(f"line must be str, got {type(line).__name__}")

    s = line
    if s.endswith("\n"):
        s = s[:-1]

    # Exactly two single spaces between three non-whitespace fields
    parts = s.split(" ")
    if len(parts) != 3:
        raise ValueError(
            f"expected exactly 3 fields separated by single spaces: {line!r}"
        )

    tag, doc_md, schema_json = parts
    # validate each token using the same constraints
    tag = _validate_token("tag", tag)
    doc_md = _validate_token("doc_md", doc_md)
    schema_json = _validate_token("schema_json", schema_json)

    return SchemaTriplet(tag=tag, doc_md=doc_md, schema_json=schema_json)


def parse_schema_triplet_tuple(line: str) -> Tuple[str, str, str]:
    """
    Back-compat convenience: returns (tag, doc_md, schema_json).
    """
    t = parse_schema_triplet(line)
    return (t.tag, t.doc_md, t.schema_json)
