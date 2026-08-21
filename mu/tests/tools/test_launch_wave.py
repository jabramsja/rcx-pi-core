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
import sqlite3
import subprocess
import sys
from pathlib import Path

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
_DISPATCHER_OVERRIDE_ENV_KEYS_FOR_TEST = (
    ec.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV,
    "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE",
    *(
        key
        for env_keys in ec.ROLE_AGENT_ENV_VARS.values()
        for key in env_keys
    ),
)


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


def _phase_b_packet_content(config):
    content = lw.render_wave_packet(config)
    content = content.replace(
        "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)",
        "Status: Phase B (pre-supervisor pending, bridge-converged)",
    )
    content = content.replace("Phase-A-Lock: UNLOCKED", "Phase-A-Lock: LOCKED")
    content += (
        "\n<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
        "## Phase B Indicator Scope Reconciliation\n\n"
        f"- Refresh wave: `{config.wave_id}`\n"
        f"- Active packet: `{config.tracked_packet}`\n"
        "- Purpose: Phase B mechanically collected and staged same-wave scope "
        "before pre-commit supervisor review.\n"
        "- Authorized staged files:\n"
        "  - `TASKS.md`\n"
        "  - `mu/tools/executors/phase_b_executor.py`\n"
        "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
    )
    return content


def _tracker_note_line(content, wave_id):
    matches = [
        line
        for line in content.splitlines()
        if line.startswith("- Tracker sync note ") and f", {wave_id}):" in line
    ]
    assert len(matches) == 1
    return matches[0]


def _phase_b_tracker_note_line(note_line):
    note_line = note_line.replace(
        "**Demo Launcher Wave 2026-06-19.**",
        "**NEXT-CODEX-POST-REDTEAM - Phase B pre-commit supervisor package.**",
    )
    note_line = note_line.replace(
        "evidence_delta: New builder mechanizes the setup.",
        "evidence_delta: (1) Phase B converged on the locked plan. "
        "(2) Final pytest gate covered wave-owned files. "
        "scope_refs: `TASKS.md`, `mu/tools/executors/phase_b_executor.py`.",
    )
    note_line = note_line.replace(
        "progress_proof_after: builder exists.",
        "progress_proof_after: Phase B staged a canonical tracker note before "
        "pre-commit supervisor validation; reentry=true.",
    )
    return note_line


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


def _write_bridge_config(repo, agents):
    path = ec.bridge_config_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"agents": agents}, indent=2) + "\n", encoding="utf-8")
    return path


def _authority_allowlist(config):
    return [
        "TASKS.md",
        config.tracked_packet,
        _authority_indicator_ref(config),
        "mu/tools/executors/candidate_authority.py",
    ]


def _authority_indicator_ref(config):
    return f"reports/l4_wave_indicators/{config.wave_id}.json"


def _authority_indicator_command(config):
    indicator_ref = _authority_indicator_ref(config)
    return (
        "python3 tools/metrics/collect_l4_wave_indicators.py "
        f"--wave-id {config.wave_id} --output {indicator_ref}"
    )


def _write_fake_indicator_collector(repo):
    collector = repo / "tools" / "metrics" / "collect_l4_wave_indicators.py"
    collector.parent.mkdir(parents=True, exist_ok=True)
    collector.write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "p=argparse.ArgumentParser(); p.add_argument('--wave-id', required=True); "
        "p.add_argument('--output', required=True); a=p.parse_args()\n"
        "out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_text(json.dumps({'wave_id': a.wave_id}, sort_keys=True)+'\\n')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "--", str(collector.relative_to(repo))], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "collector"], cwd=repo, check=True)
    return collector


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
    assert "candidate_authority" not in routing
    assert "candidate_authority_required" not in routing
    assert result.candidate_authority_spec_path is None


