#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any, Dict, List

from rcx_pi.worlds_probe import probe_world
from rcx_pi.worlds.worlds_evolve import rank_worlds, SPEC_PRESETS, DEFAULT_CANDIDATE_WORLDS
from rcx_pi.worlds.worlds_diff import diff_world_against_spec, format_diff_report

# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------


def _print_fingerprint(fp: Dict[str, Any], explain: bool = False) -> None:
    """Pretty-print a fingerprint returned by probe_world."""
    world = fp.get("world", "<unknown>")
    seeds = fp.get("seeds", [])
    routes = fp.get("routes", [])
    summary = fp.get("summary", {}) or {}
    counts = summary.get("counts", {}) or {}
    limit_cycles = summary.get("limit_cycles", []) or []
    orbits = fp.get("orbits", []) or []

    banner = f"World: {world}"
    print("=" * len(banner))
    print(banner)
    print("=" * len(banner))
    print(f"Seeds: {seeds}\n")
    print()

    # Routes table
    print("Routes:")
    print("  mu                   route   world")
    print("  " + "-" * 60)
    for row in routes:
        mu = row.get("mu", "?")
        route = row.get("route", "None")
        w = row.get("world", "") or ""
        print(f"  {mu:<20} {route:<7} {w}")
    print()

    # Summary
    print("Summary:")
    print("  counts:")
    print(f"    Ra  : {counts.get('Ra', 0)}")
    print(f"    Lobe: {counts.get('Lobe', 0)}")
    print(f"    Sink: {counts.get('Sink', 0)}")
    print(f"    None: {counts.get('None', 0)}")

    if limit_cycles:
        print("  limit_cycles:")
        for lc in limit_cycles:
            mu = lc.get("mu", "?")
            kind = lc.get("kind", "?")
            period = lc.get("period", "?")
            print(f"    - mu='{mu}', kind='{kind}', period={period}")
    else:
        print("  limit_cycles: []")

    if explain:
        _print_explain(fp)

    print()

def _print_explain(fp: Dict[str, Any]) -> None:
    print("\nExplain:")

    dispatch = fp.get("dispatch", []) or fp.get("dispatch_rows", []) or []
    summary = fp.get("summary", {}) or {}
    counts = summary.get("counts", {}) or {}
    limit_cycles = summary.get("limit_cycles", []) or []

    if dispatch:
        by_world: Dict[str, List[tuple[str, str]]] = {}
        for row in dispatch:
            mu = row.get("mu", "?")
            world = row.get("world", "?")
            reason = row.get("reason", "") or ""
            by_world.setdefault(world, []).append((mu, reason))

        print("  dispatch (world -> seeds):")
        for world in sorted(by_world.keys()):
            print(f"    {world}:")
            for (mu, reason) in by_world[world]:
                if reason:
                    print(f"      - {mu}  (reason: {reason})")
                else:
                    print(f"      - {mu}")
    else:
        print("  (no dispatch info)")

    print("\n  summary:")
    print(f"    Ra  : {counts.get('Ra', 0)}")
    print(f"    Lobe: {counts.get('Lobe', 0)}")
    print(f"    Sink: {counts.get('Sink', 0)}")
    print(f"    None: {counts.get('None', 0)}")

    if limit_cycles:
        print("  limit_cycles:")
        for lc in limit_cycles:
            mu = lc.get("mu", "?")
            kind = lc.get("kind", "?")
            period = lc.get("period", "?")
            print(f"    - mu='{mu}', kind='{kind}', period={period}")

    raw = fp.get("raw_output")
    if raw:
        print("\n  raw_output:")
        _print_indented_block(raw, indent="    ", max_blank_run=1)

    orbits = fp.get("orbits", []) or []
    if orbits:
        print("\n  orbits:")
        for o in orbits:
            mu = o.get("mu", "?")
            orbit_obj = o.get("orbit")
            print(f"    {mu}: {orbit_obj}")

def _print_promote_report(spec_name: str, max_steps: int) -> None:
    from rcx_pi.specs.triad_plus_routes import TRIAD_PLUS_ROUTE_OVERRIDES
    from rcx_pi.worlds.worlds_composite import triad_dispatch

    override_seeds = list(TRIAD_PLUS_ROUTE_OVERRIDES.keys())

    print(f"=== Promote report for spec='{spec_name}' ===")

    promotable = []
    still_override = []

    for mu in override_seeds:
        target = triad_dispatch(mu)
        fp = probe_world(target, [mu], max_steps=max_steps)

        got = fp.get("routes", [{}])[0].get("route", "None")
        exp = TRIAD_PLUS_ROUTE_OVERRIDES[mu]

        if got == exp and got != "None":
            promotable.append((mu, target, exp))
        else:
            still_override.append((mu, target, exp, got))

    if promotable:
        print("\nPromotable (native world already matches expected route):")
        for mu, target, exp in promotable:
            print(f"  ✓ {mu:<28} -> {target:<14} route={exp}")

    if still_override:
        print("\nStill needs override (native world differs):")
        for mu, target, exp, got in still_override:
            print(f"  ✗ {mu:<28} -> {target:<14} expected={exp:<5} got={got:<5}")

    print()

