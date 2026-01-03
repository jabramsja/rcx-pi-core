from rcx_pi import μ, VOID, UNIT
from rcx_omega.utils.motif_codec import motif_to_json_obj


def test_codec_leaf_is_mu_or_atom():
    obj = motif_to_json_obj(VOID)
    assert isinstance(obj, dict)
    assert ("μ" in obj) or ("atom" in obj)


def test_codec_nested_mu_shape():
    x = μ(μ())
    obj = motif_to_json_obj(x)
    assert isinstance(obj, dict)
    assert "μ" in obj
    assert isinstance(obj["μ"], list)
    assert len(obj["μ"]) == 1
    assert isinstance(obj["μ"][0], dict)
