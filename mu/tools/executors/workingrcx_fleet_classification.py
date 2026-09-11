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


def classify(census: dict, *, source_sha256: str, base_commit: str,
             carrier: str, landed: bool) -> dict:
    """Return one decision per validated row using only carrier-local objects."""
    _validate_inventory(census)
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
    protected_paths += [census["anchor_repo"], carrier]
    rows, cache = [], {}
    for index, source in enumerate(census["entries"]):
        path, reasons = source["path"], []
        git = source.get("git") if isinstance(source.get("git"), dict) else {}
        registrations = source["registered_worktrees"]
        def hold(code: str, detail: str) -> None:
            reasons.append({"code": code, "detail": detail})
        name = os.path.basename(path)
        if (any(path == p or path.startswith(p + "/") for p in protected_paths)
                or re.match(r"workingrcx[-_](audit|admin|source)([-_]|$)", name, re.I)
                or any(h in PROTECTED_HEADS for h in [git.get("HEAD"), *(r.get("HEAD") for r in registrations)])):
            hold("protected_evidence", "Primary, preservation, audit/admin/source, carrier or canonical queue evidence remains protected.")
        if any(branch in ("refs/heads/dev", "refs/heads/main", "refs/heads/master")
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
        ancestry = {"status": "NOT_PROBED", "probes": []}
        if not reasons:
            head = git["HEAD"]
            if head not in cache:
                cache[head] = _ancestry(carrier, head, base_commit)
            ancestry = cache[head]
            if ancestry["status"] != "ANCESTOR":
                hold("unmerged_history" if ancestry["status"] == "NOT_ANCESTOR" else "ancestry_unknown",
                     "Local objects do not prove this recorded HEAD is an ancestor of the exact comparison commit.")
        decision = "HOLD" if reasons else "CONDITIONAL_RETIRE_CANDIDATE"
        if not reasons:
            reasons.append({"code": "recorded_eligible_ancestor", "detail": "Recorded clean symbolic canonical linked worktree satisfies the finite policy and local exact-base ancestry proof; apply prerequisites remain unmet."})
        rows.append({"source_index": index, "path": path, "source": source,
                     "decision": decision, "reasons": reasons, "ancestry": ancestry,
                     "apply_prerequisites": list(APPLY_PREREQUISITES) if decision != "HOLD" else [],
                     "mutation_authorized": False})
    counts = Counter(r["decision"] for r in rows)
    return {
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
        landed = (Path(args.census).name == LANDED_CENSUS or census["fleet_root"] == LANDED_FLEET
                  or digest == LANDED_SHA256)
        expected = LANDED_SHA256 if landed else args.expected_census_sha256
        if (not expected or digest != expected
                or args.expected_census_sha256 not in (None, expected)):
            raise ValueError("Raw census SHA-256 binding mismatch or missing fixture hash")
        output = _output_path(args.output, census, os.getcwd(), landed)
        report = classify(census, source_sha256=digest, base_commit=args.base_commit,
                          carrier=os.getcwd(), landed=landed)
        payload = (json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii")
        _write_or_verify(output, payload)
        print(json.dumps({"entry_count": report["entry_count"], "decision_counts": report["decision_counts"],
                          "source_sha256": digest, "comparison_commit": args.base_commit}, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"classification refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
