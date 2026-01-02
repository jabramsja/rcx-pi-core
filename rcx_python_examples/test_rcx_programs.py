# test_rcx_programs.py

from rcx_pi.core.motif import Motif
from rcx_pi import PureEvaluator, num, motif_to_int
from rcx_pi.listutils import list_from_py, py_from_list
from rcx_pi.programs import succ_list_program


def _ints_from_list_motif(m: Motif):
    """
    Decode a motif list of Peano numbers into plain Python ints.

    Handles both:
      - elements that are still Motif Peano numbers
      - elements already decoded to Python ints by py_from_list
    """
    xs = py_from_list(m)
    out: list[int | None] = []

    from rcx_pi.core.motif import Motif as MotifType

    for x in xs:
        if isinstance(x, MotifType):
            v = motif_to_int(x)
            out.append(v)
        else:
            # py_from_list already gave us a plain int
            out.append(int(x))

    return out


def test_succ_list_program_basic():
    ev = PureEvaluator()
    prog = succ_list_program()

    xs = list_from_py([num(0), num(1), num(2), num(3)])
    out = ev.run(prog, xs)

    assert _ints_from_list_motif(out) == [1, 2, 3, 4]
