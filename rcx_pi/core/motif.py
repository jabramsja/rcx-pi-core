"""
RCX-π MOTIF CORE
================
No names, no symbols. Pure structure.
Void = μ()
Successor = μ(prev)
Everything is a recursive container of motifs.

This is the primitive substrate upon which projection,
closure, paradox, recursion, arithmetic and OS-shell emerge.
"""


class Motif:
    """A motif is pure structure — no strings, only structural recursion."""

    def __init__(self, *structure):
        self.structure = tuple(structure)

    # ---------- structural identity ----------

    def structurally_equal(self, other):
        if not isinstance(other, Motif):
            return False
        if len(self.structure) != len(other.structure):
            return False
        for a, b in zip(self.structure, other.structure):
            if isinstance(a, Motif) and isinstance(b, Motif):
                if not a.structurally_equal(b):
                    return False
            elif a != b:
                return False
        return True

    __eq__ = structurally_equal

    def __hash__(self):
        return hash(self.structure)

    def __repr__(self):
        if not self.structure:
            return "μ()"
        return "μ(" + ", ".join(repr(s) for s in self.structure) + ")"

    # ---------- primitive queries ----------

    def is_void(self):
        return len(self.structure) == 0

    def is_zero_pure(self):
        return self.is_void()

    def is_successor_pure(self):
        return len(
            self.structure) == 1 and isinstance(
            self.structure[0], Motif)

    def is_number_pure(self):
        if self.is_zero_pure():
            return True
        return self.is_successor_pure() and self.structure[0].is_number_pure()

    # ---------- structural operations ----------

    def head(self):
        if self.structure:
            return self.structure[0]
        return None

    def tail(self):
        if len(self.structure) > 1:
            return Motif(*self.structure[1:])
        return Motif()

    def cons(self, x):
        return Motif(x, *self.structure)

    # ---------- Peano arithmetic (structural) ----------

    def succ(self):
        if self.is_number_pure():
            return Motif(self)  # succ(n)
        return Motif(Motif(Motif()), self)  # succ-pattern

    def pred(self):
        if self.is_zero_pure():
            return self
        if self.is_successor_pure():
            return self.head()
        return Motif(Motif(Motif(Motif())), self)  # pred-pattern

    def add(self, b):
        if self.is_zero_pure():
            return b
        if self.is_successor_pure():
            return Motif(self.head().add(b))  # succ(n)+m → succ(n+m)
        return Motif(Motif(), Motif(), self, b)  # add marker

    def mult(self, b):
        if self.is_zero_pure():
            return Motif()
        if self.is_successor_pure():
            return b.add(self.head().mult(b))  # succ(n)*m -> m + n*m
        return Motif(Motif(), Motif(), Motif(), self, b)  # mult marker

    # ---------- structural analysis tools ----------

    def depth(self):
        if self.is_void():
            return 0
        return 1 + max(
            (s.depth() if isinstance(s, Motif) else 0) for s in self.structure
        )

    def count_nodes(self):
        return 1 + sum(s.count_nodes()
                       for s in self.structure if isinstance(s, Motif))

    def find_shared(self):
        seen = set()
        shared = []

        def scan(m):
            mid = id(m)
            if mid in seen:
                shared.append(m)
                return
            seen.add(mid)
            for c in m.structure:
                if isinstance(c, Motif):
                    scan(c)

        scan(self)
        return shared


# ---------- constructor and primitives ----------


def μ(*xs):
    for x in xs:
        if isinstance(x, str):
            raise ValueError("Strings forbidden in RCX-π core.")
    return Motif(*xs)


VOID = μ()  # 0
UNIT = μ(μ())  # 1
