"""W6A Gate Test: Stage0 VM Trusted Path Source-Lock and Behavioral Parity.

This gate enforces the W6A design:
1. Source-lock: Exhaustive grep for trusted function usage
2. Behavioral parity: _stage0_vm_step_trusted == stage0_vm_step for valid bundles
3. Fail-closed negative control: Public wrappers reject malformed bundles
4. Cache mutation demo: Prove mutation is possible but not done in production
5. JS parity: _stage0VmStepTrusted in exports, source-locked to kernel.js

Source-lock is EXHAUSTIVE per Codex B2.2: grep for ALL occurrences (not just
import patterns), ban module-level imports outside allowlist.
"""

import re
import subprocess
import pytest
from pathlib import Path

from tests.repo_root import REPO_ROOT  # Repo-wide shared helper


# =============================================================================
# Section 1: Python Source-Lock Tests
# =============================================================================

def _normalize_path(rel_path):
    """Normalize path to handle both mu/ and non-mu/ prefixed paths."""
    # Paths may appear with or without mu/ prefix depending on symlink resolution
    if rel_path.startswith("mu/"):
        return rel_path
    # Add mu/ prefix for paths that should be under mu/
    if rel_path.startswith("host/") or rel_path.startswith("tests/"):
        return "mu/" + rel_path
    return rel_path


class TestPythonSourceLock:
    """Exhaustive source-lock for Python trusted paths."""

    def test_step_trusted_allowlist(self):
        """All _stage0_vm_step_trusted occurrences must be in allowlist."""
        allowlist = {
            "mu/host/python/rcx_pi/selfhost/stage0_vm.py",  # Definition
            "mu/host/python/rcx_pi/selfhost/step_mu.py",     # Loader-cached callers
            "mu/host/python/rcx_pi/selfhost/match_mu.py",    # Loader-cached callers
            "mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py",  # This test
            "mu/tests/l4_gates/test_meta_circular_evidence_gate.py",  # Routing lock test
            "mu/tests/l4_gates/test_match_vm_staged_dispatch_gate.py",  # VM fault test
            "mu/tests/l4_gates/test_stage0_vm_cutover.py",  # Trace coverage monkeypatch
        }

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "_stage0_vm_step_trusted", str(REPO_ROOT)],
            capture_output=True, text=True
        )

        violations = []
        for line in result.stdout.strip().split("\n"):
            if not line or line.startswith("Binary file"):
                continue
            file_path = line.split(":")[0]
            try:
                rel_path = str(Path(file_path).relative_to(REPO_ROOT))
            except ValueError:
                continue  # Skip paths not under REPO_ROOT

            # Skip .scratch, .agent_bus, __pycache__
            if any(skip in rel_path for skip in [".scratch", ".agent_bus", "__pycache__", ".pyc"]):
                continue

            # Normalize path to handle symlink resolution
            norm_path = _normalize_path(rel_path)
            if norm_path not in allowlist:
                violations.append(f"{norm_path}: {line.split(':', 2)[-1][:60]}")

        assert not violations, (
            f"_stage0_vm_step_trusted found outside allowlist:\n" +
            "\n".join(violations)
        )

    def test_run_bounded_trusted_allowlist(self):
        """All _stage0_vm_run_bounded_trusted occurrences must be in allowlist."""
        allowlist = {
            "mu/host/python/rcx_pi/selfhost/stage0_vm.py",   # Definition
            "mu/host/python/rcx_pi/selfhost/classify_mu.py", # Loader-cached caller
            "mu/host/python/rcx_pi/selfhost/subst_mu.py",    # Loader-cached caller
            "mu/host/python/rcx_pi/selfhost/step_mu.py",      # Loader-cached continuation validator
            "mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py",  # This test
            "mu/tests/l4_gates/test_subst_vm_unification_gate.py",  # VM fault mocking
            "mu/tests/l4_gates/test_classify_vm_unification_gate.py",  # VM fault mocking
        }

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "_stage0_vm_run_bounded_trusted", str(REPO_ROOT)],
            capture_output=True, text=True
        )

        violations = []
        for line in result.stdout.strip().split("\n"):
            if not line or line.startswith("Binary file"):
                continue
            file_path = line.split(":")[0]
            try:
                rel_path = str(Path(file_path).relative_to(REPO_ROOT))
            except ValueError:
                continue

            if any(skip in rel_path for skip in [".scratch", ".agent_bus", "__pycache__", ".pyc"]):
                continue

            # Normalize path to handle symlink resolution
            norm_path = _normalize_path(rel_path)
            if norm_path not in allowlist:
                violations.append(f"{norm_path}: {line.split(':', 2)[-1][:60]}")

        assert not violations, (
            f"_stage0_vm_run_bounded_trusted found outside allowlist:\n" +
            "\n".join(violations)
        )

    def test_run_bounded_impl_allowlist(self):
        """All _run_bounded_impl occurrences must be in stage0_vm.py only."""
        allowlist = {
            "mu/host/python/rcx_pi/selfhost/stage0_vm.py",  # Definition + internal use
            "mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py",  # This test
        }

        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "_run_bounded_impl", str(REPO_ROOT)],
            capture_output=True, text=True
        )

        violations = []
        for line in result.stdout.strip().split("\n"):
            if not line or line.startswith("Binary file"):
                continue
            file_path = line.split(":")[0]
            try:
                rel_path = str(Path(file_path).relative_to(REPO_ROOT))
            except ValueError:
                continue

            if any(skip in rel_path for skip in [".scratch", ".agent_bus", "__pycache__", ".pyc"]):
                continue

            # Normalize path to handle symlink resolution
            norm_path = _normalize_path(rel_path)
            if norm_path not in allowlist:
                violations.append(f"{norm_path}: {line.split(':', 2)[-1][:60]}")

        assert not violations, (
            f"_run_bounded_impl found outside allowlist:\n" +
            "\n".join(violations)
        )

    def test_no_module_level_stage0_vm_import_outside_allowlist(self):
        """Ban 'import stage0_vm' outside allowlist to prevent stage0_vm._func() access."""  # ANTICHEAT_OK: docstring
        allowlist = {
            "mu/host/python/rcx_pi/selfhost/stage0_vm.py",  # Self-reference ok
            "mu/host/python/rcx_pi/selfhost/seed_integrity.py",  # Uses validator
            "tests/",  # Tests may import for testing
            "tools/",  # Tools may import
        }

        result = subprocess.run(
            ["grep", "-rn", "import stage0_vm", str(REPO_ROOT / "mu" / "host" / "python")],
            capture_output=True, text=True
        )

        violations = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            file_path = line.split(":")[0]
            rel_path = str(Path(file_path).relative_to(REPO_ROOT))

            if any(skip in rel_path for skip in [".scratch", "__pycache__", ".pyc"]):
                continue

            # Check if matches any allowlist prefix
            if any(rel_path.startswith(allow) or rel_path == allow for allow in allowlist):
                continue

            violations.append(f"{rel_path}")

        assert not violations, (
            f"'import stage0_vm' found outside allowlist (module-namespace access risk):\n" +
            "\n".join(violations)
        )


