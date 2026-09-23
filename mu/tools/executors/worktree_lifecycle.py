#!/usr/bin/env python3
"""Durable ownership of one registered native lane's terminal completion.

The common Git directory survives the lane. Native launch/dispatch/commit
publish ownership there before returning. A finite mechanical child retries
only pre-mutation holds; interrupted mutations require verification and fresh
authority. This is neither a dispatcher nor a polling service.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

try:
    from . import workingrcx_fleet_apply as fleet
    from .workingrcx_fleet_census import useful_work
except ImportError:
    import workingrcx_fleet_apply as fleet
    from workingrcx_fleet_census import useful_work


OWNER = "FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION"
MAX_ATTEMPTS = 3
REGISTRY = "rcx_worktree_lifecycle"
FAILED_CLOSEOUT_REASON = "Native closeout failed; source/config and correction owner retained"


def sync_primary_from_landed_source(repo: Path, *, base_branch: str, authority_commit: str) -> dict:
    """Use landed bytes in a fresh interpreter, then the existing locked API.

    PRIMARY may still contain the old checkout and unrelated WIP, and this
    caller may have imported its mutation code before the PR landed. Neither
    is an executing-source authority for the new merge's sync transaction.
    """
    if len(authority_commit) != 40 or any(c not in "0123456789abcdef" for c in authority_commit):
        raise fleet.Hold("PRIMARY handoff requires an exact landed commit")
    with fleet.safe_git_environment(network=True):
        common = Path(fleet.line(fleet.git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")))
        primary = common.parent
        fleet.plain_directory(common)
        fleet.plain_directory(primary)
        fleet.git(primary, "merge-base", "--is-ancestor", authority_commit, "origin/" + base_branch)
        tree = fleet.git_entries(primary, authority_commit)
        identity = {str(path): dict(device=path.stat().st_dev, inode=path.stat().st_ino)
                    for path in (primary, common)}
        with tempfile.TemporaryDirectory(prefix="rcx-landed-primary-sync-") as temporary:
            root = Path(temporary)
            for rel in fleet.SYNC_RECOVERY_DEPENDENCIES:
                entry = tree.get(str(rel))
                if entry is None or entry[0] not in {"100644", "100755"}:
                    raise fleet.Hold(f"Landed sync dependency is missing or nonregular: {rel}")
                source = root / rel
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(fleet.git(primary, "cat-file", "blob", entry[1]))
                source.chmod(0o755 if entry[0] == "100755" else 0o644)
            program = (
                "import json,sys; from pathlib import Path; "
                "sys.path.insert(0,sys.argv[1]); import commit_executor as boundary; "
                "primary=Path(sys.argv[2]); identity=json.loads(sys.argv[4]); "
                "assert all({'device':Path(p).stat().st_dev,'inode':Path(p).stat().st_ino}==v "
                "for p,v in identity.items()), 'PRIMARY identity changed'; "
                "binding=boundary.bind_terminal_target_identity(primary,base_branch=sys.argv[3]); "
                "assert binding.get('bound'), binding; "
                "print(json.dumps(boundary.sync_primary_worktree_to_base(primary,sys.argv[3],"
                "target_identity=binding,log=lambda _:None)))"
            )
            process = subprocess.run([sys.executable, "-I", "-B", "-c", program,
                str(root / "mu/tools/executors"), str(primary), base_branch, json.dumps(identity)],
                cwd=primary, capture_output=True, text=True, check=True, timeout=600)
            outcome = json.loads(process.stdout)
            if not isinstance(outcome, dict):
                raise fleet.Hold("Landed PRIMARY sync returned no outcome")
            return {**outcome, "source_authority_commit": authority_commit}


def lane_identity(repo: Path) -> dict:
    repo = repo.absolute()
    fleet.plain_directory(repo)
    with fleet.safe_git_environment():
        info = repo.lstat()
        ident = dict(path=str(repo), filesystem_identity=dict(
            device=info.st_dev, inode=info.st_ino, mode=info.st_mode))
        for key, args in {
            "HEAD": ("rev-parse", "HEAD"),
            "git_dir": ("rev-parse", "--absolute-git-dir"),
            "common_dir": ("rev-parse", "--path-format=absolute", "--git-common-dir"),
        }.items():
            ident[key] = fleet.line(fleet.git(repo, *args))
        ident["branch"] = fleet.line(fleet.git(repo, "symbolic-ref", "--quiet", "HEAD", allowed=(0, 1)))
        if ident["branch"]:
            fleet.inspect_identity(ident)
        elif (fleet.line(fleet.git(repo, "rev-parse", "--show-toplevel")) != str(repo)
                or Path(ident["git_dir"]).parent != Path(ident["common_dir"]) / "worktrees"
                or fleet.read_plain(repo / ".git").strip() != b"gitdir: " + os.fsencode(ident["git_dir"])):
            raise fleet.Hold("Detached native registration identity is uncertain")
    return ident


def register_lane(repo: Path, wave_id: str, *, bus_dir: str | Path | None = None,
                  base_branch: str = "dev", role: str = "native") -> Path | None:
    """Register exact linked identity; PRIMARY is never a retirement target."""
    repo = repo.resolve(strict=True)
    if not (repo / ".git").is_file():
        return None
    if not wave_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_." for c in wave_id):
        raise fleet.Hold("Lifecycle registration requires a safe native wave ID")
    ident = lane_identity(repo)
    bus = Path(bus_dir or ".agent_bus")
    if not bus.is_absolute():
        bus = repo / bus
    if bus.parent != repo or bus.is_symlink() or not bus.name.startswith(".agent_bus"):
        raise fleet.Hold("Lifecycle bus must be an exact direct native lane bus")
    key = fleet.digest(fleet.encoded(dict(wave_id=wave_id, path=ident["path"],
        git_dir=ident["git_dir"], filesystem_identity=ident["filesystem_identity"])))
    root = Path(ident["common_dir"]) / REGISTRY
    root.mkdir(mode=0o700, exist_ok=True)
    fleet.plain_directory(root)
    directory = root / key
    directory.mkdir(mode=0o700, exist_ok=True)
    fleet.plain_directory(directory)
    registration = dict(schema_version=1, owner=OWNER, wave_id=wave_id,
        identity=ident, base_branch=base_branch, bus_dir=str(bus), max_attempts=MAX_ATTEMPTS)
    path = directory / "registration.json"
    if path.exists():
        previous = json.loads(fleet.read_plain(path))
        # Native Phase B may advance HEAD/branch. The original registration is
        # immutable; the terminal observation captures their final exact values.
        if any(previous.get(k) != registration[k] for k in (
                "owner", "wave_id", "base_branch", "bus_dir", "max_attempts")) or any(
                previous["identity"].get(k) != ident[k] for k in (
                    "path", "git_dir", "common_dir", "filesystem_identity")):
            raise fleet.Hold("Lifecycle registration identity drift")
    else:
        fleet.write_new(path, fleet.encoded(registration))
    fleet.write_new(directory / f"owner-{os.getpid()}-{role}.json", fleet.encoded(dict(
        pid=os.getpid(), wave_id=wave_id, identity=key, role=role)), verify_existing=True)
    return directory


def request_completion(directory: Path, *, status: str, result: dict | None = None) -> dict:
    """Publish terminal responsibility without claiming successful cleanup."""
    with _completion_lock(directory):
        return _request_completion(directory, status=status, result=result or {})


def publish_closeout(directory: Path, *, repo: Path, handoff: dict, result: dict) -> Path:
    """Preserve real closeout/config/receipt bytes before the lane can retire.

    These are historical copies, never new receipt or replay authority. A
    failed closeout keeps the source and its native correction owner alive.
    """
    registration = json.loads(fleet.read_plain(directory / "registration.json"))
    bus = Path(registration["bus_dir"])
    artifacts = {}
    paths = [bus / name for name in ("bridge_config.json", "executors/phase_b_handoff.json",
             "meta/post_merge_routing.json", "meta/post_merge_package.json")]
    for value in (handoff.get("pre_commit_receipt_path"), handoff.get("plan_path"),
                  handoff.get("tracked_packet")):
        if value:
            path = Path(value)
            paths.append(path if path.is_absolute() else repo / path)
    if result.get("post_merge_package_path"):
        paths.append(Path(result.get("post_merge_authority_root") or repo) / result["post_merge_package_path"])
    for path in paths:
        if os.path.lexists(path):
            raw = fleet.read_plain(path)
            artifacts[str(path)] = dict(sha256=fleet.digest(raw), bytes_hex=raw.hex())
    value = dict(owner=OWNER, wave_id=registration["wave_id"], source=str(repo),
                 authority="historical_closeout_not_replay_authority", handoff=handoff,
                 result=result, artifacts=artifacts)
    path = directory / "closeout.json"
    fleet.write_new(path, fleet.encoded(value), verify_existing=True)
    return path


def _pre_merge_evidence(directory: Path, *, ancestors: frozenset[Path] = frozenset()) -> dict:
    """Bind pre-mutation failure without requiring a live parent's retirement."""
    if directory in ancestors:
        raise fleet.Hold("Same-HEAD successor predecessor cycle; no replay")
    final_path = directory / "completion.json"
    attempts = sorted(directory.glob("attempt-*"))
    finished = final_path.exists()
    # A commit child publishes failure before returning to its live dispatcher.
    # start_completion deliberately leaves every completion attempt to that
    # parent. The immutable failed closeout is sufficient retry evidence only
    # while NO attempt has started; an interrupted claim still fails closed.
    if not finished and (attempts or not (directory / "closeout.json").exists()):
        raise fleet.Hold("Same-HEAD successor requires finished pre-mutation evidence")
    registration = json.loads(fleet.read_plain(directory / "registration.json"))
    terminal = json.loads(fleet.read_plain(directory / "terminal.json"))
    final = json.loads(fleet.read_plain(final_path)) if finished else {}
    failed_closeout = not finished or final.get("reason") == FAILED_CLOSEOUT_REASON
    evidence = {name: fleet.file_hash(directory / name)
                for name in ("registration.json", "terminal.json")}
    if finished:
        evidence["completion.json"] = fleet.file_hash(final_path)
    attempts_used = 0
    predecessor_path = directory / "predecessor.json"
    if predecessor_path.exists():
        predecessor = json.loads(fleet.read_plain(predecessor_path))
        parent = Path(predecessor["record"])
        if (parent.parent != directory.parent or parent == directory
                or predecessor != _pre_merge_evidence(parent, ancestors=ancestors | {directory})
                or json.loads(fleet.read_plain(parent / "terminal.json"))["identity"] != terminal["identity"]):
            raise fleet.Hold("Same-HEAD successor predecessor evidence changed")
        attempts_used = predecessor["attempts_used"]
        evidence["predecessor.json"] = fleet.file_hash(predecessor_path)
    if finished and (not 0 < len(attempts) <= MAX_ATTEMPTS - attempts_used
            or [p.name for p in attempts] != [f"attempt-{n}" for n in range(
                attempts_used + 1, attempts_used + len(attempts) + 1)]
            or final.get("state") != "ESCALATED"
            or not (final.get("landing_owner") or failed_closeout)
            or final.get("outcome") is not None):
        raise fleet.Hold("Same-HEAD successor lacks verified pre-mutation escalation")
    for number, attempt in enumerate(attempts, attempts_used + 1):
        fleet.plain_directory(attempt)
        names = {p.name for p in attempt.iterdir()}
        if (not {"claim.json", "result.json"} <= names
                or names - {"claim.json", "result.json", "primary-sync.json", "useful-work.json"}):
            raise fleet.Hold("Same-HEAD successor has interrupted or non-pre-mutation evidence; no replay")
        claim = json.loads(fleet.read_plain(attempt / "claim.json"))
        outcome = json.loads(fleet.read_plain(attempt / "result.json"))
        if (claim != dict(number=number, terminal_sha256=fleet.digest(fleet.encoded(terminal)))
                or (attempt != attempts[-1] and (outcome.get("state") != "PENDING" or outcome.get("outcome")))
                or (attempt == attempts[-1] and outcome != final)):
            raise fleet.Hold("Same-HEAD successor pre-mutation claims/outcomes disagree")
        evidence.update({f"{attempt.name}/{name}": fleet.file_hash(attempt / name) for name in names})
    if failed_closeout:
        closeout_path = directory / "closeout.json"
        saved = json.loads(fleet.read_plain(closeout_path))
        if ((finished and final.get("evidence") != str(closeout_path))
                or saved.get("owner") != OWNER
                or saved.get("wave_id") != registration["wave_id"]
                or saved.get("source") != terminal["identity"]["path"]
                or saved.get("authority") != "historical_closeout_not_replay_authority"
                or not saved.get("result", {}).get("status")
                or saved["result"]["status"] == "success"
                or not any(json.loads(fleet.read_plain(path)).get("role") == "commit"
                           for path in directory.glob("owner-*.json"))):
            raise fleet.Hold("Same-HEAD successor failed closeout evidence differs")
        evidence["closeout.json"] = fleet.file_hash(closeout_path)
    else:
        owner = final["landing_owner"]
        inventory_path = attempts[-1] / "useful-work.json"
        if (owner.get("head") != terminal["identity"]["HEAD"]
                or owner.get("source") != terminal["identity"]["path"]
                or owner.get("evidence") != str(inventory_path)
                or json.loads(fleet.read_plain(inventory_path)).get("status") != "NEEDS_LANDING"):
            raise fleet.Hold("Same-HEAD successor pre-mutation landing identity differs")
    return dict(record=str(directory), attempts_used=attempts_used + len(attempts), evidence_sha256=evidence)


