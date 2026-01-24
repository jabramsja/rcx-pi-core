from __future__ import annotations


def schema_triplet(tag: str, doc_md: str, schema_json: str) -> str:
    # Canonical: <schema_tag> <schema_doc_path> <schema_json_path>
    return f"{tag} {doc_md} {schema_json}"


def print_schema_triplet(tag: str, doc_md: str, schema_json: str) -> None:
    print(schema_triplet(tag, doc_md, schema_json))
