"""
Tests for validate_agent_compliance.py

Verifies that agent output compliance validation actually works.
Created: 2026-02-01 (9-agent Grounding finding - zero tests existed)
"""

import pytest
import sys
import os

# Add tools to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', 'tools', 'runners'))
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
        # New structured validation reports incomplete blocks
        assert any("incomplete" in v.lower() for v in result["violations"])

    def test_no_findings_is_compliant(self):
        """Output with no findings should be compliant."""
        output = "STATUS.md mentioned. Just some text, no findings."

        result = check_compliance(output)

        assert result["findings"] == 0
        assert result["compliant"] is True

    def test_strict_mode_requires_review_scaffold(self):
        """Strict mode should reject outputs missing CHECKED/NOT_CHECKED/VERDICT."""
        output = "STATUS.md mentioned. Just some text, no findings."

        result = check_compliance(output, strict=True)

        assert result["compliant"] is False
        assert any("missing CHECKED section" in v for v in result["violations"])
        assert any("missing NOT_CHECKED section" in v for v in result["violations"])
        assert any("missing explicit VERDICT line" in v for v in result["violations"])

    def test_strict_mode_rejects_external_review_redirect(self, tmp_path, monkeypatch):
        """Strict mode should reject outputs that redirect review to external files."""
        monkeypatch.chdir(tmp_path)
        output = """
### CHECKED
- Reviewed the scoped change.

The review plan file is ready for your review at `/Users/jeffabrams/.claude/plans/glowing-fluttering-owl.md`.

### NOT_CHECKED
- No live exploit was attempted.

### Verdict
VERDICT: SECURE
"""

        result = check_compliance(output, strict=True)

        assert result["compliant"] is False
        assert any("external path outside current project directory" in v for v in result["violations"])


class TestStatusMdCheck:
    """Test STATUS.md mention detection."""

    def test_status_md_in_first_50_lines(self):
        """STATUS.md in first 50 lines should pass."""
        output = "Read STATUS.md first.\n\nFINDING: Issue\nFILE: /path\nVERIFIED: Yes"
        result = check_compliance(output)
        assert result["status_md_early"] is True

    def test_status_md_not_early(self):
        """STATUS.md not in first 50 lines - metric tracked but non-blocking.

        Note: STATUS.md requirement was downgraded to non-blocking (advisory only)
        because agents reviewing tooling files may not need to read STATUS.md.
        The metric is still tracked for visibility.
        """
        # Create 51 lines without STATUS.md
        long_header = "\n".join([f"Line {i}" for i in range(51)])
        output = long_header + "\n\nFINDING: Issue\nFILE: /path/file.py\nVERIFIED: Yes"

        result = check_compliance(output)

        # Metric is still tracked
        assert result["status_md_early"] is False
        # But no violation for STATUS.md specifically (non-blocking)
        assert not any("STATUS.md" in v for v in result["violations"])

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
        """More than 10 hallucination words should trigger violation."""
        # Agent outputs are verbose - threshold is 10 to avoid false positives
        output = """
STATUS.md mentioned.

FINDING: This probably seems like it might maybe be an issue
FILE: /path/file.py
VERIFIED: Yes

The code likely assumes that this presumably works. It appears that
this could possibly suggest that it believes this might likely
be a concern. Presumably this seems to maybe assume it could work.
"""
        result = check_compliance(output)

        assert result["hallucination_words"] > 10
        assert result["compliant"] is False
        assert any("hallucination word count" in v for v in result["violations"])

    def test_threshold_boundary_pass(self):
        """Up to 10 hallucination words should pass (verbose agent output tolerance)."""
        output = """
STATUS.md mentioned.

FINDING: This probably seems likely and might possibly be a concern
FILE: /path/file.py
LINES: 1-5
CODE:
    def foo():
        pass
VERIFIED: Yes

It appears this could suggest something.
"""
        result = check_compliance(output)

        # 10 or fewer is acceptable
        assert result["hallucination_words"] <= 10
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
LINES: 1-5
CODE:
    code_block_1()
VERIFIED: Yes

FINDING: Second issue
FILE: /path/file2.py
LINES: 10-15
CODE:
    code_block_2()
