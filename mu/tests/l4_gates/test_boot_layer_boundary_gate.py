"""L4 gate: Boot layer boundary enforcement (G3 — Host Loop Boundaries).

Proves the 3-layer bootstrap (Boot0/Boot1/Boot2) has correct import
direction and no upward dependencies.

Layer model:
  Boot0 (eval_seed.py)       — raw stepping
  Boot1 (step_mu.py)         — kernel orchestration
  Boot2 (engine_pipeline.py) — engine pipeline + routing

Dependency direction: Boot2 → Boot1 → Boot0 (downward only).
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

PY_SELFHOST = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"
JS_ENGINE_DIR = REPO_ROOT / "mu" / "host" / "js" / "engine"


def _get_relative_import_modules(filepath: Path) -> list[tuple[int, str]]:
    """Parse AST and return (lineno, module_name) for relative imports."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, str(filepath))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0 and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _get_compat_shim_line(filepath: Path) -> int | None:
    """Find the KNOWN_COMPAT_SHIM marker line, if any."""
    lines = filepath.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if "KNOWN_COMPAT_SHIM" in line:
            return i
    return None


class TestBoot0Isolation:
    """Boot0 (eval_seed.py) must not import from Boot1 or Boot2."""

    def test_boot0_has_no_boot1_imports(self):
        """eval_seed.py must not import from step_mu."""
        path = PY_SELFHOST / "eval_seed.py"
        for lineno, module in _get_relative_import_modules(path):
            base = module.split(".")[0]
            assert base != "step_mu", (
                f"Boot0 → Boot1 violation at eval_seed.py:{lineno}: imports {module}"
            )

    def test_boot0_has_no_boot2_imports(self):
        """eval_seed.py must not import from engine_pipeline."""
        path = PY_SELFHOST / "eval_seed.py"
        for lineno, module in _get_relative_import_modules(path):
            base = module.split(".")[0]
            assert base != "engine_pipeline", (
                f"Boot0 → Boot2 violation at eval_seed.py:{lineno}: imports {module}"
            )

    def test_boot0_has_no_seed_imports(self):
        """eval_seed.py must not import seed loading machinery."""
        path = PY_SELFHOST / "eval_seed.py"
        for lineno, module in _get_relative_import_modules(path):
            base = module.split(".")[0]
            assert base != "seed_integrity", (
                f"Boot0 must not load seeds: eval_seed.py:{lineno} imports {module}"
            )


class TestBoot1Isolation:
    """Boot1 (step_mu.py) must not import from Boot2 except via compat shim."""

    def test_boot1_has_no_boot2_imports_except_shim(self):
        """step_mu.py only imports from engine_pipeline.py in the re-export shim block."""
        path = PY_SELFHOST / "step_mu.py"
        shim_line = _get_compat_shim_line(path)
        assert shim_line is not None, (
            "step_mu.py must have a KNOWN_COMPAT_SHIM marker for re-exports"
        )

        for lineno, module in _get_relative_import_modules(path):
            base = module.split(".")[0]
            if base == "engine_pipeline":
                assert lineno >= shim_line, (
                    f"Boot1 → Boot2 violation at step_mu.py:{lineno}: imports {module} "
                    f"BEFORE compat shim (shim starts at line {shim_line})"
                )


class TestBoot2Dependencies:
    """Boot2 (engine_pipeline.py) has correct downward-only dependencies."""

    def test_boot2_depends_only_on_boot0_boot1_and_shared(self):
        """engine_pipeline.py only imports from allowed modules."""
        allowed_bases = {
            "eval_seed", "step_mu",  # Boot0, Boot1
            "mu_type", "kernel", "seed_integrity", "projection_loader",  # Shared
            "match_mu", "subst_mu", "recurrence_mu", "host_types",  # Shared
        }
        path = PY_SELFHOST / "engine_pipeline.py"
        for lineno, module in _get_relative_import_modules(path):
            base = module.split(".")[0]
            assert base in allowed_bases, (
                f"Boot2 imports unknown module at engine_pipeline.py:{lineno}: "
                f"{module} (allowed: {sorted(allowed_bases)})"
            )

    def test_engine_pipeline_exists(self):
        """engine_pipeline.py must exist as a real file (not just a re-export)."""
        path = PY_SELFHOST / "engine_pipeline.py"
        assert path.exists(), "engine_pipeline.py must exist"
        source = path.read_text()
        assert "def run_engine_pipeline(" in source, (
            "engine_pipeline.py must define run_engine_pipeline"
        )


