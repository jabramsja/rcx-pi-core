def test_omega_scaffold_imports():
    from rcx_omega.omega_kernel import OmegaPlan, omega_enabled

    p = OmegaPlan(name="omega-scaffold")
    assert p.name == "omega-scaffold"
    assert omega_enabled() is False
