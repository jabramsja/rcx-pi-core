#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


TMUX_SESSION = "rcx-pipeline"
WEB_PORT = 8099

STALE_MODELS_CACHE_CANARIES = (
    "team morale and being a supportive teammate as much as code quality",
    "warm, encouraging, and conversational",
    "collaboration is a kind of quiet joy",
    "Great work and smart decisions are acknowledged",
    "interesting or promising about their approach or problem framing",
)

PROMPT_HOOK_DISABLED_CANARY = (
    "Disabled because UserPromptSubmit output cannot currently be hidden in Codex."
)

SESSION_START_REQUIRED_CANARIES = (
    "codex-rcx-preflight",
    "codex-binary-guard",
    "rcx_codex_persona_hardening.md",
    "codex_binary_patch_surface.md",
)
ALLOWED_SESSION_START_PRE_EMIT_ENV_VARS = frozenset({"CODEX_RCX_PREFLIGHT_DISABLE"})

PROMPT_HOOK_REQUIRED_CANARIES = (
    "FOUNDER_SESSION_BOOTSTRAP.md",
    "repo-tracked docs",
    "pipeline path",
)

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
PYTHON_INTERPRETER_RE = re.compile(r"^python(?:\d+(?:\.\d+)*)?$")

SHELL_ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {"check-ignore", "diff", "log", "ls-files", "rev-parse", "show", "status"}
)
BROAD_INTERPRETER_ALLOW_COMMANDS = frozenset(
    {"node", "perl", "python", "python3", "ruby"}
)
INTERPRETER_SAFE_SINGLE_ARG_FLAGS = frozenset(
    {"-h", "--help", "-v", "-V", "-VV", "--version"}
)
INTERPRETER_VALUE_FLAGS = {
    "node": {"-e", "--eval", "-p", "--print"},
    "perl": {"-e"},
    "python": {"-c", "-m"},
    "python3": {"-c", "-m"},
    "ruby": {"-e"},
}
SAFE_REPO_INTERPRETER_SCRIPTS = frozenset(
    {
        "mu/host/js/eval_step.js",
        "mu/tools/executors/executor_dispatch.py",
    }
)
ENV_FLAGS_WITH_VALUES = frozenset({"-C", "-S", "-u", "--chdir", "--split-string", "--unset"})
ENV_SPLIT_STRING_FLAGS = frozenset({"-S", "--split-string"})
BRANCH_READ_ONLY_FLAGS = frozenset(
    {
        "--all",
        "-a",
        "--column",
        "--contains",
        "--format",
        "--list",
        "-l",
        "--merged",
        "--no-merged",
        "--points-at",
        "--remotes",
        "-r",
        "--show-current",
        "--sort",
        "-v",
        "-vv",
    }
)
BRANCH_MUTATING_FLAGS = frozenset(
    {
        "-c",
        "-C",
        "-d",
        "-D",
        "-f",
        "-m",
        "-M",
        "--copy",
        "--create-reflog",
        "--delete",
        "--edit-description",
        "--move",
        "--no-create-reflog",
        "--set-upstream-to",
        "--track",
        "--unset-upstream",
    }
)
SHELL_WRAPPER_COMMANDS = frozenset({"bash", "sh", "zsh"})
SHELL_FLAGS_WITH_VALUES = frozenset({"-D", "-O", "-o", "--init-file", "--rcfile"})
SHELL_SAFE_SINGLE_ARG_FLAGS = frozenset({"-h", "--help", "--version"})
SHELL_CONTROL_TOKENS = frozenset({"&&", "||", ";", "|", "&", "(", ")"})
EXPECTED_TMUX_PANE_TITLES = frozenset(
    {
        "PANE 1 · LIVE PIPELINE LOG",
        "PANE 2 · REVIEW FINDINGS",
        "PANE 3 · PLAIN-ENGLISH STATUS",
        "PANE 4 · SESSION TIMELINE",
    }
)
TMUX_PANE_STATE_CANARIES = {
    "PANE 2 · REVIEW FINDINGS": frozenset(
        {
            "Decision:",
            "Starting...",
            "In progress...",
            "No active Phase A/Phase B bridge rounds",
            "Latest meta review",
            "Meta review",
            "Commit path",
        }
    ),
    "PANE 3 · PLAIN-ENGLISH STATUS": frozenset(
        {
            "No pipeline step is running. Waiting for the next wave.",
            "WHO'S WORKING",
            "Nobody is working right now.",
            "BRIDGE",
            "Current step:",
            "Last saved Phase B checkpoint:",
            "Last gate decision:",
        }
    ),
    "PANE 4 · SESSION TIMELINE": frozenset(
        {
            "No pipeline activity yet",
            "Typical durations:",
            "← idle",
            "← Codex reviewing now",
            "← Claude implementing now",
            "← SDK review agents checking this worktree now",
            "← pipeline executor working in this worktree now",
        }
    ),
}
TMUX_PANE_1_INFRA_ERROR_PATTERNS = (
    re.compile(
        r"^(?:bash|sh|zsh): .*?(?:No such file or directory|command not found)$"
    ),
    re.compile(
        r"^tail: .*?(?:cannot open|cannot follow|no files remaining|has become inaccessible|error reading|No such file or directory).*$"
    ),
)
EXPECTED_DASHBOARD_KEYS = frozenset({"timestamp", "phase", "git_branch", "narrative"})
EXPECTED_DASHBOARD_PHASE_KEYS = frozenset({"phase", "pid", "started"})
@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"


def _repo_root() -> Path:
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
        if root:
            return Path(root)
    except Exception:
        pass
    return Path(__file__).resolve().parents[3]


def _repo_anchor_candidates() -> list[Path]:
    repo_root = _repo_root()
    anchors = [repo_root]
    result = _run(["git", "rev-parse", "--git-common-dir"], cwd=repo_root)
    if result.returncode != 0:
        return anchors
    common_dir_raw = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""
    if not common_dir_raw:
        return anchors
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    try:
        common_parent = common_dir.resolve().parent
    except OSError:
        return anchors

    if not any(_paths_resolve_equal(common_parent, anchor) for anchor in anchors):
        anchors.append(common_parent)
    return anchors