def test_authority_config_writes_bus_local_spec(wave_repo):
    config = make_config()
    comparison_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=wave_repo,
        text=True,
    ).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=comparison_commit,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
        precommit_inventory=True,
    )

    result = lw.run_wave_setup(wave_repo, config, bus_dir=".agent_bus-authority")

    spec_path = Path(result.candidate_authority_spec_path)
    assert spec_path.is_file()
    assert ".agent_bus-authority" in str(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["wave_id"] == config.wave_id
    assert spec["comparison_commit"] == comparison_commit
    assert spec["candidate_allowlist"] == sorted(_authority_allowlist(config))
    assert spec["indicator_artifact_ref"] == config.indicator_artifact_ref
    routing = json.loads(
        (
            wave_repo / ".agent_bus-authority" / "meta" / "post_merge_routing.json"
        ).read_text(encoding="utf-8")
    )
    assert routing["candidate_authority_required"] is True
    authority = routing["candidate_authority"]
    assert authority["required"] is True
    assert authority["precommit_inventory"] is True
    assert authority["spec_path"] == str(spec_path)
    identity = authority["spec_identity"]
    assert identity["identity_version"] == 1
    assert identity["wave_id"] == config.wave_id
    assert identity["comparison_commit"] == comparison_commit
    assert identity["candidate_allowlist"] == sorted(_authority_allowlist(config))
    assert identity["candidate_allowlist_hash"]
    assert identity["plan_path"] == config.tracked_packet
    assert identity["indicator_artifact_ref"] == config.indicator_artifact_ref
    assert identity["indicator_collection_command"] == config.indicator_collection_command
    assert identity["authority_required"] is True
    assert identity["spec_hash"]
    assert "target_branch_authority" not in authority


def test_authority_scope_guard_runs_before_l4_indicator_prestage(wave_repo):
    _write_fake_indicator_collector(wave_repo)
    config = make_config()
    comparison_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=wave_repo,
        text=True,
    ).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=comparison_commit,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    (wave_repo / "outside.txt").write_text("outside scope\n", encoding="utf-8")

    with pytest.raises(lw.LaunchWaveError, match="before L4 indicator pre-stage") as excinfo:
        lw.run_wave_setup(wave_repo, config, bus_dir=".agent_bus-authority")

    assert "outside.txt" in str(excinfo.value)
    assert not (wave_repo / config.indicator_artifact_ref).exists()


def test_authority_config_records_launch_owned_restart_branch(wave_repo):
    config = make_config()
    comparison_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=wave_repo,
        text=True,
    ).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=comparison_commit,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    target_branch = f"jabramsja/{config.wave_id}-restart-20260821"
    subprocess.run(
        ["git", "checkout", "-q", "-b", target_branch],
        cwd=wave_repo,
        check=True,
    )

    lw.run_wave_setup(wave_repo, config, bus_dir=".agent_bus-authority")

    routing = json.loads(
        (
            wave_repo / ".agent_bus-authority" / "meta" / "post_merge_routing.json"
        ).read_text(encoding="utf-8")
    )
    assert routing["candidate_authority"]["target_branch_authority"] == {
        "source": "launch_current_branch",
        "branch_prefix": "jabramsja",
        "target_branch": target_branch,
    }


def test_authority_config_validation_fails_closed_on_bad_schema(wave_repo):
    config = make_config()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit="not-a-commit",
        candidate_allowlist=["TASKS.md", "TASKS.md"],
        pre_review_authority=True,
    )

    errors = config.validate(wave_repo)

    assert any("duplicate candidate allowlist path" in error for error in errors)
    assert any("invalid comparison_commit" in error for error in errors)


def test_authority_config_accepts_hyphenated_aliases(wave_repo):
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=wave_repo, text=True).strip()
    raw = dataclasses.asdict(make_config())
    probe = lw.WaveConfig.from_dict(raw)
    raw["indicator_artifact_ref"] = _authority_indicator_ref(probe)
    raw["indicator_collection_command"] = _authority_indicator_command(probe)
    raw.pop("comparison_commit", None)
    raw.pop("candidate_allowlist", None)
    raw.pop("pre_review_authority", None)
    raw.pop("precommit_inventory", None)
    raw["comparison-commit"] = base
    raw["candidate-allowlist"] = _authority_allowlist(probe)
    raw["pre-review-authority"] = True
    raw["precommit-inventory"] = True

    config = lw.WaveConfig.from_dict(raw)

    assert config.comparison_commit == base
    assert config.candidate_allowlist == _authority_allowlist(config)
    assert config.pre_review_authority is True
    assert config.precommit_inventory is True


