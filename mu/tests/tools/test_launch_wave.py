"""Regression tests for the launch_wave dispatcher-wave setup builder.

launch_wave mechanizes the full per-wave setup from one wave-config as a SIMPLE
sequential chain over the existing builders (no transactional/rollback layer).
These tests cover:

  * the sequential setup (all artifacts produced from one config),
  * the baked-in packet fences (packet-integrity, line-ref lint, asterisk-free
    title, run_mu # SPEED_OK),
  * the fail-closed precondition (the dispatcher's own pre-Phase-B gate),
  * the 3-guard verification,
  * the optional dispatcher launch (off by default), and
  * the bounded re-run recovery contract: a partial run re-run with the SAME
    wave-config converges to exactly one canonical copy of each artifact.
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import launch_wave as lw  # noqa: E402,I001  (path insert must precede import)
import tracker_sync_note as tsn  # noqa: E402  (reuse proof for the note builder)
import executor_common as ec  # noqa: E402  (public seam for the routing-record path)


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                           #
# --------------------------------------------------------------------------- #

_NOTE_HEADER_RE = re.compile(r"^- Tracker sync note \([^,]+,\s*([^)]+)\):", re.MULTILINE)


def _git(repo, *args):
    subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True
    )


@pytest.fixture
def wave_repo(tmp_path):
    """A minimal git repo with the structure launch_wave's builders expect."""
    repo = tmp_path
    (repo / "pyproject.toml").write_text("[tool.placeholder]\n", encoding="utf-8")
    (repo / "reports" / "control_plane").mkdir(parents=True)
    # The Ra section must already carry at least one tracker note so the upsert
    # builder has a canonical insertion anchor.
    (repo / "TASKS.md").write_text(
        "# TASKS\n\n## Ra\n\n"
        "- Tracker sync note (2026-06-18, seed-wave): **Seed.** Class: MAINTENANCE. "
        "target_gate_id: G8. FOUNDER_OVERRIDE:seed-wave.\n\n"
        "---\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def make_config(**overrides):
    """Build a fresh L4_ENABLER WaveConfig (re-run tests need fresh objects)."""
    base = dict(
        wave_id="demo-launcher-wave-2026-06-19",
        title="Demo Launcher Wave 2026-06-19",
        task_id="[NEXT-CODEX-POST-REDTEAM]",
        purpose="Demo wave for the launch_wave builder regression test.",
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        primary_blocker_class="DESIGN",
        primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
        indicator_artifact_ref="reports/l4_wave_indicators/demo.json",
        indicator_collection_command=(
            "python3 tools/metrics/collect_l4_wave_indicators.py "
            "--wave-id demo --output reports/l4_wave_indicators/demo.json"
        ),
        evidence_command="PYTHONHASHSEED=0 python3 -m pytest -q --tb=short",
        evidence_delta="New builder mechanizes the setup.",
        progress_proof_before="no builder",
        progress_proof_after="builder exists",
        scope_items=["mu/tools/executors/launch_wave.py (NEW)"],
        work_items=["Create the builder", "Add the regression test"],
        constraints=["No runtime/substrate changes"],
        stop_conditions=["Halt on a red gate"],
        acceptance_criteria=["Builder exists", "Test passes"],
        date="2026-06-19",
    )
    base.update(overrides)
    return lw.WaveConfig(**base)


def _artifact_counts(repo, wave_id):
    """Return (packet count, tracker-note count, routing-candidate count)."""
    packets = list((repo / "reports" / "control_plane").glob(f"{wave_id}_*.md"))
    tasks = (repo / "TASKS.md").read_text(encoding="utf-8")
    notes = [m for m in _NOTE_HEADER_RE.findall(tasks) if m.strip() == wave_id]
    routing_path = repo / ".agent_bus" / "meta" / "post_merge_routing.json"
    candidates = []
    if routing_path.exists():
        record = json.loads(routing_path.read_text(encoding="utf-8"))
        candidates = [
            c for c in record.get("next_candidates", []) if c.get("candidate") == wave_id
        ]
    return len(packets), len(notes), len(candidates)


# --------------------------------------------------------------------------- #
# Sequential setup                                                            #
# --------------------------------------------------------------------------- #


def test_full_sequential_setup_produces_all_artifacts(wave_repo):
    config = make_config()
    result = lw.run_wave_setup(wave_repo, config)

    packet = wave_repo / config.tracked_packet
    assert packet.is_file()
    assert result.tracked_packet == config.tracked_packet
    assert result.tracker_note_written is True
    assert result.precondition_ok is True
    assert result.guards_ok is True
    assert result.launch["launched"] is False

    # One canonical copy of each artifact.
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)

    # Routing record carries the single next-candidate for this wave.
    routing = json.loads(
        (wave_repo / ".agent_bus" / "meta" / "post_merge_routing.json").read_text()
    )
    assert routing["wave_name"] == config.wave_id
    assert [c["candidate"] for c in routing["next_candidates"]] == [config.wave_id]
    assert routing["next_candidates"][0]["tracked_packet"] == config.tracked_packet


