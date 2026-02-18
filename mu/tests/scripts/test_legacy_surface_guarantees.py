"""
Test-lock guarantees for the legacy CLI surface (world tracing/probing).

These tests ensure that:
1. Schema mode works reliably (the only Rust-independent path).
2. Synthetic worlds (godel_liar, rcx_triad_router) produce valid fingerprints.
3. Non-synthetic worlds fail with deterministic error when bridge unavailable.
4. rcx_cli dispatches world trace correctly.
5. Error paths return deterministic codes.

The Rust bridge (worlds_bridge) was archived in Round 21D. Only synthetic
worlds and schema mode are guaranteed Rust-independent. These tests lock
that reality.
"""

import sys
from unittest import mock

import pytest
from rcx_pi.worlds.worlds_probe import probe_world
from rcx_pi.rcx_cli import main as rcx_cli_main
from rcx_pi.worlds.world_trace_cli import main as world_trace_main


# ── Guarantee 1: Schema mode works (Rust-independent) ──────────────────


class TestSchemaMode:
    """world_trace_cli --schema returns the canonical schema triplet."""

    def test_schema_flag_returns_zero(self):
        code = world_trace_main(["--schema"])
        assert code == 0

    def test_schema_via_rcx_cli(self):
        code = rcx_cli_main(["world", "trace", "--schema"])
        assert code == 0

    def test_schema_via_trace_alias(self):
        code = rcx_cli_main(["trace", "--schema"])
        assert code == 0


# ── Guarantee 2: Synthetic worlds produce valid fingerprints ────────────


class TestSyntheticWorlds:
    """Synthetic worlds (godel_liar, rcx_triad_router) work without Rust bridge."""

    def test_godel_liar_probe_returns_fingerprint(self):
        seeds = ["[liar]", "[I_am_true]", "[force_true(liar)]"]
        fp = probe_world("godel_liar", seeds)
        assert fp["world"] == "godel_liar"
        assert isinstance(fp["routes"], list)
        assert len(fp["routes"]) == 3
        assert all("mu" in r and "route" in r for r in fp["routes"])

    def test_godel_liar_route_correctness(self):
        seeds = ["[liar]", "[I_am_true]", "[force_true(liar)]"]
        fp = probe_world("godel_liar", seeds)
        route_map = {r["mu"]: r["route"] for r in fp["routes"]}
        assert route_map["[liar]"] == "Lobe"
        assert route_map["[I_am_true]"] == "Ra"
        assert route_map["[force_true(liar)]"] == "Sink"

    def test_godel_liar_summary_counts(self):
        seeds = ["[liar]", "[I_am_true]", "[force_true(liar)]"]
        fp = probe_world("godel_liar", seeds)
        counts = fp["summary"]["counts"]
        assert counts["Ra"] == 1
        assert counts["Lobe"] == 1
        assert counts["Sink"] == 1

    def test_godel_liar_unknown_seed_routes_none(self):
        fp = probe_world("godel_liar", ["[unknown_seed]"])
        assert fp["routes"][0]["route"] == "None"

    def test_rcx_triad_router_probe_returns_fingerprint(self):
        seeds = ["[null,a]"]
        fp = probe_world("rcx_triad_router", seeds)
        assert fp["world"] == "rcx_triad_router"
        assert isinstance(fp["routes"], list)

    def test_fingerprint_has_required_keys(self):
        fp = probe_world("godel_liar", ["[liar]"])
        required = {"world", "seeds", "routes", "summary", "orbits", "raw_output"}
        assert required.issubset(fp.keys())


# ── Guarantee 3: Non-synthetic worlds fail when bridge unavailable ──────


class TestNonSyntheticWorldFailure:
    """Non-synthetic worlds raise RuntimeError when Rust bridge unavailable."""

    def test_rcx_core_raises_when_bridge_none(self):
        with mock.patch("rcx_pi.worlds.worlds_probe.classify_with_world", None):
            with pytest.raises(RuntimeError, match="Rust bridge unavailable"):
                probe_world("rcx_core", ["[null,a]"])

    def test_pingpong_raises_when_bridge_none(self):
        with mock.patch("rcx_pi.worlds.worlds_probe.classify_with_world", None):
            with pytest.raises(RuntimeError, match="Rust bridge unavailable"):
                probe_world("pingpong", ["ping"])

    def test_unknown_world_raises_when_bridge_none(self):
        with mock.patch("rcx_pi.worlds.worlds_probe.classify_with_world", None):
            with pytest.raises(RuntimeError, match="Rust bridge unavailable"):
                probe_world("nonexistent_world", ["seed"])

    def test_error_message_includes_world_name(self):
        with mock.patch("rcx_pi.worlds.worlds_probe.classify_with_world", None):
            with pytest.raises(RuntimeError, match="rcx_core"):
                probe_world("rcx_core", ["[null,a]"])

    def test_error_message_suggests_synthetic(self):
        with mock.patch("rcx_pi.worlds.worlds_probe.classify_with_world", None):
            with pytest.raises(RuntimeError, match="synthetic world"):
                probe_world("rcx_core", ["[null,a]"])

    def test_world_trace_cli_returns_one_when_bridge_none(self):
        """world_trace_cli returns 1 when Rust bridge unavailable."""
        with mock.patch("rcx_pi.worlds.world_trace_cli.orbit_with_world_parsed", None):
            code = world_trace_main(["pingpong", "ping"])
            assert code == 1


# ── Guarantee 4: rcx_cli dispatch correctness ───────────────────────────


class TestCLIDispatch:
    """rcx_cli routes commands correctly and returns deterministic codes."""

    def test_help_returns_zero(self):
        assert rcx_cli_main(["--help"]) == 0

    def test_empty_args_returns_zero(self):
        assert rcx_cli_main([]) == 0

    def test_unknown_command_returns_two(self):
        assert rcx_cli_main(["nonexistent"]) == 2

    def test_unknown_world_subcommand_returns_two(self):
        assert rcx_cli_main(["world", "nonexistent"]) == 2

    def test_world_trace_missing_args_exits_two(self):
        """world_trace_cli without world/seed calls argparse.error -> SystemExit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            world_trace_main([])
        assert exc_info.value.code == 2
