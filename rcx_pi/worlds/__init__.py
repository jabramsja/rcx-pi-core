"""
World-related tools for RCX-π (Python side).

This package contains:
- worlds_bridge: bridge to Rust classifier/orbit CLI
- worlds_probe: fingerprinting and probing of worlds
- worlds_compare_demo, worlds_evolve, worlds_score_demo, worlds_mutate_demo
- orbit_ascii_demo: ASCII visualization of ω-orbits
"""

from .worlds_bridge import (
    classify_with_world,
    orbit_with_world,
    orbit_with_world_parsed,
)
