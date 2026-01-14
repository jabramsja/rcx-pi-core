import hashlib
import subprocess
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def find_snapdir(repo: Path) -> Path:
    a = repo / "snapshots"
    b = repo / "rcx_pi_rust" / "snapshots"
    if a.exists():
        return a
    if b.exists():
        return b
    raise AssertionError("No snapshots dir found at ./snapshots or ./rcx_pi_rust/snapshots")

def parse_sha256sums(p: Path) -> dict[str, str]:
    m: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        assert len(parts) >= 2, f"Bad SHA256SUMS line: {line!r}"
        sha = parts[0]
        fname = parts[-1]
        m[fname] = sha
    return m

def test_snapshot_v1_sha256sum_matches_repo_lockfile():
    repo = Path(__file__).resolve().parents[1]
    sd = find_snapdir(repo)
    sums = sd / "SHA256SUMS"
    assert sums.exists(), f"Missing {sums}"
    expected = parse_sha256sums(sums)

    assert "state_demo.state" in expected, "SHA256SUMS should include state_demo.state"
    st = sd / "state_demo.state"
    assert st.exists(), f"Missing {st}"
    assert sha256_file(st) == expected["state_demo.state"]

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

    assert "state_demo.state" in s
    assert "restore" in s.lower()