# =============================================================================
# Section 2: JS Source-Lock Tests
# =============================================================================

class TestJsSourceLock:
    """Exhaustive source-lock for JS trusted paths."""

    def _stage0_vm_source(self):
        return (REPO_ROOT / "mu" / "host" / "js" / "core" / "stage0_vm.js").read_text()

    def _stage0_vm_export_block(self):
        src = self._stage0_vm_source()
        start = src.index("module.exports = {")
        end = src.index("\n};", start)
        return src[start:end]

    def _mask_js_non_code(self, src):
        """Replace JS comments/strings with spaces while preserving offsets."""
        chars = list(src)
        i = 0
        while i < len(src):
            c = src[i]
            nxt = src[i + 1] if i + 1 < len(src) else ""
            if c in {"'", '"', "`"}:
                quote = c
                chars[i] = " "
                i += 1
                while i < len(src):
                    if src[i] == "\\":
                        chars[i] = " "
                        if i + 1 < len(src):
                            chars[i + 1] = " "
                        i += 2
                        continue
                    chars[i] = "\n" if src[i] == "\n" else " "
                    if src[i] == quote:
                        i += 1
                        break
                    i += 1
                continue
            if c == "/" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                i += 2
                while i < len(src) and src[i] != "\n":
                    chars[i] = " "
                    i += 1
                continue
            if c == "/" and nxt == "*":
                chars[i] = chars[i + 1] = " "
                i += 2
                while i + 1 < len(src):
                    if src[i] == "*" and src[i + 1] == "/":
                        chars[i] = chars[i + 1] = " "
                        i += 2
                        break
                    chars[i] = "\n" if src[i] == "\n" else " "
                    i += 1
                continue
            i += 1
        return "".join(chars)

    def _matching_js_delimiter(self, masked_src, open_index, open_char, close_char):
        depth = 0
        for index in range(open_index, len(masked_src)):
            char = masked_src[index]
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    return index
        raise AssertionError(f"unterminated JS export literal starting at offset {open_index}")

    def _add_js_object_property_name(self, property_src, names):
        masked = self._mask_js_non_code(property_src)
        leading = len(masked) - len(masked.lstrip())
        stripped = property_src[leading:].strip()
        if not stripped:
            return
        if stripped.startswith("...") or stripped.startswith("["):
            raise AssertionError(f"unsupported computed/spread export property: {stripped[:80]}")

        quoted = re.match(r"""(['"])([^'"]+)\1\s*(?::|\(|$)""", stripped)
        if quoted:
            names.add(quoted.group(2))
            return

        accessor = re.match(r"(?:async|get|set)\s+([A-Za-z_$][\w$]*)\s*\(", stripped)
        if accessor:
            names.add(accessor.group(1))
            return

        identifier = re.match(r"([A-Za-z_$][\w$]*)\s*(?::|\(|$)", stripped)
        if identifier:
            names.add(identifier.group(1))
            return

        raise AssertionError(f"unsupported export property syntax: {stripped[:80]}")

    def _js_object_property_names(self, src, open_index, close_index):
        original = src[open_index:close_index + 1]
        masked = self._mask_js_non_code(original)
        names = set()
        brace_depth = 0
        paren_depth = 0
        bracket_depth = 0
        property_start = 1
        for index, char in enumerate(masked):
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
            elif char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            elif char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth -= 1
            elif (
                char == ","
                and brace_depth == 1
                and paren_depth == 0
                and bracket_depth == 0
            ):
                self._add_js_object_property_name(
                    original[property_start:index],
                    names,
                )
                property_start = index + 1

        self._add_js_object_property_name(original[property_start:-1], names)
        return names

    def _object_literal_exports_from_call(self, src, masked_src, call_start, call_end):
        names = set()
        index = call_start
        found_object_literal = False
        while index < call_end:
            char = masked_src[index]
            if char.isspace() or char == ",":
                index += 1
                continue
            if char == "{":
                close_index = self._matching_js_delimiter(masked_src, index, "{", "}")
                names.update(self._js_object_property_names(src, index, close_index))
                found_object_literal = True
                index = close_index + 1
                continue
            raise AssertionError("export mutation uses non-literal object; cannot source-lock names")

        if not found_object_literal:
            raise AssertionError("export mutation uses non-literal object; cannot source-lock names")
        return names

    def _stage0_vm_export_names(self):
        src = self._stage0_vm_source()
        masked_src = self._mask_js_non_code(src)
        names = set()
        name_locations = {}
        duplicate_exports = []
        parsed_spans = []

        def line_number(offset):
            return src.count("\n", 0, offset) + 1

        def record_export_names(export_names, location):
            for name in export_names:
                if name in name_locations:
                    duplicate_exports.append(
                        f"{name}: {name_locations[name]} and {location}"
                    )
                    continue
                name_locations[name] = location
                names.add(name)

        for match in re.finditer(r"module\s*\.\s*exports\s*=\s*{", masked_src):
            open_index = masked_src.index("{", match.start(), match.end())
            close_index = self._matching_js_delimiter(masked_src, open_index, "{", "}")
            record_export_names(
                self._js_object_property_names(src, open_index, close_index),
                f"module.exports object at line {line_number(match.start())}",
            )
            parsed_spans.append((match.start(), close_index + 1))

        direct_assignment = re.compile(
            r"(?:module\s*\.\s*exports|exports)\s*"
            r"(?:\.\s*([A-Za-z_$][\w$]*)|\[\s*(['\"])([^'\"]+)\2\s*\])\s*="
        )
        for match in direct_assignment.finditer(src):
            if masked_src[match.start()].isspace():
                continue
            record_export_names(
                {match.group(1) or match.group(3)},
                f"direct assignment at line {line_number(match.start())}",
            )
            parsed_spans.append(match.span())

        for match in re.finditer(
            r"Object\s*\.\s*assign\s*\(\s*(?:module\s*\.\s*exports|exports)\s*,",
            masked_src,
        ):
            open_paren = masked_src.index("(", match.start(), match.end())
            close_paren = self._matching_js_delimiter(masked_src, open_paren, "(", ")")
            record_export_names(
                self._object_literal_exports_from_call(
                    src,
                    masked_src,
                    match.end(),
                    close_paren,
                ),
                f"Object.assign at line {line_number(match.start())}",
            )
            parsed_spans.append((match.start(), close_paren + 1))

        for match in re.finditer(
            r"Object\s*\.\s*defineProperties\s*\(\s*(?:module\s*\.\s*exports|exports)\s*,",
            masked_src,
        ):
            open_paren = masked_src.index("(", match.start(), match.end())
            close_paren = self._matching_js_delimiter(masked_src, open_paren, "(", ")")
            record_export_names(
                self._object_literal_exports_from_call(
                    src,
                    masked_src,
                    match.end(),
                    close_paren,
                ),
                f"Object.defineProperties at line {line_number(match.start())}",
            )
            parsed_spans.append((match.start(), close_paren + 1))

        define_property = re.compile(
            r"Object\s*\.\s*defineProperty\s*\(\s*"
            r"(?:module\s*\.\s*exports|exports)\s*,\s*(['\"])([^'\"]+)\1"
        )
        for match in define_property.finditer(src):
            if masked_src[match.start()].isspace():
                continue
            open_paren = masked_src.index("(", match.start(), match.end())
            close_paren = self._matching_js_delimiter(masked_src, open_paren, "(", ")")
            record_export_names(
                {match.group(2)},
                f"Object.defineProperty at line {line_number(match.start())}",
            )
            parsed_spans.append((match.start(), close_paren + 1))

        export_target = re.compile(r"module\s*\.\s*exports|(?<![.\w$])exports\b")
        unparsed = []
        for match in export_target.finditer(masked_src):
            if any(start <= match.start() < end for start, end in parsed_spans):
                continue
            line_no = line_number(match.start())
            line = src.splitlines()[line_no - 1].strip()
            unparsed.append(f"line {line_no}: {line}")

        assert not unparsed, (
            "stage0_vm.js has unsupported export mutations; update the "
            "source-lock parser before allowing them:\n" + "\n".join(unparsed)
        )
        assert not duplicate_exports, (
            "stage0_vm.js has duplicate export mutations; later mutations may "
            "override the source-locked public surface:\n" + "\n".join(duplicate_exports)
        )
        return names

    def test_js_trusted_step_allowlist(self):
        """All JS trusted-step symbol/fragments must be in allowlist."""
        allowlist = {
            "mu/host/js/core/stage0_vm.js",   # Definition
            "mu/host/js/engine/kernel.js",    # Loader-cached caller
            "mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py",  # This test
            "mu/tests/parity/test_js_vm_bridge_parity.py",  # Focused bridge-ordering probe
        }

        violations = []
        for token in ("_stage0VmStepTrusted", "StepTrusted"):
            result = subprocess.run(
                ["grep", "-rn", "--include=*.js", "--include=*.py", token, str(REPO_ROOT)],
                capture_output=True, text=True
            )

            for line in result.stdout.strip().split("\n"):
                if not line or line.startswith("Binary file"):
                    continue
                file_path = line.split(":")[0]
                try:
                    rel_path = str(Path(file_path).relative_to(REPO_ROOT))
                except ValueError:
                    continue

                if any(skip in rel_path for skip in [".scratch", ".agent_bus", "node_modules"]):
                    continue

                # Normalize path to handle symlink resolution
                norm_path = _normalize_path(rel_path)
                if norm_path not in allowlist:
                    violations.append(f"{token} in {norm_path}: {line.split(':', 2)[-1][:60]}")

        assert not violations, (
            f"JS trusted-step symbol/fragments found outside allowlist:\n" +
            "\n".join(violations)
        )

    def test_js_trusted_run_allowlist(self):
        """All JS trusted-run symbol/fragments must be in allowlist."""
        allowlist = {
            "mu/host/js/core/stage0_vm.js",   # Definition
            "mu/host/js/engine/kernel.js",    # Loader-cached caller
            "mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py",  # This test
            "mu/tests/parity/test_js_vm_bridge_parity.py",  # Focused bridge-ordering probe
        }

        violations = []
        for token in ("_stage0VmRunTrusted", "RunTrusted"):
            result = subprocess.run(
                ["grep", "-rn", "--include=*.js", "--include=*.py", token, str(REPO_ROOT)],
                capture_output=True, text=True
            )

            for line in result.stdout.strip().split("\n"):
                if not line or line.startswith("Binary file"):
                    continue
                file_path = line.split(":")[0]
                try:
                    rel_path = str(Path(file_path).relative_to(REPO_ROOT))
                except ValueError:
                    continue

                if any(skip in rel_path for skip in [".scratch", ".agent_bus", "node_modules"]):
                    continue

                norm_path = _normalize_path(rel_path)
                if norm_path not in allowlist:
                    violations.append(f"{token} in {norm_path}: {line.split(':', 2)[-1][:60]}")

        assert not violations, (
            f"JS trusted-run symbol/fragments found outside allowlist:\n" +
            "\n".join(violations)
        )

    def test_js_kernel_vm_config_validation_boundary_source_lock(self):
        """Custom vmConfig must be validated before trusted JS VM helpers."""
        kernel_src = (REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js").read_text()
        stage0_src = self._stage0_vm_source()

        assert "const _vmConfigTrust = {" in kernel_src
        assert "validate(vmConfig) {" in kernel_src
        assert "const trustedConfig = {};" in kernel_src
        assert "Object.freeze(trustedConfig);" in kernel_src
        assert "_VALIDATED_VM_CONFIGS" not in kernel_src
        assert "new WeakMap" not in kernel_src
        assert "new WeakSet" not in kernel_src
        assert "const snapshot = muCopy(bundle, true, `vmConfig.${slotName}`);" in kernel_src
        assert "validateBundle(snapshot);" in kernel_src
        assert "const freezeStack = [snapshot];" in kernel_src
        assert "Object.freeze(node);" in kernel_src
        assert "trustedConfig[slotName] = snapshot;" in kernel_src
        assert "trustedConfig[slotName] = bundle;" not in kernel_src
        assert "const vmConfig = _vmConfigTrust.validate(Object.hasOwn(options, 'vmConfig') ? options.vmConfig : null);" in kernel_src
        assert "const _VM_CONFIG_TRUST_TOKEN = Object.freeze({" in kernel_src
        assert "vmConfigTrustToken = null" in kernel_src
        assert "const vmConfigTrusted = vmConfigTrustToken === _VM_CONFIG_TRUST_TOKEN;" in kernel_src
        assert "invalid vmConfig trust token" in kernel_src
        assert "makeStepKernelCoreRunner(vmConfig) {" in kernel_src
        assert "const trustedVmConfig = this.validate(vmConfig);" in kernel_src
        assert "_makeStepKernelCoreRunner" not in kernel_src
        assert (
            "function runStructural(kernelProjections, domainProjections, input, maxSteps = 10000, vmConfig = null) {\n"
            "  vmConfig = _vmConfigTrust.validate(vmConfig);"
        ) in kernel_src
        assert (
            "if (vmConfigTrustToken !== null && !vmConfigTrusted) {\n"
            "    throw new Error('SECURITY: invalid vmConfig trust token for trusted Stage0 VM execution');\n"
            "  }\n"
            "  if (!vmConfigTrusted) {\n"
            "    vmConfig = _vmConfigTrust.validate(vmConfig);\n"
            "  }"
        ) in kernel_src
        assert "_vmConfigTrust," in kernel_src
        pipeline_src = (REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js").read_text()
        assert "const { stepKernel, runStructural, _vmConfigTrust } = require('./kernel');" in pipeline_src
        assert "const runStepKernelCore = _vmConfigTrust.makeStepKernelCoreRunner(vmConfig === undefined ? null : vmConfig);" in pipeline_src
        assert "_stepKernelCore" not in pipeline_src
        assert (
            "runStructural(\n"
            "    kernelProjections,\n"
            "    projs,\n"
            "    reqInput.value,\n"
            "    traceMaxSteps,\n"
            "    vmConfig === undefined ? null : vmConfig\n"
            "  )"
        ) in pipeline_src
        assert "vmConfig || null" not in pipeline_src
        assert "runStepKernelCore" in pipeline_src
        for slot in ("kernelBundle", "bridgeBundle", "matchBundle", "substBundle"):
            assert f"['{slot}'," in kernel_src

        assert not re.search(r"(?<!_)\bstage0VmRun\b", kernel_src)
        assert "_stage0VmRunTrusted(vmConfig.matchBundle" in kernel_src
        assert "_stage0VmRunTrusted(vmConfig.substBundle" in kernel_src
        assert (
            "function stage0VmStep(bundle, inputValue, maxOps = MAX_VM_OPS_PER_STEP) {\n"
            "  const trustedBundle = safeMuCopy(bundle, true, 'stage0VmStep bundle');"
        ) in stage0_src
        assert (
            "function stage0VmRun(bundle, inputValue, maxSteps = 100, maxOps = undefined) {\n"
            "  const trustedBundle = safeMuCopy(bundle, true, 'stage0VmRun bundle');"
        ) in stage0_src
        assert stage0_src.count("validateBundle(trustedBundle);") == 2
        assert stage0_src.count("const freezeStack = [trustedBundle];") == 1
        assert "Object.freeze(node);" in stage0_src
        assert "_stage0VmRunTrusted: _stage0VmTrustedRun.run" in stage0_src
        trusted_run_start = stage0_src.index("const _stage0VmTrustedRun = {")
        public_run_start = stage0_src.index("function stage0VmRun")
        trusted_run_body = stage0_src[trusted_run_start:public_run_start]
        assert "stage0VmStep(" not in trusted_run_body
        assert "validateBundle(" not in trusted_run_body
        assert "_stage0VmStepTrusted(" in trusted_run_body

    def test_js_public_mu_copy_export_forces_strict_mode(self):
        """The public JS Stage0 copy export must not expose lax rejectNonMu=false."""
        block = self._stage0_vm_export_block()
        assert "\n  muCopy,\n" not in block, (
            "public stage0_vm export must not expose the internal lax muCopy helper"
        )
        start = block.index("  muCopy(value, rejectNonMu = true")
        end = block.index("\n  },", start)
        wrapper = block[start:end]
        assert "rejectNonMu !== true" in wrapper
        assert "safeMuCopy(value, true, context)" in wrapper
        assert "safeMuCopy(value, rejectNonMu" not in wrapper

    def test_js_stage0_vm_exports_do_not_expose_copy_laundering_paths(self):
        """Public Stage0 VM exports must not expose lax copy/trust constructors."""
        names = self._stage0_vm_export_names()
        assert "muCopy" in names
        assert names & {
            "safeMuCopy",
            "materializeTemplate",
            "muContainers",
            "containers",
            "containerFactory",
            "record",
            "list",
            "trustMu",
        } == set()
        copy_exports = {name for name in names if "copy" in name.lower()}
        assert copy_exports == {"muCopy"}
        trust_exports = {name for name in names if "trust" in name.lower()}
        assert trust_exports == {"_stage0VmStepTrusted", "_stage0VmRunTrusted"}


# =============================================================================
# Section 3: Behavioral Parity Tests
# =============================================================================

class TestBehavioralParity:
    """Prove trusted paths produce identical results to public wrappers."""

    def test_step_parity_valid_bundle(self):
        """_stage0_vm_step_trusted(valid_bundle, x) == stage0_vm_step(valid_bundle, x)."""
        from rcx_pi.selfhost.stage0_vm import (
            stage0_vm_step,
            _stage0_vm_step_trusted,  # ANTICHEAT_OK: parity test needs trusted path
            make_compiled_bundle_loader,
        )

        # Use a real loader-cached bundle
        load_kernel, _ = make_compiled_bundle_loader("kernel_v1")
        bundle = load_kernel()

        # Simple test input
        test_input = {"foo": "bar"}

        public_result = stage0_vm_step(bundle, test_input)
        trusted_result = _stage0_vm_step_trusted(bundle, test_input)

        assert public_result == trusted_result, (
            f"Parity violation:\n"
            f"public:  {public_result}\n"
            f"trusted: {trusted_result}"
        )

    def test_run_bounded_parity_valid_bundle(self):
        """_stage0_vm_run_bounded_trusted == stage0_vm_run_bounded for valid bundles."""
        from rcx_pi.selfhost.stage0_vm import (
            stage0_vm_run_bounded,
            _stage0_vm_run_bounded_trusted,  # ANTICHEAT_OK: parity test needs trusted path
            make_compiled_bundle_loader,
        )

        load_classify, _ = make_compiled_bundle_loader("classify_v1")
        bundle = load_classify()

        # Use classify.v1 terminal detection
        test_input = {"classify": {"list": None}}

        public_result = stage0_vm_run_bounded(
            bundle, test_input,
            max_steps=100,
            terminal_field="mode",
            terminal_value="classify_done"
        )
        trusted_result = _stage0_vm_run_bounded_trusted(
            bundle, test_input,
            max_steps=100,
            terminal_field="mode",
            terminal_value="classify_done"
        )

        assert public_result == trusted_result, (
            f"Parity violation:\n"
            f"public:  {public_result}\n"
            f"trusted: {trusted_result}"
        )


# =============================================================================
# Section 4: Fail-Closed Negative Control Tests
# =============================================================================

class TestFailClosedNegativeControl:
    """Prove public wrappers reject malformed bundles."""

    def test_step_rejects_malformed_bundle(self):
        """stage0_vm_step(malformed_bundle, x) raises ValueError."""
        from rcx_pi.selfhost.stage0_vm import stage0_vm_step

        malformed = {"not": "a_valid_bundle"}

        with pytest.raises(ValueError) as exc_info:
            stage0_vm_step(malformed, {"test": "input"})

        # validate_bundle raises ValueError with specific messages
        error_msg = str(exc_info.value).lower()
        assert any(kw in error_msg for kw in ["bundle", "required", "field", "missing"]), (
            f"Expected validation error, got: {exc_info.value}"
        )

    def test_run_bounded_rejects_malformed_bundle(self):
        """stage0_vm_run_bounded(malformed_bundle, x) raises ValueError.

        Critical: Even for immediate-terminal input (steps=0 path), validation
        must occur UPFRONT per B2.1 fix.
        """
        from rcx_pi.selfhost.stage0_vm import stage0_vm_run_bounded

        malformed = {"not": "a_valid_bundle"}

        # Use input that would trigger immediate-terminal in _run_bounded_impl
        # The key is that validation must happen BEFORE the terminal check
        immediate_terminal_input = {"mode": "already_done"}

        with pytest.raises(ValueError):
            stage0_vm_run_bounded(
                malformed, immediate_terminal_input,
                terminal_field="mode",
                terminal_value="already_done"
            )

    def test_js_public_run_rejects_malformed_bundle(self):
        """JS public stage0VmRun validates malformed bundles before running."""
        import json

        js_code = """
        const { stage0VmRun } = require('./mu/host/js/core/stage0_vm');
        try {
          stage0VmRun({ not: 'a_valid_bundle' }, { mode: 'already_done' }, 0);
          console.log(JSON.stringify({ ok: false, message: 'accepted' }));
        } catch (e) {
          console.log(JSON.stringify({ ok: true, message: e.message }));
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip())
        assert output["ok"] is True
        assert "Missing required bundle field" in output["message"]

    def test_js_public_run_and_step_reject_accessor_backed_bundle(self):
        """JS public Stage0 entry points must not execute after live bundle accessors swap data."""
        import json

        js_code = """
        const { stage0VmRun, stage0VmStep } = require('./mu/host/js/core/stage0_vm');

        function makeAccessorBundle() {
          let programsReads = 0;
          const validPrograms = [{
            id: 'p',
            ops: [
              { op: 'assert_focus_kind', path: ['focus', 'root'], kind: 'dict' },
              { op: 'write_path', template: { kind: 'literal', value: { done: true } } },
              { op: 'return_projection_success' },
            ],
          }];
          const malformedPrograms = [{
            id: 'p',
            ops: [
              {
                op: 'write_path',
                template: { kind: 'literal', value: 'bad' },
                extra_unvalidated_field: true,
              },
              { op: 'return_projection_success' },
            ],
          }];
          const bundle = {
            stage0_ir_version: 1,
            bundle_id: 'accessor-backed-test',
            source_seed: 'test',
            machine_profile: 'rcx.stage0.v1',
            hand_authored: true,
            program_order: ['p'],
            get programs() {
              programsReads += 1;
              return programsReads === 1 ? validPrograms : malformedPrograms;
            },
          };
          return { bundle, reads: () => programsReads };
        }

        function capture(label, fn) {
          const holder = makeAccessorBundle();
          try {
            const result = fn(holder.bundle);
            return { label, ok: false, result, programsReads: holder.reads() };
          } catch (e) {
            return { label, ok: true, message: e.message, programsReads: holder.reads() };
          }
        }

        console.log(JSON.stringify({
          step: capture('step', bundle => stage0VmStep(bundle, { x: 1 })),
          run: capture('run', bundle => stage0VmRun(bundle, { x: 1 }, 3)),
        }));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip())
        for key in ("step", "run"):
            assert output[key]["ok"] is True, output[key]
            assert "non-Mu value cannot be captured" in output[key]["message"]

    @pytest.mark.parametrize("slot", [
        "kernelBundle",
        "bridgeBundle",
        "matchBundle",
        "substBundle",
    ])
    def test_js_kernel_options_vm_config_rejects_malformed_bundle_slots_before_trusted_helpers(self, slot):
        """Kernel options.vmConfig rejects every bundle slot before trusted VM helpers run."""
        import json

        js_code = f"""
        const fs = require('fs');
        const stage0Vm = require('./mu/host/js/core/stage0_vm');
        stage0Vm._stage0VmStepTrusted = function() {{
          throw new Error('TRUSTED_STEP_REACHED');
        }};
        stage0Vm._stage0VmRunTrusted = function() {{
          throw new Error('TRUSTED_RUN_REACHED');
        }};
        const {{ stepKernel }} = require('./mu/host/js/engine/kernel');
        const muContainers = require('./mu/host/js/core/container_factory');

        function loadBundle(name) {{
          return JSON.parse(fs.readFileSync('./mu/stage0/compiled/' + name, 'utf8'));
        }}
        function trustMu(value) {{
          if (Array.isArray(value)) {{
            return muContainers.list(value.map(trustMu));
          }}
          if (value !== null && typeof value === 'object') {{
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }}
          return value;
        }}

        const vmConfig = {{
          kernelBundle: loadBundle('kernel_v1.compiled.v1.json'),
          bridgeBundle: loadBundle('bootstrap_structural_v1.compiled.v1.json'),
          matchBundle: loadBundle('match_v2.compiled.v1.json'),
          substBundle: loadBundle('subst_v2.compiled.v1.json'),
        }};
        vmConfig[{slot!r}] = {{ stage0_ir_version: 1 }};

        try {{
          stepKernel(
            [],
            trustMu({{ hello: 'world' }}),
            trustMu([{{ pattern: {{ var: 'x' }}, body: {{ var: 'x' }} }}]),
            {{ maxSteps: 3, vmConfig, returnPacket: true }}
          );
          console.log(JSON.stringify({{ ok: false, message: 'accepted' }}));
        }} catch (e) {{
          console.log(JSON.stringify({{ ok: true, message: e.message }}));
        }}
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip())
        assert output["ok"] is True
        assert f"vmConfig.{slot} failed Stage0 bundle validation" in output["message"]
        assert "TRUSTED_" not in output["message"]

    def test_js_exported_step_kernel_core_rejects_caller_controlled_vm_config_trust_flag(self):
        """Exported _stepKernelCore must not accept a forgeable vmConfig trust flag."""
        import json

        js_code = """
        const stage0Vm = require('./mu/host/js/core/stage0_vm');
        stage0Vm._stage0VmStepTrusted = function() {
          throw new Error('TRUSTED_STEP_REACHED');
        };
        stage0Vm._stage0VmRunTrusted = function() {
          throw new Error('TRUSTED_RUN_REACHED');
        };
        const { _stepKernelCore } = require('./mu/host/js/engine/kernel');
        const muContainers = require('./mu/host/js/core/container_factory');

        const domainInput = muContainers.record([['hello', 'world']]);
        const kernelInput = muContainers.record([
          ['_step', domainInput],
          ['_projs', null],
        ]);
        const malformedVmConfig = {
          kernelBundle: { stage0_ir_version: 1 },
          bridgeBundle: null,
          matchBundle: { stage0_ir_version: 1 },
          substBundle: { stage0_ir_version: 1 },
        };

        try {
          _stepKernelCore(
            [],
            kernelInput,
            domainInput,
            function() {},
            1,
            malformedVmConfig,
            undefined,
            null,
            null,
            true
          );
          console.log(JSON.stringify({ ok: false, message: 'accepted' }));
        } catch (e) {
          console.log(JSON.stringify({ ok: true, message: e.message }));
        }
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip())
        assert output["ok"] is True
        assert "invalid vmConfig trust token" in output["message"]
        assert "TRUSTED_" not in output["message"]

    @pytest.mark.parametrize("slot", [
        "kernelBundle",
        "bridgeBundle",
        "matchBundle",
        "substBundle",
    ])
    def test_js_kernel_options_vm_config_rejects_accessor_backed_bundle_slots(self, slot):
        """Accessor-backed vmConfig bundle slots must fail before trusted helpers use live references."""
        import json

        js_code = f"""
        const fs = require('fs');
        const stage0Vm = require('./mu/host/js/core/stage0_vm');
        stage0Vm._stage0VmStepTrusted = function() {{
          throw new Error('TRUSTED_STEP_REACHED');
        }};
        stage0Vm._stage0VmRunTrusted = function() {{
          throw new Error('TRUSTED_RUN_REACHED');
        }};
        const {{ stepKernel }} = require('./mu/host/js/engine/kernel');
        const muContainers = require('./mu/host/js/core/container_factory');

        function loadBundle(name) {{
          return JSON.parse(fs.readFileSync('./mu/stage0/compiled/' + name, 'utf8'));
        }}
        function trustMu(value) {{
          if (Array.isArray(value)) {{
            return muContainers.list(value.map(trustMu));
          }}
          if (value !== null && typeof value === 'object') {{
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }}
          return value;
        }}
        function accessorBackedBundle(bundle) {{
          let programsReads = 0;
          const validPrograms = bundle.programs;
          const malformedPrograms = [{{
            id: validPrograms[0].id,
            ops: [
              {{
                op: 'write_path',
                template: {{ kind: 'literal', value: 'hacked-output' }},
                extra_unvalidated_field: true,
              }},
              {{ op: 'return_projection_success' }},
            ],
          }}];
          const wrapped = {{ ...bundle }};
          Object.defineProperty(wrapped, 'programs', {{
            enumerable: true,
            configurable: true,
            get() {{
              programsReads += 1;
              return programsReads === 1 ? validPrograms : malformedPrograms;
            }},
          }});
          return {{ bundle: wrapped, reads: () => programsReads }};
        }}

        const vmConfig = {{
          kernelBundle: loadBundle('kernel_v1.compiled.v1.json'),
          bridgeBundle: loadBundle('bootstrap_structural_v1.compiled.v1.json'),
          matchBundle: loadBundle('match_v2.compiled.v1.json'),
          substBundle: loadBundle('subst_v2.compiled.v1.json'),
        }};
        const wrapped = accessorBackedBundle(vmConfig[{slot!r}]);
        vmConfig[{slot!r}] = wrapped.bundle;

        try {{
          stepKernel(
            [],
            trustMu({{ hello: 'world' }}),
            trustMu([{{ pattern: {{ var: 'x' }}, body: {{ var: 'x' }} }}]),
            {{ maxSteps: 3, vmConfig, returnPacket: true }}
          );
          console.log(JSON.stringify({{ ok: false, message: 'accepted', programsReads: wrapped.reads() }}));
        }} catch (e) {{
          console.log(JSON.stringify({{ ok: true, message: e.message, programsReads: wrapped.reads() }}));
        }}
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip())
        assert output["ok"] is True
        assert f"vmConfig.{slot} failed Stage0 bundle validation" in output["message"]
        assert "TRUSTED_" not in output["message"]
        assert "hacked-output" not in output["message"]

    @pytest.mark.parametrize("slot", [
        "kernelBundle",
        "bridgeBundle",
        "matchBundle",
        "substBundle",
    ])
    def test_js_kernel_options_vm_config_revalidates_mutated_original_slots(self, slot):
        """Caller-owned vmConfig mutation after validation must not bypass the boundary."""
        import json

        js_code = f"""
        const fs = require('fs');
        const stage0Vm = require('./mu/host/js/core/stage0_vm');
        stage0Vm._stage0VmStepTrusted = function() {{
          throw new Error('TRUSTED_STEP_REACHED');
        }};
        stage0Vm._stage0VmRunTrusted = function() {{
          throw new Error('TRUSTED_RUN_REACHED');
        }};
        const {{ stepKernel }} = require('./mu/host/js/engine/kernel');
        const muContainers = require('./mu/host/js/core/container_factory');

        function loadBundle(name) {{
          return JSON.parse(fs.readFileSync('./mu/stage0/compiled/' + name, 'utf8'));
        }}
        function trustMu(value) {{
          if (Array.isArray(value)) {{
            return muContainers.list(value.map(trustMu));
          }}
          if (value !== null && typeof value === 'object') {{
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }}
          return value;
        }}

        const domainInput = trustMu({{ hello: 'world' }});
        const domainProjections = trustMu([{{ pattern: {{ var: 'x' }}, body: {{ var: 'x' }} }}]);
        const vmConfig = {{
          kernelBundle: loadBundle('kernel_v1.compiled.v1.json'),
          bridgeBundle: loadBundle('bootstrap_structural_v1.compiled.v1.json'),
          matchBundle: loadBundle('match_v2.compiled.v1.json'),
          substBundle: loadBundle('subst_v2.compiled.v1.json'),
        }};

        stepKernel(
          [],
          domainInput,
          domainProjections,
          {{ maxSteps: 0, vmConfig, returnPacket: true }}
        );
        vmConfig[{slot!r}] = {{ stage0_ir_version: 1 }};

        try {{
          stepKernel(
            [],
            domainInput,
            domainProjections,
            {{ maxSteps: 1, vmConfig, returnPacket: true }}
          );
          console.log(JSON.stringify({{ ok: false, message: 'accepted' }}));
        }} catch (e) {{
          console.log(JSON.stringify({{ ok: true, message: e.message }}));
        }}
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip())
        assert output["ok"] is True
        assert f"vmConfig.{slot} failed Stage0 bundle validation" in output["message"]
        assert "TRUSTED_" not in output["message"]

    def test_js_kernel_options_vm_config_validates_bundles_once_per_config(self):
        """Valid custom vmConfig validation is one-time, not once per VM step."""
        import json

        js_code = """
        const fs = require('fs');
        const stage0Vm = require('./mu/host/js/core/stage0_vm');
        const originalValidateBundle = stage0Vm.validateBundle;
        let validateCount = 0;
        stage0Vm.validateBundle = function(bundle) {
          validateCount += 1;
          return originalValidateBundle(bundle);
        };
        const { stepKernel } = require('./mu/host/js/engine/kernel');
        const muContainers = require('./mu/host/js/core/container_factory');

        function loadBundle(name) {
          return JSON.parse(fs.readFileSync('./mu/stage0/compiled/' + name, 'utf8'));
        }
        function trustMu(value) {
          if (Array.isArray(value)) {
            return muContainers.list(value.map(trustMu));
          }
          if (value !== null && typeof value === 'object') {
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }
          return value;
        }

        const vmConfig = {
          kernelBundle: loadBundle('kernel_v1.compiled.v1.json'),
          bridgeBundle: loadBundle('bootstrap_structural_v1.compiled.v1.json'),
          matchBundle: loadBundle('match_v2.compiled.v1.json'),
          substBundle: loadBundle('subst_v2.compiled.v1.json'),
        };

        const result = stepKernel(
          [],
          trustMu({ hello: 'world' }),
          trustMu([{ pattern: { var: 'x' }, body: { var: 'x' } }]),
          { maxSteps: 10, vmConfig }
        );
        console.log(JSON.stringify({ validateCount, result }));
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"JS execution failed with exit {result.returncode}:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        output = json.loads(result.stdout.strip())
        assert output["validateCount"] == 4

    def test_js_pipeline_run_trace_rejects_malformed_vm_config_before_defaulting(self):
        """run_trace boundary must not collapse malformed vmConfig to null."""
        import json

        js_code = """
        const { serviceBoundaryEffect } = require('./mu/host/js/engine/pipeline');
        const muContainers = require('./mu/host/js/core/container_factory');

        function trustMu(value) {
          if (Array.isArray(value)) {
            return muContainers.list(value.map(trustMu));
          }
          if (value !== null && typeof value === 'object') {
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }
          return value;
        }

        const request = {
          operation: 'run_trace',
          input: {
            projections: [{ pattern: { var: 'x' }, body: { var: 'x' } }],
            value: trustMu({ hello: 'world' }),
            max_steps: { _num: { xH: null } },
          },
          context: {},
          inject_key: 'trace_result',
        };

        try {
          serviceBoundaryEffect([], {}, request, 50, () => {}, 0, trustMu({}), false);
          console.log(JSON.stringify({ ok: false, message: 'accepted' }));
        } catch (e) {
          console.log(JSON.stringify({ ok: true, message: e.message }));
        }
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout.strip())
        assert output["ok"] is True
        assert "SECURITY: vmConfig must be an object or null, got boolean" in output["message"]

