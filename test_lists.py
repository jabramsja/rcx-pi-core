# test_lists.py

from rcx_pi import list_from_py, py_from_list, new_evaluator, swap_ends_xyz_closure

def test_swap_ends():
    ev = new_evaluator()
    xs = list_from_py([1,2,3,4])

    program = swap_ends_xyz_closure()
    out = ev.run(program, xs)

    assert py_from_list(out) == [4,2,3,1]