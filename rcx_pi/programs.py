# rcx_pi/programs.py
"""
RCX-π "program" closures for the current core.

These are *hosted* programs: each constructor returns a Motif whose
`.meta["fn"]` is a Python callable of the form

    fn(evaluator, arg: Motif) -> Motif

The evaluator (PureEvaluator) provides a small helper surface:

    ev.ensure_list(m)   - check list shape (raises on failure)
    ev.head(m)          - list head
    ev.tail(m)          - list tail
    ev.cons(h, t)       - build CONS cell
    ev.nil()            - NIL

For convenience, we also use list roundtrip helpers from `listutils`:

    list_from_py, py_from_list

Right now these programs are deliberately simple and structural:

    - swap_xy_closure          : swap a pair [x, y] -> [y, x]
    - dup_x_closure            : duplicate first element [x, ...] -> [x, x, ...]
    - rotate_xyz_closure       : rotate triple [x, y, z] -> [y, z, x]
    - swap_ends_xyz_closure    : swap first and last in a list
    - reverse_list_closure     : reverse an entire list
    - append_lists_closure     : append two lists xs ++ ys

Plus a tiny stack-based bytecode interpreter exposed via bytecode_closure.
"""

from __future__ import annotations

from typing import Callable

from rcx_pi.core.motif import Motif, μ, VOID
from rcx_pi.listutils import (
    list_from_py,
    py_from_list,
    NIL,
    CONS,
)

# ============================
# Bytecode opcodes (host-level)
# ============================

# Represent opcodes as small Python ints.
# They are encoded as Peano motifs when building instructions.

OP_PUSH_CONST = 0  # push a constant motif
OP_ADD = 1  # pop 2 Peano numbers, push their sum
OP_HALT = 2  # stop execution

OP_PUSH_NIL = 3  # push empty list NIL()
OP_CONS = 4  # stack [..., xs, x] -> [..., CONS(x, xs)]
OP_HEAD = 5  # pop list xs, push head(xs)
OP_TAIL = 6  # pop list xs, push tail(xs)


def make_instr(op: int, arg: Motif) -> Motif:
    """
    Build a single instruction motif [opcode, arg].

    `op` is a Python int -> encoded to Peano motif automatically via num().
    `arg` is a motif (typically a Peano number motif for tests).
    """
    from rcx_pi import num

    op_motif = num(op)
    return CONS(op_motif, CONS(arg, NIL()))


# ---------------------------------------------------------------------------
# Small structural utilities used by programs
# ---------------------------------------------------------------------------


def _append_lists_struct(ev, xs: Motif, ys: Motif) -> Motif:
    """
    Pure structural append of two motif lists:

        result = xs ++ ys

    Both xs and ys must be list-shaped (spine of CONS cells ending in VOID).
    """
    ev.ensure_list(xs)
    ev.ensure_list(ys)

    # Empty left list: result is ys.
    if xs == VOID:
        return ys

    # Non-empty: xs = CONS(h, t)  ⇒  result = CONS(h, append(t, ys))
    h = ev.head(xs)
    t = ev.tail(xs)
    return ev.cons(h, _append_lists_struct(ev, t, ys))


def _make_closure(fn: Callable[[object, Motif], Motif]) -> Motif:
    """
    Wrap a Python function in a Motif "closure".

    The evaluator only cares that `program.meta["fn"]` exists and is callable.
    The underlying structure of the motif is irrelevant for now, so we use
    a simple nullary μ() node.
    """
    m = μ()
    setattr(m, "meta", {"fn": fn})
    return m


def _to_py_list_strict(ev, xs: Motif, ctx: str) -> list[Motif]:
    """
    Convert a motif list to a Python list, raising TypeError on failure.

    Elements are left as Motifs or whatever they already are; we treat them
    opaquely here.
    """
    ev.ensure_list(xs)
    py = py_from_list(xs)
    if py is None:
        raise TypeError(f"{ctx}: expected list motif")
    return list(py)


# ---------------------------------------------------------------------------
# Basic combinator-ish list programs
# ---------------------------------------------------------------------------


def swap_xy_closure() -> Motif:
    """
    Closure that expects a 2-element list [x, y] and returns [y, x].

    If the input is not a 2-element list, it raises TypeError.
    """

    def _impl(ev, arg: Motif) -> Motif:
        items = _to_py_list_strict(ev, arg, "swap_xy_closure")
        if len(items) != 2:
            raise TypeError("swap_xy_closure expects a 2-element list [x, y]")
        x, y = items
        return list_from_py([y, x])

    return _make_closure(_impl)


