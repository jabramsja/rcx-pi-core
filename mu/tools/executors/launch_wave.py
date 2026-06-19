#!/usr/bin/env python3
"""launch_wave: mechanize the full dispatcher-wave setup from one wave-config.

This is the wave-launcher builder. From a single ``WaveConfig`` it runs the
complete per-wave setup as a SIMPLE sequential chain over the existing setup
builders, eliminating the per-wave hand-written setup script (founder directive
ALWAYS USE BUILDERS).

Sequential chain (seven steps, in order):

  1. packet            -- ``phase_a_executor.create_plan_draft`` places/reuses the
                          Phase A packet at its deterministic path; this module
                          then bakes the standard fences into the draft content.
  2. tracker note      -- ``tracker_sync_note.upsert_tracker_sync_note`` writes the
                          TASKS.md tracker-sync note (the canonical L4-field source).
  3. routing record    -- ``executor_common.build_and_write_routing_record`` writes
                          the post-merge routing record (single next-candidate).
  4. bridge_config sync-- ``executor_common.sync_bridge_config_agents_from_defaults``
                          converges the live bridge_config with committed defaults.
  5. fail-closed
     precondition      -- the dispatcher's own pre-Phase-B gate
                          (``executor_dispatch._tasks_tracker_entry_exists``): the
                          TASKS.md tracker entry for (wave_id, packet) MUST exist or
                          this halts, so a launched wave can never be held.
  6. 3-guard verify    -- the three ANDed Phase A pre-lock guards: Scope-mentions-
                          TASKS.md, bare ``FOUNDER_OVERRIDE:<wave_id>``, and a
                          detector-visible TASKS.md tracker note for the wave.
  7. optional launch   -- the dispatcher launch, OFF by default. When enabled it
                          shells out to ``executor_dispatch`` in ROUTING MODE
                          (``--routing-record <path>``, the record step 3 wrote),
                          failing closed on a non-zero dispatcher returncode;
                          otherwise it only returns the command it would run.

Design stance -- SIMPLE SEQUENTIAL, NO TRANSACTIONAL/ROLLBACK LAYER. A partial
run (interrupted after a subset of the artifact-producing steps) is recovered by
re-running the SAME wave-config, NOT by rolling back. The bounded re-run recovery
contract is:

  Re-running with the SAME wave-config is idempotent and convergent. Each of the
  four artifact-producing steps detects its own prior output and leaves exactly
  one canonical copy:
    (a) packet         -- create_plan_draft reuses the wave's packet in place at
                          its deterministic path (one packet, never a duplicate);
                          this module rewrites the fenced content only when it
                          differs from the canonical render.
    (b) tracker note   -- upsert is keyed by wave id; an existing note for the wave
                          id is replaced in place, never re-appended (honoring the
                          tracker-note bleed-forward hazard).
    (c) routing record -- the record file is rewritten with a single next-candidate
                          keyed by wave id (no duplicate candidate).
    (d) bridge_config  -- a converging sync; a second run is a no-op-equivalent.
  The two verification steps and the optional launch persist no artifact, so they
  need no dedup and are safe to re-run. The contract covers exactly these steps
  for the SAME wave-config; it makes NO claim about concurrent runs or a changed
  config.

The builder reuses, rather than re-implements, every setup surface: the packet
draft builder, the tracker-note builder, the routing-record builder, the
bridge_config sync, the dispatcher precondition, the Phase A guards, and the
line-ref lint.

Usage:
  python3 mu/tools/executors/launch_wave.py <wave_config.json> [--repo-root DIR]
                                            [--launch] [--bus-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import MISSING, dataclass, field
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
_CHECKS_DIR = SCRIPT_DIR.parent / "checks"

# Sibling executor modules live in this directory. Inserting it on sys.path lets
# the plain imports below resolve, and lets each imported module resolve its own
# sibling imports (the established executor import pattern, mirrored from
# phase_a_executor's own SCRIPT_DIR insertion).
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import executor_common as _ec  # noqa: E402,I001  (path insert must precede import)
import tracker_sync_note as _tsn  # noqa: E402
import phase_a_executor as _pa  # noqa: E402
import executor_dispatch as _ed  # noqa: E402


def _load_line_ref_checker() -> Any:
    """Load the control-packet line-ref lint module (lives under checks/)."""
    import importlib.util as ilu

    path = _CHECKS_DIR / "check_control_packet_line_refs.py"
    spec = ilu.spec_from_file_location("check_control_packet_line_refs", str(path))
    module = ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_line_ref = _load_line_ref_checker()


class LaunchWaveError(RuntimeError):
    """Raised when the wave launcher cannot complete a setup step."""


# --------------------------------------------------------------------------- #
# Wave config                                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class WaveConfig:
    """The single input that drives the whole dispatcher-wave setup.

    The packet content, the TASKS.md tracker note, and the routing record are all
    derived from this one object. Fields with defaults are optional. ``date`` is
    REQUIRED (an explicit ``YYYY-MM-DD``): the builder never reads the wall clock,
    so the config alone fully determines every output. ``tracked_packet`` is
    derived deterministically from ``wave_id`` + ``date`` when omitted -- a
    wall-clock date would otherwise make the derived packet path drift across
    calendar days and orphan the earlier packet, breaking the bounded re-run
    recovery contract (bridge round 2 DEFECT). Requiring ``date`` keeps every
    re-run of the SAME config convergent regardless of when it runs.
    """

    # Identity
    wave_id: str
    title: str
    task_id: str
    purpose: str
    # Wave date (YYYY-MM-DD), REQUIRED. No wall-clock fallback: an explicit date
    # is what keeps tracked_packet -- and the whole setup -- deterministic across
    # calendar days, so a re-run of the SAME config always converges.
    date: str

    # L4 / tracker-note fields
    wave_class: str
    target_gate_id: str
    primary_blocker_class: str
    primary_invariant_id: str
    indicator_artifact_ref: str
    indicator_collection_command: str

    # Evidence (required for L4_STRUCTURAL + L4_ENABLER tracker notes)
    evidence_command: str = ""
    evidence_delta: str = ""
    progress_proof_before: str = ""
    progress_proof_after: str = ""

    # Class-specific tracker-note fields
    structural_artifact_ref: str = ""
    post_gate_contract_sweep: str = ""
    no_op_proof: str = ""
    defer_reason_code: str = ""

    # Bootstrap / boot0
    boot0_track_id: str = "V1"
    boot0_progress_state: str = "HOLD"

    # Authorization
    founder_override: str = ""  # defaults to wave_id

    # Packet body
    scope_summary: str = ""
    scope_items: list[str] = field(default_factory=list)
    work_items: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    request_for_claude: str = ""
    authorization_note: str = ""
    # Slow kernel functions this wave's tests touch (drives the run_mu # SPEED_OK
    # fence). e.g. ["run_mu"]. Empty for tooling-only waves.
    slow_functions: list[str] = field(default_factory=list)

    # Routing
    routing_decision: str = "ROUTE_PHASE_A"
    routing_summary: str = ""

    # Derived / overridable. tracked_packet defaults to
    # reports/control_plane/{wave_id}_{date}.md and is deterministic because
    # date is a required, explicit input (no wall-clock read).
    tracked_packet: str = ""

    def __post_init__(self) -> None:
        # Fail closed on a missing/blank date instead of reading the wall clock.
        # A wall-clock fallback would derive a different tracked_packet on a later
        # calendar day, orphaning the earlier packet and breaking the bounded
        # re-run recovery contract (bridge round 2 DEFECT). The date must be an
        # explicit, deliberate input so the SAME config always converges.
        if not self.date or not self.date.strip():
            raise LaunchWaveError(
                "wave-config 'date' is required (an explicit YYYY-MM-DD): the "
                "builder never reads the wall clock, because a wall-clock date "
                "would make tracked_packet drift across calendar days and break "
                "the bounded re-run recovery contract."
            )
        if not self.founder_override:
            self.founder_override = self.wave_id
        if not self.tracked_packet:
            self.tracked_packet = (
                f"reports/control_plane/{self.wave_id}_{self.date}.md"
            )
        if not self.request_for_claude:
            self.request_for_claude = self.purpose
        if not self.routing_summary:
            self.routing_summary = self.purpose
        if not self.scope_summary:
            self.scope_summary = self.purpose

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WaveConfig":
        """Build a WaveConfig from a plain dict, rejecting unknown keys."""
        if not isinstance(data, dict):
            raise LaunchWaveError("wave-config must be a JSON object")
        known = {f.name for f in cls.__dataclass_fields__.values()}
        unknown = sorted(set(data) - known)
        if unknown:
            raise LaunchWaveError(f"wave-config has unknown key(s): {unknown}")
        missing = sorted(
            name
            for name, f in cls.__dataclass_fields__.items()
            if f.default is MISSING
            and f.default_factory is MISSING  # type: ignore[misc]
            and name not in data
        )
        if missing:
            raise LaunchWaveError(f"wave-config missing required key(s): {missing}")
        return cls(**data)

    def validate(self) -> list[str]:
        """Return a list of config errors (empty = valid)."""
        errors: list[str] = []
        normalized = _ec.normalize_wave_id(self.wave_id)
        if normalized != self.wave_id:
            errors.append(
                "wave_id must be an already-normalized kebab id "
                f"(got {self.wave_id!r}; normalized form is {normalized!r})"
            )
        if not self.title.strip():
            errors.append("title is required")
        if "*" in self.title:
            errors.append("title must be asterisk-free")
        if not self.task_id.strip():
            errors.append("task_id is required")
        if not self.tracked_packet.startswith("reports/control_plane/"):
            errors.append("tracked_packet must be under reports/control_plane/")
        if not self.tracked_packet.endswith(".md"):
            errors.append("tracked_packet must be a Markdown packet")
        expected_prefix = f"reports/control_plane/{self.wave_id}_"
        if not self.tracked_packet.startswith(expected_prefix):
            errors.append(
                "tracked_packet stem must start with the wave_id: "
                f"expected prefix {expected_prefix!r}"
            )
        return errors


# --------------------------------------------------------------------------- #
# Packet rendering + fences                                                    #
# --------------------------------------------------------------------------- #


def _bullets(items: list[str]) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"- {item}" for item in items)


def _numbered(items: list[str]) -> str:
    if not items:
        return "1. (none)"
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))


def render_wave_packet(config: WaveConfig) -> str:
    """Render a complete, fence-carrying Phase A packet draft from the config.

    The rendered draft is deterministic for a given config (no wall-clock reads),
    which is what makes the packet step idempotent under the re-run contract.

    Baked-in fences:
      * packet-integrity -- the Scope section names TASKS.md, and the Grounding
        section carries a bare ``FOUNDER_OVERRIDE:<wave_id>`` line.
      * line-ref lint    -- no ``<file>.<ext>:<line>`` references (code is cited by
        name); enforced at write time by :func:`_check_packet_fences`.
      * asterisk-free title.
      * run_mu # SPEED_OK -- when the wave touches a slow kernel function, the
        draft documents the in-function ``# SPEED_OK`` annotation, so any run_mu
        mention in the packet is paired with the annotation.
    """
    # Validation-gates section: only emit a run_mu reference when the wave actually
    # touches a slow function, and always pair it with the # SPEED_OK annotation so
    # the fence holds. Tooling-only waves emit no slow-function mention at all.
    validation_lines = [f"- evidence_command: `{config.evidence_command}`"]
    if config.slow_functions:
        slow = ", ".join(f"`{name}`" for name in config.slow_functions)
        validation_lines.append(
            f"- Slow-kernel guard-tests ({slow}) carry an in-function "
            "`# SPEED_OK: <reason>` annotation so they stay out of the green-gate "
            "speed lane."
        )

    scope_block = config.scope_summary.strip() or config.purpose
    scope_item_lines = list(config.scope_items)
    scope_item_lines.append(
        f"TASKS.md -- tracker-sync authority. The {config.date} tracker sync note "
        f"for wave `{config.wave_id}` is the single source of truth for this "
        "packet's L4 fields; the packet derives from it."
    )

    grounding_lines = [
        f"- Task: {config.task_id}; wave id `{config.wave_id}`.",
        f"- Governing packet: this file, `{config.tracked_packet}`.",
        (
            f"- TASKS.md authority: the {config.date} tracker sync note for wave "
            f"`{config.wave_id}` is canonical for this packet's L4 fields."
        ),
    ]
    if config.authorization_note.strip():
        grounding_lines.append(f"- Authorization: {config.authorization_note.strip()}")

    return f"""# {config.title}

