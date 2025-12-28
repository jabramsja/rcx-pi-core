# test_numbers_core.py
"""
Core invariants for RCX-π numbers and lists.

These tests are intentionally small and structural:
- Peano num <-> motif_to_int round-trip
- succ / pred sanity
- add correctness on a small grid
- list_from_py / py_from_list round-trip for various lengths
"""

import pytest
from rcx_pi import (
    Motif,
    VOID,
    num,
    succ,
    pred,
    add,
    motif_to_int,
    list_from_py,
    py_from_list,
    is_list_motif,
)


# ---------------------------------------------------------------------------
# Peano number invariants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(0, 16))
def test_peano_roundtrip(n: int) -> None:
    m = num(n)
    assert isinstance(m, Motif)
    assert motif_to_int(m) == n


@pytest.mark.parametrize("n", range(0, 10))
def test_succ_pred_inverses_for_positive(n: int) -> None:
    m = num(n)
    sp = succ(m)
    # pred(succ(n)) = n for n >= 0
    assert motif_to_int(pred(sp)) == n


def test_pred_of_zero_is_none() -> None:
    z = num(0)
    assert pred(z) is None


@pytest.mark.parametrize("a", range(0, 8))
@pytest.mark.parametrize("b", range(0, 8))
def test_addition_grid(a: int, b: int) -> None:
    ma = num(a)
    mb = num(b)
    res = add(ma, mb)
    assert motif_to_int(res) == a + b


# ---------------------------------------------------------------------------
# List invariants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("py_list", [
    [],
    [0],
    [1],
    [0, 1],
    [1, 2, 3],
    [5, 0, 7, 9],
])
def test_list_roundtrip(py_list) -> None:
    m = list_from_py(py_list)
    assert is_list_motif(m)
    back = py_from_list(m)
    assert back == py_list


def test_list_roundtrip_longer() -> None:
    data = list(range(10))
    m = list_from_py(data)
    assert is_list_motif(m)
    back = py_from_list(m)
    assert back == data