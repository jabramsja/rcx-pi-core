# test_programs_map.py
#
# Sanity checks for map_closure + add1_closure.

from rcx_pi import num, motif_to_int, PureEvaluator
from rcx_pi.programs import map_closure, add1_closure
from rcx_pi.listutils import list_from_py, py_from_list


from rcx_pi import motif_to_int
from rcx_pi.listutils import py_from_list

def _ints_from_list_motif(m):
    """
    Decode a motif list of Peano numbers into Python ints.

    py_from_list may already turn Peano motifs into ints, so we:
      - keep ints as-is
      - use motif_to_int only when elements are still Motifs.
    """
    xs = py_from_list(m)
    out = []
    for x in xs:
        if isinstance(x, int):
            out.append(x)
        else:
            out.append(motif_to_int(x))
    return out


def test_map_add1_over_nonempty_list():
    ev = PureEvaluator()

    xs = list_from_py([num(1), num(2), num(3)])
    prog = map_closure(add1_closure())

    out = ev.run(prog, xs)
    assert _ints_from_list_motif(out) == [2, 3, 4]


def test_map_add1_over_empty_list():
    ev = PureEvaluator()

    xs = list_from_py([])
    prog = map_closure(add1_closure())

    out = ev.run(prog, xs)
    assert _ints_from_list_motif(out) == []