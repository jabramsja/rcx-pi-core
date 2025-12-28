# test_programs_core.py
"""
Core program tests for RCX-π.

These tests exercise the hosted list programs in rcx_pi.programs:

    - swap_xy_closure
    - dup_x_closure
    - rotate_xyz_closure
    - append_lists_closure
"""

import pytest

from rcx_pi import (
    list_from_py,
    py_from_list,
    new_evaluator,
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    append_lists_closure,
)


def _run(prog_closure, arg_motif):
    ev = new_evaluator()
    prog = prog_closure()
    return ev.run(prog, arg_motif)


def test_swap_xy_basic():
    pair = list_from_py(["x", "y"])
    out = _run(swap_xy_closure, pair)
    assert py_from_list(out) == ["y", "x"]


def test_dup_x_basic():
    xs = list_from_py([1, 2, 3])
    out = _run(dup_x_closure, xs)
    assert py_from_list(out) == [1, 1, 2, 3]


def test_dup_x_empty_is_noop():
    xs = list_from_py([])
    out = _run(dup_x_closure, xs)
    assert py_from_list(out) == []


def test_rotate_xyz_basic():
    triple = list_from_py([1, 2, 3])
    out = _run(rotate_xyz_closure, triple)
    assert py_from_list(out) == [2, 3, 1]


def test_append_lists_basic():
    xs = list_from_py([1, 2])
    ys = list_from_py([3, 4])
    pair = list_from_py([xs, ys])

    out = _run(append_lists_closure, pair)
    assert py_from_list(out) == [1, 2, 3, 4]


def test_append_left_empty():
    xs = list_from_py([])
    ys = list_from_py([3, 4, 5])
    pair = list_from_py([xs, ys])

    out = _run(append_lists_closure, pair)
    assert py_from_list(out) == [3, 4, 5]


def test_append_right_empty():
    xs = list_from_py([1, 2, 3])
    ys = list_from_py([])
    pair = list_from_py([xs, ys])

    out = _run(append_lists_closure, pair)
    assert py_from_list(out) == [1, 2, 3]


def test_append_both_empty():
    xs = list_from_py([])
    ys = list_from_py([])
    pair = list_from_py([xs, ys])

    out = _run(append_lists_closure, pair)
    assert py_from_list(out) == []