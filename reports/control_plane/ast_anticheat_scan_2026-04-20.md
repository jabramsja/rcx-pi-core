Phase-A-Lock: LOCKED

# AST-based anti-cheat scan replaces grep for tests/ private-attr access — 2026-04-20

wave_id: ast-anticheat-scan-2026-04-20
phase: A
task_id: [NEXT-CODEX-POST-REDTEAM]
wave_class: L4_ENABLER
target_gate_id: G8

## Problem statement

`tools/audits/audit_fast.sh:113` (pre-push-fast) and `tools/audits/audit_all.sh:157` (audit_all) use a grep-based scan for private-attr access in `tests/`: `grep -RInE '\._[a-zA-Z0-9]+' tests/` followed by 6 `grep -v` allowlist filters. The scan is **docstring-blind**: a private-helper name mentioned inside a Python docstring (class-level or function-level `"""..."""`) matches the regex as plain text and fires a false positive — even though docstring contents are prose, not code.

Observed 2026-04-20 on PR #803 `routing-api-plus-write-gate` retry 1: I added a test-class docstring at `mu/tests/tools/test_executor_dispatch.py:8406-8411` reading "documents the deliberate divergence from `meta_bridge_supervisor._check_control_plane_path`'s tracked-file proof". The `_check_control_plane_path` substring matched the grep, pre-push-fast exited with `ERROR: Found private attr access`, and commit_executor bailed at Step 11 after Steps 1-10 succeeded (commit already local). Recovery required `git reset --soft HEAD~1` + tracker-note cleanup + rephrase docstring to cite by file:line (no underscore token) + relaunch. Captured as a learning entry in `.claude/rules/learning.md` on 2026-04-20.

This wave replaces the grep scan with an AST-based visitor that walks `ast.Attribute` nodes only. String-literal docstring contents are inherently invisible to the visitor (they are `ast.Constant` inside `ast.Expr`, never `ast.Attribute`), so the false-positive class is eliminated structurally. Preserves all 6 legacy allowlist behaviors. Zero regression expected on the currently-clean `tests/` tree.

## Scope (files in scope)

- `tools/checks/linters/check_private_attr_access.py` (new, ~115 LOC) — AST visitor that walks every Python file under `tests/`, collects `ast.Attribute` nodes whose `attr` starts with `_`, and filters out six allowlist cases (mirrors legacy grep): (1) `self._foo`, (2) `sys._getframe` / `sys._current_frames` by base-Name check, (3) lines containing `# ANTICHEAT_OK`, (4) lines containing `CONTRABAND_OK` when the attr is `_getframe`, (5) file allowlist `test_contraband_detection.py`, (6) `__pycache__` directory skipped during discovery. Dunder attributes (`__init__`, `__repr__`, etc.) are also skipped to match legacy grep behavior (the legacy pattern required `[a-zA-Z0-9]+` after the underscore, so `.__init__` was not matched either). Repo root discovery via walking to `.git` marker (same pattern as existing `check_underscore_imports.py`). Exit 0 clean / exit 1 with violations printed one per line.
- `tools/audits/audit_fast.sh` — replace lines 110-123 (the grep-chain block) with `python3 tools/checks/linters/check_private_attr_access.py || exit 1`. Banner text updated to "(AST-based)".
- `tools/audits/audit_all.sh` — replace lines 155-168 (the grep-chain block) with the same Python invocation + a comment block documenting the AST/docstring-aware rationale.
- `mu/tests/tools/test_check_private_attr_access.py` (new, 15 test cases) — 3 docstring false-positive elimination tests (class, function, module docstrings), 2 real-violation detection tests, 5 allowlist parity tests (`self._`, `sys._getframe`, `# ANTICHEAT_OK`, `CONTRABAND_OK + _getframe`, dunder), 1 file-allowlist test, 2 `scan()` integration tests (clean + dirty fixture trees; `__pycache__` skip), 2 `main()` entrypoint tests (exit 0 clean / exit 1 violation with printed output). Pattern-mirrors the existing `mu/tests/tools/test_check_underscore_imports.py`.
- `mu/tests/docs/test_growth_caps.py` — `CAP_TEST_FILES` 111→112 (+1 for `test_check_private_attr_access.py`) and `CAP_TOOL_SCRIPTS` 41→42 (+1 for `check_private_attr_access.py`). Annotated in the comment strings with "+1 for ... (AST-anti-cheat wave, standing pipeline-bug-fix authorization 2026-04-20)". Precedent for bumping both caps in a single pipeline-hardening wave: the 2026-04-17 PIPELINE-AGENT-PAGER fold-in bumped both for pager-wave adds.

## Constraints (out of scope)

