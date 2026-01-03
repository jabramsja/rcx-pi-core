"""
RCX-Ω kernel scaffold (staging).

Goal: build meta-circular layers *outside* rcx_pi core, then graduate via contracts.
Nothing here is considered stable yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Any


class OmegaLayer(Protocol):
    """Ω layers operate on π motifs/evaluator without mutating π."""
    def step(self, x: Any) -> Any: ...


@dataclass(frozen=True)
class OmegaPlan:
    """
    A minimal planning container for Ω experiments.
    This is intentionally boring: structure first, power later.
    """
    name: str
    notes: str = ""
    enabled: bool = False


def omega_enabled() -> bool:
    """Single switch for gating future Ω behavior."""
    return False
