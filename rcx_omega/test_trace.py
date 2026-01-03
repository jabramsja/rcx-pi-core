from rcx_pi import new_evaluator, μ, VOID


def test_trace_reduce_converges_on_void():
    ev = new_evaluator()
    x = VOID

    from rcx_omega.trace import trace_reduce

    tr = trace_reduce(ev, x, max_steps=8)
    assert tr.result == VOID
    assert len(tr.steps) >= 1
    assert tr.steps[0].value == VOID


def test_trace_reduce_records_progress():
    ev = new_evaluator()

    # A trivial motif that should be stable under reduce in current π kernel
    x = μ()

    from rcx_omega.trace import trace_reduce

    tr = trace_reduce(ev, x, max_steps=8)
    assert tr.steps[0].value == x
    assert tr.result == x
