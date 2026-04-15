from __future__ import annotations

import http.server
import json
import subprocess
import threading

import pytest

from tests.repo_root import REPO_ROOT
from mu.tests.tools.module_loader import load_module


_tool_path = REPO_ROOT / "tools" / "session" / "check_codex_startup_state.py"
startup_mod = load_module("check_codex_startup_state", _tool_path)
_snapshot_tool_path = REPO_ROOT / "tools" / "session" / "founder_learning_snapshot.py"
snapshot_mod = load_module("founder_learning_snapshot", _snapshot_tool_path)


def test_founder_learning_snapshot_preserves_fixed_entry_dates(tmp_path):
    learning_md = tmp_path / "learning.md"
    learning_md.write_text(
        "- [2026-04-15] FIXED | fingerprint: `abc` | action: `done`\n",
        encoding="utf-8",
    )

    entries = snapshot_mod._load_learning_entries(learning_md)  # ANTICHEAT_OK: tool unit test
    dated = [entry for entry in entries if entry.get("date")]
    dated.sort(
        key=lambda entry: (entry.get("date", ""), entry.get("category", "")),
        reverse=True,
    )

    assert entries == [
        {
            "date": "2026-04-15",
            "category": "FIXED",
            "fingerprint": "abc",
        }
    ]
    assert dated[0]["date"] == "2026-04-15"


def test_run_returns_timeout_result_instead_of_raising(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["python3", "-c", "import time; time.sleep(2)"],
            timeout=1,
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr(startup_mod.subprocess, "run", fake_run)

    result = startup_mod._run(["python3", "-c", "pass"], timeout=1)  # ANTICHEAT_OK: tool unit test

    assert result.returncode == 124
    assert result.stdout == "partial stdout"
    assert "TimeoutExpired" in result.stderr
    assert "partial stderr" in result.stderr


def test_binary_guard_version_drift_fails(monkeypatch, tmp_path):
    codex_home = tmp_path / ".codex"
    bin_dir = codex_home / "bin"
    bin_dir.mkdir(parents=True)
    guard = bin_dir / "codex-binary-guard"
    guard.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    monkeypatch.setattr(startup_mod.os, "access", lambda path, mode: path == guard)
    monkeypatch.setattr(
        startup_mod,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            json.dumps(
                {
                    "version": "0.120.0",
                    "version_changed_since_patch": True,
                    "last_patched": {"version": "0.119.0"},
                    "overall_status": "patched",
                }
            ),
            "",
        ),
    )

    result = startup_mod._audit_binary_guard(codex_home, tmp_path)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "version drift" in result.detail