def _codex_home() -> Path:
    override = os.environ.get("RCX_CODEX_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codex"


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = f"{type(exc).__name__}: {exc}"
        if exc.stderr:
            stderr = f"{stderr}; stderr={exc.stderr}"
        return subprocess.CompletedProcess(
            cmd,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=stderr,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            cmd,
            returncode=127,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _run_hook_script(
    hook_path: Path,
    payload: dict[str, object],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [sys.executable, str(hook_path)],
            cwd=str(_repo_root()),
            input=json.dumps(payload),
            capture_output=True,
            env=env,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = f"{type(exc).__name__}: {exc}"
        if exc.stderr:
            stderr = f"{stderr}; stderr={exc.stderr}"
        return subprocess.CompletedProcess(
            [sys.executable, str(hook_path)],
            returncode=124,
            stdout=exc.stdout or "",
            stderr=stderr,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            [sys.executable, str(hook_path)],
            returncode=127,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
        )


def _iter_json_string_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[tuple[object, ...], str]]:
    hits: list[tuple[tuple[object, ...], str]] = []
    if isinstance(value, str):
        hits.append((path, value))
        return hits
    if isinstance(value, dict):
        for key, child in value.items():
            hits.extend(_iter_json_string_paths(child, path + (key,)))
        return hits
    if isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_iter_json_string_paths(child, path + (index,)))
    return hits


def _format_json_path(path: tuple[object, ...]) -> str:
    rendered: list[str] = []
    for part in path:
        if isinstance(part, int):
            if rendered:
                rendered[-1] = f"{rendered[-1]}[{part}]"
            else:
                rendered.append(f"[{part}]")
        else:
            rendered.append(str(part))
    return ".".join(rendered)


def _is_disabled_prompt_hook_stub(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False

    main_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"]
    if len(main_defs) != 1:
        return False

    main_def = main_defs[0]
    statements = [
        node
        for node in main_def.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    if len(statements) != 1:
        return False

    only_statement = statements[0]
    if not isinstance(only_statement, ast.Return):
        return False
    value = only_statement.value
    if not isinstance(value, ast.Constant) or value.value != 0:
        return False

    for node in ast.walk(main_def):
        if isinstance(node, ast.Call):
            return False
    return True


def _python_string_literals(text: str) -> list[str] | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None

    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
    return literals


def _python_function_def(text: str, function_name: str) -> ast.FunctionDef | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node
    return None


def _function_source(text: str, function_name: str) -> str | None:
    function = _python_function_def(text, function_name)
    if function is None:
        return None
    return ast.get_source_segment(text, function)


def _literal_string(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        value = ast.literal_eval(node)
    except (SyntaxError, ValueError):
        return None
    return value if isinstance(value, str) else None


def _literal_string_list(node: ast.AST | None) -> list[str] | None:
    if node is None:
        return None
    try:
        value = ast.literal_eval(node)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, list) or any(not isinstance(part, str) for part in value):
        return None
    return value


def _resolve_literal_node(
    node: ast.AST | None,
    *,
    module_bindings: dict[str, ast.AST],
    seen_names: frozenset[str] = frozenset(),
) -> ast.AST | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        if node.id in seen_names:
            return None
        resolved = module_bindings.get(node.id)
        if resolved is None:
            return None
        return _resolve_literal_node(
            resolved,
            module_bindings=module_bindings,
            seen_names=seen_names | {node.id},
        )
    return node


def _session_start_target_repo(text: str) -> Path | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "TARGET_REPO_RAW" for target in node.targets):
            continue
        raw_value = _literal_string(node.value)
        if raw_value:
            return Path(raw_value).expanduser()
    return None


def _paths_resolve_equal(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _iter_prefix_rule_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    marker = "prefix_rule("
    index = 0
    while True:
        start = text.find(marker, index)
        if start == -1:
            return blocks

        depth = 0
        quote: str | None = None
        escaped = False
        pos = start
        while pos < len(text):
            char = text[pos]
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            else:
                if char in {"'", '"'}:
                    quote = char
                elif char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        blocks.append(text[start : pos + 1])
                        pos += 1
                        break
            pos += 1
        else:
            blocks.append(text[start:])
            return blocks

        index = pos


def _iter_allow_rule_calls(text: str) -> tuple[list[tuple[list[str] | None, str]], bool]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], False

    module_bindings, _ = _module_bindings(text)
    calls: list[tuple[list[str] | None, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != "prefix_rule":
            continue

        pattern_node = node.args[0] if node.args else None
        decision_node = node.args[1] if len(node.args) > 1 else None
        for keyword in node.keywords:
            if keyword.arg == "pattern":
                pattern_node = keyword.value
            elif keyword.arg == "decision":
                decision_node = keyword.value

        resolved_decision = _resolve_literal_node(
            decision_node,
            module_bindings=module_bindings,
        )
        if _literal_string(resolved_decision) != "allow":
            continue

        source = ast.get_source_segment(text, node) or ""
        resolved_pattern = _resolve_literal_node(
            pattern_node,
            module_bindings=module_bindings,
        )
        calls.append((_literal_string_list(resolved_pattern), source))
    return calls, True


def _suspicious_allow_rule_source(source: str) -> bool:
    for quoted in re.findall(r'"([^"]*)"|\'([^\']*)\'', source):
        token = quoted[0] or quoted[1]
        if not token:
            continue
        command = _command_name(token)
        if command == "git" or command == "env":
            return True
        if command in SHELL_WRAPPER_COMMANDS or command in BROAD_INTERPRETER_ALLOW_COMMANDS:
            return True
    return False


def _is_sys_stdout_reference(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
        and node.attr in {"stdout", "__stdout__"}
    )


def _is_json_call(node: ast.AST, method: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        and node.func.attr == method
    )


def _call_writes_json_to_stdout(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False

    if _is_json_call(node, "dump"):
        stdout_target = node.args[1] if len(node.args) >= 2 else None
        if stdout_target is None:
            for keyword in node.keywords:
                if keyword.arg in {"fp", "file"}:
                    stdout_target = keyword.value
                    break
        return stdout_target is not None and _is_sys_stdout_reference(stdout_target)

    if isinstance(node.func, ast.Name) and node.func.id == "print":
        return any(_is_json_call(arg, "dumps") for arg in node.args)

    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "write"
        and _is_sys_stdout_reference(node.func.value)
        and any(_is_json_call(arg, "dumps") for arg in node.args)
    )


def _call_exits_process(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name) and node.func.id in {"exit", "quit"}:
        return True
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "sys"
        and node.func.attr == "exit"
    )


def _is_docstring_statement(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _statement_calls_name(node: ast.stmt, name: str) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == name
        for child in ast.walk(node)
    )


def _is_environment_mapping_reference(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Name)
        and node.id == "environ"
    ) or (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
        and node.attr == "environ"
    )


def _environment_lookup_names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()

    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if (
                isinstance(child.func, ast.Attribute)
                and child.func.attr == "get"
                and _is_environment_mapping_reference(child.func.value)
            ):
                name = _literal_string(child.args[0] if child.args else None)
                if name is not None:
                    names.add(name)
                continue
            if (
                isinstance(child.func, ast.Attribute)
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "os"
                and child.func.attr == "getenv"
            ) or (isinstance(child.func, ast.Name) and child.func.id == "getenv"):
                name = _literal_string(child.args[0] if child.args else None)
                if name is not None:
                    names.add(name)
                continue
        if isinstance(child, ast.Subscript) and _is_environment_mapping_reference(child.value):
            slice_node = child.slice.value if isinstance(child.slice, ast.Index) else child.slice
            name = _literal_string(slice_node)
            if name is not None:
                names.add(name)
    return names


def _statement_may_terminate_before_emit(statement: ast.stmt, emit_name: str) -> bool:
    if _is_docstring_statement(statement):
        return False
    if _statement_calls_name(statement, emit_name):
        return False
    if isinstance(statement, (ast.Return, ast.Raise)):
        return True
    if any(_call_exits_process(node) for node in ast.walk(statement)):
        return True

    child_blocks: list[list[ast.stmt]] = []
    if isinstance(statement, ast.If):
        child_blocks.extend([statement.body, statement.orelse])
    elif isinstance(statement, ast.Try):
        child_blocks.append(statement.body)
        child_blocks.extend(handler.body for handler in statement.handlers)
        child_blocks.extend([statement.orelse, statement.finalbody])
    elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        child_blocks.extend([statement.body, statement.orelse])
    elif isinstance(statement, (ast.With, ast.AsyncWith)):
        child_blocks.append(statement.body)
    elif isinstance(statement, ast.Match):
        child_blocks.extend(case.body for case in statement.cases)

    return any(_statements_may_terminate_before_emit(block, emit_name) for block in child_blocks)


def _statements_may_terminate_before_emit(statements: list[ast.stmt], emit_name: str) -> bool:
    for statement in statements:
        if _is_docstring_statement(statement):
            continue
        if _statement_calls_name(statement, emit_name):
            return False
        if _statement_may_terminate_before_emit(statement, emit_name):
            return True
    return False


def _unapproved_pre_emit_env_gates(function: ast.FunctionDef, *, emit_name: str) -> set[str]:
    blocked: set[str] = set()

    for statement in function.body:
        if _is_docstring_statement(statement):
            continue
        if _statement_calls_name(statement, emit_name):
            break

        if isinstance(statement, ast.If):
            env_names = _environment_lookup_names(statement.test)
            if env_names and (
                _statements_may_terminate_before_emit(statement.body, emit_name)
                or _statements_may_terminate_before_emit(statement.orelse, emit_name)
            ):
                blocked |= env_names - ALLOWED_SESSION_START_PRE_EMIT_ENV_VARS

        child_blocks: list[list[ast.stmt]] = []
        if isinstance(statement, ast.Try):
            child_blocks.append(statement.body)
            child_blocks.extend(handler.body for handler in statement.handlers)
            child_blocks.extend([statement.orelse, statement.finalbody])
        elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
            child_blocks.extend([statement.body, statement.orelse])
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            child_blocks.append(statement.body)
        elif isinstance(statement, ast.Match):
            child_blocks.extend(case.body for case in statement.cases)

        for block in child_blocks:
            for child in block:
                if isinstance(child, ast.If):
                    env_names = _environment_lookup_names(child.test)
                    if env_names and (
                        _statements_may_terminate_before_emit(child.body, emit_name)
                        or _statements_may_terminate_before_emit(child.orelse, emit_name)
                    ):
                        blocked |= env_names - ALLOWED_SESSION_START_PRE_EMIT_ENV_VARS

        if _statement_may_terminate_before_emit(statement, emit_name):
            break

    return blocked


def _function_has_terminal_before_emit(function: ast.FunctionDef, emit_name: str | None = None) -> bool:
    for statement in function.body:
        if _is_docstring_statement(statement):
            continue
        if emit_name is None:
            if any(_call_writes_json_to_stdout(node) for node in ast.walk(statement)):
                return False
        elif _statement_calls_name(statement, emit_name):
            return False
        if isinstance(statement, (ast.Return, ast.Raise)):
            return True
        if any(_call_exits_process(node) for node in ast.walk(statement)):
            return True
    return True


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False

    left = test.left
    right = test.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    ) or (
        isinstance(right, ast.Name)
        and right.id == "__name__"
        and isinstance(left, ast.Constant)
        and left.value == "__main__"
    )


def _module_has_unsafe_top_level_execution(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return True

    def _is_static_assignment_value(node: ast.AST | None) -> bool:
        if node is None:
            return True
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return all(_is_static_assignment_value(elt) for elt in node.elts)
        if isinstance(node, ast.Dict):
            return all(
                _is_static_assignment_value(key) and _is_static_assignment_value(value)
                for key, value in zip(node.keys, node.values, strict=False)
            )
        return False

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Pass)):
            continue
        if isinstance(node, ast.Assign) and _is_static_assignment_value(node.value):
            continue
        if isinstance(node, ast.AnnAssign) and _is_static_assignment_value(node.value):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.If) and _is_main_guard(node):
            continue
        return True
    return False