def dup_x_closure() -> Motif:
    """
    Closure that duplicates the head of a list:

        [x, a, b, ...]  ->  [x, x, a, b, ...]

    If the list is empty, returns the empty list unchanged.
    """

    def _impl(ev, arg: Motif) -> Motif:
        items = _to_py_list_strict(ev, arg, "dup_x_closure")
        if not items:
            return arg
        x = items[0]
        return list_from_py([x, x] + items[1:])

    return _make_closure(_impl)


def rotate_xyz_closure() -> Motif:
    """
    Closure that rotates a triple:

        [x, y, z] -> [y, z, x]

    For lists of length != 3, we raise TypeError to avoid silent weirdness.
    """

    def _impl(ev, arg: Motif) -> Motif:
        items = _to_py_list_strict(ev, arg, "rotate_xyz_closure")
        if len(items) != 3:
            raise TypeError(
                "rotate_xyz_closure expects a 3-element list [x, y, z]")
        x, y, z = items
        return list_from_py([y, z, x])

    return _make_closure(_impl)


# ---------------------------------------------------------------------------
# swap_ends & reverse – used in tests and demos
# ---------------------------------------------------------------------------


def swap_ends_xyz_closure() -> Motif:
    """
    Swap the first and last elements of a list.

        [a, b, c, d] -> [d, b, c, a]
        [x]          -> [x]        (unchanged)
        []           -> []         (unchanged)
    """

    def _impl(ev, xs: Motif) -> Motif:
        items = _to_py_list_strict(ev, xs, "swap_ends_xyz_closure")
        if len(items) < 2:
            return xs
        items[0], items[-1] = items[-1], items[0]
        return list_from_py(items)

    return _make_closure(_impl)


def reverse_list_closure() -> Motif:
    """
    Reverse the entire list:

        [1, 2, 3, 4] -> [4, 3, 2, 1]
        []           -> []
    """

    def _impl(ev, xs: Motif) -> Motif:
        items = _to_py_list_strict(ev, xs, "reverse_list_closure")
        items.reverse()
        return list_from_py(items)

    return _make_closure(_impl)


# ---------------------------------------------------------------------------
# Append two lists
# ---------------------------------------------------------------------------


def append_lists_closure() -> Motif:
    """
    Return a closure that appends two lists encoded as a pair:

        input  = [xs, ys]   (as a motif list of length 2)
        output = xs ++ ys   (motif list)
    """

    def _impl(ev, arg: Motif) -> Motif:
        pair = ev.ensure_list(arg)

        # Destructure [xs, ys]
        xs = ev.head(pair)
        rest = ev.tail(pair)
        ys = ev.head(rest)

        # Perform structural append.
        return _append_lists_struct(ev, xs, ys)

    return _make_closure(_impl)


# ---------------------------------------------------------------------------
# Program composition: seq(p, q)
# ---------------------------------------------------------------------------


def seq_closure(p: Motif, q: Motif) -> Motif:
    """
    Compose two already-constructed program closures p and q.

        seq_closure(p, q)  is a new program r such that

            r(arg) = q(p(arg))

    Here p and q are *program motifs* (closures) created by other
    *_closure() constructors, not Python functions.

    Example usage:

        swap = swap_xy_closure()
        dup  = dup_x_closure()
        pipe = seq_closure(swap, dup)

        # Then in an evaluator:
        #   result = ev.run(pipe, some_arg)
    """

    def _impl(ev, arg: Motif) -> Motif:
        # Run p then q using the same evaluator.
        mid = ev.run(p, arg)
        return ev.run(q, mid)

    return _make_closure(_impl)


# ---------------------------------------------------------------------------
# Higher-order-ish: map over a list with a closure
# ---------------------------------------------------------------------------


def map_closure(func_closure: Motif) -> Motif:
    """
    Map a unary function closure over a motif list:

        input:  [x0, x1, x2, ...]
        output: [f(x0), f(x1), f(x2), ...]

    `func_closure` is a Motif with meta["fn"] = (ev, arg) -> Motif.
    """

    from rcx_pi.core.motif import VOID

    def _impl(ev, xs: Motif) -> Motif:
        # Ensure the input is list-shaped.
        xs_list = ev.ensure_list(xs)

        out_items = []
        cur = xs_list

        # Walk the motif list structurally, *without* decoding elements.
        while cur is not VOID:
            x = ev.head(cur)  # this is a Motif element
            y = ev.run(func_closure, x)
            out_items.append(y)
            cur = ev.tail(cur)

        # Rebuild the result list as a motif list.
        return list_from_py(out_items)

    return _make_closure(_impl)


def add1_closure() -> Motif:
    """
    Closure that adds 1 (Peano) to a single number.

    Given n (as a Peano motif), returns n + 1.
    """
    from rcx_pi import add, num

    def _impl(ev, n: Motif) -> Motif:
        return add(n, num(1))

    return _make_closure(_impl)


