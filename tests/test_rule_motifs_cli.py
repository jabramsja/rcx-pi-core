"""
Rule Motifs CLI Tests.

Tests the `rules --print-rule-motifs` CLI flag using subprocess calls only.
All assertions are based on PUBLIC interface output, no engine internals.

See docs/RuleAsMotif.v0.md for spec.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List, Tuple

import pytest

from rcx_pi.rule_motifs_v0 import RULE_IDS


def _run_cli_rule_motifs() -> Tuple[int, str, str]:
    """
    Run CLI with --print-rule-motifs and return (exit_code, stdout, stderr).

    Uses subprocess to ensure we test the PUBLIC interface only.
    """
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    result = subprocess.run(
        [
            "python3", "-m", "rcx_pi.rcx_cli", "rules",
            "--print-rule-motifs",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _parse_jsonl(output: str) -> List[Dict[str, Any]]:
    """Parse JSONL output into list of dicts."""
    events = []
    for line in output.strip().splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


class TestRuleMotifsCliRuns:
    """CLI must succeed and produce output."""

    def test_exit_code_zero(self) -> None:
        """CLI with --print-rule-motifs must succeed."""
        exit_code, stdout, stderr = _run_cli_rule_motifs()
        assert exit_code == 0, f"CLI failed: {stderr}"

    def test_produces_output(self) -> None:
        """CLI must produce non-empty output."""
        exit_code, stdout, stderr = _run_cli_rule_motifs()
        assert exit_code == 0
        assert stdout.strip(), "Expected non-empty output"


class TestRuleMotifsCliSchema:
    """Output must conform to v2 trace event schema."""

    def test_all_events_have_required_fields(self) -> None:
        """Each event must have v, type, i, mu fields."""
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        events = _parse_jsonl(stdout)
        assert len(events) > 0, "Expected at least one event"

        for idx, event in enumerate(events):
            assert "v" in event, f"Event {idx} missing 'v'"
            assert event["v"] == 2, f"Event {idx} has v={event['v']}, expected 2"
            assert "type" in event, f"Event {idx} missing 'type'"
            assert event["type"] == "rule.loaded", f"Event {idx} has wrong type"
            assert "i" in event, f"Event {idx} missing 'i'"
            assert event["i"] == idx, f"Event {idx} has i={event['i']}, expected {idx}"
            assert "mu" in event, f"Event {idx} missing 'mu'"

    def test_mu_contains_rule_structure(self) -> None:
        """Each mu must contain a rule with id, pattern, body."""
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        events = _parse_jsonl(stdout)
        for idx, event in enumerate(events):
            mu = event["mu"]
            assert "rule" in mu, f"Event {idx} mu missing 'rule'"
            rule = mu["rule"]
            assert "id" in rule, f"Event {idx} rule missing 'id'"
            assert "pattern" in rule, f"Event {idx} rule missing 'pattern'"
            assert "body" in rule, f"Event {idx} rule missing 'body'"
            assert isinstance(rule["id"], str), f"Event {idx} rule.id not a string"


class TestRuleMotifsCliDeterminism:
    """Output must be deterministic across runs."""

    def test_identical_output_twice(self) -> None:
        """Two runs must produce identical output."""
        exit1, stdout1, _ = _run_cli_rule_motifs()
        exit2, stdout2, _ = _run_cli_rule_motifs()

        assert exit1 == exit2 == 0
        assert stdout1 == stdout2, "Non-deterministic output detected"

    def test_indices_are_contiguous(self) -> None:
        """Event indices must be 0, 1, 2, ... (contiguous)."""
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        events = _parse_jsonl(stdout)
        indices = [e["i"] for e in events]
        expected = list(range(len(events)))
        assert indices == expected, f"Non-contiguous indices: {indices}"


class TestRuleMotifsCliCoverage:
    """Output must cover all rules from rules_pure.py."""

    def test_emitted_rule_ids_match_canonical_list(self) -> None:
        """
        Emitted rule IDs must exactly match RULE_IDS from rule_motifs_v0.py.

        This prevents quiet drift: if rules_pure.py adds/removes rules,
        either RULE_IDS or the motif definitions must be updated.
        """
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        events = _parse_jsonl(stdout)
        emitted_ids = tuple(e["mu"]["rule"]["id"] for e in events)

        assert emitted_ids == RULE_IDS, (
            f"Emitted rule IDs do not match RULE_IDS.\n"
            f"Expected: {RULE_IDS}\n"
            f"Got: {emitted_ids}"
        )

    def test_all_expected_rules_present(self) -> None:
        """All known rules from rules_pure.py must be present."""
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        events = _parse_jsonl(stdout)
        emitted_ids = {e["mu"]["rule"]["id"] for e in events}

        # These are the rules implemented in rules_pure.py
        expected_rules = {
            "add.zero",
            "add.succ",
            "mult.zero",
            "mult.succ",
            "pred.zero",
            "pred.succ",
            "activation",
            "classify",
        }

        assert emitted_ids == expected_rules, (
            f"Missing or extra rules.\n"
            f"Expected: {expected_rules}\n"
            f"Got: {emitted_ids}"
        )

    def test_count_matches_expected(self) -> None:
        """Number of emitted rules must match expected count."""
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        events = _parse_jsonl(stdout)
        assert len(events) == 8, f"Expected 8 rules, got {len(events)}"


class TestRuleMotifsCliJsonValidity:
    """Output must be valid JSON."""

    def test_each_line_is_valid_json(self) -> None:
        """Each output line must parse as valid JSON."""
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        for line_num, line in enumerate(stdout.strip().splitlines(), 1):
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"Line {line_num} is not valid JSON: {e}\nLine: {line}")

    def test_output_is_compact_json(self) -> None:
        """Output must use compact JSON (no extra whitespace)."""
        exit_code, stdout, _ = _run_cli_rule_motifs()
        assert exit_code == 0

        for line in stdout.strip().splitlines():
            # Compact JSON has no spaces after : or ,
            parsed = json.loads(line)
            compact = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
            assert line == compact, f"Non-compact JSON detected:\n{line}\nvs\n{compact}"
