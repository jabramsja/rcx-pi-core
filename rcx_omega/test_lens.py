from rcx_pi import new_evaluator, VOID
from rcx_omega.lens import CollectingObserver, evaluate_with_lens


def test_observer_lens_records_trace():
    ev = new_evaluator()
    obs = CollectingObserver(traces=[])

    result = evaluate_with_lens(ev, VOID, observer=obs)

    assert result == VOID
    assert len(obs.traces) == 1
    assert obs.traces[0].result == VOID
    assert len(obs.traces[0].steps) >= 1