def _function_calls_name(function: ast.FunctionDef, name: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
        for node in ast.walk(function)
    )


def _join_call_uses_name(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == name
    )


def _main_joins_lines_via_emit(function: ast.FunctionDef) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_emit":
            continue
        args = list(node.args)
        if not args:
            for keyword in node.keywords:
                if keyword.arg == "additional_context":
                    args.append(keyword.value)
                    break
        if args and _join_call_uses_name(args[0], "lines"):
            return True
    return False


def _is_zero_or_none_literal(node: ast.AST | None) -> bool:
    return node is None or (isinstance(node, ast.Constant) and node.value == 0)


def _function_returns_only_zero_or_none(function: ast.FunctionDef) -> bool:
    return all(
        _is_zero_or_none_literal(node.value)
        for node in ast.walk(function)
        if isinstance(node, ast.Return)
    )


def _stdout_write_kind(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    if isinstance(node.func, ast.Name) and node.func.id == "print":
        return "print"
    if _is_json_call(node, "dump"):
        stdout_target = node.args[1] if len(node.args) >= 2 else None
        if stdout_target is None:
            for keyword in node.keywords:
                if keyword.arg in {"fp", "file"}:
                    stdout_target = keyword.value
                    break
        return "json_dump_stdout" if stdout_target is not None and _is_sys_stdout_reference(stdout_target) else None
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "write"
        and _is_sys_stdout_reference(node.func.value)
    ):
        if len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and node.args[0].value == "\n":
            return "newline_stdout"
        return "stdout_write"
    return None


def _function_stdout_write_kinds(function: ast.FunctionDef) -> list[str]:
    kinds: list[str] = []
    for node in ast.walk(function):
        kind = _stdout_write_kind(node)
        if kind is not None:
            kinds.append(kind)
    return kinds


def _function_stdout_write_kinds_recursive(
    function_name: str,
    *,
    function_defs: dict[str, ast.FunctionDef],
    seen_functions: frozenset[str],
) -> list[str]:
    if function_name in seen_functions:
        return []
    function = function_defs.get(function_name)
    if function is None:
        return []

    kinds = _function_stdout_write_kinds(function)
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        nested_function_name = _call_name(node.func)
        if nested_function_name in function_defs:
            kinds.extend(
                _function_stdout_write_kinds_recursive(
                    nested_function_name,
                    function_defs=function_defs,
                    seen_functions=seen_functions | {function_name},
                )
            )
    return kinds


def _is_named_function_call(node: ast.AST | None, function_name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and _call_name(node.func) == function_name
        and not node.args
        and not node.keywords
    )


def _guard_statement_invokes_function(statement: ast.stmt, function_name: str) -> bool:
    if isinstance(statement, ast.Raise):
        exc = statement.exc
        return (
            isinstance(exc, ast.Call)
            and _call_name(exc.func) == "SystemExit"
            and len(exc.args) == 1
            and _is_named_function_call(exc.args[0], function_name)
        )
    if isinstance(statement, ast.Expr) and _call_exits_process(statement.value):
        return _is_named_function_call(statement.value.args[0] if statement.value.args else None, function_name)
    if isinstance(statement, ast.Return):
        return _is_named_function_call(statement.value, function_name)
    return False


