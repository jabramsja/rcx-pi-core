"""Regression tests for tools/checks/check_control_packet_line_refs.py.

Proves the control-packet line-ref lint (governing packet
control-packet-line-ref-lint-2026-06-01):
  (a) a packet containing a source file-and-line reference is REJECTED,
  (b) a clean packet PASSES,
  (c) a host:port string or a clock-time string is NOT a false positive,
and that the phase_a_executor plan-load pre-flight fails closed on an
offending packet BEFORE the first bridge round, citing function-name
remediation. The matcher's "by construction" false-positive immunity
(host:port / clock / range / words ending in an extension's letters) is
locked by direct matcher assertions.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mu.tests.tools.module_loader import load_module

_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
REPO_ROOT = Path(__file__).resolve().parents[3]

checker = load_module(
    "check_control_packet_line_refs",
    _TOOLS_DIR / "checks" / "check_control_packet_line_refs.py",
)
phase_a_mod = load_module(
    "phase_a_executor",
    _TOOLS_DIR / "executors" / "phase_a_executor.py",
)

GOVERNING_PACKET = (
    REPO_ROOT
    / "reports"
    / "control_plane"
    / "control_packet_line_ref_lint_2026-06-01.md"
)

# A code line-number reference assembled at runtime so this test file carries no
# literal <path>.<ext>:<line> token of its own.
_LINE_REF = "loader.py" + ":" + "128"


def _write_packet(tmp_path: Path, name: str, body: str) -> Path:
    """Write a control packet with the six required sections plus *body*."""
    plan_dir = tmp_path / "reports" / "control_plane"
    plan_dir.mkdir(parents=True, exist_ok=True)
    packet = plan_dir / name
    packet.write_text(
        "# Test Packet\n"
        "Date: 2026-06-01\n"
        "Status: Phase A\n"
        "Phase-A-Lock: UNLOCKED\n"
        "\n"
        "## Scope\n"
        f"{body}\n"
        "## Work Items\n"
        "Implement the matcher in find_offending_lines.\n"
        "## Constraints\n"
        "No general heuristic.\n"
        "## Stop Conditions\n"
        "Stop on runtime touch.\n"
        "## Acceptance Criteria\n"
        "Checker exits non-zero on offending packets.\n"
        "## Grounding / Authorization\n"
        "TASKS.md authorization.\n",
        encoding="utf-8",
    )
    return packet


# ---------------------------------------------------------------------------
# (a) reject, (b) pass, (c) no false positive — checker main() exit codes
# ---------------------------------------------------------------------------


def test_packet_with_source_line_reference_is_rejected(tmp_path, capsys):
    packet = _write_packet(tmp_path, "bad.md", f"See {_LINE_REF} for the loop.")
    rc = checker.main([str(packet)])
    assert rc == 1
    err = capsys.readouterr().err
    assert _LINE_REF in err
    assert "function name" in err


def test_clean_packet_passes(tmp_path):
    packet = _write_packet(
        tmp_path,
        "clean.md",
        "Cite code by the function name run_phase_a instead of a line number.",
    )
    assert checker.main([str(packet)]) == 0


def test_host_port_is_not_a_false_positive(tmp_path):
    packet = _write_packet(
        tmp_path,
        "hostport.md",
        "Connect the dashboard to localhost:8099 and the api to example.com:8080.",
    )
    assert checker.main([str(packet)]) == 0


def test_clock_time_is_not_a_false_positive(tmp_path):
    packet = _write_packet(
        tmp_path,
        "clock.md",
        "The nightly run starts at 14:30 and the digest lands by 12:34:56 daily.",
    )
    assert checker.main([str(packet)]) == 0


def test_numeric_range_is_not_a_false_positive(tmp_path):
    packet = _write_packet(tmp_path, "range.md", "Process the 10:20 shard window.")
    assert checker.main([str(packet)]) == 0


# ---------------------------------------------------------------------------
# Matcher false-positive immunity holds BY CONSTRUCTION (closed lexical pattern)
# ---------------------------------------------------------------------------


def test_matcher_rejects_each_closed_extension():
    for ext in checker.CODE_EXTENSIONS:
        sample = f"path.{ext}:7"
        assert checker.find_offending_lines(sample), f"{ext} not matched"


def test_matcher_rejects_yml_workflow_reference():
    """Bridge round 1 regression: ``.yml`` (the GitHub-workflow twin of ``.yaml``)
    must be caught.

    A workflow citation like ``.github/workflows/ci.yml:<line>`` is exactly the
    stale-line-number form the lint exists to reject; the matcher previously
    caught ``.yaml`` but silently allowed ``.yml``, an inconsistent gap.
    """
    yml_ref = ".github/workflows/ci.yml" + ":" + "93"
    assert checker.find_offending_lines(yml_ref), yml_ref
    assert "yml" in checker.CODE_EXTENSIONS
    # The ``.yaml`` twin must still match (no regression in the existing case).
    yaml_ref = "slow_tests.yaml" + ":" + "42"
    assert checker.find_offending_lines(yaml_ref), yaml_ref


def test_packet_with_yml_workflow_reference_is_rejected(tmp_path, capsys):
    """main() rejects a packet that cites a workflow file by line number."""
    yml_ref = ".github/workflows/ci.yml" + ":" + "93"
    packet = _write_packet(tmp_path, "yml.md", f"Update the gate at {yml_ref}.")
    rc = checker.main([str(packet)])
    assert rc == 1
    err = capsys.readouterr().err
    assert yml_ref in err
    assert "function name" in err


def test_matcher_immune_to_words_ending_in_extension_letters():
    # No dot before the extension letters -> not a file reference.
    for sample in ("bash:42", "crash:10", "happy:42", "mypy:5"):
        assert checker.find_offending_lines(sample) == [], sample


def test_matcher_immune_to_extension_not_followed_by_colon_digit():
    # The colon does not immediately follow the extension token.
    for sample in ("foo.python:42", "config.jsonx:1", "version v2.1.145 shipped"):
        assert checker.find_offending_lines(sample) == [], sample


def test_matcher_immune_to_host_port_clock_range():
    for sample in ("host:port", "localhost:8099", "12:34", "12:34:56", "10:20"):
        assert checker.find_offending_lines(sample) == [], sample


def test_find_offending_lines_reports_line_number_and_text():
    text = "clean header\nbroken at " + _LINE_REF + " here\nclean footer\n"
    offenses = checker.find_offending_lines(text)
    assert len(offenses) == 1
    lineno, line_text = offenses[0]
    assert lineno == 2
    assert _LINE_REF in line_text


def test_main_lists_each_offending_line(tmp_path, capsys):
    ref_b = "eval_step.js" + ":" + "42"
    packet = _write_packet(
        tmp_path,
        "multi.md",
        f"First offense {_LINE_REF}.\nSecond offense {ref_b}.",
    )
    rc = checker.main([str(packet)])
    assert rc == 1
    err = capsys.readouterr().err
    assert _LINE_REF in err
    assert ref_b in err
    assert "2 code line-number reference(s) found" in err


def test_main_read_error_returns_two(tmp_path):
    assert checker.main([str(tmp_path / "does_not_exist.md")]) == 2


# ---------------------------------------------------------------------------
# phase_a_executor plan-load pre-flight fails closed BEFORE the first bridge round
# ---------------------------------------------------------------------------


def test_executor_preflight_rejects_offending_packet():
    msg = phase_a_mod.preflight_control_packet_line_refs(
        "reports/control_plane/x.md",
        f"Fix the loop at {_LINE_REF} now.\n",
    )
    assert msg is not None
    assert _LINE_REF in msg
    assert "function name" in msg


def test_executor_preflight_passes_clean_packet():
    msg = phase_a_mod.preflight_control_packet_line_refs(
        "reports/control_plane/x.md",
        "Cite code by function name preflight_control_packet_line_refs.\n",
    )
    assert msg is None


def test_run_phase_a_fails_closed_before_bridge(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_packet(repo, "linty_plan.md", f"See {_LINE_REF} for the helper.")

    bridge_calls: list = []
    sdk_calls: list = []

    def recording_bridge(*args, **kwargs):
        bridge_calls.append((args, kwargs))
        return {"exit_code": 0, "stdout": "", "stderr": ""}

    def recording_sdk(*args, **kwargs):
        sdk_calls.append((args, kwargs))
        return {"exit_code": 0}

    def fake_emit(repo_root, **kwargs):
        return {"enabled": True, "event_id": kwargs["event_type"], "attempted": []}

    with patch.object(phase_a_mod, "load_routing_record", return_value={"decision": "ROUTE_PHASE_A"}), \
         patch.object(phase_a_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
         patch.object(phase_a_mod, "run_sdk_agents", side_effect=recording_sdk), \
         patch.object(phase_a_mod, "run_bridge_design_review", side_effect=recording_bridge):
        result = phase_a_mod.run_phase_a(repo, "linty_plan", max_bridge_rounds=1)

    assert result["status"] == "error"
    assert _LINE_REF in result["error"]
    assert "function name" in result["error"]
    # The whole point: rejected before any SDK review or bridge round ran.
    assert bridge_calls == []
    assert sdk_calls == []
    assert result["bridge_rounds"] == 0


# ---------------------------------------------------------------------------
# Dogfood: the governing packet for this wave must itself pass the new checker.
# ---------------------------------------------------------------------------


def test_governing_packet_is_clean():
    if not GOVERNING_PACKET.exists():
        # The packet may be archived after closeout; the reject/pass tests above
        # already lock the matcher behavior.
        return
    assert checker.find_offending_lines(GOVERNING_PACKET.read_text(encoding="utf-8")) == []
