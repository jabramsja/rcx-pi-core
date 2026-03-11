"""
Wave C Coverage Gate Tests — net-new test coverage anchors.

Tests named projection counts for 7 seeds missing dedicated tests,
skip/xfail theater prevention (AST audit), and North Star invariant
governance lock. L4_ENABLER class: no runtime dir changes.
"""
import ast
import re

import pytest

from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from tests.repo_root import REPO_ROOT

MU_DIR = REPO_ROOT / "mu"
TESTS_DIR = MU_DIR / "tests"

# Expected counts (must match test_seed_counts.py::EXPECTED_COUNTS)
EXPECTED_COUNTS = {
    "eval.v1.json": 7,
    "terminal_classify.v1.json": 7,
    "evidence_walker.v1.json": 4,
    "metabolization.v1.json": 6,
    "metabolize_cycle.v1.json": 15,
    "paxos_demo.v1.json": 6,
    "hemispheres.v1.json": 12,
}


def _load_seed(name):
    """Load a seed and return parsed JSON."""
    seed_path = get_seed_path(name)
    return load_verified_seed(seed_path, verify=True)


def _get_projection_ids(seed):
    """Extract projection IDs from a seed."""
    return [p["id"] for p in seed.get("projections", [])]


# =============================================================================
# Named Projection Count Tests
# =============================================================================

class TestNamedProjectionCounts:
    """Named tests for 7 seeds that only had parametrized coverage.

    These complement test_seed_counts.py (which has parametrized coverage
    for all 19 seeds). Named tests provide clearer failure diagnostics
    and serve as per-seed gate evidence anchors.
    """

    def test_eval_v1_projection_count(self):
        """eval.v1.json has 7 projections (deep_eval traversal)."""
        seed = _load_seed("eval.v1.json")
        ids = _get_projection_ids(seed)
        assert len(ids) == EXPECTED_COUNTS["eval.v1.json"], \
            f"eval.v1.json: expected {EXPECTED_COUNTS['eval.v1.json']}, found {len(ids)}: {ids}"

    def test_terminal_classify_v1_projection_count(self):
        """terminal_classify.v1.json has 7 projections."""
        seed = _load_seed("terminal_classify.v1.json")
        ids = _get_projection_ids(seed)
        assert len(ids) == EXPECTED_COUNTS["terminal_classify.v1.json"], \
            f"terminal_classify.v1.json: expected {EXPECTED_COUNTS['terminal_classify.v1.json']}, found {len(ids)}: {ids}"

    def test_evidence_walker_v1_projection_count(self):
        """evidence_walker.v1.json has 4 projections."""
        seed = _load_seed("evidence_walker.v1.json")
        ids = _get_projection_ids(seed)
        assert len(ids) == EXPECTED_COUNTS["evidence_walker.v1.json"], \
            f"evidence_walker.v1.json: expected {EXPECTED_COUNTS['evidence_walker.v1.json']}, found {len(ids)}: {ids}"

    def test_metabolization_v1_projection_count(self):
        """metabolization.v1.json has 6 projections."""
        seed = _load_seed("metabolization.v1.json")
        ids = _get_projection_ids(seed)
        assert len(ids) == EXPECTED_COUNTS["metabolization.v1.json"], \
            f"metabolization.v1.json: expected {EXPECTED_COUNTS['metabolization.v1.json']}, found {len(ids)}: {ids}"

    def test_metabolize_cycle_v1_projection_count(self):
        """metabolize_cycle.v1.json has 15 projections."""
        seed = _load_seed("metabolize_cycle.v1.json")
        ids = _get_projection_ids(seed)
        assert len(ids) == EXPECTED_COUNTS["metabolize_cycle.v1.json"], \
            f"metabolize_cycle.v1.json: expected {EXPECTED_COUNTS['metabolize_cycle.v1.json']}, found {len(ids)}: {ids}"

    def test_paxos_demo_v1_projection_count(self):
        """paxos_demo.v1.json has 6 projections."""
        seed = _load_seed("paxos_demo.v1.json")
        ids = _get_projection_ids(seed)
        assert len(ids) == EXPECTED_COUNTS["paxos_demo.v1.json"], \
            f"paxos_demo.v1.json: expected {EXPECTED_COUNTS['paxos_demo.v1.json']}, found {len(ids)}: {ids}"

    def test_hemispheres_v1_projection_count(self):
        """hemispheres.v1.json has 12 projections."""
        seed = _load_seed("hemispheres.v1.json")
        ids = _get_projection_ids(seed)
        assert len(ids) == EXPECTED_COUNTS["hemispheres.v1.json"], \
            f"hemispheres.v1.json: expected {EXPECTED_COUNTS['hemispheres.v1.json']}, found {len(ids)}: {ids}"


