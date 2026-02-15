"""
RCX-Ω: motif parser (staging)

Parses a minimal textual Motif literal for μ-only trees:
  μ()
  μ(μ())
  μ( μ(), μ(μ()) )

Also accepts "mu" as an alias for "μ".

This is intentionally small:
- It does NOT parse atoms (UNIT, symbols, numbers, etc) yet.
- If you need atoms, we can extend later without breaking this core grammar.
"""

from __future__ import annotations

from dataclasses import dataclass

from rcx_pi import μ


@dataclass(frozen=True)
class _Cursor:
    s: str
    i: int = 0

    def eof(self) -> bool:
        return self.i >= len(self.s)

    def peek(self) -> str:
        return "" if self.eof() else self.s[self.i]

    def consume(self, n: int = 1) -> "_Cursor":
        return _Cursor(self.s, self.i + n)

    def skip_ws(self) -> "_Cursor":
        i = self.i
        while i < len(self.s) and self.s[i].isspace():
            i += 1
        return _Cursor(self.s, i)

    def expect(self, ch: str) -> "_Cursor":
        c = self.skip_ws()
        if c.eof() or c.s[c.i] != ch:
            got = "EOF" if c.eof() else repr(c.s[c.i])
            raise ValueError(f"Expected {ch!r} at pos {c.i}, got {got}")
        return _Cursor(c.s, c.i + 1)


def parse_motif(text: str):
    """
    Parse a μ-only motif literal into an rcx_pi Motif.
    Raises ValueError on invalid syntax.
    """
    c = _Cursor(text).skip_ws()
    node, c2 = _parse_mu_expr(c)
    c2 = c2.skip_ws()
    if not c2.eof():
        raise ValueError(f"Trailing junk at pos {c2.i}: {c2.s[c2.i :]!r}")
    return node


def _parse_mu_expr(c: _Cursor):
    c = c.skip_ws()

    # accept "μ" or "mu"
    if c.s.startswith("μ", c.i):
        c = c.consume(1)
    elif c.s.startswith("mu", c.i):
        c = c.consume(2)
    else:
        raise ValueError(f"Expected 'μ' or 'mu' at pos {c.i}")

    c = c.expect("(")
    c = c.skip_ws()

    # empty args: μ()
    if c.peek() == ")":
        c = c.expect(")")
        return μ(), c

    # otherwise: μ(arg (, arg)*)
    kids = []
    while True:
        child, c = _parse_mu_expr(c)
        kids.append(child)
        c = c.skip_ws()
        if c.peek() == ",":
            c = c.consume(1)
            continue
        break

    c = c.expect(")")
    return μ(*kids), c
