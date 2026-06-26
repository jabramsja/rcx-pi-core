"""Test helpers for StructuralNumbers numerals."""


def encode_positive(p: int) -> dict:
    """Encode a host int p >= 1 as a binary-positional positive numeral."""
    assert p >= 1
    lower_bits = []
    while p > 1:
        lower_bits.append(p & 1)
        p >>= 1
    node = {"xH": None}
    for bit in reversed(lower_bits):
        node = {"xI": node} if bit else {"xO": node}
    return node


def sn(n: int) -> dict:
    """Encode a host int as a StructuralNumbers Mu numeral."""
    if n == 0:
        return {"_num": None}
    if n > 0:
        return {"_num": encode_positive(n)}
    return {"_num": {"neg": encode_positive(-n)}}


SN_ZERO = sn(0)
SN_ONE = sn(1)