def _module_has_guarded_function_entrypoint(text: str, function_name: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    return any(
        isinstance(node, ast.If)
        and _is_main_guard(node)
        and any(_guard_statement_invokes_function(statement, function_name) for statement in node.body)
        for node in tree.body
    )


def _session_start_emits_to_stdout(text: str) -> bool:
    main_function = _python_function_def(text, "main")
    emit_function = _python_function_def(text, "_emit")
    if main_function is None or emit_function is None:
        return False
    if _function_stdout_write_kinds(main_function):
        return False
    emit_stdout_kinds = _function_stdout_write_kinds(emit_function)
    return (
        _function_calls_name(main_function, "_emit")
        and _main_joins_lines_via_emit(main_function)
        and "json_dump_stdout" in emit_stdout_kinds
        and all(kind in {"json_dump_stdout", "newline_stdout"} for kind in emit_stdout_kinds)
        and not _function_has_terminal_before_emit(main_function, "_emit")
        and not _function_has_terminal_before_emit(emit_function)
    )


def _module_bindings(text: str) -> tuple[dict[str, ast.AST], dict[str, ast.FunctionDef]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}, {}

    assignments: dict[str, ast.AST] = {}
    functions: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions[node.name] = node
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
            continue
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                assignments[node.target.id] = node.value
    return assignments, functions


def _emit_additional_context_uses_parameter(emit_function: ast.FunctionDef) -> bool:
    if not emit_function.args.args:
        return False

    parameter_name = emit_function.args.args[0].arg
    for node in ast.walk(emit_function):
        if not isinstance(node, ast.Dict):
            continue
        mapping: dict[str, ast.AST] = {}
        for key, value in zip(node.keys, node.values, strict=False):
            key_name = _literal_string(key)
            if key_name is not None:
                mapping[key_name] = value

        additional_context = mapping.get("additionalContext")
        hook_event_name = mapping.get("hookEventName")
        if (
            isinstance(additional_context, ast.Name)
            and additional_context.id == parameter_name
            and isinstance(hook_event_name, ast.Constant)
            and hook_event_name.value == "SessionStart"
        ):
            return True
    return False


def _expression_string_anchors(
    node: ast.AST | None,
    *,
    local_bindings: dict[str, ast.AST],
    module_bindings: dict[str, ast.AST],
    function_defs: dict[str, ast.FunctionDef],
    seen_names: frozenset[str] = frozenset(),
    seen_functions: frozenset[str] = frozenset(),
) -> set[str]:
    if node is None:
        return set()

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}

    if isinstance(node, ast.JoinedStr):
        anchors: set[str] = set()
        for value in node.values:
            anchors |= _expression_string_anchors(
                value,
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names,
                seen_functions=seen_functions,
            )
        return anchors

    if isinstance(node, ast.FormattedValue):
        return _expression_string_anchors(
            node.value,
            local_bindings=local_bindings,
            module_bindings=module_bindings,
            function_defs=function_defs,
            seen_names=seen_names,
            seen_functions=seen_functions,
        )

    if isinstance(node, ast.Name):
        if node.id in seen_names:
            return set()
        if node.id in local_bindings:
            return _expression_string_anchors(
                local_bindings[node.id],
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names | {node.id},
                seen_functions=seen_functions,
            )
        if node.id in module_bindings:
            return _expression_string_anchors(
                module_bindings[node.id],
                local_bindings={},
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names | {node.id},
                seen_functions=seen_functions,
            )
        return set()

    if isinstance(node, ast.Starred):
        return _expression_string_anchors(
            node.value,
            local_bindings=local_bindings,
            module_bindings=module_bindings,
            function_defs=function_defs,
            seen_names=seen_names,
            seen_functions=seen_functions,
        )

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        anchors: set[str] = set()
        for element in node.elts:
            anchors |= _expression_string_anchors(
                element,
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names,
                seen_functions=seen_functions,
            )
        return anchors

    if isinstance(node, ast.Dict):
        anchors: set[str] = set()
        for key, value in zip(node.keys, node.values, strict=False):
            anchors |= _expression_string_anchors(
                key,
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names,
                seen_functions=seen_functions,
            )
            anchors |= _expression_string_anchors(
                value,
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names,
                seen_functions=seen_functions,
            )
        return anchors

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _expression_string_anchors(
            node.left,
            local_bindings=local_bindings,
            module_bindings=module_bindings,
            function_defs=function_defs,
            seen_names=seen_names,
            seen_functions=seen_functions,
        ) | _expression_string_anchors(
            node.right,
            local_bindings=local_bindings,
            module_bindings=module_bindings,
            function_defs=function_defs,
            seen_names=seen_names,
            seen_functions=seen_functions,
        )

    if isinstance(node, ast.Call):
        anchors: set[str] = set()
        if isinstance(node.func, ast.Attribute) and node.func.attr == "join":
            anchors |= _expression_string_anchors(
                node.func.value,
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names,
                seen_functions=seen_functions,
            )
        for arg in node.args:
            anchors |= _expression_string_anchors(
                arg,
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names,
                seen_functions=seen_functions,
            )
        for keyword in node.keywords:
            anchors |= _expression_string_anchors(
                keyword.value,
                local_bindings=local_bindings,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=seen_names,
                seen_functions=seen_functions,
            )

        function_name = _call_name(node.func)
        if function_name in function_defs and function_name not in seen_functions:
            anchors |= _function_string_anchors(
                function_name,
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_functions=seen_functions | {function_name},
            )
        return anchors

    return set()


def _function_string_anchors(
    function_name: str,
    *,
    module_bindings: dict[str, ast.AST],
    function_defs: dict[str, ast.FunctionDef],
    seen_functions: frozenset[str],
) -> set[str]:
    function = function_defs.get(function_name)
    if function is None:
        return set()

    anchors: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            anchors.add(node.value)
            continue
        if isinstance(node, ast.Name) and node.id in module_bindings:
            anchors |= _expression_string_anchors(
                module_bindings[node.id],
                local_bindings={},
                module_bindings=module_bindings,
                function_defs=function_defs,
                seen_names=frozenset({node.id}),
                seen_functions=seen_functions,
            )
            continue
        if isinstance(node, ast.Call):
            nested_function_name = _call_name(node.func)
            if nested_function_name in function_defs and nested_function_name not in seen_functions:
                anchors |= _function_string_anchors(
                    nested_function_name,
                    module_bindings=module_bindings,
                    function_defs=function_defs,
                    seen_functions=seen_functions | {nested_function_name},
                )
    return anchors


def _prompt_hook_code_anchors(text: str) -> set[str]:
    module_bindings, function_defs = _module_bindings(text)
    return _function_string_anchors(
        "main",
        module_bindings=module_bindings,
        function_defs=function_defs,
        seen_functions=frozenset(),
    )


def _session_start_payload_anchors(text: str) -> set[str]:
    main_function = _python_function_def(text, "main")
    if main_function is None or not _main_joins_lines_via_emit(main_function):
        return set()

    module_bindings, function_defs = _module_bindings(text)
    local_bindings: dict[str, ast.AST] = {}
    line_contributors: list[ast.AST] = []

    def _collect_statements(statements: list[ast.stmt]) -> None:
        nonlocal line_contributors
        for statement in statements:
            if isinstance(statement, ast.Assign):
                if len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                    target_name = statement.targets[0].id
                    local_bindings[target_name] = statement.value
                    if target_name == "lines":
                        line_contributors = [statement.value]
                continue

            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                target_name = statement.target.id
                if statement.value is not None:
                    local_bindings[target_name] = statement.value
                    if target_name == "lines":
                        line_contributors = [statement.value]
                continue

            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "lines"
                    and call.args
                    and call.func.attr in {"append", "extend"}
                ):
                    line_contributors.append(call.args[0])
                    continue

            if isinstance(statement, ast.If):
                _collect_statements(statement.body)
                _collect_statements(statement.orelse)
                continue

            if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                _collect_statements(statement.body)
                _collect_statements(statement.orelse)
                continue

            if isinstance(statement, (ast.With, ast.AsyncWith)):
                _collect_statements(statement.body)
                continue

            if isinstance(statement, ast.Try):
                _collect_statements(statement.body)
                for handler in statement.handlers:
                    _collect_statements(handler.body)
                _collect_statements(statement.orelse)
                _collect_statements(statement.finalbody)

    _collect_statements(main_function.body)

    anchors: set[str] = set()
    for contributor in line_contributors:
        anchors |= _expression_string_anchors(
            contributor,
            local_bindings=local_bindings,
            module_bindings=module_bindings,
            function_defs=function_defs,
        )
    return anchors


