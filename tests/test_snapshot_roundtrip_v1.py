import subprocess
from pathlib import Path

def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)

def test_snapshot_roundtrip_v1_contract(tmp_path: Path):
    """
    Contract:
      - Create a runtime with a known world
      - Produce some state
      - Save snapshot
      - Reset
      - Load snapshot
      - Verify behavior unchanged

    TODO: Wire this test to your existing Rust snapshot machinery.
    Recommended approach:
      - call the existing Rust example `state_demo` OR
      - run the REPL in scripted mode if you have one
    """
    repo = Path(__file__).resolve().parents[1]
    rust_dir = repo / "rcx_pi_rust"

    # TODO: Replace with the real command that creates + returns a snapshot path
    # Example placeholder:
    #   cargo run --example state_demo -- --out <tmp_path>/state_v1.json
    #
    # For now, just prove the example is runnable (you will strengthen this next).
    out = run(["cargo", "run", "--example", "state_demo"], cwd=rust_dir)
    assert out.returncode == 0