def test_prepare_review_refuses_when_reviewer_active(wave_repo):
    config = make_config()
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=wave_repo, text=True).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=base,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    db = wave_repo / ".agent_bus-active" / "bridge.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE jobs (job_id TEXT, status TEXT)")
    conn.execute("INSERT INTO jobs VALUES ('phase-b-r1-active', 'REVIEWER_RUNNING')")
    conn.commit()
    conn.close()

    with pytest.raises(lw.LaunchWaveError, match="reviewer job"):
        lw.prepare_review_authority(
            wave_repo,
            config,
            bus_dir=".agent_bus-active",
            phase="phase_b",
            review_round="manual-recovery",
        )


def test_prepare_review_uses_shared_builder_without_launching(wave_repo):
    _write_fake_indicator_collector(wave_repo)
    config = make_config()
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=wave_repo, text=True).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=base,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    (wave_repo / "mu" / "tools" / "executors").mkdir(parents=True, exist_ok=True)
    (wave_repo / "mu" / "tools" / "executors" / "candidate_authority.py").write_text(
        "# candidate\n",
        encoding="utf-8",
    )

    result = lw.prepare_review_authority(
        wave_repo,
        config,
        bus_dir=".agent_bus-authority",
        phase="phase_b",
        review_round="manual-recovery",
    )

    assert result["prepared"] is True
    assert Path(result["authority_spec_path"]).is_file()
    assert Path(result["receipt_path"]).is_file()
    assert (wave_repo / config.indicator_artifact_ref).is_file()


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
# Founder-override propagation into the routing record                        #
# --------------------------------------------------------------------------- #


def test_routing_record_carries_founder_override_for_commit_autobump(wave_repo):
    """The launcher threads the wave's FOUNDER_OVERRIDE into the routing record.

    Regression for the gate-authoring strand: a wave that adds a governed test
    file and DECLARES a FOUNDER_OVERRIDE still stranded at the commit-executor
    Step-5e growth-cap auto-bump, because ``setup_routing_record`` never passed
    ``config.founder_override`` to ``build_and_write_routing_record``. The record
    then carried no ``founder_override`` field and the commit flow's
    ``_extract_founder_override_from_routing_record`` returned "" -> the auto-bump
    fail-closed ``no_founder_override``. The launcher must make the declared
    override durable in the routing record so the extractor returns a non-empty
    token (the same token Gate 8 validates).
    """
    config = make_config()
    lw.setup_packet(wave_repo, config)  # routing builder validates the packet exists
    record = lw.setup_routing_record(wave_repo, config)

    # config.founder_override defaults to the wave_id (the declared override).
    assert config.founder_override == config.wave_id

    # The returned record AND the persisted record both carry the override.
    assert record["founder_override"] == config.founder_override
    on_disk = json.loads(
        (wave_repo / ".agent_bus" / "meta" / "post_merge_routing.json").read_text(
            encoding="utf-8"
        )
    )
    assert on_disk["founder_override"] == config.founder_override

    # The commit-flow extractor returns the wave's token from that record — the
    # token the Step-5e growth-cap auto-bump needs (non-empty -> not stranded).
    # Asserted directly against commit_executor's module-private extractor (the
    # field-name contract under test): the packet forbids changing commit_executor,
    # so we do NOT add a public seam; instead the ANTICHEAT_OK escape hatch mirrors
    # test_executor_dispatch.py, which unit-tests this same module's internal
    # parsers (check_private_attr_access.py allows private access on such lines).
    import commit_executor as ce  # executors dir is on sys.path (module top)

    assert ce._extract_founder_override_from_routing_record(on_disk, wave_repo) == config.founder_override  # ANTICHEAT_OK: regression locks the launcher-written founder_override as the exact field the commit-flow extractor (Step-5e auto-bump source) reads