def _format_command(pattern: list[str]) -> str:
    return " ".join(pattern)


def _command_name(token: str) -> str:
    return Path(token).name


def _is_broad_interpreter_command(command: str) -> bool:
    return (
        command in BROAD_INTERPRETER_ALLOW_COMMANDS
        or command == "nodejs"
        or PYTHON_INTERPRETER_RE.fullmatch(command) is not None
    )


def _interpreter_value_flags(command: str) -> frozenset[str]:
    if command == "nodejs":
        return frozenset(INTERPRETER_VALUE_FLAGS["node"])
    if PYTHON_INTERPRETER_RE.fullmatch(command) is not None:
        return frozenset(INTERPRETER_VALUE_FLAGS["python3"])
    return frozenset(INTERPRETER_VALUE_FLAGS.get(command, frozenset()))


def _normalize_repo_script_path(token: str) -> str | None:
    normalized = token.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = Path(normalized)
    if path.is_absolute():
        try:
            normalized = path.relative_to(_repo_root()).as_posix()
        except ValueError:
            return None
    if any(part == ".." for part in Path(normalized).parts):
        return None
    return normalized


def _is_safe_repo_interpreter_script(token: str) -> bool:
    normalized = _normalize_repo_script_path(token)
    return normalized in SAFE_REPO_INTERPRETER_SCRIPTS


def _unwrap_env_command(pattern: list[str]) -> list[str]:
    unwrapped = list(pattern)
    while unwrapped and _command_name(unwrapped[0]) == "env":
        expanded = _unwrap_single_env_command(unwrapped)
        if expanded == unwrapped:
            return expanded
        unwrapped = expanded
    return unwrapped


def _unwrap_single_env_command(pattern: list[str]) -> list[str]:
    index = 1
    while index < len(pattern):
        token = pattern[index]
        if SHELL_ASSIGNMENT_RE.fullmatch(token):
            index += 1
            continue
        if token in ENV_SPLIT_STRING_FLAGS:
            if index + 1 >= len(pattern):
                return pattern
            try:
                split_tokens = shlex.split(pattern[index + 1], posix=True)
            except ValueError:
                return pattern
            return split_tokens + pattern[index + 2 :]
        if token.startswith("--split-string="):
            try:
                split_tokens = shlex.split(token.split("=", 1)[1], posix=True)
            except ValueError:
                return pattern
            return split_tokens + pattern[index + 1 :]
        if token in ENV_FLAGS_WITH_VALUES:
            if index + 1 >= len(pattern):
                return pattern
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        break
    if index >= len(pattern):
        return pattern
    return pattern[index:]


def _strip_leading_assignments(pattern: list[str]) -> list[str]:
    index = 0
    while index < len(pattern) and SHELL_ASSIGNMENT_RE.fullmatch(pattern[index]):
        index += 1
    return pattern[index:]


def _shell_wrapped_command(pattern: list[str]) -> str | None:
    unwrapped_pattern = _strip_leading_assignments(_unwrap_env_command(pattern))
    if len(unwrapped_pattern) < 3:
        return None
    if _command_name(unwrapped_pattern[0]) not in SHELL_WRAPPER_COMMANDS:
        return None

    args = unwrapped_pattern[1:]
    index = 0
    while index < len(args):
        token = args[index]
        if token in SHELL_FLAGS_WITH_VALUES:
            index += 2
            continue
        if any(token.startswith(f"{flag}=") for flag in SHELL_FLAGS_WITH_VALUES):
            index += 1
            continue
        if token == "-c":
            return args[index + 1] if index + 1 < len(args) else None
        if token.startswith("-") and not token.startswith("--") and "c" in token[1:]:
            return args[index + 1] if index + 1 < len(args) else None
        if token.startswith("-"):
            index += 1
            continue
        break
    return None


def _replace_unquoted_newlines(command: str) -> str:
    normalized: list[str] = []
    quote: str | None = None
    escaped = False
    for char in command:
        if quote is not None:
            normalized.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            normalized.append(char)
            continue
        if char in {"\n", "\r"}:
            normalized.append(";")
            continue
        normalized.append(char)
    return "".join(normalized)


def _split_shell_commands(command: str) -> list[list[str]] | None:
    lexer = shlex.shlex(
        _replace_unquoted_newlines(command),
        posix=True,
        punctuation_chars=";&|()<>",
    )
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None

    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in SHELL_CONTROL_TOKENS:
            if current:
                commands.append(current)
                current = []
            continue
        current.append(token)
    if current:
        commands.append(current)
    return commands


def _git_commands_from_pattern(pattern: list[str]) -> list[list[str]] | None:
    if not pattern:
        return []

    unwrapped_pattern = _strip_leading_assignments(_unwrap_env_command(pattern))
    if not unwrapped_pattern:
        return []
    if _command_name(unwrapped_pattern[0]) == "git":
        return [unwrapped_pattern]

    shell_command = _shell_wrapped_command(pattern)
    if shell_command is None:
        return []

    commands = _split_shell_commands(shell_command)
    if commands is None:
        if re.search(r"(^|[\s;&|()])git($|[\s;&|()])", shell_command):
            return None
        return []

    git_commands: list[list[str]] = []
    for command_tokens in commands:
        index = 0
        while index < len(command_tokens) and SHELL_ASSIGNMENT_RE.fullmatch(command_tokens[index]):
            index += 1
        if index >= len(command_tokens):
            continue
        candidate = _unwrap_env_command(command_tokens[index:])
        if not candidate:
            continue
        if _command_name(candidate[0]) != "git":
            continue
        git_commands.append(candidate)
    return git_commands


def _git_allow_rule_is_safe(pattern: list[str]) -> bool:
    if not pattern or _command_name(pattern[0]) != "git":
        return True
    if len(pattern) == 1:
        return False

    subcommand = pattern[1]
    if subcommand in READ_ONLY_GIT_SUBCOMMANDS:
        return True
    if subcommand != "branch":
        return False

    branch_args = pattern[2:]
    if not branch_args:
        return False
    if any(arg in BRANCH_MUTATING_FLAGS for arg in branch_args):
        return False
    return any(arg in BRANCH_READ_ONLY_FLAGS for arg in branch_args)


def _interpreter_allow_rule_is_broad(pattern: list[str]) -> str | None:
    if not pattern:
        return None

    unwrapped_pattern = _strip_leading_assignments(_unwrap_env_command(pattern))
    if not unwrapped_pattern:
        return None
    command = _command_name(unwrapped_pattern[0])
    if not _is_broad_interpreter_command(command):
        return None
    if len(unwrapped_pattern) == 1:
        return f"{command} <broad interpreter allow>"

    args = unwrapped_pattern[1:]
    target = args[0]
    if target in INTERPRETER_SAFE_SINGLE_ARG_FLAGS:
        return None
    if target == "-":
        return f"{command} <broad interpreter allow>"
    if target in _interpreter_value_flags(command):
        if len(args) == 1:
            return f"{command} <broad interpreter allow>"
        return None
    if target.startswith("-") and len(args) == 1:
        return f"{command} <broad interpreter allow>"
    if not target.startswith("-"):
        if _is_safe_repo_interpreter_script(target):
            return None
        return f"{command} <script-backed interpreter allow>"
    return None