VERIFIED: Yes

FINDING: Third issue
FILE: /path/file3.py
LINES: 20-25
CODE:
    code_block_3()
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["findings"] == 3
        assert result["file_citations"] == 3
        assert result["verified_yes"] == 3
        assert result["compliant"] is True


class TestStructuredBlockParsing:
    """Test structured FINDING block parsing (2026-02-02 critical fix)."""

    def test_complete_block_is_compliant(self):
        """Finding block with all components should pass."""
        output = """
STATUS.md reviewed.

FINDING: Complete evidence
FILE: /path/to/file.py
LINES: 10-20
CODE:
    def foo():
        pass
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["compliant"] is True
        assert result.get("incomplete_blocks", 0) == 0

    def test_missing_file_marked_incomplete(self):
        """Finding without FILE should be marked incomplete."""
        output = """
STATUS.md reviewed.

FINDING: Missing file path
LINES: 10-20
CODE:
    def foo():
        pass
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["compliant"] is False
        assert result.get("incomplete_blocks", 0) == 1
        assert any("FILE" in v for v in result["violations"])

    def test_missing_lines_marked_incomplete(self):
        """Finding without LINES should be marked incomplete."""
        output = """
STATUS.md reviewed.

FINDING: Missing line numbers
FILE: /path/to/file.py
CODE:
    def foo():
        pass
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["compliant"] is False
        assert any("LINES" in v for v in result["violations"])

    def test_missing_code_marked_incomplete(self):
        """Finding without CODE should be marked incomplete."""
        output = """
STATUS.md reviewed.

FINDING: Missing code block
FILE: /path/to/file.py
LINES: 10-20
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["compliant"] is False
        assert any("CODE" in v for v in result["violations"])

    def test_verified_no_fails(self):
        """VERIFIED: No should fail even in complete block."""
        output = """
STATUS.md reviewed.

FINDING: Unverified finding
FILE: /path/to/file.py
LINES: 10-20
CODE:
    def foo():
        pass
VERIFIED: No
"""
        result = check_compliance(output)
        assert result["compliant"] is False


class TestCodeBlockEmptyLines:
    """Test CODE blocks with empty lines (2026-02-02 critical fix)."""

    def test_code_block_with_blank_line(self):
        """CODE block with blank line inside should match."""
        output = """
STATUS.md reviewed.

FINDING: Code with blank line
FILE: /path/file.py
LINES: 1-10
CODE:
    def foo():
        pass

    def bar():
        pass
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["code_blocks"] >= 1
        assert result["compliant"] is True

    def test_code_block_with_multiple_blank_lines(self):
        """CODE block with multiple blank lines should match."""
        output = """
STATUS.md reviewed.

FINDING: Code with multiple blanks
FILE: /path/file.py
LINES: 1-15
CODE:
    class Foo:
        pass


    class Bar:
        pass
VERIFIED: Yes
"""
        result = check_compliance(output)
        assert result["code_blocks"] >= 1


class TestFileVerification:
    """Test FILE path verification (2026-02-02 critical fix)."""

    def test_real_file_passes_verification(self):
        """Real file path should pass when verify_files=True."""
        import os
        # Use this test file as a known existing file
        this_file = os.path.abspath(__file__)
        output = f"""
STATUS.md reviewed.

FINDING: Real file
FILE: {this_file}
LINES: 1-5
CODE:
    import pytest
VERIFIED: Yes
"""
        result = check_compliance(output, verify_files=True)
        assert result["compliant"] is True

    def test_fake_file_fails_verification(self):
        """Fake file path should fail when verify_files=True."""
        output = """
STATUS.md reviewed.

FINDING: Fake file
FILE: /this/path/definitely/does/not/exist/anywhere.py
LINES: 1-5
CODE:
    import fake
VERIFIED: Yes
"""
        result = check_compliance(output, verify_files=True)
        assert result["compliant"] is False
        assert any("file not found" in v.lower() for v in result["violations"])

    def test_file_not_verified_by_default(self):
        """File existence should NOT be checked by default."""
        output = """
STATUS.md reviewed.

