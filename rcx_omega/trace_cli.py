"""
COMPAT SHIM (RCX-Ω)

This module moved to: rcx_omega.cli.trace_cli

This shim preserves:
  python3 -m rcx_omega.trace_cli ...

while the implementation lives in the organized Ω layout.
"""
from rcx_omega.cli.trace_cli import main  # noqa: F401

if __name__ == "__main__":
  import sys
  raise SystemExit(main(sys.argv))
