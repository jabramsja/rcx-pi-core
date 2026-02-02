"""
Tests for validate_agent_compliance.py

Verifies that agent output compliance validation actually works.
Created: 2026-02-01 (9-agent Grounding finding - zero tests existed)
"""

import pytest
import sys
import os

# Add tools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from validate_agent_compliance import (
    count_pattern,
    check_compliance,
    format_report,
    normalize_line_endings,
    HALLUCINATION_WORDS,
)


class TestNormalizeLineEndings:
    """Test line ending normalization (9-agent Fuzzer finding)."""

    def test_unix_lf_unchanged(self):
        """Unix LF should remain unchanged."""
        text = "line1\nline2\nline3"
        assert normalize_line_endings(text) == text

    def test_windows_crlf_normalized(self):
        """Windows CRLF should become LF."""
        text = "line1\r\nline2\r\nline3"
        assert normalize_line_endings(text) == "line1\nline2\nline3"

    def test_old_mac_cr_normalized(self):
        """Old Mac CR should become LF."""
        text = "line1\rline2\rline3"
        assert normalize_line_endings(text) == "line1\nline2\nline3"

    def test_mixed_line_endings(self):
        """Mixed line endings should all become LF."""
        text = "line1\r\nline2\rline3\nline4"
        assert normalize_line_endings(text) == "line1\nline2\nline3\nline4"


class TestCountPattern:
    """Test regex pattern matching counter."""

    def test_empty_string(self):
        """Empty input should return 0 matches."""
        assert count_pattern("", r"^FINDING:") == 0

    def test_single_match(self):
        """Single FINDING should be counted."""
        text = "FINDING: Some issue here"
        assert count_pattern(text, r"^FINDING:\s*[^\n]+") == 1

    def test_multiple_matches(self):
        """Multiple FINDINGs should be counted."""
        text = "FINDING: Issue 1\nFINDING: Issue 2\nFINDING: Issue 3"
        assert count_pattern(text, r"^FINDING:\s*[^\n]+") == 3

    def test_case_insensitive(self):
        """Pattern matching should be case insensitive."""
        text = "finding: lowercase issue"
        assert count_pattern(text, r"^FINDING:") == 1

    def test_multiline_anchors(self):
        """^ anchor should match line starts, not just string start."""
        text = "Some text\nFINDING: Issue here"
        assert count_pattern(text, r"^FINDING:") == 1

    def test_no_match(self):
        """Non-matching pattern should return 0."""
        text = "No findings here"
        assert count_pattern(text, r"^FINDING:") == 0


class TestCheckComplianceBasic:
    """Test basic compliance checking logic."""

    def test_compliant_output(self):
        """Valid agent output should pass all checks."""
        valid_output = """
STATUS.md is at L2 FULL.

FINDING: Issue detected
FILE: /absolute/path/file.py
LINES: 10-15
CODE:
    def some_function():
        pass
VERIFIED: Yes
"""
        result = check_compliance(valid_output)

        assert result["findings"] == 1
        assert result["file_citations"] == 1
        assert result["verified_yes"] == 1
        assert result["verified_no"] == 0
        assert result["status_md_early"] is True
        assert result["compliant"] is True
        assert len(result["violations"]) == 0

    def test_verified_no_violation(self):
        """VERIFIED: No entries should trigger violation."""
        output = """
STATUS.md mentioned.

FINDING: Issue
FILE: /path/file.py
VERIFIED: No
"""
        result = check_compliance(output)

        assert result["verified_no"] == 1
        assert result["compliant"] is False
        assert any("VERIFIED: No" in v for v in result["violations"])

    def test_missing_file_citations(self):
        """Findings without FILE: should trigger violation."""
        output = """
STATUS.md mentioned.

FINDING: Issue without file citation
VERIFIED: Yes
"""
        result = check_compliance(output)

        assert result["findings"] == 1
        assert result["file_citations"] == 0
        assert result["compliant"] is False
        assert any("FILE: citations" in v for v in result["violations"])

    def test_no_findings_is_compliant(self):
        """Output with no findings should be compliant."""
        output = "STATUS.md mentioned. Just some text, no findings."

        result = check_compliance(output)

        assert result["findings"] == 0
        assert result["compliant"] is True