FINDING: Fake file but not verified
FILE: /this/path/definitely/does/not/exist.py
LINES: 1-5
CODE:
    import fake
VERIFIED: Yes
"""
        result = check_compliance(output, verify_files=False)
        assert result["compliant"] is True


class TestFindingBlockExtraction:
    """Test the extract_finding_blocks helper function."""

    def test_single_block_extraction(self):
        """Single finding block should be extracted correctly."""
        from validate_agent_compliance import extract_finding_blocks

        text = """
FINDING: Test finding
FILE: /path/to/file.py
LINES: 10-20
CODE:
    some_code()
VERIFIED: Yes
"""
        blocks = extract_finding_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].finding == "Test finding"
        assert blocks[0].file_path == "/path/to/file.py"
        assert blocks[0].lines == "10-20"
        assert "some_code()" in blocks[0].code
        assert blocks[0].verified == "Yes"

    def test_multiple_blocks_extraction(self):
        """Multiple finding blocks should be extracted correctly."""
        from validate_agent_compliance import extract_finding_blocks

        text = """
FINDING: First
FILE: /path/a.py
LINES: 1
CODE:
    a()
VERIFIED: Yes

FINDING: Second
FILE: /path/b.py
LINES: 2
CODE:
    b()
VERIFIED: Yes
"""
        blocks = extract_finding_blocks(text)
        assert len(blocks) == 2
        assert blocks[0].finding == "First"
        assert blocks[1].finding == "Second"

    def test_no_findings(self):
        """Text with no FINDING should return empty list."""
        from validate_agent_compliance import extract_finding_blocks

        text = "Just some text without any findings."
        blocks = extract_finding_blocks(text)
        assert len(blocks) == 0

    def test_markdown_bullet_fields_extraction(self):
        """Fields with markdown bullets/emphasis/backticks should be parsed."""
        from validate_agent_compliance import extract_finding_blocks

        text = """
**FINDING:** Markdown formatted issue
- **FILE:** `/path/to/file.py`
- **LINES:** 12-15
- **CODE:**
```python
def fn():
    return 1
```
- **VERIFIED:** Yes
"""
        blocks = extract_finding_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].file_path == "/path/to/file.py"
        assert blocks[0].lines == "12-15"
        assert "def fn()" in (blocks[0].code or "")
        assert blocks[0].verified == "Yes"

    def test_inline_code_field_extraction(self):
        """Single-line CODE fields should count as complete evidence."""
        from validate_agent_compliance import extract_finding_blocks

        text = """
FINDING: Inline code issue
FILE: /path/to/file.py
LINES: 75
CODE: ROUTING_RECORD_PATH = Path(".agent_bus/meta/post_merge_routing.json")
VERIFIED: Yes
"""
        blocks = extract_finding_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].code == 'ROUTING_RECORD_PATH = Path(".agent_bus/meta/post_merge_routing.json")'

    def test_inline_code_field_passes_full_compliance(self):
        """Inline CODE evidence should not trigger incomplete-block compliance failures."""
        import inspect

        line_no = inspect.currentframe().f_lineno + 1
        inline_code_sentinel = "inline-code-sentinel"
        file_path = os.path.abspath(__file__)
        output = f"""
STATUS.md reviewed.

### CHECKED
- Verified inline code extraction.

### NOT_CHECKED
- No additional runtime evidence required.

FINDING: Inline code issue
FILE: {file_path}
LINES: {line_no}
CODE: inline_code_sentinel = "inline-code-sentinel"
VERIFIED: Yes

### Verdict
VERDICT: REQUEST_CHANGES
"""
        result = check_compliance(
            output,
            verify_files=True,
            verify_code=True,
            strict=True,
        )
        assert result["compliant"] is True
        assert result["blocks_with_code"] == 1
        assert result["incomplete_blocks"] == 0

    def test_ellipsis_excerpt_passes_code_verification(self):
        """Ellipsis-truncated excerpts should verify when cited segments appear in order."""
        import inspect

        start_line = inspect.currentframe().f_lineno + 1
        ellipsis_alpha = "alpha"
        bridge_middle_noise = "middle"
        ellipsis_omega = "omega"
        end_line = inspect.currentframe().f_lineno
        file_path = os.path.abspath(__file__)
        output = f"""