Date: {config.date}
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Task: {config.task_id}
Wave ID: {config.wave_id}
Phase-A-Lock: UNLOCKED
Purpose: {config.purpose}

## Scope

{scope_block}

Files and surfaces in scope:

{_bullets(scope_item_lines)}

## Work items

{_numbered(config.work_items)}

## Constraints

{_bullets(config.constraints)}

## Stop conditions

{_bullets(config.stop_conditions)}

## Validation gates

{chr(10).join(validation_lines)}

## Acceptance criteria

{_bullets(config.acceptance_criteria)}

## Grounding / Authorization

{chr(10).join(grounding_lines)}

FOUNDER_OVERRIDE:{config.wave_id}
"""


def _h1_title_line(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            return line
    return None


def check_packet_fences(content: str, config: WaveConfig) -> list[str]:
    """Return fence violations for a rendered packet (empty = all fences pass).

    Public API: the standard packet fences this builder bakes in --
    packet-integrity (Scope-mentions-TASKS.md + bare FOUNDER_OVERRIDE),
    line-ref lint, asterisk-free title, and run_mu # SPEED_OK.
    """
    errors: list[str] = []

    # Fence 1a: Scope mentions TASKS.md (reuse the Phase A predicate).
    if not _pa._phase_a_scope_mentions_tasks(content):
        errors.append("packet-integrity: Scope section does not mention TASKS.md")

    # Fence 1b: bare FOUNDER_OVERRIDE:<wave_id> in grounding (reuse the predicate).
    if not _pa._phase_a_same_wave_authorization_exists(content, config.wave_id):
        errors.append(
            "packet-integrity: missing bare "
            f"FOUNDER_OVERRIDE:{config.wave_id} line in Grounding"
        )

    # Fence 2: no code line-number references (reuse the line-ref lint).
    offenses = _line_ref.find_offending_lines(content)
    if offenses:
        rendered = "; ".join(f"line {n}: {text}" for n, text in offenses)
        errors.append(f"line-ref lint: code line-number reference(s): {rendered}")

    # Fence 3: asterisk-free title.
    title_line = _h1_title_line(content)
    if title_line is None:
        errors.append("asterisk-free title: packet has no H1 title")
    elif "*" in title_line:
        errors.append("asterisk-free title: title line contains an asterisk")

    # Fence 4: any run_mu mention must be paired with a # SPEED_OK annotation.
    if "run_mu" in content and "# SPEED_OK" not in content:
        errors.append(
            "run_mu # SPEED_OK: packet mentions run_mu without a # SPEED_OK annotation"
        )

    return errors


# --------------------------------------------------------------------------- #
# Setup steps (each reuses an existing builder; each is individually re-runnable)#
# --------------------------------------------------------------------------- #


def setup_packet(repo_root: Path, config: WaveConfig) -> Path:
    """Step 1: render + fence-check FIRST, then place/reuse the packet.

    The fence check gates every disk write. The canonical fenced content is
    rendered and validated BEFORE create_plan_draft is allowed to touch the packet
    path, so a failing fence raises without ever persisting an offending packet.

    Bridge round 4 DEFECT: create_plan_draft used to be called first and write its
    draft (built from the same purpose/scope) to disk; when a later fence check
    then raised, the offending packet was left on disk (Status: Phase A, carrying
    e.g. a code line-ref). render_wave_packet is the exact content this step
    persists and carries every config-derived field (purpose, scope, work items,
    title, ...), so validating it up front fail-closes the whole step before any
    write -- and leaves any prior valid packet untouched on a now-failing config.

    create_plan_draft still owns the deterministic path + reuse semantics (one
    packet, never a duplicate). Once the fences pass, this function writes the
    canonical fenced content, but only when the current content differs from the
    canonical render, so a re-run with the same config is a no-op on an
    already-fenced packet.
    """
    # Fail closed BEFORE any disk write: validate the canonical content first.
    fenced = render_wave_packet(config)
    fence_errors = check_packet_fences(fenced, config)
    if fence_errors:
        raise LaunchWaveError(
            "refusing to write a packet that fails its fences: "
            + "; ".join(fence_errors)
        )

    scope = {
        "tracked_packet": config.tracked_packet,
        "wave_name": config.wave_id,
        "task_id": config.task_id,
        "summary": config.scope_summary,
        "request": config.purpose,
    }
    packet_path = _pa.create_plan_draft(repo_root, config.wave_id, scope)

    if packet_path.read_text(encoding="utf-8") != fenced:
        packet_path.write_text(fenced, encoding="utf-8")
    return packet_path


def setup_tracker_note(repo_root: Path, config: WaveConfig) -> None:
    """Step 2: upsert the TASKS.md tracker-sync note (keyed by wave id)."""
    fields = build_tracker_fields(config)
    field_errors = _tsn.validate_fields(fields)
    if field_errors:
        raise LaunchWaveError(
            "invalid tracker-note fields: " + "; ".join(field_errors)
        )
    _tsn.upsert_tracker_sync_note(repo_root / "TASKS.md", fields)


def setup_routing_record(
    repo_root: Path,
    config: WaveConfig,
    *,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Step 3: write the post-merge routing record (single next-candidate)."""
    record, errors = _ec.build_and_write_routing_record(
        wave_name=config.wave_id,
        task_id=config.task_id,
        tracked_packet=config.tracked_packet,
        request_for_claude=config.request_for_claude,
        summary=config.routing_summary,
        decision=config.routing_decision,
        repo_root=repo_root,
        bus_dir=bus_dir,
    )
    if errors:
        raise LaunchWaveError(
            "routing-record build failed: " + "; ".join(errors)
        )
    return record


