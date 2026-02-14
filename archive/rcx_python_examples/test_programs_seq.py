# test_programs_seq.py
from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.programs import (
    swap_ends_xyz_closure,
    reverse_list_closure,
    seq_closure,
)
from rcx_pi.listutils import list_from_py, py_from_list


def _run_prog(prog, arg_py_list):
    """
    Helper: run an already-constructed program closure `prog`
    on a Python list argument (converted to motif list), and
    return the resulting Python list via py_from_list.
    """
    ev = PureEvaluator()
    arg_m = list_from_py(arg_py_list)
    out_m = ev.run(prog, arg_m)
    return py_from_list(out_m)


def test_seq_reverse_reverse_is_identity():
    # reverse ∘ reverse should be the identity on lists
    xs = [1, 2, 3, 4]

    rev1 = reverse_list_closure()
    rev2 = reverse_list_closure()
    seq_prog = seq_closure(rev1, rev2)

    out = _run_prog(seq_prog, xs)
    assert out == xs


def test_seq_swap_then_reverse():
    # Check that composition actually changes behavior
    # in a non-trivial way: swap ends, then reverse.
    xs = [1, 2, 3, 4]  # swap ends -> [4, 2, 3, 1] then reverse -> [1, 3, 2, 4]

    swap = swap_ends_xyz_closure()
    rev = reverse_list_closure()
    seq_prog = seq_closure(swap, rev)

    out = _run_prog(seq_prog, xs)
    assert out == [1, 3, 2, 4]


def test_seq_nested_three_programs():
    # seq(seq(p, q), r) should work as expected.
    xs = [1, 2, 3]

    swap = swap_ends_xyz_closure()
    rev = reverse_list_closure()

    # Compose (swap then reverse) then reverse again.
    # Effectively: swap ends once.
    first = seq_closure(swap, rev)
    pipeline = seq_closure(first, rev)

    out = _run_prog(pipeline, xs)

    # Manually: xs = [1,2,3]
    # swap ends -> [3,2,1]
    # reverse   -> [1,2,3]
    # reverse   -> [3,2,1]
    assert out == [3, 2, 1]