STATUS.md reviewed.

### CHECKED
- Verified ellipsis excerpt parsing.

### NOT_CHECKED
- No broader code review needed.

FINDING: Ellipsis excerpt
FILE: {file_path}
LINES: {start_line}-{end_line}
CODE:
    ellipsis_alpha = "alpha"
    ...
    ellipsis_omega = "omega"
VERIFIED: Yes

### Verdict
VERDICT: REQUEST_CHANGES
"""
        result = check_compliance(output, verify_files=True, verify_code=True, strict=True)
        assert result["compliant"] is True
        assert result["fabrications"] == 0


class TestApprovalWithoutFindingsEvidence:
    """Approval verdicts without findings should pass with explicit CHECKED evidence."""

    def test_approval_with_checked_section_is_compliant(self):
        output = """
### CHECKED
- /path/a.py:10 reserved-field validation
- /path/b.py:25 projection order guard

### VERDICT
SECURE
"""
        result = check_compliance(output)
        assert result["compliant"] is True


class TestHookIntegration:
    """Integration tests for the validation hook (2026-02-02 advisor recommendation)."""

    @pytest.fixture
    def hook_path(self):
        """Get path to hook script."""
        import os
        return os.path.normpath(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), '..', '..', '..',
            '.claude', 'hooks', 'validate-agent-compliance.sh'
        ))

    @pytest.fixture
    def validator_path(self):
        """Get path to validator script."""
        import os
        return os.path.normpath(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), '..', '..',
            'tools', 'runners', 'validate_agent_compliance.py'
        ))

    def test_hook_script_exists(self, hook_path):
        """Hook script should exist at expected path."""
        import os
        assert os.path.exists(hook_path), f"Hook not found: {hook_path}"

    def test_hook_is_executable(self, hook_path):
        """Hook script should be executable."""
        import os
        assert os.access(hook_path, os.X_OK), f"Hook not executable: {hook_path}"

    def test_validator_script_exists(self, validator_path):
        """Validator script should exist at expected path."""
        import os
        assert os.path.exists(validator_path), f"Validator not found: {validator_path}"

    def test_hook_contains_fail_closed_logic(self, hook_path):
        """Hook should contain fail-closed security pattern."""
        with open(hook_path, 'r') as f:
            content = f.read()

        # Check for fail-closed comments and logic
        assert 'Fail closed' in content or 'fail closed' in content, \
            "Hook should document fail-closed behavior"
        assert '"decision": "block"' in content, \
            "Hook should return block decisions"

        # Check that missing validator causes block, not exit 0 silently
        assert 'Validator script not found' in content or 'cannot verify' in content, \
            "Hook should block when validator missing"

    def test_hook_handles_review_agents(self, hook_path):
        """Hook should validate review agent types."""
        with open(hook_path, 'r') as f:
            content = f.read()

        # All 9 review agents should be handled
        review_agents = ['verifier', 'adversary', 'expert', 'structural-proof',
                        'grounding', 'fuzzer', 'translator', 'visualizer', 'advisor']
        for agent in review_agents:
            assert agent in content, f"Hook should handle {agent} agent"

    def test_hook_skips_non_review_agents(self, hook_path):
        """Hook should skip validation for non-review agent types."""
        with open(hook_path, 'r') as f:
            content = f.read()

        # Should have logic to skip certain agent types
        assert 'exit 0' in content and ('Explore' in content or 'Bash' in content or '*' in content), \
            "Hook should skip non-review agents"


class TestCodeBlockExtractionWithEmptyLines:
    """Test that extract_finding_blocks handles empty lines correctly (2026-02-02 fix)."""

    def test_extract_code_with_empty_line(self):
        """extract_finding_blocks should capture CODE with empty lines."""
        from validate_agent_compliance import extract_finding_blocks

        text = """
FINDING: Code with blank
FILE: /path/file.py
LINES: 1-10
CODE:
    def foo():
        pass

    def bar():
        pass
