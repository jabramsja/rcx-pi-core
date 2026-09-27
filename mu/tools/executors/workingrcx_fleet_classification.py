#!/usr/bin/env python3
"""Classify recorded census evidence; never inspect or mutate a fleet target.

Run from the fresh classification carrier. The default source/base binding is
the landed R3 census. Disposable inventories require their own explicit raw
--expected-census-sha256 and a disposable carrier as the working directory.
No target stat, status, worktree enumeration, process census or network query
is performed. Only local carrier Git metadata and commit objects are queried.
An existing output is verified byte-for-byte, never refreshed or overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


WAVE_ID = "workingrcx-fleet-classification-r1-2026-09-11"
RESIDUAL_WAVE_ID = "workingrcx-fleet-residual-completion-r1-2026-09-13"
RESIDUAL_BATCH_SIZE = 12
RETIREMENT_WAVE_ID = "workingrcx-fleet-real-retirement-r1-2026-09-23"
RETIREMENT_PREDECESSOR = "a76ccb9b238b45474946b93a5f3d3be1b07a8b93"
MISSING_WAVE_ID = "workingrcx-fleet-missing-registration-retirement-r1-2026-09-27"
# Only these individually enumerated predecessor sources can be proposed for
# release. The preservation container itself and the stopped Mu owner cannot.
HISTORICAL_SOURCES = (
    "WorkingRCX-audit-origin-dev-20260729",
    "WorkingRCX-fleet-preservation-owner-binding-r1-20260927",
    "WorkingRCX-fleet-validation-convergence-r1-20260927",
    "workingrcx_pr_preservation_20260630",
    "WorkingRCX-worktrees",
    *("WorkingRCX-preservation/" + name for name in (
        "never-behind-fleet-authority-r1-phase-a-request-changes-20260909",
        "never-behind-fleet-authority-r2-phase-b-policy-bound-20260909",
        "never-behind-fleet-authority-r3-precommit-needs-phase-a-20260909",
        "phase-b-private-review-byte-preserving-resume-r1-builder-stub-stop-20260909",
        "phase-b-private-review-byte-preserving-resume-r1-generation1-contract-stop-20260909",
        "phase-b-private-review-byte-preserving-resume-r1-nonconvergent-r3-20260909",
        "pr-disposition-apply-r1-phase-a-corrected-config-required-20260910",
        "pr-disposition-apply-r2-terminal-transition-blocked-20260910",
        "pr-disposition-execution-r1-phase-a-corrected-config-20260909",
        "pr-disposition-execution-r2-phase-a-corrected-config-20260909",
        "pr-disposition-r2-adoption-enabler-diverged-20260910",
        "r3c6-green-review-envelope-stop-20260909",
        "recovery-private-review-envelope-r1-review-nogo-20260909",
    )),
)
LANDED_CENSUS = "workingrcx-fleet-census-r3-2026-09-11_census.json"
LANDED_SHA256 = "ac6f61337081c9adb7c100bac061270f6c7864aaed55d48912f50b8473d0cd81"
LANDED_BASE = "c209bf29841425305003eeceddfd567a93874742"
LANDED_FLEET = "/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal"
CARRIER_NAME = "WorkingRCX-fleet-classification-r1-20260911"
DECISIONS = ("HOLD", "CONDITIONAL_RETIRE_CANDIDATE")
DIRTY_KEYS = ("entries", "tracked", "untracked", "staged", "unstaged", "unmerged")

# Finite upper bound from the landed inventory, reconciled with TASKS's current
# queue and preserved-candidate evidence. Membership alone proves nothing.
# In particular the clean codex-defaults, stopped recorded-child restart2,
# PR1211/nbfence evidence and preservation-bearing worktree are excluded.
BOUNDED_CANDIDATE_NAMES = (
    "WorkingRCX-cproof2-20260726",
    "WorkingRCX-fix36-20260712",
    "WorkingRCX-pr1219-p0imrp-receipt-model-provenance-activation-20260822",
    "WorkingRCX-pr1219-p0imrpas-north-star-numbering-repair-20260822",
    "WorkingRCX-theater-20260725",
    "workingrcx_claroles_20260627",
    "workingrcx_codexflip",
    "workingrcx_nbcomplete",
    "workingrcx_pager",
    "workingrcx_pager_route_codex_20260701",
    "workingrcx_reentry",
    "workingrcx_reentry_land",
    "workingrcx_roles",
    "workingrcx_setrolesdefault_20260628",
)
PROTECTED_NAMES = (
    "WorkingRCX",
    "WorkingRCX-preservation",
    "WorkingRCX-audit-origin-dev-20260729",
    CARRIER_NAME,
    "WorkingRCX-fleet-census-r3-20260911",
    "WorkingRCX-workingrcx-fleet-census-builder-r1-20260910",
    "WorkingRCX-workingrcx-fleet-census-builder-r2-20260910",
    "WorkingRCX-commit-governance-retry-idempotency-r1-20260910",
    "WorkingRCX-commit-governance-retry-idempotency-r2-20260910",
    "WorkingRCX-commit-supervisor-needs-phase-a-terminal-retry-fence-r1-20260911",
    "WorkingRCX-native-stub-phase-b-same-config-relaunch-repair-r1-20260910",
    "WorkingRCX-native-stub-phase-b-same-config-relaunch-repair-r2-20260911",
    "WorkingRCX-native-stub-phase-b-same-config-relaunch-repair-r3-20260911",
    "WorkingRCX-pr1219-p0ibrrcp-codex-defaults-20260826-r1",
    "WorkingRCX-pr1219-p0ibrrcp-provider-neutral-bridge-context-20260826-r2",
    "WorkingRCX-pr1219-p0ibrrcp-provider-neutral-bridge-role-context-20260826-r1",
    "WorkingRCX-pr1219-p0imrp-commit-target-role-authority-20260822",
    "WorkingRCX-roles-all-codex-pr1219-p0im-codex-model-bootstrap-restart2-20260822",
    "WorkingRCX-roles-all-codex-pr1219-p0r-role-model-authority-recovery-20260820",
    "WorkingRCX-test-provider-isolation-root-20260826-r2",
    "WorkingRCX-test-provider-isolation-root-20260826-r3",
    "WorkingRCX-roles-all-codex-pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-20260823-r2",
    "workingrcx_nbfence",
    "workingrcx_pr_preservation_20260630",
)
PROTECTED_HEADS = (
    "28081acd74c549a7afd4292351b214228d45f451",  # PR1219 reconstruction
    "4c466d1001b838e69ce141801fbbbe35f410d466",  # PR1203 reconstruction
    "10d157c4eb5b667b07006686fea86d88af268646",  # PR1211 supersession
    "b846d2e93be9ffbd3e25b30c1b7983ceb52c4ae7",  # PR1210 supersession
)
APPLY_PREREQUISITES = (
    "UNMET: Reconcile the exact census path, HEAD, symbolic branch, Git directory, common directory and registration identity with action-time target state; drift means HOLD.",
    "UNMET: Prove the target is idle and not currently active, protected or preserved noncomplete evidence under TASKS authority.",
    "UNMET: Preserve and verify all valuable, untracked and ignored evidence before retirement; a recorded clean status excludes ignored files and does not prove preservation.",
    "UNMET: Preserve and verify branch/history independently of worktree retirement.",
    "UNMET: Use supported safe never-behind preparation without losing WIP; inability to prepare safely means HOLD.",
    "UNMET: Bind the exact action-time identity with bind_terminal_target_identity and pass each terminal action itself to execute_terminal_mutation_once; its fresh fetch and behind(origin/dev)=0 checks must pass inside that one-shot boundary.",
    "UNMET: A classification or diagnostic return grants no reusable mutation authority. Any unsatisfied identity, liveness, preservation or boundary requirement must HOLD this target without blocking unrelated valid targets.",
)


def _absolute(value: object) -> bool:
    return (isinstance(value, str) and bool(value) and "\0" not in value
            and os.path.isabs(value) and os.path.normpath(value) == value)


def _oid(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def valid_missing_source(source: dict, common: str) -> bool:
    evidence = source.get("missing_registration") or {}
    ident = evidence.get("identity") or {}
    git = source.get("git") or {}
    manifest = evidence.get("admin_manifest") or {}
    return (evidence.get("status") == "OBSERVED" and evidence.get("errors") == []
        and evidence.get("ownership_holds") == [] and not evidence.get("registration", {}).get("locked")
        and evidence.get("path") == source["path"]
        and ident == dict(path=source["path"], **{k: git.get(k) for k in (
            "HEAD", "branch", "common_dir", "git_dir")})
        and _oid(ident.get("HEAD")) and ident.get("common_dir") == common
        and _absolute(ident.get("git_dir")) and str(Path(ident["git_dir"]).parent) == common + "/worktrees"
        and source.get("availability_status") == "missing" and source.get("entry_kind") == "missing"
        and source.get("inspection_status") == "admin_only" and source.get("errors") == []
        and source.get("repository_kind") == "missing_linked_worktree"
        and source.get("registration_status") == "registered"
        and source.get("registered_worktrees") == [evidence.get("registration")]
        and set(evidence.get("admin_filesystem_identity", {})) == {"device", "inode", "mode"}
        and all(type(v) is int for v in evidence["admin_filesystem_identity"].values())
        and {"HEAD", "index", "gitdir", "commondir"} <= manifest.keys()
        and manifest["index"].get("sha256") == evidence.get("index_sha256")
        and all(isinstance(evidence.get(k), str) and re.fullmatch(r"[0-9a-f]{64}", evidence[k])
                for k in ("index_sha256", "index_entries_sha256", "indexed_objects_sha256", "history_sha256")))


def _observation_valid(source: dict, census: dict) -> bool:
    try:
        times = [datetime.fromisoformat(value) for value in (
            census["started_at"], source["observed_started_at"],
            source["observed_finished_at"], census["finished_at"])]
        return all(t.tzinfo is not None for t in times) and times == sorted(times)
    except (KeyError, TypeError, ValueError):
        return False


def _unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate_inventory(census: dict) -> None:
    """Reject unverifiable coverage; inspection-level uncertainty is row-local."""
    if (not isinstance(census, dict) or type(census.get("schema_version")) is not int
            or census["schema_version"] != 1
            or census.get("observation_kind") != "read_only_fleet_census"
            or census.get("coverage_complete") is not True):
        raise ValueError("Malformed or incomplete census envelope")
    for key in ("fleet_root", "anchor_repo"):
        if not _absolute(census.get(key)):
            raise ValueError(f"Missing exact absolute census {key}")
    try:
        start, finish = (datetime.fromisoformat(census[k]) for k in ("started_at", "finished_at"))
        if start.tzinfo is None or finish.tzinfo is None or start > finish:
            raise ValueError("Invalid census observation interval")
    except (KeyError, TypeError) as exc:
        raise ValueError("Missing census observation interval") from exc
    entries = census.get("entries")
    if (not isinstance(entries, list) or type(census.get("entry_count")) is not int
            or census["entry_count"] != len(entries)):
        raise ValueError("Census entry_count does not account for every input row")
    seen, direct_count, registration_count = set(), 0, 0
    for row in entries:
        if not isinstance(row, dict) or not _absolute(row.get("path")) or row["path"] in seen:
            raise ValueError("Census row lacks a unique exact absolute path")
        seen.add(row["path"])
        sources, registrations = row.get("sources"), row.get("registered_worktrees")
        if (not isinstance(sources, list) or not sources
                or any(s not in ("fleet_root", "anchor_worktrees") for s in sources)
                or len(set(sources)) != len(sources) or not isinstance(registrations, list)
                or bool(registrations) != ("anchor_worktrees" in sources)
                or any(not isinstance(r, dict) or r.get("path") != row["path"] for r in registrations)):
            raise ValueError("Census row has incomplete enumeration provenance")
        if "fleet_root" in sources:
            if (os.path.dirname(row["path"]) != census["fleet_root"]
                    or not os.path.basename(row["path"]).lower().startswith("workingrcx")):
                raise ValueError("Census fleet-root provenance is inconsistent")
            direct_count += 1
        registration_count += len(registrations)
    enumeration = census.get("enumeration")
    if not isinstance(enumeration, dict):
        raise ValueError("Missing census enumeration evidence")
    for source, field, count in (("fleet_root", "matching_entries", direct_count),
                                 ("anchor_worktrees", "records", registration_count)):
        evidence = enumeration.get(source)
        if (not isinstance(evidence, dict) or evidence.get("status") != "complete"
                or evidence.get("errors") != [] or type(evidence.get(field)) is not int
                or evidence[field] != count):
            raise ValueError(f"Incomplete or inconsistent {source} enumeration")


def _git(carrier: str, *args: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # Git 2.43 rejects --no-lazy-fetch and ignores GIT_NO_LAZY_FETCH. Keep the
    # latter for newer Git, but enforce the portable empty transport allowlist:
    # protocol.allow=never alone can be overridden by local protocol.*.allow.
    # Missing objects must stay unavailable; never retry with weaker guards.
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1",
               GIT_GRAFT_FILE=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_PROTOCOL_FROM_USER="0", GIT_ALLOW_PROTOCOL="", LC_ALL="C")
    command = ["git", "--no-optional-locks",
               "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
               "-c", "core.commitGraph=false", "-c", "advice.graftFileDeprecated=false",
               "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "protocol.allow=never",
               "-C", carrier, *args]
    try:
        result = subprocess.run(
            command,
            env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
        )
        return {"operation": list(args), "returncode": result.returncode,
                "stdout": os.fsdecode(result.stdout[:4096]),
                "stderr": os.fsdecode(result.stderr[:4096]),
                "output_truncated": len(result.stdout) > 4096 or len(result.stderr) > 4096}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"operation": list(args), "error": type(exc).__name__}


def _success(probe: dict, stdout: str = "", *, returncode: int = 0) -> bool:
    return (probe.get("returncode") == returncode and probe.get("stdout") == stdout
            and probe.get("stderr") == "" and probe.get("output_truncated") is False)


def _ancestry(carrier: str, head: str, base: str) -> dict:
    object_probe = _git(carrier, "cat-file", "-t", head)
    if not _success(object_probe, "commit\n"):
        return {"status": "UNKNOWN", "probes": [object_probe]}
    probe = _git(carrier, "merge-base", "--is-ancestor", head, base)
    status = "UNKNOWN"
    if _success(probe):
        status = "ANCESTOR"
    elif _success(probe, returncode=1):
        status = "NOT_ANCESTOR"
    return {"status": status, "probes": [object_probe, probe]}


def retirement_authority_binding(census: dict, *, wave_id: str, predecessor: str,
                                 source_sha256: str) -> dict:
    """Bind a renewal proposal; only its later landed plan can authorize actions.

    The original retirement wave remains a legacy reader, never a renewal ID.
    Census useful-work comparisons must be observed against this predecessor;
    relabeling an earlier observation does not renew its authority.
    """
    if (not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,160}", wave_id or "")
            or wave_id in {WAVE_ID, RESIDUAL_WAVE_ID, RETIREMENT_WAVE_ID,
                          "workingrcx-fleet-apply-r1-2026-09-11",
                          "workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11"}
            or not _oid(predecessor)
            or not isinstance(source_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
            or census["anchor_repo"] != census["fleet_root"] + "/WorkingRCX"):
        raise ValueError("Fresh retirement authority requires a new wave, exact predecessor and canonical census binding")
    for source in census["entries"]:
        useful = source.get("useful_work")
        if useful is not None and (not isinstance(useful, dict)
                or useful.get("comparison_commit") != predecessor):
            raise ValueError("Fresh retirement predecessor differs from observed useful-work authority")
    return dict(schema_version=1, wave_id=wave_id, predecessor_commit=predecessor,
                census_sha256=source_sha256, fleet_root=census["fleet_root"],
                anchor_repo=census["anchor_repo"])


def classify(census: dict, *, source_sha256: str, base_commit: str,
             carrier: str, landed: bool, residual: bool = False,
             wave_id: str | None = None, protected: tuple[str, ...] = (),
             retirement: bool = False, retirement_predecessor: str | None = None,
             missing_paths: tuple[str, ...] = (), historical_paths: tuple[str, ...] = ()) -> dict:
    """Return one decision per validated row using only carrier-local objects."""
    _validate_inventory(census)
    if residual and landed:
        raise ValueError("Historical and residual classification authorities cannot be mixed")
    if wave_id is not None and (not residual or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,160}", wave_id)):
        raise ValueError("Fresh wave identity requires residual mode and a safe wave ID")
    fresh_wave = wave_id is not None and wave_id != RESIDUAL_WAVE_ID
    selected_wave = wave_id or RESIDUAL_WAVE_ID
    if retirement and (not residual or not fresh_wave):
        raise ValueError("Retirement requires fresh residual wave authority")
    authority = None
    if retirement_predecessor is not None:
        if not retirement or retirement_predecessor != base_commit:
            raise ValueError("Fresh retirement predecessor must match the explicit retirement comparison")
        authority = retirement_authority_binding(census, wave_id=selected_wave,
            predecessor=retirement_predecessor, source_sha256=source_sha256)
    if retirement and authority is None and census["fleet_root"] == LANDED_FLEET and (
            selected_wave != RETIREMENT_WAVE_ID or base_commit != RETIREMENT_PREDECESSOR):
        raise ValueError("Actual fleet retirement requires explicit fresh predecessor authority")
    observed_paths = {r["path"] for r in census["entries"]}
    allowed_historical = {census["fleet_root"] + "/" + p for p in HISTORICAL_SOURCES}
    if missing_paths or historical_paths:
        if (authority is None or not set(missing_paths + historical_paths) <= observed_paths
                or len(set(missing_paths)) != len(missing_paths)
                or len(set(historical_paths)) != len(historical_paths)
                or (historical_paths and (selected_wave != MISSING_WAVE_ID
                    or not set(historical_paths) <= allowed_historical))):
            raise ValueError("Registration/historical release requires fresh exact finite source authority")
    if not _oid(base_commit):
        raise ValueError("base-commit must be an exact 40-character commit ID")
    if not _success(_git(carrier, "rev-parse", "--show-toplevel"), carrier + "\n"):
        raise ValueError("Run from the root of the fresh classification carrier")
    # Older Git may rewrite partial-clone config before a transport ban rejects
    # its implicit fetch. Refuse every promisor configuration before querying
    # objects, including filter-only settings and false/duplicate promisor keys.
    # Only a clean no-match result establishes this portable no-fetch boundary.
    promisor = _git(carrier, "config", "--get-regexp",
                    r"^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$")
    if not _success(promisor, returncode=1):
        raise ValueError("Cannot establish a read-only, no-fetch carrier: partial-clone/promisor configuration is present or inconclusive")
    if not _success(_git(carrier, "cat-file", "-t", base_commit), "commit\n"):
        raise ValueError("Exact comparison commit unavailable in the local carrier")
    if not _success(_git(carrier, "merge-base", "--is-ancestor", base_commit, "HEAD")):
        raise ValueError("Carrier is not based on the exact comparison commit")
    common = census["fleet_root"] + "/WorkingRCX/.git"
    if landed:
        if (source_sha256 != LANDED_SHA256 or base_commit != LANDED_BASE
                or census["fleet_root"] != LANDED_FLEET or census["entry_count"] != 411
                or carrier != LANDED_FLEET + "/" + CARRIER_NAME
                or not _success(_git(carrier, "rev-parse", "--path-format=absolute", "--git-common-dir"), common + "\n")):
            raise ValueError("Landed census, exact predecessor or fresh carrier binding is wrong")
    protected_paths = [census["fleet_root"] + "/" + name for name in PROTECTED_NAMES]
    if residual:
        protected_paths = [census["fleet_root"] + "/" + name for name in (
            "WorkingRCX", "WorkingRCX-preservation", "workingrcx_pr_preservation_20260630")]
    if retirement:
        protected_paths.append(census["fleet_root"] + "/WorkingRCX-mu-coinduction-prefix-r1-20260914")
    protected_paths += [census["anchor_repo"], carrier]
    if any(not _absolute(p) for p in protected):
        raise ValueError("Protected owners require exact absolute paths")
    protected_paths += list(protected)
    rows, cache = [], {}
    for index, source in enumerate(census["entries"]):
        path, reasons = source["path"], []
        git = source.get("git") if isinstance(source.get("git"), dict) else {}
        registrations = source["registered_worktrees"]
        def hold(code: str, detail: str) -> None:
            reasons.append({"code": code, "detail": detail})
        name = os.path.basename(path)
        missing = path in missing_paths and valid_missing_source(source, common)
        admin_owner = source.get("missing_registration", {}).get("status") == "OBSERVED"
        historical = path in historical_paths
        empty = (historical and name == "WorkingRCX-worktrees"
                 and source.get("shell_entries") == [] and not registrations
                 and source.get("registration_status") == "not_registered"
                 and source.get("repository_kind") == "non_repository")
        shell = (residual and source.get("bus_only_shell") is True
                 and source.get("repository_kind") == "non_repository"
                 and source.get("inspection_status") == "not_repository"
                 and source.get("registration_status") == "not_registered" and not registrations)
        sync_dev = (residual and (fresh_wave or name == "workingrcx_clarolesfull_20260627")
                    and git.get("branch") == "refs/heads/dev")
        if (any(path == p or path.startswith(p + "/") for p in protected_paths)
                or re.match(r"workingrcx[-_](audit|admin|source)([-_]|$)", name, re.I)
                or (not retirement and any(h in PROTECTED_HEADS for h in [git.get("HEAD"), *(r.get("HEAD") for r in registrations)]))):
            hold("protected_evidence", "Primary, preservation, audit/admin/source, carrier or canonical queue evidence remains protected.")
        if not sync_dev and any(branch in ("refs/heads/dev", "refs/heads/main", "refs/heads/master")
               for branch in [git.get("branch"), *(r.get("branch") for r in registrations)]):
            hold("protected_branch", "dev/main/master worktrees cannot be selected.")
        if os.path.dirname(path) != census["fleet_root"] or not name.lower().startswith("workingrcx"):
            hold("outside_direct_fleet", "Registration is outside the direct WorkingRCX fleet-root scope.")
        if landed and name not in BOUNDED_CANDIDATE_NAMES:
            hold("outside_bounded_candidate_set", "Not in the finite candidate policy; no historical LANDED note releases preservation.")
        if source.get("availability_status") != "present" or source.get("entry_kind") != "directory":
            hold("unavailable_or_non_directory", "Missing, symlink or unknown entry remains HOLD; missing registration is not deleted-work evidence and must not be pruned.")
        if source.get("inspection_status") != "ok" or source.get("errors") != []:
            hold("inspection_uncertain", "Inspection did not succeed without errors; retain exact source evidence.")
        if source.get("repository_kind") != "linked_worktree":
            hold("not_linked_worktree", "Non-repository, standalone clone or unknown repository kind is ineligible.")
        git_dir = git.get("git_dir")
        if (git.get("root") != path or git.get("common_dir") != common
                or not _absolute(git_dir) or os.path.dirname(git_dir) != common + "/worktrees"):
            hold("repository_identity_uncertain", "Recorded root/common-dir/linked Git directory does not establish canonical repository identity.")
        if not _oid(git.get("HEAD")) or git.get("branch_status") != "symbolic" or not isinstance(git.get("branch"), str) or not git["branch"].startswith("refs/heads/") or len(git["branch"]) <= len("refs/heads/"):
            hold("head_or_branch_uncertain", "HEAD must be exact and the branch symbolic; detached/unknown states remain HOLD.")
        if (source.get("registration_status") != "registered" or len(registrations) != 1
                or any(registrations[0].get(k) != git.get(k) for k in ("HEAD", "branch"))
                or set(registrations[0]) != {"path", "HEAD", "branch"}):
            hold("registration_uncertain", "Registration must uniquely match inspected identity without locked/prunable/detached or unknown flags.")
        counts = git.get("dirty_counts")
        if (git.get("dirty_status") != "clean" or not isinstance(counts, dict)
                or set(counts) != set(DIRTY_KEYS)
                or any(type(counts[k]) is not int or counts[k] != 0 for k in DIRTY_KEYS)):
            hold("dirty_or_unknown", "Recorded dirty status/counts must be known and entirely clean; ignored evidence is still unproved.")
        if source.get("classification") != "UNCLASSIFIED" or not _observation_valid(source, census):
            hold("observation_uncertain", "Missing original unclassified observation identity or timing.")
        if residual:
            fs_identity = source.get("filesystem_identity", {})
            if (set(fs_identity) != {"device", "inode", "mode"}
                    or any(type(v) is not int for v in fs_identity.values())):
                hold("filesystem_identity_uncertain", "Fresh exact filesystem identity is required.")
            if shell and source.get("errors") == []:
                shell_exclusions = {"inspection_uncertain", "not_linked_worktree",
                                    "repository_identity_uncertain", "head_or_branch_uncertain",
                                    "registration_uncertain", "dirty_or_unknown"}
                reasons = [r for r in reasons if r["code"] not in shell_exclusions]
            elif (git.get("dirty_status") in {"clean", "dirty"} and isinstance(counts, dict)
                  and set(counts) == set(DIRTY_KEYS)
                  and all(type(v) is int and v >= 0 for v in counts.values())
                  and counts["unmerged"] == 0):
                # Full bytes/index/history are archived before native safe sync.
                reasons = [r for r in reasons if r["code"] != "dirty_or_unknown"]
        retirement_action = None
        if retirement and not shell and not empty:
            evidence = source.get("retirement_evidence", {})
            clone = source.get("repository_kind") == "standalone_repository"
            detached = git.get("branch_status") == "detached" and git.get("branch") is None
            expected_registration = dict(path=path, HEAD=git.get("HEAD"))
            expected_registration.update({"detached": True} if detached else {"branch": git.get("branch")})
            if detached and _oid(git.get("HEAD")):
                reasons = [r for r in reasons if r["code"] != "head_or_branch_uncertain"]
            if registrations == [expected_registration] and source.get("registration_status") == "registered":
                reasons = [r for r in reasons if r["code"] != "registration_uncertain"]
            if clone and (git.get("root") == path and git.get("common_dir") == path + "/.git"
                          and git.get("git_dir") == path + "/.git" and not registrations
                          and source.get("registration_status") == "not_registered"):
                reasons = [r for r in reasons if r["code"] not in {
                    "not_linked_worktree", "repository_identity_uncertain", "registration_uncertain"}]
            archive = evidence.get("preserved_operation")
            if archive and os.path.commonpath([path, census["fleet_root"]]) == census["fleet_root"]:
                reasons = [r for r in reasons if r["code"] != "outside_direct_fleet"]
                if archive.get("lifecycle_completion"):
                    reasons = [r for r in reasons if r["code"] != "protected_evidence"]
            if evidence.get("status") != "OBSERVED" or evidence.get("errors") != []:
                hold("retirement_ownership_unknown", "Fresh archive, native-bus and original journal evidence is required.")
            if git.get("branch") in {"refs/heads/dev", "refs/heads/main", "refs/heads/master"} and not clone:
                hold("protected_branch", "Active/base checkout remains a synchronization owner.")
            if any(j.get("state") not in {"HELD", "RECOVERED", "PREPARED"} for j in evidence.get("journals", [])):
                hold("pending_journal_owner", "Original native journal owner must resolve the exact unfinished transaction.")
            if any(not f["path"].startswith(".scratch/") or not f["path"].endswith(
                    "/test_metadata_rejects_fifo_wit0/mu/tools/executors/executor_common.py") for f in evidence.get("fifos", [])):
                hold("unknown_fifo_owner", "Only the captured idle pytest FIFO shape has preservation support.")
            if any(not link.get("dangling") or len(Path(link["path"]).parts) != 2
                    or Path(link["path"]).name != "bridge_config.json" for link in evidence.get("native_links", [])):
                hold("unknown_native_link_owner", "Native owner links require exact known dangling adapter evidence.")
            retirement_action = "RETIRE_CLONE" if clone else "RETIRE_ARCHIVE" if archive else "RETIRE_WORKTREE"
        if missing:
            exclusions = {"outside_direct_fleet", "unavailable_or_non_directory", "inspection_uncertain",
                "not_linked_worktree", "registration_uncertain", "dirty_or_unknown", "filesystem_identity_uncertain"}
            # Only the source-name heuristic is released. Explicit protected
            # paths, base branches and unknown Git identity still hold.
            if not any(path == p or path.startswith(p + "/") for p in protected_paths):
                exclusions.add("protected_evidence")
            reasons = [r for r in reasons if r["code"] not in exclusions]
            retirement_action = "RETIRE_MISSING_REGISTRATION"
        elif path in missing_paths:
            locks = source.get("missing_registration", {}).get("ownership_holds", [])
            if locks:
                hold("missing_admin_owned", "Original Git locks or unfinished operations remain: " + ", ".join(locks))
            else:
                hold("missing_admin_uncertain", "Explicit missing source lacks exact original admin/index/history evidence.")
        if historical:
            # The canonical preservation parent may protect an exact named
            # child; explicit --protect and the active carrier always win.
            if not any(path == p or path.startswith(p + "/") for p in (*protected, carrier, census["anchor_repo"])):
                reasons = [r for r in reasons if r["code"] not in {"protected_evidence", "outside_direct_fleet"}]
        if empty:
            reasons = [r for r in reasons if r["code"] not in {"inspection_uncertain", "not_linked_worktree",
                "repository_identity_uncertain", "head_or_branch_uncertain", "registration_uncertain", "dirty_or_unknown"}]
            if source.get("inspection_status") != "not_repository" or source.get("errors"):
                hold("empty_container_uncertain", "Exact empty container inspection failed.")
            retirement_action = "RETIRE_EMPTY_CONTAINER"
        ancestry = {"status": "NOT_APPLICABLE" if shell else "NOT_PROBED", "probes": []}
        if not reasons and not shell and not empty:
            head = git["HEAD"]
            if head not in cache:
                cache[head] = _ancestry(carrier, head, base_commit)
            ancestry = cache[head]
            if ancestry["status"] != "ANCESTOR" and not retirement:
                hold("unmerged_history" if ancestry["status"] == "NOT_ANCESTOR" else "ancestry_unknown",
                     "Local objects do not prove this recorded HEAD is an ancestor of the exact comparison commit.")
        decision = "HOLD" if reasons else "CONDITIONAL_RETIRE_CANDIDATE"
        if not reasons and residual:
            reasons.append({"code": "recorded_bus_shell" if shell else "recorded_eligible_ancestor",
                            "detail": "Fresh exact identity is conditionally eligible; liveness, byte preservation, safe preparation and the consumed terminal boundary remain required."})
        elif not reasons:
            reasons.append({"code": "recorded_eligible_ancestor", "detail": "Recorded clean symbolic canonical linked worktree satisfies the finite policy and local exact-base ancestry proof; apply prerequisites remain unmet."})
        rows.append({"source_index": index, "path": path, "source": source,
                     "decision": decision, "reasons": reasons, "ancestry": ancestry,
                     "apply_prerequisites": list(APPLY_PREREQUISITES) if decision != "HOLD" else [],
                     "mutation_authorized": False})
        if residual:
            rows[-1].update(
                owner=("native landing of retained " + str(git.get("branch"))
                       if any(r["code"] == "unmerged_history" for r in reasons)
                       else "[FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]"),
                proposed_action=("UNTOUCHED_HOLD" if decision == "HOLD" else
                                 "PRESERVE_BUS_SHELL" if shell else
                                 retirement_action if retirement_action else
                                 "SYNC_LOCAL_DEV" if sync_dev else "PRESERVE_WORKTREE"),
            )
        if fresh_wave:
            useful = source.get("useful_work", {})
            owner_id = selected_wave + "-useful-" + hashlib.sha256(path.encode("utf-8", "surrogateescape")).hexdigest()[:12]
            rows[-1]["useful_work"] = useful
            needs_landing = (useful.get("status") == "NEEDS_LANDING"
                and (admin_owner or source.get("availability_status") == "present")
                and source.get("repository_kind") in {"linked_worktree", "standalone_repository", "missing_linked_worktree"}
                and (os.path.dirname(path) == census["fleet_root"] or (retirement and
                     source.get("retirement_evidence", {}).get("preserved_operation")) or admin_owner or historical))
            rows[-1]["landing_owner"] = (
                None if not needs_landing else dict(
                    task="FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION", wave_id=owner_id,
                    source_path=path, source_head=git.get("HEAD"), source_branch=git.get("branch"),
                    comparison_commit=base_commit, status="PENDING_NATIVE_LANDING_REVIEW",
                    scope=sorted({c["path"] for c in useful.get("changes", [])}
                        | {p for commit in useful.get("local_commit_changes", []) for p in commit["paths"]}),
                    local_commits=useful.get("local_commits", []),
                    local_commit_changes=useful.get("local_commit_changes", []),
                    staged_patch_sha256=useful.get("staged_patch_sha256"),
                    unstaged_patch_sha256=useful.get("unstaged_patch_sha256"),
                    next_action="Native Phase A must compare the retained index/worktree and local commits to dev; land missing hunks before marking this owner complete."))
            if admin_owner and rows[-1]["landing_owner"]:
                rows[-1]["landing_owner"].update(unstaged_untracked_intent="UNKNOWN_ABSENT_CHECKOUT",
                    next_action="Compare retained index hunks and original receipts to dev; absent unstaged/untracked bytes remain unknown. Byte difference is not a production deficit.")
            if not shell and not empty and (not useful or useful.get("status") == "UNKNOWN"):
                # Inventory uncertainty never becomes preservation permission.
                if rows[-1]["decision"] != "HOLD":
                    rows[-1].update(decision="HOLD", proposed_action="UNTOUCHED_HOLD", apply_prerequisites=[])
                rows[-1]["reasons"].append(dict(code="useful_work_unknown", detail="Exact useful-work inventory requires the recorded native owner."))
            if retirement:
                current_review = rows[-1]["landing_owner"]
                if current_review:
                    current_review.update(wave_id=selected_wave,
                        source_key=hashlib.sha256(os.fsencode(path)).hexdigest(),
                        status="PENDING_EXACT_HUNK_REVIEW")
                rows[-1]["current_landing_review"] = current_review
                inherited = source.get("retirement_evidence", {}).get("preserved_operation") or {}
                previous_owners = [r["landing_owner"] for r in source.get("retirement_evidence", {}).get("prior_owners", [])
                                   if r.get("landing_owner")]
                rows[-1]["inherited_landing_owners"] = previous_owners
                if inherited.get("landing_owner"):
                    rows[-1]["landing_owner"] = inherited["landing_owner"]
                elif previous_owners:
                    rows[-1]["landing_owner"] = previous_owners[-1]
                if rows[-1]["decision"] != "HOLD":
                    rows[-1]["reasons"] = [dict(code="recorded_retirement_source",
                        detail="Exact historical source retained independently; preservation, original owners and one-shot retirement must be verified at action time.")]
                    rows[-1]["apply_prerequisites"] = [
                        "UNMET: Verify exact source/index/bytes/refs, native owners, journals and liveness under lock.",
                        "UNMET: Independently recover the original history and index before source/registration retirement.",
                        "UNMET: Consume a fresh source-and-preservation-bound terminal operation on synchronized PRIMARY; preserve original claims."]
    counts = Counter(r["decision"] for r in rows)
    report = {
        "schema_version": 1, "observation_kind": "read_only_fleet_classification",
        "wave_id": WAVE_ID, "source_sha256": source_sha256, "comparison_commit": base_commit,
        "object_query_carrier": carrier, "source_metadata": {k: v for k, v in census.items() if k != "entries"},
        "coverage_complete": True, "entry_count": len(rows),
        "decision_counts": {d: counts[d] for d in DECISIONS},
        "reason_counts": dict(sorted(Counter(reason["code"] for r in rows for reason in r["reasons"]).items())),
        "policy": {"authority": "TASKS.md: 2026-09-11 " + WAVE_ID + " tracker note and canonical queue",
                   "canonical_common_dir": common, "protected_paths": sorted(set(protected_paths)),
                   "protected_heads": list(PROTECTED_HEADS),
                   "bounded_candidate_paths": [census["fleet_root"] + "/" + n for n in BOUNDED_CANDIDATE_NAMES] if landed else "disposable inventory: same recorded eligibility gates",
                   "unlisted_targets": "HOLD; no implicit release of active or preserved evidence"},
        "limitations": ["Classification only; no target inspected or mutated and no reusable mutation authority.",
                        "Coverage is of recorded census rows, not current filesystem directories or a coherent action-time snapshot.",
                        "Source cleanliness excludes ignored files. Liveness, evidence preservation and action-time identity remain unproved.",
                        "Only local carrier objects were queried, with lazy fetching, optional writes, replacement objects and grafts disabled.",
                        "Every HOLD remains unresolved; apply is immediate next only after classification lands."],
        "mutation_authorized": False, "entries": rows,
    }

    if residual:
        selected = [r["source_index"] for r in rows if r["decision"] != "HOLD"]
        report.update(wave_id=selected_wave,
                      batch_size=RESIDUAL_BATCH_SIZE,
                      batches=[selected[i:i + RESIDUAL_BATCH_SIZE]
                               for i in range(0, len(selected), RESIDUAL_BATCH_SIZE)])
        report["policy"].update(
            authority="TASKS.md: " + selected_wave + " tracker note",
            bounded_candidate_paths=[r["path"] for r in rows if r["decision"] != "HOLD"],
            unlisted_targets="HOLD individually; historical HOLDs were freshly reassessed",
        )
        report["limitations"][-1] = "Committed foreground plan/apply/verify remains required for every bounded operation."
    if retirement:
        report["retirement"] = True
        report["policy"]["protected_heads"] = []
    if authority is not None:
        report["retirement_authority"] = authority
    if missing_paths or historical_paths:
        report["policy"].update(missing_registration_paths=list(missing_paths),
                                reviewed_historical_paths=list(historical_paths),
                                explicit_protected_paths=sorted(set((*protected, carrier, census["anchor_repo"]))))
    return report


def useful_work_report(classification: dict, classification_sha256: str) -> dict:
    """Full per-target landing stubs, bound to this immutable classification."""
    rows = [dict(path=row["path"], source_index=row["source_index"],
                 repository_kind=row["source"]["repository_kind"],
                 disposition=row["proposed_action"], owner=row["owner"],
                 inventory=row.get("useful_work"), landing_owner=row.get("landing_owner"))
            for row in classification["entries"]]
    if classification.get("retirement"):
        for row, source in zip(rows, classification["entries"]):
            row["inherited_landing_owners"] = source.get("inherited_landing_owners", [])
            row["current_landing_review"] = source.get("current_landing_review")
    return dict(schema_version=1, wave_id=classification["wave_id"],
        **({"retirement_authority": classification["retirement_authority"]}
           if "retirement_authority" in classification else {}),
        census_sha256=classification["source_sha256"], classification_sha256=classification_sha256,
        comparison_commit=classification["comparison_commit"], entries=rows, entry_count=len(rows),
        landing_owners=sum(row["landing_owner"] is not None for row in rows),
        completion="PENDING_NATIVE_LANDINGS_AND_COMMITTED_LIVE_ACTIONS")


def retirement_coverage_report(classification: dict, classification_sha256: str) -> dict:
    """Keep independent byte/hunk proof separate from historical owner closure."""
    entries = []
    for row in classification["entries"]:
        useful = row.get("useful_work") or {}
        evidence = row["source"].get("retirement_evidence") or {}
        inherited = evidence.get("preserved_operation")
        entries.append(dict(source_index=row["source_index"], path=row["path"],
            head=row["source"]["git"]["HEAD"], source_action=row["proposed_action"],
            current_source_coverage=useful.get("status", "UNKNOWN"),
            changes=useful.get("changes", []), commits=useful.get("local_commit_changes", []),
            landing_owner=row.get("landing_owner"), inherited_operation=inherited,
            current_landing_review=row.get("current_landing_review"),
            prior_operation_owners=evidence.get("prior_owners", []),
            retained_journal_owners=[dict(**journal,
                task="FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION",
                disposition="PRESERVED_ORIGINAL_INTENT_REQUIRES_REVIEW" if journal.get("held_paths")
                    or journal.get("state") == "PREPARED" else "HISTORICAL_RECOVERY_EVIDENCE",
                integration_completed=False) for journal in evidence.get("journals", [])]))
    return dict(schema_version=1, wave_id=classification["wave_id"],
        **({"retirement_authority": classification["retirement_authority"]}
           if "retirement_authority" in classification else {}),
        comparison_commit=classification["comparison_commit"], classification_sha256=classification_sha256,
        census_sha256=classification["source_sha256"], mutation_authorized=False, entries=entries,
        evidence_policy="Exact reverse binary patches and comparison blobs prove only the recorded source changes. A failed comparison requires hunk review, not an inference of missing code. Inherited owners and held journal intent remain open independently.",
        completion="PENDING_NATIVE_LANDING_REVIEW_AND_FOREGROUND_RETIREMENT")


def _write_or_verify(path: str, payload: bytes) -> None:
    """Exclusive creation or exact regular-file verification; never clobber."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as existing:
            info = os.fstat(existing.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or existing.read() != payload:
                raise ValueError("Refusing unrelated, linked or different existing output")
    else:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)


