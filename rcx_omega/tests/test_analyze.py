from rcx_pi import new_evaluator, VOID
from rcx_omega.engine.trace import trace_reduce
from rcx_omega.analyze import analyze_trace


def test_analyze_fixedpoint_void():
    ev = new_evaluator()
    tr = trace_reduce(ev, VOID, max_steps=8)
    an = analyze_trace(tr)
    assert an.kind == "fixedpoint"
    assert an.period is None