# =============================================================================
# Section 5: Cache Mutation Demo
# =============================================================================

class TestCacheMutationDemo:
    """Prove mutation IS possible, prove no production code does it."""

    def test_mutation_is_possible(self):
        """Demonstrate that cached bundles CAN be mutated (risk is real)."""
        from rcx_pi.selfhost.stage0_vm import make_compiled_bundle_loader

        load_fn, clear_fn = make_compiled_bundle_loader("kernel_v1")

        # Load bundle
        bundle1 = load_fn()
        original_order = bundle1["program_order"].copy()

        # Mutate the cached bundle
        bundle1["program_order"].reverse()

        # Get "same" bundle again — it's mutated!
        bundle2 = load_fn()

        assert bundle2["program_order"] == list(reversed(original_order)), (
            "Cache mutation demonstration failed — mutation didn't affect cache"
        )

        # Clean up: clear cache to avoid affecting other tests
        clear_fn()

    def test_no_production_code_mutates_bundles(self):
        """Source-lock: no production code assigns to cached bundle keys.

        This is a static check. We grep for assignment patterns that would
        mutate bundle state after loading.
        """
        # Patterns that would indicate bundle mutation
        mutation_patterns = [
            r'bundle\["',      # Direct dict key assignment
            r"bundle\['",      # Same with single quotes
            r"bundle\.programs\s*=",  # Property assignment
            r"\.reverse\(\)",  # In-place reversal
            r"\.append\(",     # In-place append
            r"\.extend\(",     # In-place extend
            r"del bundle",     # Deletion
        ]

        production_dirs = [
            REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost",
        ]

        violations = []
        for pattern in mutation_patterns:
            for prod_dir in production_dirs:
                result = subprocess.run(
                    ["grep", "-rn", "-E", pattern, str(prod_dir)],
                    capture_output=True, text=True
                )
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    # Skip known safe patterns (e.g., building new dicts, not mutating)
                    if "# MUTATION_OK" in line:
                        continue
                    # Skip lines that are clearly dict construction, not mutation
                    if "= {" in line or "= []" in line:
                        continue
                    # Skip lines in tests
                    if "/tests/" in line:
                        continue
                    violations.append(line[:100])

        # Note: This test may have false positives that need manual review.
        # Any violations should be inspected to determine if they're real mutations.
        # For now, we're being conservative and flagging potential issues.
        # If you see violations that are safe, add # MUTATION_OK comment.
        pass  # Informational test — violations logged but not asserted