def test_setup_reuses_existing_builders(wave_repo):
    """The artifacts must be byte/shape-identical to the existing builders' output.

    Proves reuse behaviorally (without reaching into private internals): the
    TASKS.md note is exactly what tracker_sync_note.render_tracker_sync_note
    produces, and the routing record carries the auto-populated fields that only
    executor_common.build_post_merge_routing_record emits.
    """
    config = make_config()
    lw.run_wave_setup(wave_repo, config)

    # Tracker note builder reuse: the note in TASKS.md is byte-identical to the
    # canonical renderer's output for the same fields.
    expected_note = tsn.render_tracker_sync_note(lw.build_tracker_fields(config))
    tasks = (wave_repo / "TASKS.md").read_text(encoding="utf-8")
    assert expected_note in tasks

    # Routing-record builder reuse: only build_post_merge_routing_record emits
    # this auto-populated field set.
    routing = json.loads(
        (wave_repo / ".agent_bus" / "meta" / "post_merge_routing.json").read_text()
    )
    for key in ("state_sha", "head_sha", "timestamp_utc", "blocker_report_paths"):
        assert key in routing


# --------------------------------------------------------------------------- #
# Baked-in fences                                                             #
# --------------------------------------------------------------------------- #


def test_generated_packet_carries_baked_in_fences(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    content = packet_path.read_text(encoding="utf-8")

    # The builder's public fence check is clean for the generated packet.
    assert lw.check_packet_fences(content, config) == []

    # packet-integrity: Scope mentions TASKS.md + a bare FOUNDER_OVERRIDE line.
    assert "## Scope" in content
    assert "TASKS.md" in content
    assert f"\nFOUNDER_OVERRIDE:{config.wave_id}\n" in content

    # line-ref lint: no code line-number references like `<file>.py:<n>`.
    assert not re.search(r"\.(?:py|js|md|sh|json|yaml|yml|txt):\d+", content)

    # asterisk-free title (the H1 line).
    title_line = content.splitlines()[0]
    assert title_line == f"# {config.title}"
    assert "*" not in title_line


def test_run_mu_speed_ok_fence_baked_when_slow_function_present(wave_repo):
    config = make_config(slow_functions=["run_mu"])
    content = lw.render_wave_packet(config)
    assert "run_mu" in content
    assert "# SPEED_OK" in content
    assert lw.check_packet_fences(content, config) == []

    # The fence is real: stripping the annotation makes the check fail.
    stripped = content.replace("# SPEED_OK", "(annotation removed)")
    errors = lw.check_packet_fences(stripped, config)
    assert any("run_mu # SPEED_OK" in e for e in errors)


def test_tooling_only_packet_has_no_unannotated_run_mu(wave_repo):
    config = make_config()  # no slow_functions
    content = lw.render_wave_packet(config)
    # A tooling-only wave never introduces an un-annotated run_mu mention.
    assert "run_mu" not in content
    assert lw.check_packet_fences(content, config) == []


def test_builder_refuses_packet_failing_line_ref_fence(wave_repo):
    # A work item that cites code by file:line must be rejected fail-closed.
    config = make_config(
        work_items=["Patch the bug cited at loader.py:128 in the kernel"]
    )
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_packet(wave_repo, config)
    assert "line-ref lint" in str(exc.value)


def test_fence_failure_persists_no_offending_packet(wave_repo):
    """Bridge round 4 DEFECT: a fence failure must NOT leave an offending packet.

    The repro put a code line-ref in ``purpose`` (which feeds create_plan_draft's
    draft, the Purpose/Scope/Request sections). create_plan_draft used to write
    that draft to disk BEFORE the fence check ran, so the offending packet
    persisted (Status: Phase A, containing loader.py:128) even though setup_packet
    raised. The fence check now gates the write: a failing fence raises before any
    packet is written.
    """
    config = make_config(
        purpose="Fix the crash at loader.py:128 in the bootstrap loader."
    )
    wave_id = config.wave_id

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_packet(wave_repo, config)
    assert "line-ref lint" in str(exc.value)

    # No packet persisted: not at the deterministic path, and none by glob.
    assert not (wave_repo / config.tracked_packet).exists()
    assert _artifact_counts(wave_repo, wave_id)[0] == 0


def test_run_wave_setup_fence_failure_persists_no_packet(wave_repo):
    """End-to-end mirror of the bridge round 4 repro via run_wave_setup.

    setup_packet is the first step, so a line-ref in ``purpose`` must fail the
    whole setup closed with no artifact of any kind persisted.
    """
    config = make_config(
        purpose="Patch the regression at loader.py:128 before shipping."
    )
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(wave_repo, config)
    assert "line-ref lint" in str(exc.value)
    assert not (wave_repo / config.tracked_packet).exists()
    assert _artifact_counts(wave_repo, config.wave_id) == (0, 0, 0)


# --------------------------------------------------------------------------- #
# Fail-closed precondition                                                    #
# --------------------------------------------------------------------------- #


def test_fail_closed_precondition_raises_when_tracker_entry_missing(wave_repo):
    config = make_config()
    # Create the packet but NOT the tracker note: the dispatcher would hold.
    lw.setup_packet(wave_repo, config)
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.verify_fail_closed_precondition(wave_repo, config)
    assert "fail-closed precondition" in str(exc.value)


def test_fail_closed_precondition_passes_after_full_setup(wave_repo):
    config = make_config()
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    # Now the same-wave TASKS entry exists -> no raise.
    lw.verify_fail_closed_precondition(wave_repo, config)


# --------------------------------------------------------------------------- #
# 3-guard verification                                                        #
# --------------------------------------------------------------------------- #


def test_three_guard_verify_raises_when_tracker_note_missing(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.verify_three_guards(wave_repo, config, packet_path)
    assert "guard 3" in str(exc.value)


def test_three_guard_verify_raises_when_founder_override_stripped(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    # Tamper the packet: remove the FOUNDER_OVERRIDE authorization line.
    tampered = packet_path.read_text(encoding="utf-8").replace(
        f"FOUNDER_OVERRIDE:{config.wave_id}", "AUTH REMOVED"
    )
    packet_path.write_text(tampered, encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.verify_three_guards(wave_repo, config, packet_path)
    assert "guard 2" in str(exc.value)


def test_three_guard_verify_passes_after_full_setup(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.verify_three_guards(wave_repo, config, packet_path)  # no raise


# --------------------------------------------------------------------------- #
# Bounded re-run recovery contract                                            #
# --------------------------------------------------------------------------- #


def test_rerun_recovery_converges_after_partial_setup(wave_repo):
    """Partial run (steps 1-2) + full re-run with SAME config -> one of each."""
    config = make_config()
    wave_id = config.wave_id

    # Partial setup: run the packet + tracker-note steps, then abort.
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 0)

    # Re-run the full chain with the SAME wave-config.
    lw.run_wave_setup(wave_repo, make_config())
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)

    # Re-running again stays convergent (idempotent).
    lw.run_wave_setup(wave_repo, make_config())
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)


def test_rerun_recovery_after_partial_routing(wave_repo):
    """Abort after the routing step; re-run converges with no duplicate."""
    config = make_config()
    wave_id = config.wave_id

    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.setup_routing_record(wave_repo, config)
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)

    lw.run_wave_setup(wave_repo, make_config())
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)


