from __future__ import annotations

from rcx_pi.cli_schema_run import run_schema_triplet


def test_python_entrypoints_schema_triplets_are_parseable():
    # These are intentionally python-only entrypoints (CI/python-only gate).
    results = [
        run_schema_triplet(["python3", "rcx_pi/program_descriptor_cli.py", "--schema"]),
        run_schema_triplet(["python3", "rcx_pi/program_run_cli.py", "--schema"]),
        run_schema_triplet(
            ["python3", "-m", "rcx_pi.worlds.world_trace_cli", "--schema"]
        ),
        run_schema_triplet(
            [
                "python3",
                "scripts/snapshot_merge.py",
                "--schema",
                "A",
                "B",
                "--out",
                "OUT.json",
            ]
        ),
    ]

    for res in results:
        trip = res.trip
        assert trip.tag.endswith(".v1")
        assert trip.doc_md.startswith("docs/") and trip.doc_md.endswith(".md")
        assert trip.schema_json.startswith(
            "docs/schemas/"
        ) and trip.schema_json.endswith(".json")