- Any change to the other 4 anti-cheat scans (`no underscored imports from rcx_pi`, AST police, seed police, JS test theater) — they are separately checked and already AST-based where appropriate.
- Any change to the grep scans in `audit_all.sh` Stages 2-4 or beyond Stage 5 item 1 — this wave touches exactly one gate.
- Generalizing the visitor to scan `mu/` non-test code — the legacy grep scanned only `tests/`; this wave preserves that scope.
- Removing the `test_contraband_detection.py` file-level allowlist — it is kept for forward-compat even though the AST visitor no longer requires it (the file's docstring citations would be invisible anyway, but a code-level `_getframe` test reference is still in-scope if it appears).
- Adding a `--json` report mode, an `--autofix` mode, or any CLI flag beyond an optional single positional `<repo_root>` arg (matches `check_underscore_imports.py` style).
- Refactoring `check_underscore_imports.py` — it already AST-based and correct; left unchanged.

## Work items

1. Create `tools/checks/linters/check_private_attr_access.py` per the Scope description. Make executable (`chmod +x`).
2. Edit `tools/audits/audit_fast.sh:110-123` to replace the grep chain with the Python invocation. Keep the `==` banner header and the `-- no private attr access in tests/` sub-banner, update the sub-banner to `(AST-based)`.
3. Edit `tools/audits/audit_all.sh:155-168` similarly, with an inline comment block explaining the AST/docstring-aware replacement.
4. Create `mu/tests/tools/test_check_private_attr_access.py` with the 15 tests per Scope. Pattern-follow `mu/tests/tools/test_check_underscore_imports.py` for the `importlib.util.spec_from_file_location` module-loading style and the `tempfile.NamedTemporaryFile` fixture pattern.
5. Edit `mu/tests/docs/test_growth_caps.py` to bump `CAP_TEST_FILES` 111→112 and `CAP_TOOL_SCRIPTS` 41→42, with wave-attribution comments.

## Stop conditions

- Any change to a file outside the 5-file scope → HALT, escalate.
- Linter exit >0 on the currently-clean `tests/` tree → HALT, diagnose (unexpected regression since the tree passes the legacy grep today per PR #803 post-fix).
- Plan body > 100 lines → HALT, re-scope.
- Founder amends directive before Phase B → HALT, re-plan.

## Acceptance criteria

- `python3 tools/checks/linters/check_private_attr_access.py` exits 0 on the current `tests/` tree (demonstrable by direct invocation from the repo root after apply).
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_check_private_attr_access.py` passes with 15 test cases green.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_growth_caps.py` passes with 3 test cases green (test-file count, tool-script count, core-docs count all within the bumped caps).
- The docstring-false-positive regression is proved eliminated: `test_private_attr_inside_class_docstring_is_not_flagged`, `test_private_attr_inside_function_docstring_is_not_flagged`, `test_private_attr_inside_module_docstring_is_not_flagged` all green — a docstring citing `meta_bridge_supervisor._check_control_plane_path` (exactly the 2026-04-20 failing input) returns zero violations.
- All 6 legacy allowlist behaviors preserved by green parametrized tests: `self._` skipped, `sys._getframe` skipped, `# ANTICHEAT_OK` lines skipped, `CONTRABAND_OK + _getframe` skipped, `test_contraband_detection.py` file-allowlisted, `__pycache__` directory skipped.
- `bash tools/hooks/pre-push-fast` on the current HEAD completes its anti-cheat scan step with `-- no private attr access in tests/ (AST-based)` banner + `OK`, not the legacy `ERROR: Found private attr access` line.

## Grounding / Authorization

- **Governing tracked packet:** `reports/control_plane/ast_anticheat_scan_2026-04-20.md` (this file). Third sibling narrow control-surface pipeline-hardening wave this session — precedents landed this session: PR #802 `supervisor-prompt-override-2026-04-20`, PR #803 `routing-api-plus-write-gate-2026-04-20`, PR #804 `pager-session-id-autowrite-2026-04-20`. All used the same anchor + FOUNDER_OVERRIDE pattern.
- **`task_id` is a procedural Gate 8 anchor.** `meta_bridge_supervisor.check_tasks_authorization` at `meta_bridge_supervisor.py:559-600` accepts any bracketed token matching an active NOW/NEXT entry. `[NEXT-CODEX-POST-REDTEAM]` at TASKS.md:241 is UNPARKED and founder-authorized. The 3 precedent waves cited above all used the same anchor for narrow control-surface pipeline-hardening work.
- **Direct learning trigger:** `.claude/rules/learning.md` 2026-04-20 entry `audit_fast.sh anti-cheat scan grep -RInE private attr access in tests docstring false positive` (top of log) documents the exact bug this wave closes. The "Structural fix candidate" note in that entry names the AST-based scanner as the mechanization target — this wave executes it.
- **Founder in-session autonomous directive 2026-04-20**: "standing automated authorization is if pipeline fails, to do structural fix, and add to either API, recovery or other needed way for mechanical if fails again. Also, after this wave, automatically do next valuable highest roi wave autonomously. If override needed give override." — explicit autonomy for this wave + authorization for the growth-cap bump.
- **Standing pipeline-bug-fix authorization** per memory `feedback_autonomous_executor_fix.md` (founder, 2026-04-06): autonomous authority for mechanical executor/governance fixes.
- **`FOUNDER_OVERRIDE:ast-anticheat-scan-2026-04-20`** — wave-specific single-use token, auto-appended by the `founder_override_token` mechanization landed in PR #803. Third self-test of the mechanization in-session.
- **Lane: control-surface (enforcement hardening)** — same lane as [ANTI-DRIFT-ENFORCEMENT] (TASKS.md:207-212, CLOSED 2026-04-16; this wave's linter is a structural improvement on the anti-cheat family of checks that bucket governed).
- **Bootstrap classification: NOT bootstrap.** Touches `tools/checks/linters/` (new AST tool) + `tools/audits/*.sh` (invocation updates) + `mu/tests/tools/` (tests) + `mu/tests/docs/test_growth_caps.py` (cap bumps). No substrate code; no implementer/bridge/adapter surface changed.