def _verify_merge_authority(registration: dict, identity: dict, merge_sha: str) -> None:
    """Require the exact retained HEAD to have landed through the named merge."""
    if (not isinstance(merge_sha, str) or len(merge_sha) != 40
            or any(c not in "0123456789abcdef" for c in merge_sha)):
        raise fleet.Hold("Same-HEAD completion requires exact merge authority")
    primary = Path(identity["common_dir"]).parent
    with fleet.safe_git_environment(network=True):
        fleet.git(primary, "fetch", "origin", registration["base_branch"])
        base = fleet.line(fleet.git(primary, "rev-parse", "origin/" + registration["base_branch"]))
        for ancestor, descendant in ((identity["HEAD"], merge_sha), (merge_sha, base)):
            if fleet.line(fleet.git(primary, "merge-base", ancestor, descendant)) != ancestor:
                raise fleet.Hold("Same-HEAD completion merge authority is not landed")


def _request_completion(directory: Path, *, status: str, result: dict) -> dict:
    registration = json.loads(fleet.read_plain(directory / "registration.json"))
    source = Path(registration["identity"]["path"])
    request = directory / "terminal.json"
    if request.exists():
        previous = json.loads(fleet.read_plain(request))
        merged_link = directory / "merged-successor.json"
        if merged_link.exists():
            successor = Path(json.loads(fleet.read_plain(merged_link))["record"])
            if (successor.parent != directory.parent or successor == directory
                    or json.loads(fleet.read_plain(successor / "predecessor.json")) != _pre_merge_evidence(directory)):
                raise fleet.Hold("Same-HEAD successor predecessor evidence changed")
            for owner in directory.glob("owner-*.json"):
                fleet.write_new(successor / owner.name, fleet.read_plain(owner), verify_existing=True)
            return request_completion(successor, status=status, result=result)
        if not source.exists():
            return previous
        current = lane_identity(source)
        if current == previous["identity"]:
            if status not in {"merged", "success"} or not result.get("merge_sha"):
                return previous
            if previous.get("merge_sha"):
                final = directory / "completion.json"
                if final.exists():
                    if json.loads(fleet.read_plain(final)).get("reason") != FAILED_CLOSEOUT_REASON:
                        return previous
                else:
                    closeout = directory / "closeout.json"
                    if (not closeout.exists() or json.loads(fleet.read_plain(closeout)).get(
                            "result", {}).get("status") in {None, "", "success"}):
                        return previous
                if previous["merge_sha"] != result["merge_sha"]:
                    raise fleet.Hold("Same-HEAD successor changed the recorded merge authority")
            predecessor = _pre_merge_evidence(directory)
            _verify_merge_authority(registration, current, result["merge_sha"])
            key = fleet.digest(fleet.encoded(dict(identity=current, merge_sha=result["merge_sha"])))[:16]
            successor = directory.parent / (directory.name + "-" + key)
            successor.mkdir(mode=0o700, exist_ok=True)
            fleet.plain_directory(successor)
            fleet.write_new(successor / "registration.json", fleet.encoded(registration), verify_existing=True)
            fleet.write_new(successor / "predecessor.json", fleet.encoded(predecessor), verify_existing=True)
            for owner in directory.glob("owner-*.json"):
                fleet.write_new(successor / owner.name, fleet.read_plain(owner), verify_existing=True)
            value = request_completion(successor, status=status, result=result)
            fleet.write_new(merged_link, fleet.encoded(dict(record=str(successor), identity=current,
                merge_sha=result["merge_sha"])), verify_existing=True)
            return value
        # A later native commit can advance this lane after a stopped attempt.
        # Its completion has a fresh immutable identity/budget; the old claim
        # and any interrupted mutation are never edited or retried.
        if any(current[k] != registration["identity"][k]
               for k in ("path", "git_dir", "common_dir", "filesystem_identity")):
            raise fleet.Hold("Native successor changed the registered lane identity")
        successor = directory.parent / (directory.name + "-" + fleet.digest(fleet.encoded(current))[:16])
        successor.mkdir(mode=0o700, exist_ok=True)
        fleet.write_new(successor / "registration.json", fleet.encoded(registration), verify_existing=True)
        for owner in directory.glob("owner-*.json"):
            fleet.write_new(successor / owner.name, fleet.read_plain(owner), verify_existing=True)
        fleet.write_new(directory / ("successor-" + successor.name[-16:] + ".json"),
                        fleet.encoded(dict(record=str(successor), identity=current)), verify_existing=True)
        return request_completion(successor, status=status, result=result)
    ident = lane_identity(source)
    for key in ("path", "git_dir", "common_dir", "filesystem_identity"):
        if ident[key] != registration["identity"][key]:
            raise fleet.Hold("Terminal lifecycle identity differs from registered lane")
    primary = Path(ident["common_dir"]).parent
    info = primary.stat()
    value = dict(schema_version=1, state="PENDING", status=status, identity=ident, record=str(directory),
        owner=OWNER, wave_id=registration["wave_id"], merge_sha=result.get("merge_sha"),
        surviving_root=dict(path=str(primary), device=info.st_dev, inode=info.st_ino),
        pr_lifecycle=result.get("pr_lifecycle"), pr_number=result.get("pr_number"),
        next_action=f"python3 mu/tools/executors/worktree_lifecycle.py --record {directory} --complete")
    fleet.write_new(request, fleet.encoded(value))
    return value