class TestTerminalClassificationStaysInBoot1:
    """Terminal classification is Boot1 — must stay in step_mu.py."""

    def test_classify_terminal_kind_in_step_mu(self):
        """classify_terminal_kind must be defined in step_mu.py (Boot1)."""
        path = PY_SELFHOST / "step_mu.py"
        source = path.read_text()
        assert "def classify_terminal_kind(" in source, (
            "classify_terminal_kind must be defined in step_mu.py (Boot1)"
        )

    def test_classify_terminal_kind_not_in_engine_pipeline(self):
        """classify_terminal_kind must NOT be defined in engine_pipeline.py (Boot2)."""
        path = PY_SELFHOST / "engine_pipeline.py"
        source = path.read_text()
        assert "def classify_terminal_kind(" not in source, (
            "classify_terminal_kind must stay in step_mu.py (Boot1), not engine_pipeline.py"
        )


class TestReexportCoverage:
    """step_mu.py re-exports must cover all moved public functions."""

    def test_reexports_cover_all_moved_functions(self):
        """step_mu.py re-exports every public function defined in engine_pipeline.py."""
        # Get module-level public names from engine_pipeline.py (top-level only)
        ep_path = PY_SELFHOST / "engine_pipeline.py"
        ep_source = ep_path.read_text()
        ep_tree = ast.parse(ep_source, str(ep_path))
        ep_public_names = set()
        for node in ep_tree.body:  # Top-level statements only
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    ep_public_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        ep_public_names.add(target.id)

        # Get names imported in step_mu.py from engine_pipeline (shim block)
        sm_path = PY_SELFHOST / "step_mu.py"
        sm_source = sm_path.read_text()
        sm_tree = ast.parse(sm_source, str(sm_path))
        reexported_names = set()
        for node in ast.walk(sm_tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                if node.module and node.module.split(".")[0] == "engine_pipeline":
                    for alias in node.names:
                        reexported_names.add(alias.name)

        missing = ep_public_names - reexported_names
        assert not missing, (
            f"step_mu.py compat shim missing re-exports for: {sorted(missing)}"
        )


class TestNoCyclesWithoutShim:
    """No import cycles when compat shim is excluded."""

    def test_no_semantic_import_cycles(self):
        """Boot layer imports (excluding compat shim) form a DAG."""
        files = {
            "eval_seed.py": PY_SELFHOST / "eval_seed.py",
            "step_mu.py": PY_SELFHOST / "step_mu.py",
            "engine_pipeline.py": PY_SELFHOST / "engine_pipeline.py",
        }
        base_to_file = {f.removesuffix(".py"): f for f in files}

        # Build graph excluding shim
        graph: dict[str, set[str]] = {}
        for fname, fpath in files.items():
            shim_line = _get_compat_shim_line(fpath) if fname == "step_mu.py" else None
            deps: set[str] = set()
            for lineno, module in _get_relative_import_modules(fpath):
                base = module.split(".")[0]
                if base in base_to_file:
                    if shim_line is not None and lineno >= shim_line:
                        continue
                    deps.add(base_to_file[base])
            graph[fname] = deps

        # Topological sort — if it fails, there's a cycle
        remaining = dict(graph)
        order = []
        while remaining:
            # Find a node with no remaining dependencies
            no_deps = [n for n, deps in remaining.items()
                       if not (deps & set(remaining))]
            assert no_deps, (
                f"Import cycle among boot layers: {sorted(remaining.keys())}"
            )
            for n in no_deps:
                order.append(n)
                del remaining[n]


class TestEnforcerScript:
    """The boot layer boundary enforcer script passes."""

    def test_enforcer_passes(self):
        """tools/checks/check_boot_layer_boundaries.py exits 0."""
        script = REPO_ROOT / "tools" / "checks" / "check_boot_layer_boundaries.py"
        assert script.exists(), "Boot layer boundary enforcer must exist"
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
        )
        assert result.returncode == 0, (
            f"Boot layer enforcer failed:\n{result.stdout}\n{result.stderr}"
        )