# =============================================================================
# Skip/Xfail Theater Prevention
# =============================================================================

class TestSkipXfailTheaterPrevention:
    """AST audit ensuring all skip/xfail markers have documented reasons.

    Prevents future test theater: bare @pytest.mark.skip (without reason)
    or @pytest.mark.xfail (without reason) silently hides failures.
    """

    def _collect_skip_xfail_decorators(self):
        """Scan all test files via AST for skip/xfail/skipif decorators."""
        findings = []
        for py_file in sorted(TESTS_DIR.rglob("test_*.py")):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                for decorator in node.decorator_list:
                    marker_name = self._extract_marker_name(decorator)
                    if marker_name in ("skip", "xfail", "skipif"):
                        has_reason = self._has_reason_kwarg(decorator)
                        findings.append({
                            "file": str(py_file.relative_to(REPO_ROOT)),
                            "line": decorator.lineno,
                            "marker": marker_name,
                            "has_reason": has_reason,
                            "node_name": node.name,
                        })
        return findings

    def _extract_marker_name(self, decorator):
        """Extract pytest.mark.X name from a decorator AST node."""
        # @pytest.mark.skip / @pytest.mark.skipif / @pytest.mark.xfail
        if isinstance(decorator, ast.Call):
            return self._extract_marker_name(decorator.func)
        if isinstance(decorator, ast.Attribute):
            # Check for pytest.mark.<name> pattern
            if decorator.attr in ("skip", "xfail", "skipif"):
                return decorator.attr
        return None

    def _has_reason_kwarg(self, decorator):
        """Check if a decorator Call node has a 'reason' keyword argument."""
        if isinstance(decorator, ast.Call):
            for kw in decorator.keywords:
                if kw.arg == "reason":
                    # Verify it's not an empty string
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        return len(kw.value.value.strip()) > 0
                    return True  # non-constant reason (variable, f-string, etc.)
            return False
        # Bare decorator (no call) — e.g., @pytest.mark.skip without ()
        return False

    def test_all_skip_markers_have_reasons(self):
        """Every @pytest.mark.skip must have a reason parameter."""
        findings = self._collect_skip_xfail_decorators()
        skip_without_reason = [
            f for f in findings
            if f["marker"] == "skip" and not f["has_reason"]
        ]
        assert not skip_without_reason, (
            f"Found {len(skip_without_reason)} @pytest.mark.skip without reason:\n"
            + "\n".join(
                f"  {f['file']}:{f['line']} ({f['node_name']})"
                for f in skip_without_reason
            )
        )

    def test_all_xfail_markers_have_reasons(self):
        """Every @pytest.mark.xfail must have a reason parameter."""
        findings = self._collect_skip_xfail_decorators()
        xfail_without_reason = [
            f for f in findings
            if f["marker"] == "xfail" and not f["has_reason"]
        ]
        assert not xfail_without_reason, (
            f"Found {len(xfail_without_reason)} @pytest.mark.xfail without reason:\n"
            + "\n".join(
                f"  {f['file']}:{f['line']} ({f['node_name']})"
                for f in xfail_without_reason
            )
        )

    def test_all_skipif_markers_have_reasons(self):
        """Every @pytest.mark.skipif must have a reason parameter."""
        findings = self._collect_skip_xfail_decorators()
        skipif_without_reason = [
            f for f in findings
            if f["marker"] == "skipif" and not f["has_reason"]
        ]
        assert not skipif_without_reason, (
            f"Found {len(skipif_without_reason)} @pytest.mark.skipif without reason:\n"
            + "\n".join(
                f"  {f['file']}:{f['line']} ({f['node_name']})"
                for f in skipif_without_reason
            )
        )

    def test_no_bare_skip_decorators(self):
        """No bare @pytest.mark.skip (without parentheses) — always use skip(reason=...)."""
        findings = self._collect_skip_xfail_decorators()
        # A bare skip is marker=skip with no reason (the decorator isn't a Call node)
        bare_skips = [
            f for f in findings
            if f["marker"] == "skip" and not f["has_reason"]
        ]
        assert not bare_skips, (
            f"Found {len(bare_skips)} bare @pytest.mark.skip:\n"
            + "\n".join(
                f"  {f['file']}:{f['line']} ({f['node_name']})"
                for f in bare_skips
            )
        )