def _shell_allow_rule_runs_script(pattern: list[str]) -> str | None:
    if not pattern:
        return None

    unwrapped_pattern = _strip_leading_assignments(_unwrap_env_command(pattern))
    if not unwrapped_pattern:
        return None
    command = _command_name(unwrapped_pattern[0])
    if command not in SHELL_WRAPPER_COMMANDS:
        return None
    if len(unwrapped_pattern) == 1:
        return None

    args = unwrapped_pattern[1:]
    index = 0
    while index < len(args):
        token = args[index]
        if token in SHELL_FLAGS_WITH_VALUES:
            if index + 1 >= len(args):
                return None
            index += 2
            continue
        if any(token.startswith(f"{flag}=") for flag in SHELL_FLAGS_WITH_VALUES):
            index += 1
            continue
        if token in SHELL_SAFE_SINGLE_ARG_FLAGS and len(args) == 1:
            return None
        if token == "-c":
            return None
        if token.startswith("-") and not token.startswith("--") and "c" in token[1:]:
            return None
        if token.startswith("-"):
            index += 1
            continue
        return f"{command} <script-backed shell allow>"
    return None


def _broad_execution_allow_rule(pattern: list[str]) -> str | None:
    if not pattern:
        return None

    shell_script = _shell_allow_rule_runs_script(pattern)
    if shell_script is not None:
        return shell_script

    broad_interpreter = _interpreter_allow_rule_is_broad(pattern)
    if broad_interpreter is not None:
        return broad_interpreter

    shell_command = _shell_wrapped_command(pattern)
    if shell_command is None:
        return None

    commands = _split_shell_commands(shell_command)
    if commands is None:
        return None

    for command_tokens in commands:
        index = 0
        while index < len(command_tokens) and SHELL_ASSIGNMENT_RE.fullmatch(command_tokens[index]):
            index += 1
        if index >= len(command_tokens):
            continue
        candidate = _unwrap_env_command(command_tokens[index:])
        if not candidate:
            continue
        shell_script = _shell_allow_rule_runs_script(candidate)
        if shell_script is not None:
            return shell_script
        broad_interpreter = _interpreter_allow_rule_is_broad(candidate)
        if broad_interpreter is not None:
            return broad_interpreter
    return None


def _unsafe_git_allow_rules(text: str) -> list[str]:
    matches: list[str] = []
    allow_calls, parsed = _iter_allow_rule_calls(text)
    if not parsed:
        for block in _iter_prefix_rule_blocks(text):
            if not re.search(r'decision\s*=\s*["\']allow["\']', block):
                continue
            if _suspicious_allow_rule_source(block):
                matches.append("git <unparseable allow rule>")
        return matches

    for pattern, source in allow_calls:
        if pattern is None:
            if _suspicious_allow_rule_source(source):
                matches.append("git <unparseable allow rule>")
            continue

        broad_execution = _broad_execution_allow_rule(pattern)
        if broad_execution is not None:
            matches.append(broad_execution)
            continue

        git_commands = _git_commands_from_pattern(pattern)
        if git_commands is None:
            matches.append("git <unparseable shell allow rule>")
            continue
        for git_command in git_commands:
            if not _git_allow_rule_is_safe(git_command):
                matches.append(_format_command(git_command))
    return matches


def _extract_binary_contradictions(payload: dict) -> list[str]:
    contradictions: list[str] = []
    for item in payload.get("specs") or []:
        if item.get("status") == "contradiction_present" and item.get("patch_id"):
            contradictions.append(str(item["patch_id"]))
    return contradictions


def _audit_binary_guard(codex_home: Path, repo_root: Path) -> CheckResult:
    binary_guard = codex_home / "bin" / "codex-binary-guard"
    if not binary_guard.exists():
        return CheckResult(
            "binary_guard",
            "FAIL",
            f"missing at {binary_guard}",
        )
    if not os.access(binary_guard, os.X_OK):
        return CheckResult(
            "binary_guard",
            "FAIL",
            f"not executable: {binary_guard}",
        )

    proc = _run([str(binary_guard), "audit", "--json"], cwd=repo_root, timeout=60)
    payload_raw = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0 or not payload_raw:
        return CheckResult(
            "binary_guard",
            "FAIL",
            "audit unreadable or non-zero",
        )

    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        return CheckResult(
            "binary_guard",
            "FAIL",
            f"invalid JSON: {exc}",
        )

    version = payload.get("version", "unknown")
    contradictions = _extract_binary_contradictions(payload)
    if payload.get("version_changed_since_patch"):
        last_patched = payload.get("last_patched") or {}
        last_version = last_patched.get("version", "unknown")
        return CheckResult(
            "binary_guard",
            "FAIL",
            f"version drift current=v{version} last_patched=v{last_version}",
        )
    if payload.get("overall_status") != "patched":
        return CheckResult(
            "binary_guard",
            "FAIL",
            f"overall_status={payload.get('overall_status')} version=v{version}",
        )
    if contradictions:
        return CheckResult(
            "binary_guard",
            "FAIL",
            "contradictions present: " + ", ".join(contradictions),
        )
    return CheckResult(
        "binary_guard",
        "OK",
        f"patched version=v{version}",
    )


def _check_session_start_hook(codex_home: Path) -> CheckResult:
    hook_path = codex_home / "hooks" / "session_start_rcx_preflight.py"
    text = _read_text(hook_path)
    if text is None:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            f"missing: {hook_path}",
        )

    missing = [needle for needle in SESSION_START_REQUIRED_CANARIES if needle not in text]
    if missing:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "missing canaries: " + ", ".join(missing),
        )

    literals = _python_string_literals(text)
    if literals is None:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "hook source is not valid Python",
        )

    if _module_has_unsafe_top_level_execution(text):
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "unsafe top-level execution outside main guard",
        )

    main_function = _python_function_def(text, "main")
    emit_function = _python_function_def(text, "_emit")
    if main_function is None or emit_function is None:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "missing SessionStart emission structure",
        )

    target_repo = _session_start_target_repo(text)
    if target_repo is None:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "missing target repo anchor",
        )
    missing_literals = [
        needle
        for needle in SESSION_START_REQUIRED_CANARIES
        if not any(needle in literal for literal in literals)
    ]
    if missing_literals:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "missing code-bound canaries: " + ", ".join(missing_literals),
        )

    required_structure = ("SessionStart", "additionalContext", "hookSpecificOutput")
    emit_source = _function_source(text, "_emit") or ""
    missing_structure = [marker for marker in required_structure if marker not in emit_source]
    emits_session_payload = _session_start_emits_to_stdout(text)
    if (
        missing_structure
        or not _emit_additional_context_uses_parameter(emit_function)
        or not emits_session_payload
        or not _module_has_guarded_function_entrypoint(text, "main")
        or not _function_returns_only_zero_or_none(main_function)
    ):
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "missing SessionStart emission structure",
        )

    payload_anchors = _session_start_payload_anchors(text)
    missing_payload_canaries = [
        needle
        for needle in SESSION_START_REQUIRED_CANARIES
        if not any(needle in anchor for anchor in payload_anchors)
    ]
    if missing_payload_canaries:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "missing emitted payload canaries: " + ", ".join(missing_payload_canaries),
        )

    blocked_env_gates = sorted(_unapproved_pre_emit_env_gates(main_function, emit_name="_emit"))
    if blocked_env_gates:
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "unapproved pre-emit environment gates: " + ", ".join(blocked_env_gates),
        )

    expected_repos = _repo_anchor_candidates()
    if not any(_paths_resolve_equal(target_repo, expected_repo) for expected_repo in expected_repos):
        return CheckResult(
            "session_start_hook",
            "FAIL",
            "target repo anchor mismatch: "
            f"{target_repo} not in {[str(path) for path in expected_repos]}",
        )

    return CheckResult(
        "session_start_hook",
        "OK",
        "startup hook statically anchors preflight, binary guard, drift memory, and target repo",
    )


