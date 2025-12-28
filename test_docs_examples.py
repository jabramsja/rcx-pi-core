"""
Smoke tests for examples referenced in the RCX-π paper.

These are deliberately minimal and only rely on APIs that actually exist
in the current rcx_pi package. The goal is:

- 00-overview: basic number round-trip, classification call, and pretty-print.
- Numbers: pred/succ sanity.
- Addition: simple structural addition check.

We *don't* currently test list-based examples (like swap_ends_xyz_closure)
because helpers like `list_from_py` are not yet implemented in rcx_pi.
Those can be added later once the API stabilises.
"""

import pytest

from rcx_pi import (
    num,
    motif_to_int,
    classify_motif,
    pretty_motif,
    zero,
    succ,
    pred,
    add,
    Motif,
)


def test_00_overview_example():
    """
    00-overview: basic number round-trip and tagging.

    - Build 3 with num(3)
    - Convert back with motif_to_int
    - Call classify_motif (API currently returns a Motif tag wrapper)
    - Pretty-print should mention "3" somewhere
    """
    n3 = num(3)

    # Round-trip through the integer view
    assert motif_to_int(n3) == 3

    # Classification: current rcx_pi.classify_motif returns a Motif,
    # not a (tag, core) pair as the paper's first draft suggests.
    tagged = classify_motif(n3)
    assert isinstance(tagged, Motif)

    # Pretty-print should contain "3" somewhere
    rendered = pretty_motif(n3)
    assert "3" in rendered


def test_pred_of_succ_zero():
    """
    Basic numbers sanity: pred(succ(0)) == 0 in the integer view.
    """
    z = zero()
    one = succ(z)
    back_to_zero = pred(one)

    assert motif_to_int(z) == 0
    assert motif_to_int(one) == 1
    assert motif_to_int(back_to_zero) == 0


def test_addition_example():
    """
    Simple addition example: add(2, 3) = 5 as motifs.
    """
    two = num(2)
    three = num(3)

    five = add(two, three)

    assert motif_to_int(five) == 5
    # Pretty-print should at least mention "5"
    pretty = pretty_motif(five)
    assert "5" in pretty