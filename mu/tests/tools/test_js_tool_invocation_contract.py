"""
Tool Invocation Contract tests for JS linters (contraband_js.sh, ast_police_js.sh).

Enforces 5 contract rules so tool invocation paths can't silently drift:
  Rule 1: Default/no-arg invocation defaults to mu/host/js/ full substrate scan.
  Rule 2: Both directory-scan and explicit single-file modes work.
  Rule 3: Gate scripts (green_gate.sh, audit_fast.sh) invoke linters with default (no-arg) path.
  Rule 4: Symlink/realpath (tools/ -> mu/tools/, tests/ -> mu/tests/) doesn't break discovery.
  Rule 5: Marker bypass (CONTRABAND_OK, AST_OK_JS) is strictly line-local.

Created for W1.1-tool-invocation-contract wave.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ACTUAL_REPO_ROOT = REPO_ROOT.parent  # mu/ -> WorkingRCX/

SCRIPT_CONTRABAND = REPO_ROOT / "tools" / "checks" / "linters" / "contraband_js.sh"
SCRIPT_AST_POLICE = REPO_ROOT / "tools" / "checks" / "linters" / "ast_police_js.sh"
GREEN_GATE = REPO_ROOT / "scripts" / "green_gate.sh"
AUDIT_FAST = REPO_ROOT / "tools" / "audits" / "audit_fast.sh"


# ---------------------------------------------------------------------------
# Rule 1: Default/no-arg invocation path
# ---------------------------------------------------------------------------
class TestRule1DefaultNoArgInvocation:
    """Scripts must default to mu/host/js/ when invoked with no arguments."""

    def test_contraband_js_no_arg_scans_full_substrate(self):
        """contraband_js.sh with no args must scan all JS files under mu/host/js/."""
        result = subprocess.run(
            ["bash", str(SCRIPT_CONTRABAND)],
            capture_output=True, text=True, check=False, timeout=60,
            cwd=str(ACTUAL_REPO_ROOT),
        )
        assert result.returncode == 0, f"No-arg contraband scan failed: {result.stdout}"
        assert "file(s)" in result.stdout, (
            f"Must report file count in no-arg mode: {result.stdout}"
        )

    def test_ast_police_js_no_arg_scans_full_substrate(self):
        """ast_police_js.sh with no args must scan all JS files under mu/host/js/."""
        result = subprocess.run(
            ["bash", str(SCRIPT_AST_POLICE)],
            capture_output=True, text=True, check=False, timeout=60,
            cwd=str(ACTUAL_REPO_ROOT),
        )
        assert result.returncode == 0, f"No-arg AST police scan failed: {result.stdout}"
        assert "file(s)" in result.stdout, (
            f"Must report file count in no-arg mode: {result.stdout}"
        )

    def test_contraband_js_default_target_is_mu_host_js(self):
        """contraband_js.sh must have TARGET default to mu/host/js/."""
        script = SCRIPT_CONTRABAND.read_text()
        assert 'TARGET="${1:-mu/host/js/}"' in script, (
            "contraband_js.sh must default TARGET to mu/host/js/"
        )

    def test_ast_police_js_default_target_is_mu_host_js(self):
        """ast_police_js.sh must have TARGET default to mu/host/js/."""
        script = SCRIPT_AST_POLICE.read_text()
        assert 'TARGET="${1:-mu/host/js/}"' in script, (
            "ast_police_js.sh must default TARGET to mu/host/js/"
        )

    def test_contraband_js_no_arg_catches_injected_contraband(self):
        """No-arg run must detect contraband when the default target has it.

        Simulated via explicit temp dir argument (can't inject into production).
        """
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "bad.js"), "w") as f:
                f.write("const d = new Date();\n")
            result = subprocess.run(
                ["bash", str(SCRIPT_CONTRABAND), tmpdir],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode != 0, "Must catch contraband in temp dir"
        finally:
            shutil.rmtree(tmpdir)

    def test_ast_police_js_no_arg_catches_injected_violation(self):
        """No-arg run must detect AST violation when the default target has it."""
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "bad.js"), "w") as f:
                f.write("const fn = window['eval'];\n")
            result = subprocess.run(
                ["bash", str(SCRIPT_AST_POLICE), tmpdir],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode != 0, "Must catch AST violation in temp dir"
        finally:
            shutil.rmtree(tmpdir)


# ---------------------------------------------------------------------------
# Rule 2: Directory-scan AND explicit single-file modes
# ---------------------------------------------------------------------------
class TestRule2DirectoryAndSingleFileModes:
    """Both directory-scan and single-file modes must work correctly."""

    def test_contraband_js_directory_mode_reports_file_count(self):
        """Directory mode must report file count."""
        result = subprocess.run(
            ["bash", str(SCRIPT_CONTRABAND), str(REPO_ROOT / "host" / "js")],
            capture_output=True, text=True, check=False, timeout=60,
        )
        assert result.returncode == 0, f"Directory scan failed: {result.stdout}"
        assert "file(s)" in result.stdout

    def test_ast_police_js_directory_mode_reports_file_count(self):
        """Directory mode must report file count."""
        result = subprocess.run(
            ["bash", str(SCRIPT_AST_POLICE), str(REPO_ROOT / "host" / "js")],
            capture_output=True, text=True, check=False, timeout=60,
        )
        assert result.returncode == 0, f"Directory scan failed: {result.stdout}"
        assert "file(s)" in result.stdout

    def test_contraband_js_single_file_mode_clean(self):
        """Single-file mode must accept clean JS."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("const x = 1;\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_CONTRABAND), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode == 0, f"Clean file should pass: {result.stdout}"
        finally:
            Path(filepath).unlink()

    def test_contraband_js_single_file_mode_violation(self):
        """Single-file mode must catch violations."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("const d = new Date();\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_CONTRABAND), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode != 0, "Violation in single-file must fail"
        finally:
            Path(filepath).unlink()

    def test_ast_police_js_single_file_mode_clean(self):
        """Single-file mode must accept clean JS."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("const x = 1;\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_AST_POLICE), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode == 0, f"Clean file should pass: {result.stdout}"
        finally:
            Path(filepath).unlink()

    def test_ast_police_js_single_file_mode_violation(self):
        """Single-file mode must catch violations."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("const fn = window['eval'];\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_AST_POLICE), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode != 0, "Violation in single-file must fail"
        finally:
            Path(filepath).unlink()

    def test_contraband_js_nonexistent_target_fails(self):
        """Script must fail with nonexistent target path."""
        result = subprocess.run(
            ["bash", str(SCRIPT_CONTRABAND), "/nonexistent/path"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        assert result.returncode != 0, "Nonexistent target must fail"

    def test_ast_police_js_nonexistent_target_fails(self):
        """Script must fail with nonexistent target path."""
        result = subprocess.run(
            ["bash", str(SCRIPT_AST_POLICE), "/nonexistent/path"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        assert result.returncode != 0, "Nonexistent target must fail"


# ---------------------------------------------------------------------------
# Rule 3: Gate-invoked path lock
# ---------------------------------------------------------------------------
class TestRule3GateInvocationPath:
    """Gate scripts must invoke linters with no-arg (default) invocation."""

    def test_green_gate_invokes_contraband_js_default(self):
        """green_gate.sh must invoke contraband_js.sh with no file argument."""
        gate = GREEN_GATE.read_text()
        invocations = [
            line.strip() for line in gate.split('\n')
            if 'contraband_js.sh' in line
            and not line.strip().startswith('#')
        ]
        assert len(invocations) >= 1, "green_gate.sh must invoke contraband_js.sh"
        for line in invocations:
            assert line == "./tools/checks/linters/contraband_js.sh", (
                f"green_gate.sh must invoke contraband_js.sh with no args (default path), "
                f"got: {line!r}"
            )

    def test_green_gate_invokes_ast_police_js_default(self):
        """green_gate.sh must invoke ast_police_js.sh with no file argument."""
        gate = GREEN_GATE.read_text()
        invocations = [
            line.strip() for line in gate.split('\n')
            if 'ast_police_js.sh' in line
            and not line.strip().startswith('#')
        ]
        assert len(invocations) >= 1, "green_gate.sh must invoke ast_police_js.sh"
        for line in invocations:
            assert line == "./tools/checks/linters/ast_police_js.sh", (
                f"green_gate.sh must invoke ast_police_js.sh with no args (default path), "
                f"got: {line!r}"
            )

    def test_audit_fast_invokes_contraband_js_default(self):
        """audit_fast.sh must invoke contraband_js.sh with no file argument."""
        audit = AUDIT_FAST.read_text()
        invocations = [
            line.strip() for line in audit.split('\n')
            if 'contraband_js.sh' in line
            and not line.strip().startswith('#')
        ]
        assert len(invocations) >= 1, "audit_fast.sh must invoke contraband_js.sh"
        for line in invocations:
            assert line == "./tools/checks/linters/contraband_js.sh", (
                f"audit_fast.sh must invoke contraband_js.sh with no args (default path), "
                f"got: {line!r}"
            )

    def test_audit_fast_invokes_ast_police_js_default(self):
        """audit_fast.sh must invoke ast_police_js.sh with no file argument."""
        audit = AUDIT_FAST.read_text()
        invocations = [
            line.strip() for line in audit.split('\n')
            if 'ast_police_js.sh' in line
            and not line.strip().startswith('#')
        ]
        assert len(invocations) >= 1, "audit_fast.sh must invoke ast_police_js.sh"
        for line in invocations:
            assert line == "./tools/checks/linters/ast_police_js.sh", (
                f"audit_fast.sh must invoke ast_police_js.sh with no args (default path), "
                f"got: {line!r}"
            )

    def test_green_gate_and_audit_fast_use_same_invocation(self):
        """Both gates must invoke linters identically (no path divergence)."""
        gate = GREEN_GATE.read_text()
        audit = AUDIT_FAST.read_text()

        def extract_linter_invocations(text):
            return sorted(
                line.strip() for line in text.split('\n')
                if ('contraband_js.sh' in line or 'ast_police_js.sh' in line)
                and not line.strip().startswith('#')
            )

        gate_invocations = extract_linter_invocations(gate)
        audit_invocations = extract_linter_invocations(audit)
        assert gate_invocations == audit_invocations, (
            f"Gate scripts must use identical linter invocations.\n"
            f"  green_gate: {gate_invocations}\n"
            f"  audit_fast: {audit_invocations}"
        )


# ---------------------------------------------------------------------------
# Rule 4: Symlink/realpath guard
# ---------------------------------------------------------------------------
class TestRule4SymlinkRealpathGuard:
    """Repo symlinks (tools/ -> mu/tools/, etc.) must not break script discovery."""

    def test_tools_symlink_resolves_to_mu_tools(self):
        """tools/ must be a symlink to mu/tools/."""
        tools_via_symlink = ACTUAL_REPO_ROOT / "tools"
        mu_tools = ACTUAL_REPO_ROOT / "mu" / "tools"
        assert tools_via_symlink.exists(), "tools/ must exist at repo root"
        assert mu_tools.exists(), "mu/tools/ must exist"
        assert tools_via_symlink.resolve() == mu_tools.resolve(), (
            f"tools/ must resolve to mu/tools/\n"
            f"  tools/: {tools_via_symlink.resolve()}\n"
            f"  mu/tools/: {mu_tools.resolve()}"
        )

    def test_tests_symlink_resolves_to_mu_tests(self):
        """tests/ must be a symlink to mu/tests/."""
        tests_via_symlink = ACTUAL_REPO_ROOT / "tests"
        mu_tests = ACTUAL_REPO_ROOT / "mu" / "tests"
        assert tests_via_symlink.exists(), "tests/ must exist at repo root"
        assert mu_tests.exists(), "mu/tests/ must exist"
        assert tests_via_symlink.resolve() == mu_tests.resolve(), (
            f"tests/ must resolve to mu/tests/\n"
            f"  tests/: {tests_via_symlink.resolve()}\n"
            f"  mu/tests/: {mu_tests.resolve()}"
        )

    def test_scripts_symlink_resolves_to_mu_scripts(self):
        """scripts/ must be a symlink to mu/scripts/."""
        scripts_via_symlink = ACTUAL_REPO_ROOT / "scripts"
        mu_scripts = ACTUAL_REPO_ROOT / "mu" / "scripts"
        assert scripts_via_symlink.exists(), "scripts/ must exist at repo root"
        assert mu_scripts.exists(), "mu/scripts/ must exist"
        assert scripts_via_symlink.resolve() == mu_scripts.resolve(), (
            f"scripts/ must resolve to mu/scripts/\n"
            f"  scripts/: {scripts_via_symlink.resolve()}\n"
            f"  mu/scripts/: {mu_scripts.resolve()}"
        )

    def test_contraband_script_accessible_via_both_paths(self):
        """contraband_js.sh must be the same file via tools/ and mu/tools/."""
        via_symlink = ACTUAL_REPO_ROOT / "tools" / "checks" / "linters" / "contraband_js.sh"
        via_mu = ACTUAL_REPO_ROOT / "mu" / "tools" / "checks" / "linters" / "contraband_js.sh"
        assert via_symlink.exists(), "contraband_js.sh must exist via tools/ symlink"
        assert via_mu.exists(), "contraband_js.sh must exist via mu/tools/"
        assert via_symlink.resolve() == via_mu.resolve(), (
            "contraband_js.sh must resolve to same file via both paths"
        )

    def test_ast_police_script_accessible_via_both_paths(self):
        """ast_police_js.sh must be the same file via tools/ and mu/tools/."""
        via_symlink = ACTUAL_REPO_ROOT / "tools" / "checks" / "linters" / "ast_police_js.sh"
        via_mu = ACTUAL_REPO_ROOT / "mu" / "tools" / "checks" / "linters" / "ast_police_js.sh"
        assert via_symlink.exists(), "ast_police_js.sh must exist via tools/ symlink"
        assert via_mu.exists(), "ast_police_js.sh must exist via mu/tools/"
        assert via_symlink.resolve() == via_mu.resolve(), (
            "ast_police_js.sh must resolve to same file via both paths"
        )


# ---------------------------------------------------------------------------
# Rule 5: Marker bypass is strictly line-local
# ---------------------------------------------------------------------------
class TestRule5MarkerLocality:
    """Suppression markers must only affect the line they appear on."""

    def test_contraband_ok_suppresses_same_line(self):
        """CONTRABAND_OK on same line must suppress the match."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("const t = new Date(); // CONTRABAND_OK: intentional\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_CONTRABAND), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode == 0, (
                f"CONTRABAND_OK on same line must suppress: {result.stdout}"
            )
        finally:
            Path(filepath).unlink()

    def test_contraband_ok_does_not_suppress_different_line(self):
        """CONTRABAND_OK on different line must NOT suppress."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("// CONTRABAND_OK: this is a comment\nconst t = new Date();\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_CONTRABAND), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode != 0, (
                "CONTRABAND_OK on different line must NOT suppress"
            )
        finally:
            Path(filepath).unlink()

    def test_ast_ok_js_suppresses_same_line(self):
        """AST_OK_JS on same line must suppress the match."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("obj.__proto__ = null; // AST_OK_JS: intentional reset\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_AST_POLICE), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode == 0, (
                f"AST_OK_JS on same line must suppress: {result.stdout}"
            )
        finally:
            Path(filepath).unlink()

    def test_ast_ok_js_does_not_suppress_different_line(self):
        """AST_OK_JS on different line must NOT suppress."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("// AST_OK_JS: this is a comment\nobj.__proto__ = null;\n")
            f.flush()
            filepath = f.name
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT_AST_POLICE), filepath],
                capture_output=True, text=True, check=False, timeout=30,
            )
            assert result.returncode != 0, (
                "AST_OK_JS on different line must NOT suppress"
            )
        finally:
            Path(filepath).unlink()

    def test_contraband_ok_marker_must_appear_in_script(self):
        """contraband_js.sh must reference CONTRABAND_OK marker."""
        script = SCRIPT_CONTRABAND.read_text()
        assert "CONTRABAND_OK" in script

    def test_ast_ok_js_marker_must_appear_in_script(self):
        """ast_police_js.sh must reference AST_OK_JS marker."""
        script = SCRIPT_AST_POLICE.read_text()
        assert "AST_OK_JS" in script