def setup_bridge_config(
    repo_root: Path,
    *,
    bus_dir: str | Path | None = None,
) -> Path | None:
    """Step 4: converge the live bridge_config with the committed defaults.

    Graceful no-op (returns None) ONLY when no bridge_config.json exists. When the
    file IS present it must be a well-formed bridge_config (a JSON object with an
    ``agents`` object) and the sync must actually process it; otherwise this FAILS
    CLOSED with :class:`LaunchWaveError`.

    Bridge round 2 DEFECT: ``sync_bridge_config_agents_from_defaults`` returns the
    same ``None`` for an ABSENT file (the intended no-op) and for a PRESENT-but-
    malformed file (unparseable JSON / wrong shape), so a broken live bridge_config
    was silently skipped while the wave setup reported success. This wrapper splits
    those two cases: absent -> no-op (None); present-but-broken -> raise. The sync
    itself remains convergent, so a second run over a healthy config is a
    no-op-equivalent (the bounded re-run recovery contract still holds: fix the
    file and re-run the same config).
    """
    config_path = _ec.bridge_config_path(repo_root, bus_dir)
    if not config_path.exists():
        # Genuinely absent: nothing to converge -> graceful no-op (safe to re-run).
        return None

    # Present file: it MUST parse as a bridge_config object, or we fail closed
    # rather than let the sync silently skip it and report a phantom success.
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LaunchWaveError(
            f"bridge_config is present but unreadable/malformed at {config_path}: "
            f"{exc}. Refusing to report a successful wave setup over a broken "
            "bridge_config; fix the file and re-run the same config."
        ) from exc
    if not isinstance(loaded, dict) or not isinstance(loaded.get("agents"), dict):
        raise LaunchWaveError(
            f"bridge_config at {config_path} is present but not a valid "
            "bridge_config object (expected a JSON object with an 'agents' "
            "object). Refusing to silently skip it; fix the file and re-run."
        )

    synced = _ec.sync_bridge_config_agents_from_defaults(repo_root, bus_dir)
    if synced is None:
        # The file existed and parsed as a valid bridge_config above, so the sync
        # must have processed it. A None here means it skipped a present, valid-
        # looking config -> fail closed instead of reporting a phantom success.
        raise LaunchWaveError(
            "bridge_config sync returned no path for a present, valid-looking "
            f"bridge_config at {config_path}; refusing to report success."
        )
    return synced


