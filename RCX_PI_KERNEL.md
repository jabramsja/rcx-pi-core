RCX-π Kernel Overview (tag: rcx-pi-green-002)
Status: 123 passed, 1 skipped
Layer: Core RCX-π minimal, stable baseline
Purpose: A self-consistent execution nucleus for RCX, from which higher layers can grow.

This document describes exactly what exists today and is verified by tests.
This is now the canonical ground truth snapshot.

⸻

	1.	Motifs

Everything in RCX-π is a Motif (μ-tree).
μ(…) is the single constructor.
VOID = zero / base.
UNIT = trivial Motif.

All structure (numbers, lists, closures, bytecode, projections) is encoded through nested Motifs.
There are no other primitives.

⸻

	2.	Evaluator

PureEvaluator executes Motifs and hosted programs.

Key features:
• reduce motifs structurally
• run closures stored inside meta[“fn”]
• list helpers (ensure_list, head, tail, cons, nil)

Evaluator is the execution engine of RCX-π.

⸻

	3.	Numbers (Peano over VOID)

num(n) builds successors:
0 = VOID
1 = μ()
2 = μ(μ())
3 = μ(μ(μ()))
…

motif_to_int converts back to integer.
add(a,b) performs integer add with re-encoding.

All number tests pass.

⸻

	4.	Lists

Encoded as CONS(h,t) motif spines ending in NIL/VOID.

Round-trip API:
list_from_py([1,2,3]) → motif
py_from_list(motif)   → [1,2,3]

is_list_motif verifies shape only.
This is pure structural — no Python lists stored inside motif.

⸻

	5.	Hosted Programs (closures)

Programs are Motifs with meta[“fn”] = (ev,arg)->Motif.

Built-ins currently included:

swap_xy_closure       swap first two list elements
dup_x_closure         duplicate head
rotate_xyz_closure    [x,y,z] → [y,z,x]
swap_ends_xyz_closure swap first+last
reverse_list_closure  reverse list
append_lists_closure  append two lists

Composition layer:

seq_closure(p,q)      run p then q
map_closure(f)        map f over motif list
add1_closure          Peano increment

⸻

	6.	Bytecode VM

Motif-encoded stack machine.

Opcodes:
OP_PUSH_CONST
OP_ADD
OP_HALT
OP_PUSH_NIL
OP_CONS
OP_HEAD
OP_TAIL

make_instr(op,arg) encodes instruction.
bytecode_closure(list_of_instr) builds runnable program.

Works as tested:
Push → Push → Add → Halt → returns result.

⸻

	7.	Projection System

Pattern matching on Motif structure.

Exports:
var_x, var_y
make_projection_closure(pattern,body)
activate(func,arg)

Demo case in test_projection.py reproduces structural swap (x,y)->(y,x).
Projection output decoded using pair_motif_to_ints.

Projection is stable, test-verified.

⸻

	8.	Program Registry

register_program(name,program)
get_program(name)

Allows lookup and running programs by human-readable identifier.

Registry tests pass.

⸻

	9.	First Named RCX Program

succ-list = map(add1)
Transforms:
[0,1,2,3] → [1,2,3,4]

Marked with meta[“rcx_name”] = “succ-list”.
Demonstrated in demo_rcx_pi.py.

This is the first fully named/registered RCX layer program.

⸻

	10.	Kernel Snapshot Summary

Current state: rcx-pi-green-002
Test status: 123 passed, 1 skipped

Features complete:
✔ Motif core
✔ Evaluator
✔ Peano numbers
✔ Structural lists
✔ Program closures
✔ Map/Seq composition
✔ Bytecode interpreter
✔ Projection matching
✔ Program registry
✔ succ-list named program

This file is the stable kernel definition for downstream RCX-Ω layers.
