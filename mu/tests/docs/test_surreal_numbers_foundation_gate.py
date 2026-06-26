"""Compatibility entry point for the SurrealNumbers foundation gate.

The authoritative L4 gate lives under ``mu/tests/l4_gates`` so the L4 execution
contract can bind this docs-only foundation wave to a gate target. This wrapper
keeps the original docs path runnable for existing evidence commands.
"""

from tests.l4_gates.test_surreal_numbers_foundation_gate import *  # noqa: F401,F403