def test_models_cache_canaries_fail(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    models_cache = codex_home / "models_cache.json"
    models_cache.write_text(
        json.dumps(
            {
                "system": "warm, encouraging, and conversational; "
                "collaboration is a kind of quiet joy",
            }
        ),
        encoding="utf-8",
    )

    result = startup_mod._check_models_cache(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "stale friendly-persona canaries present" in result.detail


def test_models_cache_allows_vendor_personality_friendly_lane(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    models_cache = codex_home / "models_cache.json"
    models_cache.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "slug": "gpt-5.4",
                        "base_instructions": "You are a deeply pragmatic, effective software engineer.",
                        "instructions_variables": {
                            "personality_default": "",
                            "personality_friendly": (
                                "You optimize for team morale and being a supportive teammate as much as code quality. "
                                "Your voice is warm, encouraging, and conversational."
                            ),
                            "personality_pragmatic": "You are a deeply pragmatic, effective software engineer.",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = startup_mod._check_models_cache(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "OK"
    assert "personality_friendly variants" in result.detail


def test_models_cache_invalid_json_fails_closed(tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    models_cache = codex_home / "models_cache.json"
    models_cache.write_text("{not valid json", encoding="utf-8")

    result = startup_mod._check_models_cache(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "invalid JSON" in result.detail


def test_prompt_hook_disabled_canary_is_accepted(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "def main():\n"
        "    # Disabled because UserPromptSubmit output cannot currently be hidden in Codex.\n"
        "    return 0\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"
    assert "disabled intentionally" in result.detail


def test_session_start_hook_missing_canaries_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        "print('codex-rcx-preflight only')\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "missing canaries" in result.detail


def test_session_start_hook_comment_only_canaries_fail(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        "# codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md\n"
        "print('noop')\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert (
        "code-bound canaries" in result.detail
        or "SessionStart" in result.detail
        or "unsafe top-level execution" in result.detail
    )


def test_session_start_hook_valid_sessionstart_payload_is_accepted(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    repo_root = tmp_path / "repo"
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(repo_root)!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(startup_mod, "_repo_root", lambda: repo_root)
    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"


def test_session_start_hook_requires_target_repo_anchor_for_linked_worktree(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    target_repo = tmp_path / "canonical-repo"
    hook_path = hook_dir / "session_start_rcx_preflight.py"
    hook_path.write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(target_repo)!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(startup_mod, "_repo_root", lambda: target_repo)
    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "OK"
    assert startup_mod._session_start_target_repo(hook_path.read_text(encoding="utf-8")) == target_repo  # ANTICHEAT_OK: tool unit test


def test_session_start_hook_accepts_primary_checkout_anchor_from_git_common_dir(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    primary_repo = tmp_path / "primary-checkout"
    linked_worktree = tmp_path / "linked-worktree"
    common_dir = primary_repo / ".git"
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(primary_repo)!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(startup_mod, "_repo_root", lambda: linked_worktree)

    def fake_run(cmd, *, cwd=None, timeout=60):
        if cmd == ["git", "rev-parse", "--git-common-dir"]:
            return subprocess.CompletedProcess(cmd, 0, f"{common_dir}\n", "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(startup_mod, "_run", fake_run)

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "OK"


def test_session_start_hook_wrong_target_repo_fails(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    expected_repo = tmp_path / "expected-repo"
    wrong_repo = tmp_path / "wrong-repo"
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(wrong_repo)!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(startup_mod, "_repo_root", lambda: expected_repo)
    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "target repo anchor mismatch" in result.detail


def test_session_start_hook_payload_without_emit_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        "def main():\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md'}}\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "emission structure" in result.detail


def test_session_start_hook_payload_dumped_off_stdout_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "def main():\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md'}}\n"
        "    json.dump(payload, open('/dev/null', 'w'))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "emission structure" in result.detail


def test_session_start_hook_dead_payload_constant_does_not_count(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, sys\n"
        "DUMMY = {'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md'}}\n"
        "def _emit(message):\n"
        "    json.dump({'systemMessage': message}, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    _emit('hello')\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "emission structure" in result.detail


def test_session_start_hook_wrong_emitted_payload_fails_even_with_dead_canaries(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, sys\n"
        "DUMMY = {'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md'}}\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    lines = ['WRONG PAYLOAD']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "missing emitted payload canaries" in result.detail


def test_session_start_hook_emit_must_thread_argument_into_additional_context(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'WRONG PAYLOAD'}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "emission structure" in result.detail


def test_session_start_hook_top_level_exit_before_main_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "raise SystemExit(7)\n"
        "def main():\n"
        "    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md'}}))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "unsafe top-level execution" in result.detail


def test_session_start_hook_top_level_assign_call_before_main_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "SIDE_EFFECT = os.system('echo side-effect')\n"
        "def main():\n"
        "    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md'}}))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "unsafe top-level execution" in result.detail


def test_session_start_hook_main_raise_before_emit_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    raise SystemExit(7)\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "emission structure" in result.detail


def test_session_start_hook_nonzero_after_emit_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 7\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "emission structure" in result.detail


def test_session_start_hook_extra_stdout_noise_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    print('noise')\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "emission structure" in result.detail


def test_session_start_hook_unapproved_env_skip_before_emit_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, os, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    if os.environ.get('RCX_SKIP_EMIT'):\n"
        "        return 0\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "unapproved pre-emit environment gates" in result.detail
    assert "RCX_SKIP_EMIT" in result.detail


def test_session_start_hook_allows_known_disable_env_gate(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    repo_root = tmp_path / "repo"
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(repo_root)!r}\n"
        "import json, os, sys\n"
        "def _emit(additional_context):\n"
        "    payload = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': additional_context}}\n"
        "    json.dump(payload, sys.stdout)\n"
        "    sys.stdout.write('\\n')\n"
        "def main():\n"
        "    if os.environ.get('CODEX_RCX_PREFLIGHT_DISABLE') == '1':\n"
        "        return 0\n"
        "    sys.stdin.read()\n"
        "    lines = ['codex-rcx-preflight codex-binary-guard rcx_codex_persona_hardening.md codex_binary_patch_surface.md']\n"
        "    _emit('\\n'.join(lines))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(startup_mod, "_repo_root", lambda: repo_root)

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "OK"


def test_session_start_hook_does_not_execute_main_side_effects_during_audit(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    marker = tmp_path / "side_effect_marker"
    (hook_dir / "session_start_rcx_preflight.py").write_text(
        "#!/usr/bin/env python3\n"
        f"TARGET_REPO_RAW = {str(tmp_path / 'repo')!r}\n"
        "import json, os, sys\n"
        "def main():\n"
        f"    os.system('touch {marker}')\n"
        "    sys.stdin.read()\n"
        "    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', "
        "'additionalContext': 'codex-rcx-preflight codex-binary-guard "
        "rcx_codex_persona_hardening.md codex_binary_patch_surface.md'}}))\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_session_start_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert not marker.exists()


def test_prompt_hook_requires_anchor_canaries_when_enabled(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "PROMPT = 'FOUNDER_SESSION_BOOTSTRAP.md only'\n"
        "def main():\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "missing code-bound RCX protocol canaries" in result.detail


def test_prompt_hook_enabled_with_code_bound_canaries_is_accepted(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "PROMPT_CONTEXT = 'FOUNDER_SESSION_BOOTSTRAP.md repo-tracked docs pipeline path'\n"
        "def main():\n"
        "    _ = PROMPT_CONTEXT\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"


def test_prompt_hook_enabled_nonzero_execution_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "PROMPT = 'FOUNDER_SESSION_BOOTSTRAP.md repo-tracked docs pipeline path'\n"
        "def main():\n"
        "    return 7\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "return 0 or None" in result.detail


def test_prompt_hook_enabled_output_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "PROMPT = 'FOUNDER_SESSION_BOOTSTRAP.md repo-tracked docs pipeline path'\n"
        "def main():\n"
        "    _ = PROMPT\n"
        "    print('visible output')\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "active prompt hook emitted output" in result.detail


def test_prompt_hook_enabled_comment_only_canaries_fail(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "# FOUNDER_SESSION_BOOTSTRAP.md repo-tracked docs pipeline path\n"
        "def main():\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "missing code-bound RCX protocol canaries" in result.detail


def test_prompt_hook_enabled_top_level_side_effect_fails_without_execution(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    marker = tmp_path / "prompt_enabled_side_effect_marker"
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "PROMPT = 'FOUNDER_SESSION_BOOTSTRAP.md repo-tracked docs pipeline path'\n"
        f"Path({str(marker)!r}).write_text('side effect', encoding='utf-8')\n"
        "def main():\n"
        "    _ = PROMPT\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "unsafe top-level execution" in result.detail
    assert not marker.exists()


def test_prompt_hook_disabled_comment_with_active_output_fails(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "def main():\n"
        "    # Disabled because UserPromptSubmit output cannot currently be hidden in Codex.\n"
        "    print('still active')\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "active code" in result.detail or "emitted output" in result.detail


def test_prompt_hook_disabled_top_level_side_effect_fails_without_execution(tmp_path):
    codex_home = tmp_path / ".codex"
    hook_dir = codex_home / "hooks"
    hook_dir.mkdir(parents=True)
    marker = tmp_path / "prompt_side_effect_marker"
    (hook_dir / "user_prompt_submit_rcx_identity.py").write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('side effect', encoding='utf-8')\n"
        "def main():\n"
        "    # Disabled because UserPromptSubmit output cannot currently be hidden in Codex.\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = startup_mod._check_prompt_hook(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "unsafe top-level execution" in result.detail
    assert not marker.exists()


@pytest.mark.parametrize(
    ("rule", "expected_fragment"),
    [
        ('prefix_rule(pattern=["git", "commit"], decision="allow")\n', "git commit"),
        ('prefix_rule(pattern=["git", "branch"], decision="allow")\n', "git branch"),
        ('prefix_rule(pattern=["git", "fetch", "origin"], decision="allow")\n', "git fetch origin"),
        (
            'prefix_rule(pattern=["/usr/bin/env", "git", "fetch", "origin"], decision="allow")\n',
            "git fetch origin",
        ),
        ('prefix_rule(pattern=["git", "reset", "--hard"], decision="allow")\n', "git reset --hard"),
        (
            'prefix_rule(pattern=["git", "restore", "--source", "HEAD", "foo"], decision="allow")\n',
            "git restore --source HEAD foo",
        ),
        ('prefix_rule(pattern=["git", "merge", "main"], decision="allow")\n', "git merge main"),
        ('prefix_rule(pattern=["git", "rebase", "main"], decision="allow")\n', "git rebase main"),
    ],
)
def test_default_rules_reject_unsafe_manual_git_allows(tmp_path, rule, expected_fragment):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert expected_fragment in result.detail


def test_default_rules_reject_multiline_manual_git_fetch_allow(tmp_path):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(
        'prefix_rule(\n  pattern=["git", "fetch", "origin"],\n  decision="allow"\n)\n',
        encoding="utf-8",
    )

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "git fetch origin" in result.detail


@pytest.mark.parametrize(
    ("rule", "expected_fragment"),
    [
        (
            'ALLOW = "allow"\n'
            'FETCH_RULE = ["git", "fetch", "origin"]\n'
            'prefix_rule(pattern=FETCH_RULE, decision=ALLOW)\n',
            "git fetch origin",
        ),
        (
            'ALLOW = "allow"\n'
            'BROAD_PYTHON = ["/usr/bin/env", "python3"]\n'
            'prefix_rule(pattern=BROAD_PYTHON, decision=ALLOW)\n',
            "python3 <broad interpreter allow>",
        ),
        (
            'ALLOW = "allow"\n'
            'RULE = ["python3", "evil.py"]\n'
            'ALIAS = RULE\n'
            'prefix_rule(pattern=ALIAS, decision=ALLOW)\n',
            "python3 <script-backed interpreter allow>",
        ),
    ],
)
def test_default_rules_reject_identifier_backed_allow_aliases(tmp_path, rule, expected_fragment):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert expected_fragment in result.detail


@pytest.mark.parametrize(
    ("rule", "expected_fragment"),
    [
        (
            'prefix_rule(pattern=["python3", "evil.py"], decision="allow")\n',
            "python3 <script-backed interpreter allow>",
        ),
        (
            'prefix_rule(pattern=["/usr/bin/env", "python3", "evil.py"], decision="allow")\n',
            "python3 <script-backed interpreter allow>",
        ),
        (
            'prefix_rule(pattern=["bash", "script.sh"], decision="allow")\n',
            "bash <script-backed shell allow>",
        ),
        (
            'prefix_rule(pattern=["/usr/bin/env", "bash", "script.sh"], decision="allow")\n',
            "bash <script-backed shell allow>",
        ),
    ],
)
def test_default_rules_reject_script_backed_execution_allows(tmp_path, rule, expected_fragment):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert expected_fragment in result.detail


@pytest.mark.parametrize(
    ("rule", "expected_fragment"),
    [
        ('prefix_rule(pattern=["python3"], decision="allow")\n', "python3 <broad interpreter allow>"),
        ('prefix_rule(pattern=["python3", "-c"], decision="allow")\n', "python3 <broad interpreter allow>"),
        (
            'prefix_rule(pattern=["/usr/bin/python3"], decision="allow")\n',
            "python3 <broad interpreter allow>",
        ),
        (
            'prefix_rule(pattern=["/usr/bin/env", "python3"], decision="allow")\n',
            "python3 <broad interpreter allow>",
        ),
        (
            'prefix_rule(pattern=["/usr/bin/env", "python3", "-c"], decision="allow")\n',
            "python3 <broad interpreter allow>",
        ),
    ],
)
def test_default_rules_reject_broad_interpreter_allows(tmp_path, rule, expected_fragment):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert expected_fragment in result.detail


def test_default_rules_reject_multiline_broad_interpreter_allow(tmp_path):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(
        'prefix_rule(\n  pattern=["/usr/bin/env", "python3"],\n  decision="allow"\n)\n',
        encoding="utf-8",
    )

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "python3 <broad interpreter allow>" in result.detail


@pytest.mark.parametrize(
    "rule",
    [
        'prefix_rule(pattern=["python3", "-m", "json.tool"], decision="allow")\n',
        'prefix_rule(pattern=["node", "-e", "console.log(1)"], decision="allow")\n',
        'prefix_rule(pattern=["node", "-v"], decision="allow")\n',
        'prefix_rule(pattern=["node", "mu/host/js/eval_step.js", "--json-api", \'{"action":"step_kernel_meta"}\'], decision="allow")\n',
        'prefix_rule(pattern=["python3", "mu/tools/executors/executor_dispatch.py", "phase-b"], decision="allow")\n',
    ],
)
def test_default_rules_accept_fully_specified_interpreter_invocations(tmp_path, rule):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"
    assert "no disallowed manual git write/fetch allow rules detected" in result.detail


def test_default_rules_accept_shell_wrapped_fixed_repo_script_invocation(tmp_path):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(
        'prefix_rule(pattern=["/bin/bash", "-lc", "node mu/host/js/eval_step.js 2>&1 | tail -3"], decision="allow")\n',
        encoding="utf-8",
    )

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test

    assert result.status == "OK"
    assert "no disallowed manual git write/fetch allow rules detected" in result.detail


def test_default_rules_accept_read_only_git_branch_listing(tmp_path):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(
        'prefix_rule(pattern=["git", "branch", "--all", "--list", "*main*", "*dev*"], decision="allow")\n',
        encoding="utf-8",
    )

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"
    assert "no disallowed manual git write/fetch allow rules detected" in result.detail


def test_default_rules_accept_multiline_read_only_git_branch_listing(tmp_path):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(
        'prefix_rule(\n  pattern=["git", "branch", "--all", "--list", "*main*", "*dev*"],\n  decision="allow"\n)\n',
        encoding="utf-8",
    )

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"
    assert "no disallowed manual git write/fetch allow rules detected" in result.detail


@pytest.mark.parametrize(
    ("rule", "expected_fragment"),
    [
        (
            'prefix_rule(pattern=["/bin/bash", "-lc", "git reset --hard"], decision="allow")\n',
            "git reset --hard",
        ),
        (
            'prefix_rule(pattern=["/bin/bash", "-lc", "git fetch origin && echo ok"], decision="allow")\n',
            "git fetch origin",
        ),
        (
            'prefix_rule(pattern=["/bin/bash", "-lc", "/usr/bin/env git fetch origin"], decision="allow")\n',
            "git fetch origin",
        ),
        (
            'prefix_rule(pattern=["/usr/bin/env", "bash", "-lc", "git fetch origin"], decision="allow")\n',
            "git fetch origin",
        ),
    ],
)
def test_default_rules_reject_unsafe_shell_wrapped_git_allows(tmp_path, rule, expected_fragment):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert expected_fragment in result.detail


@pytest.mark.parametrize(
    ("rule", "expected_fragment"),
    [
        (
            'prefix_rule(pattern=["/bin/bash", "-lc", "git branch --all\\ngit fetch origin"], decision="allow")\n',
            "git fetch origin",
        ),
        (
            'prefix_rule(pattern=["/bin/bash", "-ic", "git fetch origin"], decision="allow")\n',
            "git fetch origin",
        ),
        (
            'prefix_rule(pattern=["/usr/bin/env", "-S", "bash -lc", "git fetch origin"], decision="allow")\n',
            "git fetch origin",
        ),
    ],
)
def test_default_rules_reject_shell_wrapped_git_variants_with_newlines_and_env_split(
    tmp_path, rule, expected_fragment
):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert expected_fragment in result.detail


@pytest.mark.parametrize(
    "rule",
    [
        'prefix_rule(pattern=["/bin/bash", "-lc", "/usr/bin/env python3"], decision="allow")\n',
        'prefix_rule(pattern=["/bin/bash", "-lc", "python3 -c"], decision="allow")\n',
        'prefix_rule(pattern=["/bin/bash", "-lc", "/usr/bin/env python3 -c"], decision="allow")\n',
        'prefix_rule(pattern=["/usr/bin/env", "bash", "-lc", "python3"], decision="allow")\n',
    ],
)
def test_default_rules_reject_shell_wrapped_broad_env_python_allow(tmp_path, rule):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "python3 <broad interpreter allow>" in result.detail


@pytest.mark.parametrize(
    "rule",
    [
        'prefix_rule(pattern=["/bin/bash", "-ic", "python3"], decision="allow")\n',
        'prefix_rule(pattern=["/usr/bin/env", "-S", "bash -lc", "python3"], decision="allow")\n',
    ],
)
def test_default_rules_reject_shell_wrapped_broad_interpreter_variants(tmp_path, rule):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(rule, encoding="utf-8")

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "python3 <broad interpreter allow>" in result.detail


def test_default_rules_accept_safe_shell_wrapped_git_branch_listing(tmp_path):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(
        'prefix_rule(pattern=["/bin/bash", "-lc", "git branch --all --list \'*main*\' \'*dev*\'"], decision="allow")\n',
        encoding="utf-8",
    )

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"
    assert "no disallowed manual git write/fetch allow rules detected" in result.detail


def test_default_rules_accept_safe_env_split_shell_wrapped_git_branch_listing(tmp_path):
    codex_home = tmp_path / ".codex"
    rules_dir = codex_home / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "default.rules").write_text(
        'prefix_rule(pattern=["/usr/bin/env", "-S", "bash -lc", "git branch --all --list \'*main*\' \'*dev*\'"], decision="allow")\n',
        encoding="utf-8",
    )

    result = startup_mod._check_default_rules(codex_home)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"
    assert "no disallowed manual git write/fetch allow rules detected" in result.detail


def test_dashboard_health_rejects_unrelated_json_service():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        healthy, detail = startup_mod._dashboard_health(server.server_address[1])  # ANTICHEAT_OK: tool unit test
        assert healthy is False
        assert "missing keys" in detail
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_web_dashboard_recovery_starts_requested_port(monkeypatch, tmp_path):
    web_script = tmp_path / "tools" / "observability" / "pipeline_dashboard_web.py"
    web_script.parent.mkdir(parents=True)
    web_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    health_calls: list[int] = []
    health_results = iter(
        [
            (False, "http://127.0.0.1:8123/api/state unavailable: URLError"),
            (True, "serving RCX dashboard on http://127.0.0.1:8123/api/state"),
        ]
    )

    def fake_health(port: int):
        health_calls.append(port)
        return next(health_results)

    popen_calls: list[list[str]] = []

    class DummyProcess:
        pass

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd)
        return DummyProcess()

    monkeypatch.setattr(startup_mod, "_dashboard_health", fake_health)
    monkeypatch.setattr(startup_mod.subprocess, "Popen", fake_popen)

    result = startup_mod._ensure_web_dashboard(tmp_path, port=8123)  # ANTICHEAT_OK: tool unit test

    assert health_calls == [8123, 8123]
    assert popen_calls == [
        [startup_mod.sys.executable, str(web_script), "8123"]
    ]
    assert result.status == "OK"
    assert result.detail == "started RCX dashboard on http://127.0.0.1:8123/api/state"


def test_web_dashboard_recovery_spawn_failure_fails_closed(monkeypatch, tmp_path):
    web_script = tmp_path / "tools" / "observability" / "pipeline_dashboard_web.py"
    web_script.parent.mkdir(parents=True)
    web_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    monkeypatch.setattr(
        startup_mod,
        "_dashboard_health",
        lambda port: (False, f"http://127.0.0.1:{port}/api/state unavailable: URLError"),
    )
    monkeypatch.setattr(
        startup_mod.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("spawn failed")),
    )

    result = startup_mod._ensure_web_dashboard(tmp_path, port=8123)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "failed closed after recovery attempt" in result.detail
    assert "OSError: spawn failed" in result.detail


def test_tmux_monitor_signature_accepts_live_pane_content(monkeypatch, tmp_path):
    pane_listing = "\n".join(
        [
            "%1\tPANE 1 · LIVE PIPELINE LOG",
            "%2\tPANE 2 · REVIEW FINDINGS",
            "%3\tPANE 3 · PLAIN-ENGLISH STATUS",
            "%4\tPANE 4 · SESSION TIMELINE",
        ]
    )
    pane_bodies = {
        "%1": "Pane 1: live pipeline log\nNo active pipeline log in the last 1 hour.\nWorktree: /tmp/repo\n",
        "%2": "Pane 2: review findings\nDecision: GO  0B 1NB\nMeaning: Ready to continue.\n",
        "%3": "Pane 3: plain-English status\nBRIDGE\nNo pipeline step is running. Waiting for the next wave.\n",
        "%4": "Pane 4: session timeline\n12:34  ← idle\nTypical durations:\n",
    }

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["tmux", "list-panes"]:
            return subprocess.CompletedProcess(cmd, 0, pane_listing, "")
        if cmd[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(cmd, 0, pane_bodies[cmd[-1]], "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(startup_mod, "_run", fake_run)

    healthy, detail = startup_mod._tmux_monitor_signature(tmp_path, startup_mod.TMUX_SESSION)  # ANTICHEAT_OK: tool unit test

    assert healthy is True
    assert "pipeline monitor panes" in detail


@pytest.mark.parametrize(
    ("pane_body", "detail_fragment"),
    [
        (
            "bash: /tmp/rcx_log_watcher.sh: No such file or directory\n",
            "bash: /tmp/rcx_log_watcher.sh: No such file or directory",
        ),
        (
            "tail: cannot open '/tmp/missing.log' for reading: No such file or directory\n",
            "tail: cannot open '/tmp/missing.log' for reading: No such file or directory",
        ),
    ],
)
def test_tmux_pane_1_rejects_monitor_error_only_output(pane_body, detail_fragment):
    healthy, detail = startup_mod._tmux_pane_has_live_content(  # ANTICHEAT_OK: tool unit test
        "PANE 1 · LIVE PIPELINE LOG",
        pane_body,
    )

    assert healthy is False
    assert "only monitor error output" in detail
    assert detail_fragment in detail


def test_tmux_monitor_signature_rejects_pane_1_monitor_errors(monkeypatch, tmp_path):
    pane_listing = "\n".join(
        [
            "%1\tPANE 1 · LIVE PIPELINE LOG",
            "%2\tPANE 2 · REVIEW FINDINGS",
            "%3\tPANE 3 · PLAIN-ENGLISH STATUS",
            "%4\tPANE 4 · SESSION TIMELINE",
        ]
    )
    pane_bodies = {
        "%1": "bash: /tmp/rcx_log_watcher.sh: No such file or directory\n",
        "%2": "Pane 2: review findings\nDecision: GO  0B 1NB\nMeaning: Ready to continue.\n",
        "%3": "Pane 3: plain-English status\nBRIDGE\nNo pipeline step is running. Waiting for the next wave.\n",
        "%4": "Pane 4: session timeline\n12:34  ← idle\nTypical durations:\n",
    }

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["tmux", "list-panes"]:
            return subprocess.CompletedProcess(cmd, 0, pane_listing, "")
        if cmd[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(cmd, 0, pane_bodies[cmd[-1]], "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(startup_mod, "_run", fake_run)

    healthy, detail = startup_mod._tmux_monitor_signature(tmp_path, startup_mod.TMUX_SESSION)  # ANTICHEAT_OK: tool unit test

    assert healthy is False
    assert "PANE 1 · LIVE PIPELINE LOG missing live state content" in detail
    assert "only monitor error output" in detail


def test_tmux_session_stable_rejects_session_without_monitor_panes(monkeypatch, tmp_path):
    calls = iter(
        [
            subprocess.CompletedProcess(["tmux", "has-session"], 0, "", ""),
            subprocess.CompletedProcess(
                ["tmux", "list-panes"],
                0,
                "%1\tPANE 1 · LIVE PIPELINE LOG\n",
                "",
            ),
        ]
    )
    monkeypatch.setattr(startup_mod, "_run", lambda *args, **kwargs: next(calls))

    stable, detail = startup_mod._tmux_session_stable(  # ANTICHEAT_OK: tool unit test
        tmp_path,
        startup_mod.TMUX_SESSION,
        checks=1,
    )

    assert stable is False
    assert "missing monitor panes" in detail


def test_tmux_session_stable_rejects_degraded_pane_content(monkeypatch, tmp_path):
    pane_listing = "\n".join(
        [
            "%1\tPANE 1 · LIVE PIPELINE LOG",
            "%2\tPANE 2 · REVIEW FINDINGS",
            "%3\tPANE 3 · PLAIN-ENGLISH STATUS",
            "%4\tPANE 4 · SESSION TIMELINE",
        ]
    )
    pane_bodies = {
        "%1": "Pane 1: live pipeline log\nNo active pipeline log in the last 1 hour.\nWorktree: /tmp/repo\n",
        "%2": (
            "Pane 2: review findings\n"
            "This pane shows the latest reviewer decision and why it passed or failed.\n"
            "Watching: feature/startup\n"
            "Worktree: /tmp/repo\n"
        ),
        "%3": "Pane 3: plain-English status\nBRIDGE\nNobody is working right now.\n",
        "%4": "Pane 4: session timeline\n12:34  ← idle\nTypical durations:\n",
    }

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["tmux", "has-session", "-t"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["tmux", "list-panes"]:
            return subprocess.CompletedProcess(cmd, 0, pane_listing, "")
        if cmd[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(cmd, 0, pane_bodies[cmd[-1]], "")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(startup_mod, "_run", fake_run)

    stable, detail = startup_mod._tmux_session_stable(  # ANTICHEAT_OK: tool unit test
        tmp_path,
        startup_mod.TMUX_SESSION,
        checks=1,
    )

    assert stable is False
    assert "PANE 2 · REVIEW FINDINGS missing live state content" in detail


def test_tmux_monitor_requires_monitor_script_even_for_existing_session(monkeypatch, tmp_path):
    monkeypatch.setattr(
        startup_mod,
        "_tmux_session_stable",
        lambda *args, **kwargs: (True, "session rcx-pipeline active with pipeline monitor panes"),
    )

    result = startup_mod._ensure_tmux_monitor(tmp_path)  # ANTICHEAT_OK: tool unit test

    assert result.status == "FAIL"
    assert "missing monitor script" in result.detail


def test_tmux_monitor_recovers_when_restart_establishes_session(monkeypatch, tmp_path):
    monitor_script = tmp_path / "tools" / "observability" / "pipeline_monitor.sh"
    monitor_script.parent.mkdir(parents=True)
    monitor_script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    states = iter(
        [
            (False, "session missing"),
            (True, "session rcx-pipeline active"),
        ]
    )
    monkeypatch.setattr(startup_mod, "_tmux_session_stable", lambda *args, **kwargs: next(states))
    monkeypatch.setattr(
        startup_mod,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )

    result = startup_mod._ensure_tmux_monitor(tmp_path)  # ANTICHEAT_OK: tool unit test
    assert result.status == "OK"
    assert "started; session rcx-pipeline active" in result.detail


def test_tmux_monitor_fails_closed_when_restart_does_not_establish_session(monkeypatch, tmp_path):
    monitor_script = tmp_path / "tools" / "observability" / "pipeline_monitor.sh"
    monitor_script.parent.mkdir(parents=True)
    monitor_script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

    states = iter(
        [
            (False, "session missing"),
            (False, "still missing"),
        ]
    )
    monkeypatch.setattr(startup_mod, "_tmux_session_stable", lambda *args, **kwargs: next(states))
    monkeypatch.setattr(
        startup_mod,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            "",
            "start failed",
        ),
    )

    result = startup_mod._ensure_tmux_monitor(tmp_path)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "failed closed after recovery attempt" in result.detail


def test_tmux_monitor_fails_closed_when_start_exits_non_zero_after_partial_start(monkeypatch, tmp_path):
    monitor_script = tmp_path / "tools" / "observability" / "pipeline_monitor.sh"
    monitor_script.parent.mkdir(parents=True)
    monitor_script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

    states = iter(
        [
            (False, "session missing"),
            (True, "session rcx-pipeline active"),
        ]
    )
    monkeypatch.setattr(startup_mod, "_tmux_session_stable", lambda *args, **kwargs: next(states))
    monkeypatch.setattr(
        startup_mod,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            "",
            "start failed but session exists",
        ),
    )

    result = startup_mod._ensure_tmux_monitor(tmp_path)  # ANTICHEAT_OK: tool unit test
    assert result.status == "FAIL"
    assert "failed closed after recovery attempt" in result.detail
    assert "tmux state=session rcx-pipeline active" in result.detail


def test_gather_results_fails_closed_when_codex_home_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        startup_mod,
        "_ensure_tmux_monitor",
        lambda repo_root: startup_mod.CheckResult("tmux_monitor", "OK", "session active"),
    )
    monkeypatch.setattr(
        startup_mod,
        "_ensure_web_dashboard",
        lambda repo_root: startup_mod.CheckResult("web_dashboard", "OK", "dashboard active"),
    )

    local_results, observability_results = startup_mod.gather_results(
        tmp_path,
        tmp_path / ".codex-missing",
    )

    assert local_results == [
        startup_mod.CheckResult(
            "codex_home",
            "FAIL",
            f"missing required Codex-local startup state: {tmp_path / '.codex-missing'}",
        )
    ]
    assert observability_results == [
        startup_mod.CheckResult("tmux_monitor", "OK", "session active"),
        startup_mod.CheckResult("web_dashboard", "OK", "dashboard active"),
    ]
