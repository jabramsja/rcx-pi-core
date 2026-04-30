from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT


SCRIPT = REPO_ROOT / "mu" / "tools" / "observability" / "_pane_prci.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _init_temp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(
        ["git", "checkout", "-b", "feature/prci"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("temp repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
    return repo


def _install_fake_tools(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "clear",
        """
        #!/usr/bin/env bash
        exit 0
        """,
    )
    _write_executable(
        fake_bin / "gh",
        r"""
        #!/usr/bin/env bash
        set -euo pipefail

        printf '%s\n' "$*" >> "${GH_LOG:?}"

        if [ "${1:-}" = "pr" ]; then
          case "${2:-}" in
            list)
              printf '%s\n' "${GH_PR_LIST_RESULT-123}"
              exit 0
              ;;
            checks)
              printf 'build\tpass\t0s\t%s\n' "${3:-}"
              exit 0
              ;;
            view)
              json_field=""
              jq_expr=""
              while [ "$#" -gt 0 ]; do
                case "$1" in
                  --json)
                    json_field="${2:-}"
                    shift 2
                    ;;
                  --jq)
                    jq_expr="${2:-}"
                    shift 2
                    ;;
                  *)
                    shift
                    ;;
                esac
              done
              if [ "$json_field" = "reviews" ]; then
                printf '{"reviews":[]}' | jq -r "$jq_expr"
                exit 0
              fi
              if [ "$json_field" = "comments" ]; then
                jq -r "$jq_expr" "${GH_COMMENTS_JSON:?}"
                exit 0
              fi
              exit 1
              ;;
          esac
        fi

        if [ "${1:-}" = "api" ]; then
          printf '%s\n' "${2:-}" >> "${GH_API_LOG:?}"
          printf '2\n'
          exit 0
        fi

        printf 'unexpected gh call: %s\n' "$*" >&2
        exit 2
        """,
    )
    return fake_bin


def _run_pane_once(
    tmp_path: Path,
    comments: list[dict],
    *,
    executor_pr: str | None = None,
    pr_list_result: str = "123",
) -> tuple[str, str, str]:
    repo = _init_temp_repo(tmp_path)
    pane_script = tmp_path / "_pane_prci.sh"
    shutil.copy2(SCRIPT, pane_script)

    if executor_pr is not None:
        executor_dir = repo / ".agent_bus" / "executors"
        executor_dir.mkdir(parents=True)
        (executor_dir / "commit_executor_test.json").write_text(
            json.dumps({"pr_number": executor_pr}),
            encoding="utf-8",
        )

    comments_json = tmp_path / "comments.json"
    comments_json.write_text(json.dumps({"comments": comments}), encoding="utf-8")

    fake_bin = _install_fake_tools(tmp_path)
    gh_log = tmp_path / "gh.log"
    gh_api_log = tmp_path / "gh_api.log"
    env = os.environ.copy()
    env.update(
        {
            "GH_API_LOG": str(gh_api_log),
            "GH_COMMENTS_JSON": str(comments_json),
            "GH_LOG": str(gh_log),
            "GH_PR_LIST_RESULT": pr_list_result,
            "PATH": f"{fake_bin}:{env['PATH']}",
            "RCX_PANE_PRCI_ONCE": "1",
            "TERM": "dumb",
        }
    )

    result = subprocess.run(
        ["bash", str(pane_script)],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return (
        result.stdout,
        gh_log.read_text(encoding="utf-8") if gh_log.exists() else "",
        gh_api_log.read_text(encoding="utf-8") if gh_api_log.exists() else "",
    )


def _comment(author: str, body: str) -> dict:
    return {"author": {"login": author}, "body": body}


def test_pane_prci_no_longer_uses_jq_last_arity() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "last(3)" not in source
    assert ".[-3:][]" in source


@pytest.mark.parametrize(
    ("comments", "expected_lines", "absent_lines"),
    [
        ([], [], []),
        ([_comment("bot", "one\nignored")], ["bot: one"], []),
        (
            [_comment("bot", "one"), _comment("github-actions", "two")],
            ["bot: one", "github-actions: two"],
            [],
        ),
        (
            [
                _comment("bot", "one"),
                _comment("human", "not selected"),
                _comment("bot", "two"),
                _comment("dependabot[bot]", "three"),
                _comment("github-actions", "four"),
            ],
            ["bot: two", "dependabot[bot]: three", "github-actions: four"],
            ["bot: one", "human: not selected"],
        ),
    ],
    ids=["empty", "one", "two", "three_or_more"],
)
def test_bot_comment_selection_handles_empty_short_and_long_inputs(
    tmp_path: Path,
    comments: list[dict],
    expected_lines: list[str],
    absent_lines: list[str],
) -> None:
    stdout, _, _ = _run_pane_once(tmp_path, comments)

    if expected_lines:
        assert "Bot comments:" in stdout
    else:
        assert "Bot comments:" not in stdout

    for line in expected_lines:
        assert line in stdout
    for line in absent_lines:
        assert line not in stdout


def test_displayed_bot_comment_text_is_escape_sanitized(tmp_path: Path) -> None:
    stdout, _, _ = _run_pane_once(
        tmp_path,
        [
            _comment(
                "github-actions[bot]",
                "safe \x1b[31mred\x1b[0m \x1b]0;owned\x07text bad\rrewrite \x08tail",
            )
        ],
    )

    assert "\x1b" not in stdout
    assert "\x07" not in stdout
    assert "\r" not in stdout
    assert "\x08" not in stdout
    assert "owned" not in stdout
    assert "github-actions[bot]: safe red text badrewrite tail" in stdout


def test_nonnumeric_pr_does_not_invoke_review_comments_api(tmp_path: Path) -> None:
    stdout, gh_log, gh_api_log = _run_pane_once(
        tmp_path,
        [],
        executor_pr="abc/../../issues",
    )

    assert "PR status unavailable: invalid PR identifier" in stdout
    assert gh_log == ""
    assert gh_api_log == ""


def test_empty_pr_does_not_invoke_review_comments_api(tmp_path: Path) -> None:
    stdout, gh_log, gh_api_log = _run_pane_once(
        tmp_path,
        [],
        pr_list_result="",
    )

    assert "No active PR for this worktree" in stdout
    assert "pr list" in gh_log
    assert gh_api_log == ""