def succ_list_program() -> Motif:
    """
    RCX-π named program:
        succ-list : [n0, n1, ...] -> [n0+1, n1+1, ...]

    Implemented as map(add1) over a motif list of Peano numbers.
    """
    # Build the underlying closure: map(add1)
    mapper = map_closure(add1_closure())

    # Attach a small RCX-facing name tag so higher layers
    # can treat this as a "program cell".
    meta = getattr(mapper, "meta", {}) or {}
    meta.setdefault("rcx_name", "succ-list")
    mapper.meta = meta

    return mapper


# ============================
# Bytecode interpreter support
# ============================


def bytecode_closure(bytecode: Motif) -> Motif:
    """
    Wrap a bytecode motif (list of [opcode, arg]) as a runnable program.

    The resulting motif has meta['fn'] = implementation that interprets
    the bytecode. The argument to the program is the initial stack,
    encoded as a motif list (top of stack is the *last* element).
    """

    def _impl(ev, stack_motif: Motif) -> Motif:
        return _eval_bytecode(ev, bytecode, stack_motif)

    prog = μ()
    prog.meta = {"fn": _impl}
    return prog


def _eval_bytecode(ev, bytecode_motif: Motif, stack_motif: Motif) -> Motif:
    """
    Tiny stack-based bytecode interpreter.

    - `bytecode_motif` is a motif list of instructions, each [opcode, arg].
    - `stack_motif` is a motif list representing the initial stack
      (top of stack is the last element).
    - Returns the top-of-stack motif after execution, or VOID if empty.

    For now we support:
      OP_PUSH_CONST: push the arg motif.
      OP_ADD       : pop 2 numbers (Peano motifs), push their sum.
      OP_HALT      : stop iterating and return top of stack.
      OP_PUSH_NIL  : push NIL() list.
      OP_CONS      : stack [..., xs, x] -> [..., CONS(x, xs)].
      OP_HEAD      : pop xs, push head(xs).
      OP_TAIL      : pop xs, push tail(xs).
    """
    # Local imports to avoid circular imports at module import time.
    from rcx_pi import add, num, motif_to_int
    from rcx_pi.listutils import py_from_list, NIL, CONS
    from rcx_pi.core.motif import Motif, VOID

    # Decode only the *list structure* of the bytecode into Python lists.
    instructions_py = py_from_list(bytecode_motif)

    # Decode the initial stack motif as a Python list (top-of-stack is last).
    stack_py = py_from_list(stack_motif)

    stack: list[Motif | int] = []
    if stack_py is not None:
        for item in stack_py:
            if isinstance(item, Motif):
                stack.append(item)
            else:
                # If py_from_list converted a Peano motif to an int, re-box it.
                stack.append(num(int(item)))

    for instr in instructions_py:
        # Each instr is a motif list [opcode, arg] → Python list [opcode_val,
        # arg_val]
        pair = py_from_list(instr)
        if len(pair) != 2:
            raise TypeError("Bytecode instruction must be [opcode, arg]")

        opcode_val, arg_val = pair

        # ----- Decode opcode to a small Python int -----
        if isinstance(opcode_val, Motif):
            op_code = motif_to_int(opcode_val)
            if op_code is None:
                raise TypeError("Opcode motif must be a Peano number")
        else:
            # Already a Python int (due to py_from_list); accept it.
            op_code = int(opcode_val)

        # ----- Execute -----
        if op_code == OP_PUSH_CONST:
            # Ensure we push a *motif* onto the stack.
            if isinstance(arg_val, Motif):
                pushed = arg_val
            else:
                pushed = num(int(arg_val))
            stack.append(pushed)

        elif op_code == OP_ADD:
            if len(stack) < 2:
                raise RuntimeError("OP_ADD requires at least 2 stack items")

            b = stack.pop()
            a = stack.pop()

            if not isinstance(a, Motif):
                a = num(int(a))
            if not isinstance(b, Motif):
                b = num(int(b))

            stack.append(add(a, b))

        elif op_code == OP_HALT:
            break

        elif op_code == OP_PUSH_NIL:
            stack.append(NIL())

        elif op_code == OP_CONS:
            if len(stack) < 2:
                raise RuntimeError("OP_CONS requires at least 2 stack items")

            x = stack.pop()  # element
            xs = stack.pop()  # list

            if not isinstance(xs, Motif):
                raise TypeError("OP_CONS expects a list motif as xs")

            # Just trust caller that xs is list-shaped; we can tighten later.
            stack.append(CONS(x, xs))

        elif op_code == OP_HEAD:
            if not stack:
                raise RuntimeError("OP_HEAD requires a list on the stack")

            xs = stack.pop()
            if not isinstance(xs, Motif):
                raise TypeError("OP_HEAD expects a list motif")

            xs_list = ev.ensure_list(xs)
            stack.append(ev.head(xs_list))

        elif op_code == OP_TAIL:
            if not stack:
                raise RuntimeError("OP_TAIL requires a list on the stack")

            xs = stack.pop()
            if not isinstance(xs, Motif):
                raise TypeError("OP_TAIL expects a list motif")

            xs_list = ev.ensure_list(xs)
            stack.append(ev.tail(xs_list))

        else:
            raise ValueError(f"Unknown bytecode opcode: {op_code!r}")

    # Result is top-of-stack motif, or VOID if stack empty.
    return stack[-1] if stack else VOID


