"""
RCX-Ω staging namespace.

Ω is allowed to evolve.
π (rcx_pi/) remains frozen except for green-preserving bugfixes.

Layout:
- rcx_omega/core   : Ω core scaffolds and layer definitions
- rcx_omega/engine : wrappers around π execution (trace, observers, etc.)
- rcx_omega/cli    : Ω command line tools
- rcx_omega/tests  : Ω tests

Compatibility:
Top-level modules rcx_omega.trace / rcx_omega.trace_cli / rcx_omega.omega_kernel
remain as shims so older entrypoints keep working.
"""

# Convenience re-exports (stable-ish):
from rcx_omega.core.omega_kernel import OmegaPlan, omega_enabled  # noqa: F401
from rcx_omega.engine.trace import trace_reduce  # noqa: F401
