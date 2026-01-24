# rcx_pi/reduction/pattern_matching.py
from ..core.motif import Motif, μ


def _motif_to_json(m):
    """Convert a Motif to JSON-serializable form for deterministic hashing."""
    if not isinstance(m, Motif):
        return m
    if not m.structure:
        return {"_void": True}
    return {"_struct": [_motif_to_json(c) for c in m.structure]}


# Marker depths (structural symbols)
PROJECTION = μ(μ(μ(μ(μ(μ(μ()))))))  # 6-deep marker
CLOSURE = μ(μ(μ(μ(μ()))))  # 4-deep marker
ACTIVATION = μ(μ(μ(μ(μ(μ())))))  # 5-deep marker

# 7-deep marker = pattern variable
VAR = μ(μ(μ(μ(μ(μ(μ(μ())))))))  # internal name
PATTERN_VAR_MARKER = VAR  # exported name used by rules_pure


def is_var(m):
    return (
        isinstance(m, Motif)
        and len(m.structure) >= 2
        and isinstance(m.structure[0], Motif)
        and m.structure[0].structurally_equal(VAR)
    )


def is_closure(m):
    return (
        isinstance(m, Motif)
        and len(m.structure) >= 2
        and isinstance(m.structure[0], Motif)
        and m.structure[0].structurally_equal(CLOSURE)
    )


def is_proj(m):
    return (
        isinstance(m, Motif)
        and len(m.structure) >= 3
        and isinstance(m.structure[0], Motif)
        and m.structure[0].structurally_equal(PROJECTION)
    )


def is_act(m):
    return (
        isinstance(m, Motif)
        and len(m.structure) >= 3
        and isinstance(m.structure[0], Motif)
        and m.structure[0].structurally_equal(ACTIVATION)
    )


class PatternMatcher:
    """Pure structural projection engine — no strings anywhere."""

    def __init__(self, observer=None, execution_engine=None):
        self._observer = observer
        self._execution_engine = execution_engine

    def apply_projection(self, proj, value):
        """Apply a PROJECTION(pattern, body) to a value motif."""
        if not is_proj(proj):
            return value

        # proj = μ(PROJECTION, pattern, body)
        _, pattern, body = proj.structure

        bindings = {}
        if not self._match(pattern, value, bindings):
            # pattern did not match; return value unchanged
            if self._observer:
                self._observer.stall("pattern_mismatch")
            # Execution mode: track stall state (RCX_EXECUTION_V0=1)
            if self._execution_engine:
                # Convert value to JSON-serializable form for hashing
                value_repr = _motif_to_json(value) if hasattr(value, 'structure') else value
                self._execution_engine.stall("projection.pattern_mismatch", value_repr)
            return value

        return self._apply(body, bindings)

    # ----- structural matching -----

    def _match(self, p, v, env):
        """Match pattern p against value v, filling env with bindings."""
        if is_var(p):
            key = repr(p)  # structural key for this variable pattern
            env[key] = v
            return True

        if not isinstance(p, Motif) or not isinstance(v, Motif):
            return False

        if len(p.structure) != len(v.structure):
            return False

        return all(self._match(a, b, env) for a, b in zip(p.structure, v.structure))

    # ----- binding substitution -----

    def _apply(self, body, env):
        """Recursively substitute bindings in body."""
        if is_var(body):
            return env.get(repr(body), body)

        if not isinstance(body, Motif):
            return body

        return Motif(*(self._apply(x, env) for x in body.structure))


# Optional: explicit export list (nice but not required)
__all__ = [
    "PatternMatcher",
    "PROJECTION",
    "CLOSURE",
    "ACTIVATION",
    "PATTERN_VAR_MARKER",
    "is_var",
    "is_closure",
    "is_proj",
    "is_act",
]