def _check_prompt_hook(codex_home: Path) -> CheckResult:
    hook_path = codex_home / "hooks" / "user_prompt_submit_rcx_identity.py"
    text = _read_text(hook_path)
    if text is None:
        return CheckResult(
            "prompt_hook",
            "FAIL",
            f"missing: {hook_path}",
        )

    if PROMPT_HOOK_DISABLED_CANARY in text:
        if not _is_disabled_prompt_hook_stub(text):
            return CheckResult(
                "prompt_hook",
                "FAIL",
                "disabled prompt hook contains active code beyond a return-0 stub",
            )
        if _module_has_unsafe_top_level_execution(text):
            return CheckResult(
                "prompt_hook",
                "FAIL",
                "disabled prompt hook contains unsafe top-level execution",
            )
        return CheckResult(
            "prompt_hook",
            "OK",
            "disabled intentionally until UserPromptSubmit can be hidden",
        )

    literals = _python_string_literals(text)
    if literals is None:
        return CheckResult(
            "prompt_hook",
            "FAIL",
            "hook source is not valid Python",
        )

    if _module_has_unsafe_top_level_execution(text):
        return CheckResult(
            "prompt_hook",
            "FAIL",
            "active prompt hook contains unsafe top-level execution",
        )

    main_function = _python_function_def(text, "main")
    if main_function is None or not _module_has_guarded_function_entrypoint(text, "main"):
        return CheckResult(
            "prompt_hook",
            "FAIL",
            "active prompt hook missing guarded main entrypoint",
        )

    if not _function_returns_only_zero_or_none(main_function):
        return CheckResult(
            "prompt_hook",
            "FAIL",
            "active prompt hook main must return 0 or None",
        )

    anchors = _prompt_hook_code_anchors(text)
    missing = [
        needle
        for needle in PROMPT_HOOK_REQUIRED_CANARIES
        if not any(needle in anchor for anchor in anchors)
    ]
    if missing:
        return CheckResult(
            "prompt_hook",
            "FAIL",
            "missing code-bound RCX protocol canaries: " + ", ".join(missing),
        )

    _, function_defs = _module_bindings(text)
    if _function_stdout_write_kinds_recursive(
        "main",
        function_defs=function_defs,
        seen_functions=frozenset(),
    ):
        return CheckResult(
            "prompt_hook",
            "FAIL",
            "active prompt hook emitted output",
        )

    return CheckResult(
        "prompt_hook",
        "OK",
        "active prompt hook statically anchors RCX protocol canaries",
    )


def _check_default_rules(codex_home: Path) -> CheckResult:
    rules_path = codex_home / "rules" / "default.rules"
    text = _read_text(rules_path)
    if text is None:
        return CheckResult(
            "default_rules",
            "FAIL",
            f"missing: {rules_path}",
        )

    matches = _unsafe_git_allow_rules(text)
    if matches:
        return CheckResult(
            "default_rules",
            "FAIL",
            "permissive manual git allow reintroduced: "
            + ", ".join(sorted(set(matches))),
        )

    return CheckResult(
        "default_rules",
        "OK",
        "no disallowed manual git write/fetch allow rules detected",
    )


def _check_models_cache(codex_home: Path) -> CheckResult:
    models_cache = codex_home / "models_cache.json"
    text = _read_text(models_cache)
    if text is None:
        return CheckResult(
            "models_cache",
            "FAIL",
            f"missing: {models_cache}",
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return CheckResult(
            "models_cache",
            "FAIL",
            f"invalid JSON: {exc}",
        )

    disallowed_paths: list[str] = []
    allowed_paths: list[str] = []
    allowed_suffix = ("instructions_variables", "personality_friendly")
    for path, string_value in _iter_json_string_paths(payload):
        matched = [
            needle for needle in STALE_MODELS_CACHE_CANARIES if needle in string_value
        ]
        if not matched:
            continue
        if tuple(path[-2:]) == allowed_suffix:
            allowed_paths.append(_format_json_path(path))
            continue
        disallowed_paths.append(_format_json_path(path))
    if disallowed_paths:
        preview = "; ".join(disallowed_paths[:3])
        if len(disallowed_paths) > 3:
            preview += f"; +{len(disallowed_paths) - 3} more"
        return CheckResult(
            "models_cache",
            "FAIL",
            "stale friendly-persona canaries present outside personality_friendly: " + preview,
        )

    if allowed_paths:
        return CheckResult(
            "models_cache",
            "OK",
            "friendly canaries confined to vendor personality_friendly variants",
        )

    return CheckResult(
        "models_cache",
        "OK",
        "no stale friendly-persona canaries detected",
    )


def _dashboard_health(port: int = WEB_PORT) -> tuple[bool, str]:
    url = f"http://127.0.0.1:{port}/api/state"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status != 200:
                return False, f"unexpected HTTP {response.status} from {url}"
            payload = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return False, f"{url} unavailable: {type(exc).__name__}"

    if not isinstance(payload, dict):
        return False, f"{url} returned a non-object JSON payload"

    missing = sorted(EXPECTED_DASHBOARD_KEYS.difference(payload))
    if missing:
        return False, f"{url} missing keys: {', '.join(missing)}"

    phase = payload.get("phase")
    if not isinstance(phase, dict):
        return False, f"{url} has invalid phase payload"

    missing_phase = sorted(EXPECTED_DASHBOARD_PHASE_KEYS.difference(phase))
    if missing_phase:
        return False, f"{url} phase missing keys: {', '.join(missing_phase)}"

    if not isinstance(payload.get("git_branch"), str):
        return False, f"{url} has invalid git_branch payload"
    if not isinstance(payload.get("narrative"), list):
        return False, f"{url} has invalid narrative payload"

    return True, f"serving RCX dashboard on {url}"


def _dashboard_healthy(port: int = WEB_PORT) -> bool:
    healthy, _ = _dashboard_health(port)
    return healthy


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text).replace("\r", "")


