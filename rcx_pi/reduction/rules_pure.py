# rcx_pi/reduction/rules_pure.py

from ..core.motif import Motif, μ, VOID
from ..utils.compression import compression
from .pattern_matching import (
    PatternMatcher,
    PROJECTION,
    CLOSURE,
    ACTIVATION,
    PATTERN_VAR_MARKER,
)

# ---------- structural arithmetic markers ----------

ADD = μ(μ(), μ())  # 2-void header
MULT = μ(μ(), μ(), μ())  # 3-void header
SUCC = μ(μ(μ()))  # encoded successor
PRED = μ(μ(μ(μ())))  # encoded predecessor

# ---------- meta-classification markers (RCX-π "introspection ops") ----------

# operator: classify(target)
CLASSIFY = compression.marker(20)

# tags (these are just structural motifs; engine treats them as opaque labels)
VALUE_TAG = compression.marker(21)  # “pure value / number lobe”
PROGRAM_TAG = compression.marker(22)  # “program / projection lobe”
MIXED_TAG = compression.marker(23)  # “mixed value+program lobe”
STRUCT_TAG = compression.marker(24)  # “generic structural lobe”


class PureRules(PatternMatcher):
    """Pure reduction rules without naming."""

    def reduce(self, m: Motif) -> Motif:
        # --- trivial / already-normal cases ----
        if not isinstance(m, Motif):
            return m

        # Zero is already in normal form
        if m.is_void():
            return m

        # Bare successors (no ADD/MULT/PRED header) are normal Peano values
        if m.is_successor_pure():
            return m

        # ----- arithmetic: ADD -----
        if m.structure and isinstance(m.structure[0], Motif):
            head = m.structure[0]

            # add(a,b) encoded as μ(ADD, a, b)
            if head.structurally_equal(ADD) and len(m.structure) >= 3:
                a, b = m.structure[1], m.structure[2]

                # 0 + b -> b
                if isinstance(a, Motif) and a.is_void():
                    return b

                # succ(n) + b -> succ(n + b)
                if isinstance(a, Motif) and a.is_successor_pure():
                    return μ(a.head().add(b))

            # mult(a,b) encoded as μ(MULT, a, b)
            if head.structurally_equal(MULT) and len(m.structure) >= 3:
                a, b = m.structure[1], m.structure[2]

                # 0 * b -> 0
                if isinstance(a, Motif) and a.is_void():
                    return VOID

                # succ(n) * b -> b + (n * b)
                if isinstance(a, Motif) and a.is_successor_pure():
                    return b.add(a.head().mult(b))

            # pred pattern encoded as μ(PRED, x)
            if head.structurally_equal(PRED) and len(m.structure) >= 2:
                arg = m.structure[1]
                if isinstance(arg, Motif):
                    # pred(0) -> 0
                    if arg.is_zero_pure():
                        return arg
                    # pred(succ(n)) -> n
                    if arg.is_successor_pure():
                        return arg.head()

            # ----- closure activation -----
            # activation encoded as μ(ACTIVATION, func, arg)
            if head.structurally_equal(ACTIVATION) and len(m.structure) >= 3:
                func, arg = m.structure[1], m.structure[2]

                if isinstance(func, Motif) and func.structure:
                    fhead = func.structure[0]
                    # closure encoded as μ(CLOSURE, projection)
                    if isinstance(fhead,
                                  Motif) and fhead.structurally_equal(CLOSURE):
                        # projection is second element of closure
                        if len(func.structure) >= 2:
                            projection = func.structure[1]
                            # PatternMatcher.apply_projection (inherited)
                            return self.apply_projection(projection, arg)

            # ----- meta-classification: classify(target) -----
            # μ(CLASSIFY, target)
            if head.structurally_equal(CLASSIFY) and len(m.structure) >= 2:
                target = m.structure[1]
                return self._classify_target(target)

        # Nothing matched → normal form
        return m

    # =======================================================================
    # META-HELPERS: RCX-π structural introspection
    # =======================================================================

    def _classify_target(self, target: Motif) -> Motif:
        """
        Given a motif 'target', return a tagged motif:

          μ(VALUE_TAG,   target)  if pure Peano number
          μ(PROGRAM_TAG, target)  if contains program markers only
          μ(MIXED_TAG,   target)  if both number-like + program-like
          μ(STRUCT_TAG,  target)  otherwise
        """
        if not isinstance(target, Motif):
            # Non-motif → generic structural
            return μ(STRUCT_TAG, target)

        is_num = target.is_number_pure()
        has_prog = self._contains_program_marker(target)
        has_num_sub = self._contains_number_substructure(target)

        # Pure value lobe
        if is_num and not has_prog:
            return μ(VALUE_TAG, target)

        # Mixed: program markers + at least one number-like substructure
        if has_prog and (is_num or has_num_sub):
            return μ(MIXED_TAG, target)

        # Program-only (closures, projections, activations, pattern vars)
        if has_prog:
            return μ(PROGRAM_TAG, target)

        # Non-number, no program markers → generic structure
        if is_num:
            return μ(VALUE_TAG, target)

        return μ(STRUCT_TAG, target)

    def _contains_program_marker(self, m: Motif) -> bool:
        """Does motif contain any of PROJECTION / CLOSURE / ACTIVATION / pattern vars?"""
        if not isinstance(m, Motif):
            return False

        if m.structure and isinstance(m.structure[0], Motif):
            h = m.structure[0]
            if (
                h.structurally_equal(PROJECTION)
                or h.structurally_equal(CLOSURE)
                or h.structurally_equal(ACTIVATION)
                or h.structurally_equal(PATTERN_VAR_MARKER)
            ):
                return True

        for child in m.structure:
            if isinstance(
                    child,
                    Motif) and self._contains_program_marker(child):
                return True

        return False

    def _contains_number_substructure(self, m: Motif) -> bool:
        """Does motif contain any sub-motif that is a pure Peano number?"""
        if not isinstance(m, Motif):
            return False

        if m.is_number_pure():
            return True

        for child in m.structure:
            if isinstance(
                    child,
                    Motif) and self._contains_number_substructure(child):
                return True

        return False
