# test_program_registry.py

from rcx_pi import PureEvaluator, num
from rcx_pi.listutils import list_from_py, py_from_list
from rcx_pi.program_registry import (
    list_program_names,
    has_program,
    get_program,
)


def test_registry_exposes_succ_list():
    names = list_program_names()
    assert "succ-list" in names
    assert has_program("succ-list")
    assert not has_program("definitely-not-a-real-program")


def test_registry_runs_succ_list_program():
    ev = PureEvaluator()
    prog = get_program("succ-list")

    xs = list_from_py([num(0), num(1), num(2), num(3)])
    out = ev.run(prog, xs)

    # py_from_list decodes Peano motifs back to ints
    assert py_from_list(out) == [1, 2, 3, 4]
