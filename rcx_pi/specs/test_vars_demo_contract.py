from rcx_pi.worlds_probe import score_world, spec_from_world

def test_vars_demo_matches_rcx_core_spec():
    seeds = [
        "[null,a]",
        "[inf,a]",
        "[paradox,a]",
        "[omega,[a,b]]",
        "[a,a]",
        "[dog,cat]",
    ]

    spec = spec_from_world("rcx_core", seeds)
    result = score_world("vars_demo", spec)

    assert result["accuracy"] == 1.0
    assert result["mismatches"] == []