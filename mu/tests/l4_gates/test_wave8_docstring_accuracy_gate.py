"""
L4 gate test: Wave 8 — README and doc wording accuracy.

Proves that README.md and docs use accurate 'tracked @host_* markers'
wording instead of stale 'irreducible bootstrap floor'.
"""
from tests.repo_root import REPO_ROOT


def test_readme_uses_tracked_marker_wording():
    """README.md must use 'tracked @host_* markers' not 'irreducible bootstrap floor'."""
    content = (REPO_ROOT / "README.md").read_text()

    assert "irreducible bootstrap floor" not in content, (
        "README.md still uses stale 'irreducible bootstrap floor' wording. "
        "Should say 'tracked @host_* markers (bootstrap substrate lower bound)'."
    )
    assert "tracked host-debt markers" in content or "@host_* markers" in content, (
        "README.md should reference 'tracked host-debt markers' or '@host_* markers' for debt count."
    )


def test_content_addressed_mu_uses_tracked_marker_wording():
    """ContentAddressedMu.md must use 'tracked @host_* markers' not 'irreducible host debt floor'."""
    content = (REPO_ROOT / "roadmap" / "ContentAddressedMu.md").read_text()

    assert "irreducible host debt floor" not in content, (
        "ContentAddressedMu.md still uses stale 'irreducible host debt floor' wording."
    )
