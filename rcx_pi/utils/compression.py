# rcx_pi/utils/compression.py
from ..core.motif import μ, VOID

class Compression:
    """Depth markers used by recursion, divergence detection and pattern scopes."""

    def __init__(self):
        self.cache = {0: VOID}
        for d in range(1, 40):
            self.cache[d] = self._mk(d)

    def _mk(self, depth):
        x = VOID
        for _ in range(depth):
            x = μ(x)
        return x

    def marker(self, depth):
        if depth not in self.cache:
            self.cache[depth] = self._mk(depth)
        return self.cache[depth]

compression = Compression()