# ---------------------------------------------------------------------------
# Misc helper – "activate" convenience
# ---------------------------------------------------------------------------


def activate(ev, program: Motif, arg: Motif) -> Motif:
    """
    Convenience wrapper:

        activate(ev, prog, arg) ≡ ev.run(prog, arg)

    Backwards-compat: if prog is a tagged program block / seq block,
    unwrap and execute structurally.
    """
    # Tagged program blocks / seq blocks (legacy)
    try:
        if is_program_block(program) or _is_seq_block(program):
            return run_program_block(ev, program, arg)
    except Exception:
        # If anything about shape/parsing is weird, fall back to native run
        pass

    # Native closure motifs
    return ev.run(program, arg)

# ---------------------------------------------------------------------------
# Backwards-compatibility shims for older rcx_python_examples/test_programs.py
# ---------------------------------------------------------------------------

# Historically, some examples treated "programs" as tagged motif blocks.
# The current core uses closure motifs (meta["fn"]). To keep both working,
# we provide a minimal "program block" representation:
#
#   program_block := [PROGRAM_TAG, closure]
#   seq_block     := [SEQ_TAG, [p_block, q_block]]
#
# wrap_program(closure) -> program_block
# is_program_block(x)   -> bool
# seq(p_block, q_block) -> seq_block
#
# And we also provide an *evaluator-friendly* way to run them by unwrapping
# to closures when needed.

PROGRAM_TAG = "program"
SEQ_TAG = "seq"


def wrap_program(prog: Motif) -> Motif:
    """Wrap a closure-motif as a tagged 'program block' motif."""
    return list_from_py([PROGRAM_TAG, prog])


def is_program_block(m: Motif) -> bool:
    """True iff m is a tagged program block [PROGRAM_TAG, <closure>]."""
    py = py_from_list(m)
    return bool(
        py is not None
        and len(py) == 2
        and py[0] == PROGRAM_TAG
    )


def _unwrap_program_block(m: Motif) -> Motif:
    """Extract closure from [PROGRAM_TAG, closure]. Raise on invalid shape."""
    py = py_from_list(m)
    if py is None or len(py) != 2 or py[0] != PROGRAM_TAG:
        raise TypeError("expected program block [PROGRAM_TAG, closure]")
    closure = py[1]
    if not isinstance(closure, Motif):
        # Some list roundtrips might return non-Motif elements; be strict.
        raise TypeError("program block must contain a Motif closure")
    return closure


def seq(p_block: Motif, q_block: Motif) -> Motif:
    """
    Build a tagged seq block.

    Note: this is a *structural* tagged representation for tests/examples.
    """
    return list_from_py([SEQ_TAG, list_from_py([p_block, q_block])])


def _is_seq_block(m: Motif) -> bool:
    py = py_from_list(m)
    return bool(py is not None and len(py) == 2 and py[0] == SEQ_TAG)


def run_program_block(ev, block: Motif, arg: Motif) -> Motif:
    """
    Execute either a program block or a seq block.

    - program block: [PROGRAM_TAG, closure] => ev.run(closure, arg)
    - seq block:     [SEQ_TAG, [p_block, q_block]] => run q(run p(arg))
    """
    if is_program_block(block):
        closure = _unwrap_program_block(block)
        return ev.run(closure, arg)

    if _is_seq_block(block):
        py = py_from_list(block)
        pair = py_from_list(py[1]) if py and isinstance(py[1], Motif) else None
        if pair is None or len(pair) != 2:
            raise TypeError("seq block must be [SEQ_TAG, [p_block, q_block]]")
        p_block, q_block = pair[0], pair[1]
        if not isinstance(p_block, Motif) or not isinstance(q_block, Motif):
            raise TypeError("seq children must be Motifs")
        mid = run_program_block(ev, p_block, arg)
        return run_program_block(ev, q_block, mid)

    raise TypeError("unknown program block shape")


