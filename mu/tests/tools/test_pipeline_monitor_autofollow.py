"""Proof test for default-monitor lane autofollow.

Wave: monitor-default-autofollow-bus-resolver-narrow-2026-06-10
FOUNDER_OVERRIDE: monitor-default-autofollow-bus-resolver-narrow-2026-06-10

Covers three surfaces that together let the DEFAULT pipeline monitor's panes 2-4
follow the freshest active lane bus by re-resolving the (root, bus) pair on each
pane refresh:

* WI-1/WI-3 — ``_resolve_live_root.sh --emit-pair`` opt-in pair mode with the
  unique-strict-max lane selection rule (A1-A7).
* WI-2 — ``pipeline_monitor.sh rebuild_tmux_session`` wires the ephemeral
  ``RCX_OBS_AUTOFOLLOW_BUS=1`` signal into the DEFAULT monitor's pane 2/3/4
  commands, and pinned monitors keep their fixed bus (B1-B2).
* WI-2B — each pane script's ``refresh_context`` rebinds the effective bus from
  the pair helper when the signal is set, with a fail-safe that keeps the
  current bus on empty/invalid output (B3-B5).

Run: ``PYTHONHASHSEED=0 python3 -m pytest -q
mu/tests/tools/test_pipeline_monitor_autofollow.py``
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

OBSERVABILITY_DIR = Path(__file__).resolve().parents[2] / "tools" / "observability"
_TIMEOUT_S = int(os.environ.get("RCX_TEST_OBSERVABILITY_ONESHOT_TIMEOUT_S", "30"))

# Deterministic activity-file mtimes (epoch seconds). No wall-clock reads so the
# selection is stable under PYTHONHASHSEED=0 and across machines.
_T0 = 1_700_000_000
_T1 = 1_700_000_100
_T2 = 1_700_000_200


def _write_exec(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _fake_git_dir(
    tmp_path: Path,
    *,
    show_toplevel: str | None,
    branch: str | None,
    worktree_output: str = "",
) -> Path:
    """A canned ``git`` that answers only the calls these scripts make."""
    bin_dir = tmp_path / "git-bin"
    bin_dir.mkdir(exist_ok=True)
    script = f"""#!/usr/bin/env bash
set -eu
args=("$@")
git_c_dir=""
if [ "${{args[0]:-}}" = "-C" ]; then
  git_c_dir="${{args[1]:-}}"
  args=("${{args[@]:2}}")
fi
case "${{args[*]}}" in
  "rev-parse --show-toplevel")
    if [ -n "$git_c_dir" ]; then
      printf '%s\\n' "$git_c_dir"
    else
      {"printf '%s\\n' " + repr(show_toplevel) if show_toplevel is not None else "exit 128"}
    fi
    ;;
  "rev-parse --abbrev-ref HEAD")
    if [ -n "$git_c_dir" ]; then
      printf '%s\\n' "follow-branch"
    else
      {"printf '%s\\n' " + repr(branch) if branch is not None else "exit 1"}
    fi
    ;;
  "worktree list --porcelain")
    printf '%b' {worktree_output!r}
    ;;
  *)
    exit 1
    ;;
esac
"""
    _write_exec(bin_dir / "git", script)
    return bin_dir


def _fake_tmux_dir(tmp_path: Path, *, log_path: Path) -> Path:
    """A recording ``tmux`` shim — logs every call and fakes pane/window ids.

    Mirrors the proven shim in test_recovery_gate.py so the first ``start`` runs a
    real ``rebuild_tmux_session`` and the pane commands land in ``log_path``.
    """
    bin_dir = tmp_path / "tmux-bin"
    bin_dir.mkdir(exist_ok=True)
    counter_path = tmp_path / "tmux-split-counter.txt"
    session_path = tmp_path / "tmux-session-active"
    panes_path = tmp_path / "tmux-panes.txt"
    script = f"""#!/usr/bin/env bash
