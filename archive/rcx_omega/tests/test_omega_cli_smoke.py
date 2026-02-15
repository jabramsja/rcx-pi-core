import json
import subprocess
import sys


def test_omega_cli_json_smoke_structure():
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", "μ(μ())"],
        capture_output=True,
        text=True,
        check=True,
    )
    obj = json.loads(p.stdout)
    assert obj["kind"] == "omega"
    assert "seed" in obj and isinstance(obj["seed"], dict)
    assert "result" in obj and isinstance(obj["result"], dict)
    assert "classification" in obj and "type" in obj["classification"]
    assert "orbit" in obj and isinstance(obj["orbit"], list)
    assert obj["orbit"][0]["i"] == 0


def test_omega_cli_reads_stdin_json():
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", "--stdin"],
        input="μ(μ(), μ(μ()))\n",
        capture_output=True,
        text=True,
        check=True,
    )
    obj = json.loads(p.stdout)
    assert obj["kind"] == "omega"
    assert isinstance(obj["seed"], dict)


def test_omega_cli_reads_file_json(tmp_path):
    f = tmp_path / "motif.txt"
    f.write_text("μ(μ())\n", encoding="utf-8")

    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", "--file", str(f)],
        capture_output=True,
        text=True,
        check=True,
    )
    obj = json.loads(p.stdout)
    assert obj["kind"] == "omega"
    assert isinstance(obj["seed"], dict)
