"""
Shim so old imports `from rcx_pi.worlds_probe import probe_world`
continue to work after moving code into rcx_pi/worlds/worlds_probe.py.
"""

from .worlds.worlds_probe import *  # type: ignore  # noqa: F401,F403
