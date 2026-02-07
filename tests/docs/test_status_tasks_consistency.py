"""
Cross-doc consistency checks for root canonical trackers.

This module enforces semantic agreement between STATUS.md and TASKS.md for
high-risk execution-layer claims that can otherwise drift silently.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = REPO_ROOT / "STATUS.md"
TASKS_PATH = REPO_ROOT / "TASKS.md"

LAYER_TOKENS = ("BOOTSTRAP", "META_CIRCULAR")
SEED_ALIASES = {
    "recurrence": ("recurrence.v1.json", "recurrence.v1"),
    "exhaustion": ("exhaustion.v1.json", "exhaustion.v1"),
}


def _find_layer_claims(text: str, aliases: tuple[str, ...]) -> list[tuple[int, str, str]]:
    claims: list[tuple[int, str, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not any(alias in line for alias in aliases):
            continue
        for token in LAYER_TOKENS:
            if token in line:
                claims.append((line_no, token, line.strip()))
    return claims


def _format_claims(doc_name: str, claims: list[tuple[int, str, str]]) -> str:
    if not claims:
        return f"{doc_name}: (no matching layer claims found)"
    lines = [f"{doc_name} claims:"]
    for line_no, token, line in claims:
        lines.append(f"  - L{line_no}: {token} | {line}")
    return "\n".join(lines)


def test_execution_layer_claims_match_between_status_and_tasks() -> None:
    """
    STATUS.md and TASKS.md must not disagree on recurrence/exhaustion layer.

    If one file says BOOTSTRAP and the other says META_CIRCULAR for the same
    seeds, tracker sync should fail to prevent semantic drift.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    for seed_name, aliases in SEED_ALIASES.items():
        status_claims = _find_layer_claims(status_text, aliases)
        tasks_claims = _find_layer_claims(tasks_text, aliases)

        status_layers = {token for _, token, _ in status_claims}
        tasks_layers = {token for _, token, _ in tasks_claims}

        assert len(status_layers) == 1, (
            f"STATUS.md must have exactly one execution-layer claim for {seed_name}.\n"
            f"{_format_claims('STATUS.md', status_claims)}"
        )
        assert len(tasks_layers) == 1, (
            f"TASKS.md must have exactly one execution-layer claim for {seed_name}.\n"
            f"{_format_claims('TASKS.md', tasks_claims)}"
        )
        assert status_layers == tasks_layers, (
            f"STATUS.md and TASKS.md disagree on execution layer for {seed_name}.\n"
            f"{_format_claims('STATUS.md', status_claims)}\n"
            f"{_format_claims('TASKS.md', tasks_claims)}"
        )


def test_both_trackers_state_algorithm_path_is_currently_hybrid() -> None:
    """
    Both trackers must explicitly reflect current runtime path.

    Runtime truth: recurrence/exhaustion still execute through Python
    match/substitute path in production (hybrid), not structural-only.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    status_has_hybrid_marker = (
        "uses Python match/substitute" in status_text
        or "Current Algorithm Execution" in status_text
    )
    tasks_has_hybrid_marker = (
        "uses Python match/substitute" in tasks_text
        or "Current architecture" in tasks_text
    )

    assert status_has_hybrid_marker, (
        "STATUS.md must explicitly describe current hybrid runtime path."
    )
    assert tasks_has_hybrid_marker, (
        "TASKS.md must explicitly describe current hybrid runtime path."
    )
