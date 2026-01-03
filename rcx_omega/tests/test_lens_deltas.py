from rcx_pi import new_evaluator, μ, VOID
from rcx_omega.engine.lens import trace_reduce_with_stats


def test_lens_deltas_void():
    ev = new_evaluator()
    lr = trace_reduce_with_stats(ev, VOID, max_steps=4)
    assert len(lr.stats.deltas) >= 1
    assert lr.stats.deltas[0].delta_nodes == 0
    assert lr.stats.deltas[0].delta_depth == 0


def test_lens_deltas_nested_mu():
    ev = new_evaluator()
    x = μ(μ())
    lr = trace_reduce_with_stats(ev, x, max_steps=4)
    ds = lr.stats.deltas
    assert ds[0].nodes == 2
    assert ds[0].depth == 2