set -eu
log_path={str(log_path)!r}
counter_path={str(counter_path)!r}
session_path={str(session_path)!r}
panes_path={str(panes_path)!r}
printf '%s\\n' "$*" >> "$log_path"
cmd="${{1:-}}"
shift || true
healthy_panes() {{
  local root="${{PWD}}"
  printf 'PANE 1 · LIVE PIPELINE LOG\\t%s\\n' "$root"
  printf 'PANE 2 · REVIEW FINDINGS\\t%s\\n' "$root"
  printf 'PANE 3 · PLAIN-ENGLISH STATUS\\t%s\\n' "$root"
  printf 'PANE 4 · SESSION TIMELINE\\t%s\\n' "$root"
}}
case "$cmd" in
  has-session)
    [ -f "$session_path" ]
    ;;
  kill-session)
    if [ -f "$session_path" ]; then
      rm -f "$session_path" "$panes_path" "$counter_path"
      exit 0
    fi
    exit 1
    ;;
  new-session)
    : > "$session_path"
    printf '0' > "$counter_path"
    healthy_panes > "$panes_path"
    exit 0
    ;;
  list-panes)
    [ -f "$session_path" ] || exit 1
    if [ -f "$panes_path" ]; then
      cat "$panes_path"
    else
      healthy_panes
    fi
    ;;
  select-pane|setw|attach-session)
    exit 0
    ;;
  display-message)
    [ "${{1:-}}" = "-p" ] && shift
    if [ "${{1:-}}" = "-t" ]; then
      shift 2
    fi
    case "${{1:-}}" in
      '#{{window_id}}')
        printf '@1\\n'
        ;;
      '#{{pane_id}}')
        printf '%%10\\n'
        ;;
      *)
        exit 1
        ;;
    esac
    ;;
  split-window)
    count=0
    if [ -f "$counter_path" ]; then
      count=$(cat "$counter_path")
    fi
    count=$((count + 1))
    printf '%s' "$count" > "$counter_path"
    case "$count" in
      1) printf '%%11\\n' ;;
      2) printf '%%12\\n' ;;
      3) printf '%%13\\n' ;;
      *) exit 1 ;;
    esac
    ;;
  *)
    exit 1
    ;;