def test_routing_record_omits_founder_override_when_builder_not_threaded(wave_repo):
    """Backward-compat: the optional param defaults empty, so existing direct
    callers and records are byte-unchanged (no ``founder_override`` key emitted),
    and threading a non-empty override adds exactly that one key.
    """
    config = make_config()
    lw.setup_packet(wave_repo, config)  # a valid tracked_packet must exist on disk

    # Direct builder call WITHOUT founder_override == every existing caller today.
    record, errors = ec.build_post_merge_routing_record(
        wave_name=config.wave_id,
        task_id=config.task_id,
        tracked_packet=config.tracked_packet,
        request_for_claude=config.request_for_claude,
        request_for_agent=config.request_for_agent,
        summary=config.routing_summary,
        repo_root=wave_repo,
    )
    assert errors == []
    assert "founder_override" not in record

    # Threading a non-empty override adds exactly that key (the bare token).
    threaded, threaded_errors = ec.build_post_merge_routing_record(
        wave_name=config.wave_id,
        task_id=config.task_id,
        tracked_packet=config.tracked_packet,
        request_for_claude=config.request_for_claude,
        request_for_agent=config.request_for_agent,
        summary=config.routing_summary,
        repo_root=wave_repo,
        founder_override=config.founder_override,
    )
    assert threaded_errors == []
    assert threaded["founder_override"] == config.founder_override


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


