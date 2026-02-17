"""
World-related tools for RCX-π (Python side).

This package contains:
- worlds_probe: fingerprinting and probing of worlds
- worlds_composite, worlds_diff, worlds_evolve
- world_trace_cli: CLI for world tracing
- archive/worlds_bridge: DEPRECATED bridge to archived Rust substrate (rcx_pi_rust).
    Still imported by worlds_probe and world_trace_cli via try/except ImportError
    (graceful degradation — Rust-backed paths are non-functional).

Archived in 24E-R2d: worlds_score_demo, worlds_compare_demo, orbit_ascii_demo,
worlds_mutate_demo, worlds_mutate_loop (0 active imports).
Archived in 24H-turbo1: worlds_mutate_engine (0 imports, broken dependency).
"""