def _surviving_root(terminal: dict) -> Path:
    identity = terminal["surviving_root"]
    root = Path(identity["path"])
    fleet.plain_directory(root)
    info = root.stat()
    if (info.st_dev, info.st_ino) != (identity["device"], identity["inode"]):
        raise fleet.Hold("Surviving lifecycle root identity changed")
    return root


@contextmanager
def _completion_lock(directory: Path):
    fd = os.open(directory / "completion.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _attempt(directory: Path, registration: dict, terminal: dict, attempt: Path) -> dict:
    ident = terminal["identity"]
    primary = Path(ident["common_dir"]).parent
    target = Path(ident["path"])
    try:
        for owner in directory.glob("owner-*.json"):
            pid = json.loads(fleet.read_plain(owner)).get("pid")
            if not fleet._absent_pid(pid):
                raise fleet.Hold("Registered native owner remains live or uncertain")
        commit_owned = any(json.loads(fleet.read_plain(path)).get("role") == "commit"
                           for path in directory.glob("owner-*.json"))
        if commit_owned:
            closeout = directory / "closeout.json"
            if not closeout.exists():
                raise fleet.Hold("Native commit closeout is not durably published; source retained")
            saved = json.loads(fleet.read_plain(closeout))
            if saved["result"].get("status") != "success":
                return dict(state="ESCALATED", owner=OWNER, evidence=str(closeout),
                    reason=FAILED_CLOSEOUT_REASON,
                    next_action=terminal["next_action"].replace(" --complete", ""))
        if terminal.get("pr_number") and not terminal.get("merge_sha"):
            return dict(state="ESCALATED", owner=OWNER,
                        reason="Stopped PR retains native disposition ownership",
                        pr_owner=terminal.get("pr_lifecycle"), pr_number=terminal["pr_number"],
                        next_action="Resolve this exact PR through the native disposition owner; retain the lane and its history.")
        with fleet.safe_git_environment(network=True):
            detached = not ident["branch"]
            if detached:
                # Detached lanes can own useful work but have no branch-based
                # retirement authority. Recheck their registered identity only
                # for inventory; they never reach preservation admission.
                if lane_identity(target) != ident:
                    raise fleet.Hold("Detached native completion identity drift")
            else:
                fleet.inspect_identity(ident)
            fleet.process_idle(ident)
            fleet.native_idle(target, fleet.tree_manifest(target), reconcile_r1=True)
            from importlib import import_module
            boundary = import_module("mu.tools.executors.commit_executor" if __package__ else "commit_executor")
            sync = boundary.sync_primary_worktree_to_base(primary, registration["base_branch"], log=lambda _: None)
            fleet.write_new(attempt / "primary-sync.json", fleet.encoded(sync))
            fleet.git(primary, "fetch", "origin", registration["base_branch"])
            base = fleet.line(fleet.git(primary, "rev-parse", "origin/" + registration["base_branch"]))
            if fleet.line(fleet.git(primary, "rev-parse", "HEAD")) != base:
                raise fleet.Hold("Surviving PRIMARY still requires preservation-safe base synchronization")
            inventory = useful_work(str(target), base)
            fleet.write_new(attempt / "useful-work.json", fleet.encoded(inventory))
            if detached or inventory["status"] != "COVERED":
                return dict(state="ESCALATED", owner=OWNER,
                    reason=("Detached native lane retains retirement and useful-work ownership" if detached
                            else "Retained useful work requires native landing review"),
                    landing_owner=dict(wave_id=registration["wave_id"], branch=ident["branch"],
                        head=ident["HEAD"], source=str(target), evidence=str(attempt / "useful-work.json")),
                    next_action=("Native owner must review the exact detached HEAD/index/WIP and prove dev coverage; "
                                 "retain this lane pending fresh reviewed retirement authority." if detached else
                                 "Native owner must land or prove dev coverage of the recorded local commits/index/WIP; retain this lane."))
            if ident["branch"] in {"refs/heads/" + registration["base_branch"], "refs/heads/main", "refs/heads/master"}:
                raise fleet.Hold("Base checkout remains a retained synchronization owner")
            # Bind the coverage receipt to preservation admission. The shared
            # transaction rechecks index/content under its preparation lock;
            # drift must HOLD before it can retire newly useful work.
            entry = dict(source_index=0, path=str(target), source_identity=ident,
                destination=str(attempt / "worktree"), action="PRESERVE_WORKTREE",
                owner=OWNER, comparison_commit=base, useful_work=inventory)
            outcome = fleet.apply_target(primary, entry, attempt, boundary, residual=True)
            if outcome["status"] == "MOVED":
                return dict(state="COMPLETE", owner=OWNER, destination=entry["destination"],
                            source_absent=not os.path.lexists(target), outcome=outcome)
            return dict(state="ESCALATED" if outcome["status"] == "INCOMPLETE" else "PENDING",
                        owner=OWNER, reason=outcome.get("reason"), outcome=outcome,
                        landing_owner=outcome.get("landing_owner"),
                        next_action="Verify captured preservation/terminal receipts; a started mutation is never replayed.")
    except (fleet.Hold, OSError, ValueError, subprocess.SubprocessError) as exc:
        return dict(state="PENDING", owner=OWNER, reason=str(exc),
                    next_action="Resolve only this exact owner/identity/preservation hold; request fresh bounded authority if the budget is consumed.")


def complete_pending(directory: Path, *, delay: float = 2.0) -> dict:
    """At most three durable claims; no retry after an interrupted mutation."""
    fleet.plain_directory(directory)
    registration = json.loads(fleet.read_plain(directory / "registration.json"))
    common = Path(registration["identity"]["common_dir"])
    if directory.parent != common / REGISTRY or registration.get("max_attempts") != MAX_ATTEMPTS:
        raise fleet.Hold("Unrecognized bounded lifecycle registration")
    inspection = shlex.join([sys.executable, str(Path(__file__).resolve()), "--record", str(directory)])

    def retained_action(value: dict, evidence: Path) -> dict:
        if value["state"] == "COMPLETE" or value.get("next_action") == inspection:
            return value
        return {**value, "evidence": value.get("evidence", str(evidence)),
                "required_resolution": value.get("next_action", "Reconcile the recorded owner before fresh authority."),
                "next_action": inspection}

    with _completion_lock(directory):
        final = directory / "completion.json"
        if final.exists():
            value = json.loads(fleet.read_plain(final))
            if value["state"] == "COMPLETE":
                target = Path(registration["identity"]["path"])
                destination = Path(value["destination"])
                manifest = json.loads(fleet.read_plain(destination.parent / "after.json"))
                if os.path.lexists(target) or fleet.tree_manifest(destination) != manifest:
                    raise fleet.Hold("Completed lifecycle destination/source verification failed")
                fleet.require_transaction_state(destination, json.loads(fleet.read_plain(
                    destination.parent / "retired-state.json")), "completion-verification")
            return value
        merged_link = directory / "merged-successor.json"
        if merged_link.exists():
            successor = Path(json.loads(fleet.read_plain(merged_link))["record"])
            if (successor.parent != directory.parent or successor == directory
                    or json.loads(fleet.read_plain(successor / "predecessor.json")) != _pre_merge_evidence(directory)):
                raise fleet.Hold("Same-HEAD successor predecessor evidence changed")
            # A deferred predecessor is sealed by the successor's hashes. Never
            # start a late attempt there and invalidate that preserved evidence.
            return complete_pending(successor, delay=delay)
        terminal = json.loads(fleet.read_plain(directory / "terminal.json"))
        if any(terminal["identity"].get(key) != registration["identity"][key]
               for key in ("path", "git_dir", "common_dir", "filesystem_identity")):
            raise fleet.Hold("Terminal ownership does not match the registered lane")
        _surviving_root(terminal)
        attempts_used = 0
        predecessor_path = directory / "predecessor.json"
        if predecessor_path.exists():
            predecessor = json.loads(fleet.read_plain(predecessor_path))
            parent = Path(predecessor["record"])
            if (parent.parent != common / REGISTRY or parent == directory
                    or predecessor != _pre_merge_evidence(parent)
                    or json.loads(fleet.read_plain(parent / "terminal.json"))["identity"] != terminal["identity"]):
                raise fleet.Hold("Same-HEAD successor predecessor evidence changed")
            _verify_merge_authority(registration, terminal["identity"], terminal.get("merge_sha"))
            attempts_used = predecessor["attempts_used"]
        value = dict(state="ESCALATED", owner=OWNER, reason="Bounded native completion budget exhausted",
                     attempts_exhausted=MAX_ATTEMPTS)
        for number in range(attempts_used + 1, MAX_ATTEMPTS + 1):
            attempt = directory / f"attempt-{number}"
            if attempt.exists():
                outcome_path = attempt / "result.json"
                if not outcome_path.exists():
                    value = dict(state="ESCALATED", owner=OWNER,
                        reason="Interrupted completion attempt; outcome unknown, no replay",
                        next_action=f"Verify exact receipts in {attempt}; issue fresh authority for any remaining mutation.")
                    break
                value = json.loads(fleet.read_plain(outcome_path))
            else:
                fleet.new_directory(attempt)
                fleet.write_new(attempt / "claim.json", fleet.encoded(dict(number=number, terminal_sha256=fleet.digest(fleet.encoded(terminal)))))
                value = _attempt(directory, registration, terminal, attempt)
                value = retained_action(value, attempt)
                fleet.write_new(attempt / "result.json", fleet.encoded(value))
            if value["state"] != "PENDING":
                break
            if number < MAX_ATTEMPTS:
                time.sleep(delay)
        if value["state"] == "PENDING":
            value = {**value, "state": "ESCALATED", "attempts_exhausted": MAX_ATTEMPTS}
        value = retained_action(value, directory)
        fleet.write_new(final, fleet.encoded(value))
        if value["state"] == "ESCALATED":
            try:
                try:
                    from ..observability.pipeline_agent_pager import emit_transition_event
                except ImportError:
                    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "observability"))
                    from pipeline_agent_pager import emit_transition_event
                event = emit_transition_event(_surviving_root(terminal), event_type="pipeline_hard_fail",
                    wave_id=registration["wave_id"], task_id="[" + OWNER + "]",
                    phase="worktree_lifecycle", state="incomplete", transition_key=directory.name,
                    summary="Native worktree completion remains incomplete: " + str(value.get("reason", "")),
                    artifact_paths={"completion": str(final)}, route="codex")
                fleet.write_new(directory / "pager.json", fleet.encoded(event))
            except Exception as exc:
                fleet.write_new(directory / "pager-error.json", fleet.encoded(dict(error=str(exc))))
        return value


