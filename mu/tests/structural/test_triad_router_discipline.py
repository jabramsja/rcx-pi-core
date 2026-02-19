"""
Triad router dispatch and CLI umbrella routing discipline.

Verifies:
1. triad_dispatch routes known mu strings to correct worlds.
2. rcx_cli.main routes the "replay" subcommand correctly.
3. rcx_cli.main rejects unknown top-level commands.

What this checker PROVES:
- Deterministic routing for paradox_1over0, godel_liar, rcx_core worlds.
- Heuristic routing keywords reach the expected world.
- CLI replay subcommand reaches _cmd_replay path.
- Unknown CLI commands return non-zero exit code.

What this checker does NOT prove:
- Semantic correctness of world probing.
- End-to-end replay execution behavior.
"""

from __future__ import annotations

from rcx_pi.worlds.worlds_composite import triad_dispatch


# ── Triad dispatch route correctness ──────────────────────────────────────


class TestTriadDispatchRouteCorrectness:
    """triad_dispatch must route known mu strings to the correct world."""

    def test_paradox_1over0_explicit(self):
        """Mu strings in _PARADOX_1OVER0_MUS route to paradox_1over0."""
        # "1/0" is the canonical paradox mu
        result = triad_dispatch("1/0")
        assert result == "paradox_1over0", f"Expected paradox_1over0, got {result}"

    def test_godel_liar_explicit(self):
        """Mu strings in _GODEL_LIAR_MUS route to godel_liar."""
        result = triad_dispatch("liar_paradox")
        assert result == "godel_liar", f"Expected godel_liar, got {result}"

    def test_core_fallback(self):
        """Unknown mu strings without heuristic keywords route to rcx_core."""
        result = triad_dispatch("ordinary_mu_value")
        assert result == "rcx_core", f"Expected rcx_core, got {result}"

    def test_heuristic_white_light(self):
        """Heuristic: mu containing 'white_light' routes to paradox_1over0."""
        result = triad_dispatch("some_white_light_test")
        assert result == "paradox_1over0", f"Expected paradox_1over0, got {result}"


# ── CLI replay route ──────────────────────────────────────────────────────


class TestCliReplayRoute:
    """rcx_cli.main must route replay and reject unknown commands."""

    def test_unknown_command_returns_nonzero(self):
        """Unknown top-level command returns exit code 2."""
        from rcx_pi.rcx_cli import main as cli_main
        code = cli_main(["totally_bogus_command"])
        assert code == 2, f"Expected exit code 2 for unknown command, got {code}"

    def test_replay_routes_to_cmd_replay(self):
        """'replay --help' must route through _cmd_replay (argparse exits 0)."""
        import pytest
        from rcx_pi.rcx_cli import main as cli_main
        # argparse --help triggers SystemExit(0) — that proves routing worked
        with pytest.raises(SystemExit) as exc_info:
            cli_main(["replay", "--help"])
        assert exc_info.value.code == 0, (
            f"Expected exit code 0 from replay --help, got {exc_info.value.code}"
        )