def test_each_artifact_step_is_individually_idempotent(wave_repo):
    config = make_config()
    wave_id = config.wave_id

    # Run each artifact step twice; none may duplicate its artifact.
    lw.setup_packet(wave_repo, config)
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.setup_routing_record(wave_repo, config)
    lw.setup_routing_record(wave_repo, config)

    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)


def test_packet_content_is_byte_stable_across_reruns(wave_repo):
    config = make_config()
    first = lw.setup_packet(wave_repo, config).read_text(encoding="utf-8")
    second = lw.setup_packet(wave_repo, make_config()).read_text(encoding="utf-8")
    assert first == second


# --------------------------------------------------------------------------- #
# bridge_config sync convergence                                              #
# --------------------------------------------------------------------------- #


def test_bridge_config_sync_is_noop_when_absent(wave_repo):
    # No bridge_config.json on this bus -> graceful no-op (safe to re-run).
    assert lw.setup_bridge_config(wave_repo) is None
    assert lw.setup_bridge_config(wave_repo) is None


def test_bridge_config_sync_converges(wave_repo):
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text(
        json.dumps(
            {
                "agents": {
                    "claude": {
                        "cmd": ["claude", "--model", "stale-model"],
                        "display_name": "Claude",
                        "mode": "review",
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    path1 = lw.setup_bridge_config(wave_repo)
    after_first = (bus / "bridge_config.json").read_text(encoding="utf-8")
    path2 = lw.setup_bridge_config(wave_repo)
    after_second = (bus / "bridge_config.json").read_text(encoding="utf-8")

    assert path1 == path2  # idempotent target
    assert after_first == after_second  # converged: second run is a no-op


def test_setup_bridge_config_fails_closed_on_malformed_json(wave_repo):
    """Bridge round 2 DEFECT: a PRESENT-but-malformed bridge_config must NOT be
    silently skipped as if absent; the setup must fail closed.

    The sync builder returns the same None for an absent file (the intended
    no-op) and for a present-but-unparseable file; the launcher splits those so a
    broken live config can never be reported as a clean setup.
    """
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_bridge_config(wave_repo)
    msg = str(exc.value)
    assert "bridge_config" in msg
    assert "malformed" in msg or "unreadable" in msg


def test_setup_bridge_config_fails_closed_on_non_object(wave_repo):
    """A present bridge_config lacking an 'agents' object is malformed for sync
    purposes -> fail closed, not a silent skip."""
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text('{"no_agents_key": 1}', encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_bridge_config(wave_repo)
    assert "agents" in str(exc.value)


def test_run_wave_setup_fails_closed_on_malformed_bridge_config(wave_repo):
    """End-to-end: a malformed live bridge_config fails the WHOLE setup closed.

    Directly refutes the bridge round 2 repro, where run_wave_setup returned
    raised=false / bridge_config_path=null / precondition_ok=true / guards_ok=true
    over a malformed config. The launcher must raise instead, and must NOT touch
    the broken file (no silent rewrite).
    """
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(wave_repo, make_config())
    # The broken file is left untouched (not silently rewritten or "repaired").
    assert (bus / "bridge_config.json").read_text(encoding="utf-8") == "{not valid json"


def test_rerun_recovers_after_malformed_bridge_config_fixed(wave_repo):
    """The fail-closed bridge_config step composes with the re-run recovery.

    A malformed bridge_config fails step 4 closed AFTER steps 1-3 wrote their
    artifacts (simple-sequential, no rollback). Fixing the file and re-running the
    SAME config converges to exactly one canonical copy of each artifact -- the
    bounded re-run recovery contract, now with the new fail-closed step in line.
    """
    config = make_config()
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text("{not valid json", encoding="utf-8")

    # First run fails closed at the bridge_config step (after packet/note/routing).
    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(wave_repo, config)
    # Steps 1-3 already persisted their artifacts -> one of each, no duplicates.
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)

    # Fix the bridge_config, re-run the SAME config -> converges (still one each).
    (bus / "bridge_config.json").write_text(
        json.dumps(
            {"agents": {"claude": {"cmd": ["claude"], "display_name": "C",
                                   "mode": "review"}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    result = lw.run_wave_setup(wave_repo, make_config())
    assert result.bridge_config_path is not None
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)


# --------------------------------------------------------------------------- #
# Optional dispatcher launch                                                  #
# --------------------------------------------------------------------------- #


def test_launch_off_by_default_runs_no_subprocess(wave_repo):
    calls = []

    def runner(*a, **k):
        calls.append((a, k))
        raise AssertionError("runner must not be called when launch is off")

    result = lw.run_wave_setup(wave_repo, make_config(), runner=runner)
    assert calls == []
    assert result.launch["launched"] is False
    assert result.launch["command"][0] == sys.executable
    assert "executor_dispatch.py" in result.launch["command"][1]
    # Routing-mode argv, NOT the flat --wave-id/--plan form the dispatcher rejects.
    assert "--routing-record" in result.launch["command"]
    assert "--wave-id" not in result.launch["command"]
    assert "--plan" not in result.launch["command"]


def test_launch_invokes_runner_when_enabled(wave_repo):
    calls = []

    class _R:
        returncode = 0

    def runner(cmd, **k):
        calls.append(cmd)
        return _R()

    result = lw.run_wave_setup(
        wave_repo, make_config(), launch=True, runner=runner
    )
    assert len(calls) == 1
    assert "executor_dispatch.py" in calls[0][1]
    assert "--routing-record" in calls[0]
    assert result.launch["launched"] is True
    assert result.launch["returncode"] == 0


def test_dispatch_command_targets_dispatcher_routing_mode(wave_repo):
    """The launch argv must be the dispatcher's routing-mode form.

    executor_dispatch exposes surface subcommands (phase-a/phase-b/...) and a
    default routing mode (``--routing-record <path>``). It has NO ``--wave-id``
    or top-level ``--plan`` flag and rejects them (bridge round 1 DEFECT). The
    builder must emit routing mode pointed at the same routing record the
    routing step writes, so the dispatcher consumes the record and routes to
    Phase A.
    """
    config = make_config()
    cmd = lw.build_dispatch_command(wave_repo, config)

    assert cmd[0] == sys.executable
    assert cmd[1].endswith("executor_dispatch.py")
    assert "--routing-record" in cmd
    # The argv carries the exact record path the routing step writes/reads.
    routing_path = str(ec.routing_record_path(wave_repo))
    assert cmd[cmd.index("--routing-record") + 1] == routing_path
    # The first token after the program is NOT a surface subcommand, so the
    # dispatcher takes its routing-mode branch.
    assert cmd[2] not in {"phase-a", "phase-b", "pre-commit-supervisor",
                          "commit", "post-merge-supervisor"}
    # None of the dispatcher-rejected flat flags are present.
    assert "--wave-id" not in cmd
    assert "--plan" not in cmd


def test_dispatch_command_threads_bus_dir(wave_repo):
    """A bus_dir override is forwarded to the dispatcher and the record path."""
    cmd = lw.build_dispatch_command(wave_repo, make_config(), bus_dir=".agent_bus-x7")
    assert "--bus-dir" in cmd
    assert cmd[cmd.index("--bus-dir") + 1] == ".agent_bus-x7"
    routing_path = str(ec.routing_record_path(wave_repo, ".agent_bus-x7"))
    assert cmd[cmd.index("--routing-record") + 1] == routing_path


def test_launch_fails_closed_on_dispatcher_failure(wave_repo):
    """A non-zero dispatcher returncode must raise, not report a launch.

    Bridge round 1 DEFECT: a failed dispatcher subprocess was reported as a
    completed launch ({'launched': True, 'returncode': 99}). The launcher must
    fail closed so a failed dispatcher can never look like a launched wave.
    """
    class _R:
        returncode = 99

    def runner(cmd, **k):
        return _R()

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(wave_repo, make_config(), launch=True, runner=runner)
    assert "dispatcher launch failed" in str(exc.value)
    assert "99" in str(exc.value)


def test_maybe_launch_fails_closed_on_none_returncode(wave_repo):
    """A runner result with no/None returncode also fails closed (not a launch)."""
    class _R:
        returncode = None

    with pytest.raises(lw.LaunchWaveError):
        lw.maybe_launch_dispatcher(
            wave_repo, make_config(), launch=True, runner=lambda *a, **k: _R()
        )


# --------------------------------------------------------------------------- #
# Config + CLI                                                                #
# --------------------------------------------------------------------------- #


def test_config_validation_rejects_underscore_wave_id():
    config = make_config(
        wave_id="bad_wave_id",
        tracked_packet="reports/control_plane/bad_wave_id_2026-06-19.md",
    )
    errors = config.validate()
    assert any("normalized kebab id" in e for e in errors)


def test_config_validation_rejects_asterisk_title():
    config = make_config(title="Bad *Title*")
    assert any("asterisk-free" in e for e in config.validate())


def test_config_requires_explicit_date_no_wall_clock():
    """Bridge round 2 DEFECT: the builder must never derive 'date' from the wall
    clock -- that drifts tracked_packet across calendar days and orphans the
    earlier packet on a re-run. 'date' is a required, explicit input, and the
    module carries no wall-clock dependency at all.
    """
    # The module no longer imports/holds a wall clock (nothing to read or mock).
    assert not hasattr(lw, "datetime")

    # from_dict without 'date' -> missing required key (fail-closed), same class
    # of error as any other required field.
    data = dataclasses.asdict(make_config())
    data.pop("date", None)
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.WaveConfig.from_dict(data)
    assert "missing required key" in str(exc.value)
    assert "date" in str(exc.value)


def test_config_rejects_blank_date():
    """A blank/whitespace date fails closed (no silent wall-clock fallback)."""
    with pytest.raises(lw.LaunchWaveError) as exc:
        make_config(date="")
    assert "date" in str(exc.value)
    with pytest.raises(lw.LaunchWaveError):
        make_config(date="   ")


def test_tracked_packet_is_deterministic_from_config_date():
    """The same config yields the same tracked_packet no matter when it runs.

    Refutes the cross-UTC-day duplicate packet: with date an explicit input (not
    the wall clock), the derived packet path is identical across re-constructions,
    so a re-run of the SAME config can never produce a second, date-shifted
    packet. A different explicit date is still honored deterministically.
    """
    p1 = make_config(date="2026-06-19").tracked_packet
    p2 = make_config(date="2026-06-19").tracked_packet
    assert (
        p1 == p2 == "reports/control_plane/demo-launcher-wave-2026-06-19_2026-06-19.md"
    )
    p3 = make_config(date="2026-06-20").tracked_packet
    assert p3 == "reports/control_plane/demo-launcher-wave-2026-06-19_2026-06-20.md"
    assert p3 != p1


def test_run_wave_setup_rejects_invalid_config(wave_repo):
    config = make_config(title="Bad *Title*")
    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(wave_repo, config)


def test_from_dict_rejects_unknown_key():
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.WaveConfig.from_dict({"wave_id": "w", "bogus": 1})
    assert "unknown key" in str(exc.value)


def test_from_dict_rejects_missing_required_key():
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.WaveConfig.from_dict({"wave_id": "demo-wave-2026-06-19"})
    assert "missing required key" in str(exc.value)


def test_cli_main_runs_setup_from_json_config(wave_repo, capsys):
    config = make_config()
    config_dict = {
        "wave_id": config.wave_id,
        "title": config.title,
        "task_id": config.task_id,
        "purpose": config.purpose,
        "wave_class": config.wave_class,
        "target_gate_id": config.target_gate_id,
        "primary_blocker_class": config.primary_blocker_class,
        "primary_invariant_id": config.primary_invariant_id,
        "indicator_artifact_ref": config.indicator_artifact_ref,
        "indicator_collection_command": config.indicator_collection_command,
        "evidence_command": config.evidence_command,
        "evidence_delta": config.evidence_delta,
        "progress_proof_before": config.progress_proof_before,
        "progress_proof_after": config.progress_proof_after,
        "work_items": config.work_items,
        "constraints": config.constraints,
        "stop_conditions": config.stop_conditions,
        "acceptance_criteria": config.acceptance_criteria,
        "date": config.date,
    }
    config_file = wave_repo / "wave_config.json"
    config_file.write_text(json.dumps(config_dict), encoding="utf-8")

    rc = lw.main([str(config_file), "--repo-root", str(wave_repo)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["wave_id"] == config.wave_id
    assert out["precondition_ok"] is True
    assert out["guards_ok"] is True
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)