esac
"""
    _write_exec(bin_dir / "tmux", script)
    return bin_dir


def _install(repo: Path, name: str) -> Path:
    target = repo / "mu" / "tools" / "observability"
    target.mkdir(parents=True, exist_ok=True)
    dest = target / name
    dest.write_text((OBSERVABILITY_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    dest.chmod(0o755)
    return dest


def _touch_activity(root: Path, bus: str, mtime: int) -> None:
    """Create one bus-relative activity file so worktree_score sees ``mtime``."""
    state = root / bus / "executors" / "phase_b_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{}\n", encoding="utf-8")
    os.utime(state, (mtime, mtime))


def _porcelain(*roots: Path) -> str:
    blocks = []
    for index, root in enumerate(roots):
        blocks.append(f"worktree {root}\nHEAD {index + 1:040d}\nbranch refs/heads/wt{index}\n\n")
    return "".join(blocks)


# ───────────────────────────── resolver pair mode ─────────────────────────────


def _run_resolver(cur_root: Path, *args: str, git_bin: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(OBSERVABILITY_DIR / "_resolve_live_root.sh"), *args],
        cwd=cur_root,
        capture_output=True,
        text=True,
        env=os.environ | {"PATH": f"{git_bin}:{os.environ['PATH']}"},
        timeout=_TIMEOUT_S,
    )


def _emit_pair(tmp_path: Path, scenario: dict[str, list[tuple[str, int]]]):
    """Build a synthetic repo+worktrees and return the resolver's (root, bus).

    ``scenario`` maps a worktree label ("cur" is the current root) to a list of
    ``(bus, mtime)`` activity entries. Every labelled worktree appears in the
    canned ``git worktree list`` so the resolver enumerates and scores it.
    """
    roots: dict[str, Path] = {}
    cur = tmp_path / "cur"
    cur.mkdir(exist_ok=True)
    roots["cur"] = cur
    for label in scenario:
        root = tmp_path / label
        root.mkdir(exist_ok=True)
        roots[label] = root
    for label, entries in scenario.items():
        for bus, mtime in entries:
            _touch_activity(roots[label], bus, mtime)

    git_bin = _fake_git_dir(
        tmp_path,
        show_toplevel=str(cur),
        branch="follow-branch",
        worktree_output=_porcelain(*roots.values()),
    )
    result = _run_resolver(cur, "--emit-pair", git_bin=git_bin)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 2, f"pair mode must print exactly root+bus, got {lines!r}"
    return Path(lines[0]), lines[1], roots


def _real(path: Path) -> str:
    return os.path.realpath(str(path))


def test_a1_single_lane_strictly_fresher_emits_lane(tmp_path):
    root, bus, roots = _emit_pair(
        tmp_path,
        {"cur": [(".agent_bus", _T0)], "wt1": [(".agent_bus-lane1", _T1)]},
    )
    assert bus == ".agent_bus-lane1"
    assert _real(root) == _real(roots["wt1"])


def test_a2_two_lanes_above_default_unique_max_emits_freshest(tmp_path):
    root, bus, roots = _emit_pair(
        tmp_path,
        {
            "cur": [(".agent_bus", _T0)],
            "wt1": [(".agent_bus-lane1", _T1)],
            "wt2": [(".agent_bus-lane2", _T2)],
        },
    )
    assert bus == ".agent_bus-lane2"
    assert _real(root) == _real(roots["wt2"])


def test_a3_two_lanes_tied_at_top_falls_back_to_default(tmp_path):
    root, bus, roots = _emit_pair(
        tmp_path,
        {
            "cur": [(".agent_bus", _T0)],
            "wt1": [(".agent_bus-lane1", _T2)],
            "wt2": [(".agent_bus-lane2", _T2)],
        },
    )
    assert bus == ".agent_bus"
    assert _real(root) == _real(roots["cur"])


def test_a4_default_bus_greatest_falls_back_to_default(tmp_path):
    root, bus, roots = _emit_pair(
        tmp_path,
        {"cur": [(".agent_bus", _T2)], "wt1": [(".agent_bus-lane1", _T0)]},
    )
    assert bus == ".agent_bus"
    assert _real(root) == _real(roots["cur"])


def test_a5_single_lane_tied_with_default_falls_back_to_default(tmp_path):
    root, bus, roots = _emit_pair(
        tmp_path,
        {"cur": [(".agent_bus", _T1)], "wt1": [(".agent_bus-lane1", _T1)]},
    )
    assert bus == ".agent_bus"
    assert _real(root) == _real(roots["cur"])


def test_a6_absent_lane_bus_falls_back_to_default(tmp_path):
    root, bus, roots = _emit_pair(tmp_path, {"cur": [(".agent_bus", _T0)]})
    assert bus == ".agent_bus"
    assert _real(root) == _real(roots["cur"])


def test_a7_no_flag_prints_only_resolved_root(tmp_path):
    cur = tmp_path / "cur"
    cur.mkdir()
    _touch_activity(cur, ".agent_bus", _T0)
    git_bin = _fake_git_dir(
        tmp_path,
        show_toplevel=str(cur),
        branch="follow-branch",
        worktree_output=_porcelain(cur),
    )
    result = _run_resolver(cur, git_bin=git_bin)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 1, f"legacy no-flag must print only the root, got {lines!r}"
    assert _real(Path(lines[0])) == _real(cur)


def _touch_scratch(root: Path, name: str, mtime: int) -> None:
    """Create one bus-AGNOSTIC ``.scratch`` signal at the worktree root.

    These executor live-logs / agent-review status files are NOT under any bus,
    so worktree_score (full scope) counts them for EVERY candidate bus.
    """
    path = root / ".scratch" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))


@pytest.mark.parametrize(
    "scratch_name",
    [
        pytest.param("phase_b_executor_live.log", id="executor-live-log"),
        pytest.param("phase_b_agent_review_w.status.json", id="agent-review-status"),
    ],
)
def test_a8_bus_agnostic_scratch_signal_does_not_defeat_lane_follow(tmp_path, scratch_name):
    """Bridge round-1 DEFECT: a bus-agnostic ``.scratch`` signal in the lane
    worktree must NOT prop up ``.agent_bus``'s score and tie the genuinely-active
    lane against the default. Pair-mode scoring is bus-specific, so the lane bus
    follows on its OWN bus-relative activity even when a fresh ``.scratch``
    executor live-log / agent-review status file is present at that root.

    This is the live-log scenario the A1-A7 cases (bus-relative activity only)
    missed; before the bus-specific scoring fix the resolver fell back to
    ``.agent_bus`` here because the root-level ``.scratch`` mtime scored every bus.
    """
    cur = tmp_path / "cur"
    cur.mkdir()
    wt1 = tmp_path / "wt1"
    wt1.mkdir()
    _touch_activity(cur, ".agent_bus", _T0)        # older default-bus activity
    _touch_activity(wt1, ".agent_bus-lane1", _T2)  # fresher lane-bus activity
    _touch_scratch(wt1, scratch_name, _T2)         # bus-agnostic; scores every bus

    git_bin = _fake_git_dir(
        tmp_path,
        show_toplevel=str(cur),
        branch="follow-branch",
        worktree_output=_porcelain(cur, wt1),
    )
    result = _run_resolver(cur, "--emit-pair", git_bin=git_bin)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 2, f"pair mode must print exactly root+bus, got {lines!r}"
    assert lines[1] == ".agent_bus-lane1", (
        f"bus-agnostic {scratch_name} must not defeat lane follow; got {lines!r}"
    )
    assert _real(Path(lines[0])) == _real(wt1)


@pytest.mark.parametrize(
    "scratch_name",
    [
        pytest.param("phase_b_executor_live.log", id="executor-live-log"),
        pytest.param("phase_b_agent_review_w.status.json", id="agent-review-status"),
    ],
)
def test_a9_pair_fallback_root_matches_legacy_no_flag_on_scratch_liveness(
    tmp_path, scratch_name
):
    """Bridge round-2 DEFECT: when pair mode falls back to ``.agent_bus``, the root
    it emits MUST equal the legacy no-flag resolver's root.

    The default monitor always sets ``RCX_OBS_AUTOFOLLOW_BUS=1`` and its panes take
    the pair-mode root verbatim (while autofollowing they never fall through to the
    no-flag ``resolve_repo_root``). So when a worktree's only fresh signal is
    root-level ``.scratch`` liveness (an executor live-log / agent-review status
    file, NOT bus activity), the bus-specific lane comparison must NOT cost the
    fallback its full-scope root-follow. Before the fix, ``--emit-pair`` scored the
    fallback root bus-specifically and returned ``cur`` while the no-flag path
    returned the ``.scratch``-active worktree — a silent root-follow regression for
    the default monitor. The full-scope ``.scratch`` signal dominates for any bus,
    so this equivalence holds regardless of the ambient ``RCX_AGENT_BUS_DIR``.
    """
    cur = tmp_path / "cur"
    cur.mkdir()
    wt_scratch = tmp_path / "wt_scratch_active"
    wt_scratch.mkdir()
    _touch_activity(cur, ".agent_bus", _T0)        # older default-bus activity at cur
    _touch_scratch(wt_scratch, scratch_name, _T2)  # fresher, root-level .scratch only

    git_bin = _fake_git_dir(
        tmp_path,
        show_toplevel=str(cur),
        branch="follow-branch",
        worktree_output=_porcelain(cur, wt_scratch),
    )

    # Legacy no-flag resolver: full-scope scoring counts the .scratch liveness, so
    # it follows the scratch-active worktree.
    legacy = _run_resolver(cur, git_bin=git_bin)
    assert legacy.returncode == 0, legacy.stderr
    legacy_lines = legacy.stdout.splitlines()
    assert len(legacy_lines) == 1, f"legacy must print only the root, got {legacy_lines!r}"
    assert _real(Path(legacy_lines[0])) == _real(wt_scratch), legacy_lines

    # Pair mode falls back to .agent_bus (no lane bus present); its root MUST match
    # the legacy root so the autofollowing default monitor never loses root-follow.
    pair = _run_resolver(cur, "--emit-pair", git_bin=git_bin)
    assert pair.returncode == 0, pair.stderr
    pair_lines = pair.stdout.splitlines()
    assert len(pair_lines) == 2, f"pair mode must print root+bus, got {pair_lines!r}"
    assert pair_lines[1] == ".agent_bus", pair_lines
    assert _real(Path(pair_lines[0])) == _real(wt_scratch), pair_lines
    assert _real(Path(pair_lines[0])) == _real(Path(legacy_lines[0])), (
        f"pair fallback root must match legacy no-flag root; "
        f"legacy={legacy_lines[0]!r} pair={pair_lines[0]!r}"
    )


# ─────────────────────────── default-monitor wiring ───────────────────────────


def _start_and_capture(
    tmp_path: Path,
    repo: Path,
    *monitor_args: str,
    install_identity: bool = False,
    lane_config: dict | None = None,
) -> list[str]:
    _install(repo, "pipeline_monitor.sh")
    if install_identity:
        _install(repo, "pipeline_monitor_identity.py")
    if lane_config is not None:
        config_path = repo / "mu" / "tools" / "executors" / "executor_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        config_path.write_text(
            json.dumps({"pipeline_monitor": {"lanes": lane_config}}) + "\n",
            encoding="utf-8",
        )

    git_bin = _fake_git_dir(tmp_path, show_toplevel=str(repo), branch="jabramsja/test-wave")
    tmux_log = tmp_path / "tmux.log"
    tmux_bin = _fake_tmux_dir(tmp_path, log_path=tmux_log)
    env = os.environ | {
        "PATH": f"{tmux_bin}:{git_bin}:{os.environ['PATH']}",
        "RCX_PIPELINE_MONITOR_STATE_DIR": str(tmp_path / "monitor-state"),
        "RCX_PIPELINE_MONITOR_HEALTH_INTERVAL": "60",
    }
    monitor = repo / "mu" / "tools" / "observability" / "pipeline_monitor.sh"
    try:
        result = subprocess.run(
            ["bash", str(monitor), *monitor_args, "start", "--detach"],
            cwd=repo,
            capture_output=True,
            text=True,
            env=env,
            timeout=_TIMEOUT_S,
        )
        assert result.returncode == 0, result.stderr
        return tmux_log.read_text(encoding="utf-8").splitlines()
    finally:
        subprocess.run(
            ["bash", str(monitor), *monitor_args, "stop"],
            cwd=repo,
            capture_output=True,
            text=True,
            env=env,
            timeout=_TIMEOUT_S,
        )


def _pane_command_lines(log_lines: list[str], pane_script: str) -> list[str]:
    return [line for line in log_lines if pane_script in line]


def test_b1_default_monitor_panes_carry_autofollow_signal(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    log_lines = _start_and_capture(tmp_path, repo)

    for pane_script in ("_pane_findings.sh", "_pane_processes.sh", "_pane_timeline.sh"):
        commands = _pane_command_lines(log_lines, pane_script)
        assert commands, f"no pane command captured for {pane_script}"
        for command in commands:
            assert "RCX_OBS_AUTOFOLLOW_BUS=1" in command, command
            # Still seeds the default bus; the signal only ENABLES per-refresh
            # re-resolution (a one-shot pane command cannot bake a dynamic bus).
            assert "BUS_DIR=.agent_bus " in command, command
            assert "RCX_AGENT_BUS_DIR=.agent_bus " in command, command

    # Pane 1 (live-log watcher) is out of scope and must NOT carry the signal.
    watcher = _pane_command_lines(log_lines, "rcx_log_watcher.sh")
    assert watcher, "watcher pane command not captured"
    for command in watcher:
        assert "RCX_OBS_AUTOFOLLOW_BUS" not in command, command


@pytest.mark.parametrize(
    "pin_args",
    [
        pytest.param(("--bus-dir", ".agent_bus-alpha"), id="bus-dir"),
        pytest.param(("--lane", "alpha"), id="lane"),
    ],
)
def test_b2_pinned_monitor_panes_have_no_autofollow_signal(tmp_path, pin_args):
    repo = tmp_path / "repo"
    repo.mkdir()
    log_lines = _start_and_capture(
        tmp_path,
        repo,
        *pin_args,
        install_identity=True,
        lane_config={
            "alpha": {
                "bus_dir": ".agent_bus-alpha",
                "dashboard_port": 8101,
                "tmux_session": "rcx-pipeline-alpha",
            }
        },
    )

    for pane_script in ("_pane_findings.sh", "_pane_processes.sh", "_pane_timeline.sh"):
        commands = _pane_command_lines(log_lines, pane_script)
        assert commands, f"no pane command captured for {pane_script}"
        for command in commands:
            assert "RCX_OBS_AUTOFOLLOW_BUS" not in command, command
            # Pinned monitors keep their explicit fixed bus.
            assert "BUS_DIR=.agent_bus-alpha " in command, command


# ───────────────────────── pane refresh-loop rebinding ─────────────────────────

_PANE_SCRIPTS = {
    "_pane_findings.sh": "RAW_DIR",
    "_pane_processes.sh": "BUS",
    "_pane_timeline.sh": "RAW_DIR",
}


def _write_pair_stub(work: Path, *, emit_lines: list[str]) -> None:
    """Stub ``_resolve_live_root.sh`` in ``work`` (== $SCRIPT_DIR for the pane).

    ``--emit-pair`` prints ``emit_lines`` verbatim (so the test controls the pair
    the pane sees); any other invocation prints the work dir as the resolved root.
    """
    lines = ["#!/usr/bin/env bash", 'if [ "$1" = "--emit-pair" ]; then']
    for value in emit_lines:
        lines.append(f"  printf '%s\\n' {_shquote(value)}")
    lines.append("  exit 0")
    lines.append("fi")
    lines.append(f"printf '%s\\n' {_shquote(str(work))}")
    stub = work / "_resolve_live_root.sh"
    _write_exec(stub, "\n".join(lines) + "\n")


def _shquote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _drive_refresh_context(
    work: Path,
    pane_script: str,
    *,
    signal: str,
) -> dict[str, str]:
    """Source the pane script (main-guard suppresses its while-loop), call
    ``refresh_context`` once, and report the resulting bus binding."""
    harness = (
        f"source './{pane_script}' >/dev/null 2>&1\n"
        "refresh_context >/dev/null 2>&1\n"
        'printf "BUS_DIR=%s\\n" "$BUS_DIR"\n'
        'printf "REPO_ROOT=%s\\n" "$REPO_ROOT"\n'
        'printf "RCX_AGENT_BUS_DIR=%s\\n" "${RCX_AGENT_BUS_DIR:-<unset>}"\n'
        'printf "RAW_DIR=%s\\n" "${RAW_DIR:-}"\n'
        'printf "BUS=%s\\n" "${BUS:-}"\n'
    )
    env = os.environ | {
        "BUS_DIR": ".agent_bus",
        "RCX_PANE_ONESHOT": "1",
    }
    if signal is not None:
        env["RCX_OBS_AUTOFOLLOW_BUS"] = signal
    else:
        env.pop("RCX_OBS_AUTOFOLLOW_BUS", None)
    result = subprocess.run(
        ["bash", "-c", harness],
        cwd=work,
        capture_output=True,
        text=True,
        env=env,
        timeout=_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr
    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        parsed[key] = value
    return parsed


def _expected_derived(repo_root: str, path_var: str, bus: str) -> str:
    # processes builds BUS="$REPO_ROOT/$BUS_DIR"; findings/timeline build
    # RAW_DIR="$REPO_ROOT/$BUS_DIR/raw" (timeline in its loop, reconstructed here).
    base = f"{repo_root}/{bus}"
    return base if path_var == "BUS" else f"{base}/raw"


def _prepare_pane_workdir(tmp_path: Path, pane_script: str) -> Path:
    work = tmp_path / "panework"
    work.mkdir(exist_ok=True)
    dest = work / pane_script
    dest.write_text((OBSERVABILITY_DIR / pane_script).read_text(encoding="utf-8"), encoding="utf-8")
    dest.chmod(0o755)
    subprocess.run(["git", "init", "-q"], cwd=work, check=True, timeout=_TIMEOUT_S)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=work, check=True, timeout=_TIMEOUT_S)
    subprocess.run(["git", "config", "user.name", "t"], cwd=work, check=True, timeout=_TIMEOUT_S)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=work,
        check=True,
        timeout=_TIMEOUT_S,
    )
    return work


@pytest.mark.parametrize("pane_script,path_var", sorted(_PANE_SCRIPTS.items()))
def test_b3_signal_set_unique_lane_rebinds_effective_bus(tmp_path, pane_script, path_var):
    work = _prepare_pane_workdir(tmp_path, pane_script)
    _write_pair_stub(work, emit_lines=[str(work), ".agent_bus-lane9"])

    state = _drive_refresh_context(work, pane_script, signal="1")

    # The canonical effective bus is rebound and re-exported for child helpers.
    assert state["BUS_DIR"] == ".agent_bus-lane9"
    assert state["RCX_AGENT_BUS_DIR"] == ".agent_bus-lane9"
    assert state["REPO_ROOT"] == str(work)
    # The bus-derived path the pane builds now lives under the lane bus.
    derived = state[path_var] or f"{state['REPO_ROOT']}/{state['BUS_DIR']}/raw"
    assert derived == _expected_derived(state["REPO_ROOT"], path_var, ".agent_bus-lane9"), derived


@pytest.mark.parametrize("pane_script,path_var", sorted(_PANE_SCRIPTS.items()))
def test_b4_signal_unset_keeps_fixed_default_bus(tmp_path, pane_script, path_var):
    work = _prepare_pane_workdir(tmp_path, pane_script)
    # Stub WOULD report a lane bus, but with the signal unset it must be ignored.
    _write_pair_stub(work, emit_lines=[str(work), ".agent_bus-lane9"])

    state = _drive_refresh_context(work, pane_script, signal=None)

    assert state["BUS_DIR"] == ".agent_bus"
    assert state["RCX_AGENT_BUS_DIR"] == "<unset>"
    derived = state[path_var] or f"{state['REPO_ROOT']}/{state['BUS_DIR']}/raw"
    assert "/.agent_bus-lane9" not in derived, derived
    assert derived == _expected_derived(state["REPO_ROOT"], path_var, ".agent_bus"), derived


@pytest.mark.parametrize(
    "emit_lines",
    [
        pytest.param([str("X"), "/etc/passwd"], id="invalid-bus"),
        pytest.param([], id="empty-output"),
    ],
)
@pytest.mark.parametrize("pane_script,path_var", sorted(_PANE_SCRIPTS.items()))
def test_b5_signal_set_invalid_helper_output_keeps_current_bus(
    tmp_path, pane_script, path_var, emit_lines
):
    work = _prepare_pane_workdir(tmp_path, pane_script)
    # Re-point a placeholder root token to the work dir so the path is real.
    resolved = [str(work) if value == "X" else value for value in emit_lines]
    _write_pair_stub(work, emit_lines=resolved)

    state = _drive_refresh_context(work, pane_script, signal="1")

    # Fail-safe: never blanked, never errored, bus stays on the current value.
    assert state["BUS_DIR"] == ".agent_bus"
    assert state["RCX_AGENT_BUS_DIR"] == "<unset>"
    derived = state[path_var] or f"{state['REPO_ROOT']}/{state['BUS_DIR']}/raw"
    assert "/etc/passwd" not in derived, derived
    assert derived == _expected_derived(state["REPO_ROOT"], path_var, ".agent_bus"), derived
