# test_bytecode_core.py

from rcx_pi import num, motif_to_int, new_evaluator, list_from_py
from rcx_pi.programs import (
    OP_PUSH_CONST, OP_ADD, OP_HALT,
    make_instr, bytecode_closure,
)

def run(bytecode):
    ev = new_evaluator()
    prog = bytecode_closure(bytecode)
    empty = list_from_py([])
    return ev.run(prog, empty)

def test_bytecode_add():
    n2 = num(2)
    n3 = num(3)

    bc = list_from_py([
        make_instr(OP_PUSH_CONST, n2),
        make_instr(OP_PUSH_CONST, n3),
        make_instr(OP_ADD,        n2),   # arg ignored
        make_instr(OP_HALT,       n3),   # arg ignored
    ])

    assert motif_to_int(run(bc)) == 5