class TestStatusMdCheck:
    """Test STATUS.md mention detection."""

    def test_status_md_in_first_50_lines(self):
        """STATUS.md in first 50 lines should pass."""
        output = "Read STATUS.md first.\n\nFINDING: Issue\nFILE: /path\nVERIFIED: Yes"
        result = check_compliance(output)
        assert result["status_md_early"] is True

    def test_status_md_not_early(self):
        """STATUS.md not in first 50 lines should trigger violation."""
        # Create 51 lines without STATUS.md
        long_header = "\n".join([f"Line {i}" for i in range(51)])
        output = long_header + "\n\nFINDING: Issue\nFILE: /path/file.py\nVERIFIED: Yes"

        result = check_compliance(output)

        assert result["status_md_early"] is False
        assert result["compliant"] is False
        assert any("STATUS.md not mentioned" in v for v in result["violations"])

    def test_status_md_exactly_line_50(self):
        """STATUS.md on exactly line 50 should pass."""
        lines = [f"Line {i}" for i in range(49)]
        lines.append("STATUS.md is here on line 50")
        output = "\n".join(lines) + "\n\nFINDING: Issue\nFILE: /path/file.py\nVERIFIED: Yes"

        result = check_compliance(output)

        assert result["status_md_early"] is True


class TestHallucinationWords:
    """Test hallucination word detection."""

    def test_high_hallucination_count(self):
        """More than 3 hallucination words should trigger violation."""
        output = """
STATUS.md mentioned.

FINDING: This probably seems like it might maybe be an issue
FILE: /path/file.py
VERIFIED: Yes

The code likely assumes that this presumably works.
"""
        result = check_compliance(output)

        assert result["hallucination_words"] > 3
        assert result["compliant"] is False
        assert any("hallucination word count" in v for v in result["violations"])

    def test_threshold_boundary_pass(self):
        """Exactly 3 hallucination words should pass."""
        output = """
STATUS.md mentioned.

FINDING: This probably seems likely
FILE: /path/file.py
VERIFIED: Yes
"""
        result = check_compliance(output)

        assert result["hallucination_words"] == 3
        assert result["compliant"] is True

    def test_expanded_hallucination_words(self):
        """New hallucination words should be detected (9-agent finding)."""
        output = "This appears to be an issue. It possibly could perhaps suggests something."
        count = count_pattern(output, HALLUCINATION_WORDS)
        # appears, possibly, could, perhaps, suggests = 5
        assert count == 5

    def test_original_hallucination_words(self):
        """Original hallucination words should still be detected."""
        output = "probably likely seems assume maybe might presumably"
        count = count_pattern(output, HALLUCINATION_WORDS)
        assert count == 7


class TestCodeBlockPattern:
    """Test CODE block pattern matching (9-agent Fuzzer finding)."""

    def test_four_space_indent(self):
        """CODE block with 4-space indent should match."""
        text = """CODE:
    def foo():
        return 42
"""
        result = check_compliance("STATUS.md\n\nFINDING: x\nFILE: /p\n" + text + "VERIFIED: Yes")
        assert result["code_blocks"] == 1

    def test_tab_indent(self):
        """CODE block with tab indent should match (was broken)."""
        text = """CODE:
\tdef foo():
\t\treturn 42
"""
        result = check_compliance("STATUS.md\n\nFINDING: x\nFILE: /p\n" + text + "VERIFIED: Yes")
        assert result["code_blocks"] == 1

    def test_two_space_indent(self):
        """CODE block with 2-space indent should match."""
        text = """CODE:
  def foo():
    return 42
"""
        result = check_compliance("STATUS.md\n\nFINDING: x\nFILE: /p\n" + text + "VERIFIED: Yes")
        assert result["code_blocks"] == 1

    def test_eight_space_indent(self):
        """CODE block with 8-space indent should match."""
        text = """CODE:
        def foo():
            return 42
"""
        result = check_compliance("STATUS.md\n\nFINDING: x\nFILE: /p\n" + text + "VERIFIED: Yes")
        assert result["code_blocks"] == 1

    def test_no_indent_fails(self):
        """CODE block without indentation should not match."""
        text = """CODE:
def foo():
    return 42
"""
        result = check_compliance("STATUS.md\n\nFINDING: x\nFILE: /p\n" + text + "VERIFIED: Yes")
        assert result["code_blocks"] == 0


class TestFilePathPattern:
    """Test FILE path pattern matching."""

    def test_absolute_path(self):
        """FILE: with absolute path should match."""
        text = "FILE: /absolute/path/to/file.py"
        assert count_pattern(text, r"^FILE:\s*/[^\n]+") == 1

    def test_relative_path_rejected(self):
        """FILE: with relative path should NOT match."""
        text = "FILE: relative/path/file.py"
        assert count_pattern(text, r"^FILE:\s*/[^\n]+") == 0

    def test_windows_path_rejected(self):
        """FILE: with Windows backslash path should NOT match."""
        text = r"FILE: C:\Users\path\file.py"
        assert count_pattern(text, r"^FILE:\s*/[^\n]+") == 0