def test_setup_packet_preserves_locked_phase_b_packet_on_rerun(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    advanced = _phase_b_packet_content(config)
    packet_path.write_text(advanced, encoding="utf-8")

    rerun_path = lw.setup_packet(wave_repo, make_config())

    assert rerun_path == packet_path
    assert packet_path.read_text(encoding="utf-8") == advanced


def test_setup_packet_restores_staged_phase_b_packet_after_worktree_clobber(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    advanced = _phase_b_packet_content(config)
    packet_path.write_text(advanced, encoding="utf-8")
    _git(wave_repo, "add", config.tracked_packet)

    packet_path.write_text(lw.render_wave_packet(config), encoding="utf-8")
    assert "Phase-A-Lock: UNLOCKED" in packet_path.read_text(encoding="utf-8")

    lw.setup_packet(wave_repo, make_config())

    assert packet_path.read_text(encoding="utf-8") == advanced


def test_setup_tracker_note_restores_staged_phase_b_note_after_worktree_clobber(wave_repo):
    config = make_config()
    lw.setup_tracker_note(wave_repo, config)
    tasks_path = wave_repo / "TASKS.md"
    initial = tasks_path.read_text(encoding="utf-8")
    initial_note = _tracker_note_line(initial, config.wave_id)
    advanced_note = _phase_b_tracker_note_line(initial_note)
    advanced = initial.replace(initial_note, advanced_note)
    tasks_path.write_text(advanced, encoding="utf-8")
    _git(wave_repo, "add", "TASKS.md")

    tasks_path.write_text(initial, encoding="utf-8")
    assert "scope_refs:" not in tasks_path.read_text(encoding="utf-8")

    lw.setup_tracker_note(wave_repo, make_config())

    assert tasks_path.read_text(encoding="utf-8") == advanced


def test_setup_tracker_note_restores_staged_phase_b_note_when_worktree_note_missing(wave_repo):
    config = make_config(wave_id="demo-wave-2026-06-27")
    lw.setup_tracker_note(wave_repo, config)
    tasks_path = wave_repo / "TASKS.md"
    initial = tasks_path.read_text(encoding="utf-8")
    initial_note = _tracker_note_line(initial, config.wave_id)
    advanced_note = _phase_b_tracker_note_line(initial_note)
    advanced = initial.replace(initial_note, advanced_note)
    tasks_path.write_text(advanced, encoding="utf-8")
    _git(wave_repo, "add", "TASKS.md")

    missing_note = initial.replace(initial_note + "\n", "")
    tasks_path.write_text(missing_note, encoding="utf-8")
    assert f", {config.wave_id}):" not in tasks_path.read_text(encoding="utf-8")

    lw.setup_tracker_note(wave_repo, config)

    restored = tasks_path.read_text(encoding="utf-8")
    assert _tracker_note_line(restored, config.wave_id) == advanced_note
    assert restored.count(f", {config.wave_id}):") == 1
    assert "scope_refs:" in restored


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


def test_setup_bridge_config_auto_seeds_fresh_namespaced_bus(wave_repo):
    """PIPELINE-FIX-33: a fresh namespaced bus with NO bridge_config is seeded from
    the canonical default bus, then synced -- no manual pre-seed needed.

    Before this fix, launching a wave on a fresh worktree required the orchestrator
    to hand-run ensure_bridge_config_path + sync first, because setup_bridge_config
    no-op'd over the absent namespaced config. Now setup_bridge_config seeds it from
    the trusted same-repo default and returns the namespaced path with agents present.
    """
    # Trusted seed source: the canonical default-bus bridge_config.
    default_bus = wave_repo / ".agent_bus"
    default_bus.mkdir(exist_ok=True)
    (default_bus / "bridge_config.json").write_text(
        json.dumps(
            {
                "agents": {
                    "claude": {
                        "cmd": ["claude", "--model", "seed-model"],
                        "display_name": "Claude",
                        "mode": "review",
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    namespaced = ec.bridge_config_path(wave_repo, ".agent_bus-x7")
    assert not namespaced.exists()  # fresh bus: no bridge_config of its own yet

    result = lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7")

    # Seeded into the namespaced bus and synced -> returns that bus's path with the
    # configured agent present (no manual ensure+sync pre-step was needed).
    assert result == namespaced
    assert namespaced.exists()
    seeded = json.loads(namespaced.read_text(encoding="utf-8"))
    assert isinstance(seeded.get("agents"), dict)
    assert "claude" in seeded["agents"]

    # A second run over the now-healthy seeded config converges (no-op-equivalent):
    # the seeder short-circuits on the present file and the sync stays idempotent.
    result2 = lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7")
    assert result2 == namespaced
    assert "claude" in json.loads(namespaced.read_text(encoding="utf-8"))["agents"]


def test_setup_bridge_config_auto_seed_does_not_overwrite_present_malformed(wave_repo):
    """The auto-seed must NOT weaken the present-but-malformed fail-closed.

    Even with a valid trusted seed source available, a PRESENT-but-malformed
    bridge_config on the active bus is left untouched (the seeder short-circuits on
    an existing file) and still fails the setup closed -- it is never silently
    overwritten or 'repaired' by the seed.
    """
    # A valid trusted seed source exists on the default bus...
    default_bus = wave_repo / ".agent_bus"
    default_bus.mkdir(exist_ok=True)
    (default_bus / "bridge_config.json").write_text(
        json.dumps(
            {"agents": {"claude": {"cmd": ["claude"], "display_name": "C",
                                   "mode": "review"}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    # ...but the active namespaced bus already has a MALFORMED bridge_config.
    namespaced = ec.bridge_config_path(wave_repo, ".agent_bus-x7")
    namespaced.parent.mkdir(parents=True, exist_ok=True)
    namespaced.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7")
    msg = str(exc.value)
    assert "bridge_config" in msg
    assert "malformed" in msg or "unreadable" in msg

    # The malformed file was NOT overwritten by the seed (left byte-identical).
    assert namespaced.read_text(encoding="utf-8") == "{not valid json"


def test_setup_bridge_config_noop_when_no_seed_source_on_namespaced_bus(wave_repo):
    """Genuine no-source case still no-ops on a fresh namespaced bus.

    With NO trusted seed source available (no default-bus bridge_config and no other
    source), the seeder copies nothing, so setup_bridge_config returns None and
    creates no file -- and re-running stays a no-op.
    """
    namespaced = ec.bridge_config_path(wave_repo, ".agent_bus-x7")
    assert not namespaced.exists()

    assert lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7") is None
    assert not namespaced.exists()  # the seeder created nothing
    assert lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7") is None


def test_launch_max_turns_updates_existing_bridge_token(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            }
        },
    )

    result = lw.run_wave_setup(
        wave_repo,
        make_config(implementer_agent="claude", reviewer_agent="claude", max_turns=42),
    )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    cmd = bridge["agents"]["claude"]["cmd"]
    assert cmd.count("--max-turns") == 1
    assert cmd[cmd.index("--max-turns") + 1] == "42"
    assert result.launch["launch_overrides"] == {
        "implementer_agent": "claude",
        "reviewer_agent": "claude",
        "max_turns": 42,
    }
    assert result.launch["bridge_max_turns_override"]["agents"] == ["claude"]


def test_launch_max_turns_appends_to_claude_bridge_command_without_token(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--model", "claude-opus-4-8"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            }
        },
    )

    result = lw.run_wave_setup(
        wave_repo,
        make_config(
            implementer_agent="claude",
            reviewer_agent="claude",
            max_turns=37,
        ),
    )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    cmd = bridge["agents"]["claude"]["cmd"]
    assert cmd[-2:] == ["--max-turns", "37"]
    assert cmd.count("--max-turns") == 1
    assert result.launch["launch_overrides"] == {
        "implementer_agent": "claude",
        "reviewer_agent": "claude",
        "max_turns": 37,
    }
    assert result.launch["bridge_max_turns_override"]["max_turns"] == 37
    assert result.launch["bridge_max_turns_override"]["agents"] == ["claude"]


def test_launch_max_turns_rejects_codex_exec_without_verified_override(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "codex": {
                "mode": "live",
                "display_name": "Codex",
                "cmd": [
                    "codex",
                    "exec",
                    "-",
                    "--json",
                    "-m",
                    "gpt-5.5",
                    "-c",
                    'model_reasoning_effort="xhigh"',
                    "--sandbox",
                    "danger-full-access",
                ],
                "prompt_via_stdin": True,
                "timeout_s": 1200,
                "env": {},
            }
        },
    )

    config = make_config(
        implementer_agent="codex",
        reviewer_agent="codex",
        pager_route="codex",
        max_turns=37,
    )

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(wave_repo, config)

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    cmd = bridge["agents"]["codex"]["cmd"]
    assert "--max-turns" not in cmd
    assert "max_turns=37" not in cmd
    assert "codex" in str(exc.value)
    assert "verified max-turn override" in str(exc.value)
    assert "support a max-turn override" in str(exc.value)


def test_launch_max_turns_rejects_codex_exec_with_unsupported_token(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "codex": {
                "mode": "live",
                "display_name": "Codex",
                "cmd": ["codex", "exec", "-", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 1200,
                "env": {},
            }
        },
    )

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(
            wave_repo,
            make_config(
                implementer_agent="codex",
                reviewer_agent="codex",
                pager_route="codex",
                max_turns=37,
            ),
        )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    assert bridge["agents"]["codex"]["cmd"] == [
        "codex",
        "exec",
        "-",
        "--max-turns",
        "100",
    ]
    assert "codex" in str(exc.value)
    assert "--max-turns" in str(exc.value)
    assert "support a max-turn override" in str(exc.value)


def test_launch_max_turns_rejects_mixed_agents_without_partial_mutation(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            },
            "custom": {
                "mode": "live",
                "display_name": "Custom",
                "cmd": ["python3", "custom_agent.py"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            },
        },
    )

    config_path = wave_repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "claude", "reviewer": "custom"},
                "bridge_agent_defaults": {"claude": {}, "custom": {}},
                "pipeline_agent_pager": {"enabled": False, "route": "notify-only"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(
            wave_repo,
            make_config(
                implementer_agent="claude",
                reviewer_agent="custom",
                max_turns=42,
            ),
        )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    assert bridge["agents"]["claude"]["cmd"] == [
        "claude",
        "--print",
        "--max-turns",
        "100",
    ]
    assert bridge["agents"]["custom"]["cmd"] == ["python3", "custom_agent.py"]
    assert "custom" in str(exc.value)
    assert "support a max-turn override" in str(exc.value)


def test_launch_max_turns_does_not_mutate_executor_config(wave_repo):
    config_path = wave_repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"role_agents": {"implementer": "claude", "reviewer": "claude"}}),
        encoding="utf-8",
    )
    before = config_path.read_text(encoding="utf-8")
    _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            }
        },
    )

    lw.run_wave_setup(wave_repo, make_config(max_turns=55))

    assert config_path.read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------- #