def verify_fail_closed_precondition(
    repo_root: Path,
    config: WaveConfig,
) -> None:
    """Step 5: assert the dispatcher's own pre-Phase-B tracker precondition.

    Reuses ``executor_dispatch._tasks_tracker_entry_exists`` so this check is
    byte-identical to the gate the dispatcher applies: a launched wave can never
    be held for a missing same-wave TASKS.md tracker entry. Fail-closed: raises
    when the entry is absent.
    """
    if not _ed._tasks_tracker_entry_exists(
        repo_root,
        wave_id=config.wave_id,
        tracked_packet=config.tracked_packet,
    ):
        raise LaunchWaveError(
            "fail-closed precondition unmet: TASKS.md lacks a tracker entry for "
            f"wave_id={config.wave_id!r} + packet={config.tracked_packet!r}; the "
            "dispatcher would hold Phase B."
        )


def verify_three_guards(
    repo_root: Path,
    config: WaveConfig,
    packet_path: Path,
) -> None:
    """Step 6: the three ANDed Phase A pre-lock guards.

    Reuses the Phase A predicates so this check matches what Phase A enforces:
      guard 1 -- Scope mentions TASKS.md
      guard 2 -- bare FOUNDER_OVERRIDE:<wave_id> authorization
      guard 3 -- a detector-visible TASKS.md tracker note for the wave
    Fail-closed: raises listing every failing guard.
    """
    content = packet_path.read_text(encoding="utf-8")
    failures: list[str] = []
    if not _pa._phase_a_scope_mentions_tasks(content):
        failures.append("guard 1: Scope must mention TASKS.md")
    if not _pa._phase_a_same_wave_authorization_exists(content, config.wave_id):
        failures.append(
            f"guard 2: packet must carry FOUNDER_OVERRIDE:{config.wave_id}"
        )
    if not _pa._tasks_tracker_note_wave_exists(repo_root, config.wave_id):
        failures.append(
            "guard 3: TASKS.md must have a detector-visible tracker note for the wave"
        )
    if failures:
        raise LaunchWaveError("3-guard verification failed: " + "; ".join(failures))


