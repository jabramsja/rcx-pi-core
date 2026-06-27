"""Compatibility entry point for the Coinduction foundation gate.

The authoritative L4 gate lives under ``mu/tests/l4_gates`` so the L4 execution
contract can bind this docs-only foundation wave to a gate target. This wrapper
keeps the docs path runnable for evidence commands.
"""

from tests.l4_gates.test_coinduction_foundation_gate import *  # noqa: F401,F403
