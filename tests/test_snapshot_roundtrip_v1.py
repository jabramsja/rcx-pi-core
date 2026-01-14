import hashlib
import subprocess
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def test_snapshot_v1_sha256sum_matches_repo_lockfile():
    repo = Path(__file__).resolve().parents[1]
    snapdir = repo / "snapshots"
    sums = snapdir / "SHA256SUMS"
    assert sums.exists(), "Missing snapshots/SHA256SUMS (expected canonical lockfile)"

    expected = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        assert len(parts) >= 2, f"Bad SHA256SUMS line: {line!r}"
        expected_sha = parts[0]
        fname = parts[-1]
        expected[fname] = expected_sha

    assert "state_demo.state" in expected, "SHA256SUMS should include state_demo.state"
    p = snapdir / "state_demo.state"
    assert p.exists(), "Missing snapshots/state_demo.state"
    assert sha256_file(p) == expected["state_demo.state"]

def test_snapshot_roundtrip_demo_runs_and_mentions_restore():
    repo = Path(__file__).resolve().parents[1]
    rust_dir = repo / "rcx_pi_rust"
    assert rust_dir.exists(), "Missing rcx_pi_rust directory"

    out = subprocess.run(
        ["cargo", "run", "--example", "state_demo"],
        cwd=rust_dir,
        check=True,
        text=True,
        capture_output=True,
    )
    s = (out.stdout or "") + "\n" + (out.stderr or "")

    assert "wrote snapshot to snapshots/state_demo.state" in s
    assert "after restore" in s
    assert "=== done ===" in s