def _output_path(output: str, census: dict, carrier: str, landed: bool) -> str:
    # Resolve only the requested output parent, never a census target. Refuse
    # symlinked parents and lexical target/Git metadata destinations before open.
    path = os.path.abspath(output)
    if str(Path(path).parent.resolve(strict=True)) != os.path.dirname(path):
        raise ValueError("Output parent must be an exact directory, without symlink aliases")
    if landed:
        if path != carrier + "/reports/control_plane/" + WAVE_ID + "_classification.json":
            raise ValueError("Landed classification may write only its wave-owned report")
    else:
        protected = [LANDED_FLEET, carrier + "/.git"]
        for row in census["entries"]:
            protected.append(row["path"])
            git = row.get("git")
            if isinstance(git, dict):
                protected.extend(p for p in (git.get("common_dir"), git.get("git_dir")) if _absolute(p))
        if any(path == p or path.startswith(p + "/") for p in protected):
            raise ValueError("Output would write into a census target or Git metadata")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--residual", action="store_true", help="Fresh manifest-bound residual batches; historical authority is unchanged")
    parser.add_argument("--retirement", action="store_true", help="Fresh preservation-first physical/registration retirement")
    parser.add_argument("--retirement-predecessor", help="Explicit exact comparison commit for a new reviewed retirement authority; cannot rebind the original wave")
    parser.add_argument("--wave-id", help="Fresh residual owner; omitted retains the legacy authority")
    parser.add_argument("--protect", action="append", default=[], help="Exact additional active/preserved source path")
    parser.add_argument("--missing-registration", action="append", default=[], help="One exact observed admin-only source; repeated finite opt-in")
    parser.add_argument("--historical-source", action="append", default=[], help="One exact enumerated historical source in this wave")
    parser.add_argument("--census", required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-census-sha256", help="Required raw SHA-256 for disposable census fixtures")
    args = parser.parse_args(argv)
    try:
        raw = Path(args.census).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        census = json.loads(raw, object_pairs_hook=_unique_object,
                            parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON: " + value)))
        _validate_inventory(census)
        historical = Path(args.census).name == LANDED_CENSUS or digest == LANDED_SHA256
        if args.residual and historical:
            raise ValueError("Residual operations require a fresh census, never historical authority")
        landed = not args.residual and (historical or census["fleet_root"] == LANDED_FLEET)
        expected = LANDED_SHA256 if landed else args.expected_census_sha256
        if (not expected or digest != expected
                or args.expected_census_sha256 not in (None, expected)):
            raise ValueError("Raw census SHA-256 binding mismatch or missing fixture hash")
        if args.residual:
            output = os.path.abspath(args.output)
            expected_output = os.getcwd() + "/reports/control_plane/" + (args.wave_id or RESIDUAL_WAVE_ID) + "_classification.json"
            if output != expected_output or str(Path(output).parent.resolve(strict=True)) != os.path.dirname(output):
                raise ValueError("Residual classification may write only its wave-owned report")
        else:
            output = _output_path(args.output, census, os.getcwd(), landed)
        report = classify(census, source_sha256=digest, base_commit=args.base_commit,
                          carrier=os.getcwd(), landed=landed, residual=args.residual,
                          wave_id=args.wave_id, protected=tuple(args.protect), retirement=args.retirement,
                          retirement_predecessor=args.retirement_predecessor,
                          missing_paths=tuple(args.missing_registration), historical_paths=tuple(args.historical_source))
        payload = (json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii")
        _write_or_verify(output, payload)
        if args.wave_id and args.wave_id != RESIDUAL_WAVE_ID:
            useful = useful_work_report(report, hashlib.sha256(payload).hexdigest())
            _write_or_verify(os.getcwd() + "/reports/control_plane/" + args.wave_id + "_useful_work.json",
                             (json.dumps(useful, indent=2, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii"))
        if args.retirement:
            coverage = retirement_coverage_report(report, hashlib.sha256(payload).hexdigest())
            _write_or_verify(os.getcwd() + "/reports/control_plane/" + args.wave_id + "_useful_work_coverage.json",
                             (json.dumps(coverage, indent=2, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii"))
        print(json.dumps({"entry_count": report["entry_count"], "decision_counts": report["decision_counts"],
                          "source_sha256": digest, "comparison_commit": args.base_commit}, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"classification refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