VERIFIED: Yes
"""
        blocks = extract_finding_blocks(text)
        assert len(blocks) == 1
        # The code block should include content after the empty line
        assert blocks[0].code is not None
        assert "foo" in blocks[0].code
        assert "bar" in blocks[0].code

    def test_extract_code_multiple_empty_lines(self):
        """extract_finding_blocks should handle multiple consecutive empty lines."""
        from validate_agent_compliance import extract_finding_blocks

        text = """
FINDING: Multi-blank code
FILE: /path/file.py
LINES: 1-15
CODE:
    class A:
        pass


    class B:
        pass
VERIFIED: Yes
"""
        blocks = extract_finding_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].code is not None
        assert "class A" in blocks[0].code
        assert "class B" in blocks[0].code


class TestFabricationClassification:
    """True fabrication must hard-block compliance (2026-02-08 severity split)."""

    def test_completely_fabricated_code_blocks(self):
        """Code with zero resemblance to actual file content must block."""
        import os
        this_file = os.path.abspath(__file__)
        # Lines 1-5 of this file are the module docstring.
        # Cite completely unrelated code — no token overlap.
        output = f"""
STATUS.md reviewed.

FINDING: Fabricated code
FILE: {this_file}
LINES: 1-5
CODE:
    async function handleRequest(req, res) {{
        const payload = await req.json();
        return res.status(200).send(payload);
    }}
VERIFIED: Yes
"""
        result = check_compliance(output, verify_files=True, verify_code=True, strict=True)
        assert result["compliant"] is False
        assert result["fabrications"] >= 1
        assert result["imprecise_citations"] == 0
        assert any("FABRICATION" in v for v in result["violations"])

    def test_nonexistent_file_is_fabrication(self):
        """Citation of a file that doesn't exist must be classified as fabrication."""
        output = """
STATUS.md reviewed.

FINDING: Phantom file
FILE: /this/file/does/not/exist/anywhere/phantom.py
LINES: 1-5
CODE:
    def phantom():
        pass
VERIFIED: Yes
"""
        result = check_compliance(output, verify_files=True, verify_code=True, strict=True)
        assert result["compliant"] is False
        assert result["fabrications"] >= 1