# L4 indicator pre-stage (kills the agent_review_crash indicator-absent strand) #
# --------------------------------------------------------------------------- #

_PRESTAGE_WARNING = "L4 indicator pre-stage skipped"


def _staged_paths(repo):
    """Return the list of paths currently staged in the index (vs HEAD)."""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    return out.split()


def _write_indicator_generator(repo):
    """Write a generator the wave_repo can actually run: it creates the artifact
    at the output path passed as argv[1] (stands in for the canonical collector,
    which is absent from the tmp repo)."""
    gen = repo / "gen_indicator.py"
    gen.write_text(
        "import json, os, sys\n"
        "out = sys.argv[1]\n"
        "os.makedirs(os.path.dirname(out) or '.', exist_ok=True)\n"
        "with open(out, 'w', encoding='utf-8') as fh:\n"
        "    json.dump({'wave_id': 'demo', 'indicator': True}, fh)\n",
        encoding="utf-8",
    )
    return gen


def test_prestage_l4_indicator_collects_and_stages_artifact(wave_repo, capsys):
    """(a) A config WITH an indicator command -> after setup the indicator artifact
    exists on disk AND is staged in the index, so the L4 ``--staged`` contract
    finds it PRESENT at Phase-B review (instead of stranding on indicator-absent).
    """
    _write_indicator_generator(wave_repo)
    artifact_ref = "reports/l4_wave_indicators/demo.json"
    config = make_config(
        indicator_artifact_ref=artifact_ref,
        indicator_collection_command=f"python3 gen_indicator.py {artifact_ref}",
    )

    lw.run_wave_setup(wave_repo, config)

    # Exists on disk AND staged in the git index.
    assert (wave_repo / artifact_ref).is_file()
    assert artifact_ref in _staged_paths(wave_repo)
    # Success path: no fail-open warning was emitted.
    assert _PRESTAGE_WARNING not in capsys.readouterr().err


