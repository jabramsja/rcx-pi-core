from rcx_pi import new_evaluator, μ, VOID
from rcx_omega.engine.lens import trace_reduce_with_stats


def test_trace_reduce_with_stats_void():
    ev = new_evaluator()
    lr = trace_reduce_with_stats(ev, VOID, max_steps=8)
    assert lr.trace.result == VOID
    assert lr.stats.input_stats.nodes == 1
    assert lr.stats.result_stats.nodes == 1


def test_trace_reduce_with_stats_nested_mu():
    ev = new_evaluator()
    x = μ(μ())
    lr = trace_reduce_with_stats(ev, x, max_steps=8)
    assert lr.trace.result == x
    assert lr.stats.input_stats.nodes == 2
    assert lr.stats.input_stats.depth == 2