def build_dispatch_command(
    repo_root: Path,
    config: WaveConfig,
    *,
    bus_dir: str | Path | None = None,
) -> list[str]:
    """The dispatcher launch command this wave would run (step 7).

    Emits the dispatcher's ROUTING-MODE argv -- ``executor_dispatch.py
    --routing-record <path>`` -- NOT a flat ``--wave-id``/``--plan`` invocation.
    ``executor_dispatch`` exposes only surface subcommands (``phase-a``,
    ``phase-b``, ...) and, as its default, a routing mode that reads a routing
    record; it has no ``--wave-id`` or top-level ``--plan`` flag and rejects
    them. Routing mode is the correct entry here because step 3 already wrote
    the routing record at exactly this path with decision ``ROUTE_PHASE_A``, so
    the dispatcher reads it and routes the freshly set-up wave to Phase A. An
    explicit ``--routing-record`` also tells the dispatcher the caller owns
    scope (it skips the dirty-worktree refusal), which is correct for a
    launcher handing over a record it just produced.
    """
    routing_path = _ec.routing_record_path(Path(repo_root), bus_dir)
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "executor_dispatch.py"),
        "--routing-record",
        str(routing_path),
    ]
    if bus_dir is not None:
        cmd.extend(["--bus-dir", str(bus_dir)])
    return cmd