def test_prestage_l4_indicator_fail_open_on_nonzero_command(wave_repo, capsys):
    """(b) A config whose indicator command exits non-zero -> setup still SUCCEEDS
    (fail-open): the whole launch completes, a warning is logged, and the launch is
    NOT aborted. commit_executor Step 5 remains the commit-time authority.
    """
    artifact_ref = "reports/l4_wave_indicators/demo.json"
    config = make_config(
        indicator_artifact_ref=artifact_ref,
        # A command that always fails -> exercises the fail-open path.
        indicator_collection_command='python3 -c "import sys; sys.exit(3)"',
    )

    # MUST NOT raise: a failing pre-stage can never abort a wave launch.
    result = lw.run_wave_setup(wave_repo, config)
    assert result.precondition_ok is True
    assert result.guards_ok is True
    assert result.launch["launched"] is False

    # Fail-open warning emitted, and nothing staged (the command failed).
    assert _PRESTAGE_WARNING in capsys.readouterr().err
    assert artifact_ref not in _staged_paths(wave_repo)


def test_prestage_l4_indicator_noop_when_indicator_fields_empty(wave_repo, capsys):
    """(c) A config with empty indicator fields -> a silent no-op: no command is
    run, no warning is logged, and nothing is staged.

    Tested against the helper directly because the full run_wave_setup chain
    requires non-empty indicator fields at the tracker-note step; the no-op is a
    property of the helper itself.
    """
    config = make_config(
        indicator_artifact_ref="",
        indicator_collection_command="",
    )

    lw._prestage_l4_indicator(wave_repo, config)  # ANTICHEAT_OK: unit-tests the launcher's own private helper's declared no-op contract (empty indicator fields), mirroring this module's existing direct-call precedent

    # Silent no-op: no warning, nothing staged, no indicator dir created.
    assert capsys.readouterr().err == ""
    assert _staged_paths(wave_repo) == []
    assert not (wave_repo / "reports" / "l4_wave_indicators").exists()


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


