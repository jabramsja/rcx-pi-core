from __future__ import annotations


# RCX_REPLAY_FASTPATH_V1
# Keep umbrella CLI stable: only import replay when explicitly invoked.
# Do NOT rely on sys being imported elsewhere.
if __name__ == "__main__":
    _sys = __import__("sys")
    if len(_sys.argv) > 1 and _sys.argv[1] == "replay":
        from rcx_pi.replay_cli import replay_main  # local import on purpose

        raise SystemExit(replay_main(_sys.argv[2:]))
"""
rcx_cli.py

Umbrella CLI router for RCX-π tools.

This file is intentionally thin and does not re-implement leaf flags.
It only routes:

  rcx world trace <...>        -> rcx_pi.worlds.world_trace_cli.main(<...>)

Convenience alias:
  rcx trace <...>              -> rcx world trace <...>

All remaining arguments are forwarded verbatim.

DEPRECATED subcommands (archived in Round 24H, PR #314):
  - `rcx program` (program_descriptor_cli, program_run_cli) — removed.
    These depended on the archived Rust substrate (rcx_pi_rust).
    Archived to archive/rcx_pi_legacy/.
"""

# Allow running this file directly without requiring PYTHONPATH.
# When invoked as a module (python -m rcx_pi.rcx_cli), this block is harmless.
if __package__ is None or __package__ == "":
    import sys

    from pathlib import Path

    repo_root = Path(__file__).parents[1]
    sys.path.insert(0, str(repo_root))

import sys
from rcx_pi.replay_cli import replay_main
from typing import List


HELP = """\
usage: rcx <world|trace|rules|replay> ...

RCX umbrella CLI (routes to world trace, rules, and replay tools).

commands:
  world trace        Delegate to: python -m rcx_pi.worlds.world_trace_cli ...
  trace              Alias for:   world trace
  rules              Rule motif observability (--print-rule-motifs)
  replay             Replay execution traces

examples:
  python3 -m rcx_pi.rcx_cli world trace pingpong ping --max-steps 12 --pretty
  python3 -m rcx_pi.rcx_cli trace pingpong ping --max-steps 6 --pretty
  python3 -m rcx_pi.rcx_cli rules --print-rule-motifs
  python3 -m rcx_pi.rcx_cli replay <trace-file>
"""


def _help(code: int = 0) -> int:
    print(HELP)
    return code


def _cmd_replay(argv: list[str]) -> int:
    return replay_main(argv)


def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        return _help(0)

    # Convenience alias: `rcx trace ...` -> `world trace ...`
    if argv[0] == "trace":
        argv = ["world", "trace"] + argv[1:]

    if len(argv) < 2:
        # Single-arg commands
        if argv[0] == "rules":
            from rcx_pi.rule_motifs_v0 import rules_main

            return int(rules_main([]))

        return _help(2)

    top = argv[0]

    if top == "world":
        sub = argv[1]
        rest = argv[2:]

        if sub == "trace":
            from rcx_pi.worlds.world_trace_cli import main as world_trace_main

            return int(world_trace_main(rest))

        print(f"rcx: unknown world subcommand: {sub!r}", file=sys.stderr)
        return _help(2)

    if top == "rules":
        rest = argv[1:]
        from rcx_pi.rule_motifs_v0 import rules_main

        return int(rules_main(rest))

    if top == "replay":
        return _cmd_replay(argv[1:])

    print(f"rcx: unknown command: {top!r}", file=sys.stderr)
    return _help(2)


if __name__ == "__main__":
    raise SystemExit(main())