# =============================================================================
# North Star Invariant Governance Lock
# =============================================================================

class TestNorthStarInvariantLock:
    """Verify the 15 North Star invariants in TASKS.md haven't drifted.

    Checks: count, numbering continuity, and key anchoring phrases.
    """

    TASKS_PATH = REPO_ROOT / "TASKS.md"

    # Key phrases that MUST appear in the North Star section (one per invariant).
    # These are stable anchoring phrases, not full text matches.
    INVARIANT_ANCHORS = {
        1: "structure is the primitive",
        2: "Code = data",
        3: "Stall",  # "Stall → Fix → Trace → Closure"
        4: "explicit, deterministic, and measurable",
        5: "Emergence must be attributable",
        6: "Host languages are scaffolding",
        7: "native routing states",
        8: "Seeds must be minimal",
        9: "Determinism is a hard invariant",
        10: "pressure vessel",
        11: "closure actually emerge",
        12: "reduce host smuggling",
        13: "L3 Parity",
        14: "Seeds must declare their execution layer",
        15: "True self-hosting is the path",
    }

    def _extract_north_star_section(self):
        """Extract the North Star section from TASKS.md."""
        content = self.TASKS_PATH.read_text(encoding="utf-8")
        # Find section start
        match = re.search(r"^## North Star.*$", content, re.MULTILINE)
        assert match, "TASKS.md must contain '## North Star' section"
        start = match.end()
        # Find next section (## heading)
        next_section = re.search(r"^## ", content[start:], re.MULTILINE)
        if next_section:
            return content[start:start + next_section.start()]
        return content[start:]

    def test_invariant_count_is_15(self):
        """North Star section has exactly 15 numbered invariants."""
        section = self._extract_north_star_section()
        # Count lines starting with a number followed by period
        numbered = re.findall(r"^\d+\.", section, re.MULTILINE)
        assert len(numbered) == 15, (
            f"Expected 15 North Star invariants, found {len(numbered)}. "
            f"Numbers found: {numbered}"
        )

    def test_invariant_numbering_continuous(self):
        """Invariants are numbered 1-15 without gaps."""
        section = self._extract_north_star_section()
        numbers = [int(m) for m in re.findall(r"^(\d+)\.", section, re.MULTILINE)]
        expected = list(range(1, 16))
        assert numbers == expected, (
            f"Invariant numbering should be 1-15, got: {numbers}"
        )

    def test_invariant_anchor_phrases_present(self):
        """Each invariant contains its expected anchoring phrase."""
        section = self._extract_north_star_section()
        missing = []
        for num, anchor in self.INVARIANT_ANCHORS.items():
            if anchor not in section:
                missing.append(f"Invariant {num}: missing anchor '{anchor}'")
        assert not missing, (
            f"North Star anchor phrases missing:\n" + "\n".join(missing)
        )

    def test_section_header_exact(self):
        """North Star section header is '## North Star (Keep This True)'."""
        content = self.TASKS_PATH.read_text(encoding="utf-8")
        assert "## North Star (Keep This True)" in content, \
            "TASKS.md must contain exact header '## North Star (Keep This True)'"