def _tmux_pane_body_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in _strip_ansi(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Pane "):
            continue
        if set(line) <= {"━", "─", "-"}:
            continue
        if line.startswith("── ") and line.endswith(" ──"):
            continue
        lines.append(line)
    return lines


def _preview_lines(lines: list[str], *, limit: int = 3) -> str:
    if not lines:
        return "no rendered body content"
    preview = "; ".join(lines[:limit])
    if len(lines) > limit:
        preview += f"; +{len(lines) - limit} more"
    return preview


def _tmux_pane_1_live_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    live_lines: list[str] = []
    infra_errors: list[str] = []
    for line in lines:
        if any(pattern.match(line) for pattern in TMUX_PANE_1_INFRA_ERROR_PATTERNS):
            infra_errors.append(line)
            continue
        live_lines.append(line)
    return live_lines, infra_errors


def _tmux_pane_has_live_content(title: str, body: str) -> tuple[bool, str]:
    lines = _tmux_pane_body_lines(body)
    if title == "PANE 1 · LIVE PIPELINE LOG":
        live_lines, infra_errors = _tmux_pane_1_live_lines(lines)
        if live_lines:
            return True, _preview_lines(live_lines)
        if infra_errors:
            return False, "only monitor error output: " + _preview_lines(infra_errors)
        return False, _preview_lines(lines)

    joined = "\n".join(lines)
    canaries = TMUX_PANE_STATE_CANARIES.get(title, frozenset())
    has_live_state = any(canary in joined for canary in canaries)
    return has_live_state, _preview_lines(lines)


def _tmux_monitor_signature(repo_root: Path, session: str) -> tuple[bool, str]:
    panes = _run(
        ["tmux", "list-panes", "-t", session, "-F", "#{pane_id}\t#{pane_title}"],
        cwd=repo_root,
        timeout=10,
    )
    if panes.returncode != 0:
        detail = (panes.stderr or panes.stdout or "").strip()
        if not detail:
            detail = f"tmux list-panes exit {panes.returncode}"
        return False, detail

    pane_titles: dict[str, str] = {}
    for raw_line in panes.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pane_id, separator, pane_title = line.partition("\t")
        if not separator or not pane_id.strip() or not pane_title.strip():
            return False, "tmux list-panes returned an unparseable pane entry"
        pane_titles[pane_title.strip()] = pane_id.strip()

    missing_titles = sorted(EXPECTED_TMUX_PANE_TITLES.difference(pane_titles))
    if missing_titles:
        return False, "missing monitor panes: " + ", ".join(missing_titles)

    for pane_title in sorted(EXPECTED_TMUX_PANE_TITLES):
        pane_id = pane_titles[pane_title]
        pane_capture = _run(
            ["tmux", "capture-pane", "-p", "-t", pane_id],
            cwd=repo_root,
            timeout=10,
        )
        if pane_capture.returncode != 0:
            detail = (pane_capture.stderr or pane_capture.stdout or "").strip()
            if not detail:
                detail = f"tmux capture-pane exit {pane_capture.returncode}"
            return False, f"{pane_title} capture failed: {detail}"

        healthy, detail = _tmux_pane_has_live_content(pane_title, pane_capture.stdout)
        if not healthy:
            return False, f"{pane_title} missing live state content: {detail}"

    return True, f"session {session} active with pipeline monitor panes"


def _tmux_session_stable(
    repo_root: Path,
    session: str,
    *,
    checks: int = 2,
    delay_seconds: float = 0.5,
) -> tuple[bool, str]:
    last_detail = ""
    for index in range(checks):
        probe = _run(["tmux", "has-session", "-t", session], cwd=repo_root, timeout=10)
        if probe.returncode != 0:
            last_detail = (probe.stderr or probe.stdout or "").strip()
            if not last_detail:
                last_detail = f"tmux has-session exit {probe.returncode}"
            if index + 1 >= checks:
                return False, last_detail
        else:
            stable, detail = _tmux_monitor_signature(repo_root, session)
            last_detail = detail
            if stable and index + 1 >= checks:
                return True, detail
        if index + 1 < checks:
            time.sleep(delay_seconds)
    return False, last_detail or f"session {session} not stable"


def _ensure_tmux_monitor(repo_root: Path, session: str = TMUX_SESSION) -> CheckResult:
    monitor_script = repo_root / "tools" / "observability" / "pipeline_monitor.sh"
    if not monitor_script.exists():
        return CheckResult(
            "tmux_monitor",
            "FAIL",
            f"missing monitor script: {monitor_script}",
        )

    stable, detail = _tmux_session_stable(repo_root, session)
    if stable:
        return CheckResult(
            "tmux_monitor",
            "OK",
            detail,
        )

    start = _run(
        [str(monitor_script), "start", "--detach"],
        cwd=repo_root,
        timeout=30,
    )
    stable_after_start, stable_detail = _tmux_session_stable(repo_root, session)
    if start.returncode != 0:
        start_detail = (start.stderr or start.stdout or "").strip()
        if stable_after_start and stable_detail:
            start_detail = f"{start_detail}; tmux state={stable_detail}" if start_detail else stable_detail
        detail = start_detail or stable_detail or detail
        return CheckResult(
            "tmux_monitor",
            "FAIL",
            "failed closed after recovery attempt: " + detail.splitlines()[-1],
        )

    if stable_after_start:
        return CheckResult(
            "tmux_monitor",
            "OK",
            f"started; {stable_detail}",
        )

    detail = (start.stderr or start.stdout or "").strip() or stable_detail or detail
    return CheckResult(
        "tmux_monitor",
        "FAIL",
        "failed closed after recovery attempt: " + detail.splitlines()[-1],
    )


def _ensure_web_dashboard(repo_root: Path, port: int = WEB_PORT) -> CheckResult:
    web_script = repo_root / "tools" / "observability" / "pipeline_dashboard_web.py"
    if not web_script.exists():
        return CheckResult(
            "web_dashboard",
            "FAIL",
            f"missing dashboard script: {web_script}",
        )

    healthy, detail = _dashboard_health(port)
    if healthy:
        return CheckResult(
            "web_dashboard",
            "OK",
            detail,
        )

    try:
        with open(os.devnull, "wb") as sink:
            subprocess.Popen(
                [sys.executable, str(web_script), str(port)],
                cwd=str(repo_root),
                stdout=sink,
                stderr=sink,
                start_new_session=True,
            )
    except OSError as exc:
        return CheckResult(
            "web_dashboard",
            "FAIL",
            "failed closed after recovery attempt: " + f"{type(exc).__name__}: {exc}",
        )

    deadline = time.time() + 8
    last_detail = detail
    while time.time() < deadline:
        healthy, last_detail = _dashboard_health(port)
        if healthy:
            return CheckResult(
                "web_dashboard",
                "OK",
                last_detail.replace("serving", "started"),
            )
        time.sleep(0.5)

    return CheckResult(
        "web_dashboard",
        "FAIL",
        "failed closed after recovery attempt: " + last_detail,
    )


def gather_results(repo_root: Path, codex_home: Path) -> tuple[list[CheckResult], list[CheckResult]]:
    local_results: list[CheckResult]
    if codex_home.exists():
        local_results = [
            _audit_binary_guard(codex_home, repo_root),
            _check_session_start_hook(codex_home),
            _check_prompt_hook(codex_home),
            _check_default_rules(codex_home),
            _check_models_cache(codex_home),
        ]
    else:
        local_results = [
            CheckResult(
                "codex_home",
                "FAIL",
                f"missing required Codex-local startup state: {codex_home}",
            )
        ]

    observability_results = [
        _ensure_tmux_monitor(repo_root),
        _ensure_web_dashboard(repo_root),
    ]
    return local_results, observability_results


def main() -> int:
    repo_root = _repo_root()
    codex_home = _codex_home()
    local_results, observability_results = gather_results(repo_root, codex_home)

    print("RCX Codex startup state:")
    for result in local_results:
        print(f"  - {result.name}: {result.status} {result.detail}")

    print("RCX observability state:")
    for result in observability_results:
        print(f"  - {result.name}: {result.status} {result.detail}")

    failures = [result for result in [*local_results, *observability_results] if result.failed]
    if failures:
        print("FAIL: startup drift or observability issues detected.")
        return 1

    print("OK: Codex local startup state and observability checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
