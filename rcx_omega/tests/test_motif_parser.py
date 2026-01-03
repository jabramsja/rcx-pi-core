from rcx_pi import μ
from rcx_omega.core import parse_motif


def test_parse_motif_mu_empty():
    assert parse_motif("μ()") == μ()
    assert parse_motif("mu()") == μ()


def test_parse_motif_nested():
    assert parse_motif("μ(μ())") == μ(μ())
    assert parse_motif("mu(mu())") == μ(μ())


def test_parse_motif_multi_kids():
    assert parse_motif("μ(μ(), μ(μ()))") == μ(μ(), μ(μ()))