def test_launch_omitted_pins_preserve_runner_environment_shape(wave_repo, monkeypatch):
    for key in _DISPATCHER_OVERRIDE_ENV_KEYS_FOR_TEST:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", str(wave_repo / "parent"))

    calls = []

    class _R:
        returncode = 0

    def runner(cmd, **k):
        calls.append(k)
        return _R()

    config = make_config()
    assert config.implementer_agent == ""
    assert config.reviewer_agent == ""
    assert config.pager_route == ""

    result = lw.run_wave_setup(wave_repo, config, launch=True, runner=runner)

    assert calls == [{"cwd": str(wave_repo)}]
    assert "environment_overrides" not in result.launch


def test_launch_partial_pins_scrub_stale_parent_override_env(wave_repo, monkeypatch):
    monkeypatch.setenv("RCX_IMPLEMENTER_AGENT_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_REVIEWER_AGENT_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_BRIDGE_REVIEWER_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", "/tmp/stale-root")
    monkeypatch.setenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", "claude")
    captured = {}

    class _R:
        returncode = 0

    def runner(cmd, **k):
        captured["kwargs"] = k
        return _R()

    result = lw.run_wave_setup(
        wave_repo,
        make_config(implementer_agent="codex"),
        launch=True,
        runner=runner,
    )

    env = captured["kwargs"]["env"]
    assert env["RCX_IMPLEMENTER_AGENT_OVERRIDE"] == "codex"
    assert env["RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT"] == str(wave_repo.resolve())
    assert "RCX_REVIEWER_AGENT_OVERRIDE" not in env
    assert "RCX_BRIDGE_REVIEWER_OVERRIDE" not in env
    assert "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE" not in env
    assert result.launch["environment_overrides"] == {
        "RCX_IMPLEMENTER_AGENT_OVERRIDE": "codex",
    }


def test_config_accepts_valid_role_and_pager_pins(wave_repo):
    config = make_config(
        implementer_agent="codex",
        reviewer_agent="codex",
        pager_route="codex",
    )
    assert config.validate(wave_repo) == []


def test_config_accepts_valid_max_turns_override(wave_repo):
    assert make_config(max_turns=100).validate(wave_repo) == []


@pytest.mark.parametrize("bad_max_turns", [0, -1, 1.5, "50", True, 1001])
def test_config_rejects_invalid_max_turns_override(wave_repo, bad_max_turns):
    errors = make_config(max_turns=bad_max_turns).validate(wave_repo)
    assert any("max_turns" in error for error in errors)


def test_config_validation_uses_configured_bridge_agent_defaults(wave_repo):
    config_path = wave_repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "bridge_agent_defaults": {
                    "localcodex": {
                        "display_name": "Local Codex",
                        "model": "gpt-local",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert make_config(implementer_agent="localcodex").validate(wave_repo) == []


def test_config_rejects_invalid_role_and_pager_pins(wave_repo):
    config = make_config(
        implementer_agent="missing-impl",
        reviewer_agent="missing-reviewer",
        pager_route="pager-nowhere",
    )

    errors = config.validate(wave_repo)

    assert any("implementer_agent" in error for error in errors)
    assert any("reviewer_agent" in error for error in errors)
    assert any("pager_route" in error for error in errors)


def test_launch_threads_role_and_pager_pins_to_dispatcher_env(wave_repo):
    captured = {}

    class _R:
        returncode = 0

    def runner(cmd, **k):
        captured["cmd"] = cmd
        captured["kwargs"] = k
        return _R()

    result = lw.run_wave_setup(
        wave_repo,
        make_config(
            implementer_agent="codex",
            reviewer_agent="codex",
            pager_route="codex",
        ),
        launch=True,
        runner=runner,
    )

    env = captured["kwargs"]["env"]
    expected = {
        "RCX_IMPLEMENTER_AGENT_OVERRIDE": "codex",
        "RCX_REVIEWER_AGENT_OVERRIDE": "codex",
        "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE": "codex",
    }
    for key, value in expected.items():
        assert env[key] == value
    assert captured["kwargs"]["cwd"] == str(wave_repo)
    assert result.launch["environment_overrides"] == expected
    assert set(result.launch["environment_overrides"]) == set(expected)


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