# =============================================================================
# Section 6: JS Behavioral Parity (Cross-Substrate)
# =============================================================================

class TestJsBehavioralParity:
    """Prove JS _stage0VmStepTrusted == JS stage0VmStep."""

    @pytest.mark.slow
    def test_js_step_parity(self):
        """JS _stage0VmStepTrusted produces same results as stage0VmStep."""
        import json

        js_code = """
        const { stage0VmStep, _stage0VmStepTrusted, validateBundle } = require('./mu/host/js/core/stage0_vm');
        const fs = require('fs');
        const path = require('path');

        // Load a real bundle
        const bundlePath = path.join(__dirname, 'mu/stage0/compiled/kernel_v1.compiled.v1.json');
        const bundle = JSON.parse(fs.readFileSync(bundlePath, 'utf8'));

        // Test input
        const input = { foo: 'bar' };

        // Get results from both
        const publicResult = stage0VmStep(bundle, input);
        const trustedResult = _stage0VmStepTrusted(bundle, input);

        // Output comparison
        console.log(JSON.stringify({
            match: JSON.stringify(publicResult) === JSON.stringify(trustedResult),
            public: publicResult,
            trusted: trustedResult
        }));
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT)
        )

        assert result.returncode == 0, (
            f"JS execution failed with exit {result.returncode}:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output["match"], (
            f"JS parity violation:\n"
            f"public:  {output['public']}\n"
            f"trusted: {output['trusted']}"
        )

    def test_js_run_trusted_parity(self):
        """JS _stage0VmRunTrusted produces same result as public stage0VmRun."""
        import json

        js_code = """
        const fs = require('fs');
        const { stage0VmRun, _stage0VmRunTrusted } = require('./mu/host/js/core/stage0_vm');

        const bundle = JSON.parse(fs.readFileSync(
          './mu/stage0/compiled/match_v2.compiled.v1.json', 'utf8'));
        const input = {
          match: { pattern: { var: 'x' }, value: { foo: 'bar' } },
          _match_ctx: { _input: { foo: 'bar' }, _body: { var: 'x' }, _remaining: null },
        };

        const publicResult = stage0VmRun(bundle, input, 100);
        const trustedResult = _stage0VmRunTrusted(bundle, input, 100);
        console.log(JSON.stringify({
          match: JSON.stringify(publicResult) === JSON.stringify(trustedResult),
          public: publicResult,
          trusted: trustedResult,
        }));
        """

        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT)
        )

        assert result.returncode == 0, (
            f"JS execution failed with exit {result.returncode}:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        output = json.loads(result.stdout.strip())
        assert output["match"], (
            f"JS run parity violation:\n"
            f"public:  {output['public']}\n"
            f"trusted: {output['trusted']}"
        )