def maybe_launch_dispatcher(
    repo_root: Path,
    config: WaveConfig,
    *,
    launch: bool = False,
    runner: Callable[..., Any] = subprocess.run,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Step 7: optionally launch the dispatcher. OFF by default.

    When ``launch`` is False (the default), this persists nothing and runs no
    subprocess; it only returns the command it would run. When True, it shells
    out via ``runner`` (injectable for tests) and FAILS CLOSED: a non-zero
    dispatcher returncode raises :class:`LaunchWaveError` instead of reporting a
    completed launch, so a failed dispatcher subprocess can never be mistaken
    for a launched wave. (The wave setup itself is already persisted and
    idempotent, so re-running the same config after fixing the dispatcher
    failure converges -- see the bounded re-run recovery contract.)
    """
    cmd = build_dispatch_command(repo_root, config, bus_dir=bus_dir)
    if not launch:
        return {"launched": False, "command": cmd}
    result = runner(cmd, cwd=str(repo_root))
    returncode = getattr(result, "returncode", None)
    if returncode != 0:
        raise LaunchWaveError(
            f"dispatcher launch failed (returncode={returncode!r}); wave setup is "
            "complete and idempotent, but the dispatcher did not start. Resolve the "
            "dispatcher failure and re-run with --launch."
        )
    return {
        "launched": True,
        "command": cmd,
        "returncode": returncode,
    }


def build_tracker_fields(config: WaveConfig) -> Any:
    """Build the typed tracker-note fields from the config."""
    return _tsn.TrackerSyncNoteFields(
        wave_id=config.wave_id,
        title=config.title,
        wave_class=config.wave_class,
        target_gate_id=config.target_gate_id,
        primary_blocker_class=config.primary_blocker_class,
        primary_invariant_id=config.primary_invariant_id,
        indicator_artifact_ref=config.indicator_artifact_ref,
        indicator_collection_command=config.indicator_collection_command,
        evidence_command=config.evidence_command,
        evidence_delta=config.evidence_delta,
        progress_proof_before=config.progress_proof_before,
        progress_proof_after=config.progress_proof_after,
        structural_artifact_ref=config.structural_artifact_ref,
        post_gate_contract_sweep=config.post_gate_contract_sweep,
        no_op_proof=config.no_op_proof,
        defer_reason_code=config.defer_reason_code,
        boot0_track_id=config.boot0_track_id,
        boot0_progress_state=config.boot0_progress_state,
        founder_override=config.founder_override,
        packet_ref=config.tracked_packet,
        date=config.date,
    )


# --------------------------------------------------------------------------- #
# Orchestrator                                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class WaveSetupResult:
    """Outcome of a full wave setup."""

    wave_id: str
    packet_path: str
    tracked_packet: str
    tracker_note_written: bool
    routing_record_path: str
    bridge_config_path: str | None
    precondition_ok: bool
    guards_ok: bool
    launch: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "wave_id": self.wave_id,
            "packet_path": self.packet_path,
            "tracked_packet": self.tracked_packet,
            "tracker_note_written": self.tracker_note_written,
            "routing_record_path": self.routing_record_path,
            "bridge_config_path": self.bridge_config_path,
            "precondition_ok": self.precondition_ok,
            "guards_ok": self.guards_ok,
            "launch": self.launch,
        }


def run_wave_setup(
    repo_root: Path,
    config: WaveConfig,
    *,
    launch: bool = False,
    bus_dir: str | Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> WaveSetupResult:
    """Run the full seven-step sequential setup chain for one wave-config.

    Simple sequential: no transactional layer. A partial run is recovered by
    re-running with the SAME config (see module docstring for the bounded
    re-run recovery contract).
    """
    config_errors = config.validate()
    if config_errors:
        raise LaunchWaveError("invalid wave-config: " + "; ".join(config_errors))

    repo_root = Path(repo_root)

    # Steps 1-4: artifact-producing (each idempotent under the re-run contract).
    packet_path = setup_packet(repo_root, config)
    setup_tracker_note(repo_root, config)
    setup_routing_record(repo_root, config, bus_dir=bus_dir)
    bridge_config_path = setup_bridge_config(repo_root, bus_dir=bus_dir)

    # Steps 5-6: verification (persist nothing; fail-closed).
    verify_fail_closed_precondition(repo_root, config)
    verify_three_guards(repo_root, config, packet_path)

    # Step 7: optional launch (off by default). Fail-closed on dispatcher error.
    launch_result = maybe_launch_dispatcher(
        repo_root, config, launch=launch, runner=runner, bus_dir=bus_dir
    )

    routing_path = _ec.routing_record_path(repo_root, bus_dir)
    return WaveSetupResult(
        wave_id=config.wave_id,
        packet_path=str(packet_path),
        tracked_packet=config.tracked_packet,
        tracker_note_written=True,
        routing_record_path=str(routing_path),
        bridge_config_path=(
            str(bridge_config_path) if bridge_config_path is not None else None
        ),
        precondition_ok=True,
        guards_ok=True,
        launch=launch_result,
    )


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def load_wave_config(path: Path) -> WaveConfig:
    """Load a wave-config from a JSON file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise LaunchWaveError(f"cannot read wave-config {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LaunchWaveError(f"wave-config {path} is not valid JSON: {exc}") from exc
    return WaveConfig.from_dict(data)


def _discover_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(12):
        if (cur / "pyproject.toml").is_file() or (cur / ".git").exists():
            return cur
        if cur == cur.parent:
            break
        cur = cur.parent
    return start.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mechanize the full dispatcher-wave setup from one wave-config "
            "(simple sequential; partial runs recovered by re-running)."
        )
    )
    parser.add_argument("config", help="Path to the wave-config JSON file.")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (default: discovered from cwd).",
    )
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Agent-bus directory override (default: the primary bus).",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Also launch the dispatcher after setup (default: off).",
    )
    args = parser.parse_args(argv)

    repo_root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else _discover_repo_root(Path.cwd())
    )
    config = load_wave_config(Path(args.config))
    try:
        result = run_wave_setup(
            repo_root, config, launch=args.launch, bus_dir=args.bus_dir
        )
    except LaunchWaveError as exc:
        print(f"launch_wave: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
