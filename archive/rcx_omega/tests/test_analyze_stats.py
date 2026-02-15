from rcx_pi import μ, VOID
from rcx_omega.engine.analyze import analyze_motif


def test_analyze_void():
    stats = analyze_motif(VOID)
    assert stats.nodes == 1
    assert stats.depth == 1


def test_analyze_nested_mu():
    x = μ(μ())
    stats = analyze_motif(x)
    assert stats.nodes == 2
    assert stats.depth == 2