def start_completion(directory: Path) -> dict:
    """Launch a finite providerless child from surviving common-dir authority."""
    registration = json.loads(fleet.read_plain(directory / "registration.json"))
    primary = Path(registration["identity"]["common_dir"]).parent
    for path in directory.glob("owner-*.json"):
        owner = json.loads(fleet.read_plain(path))
        if (owner.get("role") == "dispatcher" and owner.get("pid") != os.getpid()
                and not fleet._absent_pid(owner.get("pid"))):
            return dict(state="PENDING", owner=OWNER, record=str(directory),
                        continuation="dispatcher terminal finally owns the bounded child")
    # The script is loaded before it can retire a source. Its cwd/log/output
    # always survive. No pager writes ever use a retired source path here.
    with (directory / "worker.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
            "--record", str(directory), "--complete"], cwd=primary,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, close_fds=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return dict(state="PENDING", owner=OWNER, record=str(directory), worker_pid=process.pid)


def recover_pending_sync(manifest_path: Path, *, authority_commit: str) -> dict:
    """Use the landed fleet recovery API and its existing single-use claim."""
    manifest = json.loads(fleet.read_plain(manifest_path))
    primary = Path(manifest["common_dir_identity"]["path"]).parent
    with fleet.safe_git_environment(network=True):
        if len(authority_commit) != 40 or any(c not in "0123456789abcdef" for c in authority_commit):
            raise fleet.Hold("Recovery requires an exact landed commit")
        fleet.git(primary, "merge-base", "--is-ancestor", authority_commit, "origin/dev")
        for rel in fleet.SYNC_RECOVERY_DEPENDENCIES:
            if fleet.read_plain(primary / rel) != fleet.git(primary, "show", f"{authority_commit}:{rel}"):
                raise fleet.Hold(f"Native recovery dependency differs from committed authority: {rel}")
        # A new interpreter prevents cached imports from an old source checkout.
        # The public command rechecks all dependency, identity, lock and receipt
        # bindings before using the original owner's transaction. No second claim.
        program = ("import sys; sys.path.insert(0,sys.argv[1]); "
                   "import workingrcx_fleet_apply as fleet; raise SystemExit(fleet.main(sys.argv[2:]))")
        process = subprocess.run([sys.executable, "-I", "-B", "-c", program,
            str(primary / "mu/tools/executors"),
            "--recover-sync", str(manifest_path), "--authority-commit", authority_commit],
            cwd=primary, capture_output=True, text=True, timeout=600)
        if process.returncode not in {0, 3}:
            raise fleet.Hold("Native sync recovery failed: " + (process.stderr or process.stdout)[-6000:])
        value = json.loads(process.stdout)
        if not isinstance(value, dict) or value.get("state") not in {"RECOVERED", "INCOMPLETE"}:
            raise fleet.Hold("Native sync recovery returned no verified outcome")
        return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--recover-sync", action="store_true")
    parser.add_argument("--authority-commit")
    args = parser.parse_args(argv)
    if args.recover_sync:
        if args.complete or not args.authority_commit:
            parser.error("--recover-sync requires --authority-commit and excludes --complete")
        value = recover_pending_sync(args.record, authority_commit=args.authority_commit)
    elif not (args.record / "terminal.json").exists():
        value = dict(state="PENDING_TERMINAL_OBSERVATION", owner=OWNER,
            registration=json.loads(fleet.read_plain(args.record / "registration.json")),
            next_action="Native owner must reconcile the surviving terminal receipt before requesting completion; registration alone cannot authorize retirement.")
    elif args.complete:
        value = complete_pending(args.record)
    else:
        name = "completion.json" if (args.record / "completion.json").exists() else "terminal.json"
        value = json.loads(fleet.read_plain(args.record / name))
    print(json.dumps(value, sort_keys=True))
    return 0 if value.get("state") in {"COMPLETE", "RECOVERED"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