class TestLineNumberPattern:
    """Test LINES pattern matching."""

    def test_single_line_number(self):
        """LINES: with single number should match."""
        text = "LINES: 42"
        assert count_pattern(text, r"^LINES?:\s*\d+") == 1

    def test_line_range(self):
        """LINES: with range should match."""
        text = "LINES: 10-20"
        assert count_pattern(text, r"^LINES?:\s*\d+") == 1

    def test_singular_form(self):
        """LINE: (singular) should also match."""
        text = "LINE: 42"
        assert count_pattern(text, r"^LINES?:\s*\d+") == 1


class TestVerifiedPattern:
    """Test VERIFIED pattern matching."""

    def test_verified_yes(self):
        """VERIFIED: Yes should match."""
        text = "VERIFIED: Yes"
        assert count_pattern(text, r"^VERIFIED:\s*Yes") == 1

    def test_verified_no(self):
        """VERIFIED: No should match."""
        text = "VERIFIED: No"
        assert count_pattern(text, r"^VERIFIED:\s*No") == 1

    def test_verified_lowercase_yes(self):
        """VERIFIED: yes (lowercase) should match due to IGNORECASE."""
        text = "VERIFIED: yes"
        assert count_pattern(text, r"^VERIFIED:\s*Yes") == 1


class TestFormatReport:
    """Test report formatting."""

    def test_compliant_report(self):
        """Compliant metrics should produce COMPLIANT report."""
        metrics = {
            "findings": 1,
            "file_citations": 1,
            "line_citations": 1,
            "code_blocks": 1,
            "verified_yes": 1,
            "verified_no": 0,
            "status_md_early": True,
            "hallucination_words": 0,
            "violations": [],
            "compliant": True,
        }

        report = format_report(metrics)

        assert "COMPLIANT" in report
        assert "All guardrail requirements met" in report
        assert "NON-COMPLIANT" not in report

    def test_non_compliant_report(self):
        """Non-compliant metrics should produce NON-COMPLIANT report."""
        metrics = {
            "findings": 1,
            "file_citations": 0,
            "line_citations": 0,
            "code_blocks": 0,
            "verified_yes": 0,
            "verified_no": 1,
            "status_md_early": False,
            "hallucination_words": 10,
            "violations": ["Missing FILE: citations", "VERIFIED: No entries"],
            "compliant": False,
        }

        report = format_report(metrics)

        assert "NON-COMPLIANT" in report
        assert "Missing FILE: citations" in report
        assert "VERIFIED: No entries" in report


class TestLineEndingIntegration:
    """Integration tests for line ending fixes."""

    def test_windows_crlf_finding_detected(self):
        """Windows CRLF in agent output should still detect findings."""
        output = "STATUS.md\r\n\r\nFINDING: Issue\r\nFILE: /path/file.py\r\nVERIFIED: Yes\r\n"
        result = check_compliance(output)

        assert result["findings"] == 1
        assert result["file_citations"] == 1
        assert result["verified_yes"] == 1

    def test_old_mac_cr_finding_detected(self):
        """Old Mac CR in agent output should still detect findings."""
        output = "STATUS.md\r\rFINDING: Issue\rFILE: /path/file.py\rVERIFIED: Yes\r"
        result = check_compliance(output)

        assert result["findings"] == 1
        assert result["file_citations"] == 1
        assert result["verified_yes"] == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_input(self):
        """Empty string should not crash."""
        result = check_compliance("")
        assert result["findings"] == 0
        assert result["compliant"] is True

    def test_unicode_in_code_block(self):
        """Unicode characters should not break pattern matching."""
        output = """
STATUS.md mentioned.

FINDING: Unicode issue
FILE: /path/file.py
CODE:
    # λ calculus detector
    def λ_guard():
        return "🚫"
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["code_blocks"] >= 1

    def test_finding_with_colon_in_description(self):
        """Colons in FINDING description should not break parsing."""
        output = """
STATUS.md mentioned.

FINDING: Error: something failed
FILE: /path/file.py
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["findings"] == 1

    def test_multiple_findings_all_cited(self):
        """Multiple findings each with citations should pass."""
        output = """
STATUS.md mentioned.

FINDING: First issue
FILE: /path/file1.py
VERIFIED: Yes

FINDING: Second issue
FILE: /path/file2.py
VERIFIED: Yes

FINDING: Third issue
FILE: /path/file3.py
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["findings"] == 3
        assert result["file_citations"] == 3
        assert result["verified_yes"] == 3
        assert result["compliant"] is True