class TestHookExecutionAgainstMalformedPayloads:
    """B2 proof: hook script blocks malformed agent_type payloads (deferred_cleanup wave).

    These tests execute the actual validate-agent-compliance.sh hook script
    with crafted JSON inputs to prove fail-closed behavior.
    """

    @pytest.fixture
    def hook_path(self):
        """Get path to hook script."""
        path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), '..', '..', '..',
            '.claude', 'hooks', 'validate-agent-compliance.sh'
        ))
        assert os.path.exists(path), f"Hook not found: {path}"
        return path

    def _run_hook(self, hook_path, payload):
        """Run hook script with JSON payload on stdin, return (stdout, exit_code)."""
        import subprocess
        result = subprocess.run(
            ['bash', hook_path],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip(), result.returncode

    def test_missing_agent_type_blocks(self, hook_path):
        """Payload with no agent_type must be blocked (fail-closed)."""
        import json
        payload = json.dumps({"agent_transcript_path": "/tmp/fake.jsonl"})
        stdout, exit_code = self._run_hook(hook_path, payload)
        assert exit_code == 0, "Hook should exit 0 (decision is in JSON)"
        assert stdout, "Missing agent_type should produce block JSON"
        decision = json.loads(stdout)
        assert decision["decision"] == "block", \
            f"Missing agent_type should block, got: {decision}"

    def test_unknown_agent_type_blocks(self, hook_path):
        """Payload with unrecognized agent_type must be blocked (fail-closed)."""
        import json
        payload = json.dumps({
            "agent_type": "not-a-real-agent-type",
            "agent_transcript_path": "/tmp/fake.jsonl",
        })
        stdout, exit_code = self._run_hook(hook_path, payload)
        assert exit_code == 0
        assert stdout, "Unknown agent_type should produce block JSON"
        decision = json.loads(stdout)
        assert decision["decision"] == "block"
        assert "Unknown agent_type" in decision.get("reason", "")

    def test_empty_payload_blocks(self, hook_path):
        """Empty JSON object must be blocked (fail-closed)."""
        import json
        payload = json.dumps({})
        stdout, exit_code = self._run_hook(hook_path, payload)
        assert exit_code == 0
        assert stdout, "Empty payload should produce block JSON"
        decision = json.loads(stdout)
        assert decision["decision"] == "block", \
            f"Empty payload should block, got: {decision}"

    def test_valid_agent_type_missing_transcript_blocks(self, hook_path):
        """Known review agent_type with empty transcript should block (fail-closed)."""
        import json
        # verifier is a known review agent; with no transcript path, hook now blocks
        payload = json.dumps({
            "agent_type": "verifier",
            "agent_transcript_path": "",
        })
        stdout, exit_code = self._run_hook(hook_path, payload)
        assert exit_code == 0
        assert stdout, "Hook should emit block JSON for missing transcript"
        decision = json.loads(stdout)
        assert decision.get("decision") == "block", \
            f"Missing transcript should block (fail-closed), got: {decision}"


class TestImpreciseCitationClassification:
    """Near-match/paraphrase must warn but NOT block compliance (2026-02-08 severity split)."""

    def test_imprecise_citation_unit_classification(self):
        """verify_code_at_location must classify near-match as imprecise_citation.

        Uses code sharing structural patterns (frozenset, assignment, numbers)
        but with different identifiers, producing char similarity ~0.35 (above 0.3
        fabrication threshold) but below 0.7 pass threshold.
        """
        import tempfile
        from validate_agent_compliance import verify_code_at_location, FindingBlock

        # Actual file content: constants with frozenset + numbers
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir='.', delete=False) as f:
            f.write('KERNEL_RESERVED = frozenset({"_mode", "_result"})\n')
            f.write('MAX_DEPTH = 50\n')
            f.write('TIMEOUT = 3000\n')
            tmp_path = f.name

        try:
            # Claimed code: same structure (frozenset, assignments, numbers)
            # but different identifiers → char similarity ~0.35, token Jaccard ~0.09
            block = FindingBlock(
                finding="Near-match code",
                file_path=os.path.abspath(tmp_path),
                lines="1-3",
                code='BRIDGE_PROJECTIONS = frozenset({"_step", "_trace"})\nMIN_ITERATIONS = 200\nDEADLINE = 8000',
                verified="Yes",
            )
            is_valid, error, severity = verify_code_at_location(block)

            assert is_valid is False, "Structurally similar but different code should not pass"
            assert severity == "imprecise_citation", (
                f"Expected imprecise_citation, got {severity}. Error: {error}"
            )
        finally:
            os.unlink(tmp_path)

    def test_imprecise_citation_does_not_block_compliance(self):
        """check_compliance must remain compliant when only imprecise citations found."""
        import tempfile

        # Create temp file with known content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir='.', delete=False) as f:
            f.write('KERNEL_RESERVED = frozenset({"_mode", "_result"})\n')
            f.write('MAX_DEPTH = 50\n')
            f.write('TIMEOUT = 3000\n')
            tmp_path = os.path.abspath(f.name)

        try:
            output = f"""
STATUS.md reviewed.

### CHECKED
- Verified near-match citation handling.

### NOT_CHECKED
- No exact-code match expected in this fixture.

FINDING: Near-match code
FILE: {tmp_path}
LINES: 1-3
CODE:
    BRIDGE_PROJECTIONS = frozenset({{"_step", "_trace"}})
    MIN_ITERATIONS = 200
    DEADLINE = 8000
VERIFIED: Yes

### Verdict
VERDICT: REQUEST_CHANGES
"""
            result = check_compliance(output, verify_files=True, verify_code=True, strict=True)
            # Must NOT be blocked — imprecise citation is a warning
            assert result["compliant"] is True, (
                f"Imprecise citation should not block. Violations: {result['violations']}"
            )
            assert result["imprecise_citations"] >= 1
            assert result["fabrications"] == 0
            assert not any("FABRICATION" in v for v in result["violations"])
            # Details should still be reported
            assert len(result.get("imprecise_citation_details", [])) >= 1
        finally:
            os.unlink(tmp_path)
