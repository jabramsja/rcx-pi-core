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

def test_bytecode_build_list_and_head():
    from rcx_pi import num, motif_to_int
    from rcx_pi.listutils import py_from_list
    from rcx_pi.engine.evaluator_pure import PureEvaluator
    from rcx_pi.programs import (
        OP_PUSH_CONST,
        OP_PUSH_NIL,
        OP_CONS,
        OP_HEAD,
        OP_HALT,
        make_instr,
        bytecode_closure,
    )

    # We'll build the list [1, 2, 3] structurally using:
    #   PUSH_NIL
    #   PUSH_CONST 3 ; CONS   -> [3]
    #   PUSH_CONST 2 ; CONS   -> [2, 3]
    #   PUSH_CONST 1 ; CONS   -> [1, 2, 3]
    #   HEAD                 -> 1
    n1 = num(1)
    n2 = num(2)
    n3 = num(3)

    bc = list_from_py([
        make_instr(OP_PUSH_NIL, 0),     # arg ignored
        make_instr(OP_PUSH_CONST, n3),
        make_instr(OP_CONS, 0),
        make_instr(OP_PUSH_CONST, n2),
        make_instr(OP_CONS, 0),
        make_instr(OP_PUSH_CONST, n1),
        make_instr(OP_CONS, 0),
        make_instr(OP_HEAD, 0),
        make_instr(OP_HALT, 0),
    ])

    prog = bytecode_closure(bc)
    ev = PureEvaluator()

    result = ev.run(prog, list_from_py([]))
    assert motif_to_int(result) == 1

def test_bytecode_add_with_initial_stack():
    from rcx_pi import num, motif_to_int
    from rcx_pi.listutils import list_from_py
    from rcx_pi.engine.evaluator_pure import PureEvaluator
    from rcx_pi.programs import (
        OP_ADD,
        OP_HALT,
        make_instr,
        bytecode_closure,
    )

    n2 = num(2)
    n3 = num(3)

    # Program:
    #   OP_ADD  (consume two numbers from initial stack)
    #   OP_HALT
    bc = list_from_py([
        make_instr(OP_ADD, 0),   # arg ignored
        make_instr(OP_HALT, 0),  # arg ignored
    ])

    prog = bytecode_closure(bc)
    ev = PureEvaluator()

    # Initial stack is [2, 3] (3 is top of stack).
    initial_stack = list_from_py([n2, n3])

    result = ev.run(prog, initial_stack)
    assert motif_to_int(result) == 5