def _print_indented_block(text: str, indent: str = "    ", max_blank_run: int = 1) -> None:
    """
    Print a block with indentation, collapsing long blank runs.
    """
    blank_run = 0
    for line in str(text).splitlines():
        if not line.strip():
            blank_run += 1
            if blank_run > max_blank_run:
                continue
        else:
            blank_run = 0
        print(f"{indent}{line}")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RCX-π runtime / world probe"
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show routing/explanation details (dispatch + raw classifier output).",
    )

    parser.add_argument(
        "--promote",
        action="store_true",
        help="Show which triad_plus override seeds can be promoted into native worlds",
    )

    parser.add_argument(
        "--world",
        help="Run a single Mu world (e.g. rcx_core, paradox_1over0, pingpong)",
    )
    parser.add_argument(
        "--spec",
        help=(
            "Spec preset name (e.g. 'core', 'paradox_1over0'). "
            "If used alone, picks the best world from default candidates. "
            "If combined with --worlds, ranks those worlds."
        ),
    )
    parser.add_argument(
        "--worlds",
        nargs="+",
        help="Explicit list of candidate worlds for spec dashboard / ranking.",
    )

    parser.add_argument(
        "--seed",
        dest="seeds",
        nargs="+",
        help="Mu seeds to classify (e.g. \"[null,a]\" \"[inf,a]\").",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=12,
        help="Max steps used for orbit modeling in some worlds (e.g. pingpong).",
    )

    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Mode 0: promotion report for triad_plus overrides
    if args.promote:
        if not args.spec:
            raise SystemExit("--promote requires --spec (e.g. --spec rcx_triad_plus)")
        if args.spec not in SPEC_PRESETS:
            raise SystemExit(
                f"Unknown spec preset {args.spec!r}. Available: {sorted(SPEC_PRESETS.keys())}"
            )
        _print_promote_report(args.spec, max_steps=args.max_steps)
        return
   
    # Mode 1: spec dashboard over explicit worlds (with optional probing)
    if args.spec and args.worlds:
        _print_ranked_worlds_dashboard(args.spec, args.worlds)

        if args.seeds:
            # Pick top world and probe it with the provided seeds.
            spec = SPEC_PRESETS[args.spec]
            scores = rank_worlds(args.worlds, spec)
            if not scores:
                return

            best = scores[0].world
            print(
                f"Probing best world {best!r} for spec='{args.spec}' "
                f"with seeds {args.seeds}...\n"
            )
            fp = probe_world(best, args.seeds, max_steps=args.max_steps)
            _print_fingerprint(fp, explain=args.explain)
        return

    # Mode 2: spec-only, no explicit worlds → use default candidate set
    if args.spec and not args.world:
        if args.spec not in SPEC_PRESETS:
            raise ValueError(
                f"Unknown spec preset {args.spec!r}. "
                f"Available: {sorted(SPEC_PRESETS.keys())}"
            )

        spec = SPEC_PRESETS[args.spec]
        scores = rank_worlds(DEFAULT_CANDIDATE_WORLDS, spec)
        if not scores:
            print("No candidate worlds available to rank.")
            return

        best = scores[0].world

        if args.explain:
            report = diff_world_against_spec(
                best,
                args.spec,
                spec,
                max_steps=args.max_steps,
            )
            print(format_diff_report(report))

            # If the selected world provides dispatch info (e.g.
            # rcx_triad_router)
            fp = probe_world(best, list(spec.keys()), max_steps=args.max_steps)
            dispatch = fp.get("dispatch", []) or []
            if dispatch:
                print("\nDispatch:")
                for row in dispatch:
                    mu = row.get("mu", "")
                    w = row.get("world", "")
                    if mu and w:
                        print(f"  {mu:<32} -> {w}")
            print()

        # If no seeds, just show the dashboard and exit.
        if not args.seeds:
            _print_ranked_worlds_dashboard(args.spec, DEFAULT_CANDIDATE_WORLDS)
            return

        banner = (
            f"World: {best}  (selected by spec='{args.spec}' "
            f"from {', '.join(DEFAULT_CANDIDATE_WORLDS)})"
        )
        print("=" * len(banner))
        print(banner)
        print("=" * len(banner))

        fp = probe_world(best, args.seeds, max_steps=args.max_steps)
        _print_fingerprint(fp, explain=args.explain)
        return

    # Mode 3: direct world probing
    if args.world:
        if not args.seeds:
            raise SystemExit(
                "You must provide --seed when using --world.\n"
                "Example:\n"
                "  python3 rcx_runtime.py --world rcx_core "
                "--seed \"[null,a]\" \"[inf,a]\""
            )
        fp = probe_world(args.world, args.seeds, max_steps=args.max_steps)
        _print_fingerprint(fp, explain=args.explain)
        return

    # If we got here, no meaningful mode was selected.
    raise SystemExit(
        "No mode selected.\n\n"
        "Examples:\n"
        "  # Direct world probe\n"
        "  python3 rcx_runtime.py --world rcx_core "
        "--seed \"[null,a]\" \"[inf,a]\" \"[paradox,a]\" \"[omega,[a,b]]\"\n\n"
        "  # Let a spec pick the best world from defaults and probe it\n"
        "  python3 rcx_runtime.py --spec core "
        "--seed \"[null,a]\" \"[inf,a]\" \"[paradox,a]\" \"[omega,[a,b]]\"\n\n"
        "  # Spec dashboard over explicit worlds\n"
        "  python3 rcx_runtime.py --spec core "
        "--worlds rcx_core vars_demo pingpong news paradox_1over0\n\n"
        "  # Spec dashboard + probe top world on given seeds\n"
        "  python3 rcx_runtime.py --spec core "
        "--worlds rcx_core vars_demo pingpong news paradox_1over0 "
        "--seed \"[null,a]\" \"[inf,a]\" \"[paradox,a]\" \"[omega,[a,b]]\"\n"
    )


if __name__ == "__main__":
    main()
