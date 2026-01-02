# rcx_pi/worlds/worlds_diff.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from rcx_pi.worlds_probe import probe_world


@dataclass(frozen=True)
class Mismatch:
    mu: str
    expected: str
    got: str


@dataclass(frozen=True)
class DiffReport:
    world: str
    spec_name: str
    total: int
    matches: int
    mismatches: List[Mismatch]

    @property
    def accuracy(self) -> float:
        return 0.0 if self.total == 0 else self.matches / self.total

    def by_expected(self) -> Dict[str, List[Mismatch]]:
        buckets: Dict[str, List[Mismatch]] = {
            "Ra": [], "Lobe": [], "Sink": [], "None": []}
        for m in self.mismatches:
            buckets.setdefault(m.expected, []).append(m)
        return buckets


def diff_world_against_spec(
    world: str,
    spec_name: str,
    spec: Dict[str, str],
    *,
    max_steps: int = 20,
) -> DiffReport:
    """
    Probe `world` against `spec` and return a structured diff report.
    """
    seeds: List[str] = list(spec.keys())
    fp: Dict[str, Any] = probe_world(world, seeds, max_steps=max_steps)

    got_map: Dict[str, str] = {}
    for row in fp.get("routes", []) or []:
        mu = row.get("mu", "")
        route = row.get("route", "None")
        if not mu:
            continue
        if route not in ("Ra", "Lobe", "Sink", "None"):
            route = "None"
        got_map[mu] = route

    mismatches: List[Mismatch] = []
    matches = 0

    for mu, expected in spec.items():
        got = got_map.get(mu, "None")
        if got == expected:
            matches += 1
        else:
            mismatches.append(Mismatch(mu=mu, expected=expected, got=got))

    return DiffReport(
        world=world,
        spec_name=spec_name,
        total=len(seeds),
        matches=matches,
        mismatches=mismatches,
    )


def format_diff_report(report: DiffReport, *, limit: int | None = None) -> str:
    """
    Pretty-print the report for CLI/debug output.
    """
    lines: List[str] = []
    lines.append(
        f"=== Diff: world='{
            report.world}' vs spec='{
            report.spec_name}' ===")
    lines.append(
        f"Summary: {report.matches}/{report.total} "
        f"(accuracy={report.accuracy:.3f}), mismatches={len(report.mismatches)}"
    )
    if not report.mismatches:
        return "\n".join(lines)

    lines.append("")
    show = report.mismatches if limit is None else report.mismatches[: max(
        0, limit)]
    for m in show:
        lines.append(f"✗ {m.mu:<32} expected={m.expected:<4} got={m.got:<4}")

    if limit is not None and len(report.mismatches) > limit:
        lines.append(f"... ({len(report.mismatches) - limit} more)")

    return "\n".join(lines)
