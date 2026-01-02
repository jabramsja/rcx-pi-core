# test_lists.py
"""
Tests for list-based programs in rcx_pi.

Currently:
- swap_ends_xyz_closure
- reverse_list_closure
"""

from rcx_pi import list_from_py, py_from_list, new_evaluator, swap_ends_xyz_closure
from rcx_pi.programs import reverse_list_closure


def test_swap_ends():
    ev = new_evaluator()
    xs = list_from_py([1, 2, 3, 4])

    program = swap_ends_xyz_closure()
    out = ev.run(program, xs)

    assert py_from_list(out) == [4, 2, 3, 1]


def test_reverse_list_basic():
    ev = new_evaluator()
    program = reverse_list_closure()

    # Empty list
    xs0 = list_from_py([])
    out0 = ev.run(program, xs0)
    assert py_from_list(out0) == []

    # Single element
    xs1 = list_from_py([42])
    out1 = ev.run(program, xs1)
    assert py_from_list(out1) == [42]

    # Multiple elements
    xs2 = list_from_py([1, 2, 3, 4])
    out2 = ev.run(program, xs2)
    assert py_from_list(out2) == [4, 3, 2, 1]
