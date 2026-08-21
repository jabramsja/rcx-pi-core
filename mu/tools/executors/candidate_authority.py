#!/usr/bin/env python3
"""Candidate-authority builder for Phase B pre-review entry.

The builder is intentionally repository-local but bus-local in its durable
outputs: it stages only a declared allowlist in a target repository, validates
the resulting literal-base candidate inventory, runs the same-wave L4 indicator
collector, enforces the staged L4 contract when present, and writes an ignored
receipt bound to the current staged candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


class CandidateAuthorityError(RuntimeError):
    """Raised when candidate authority cannot be established or verified."""


CANONICAL_COLLECTOR_PATH = "tools/metrics/collect_l4_wave_indicators.py"
CANONICAL_MU_COLLECTOR_PATH = "mu/tools/metrics/collect_l4_wave_indicators.py"
CANONICAL_COLLECTOR_PATHS = frozenset(
    {CANONICAL_COLLECTOR_PATH, CANONICAL_MU_COLLECTOR_PATH}
)
_VALID_L4_SKIP_REASONS = frozenset({"missing_l4_checker", "spec_disabled"})
_RECEIPT_VERSION = 1


def _run_git(
    repo_root: Path,
    args: list[str],
    *,
    text: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=text,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", "replace")
        stdout = result.stdout if text else result.stdout.decode("utf-8", "replace")
        detail = (stderr or stdout or "").strip()
        raise CandidateAuthorityError(
            f"git {' '.join(args)} failed with exit={result.returncode}: {detail}"
        )
    return result


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_hash(value: Any) -> str:
    return _sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _normalize_repo_path(path: str) -> str:
    if not isinstance(path, str):
        raise CandidateAuthorityError("candidate path must be a string")
    raw = path.strip().replace("\\", "/")
    if not raw:
        raise CandidateAuthorityError("candidate path cannot be empty")
    if "\0" in raw:
        raise CandidateAuthorityError(f"candidate path contains NUL: {path!r}")
    if raw.startswith("/"):
        raise CandidateAuthorityError(f"candidate path must be repo-relative: {path!r}")
    posix = PurePosixPath(raw)
    parts = posix.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise CandidateAuthorityError(f"candidate path is unsafe: {path!r}")
    normalized = posix.as_posix()
    if normalized == "." or normalized.startswith("../") or "/../" in normalized:
        raise CandidateAuthorityError(f"candidate path escapes repository: {path!r}")
    if normalized == ".git" or normalized.startswith(".git/"):
        raise CandidateAuthorityError(f"candidate path targets git control data: {path!r}")
    return normalized


def normalize_allowlist(paths: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for path in paths:
        clean = _normalize_repo_path(path)
        if clean in seen:
            raise CandidateAuthorityError(f"duplicate candidate allowlist path: {clean}")
        seen.add(clean)
        normalized.append(clean)
    if not normalized:
        raise CandidateAuthorityError("candidate allowlist cannot be empty")
    return tuple(sorted(normalized))


def validate_comparison_commit(repo_root: Path, commit: str) -> str:
    raw = str(commit or "").strip()
    if not raw:
        raise CandidateAuthorityError("comparison commit is required")
    _run_git(repo_root, ["cat-file", "-e", f"{raw}^{{commit}}"])
    result = _run_git(repo_root, ["rev-parse", f"{raw}^{{commit}}"])
    return str(result.stdout).strip()


def _repo_identity(repo_root: Path) -> dict[str, str]:
    top = str(_run_git(repo_root, ["rev-parse", "--show-toplevel"]).stdout).strip()
    common_dir = str(_run_git(repo_root, ["rev-parse", "--git-common-dir"]).stdout).strip()
    common_path = Path(common_dir)
    if not common_path.is_absolute():
        common_path = repo_root / common_path
    return {
        "worktree_root": str(Path(top).resolve()),
        "git_common_dir": str(common_path.resolve()),
    }


def _parse_diff_raw_z(data: bytes) -> list[dict[str, Any]]:
    if not data:
        return []
    fields = data.split(b"\0")
    if fields and fields[-1] == b"":
        fields = fields[:-1]
    entries: list[dict[str, Any]] = []
    i = 0
    while i < len(fields):
        header = fields[i].decode("utf-8", "surrogateescape")
        i += 1
        if not header.startswith(":"):
            raise CandidateAuthorityError(f"unexpected git diff --raw header: {header!r}")
        parts = header[1:].split()
        if len(parts) != 5:
            raise CandidateAuthorityError(f"malformed git diff --raw header: {header!r}")
        old_mode, new_mode, old_oid, new_oid, status_token = parts
        if i >= len(fields):
            raise CandidateAuthorityError(f"missing path for git diff --raw entry: {header!r}")
        old_path = fields[i].decode("utf-8", "surrogateescape")
        i += 1
        status = status_token[0]
        score = status_token[1:] or ""
        entry: dict[str, Any] = {
            "kind": "tracked",
            "status": status,
            "score": score,
            "old_mode": old_mode,
            "new_mode": new_mode,
            "old_oid": old_oid,
            "new_oid": new_oid,
            "path": _normalize_repo_path(old_path),
        }
        if status in {"R", "C"}:
            if i >= len(fields):
                raise CandidateAuthorityError(
                    f"missing destination path for git diff --raw entry: {header!r}"
                )
            new_path = fields[i].decode("utf-8", "surrogateescape")
            i += 1
            entry["old_path"] = entry.pop("path")
            entry["path"] = _normalize_repo_path(new_path)
        entries.append(entry)
    return entries


def _ls_untracked(repo_root: Path) -> list[str]:
    result = _run_git(
        repo_root,
        ["ls-files", "--others", "--exclude-standard", "-z"],
        text=False,
    )
    data = bytes(result.stdout)
    if not data:
        return []
    return sorted(
        _normalize_repo_path(item.decode("utf-8", "surrogateescape"))
        for item in data.split(b"\0")
        if item
    )


def collect_literal_base_inventory(
    repo_root: Path,
    comparison_commit: str,
) -> list[dict[str, Any]]:
    """Return sorted tracked diff and non-ignored untracked inventory."""
    base = validate_comparison_commit(repo_root, comparison_commit)
    raw = _run_git(
        repo_root,
        ["diff", "--raw", "-z", "--no-abbrev", "-M", base, "--"],
        text=False,
    )
    entries = _parse_diff_raw_z(bytes(raw.stdout))
    for path in _ls_untracked(repo_root):
        entries.append({"kind": "untracked", "status": "??", "path": path})
    return sorted(
        entries,
        key=lambda item: (
            item.get("path", ""),
            item.get("old_path", ""),
            item.get("kind", ""),
            item.get("status", ""),
        ),
    )


def collect_staged_literal_base_inventory(
    repo_root: Path,
    comparison_commit: str,
) -> list[dict[str, Any]]:
    """Return sorted staged tracked diff inventory against the literal base."""
    base = validate_comparison_commit(repo_root, comparison_commit)
    raw = _run_git(
        repo_root,
        ["diff", "--cached", "--raw", "-z", "--no-abbrev", "-M", base, "--"],
        text=False,
    )
    entries = _parse_diff_raw_z(bytes(raw.stdout))
    return sorted(
        entries,
        key=lambda item: (
            item.get("path", ""),
            item.get("old_path", ""),
            item.get("kind", ""),
            item.get("status", ""),
        ),
    )


def _entry_paths(entry: dict[str, Any]) -> set[str]:
    paths = {str(entry["path"])}
    old_path = entry.get("old_path")
    if old_path:
        paths.add(str(old_path))
    return paths


def _inventory_paths(inventory: list[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for entry in inventory:
        paths.update(_entry_paths(entry))
    return paths


def _reject_outside_allowlist(inventory: list[dict[str, Any]], allowlist: set[str]) -> None:
    outside = sorted(path for path in _inventory_paths(inventory) if path not in allowlist)
    if outside:
        raise CandidateAuthorityError(
            "candidate inventory contains path(s) outside allowlist: "
            + ", ".join(outside)
        )


def _unstaged_allowed_residue(repo_root: Path, allowlist: tuple[str, ...]) -> list[str]:
    result = _run_git(
        repo_root,
        ["diff", "--name-only", "-z", "--", *allowlist],
        text=False,
    )
    return sorted(
        _normalize_repo_path(item.decode("utf-8", "surrogateescape"))
        for item in bytes(result.stdout).split(b"\0")
        if item
    )


def _validate_indicator_command(
    *,
    wave_id: str,
    indicator_artifact_ref: str,
    indicator_collection_command: str,
) -> list[str]:
    try:
        argv = shlex.split(indicator_collection_command)
    except ValueError as exc:
        raise CandidateAuthorityError(
            f"indicator_collection_command is not parseable: {exc}"
        ) from exc
    if len(argv) < 2:
        raise CandidateAuthorityError("indicator_collection_command is incomplete")
    script = _normalize_repo_path(argv[1] if Path(argv[0]).name.startswith("python") else argv[0])
    if script not in CANONICAL_COLLECTOR_PATHS:
        raise CandidateAuthorityError(
            "indicator_collection_command must use one of "
            f"{sorted(CANONICAL_COLLECTOR_PATHS)!r} (got {script!r})"
        )
    parsed_wave = ""
    parsed_output = ""
    for idx, token in enumerate(argv):
        if token == "--wave-id" and idx + 1 < len(argv):
            parsed_wave = argv[idx + 1]
        if token == "--output" and idx + 1 < len(argv):
            parsed_output = argv[idx + 1]
    if parsed_wave != wave_id:
        raise CandidateAuthorityError(
            "indicator_collection_command wave mismatch: "
            f"expected {wave_id!r}, got {parsed_wave!r}"
        )
    if _normalize_repo_path(parsed_output) != indicator_artifact_ref:
        raise CandidateAuthorityError(
            "indicator_collection_command output mismatch: "
            f"expected {indicator_artifact_ref!r}, got {parsed_output!r}"
        )
    return argv


def validate_indicator_declaration(
    *,
    wave_id: str,
    indicator_artifact_ref: str,
    indicator_collection_command: str,
) -> None:
    artifact = _normalize_repo_path(indicator_artifact_ref)
    if artifact != f"reports/l4_wave_indicators/{wave_id}.json":
        raise CandidateAuthorityError(
            "indicator_artifact_ref must be the same-wave canonical artifact "
            f"(expected reports/l4_wave_indicators/{wave_id}.json, got {artifact!r})"
        )
    _validate_indicator_command(
        wave_id=wave_id,
        indicator_artifact_ref=artifact,
        indicator_collection_command=indicator_collection_command,
    )


def _collect_indicator(
    repo_root: Path,
    *,
    wave_id: str,
    indicator_artifact_ref: str,
    indicator_collection_command: str,
) -> None:
    argv = _validate_indicator_command(
        wave_id=wave_id,
        indicator_artifact_ref=indicator_artifact_ref,
        indicator_collection_command=indicator_collection_command,
    )
    result = subprocess.run(
        argv,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CandidateAuthorityError(
            f"indicator collector failed with exit={result.returncode}: {detail}"
        )
    if not (repo_root / indicator_artifact_ref).is_file():
        raise CandidateAuthorityError(
            f"indicator collector did not produce {indicator_artifact_ref}"
        )


def _stage_paths(repo_root: Path, paths: list[str]) -> None:
    if not paths:
        return
    result = _run_git(repo_root, ["add", "-A", "--", *paths], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CandidateAuthorityError(
            f"git add -A failed for candidate allowlist paths: {detail}"
        )


def _enforce_staged_l4_contract(repo_root: Path, *, wave_id: str, wave_class: str) -> dict[str, Any]:
    checker = repo_root / "tools" / "checks" / "enforce_l4_execution_contract.py"
    if not checker.exists():
        return {"status": "skipped", "reason": "missing_l4_checker"}
    result = subprocess.run(
        [
            sys.executable,
            "tools/checks/enforce_l4_execution_contract.py",
            "--staged",
            "--wave-id",
            wave_id,
            "--wave-class",
            wave_class,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise CandidateAuthorityError(
            f"staged L4 execution contract failed with exit={result.returncode}: {detail}"
        )
    return {"status": "passed"}


def _normalize_l4_contract_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CandidateAuthorityError("l4_contract must be a JSON object")
    status = value.get("status")
    if status == "passed":
        if set(value) != {"status"}:
            raise CandidateAuthorityError(
                "l4_contract passed result must contain only status"
            )
        return {"status": "passed"}
    if status == "skipped":
        reason = value.get("reason")
        if reason not in _VALID_L4_SKIP_REASONS:
            raise CandidateAuthorityError(
                "l4_contract skipped result has invalid reason: "
                f"{reason!r}"
            )
        if set(value) != {"status", "reason"}:
            raise CandidateAuthorityError(
                "l4_contract skipped result must contain only status and reason"
            )
        return {"status": "skipped", "reason": str(reason)}
    raise CandidateAuthorityError(f"l4_contract has invalid status: {status!r}")


def _receipt_require_l4_staged(receipt: dict[str, Any]) -> bool:
    raw = receipt.get("require_l4_staged", True)
    if not isinstance(raw, bool):
        raise CandidateAuthorityError("require_l4_staged must be a boolean")
    return raw


def _read_file_hash(repo_root: Path, rel_path: str) -> str:
    path = repo_root / rel_path
    if not path.is_file():
        raise CandidateAuthorityError(f"required file is missing: {rel_path}")
    return _sha256_bytes(path.read_bytes())


def _plan_hash(repo_root: Path, plan_path: str, explicit_hash: str = "") -> str:
    if explicit_hash:
        return explicit_hash
    if not plan_path or plan_path.startswith("<"):
        return ""
    return _read_file_hash(repo_root, _normalize_repo_path(plan_path))


def _index_tree_hash(repo_root: Path) -> str:
    return str(_run_git(repo_root, ["write-tree"]).stdout).strip()


def _staged_binary_diff_hash(repo_root: Path, comparison_commit: str) -> str:
    result = _run_git(
        repo_root,
        [
            "diff",
            "--cached",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            comparison_commit,
            "--",
        ],
        text=False,
    )
    return _sha256_bytes(bytes(result.stdout))


def _bus_root(repo_root: Path, bus_dir: str | Path | None) -> Path:
    if bus_dir is None:
        return repo_root / ".agent_bus"
    raw = Path(bus_dir)
    if raw.is_absolute():
        return raw
    return repo_root / raw


def _ensure_bus_ignored(repo_root: Path, bus_dir: str | Path | None) -> None:
    bus_root = _bus_root(repo_root, bus_dir)
    try:
        rel = bus_root.resolve(strict=False).relative_to(repo_root.resolve())
    except ValueError:
        return
    pattern = f"/{rel.as_posix().rstrip('/')}/"
    exclude_path = Path(
        str(_run_git(repo_root, ["rev-parse", "--git-path", "info/exclude"]).stdout).strip()
    )
    if not exclude_path.is_absolute():
        exclude_path = repo_root / exclude_path
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    if pattern not in existing.splitlines():
        with exclude_path.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(pattern + "\n")


def authority_spec_path(
    repo_root: Path,
    *,
    bus_dir: str | Path | None,
    wave_id: str,
) -> Path:
    return _bus_root(repo_root, bus_dir) / "meta" / "candidate_authority" / f"{wave_id}.spec.json"


def receipt_path_for(
    repo_root: Path,
    *,
    bus_dir: str | Path | None,
    wave_id: str,
    phase: str,
    review_round: str,
) -> Path:
    safe_phase = _normalize_token(phase, "phase")
    safe_round = _normalize_token(review_round, "review round")
    return (
        _bus_root(repo_root, bus_dir)
        / "meta"
        / "candidate_authority_receipts"
        / wave_id
        / f"{safe_phase}-{safe_round}.json"
    )


def _normalize_token(value: str, label: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise CandidateAuthorityError(f"{label} is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(ch not in allowed for ch in token):
        raise CandidateAuthorityError(f"{label} contains unsafe characters: {token!r}")
    return token


@dataclass(frozen=True)
class CandidateAuthoritySpec:
    wave_id: str
    comparison_commit: str
    candidate_allowlist: tuple[str, ...] = field(default_factory=tuple)
    plan_path: str = ""
    plan_hash: str = ""
    phase: str = "phase_b"
    review_round: str = "review"
    indicator_artifact_ref: str = ""
    indicator_collection_command: str = ""
    wave_class: str = "L4_ENABLER"
    require_l4_staged: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "CandidateAuthoritySpec":
        if not isinstance(data, dict):
            raise CandidateAuthorityError("candidate authority spec must be a JSON object")
        return cls(
            wave_id=str(data.get("wave_id", "")).strip(),
            comparison_commit=str(data.get("comparison_commit", "")).strip(),
            candidate_allowlist=normalize_allowlist(data.get("candidate_allowlist", [])),
            plan_path=str(data.get("plan_path", "")).strip(),
            plan_hash=str(data.get("plan_hash", "")).strip(),
            phase=str(data.get("phase", "phase_b")).strip() or "phase_b",
            review_round=str(data.get("review_round", "review")).strip() or "review",
            indicator_artifact_ref=str(data.get("indicator_artifact_ref", "")).strip(),
            indicator_collection_command=str(data.get("indicator_collection_command", "")).strip(),
            wave_class=str(data.get("wave_class", "L4_ENABLER")).strip() or "L4_ENABLER",
            require_l4_staged=bool(data.get("require_l4_staged", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "wave_id": self.wave_id,
            "comparison_commit": self.comparison_commit,
            "candidate_allowlist": list(self.candidate_allowlist),
            "plan_path": self.plan_path,
            "plan_hash": self.plan_hash,
            "phase": self.phase,
            "review_round": self.review_round,
            "indicator_artifact_ref": self.indicator_artifact_ref,
            "indicator_collection_command": self.indicator_collection_command,
            "wave_class": self.wave_class,
            "require_l4_staged": self.require_l4_staged,
        }


def build_spec_from_wave_config(config: Any, *, phase: str, review_round: str) -> CandidateAuthoritySpec:
    return CandidateAuthoritySpec(
        wave_id=str(config.wave_id).strip(),
        comparison_commit=str(config.comparison_commit).strip(),
        candidate_allowlist=normalize_allowlist(config.candidate_allowlist),
        plan_path=str(config.tracked_packet).strip(),
        phase=phase,
        review_round=review_round,
        indicator_artifact_ref=str(config.indicator_artifact_ref).strip(),
        indicator_collection_command=str(config.indicator_collection_command).strip(),
        wave_class=str(config.wave_class).strip() or "L4_ENABLER",
        require_l4_staged=bool(config.pre_review_authority),
    )


def write_authority_spec(
    repo_root: Path,
    spec: CandidateAuthoritySpec,
    *,
    bus_dir: str | Path | None,
) -> Path:
    _ensure_bus_ignored(repo_root, bus_dir)
    path = authority_spec_path(repo_root, bus_dir=bus_dir, wave_id=spec.wave_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, spec.to_dict())
    return path


def load_authority_spec(path: Path) -> CandidateAuthoritySpec:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise CandidateAuthorityError(f"cannot read authority spec {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CandidateAuthorityError(f"authority spec is not JSON: {path}: {exc}") from exc
    return CandidateAuthoritySpec.from_mapping(data)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _receipt_payload(
    repo_root: Path,
    spec: CandidateAuthoritySpec,
    *,
    comparison_commit: str,
    inventory: list[dict[str, Any]],
    staged_inventory: list[dict[str, Any]],
    indicator_hash: str,
    l4_contract: dict[str, Any],
) -> dict[str, Any]:
    allowlist = normalize_allowlist(spec.candidate_allowlist)
    normalized_l4_contract = _normalize_l4_contract_result(l4_contract)
    return {
        "version": _RECEIPT_VERSION,
        "repository": _repo_identity(repo_root),
        "wave_id": spec.wave_id,
        "comparison_commit": comparison_commit,
        "candidate_allowlist": list(allowlist),
        "candidate_allowlist_hash": _json_hash(list(allowlist)),
        "phase": _normalize_token(spec.phase, "phase"),
        "review_round": _normalize_token(spec.review_round, "review round"),
        "plan_path": spec.plan_path,
        "plan_hash": _plan_hash(repo_root, spec.plan_path, spec.plan_hash),
        "indicator_artifact_ref": spec.indicator_artifact_ref,
        "indicator_hash": indicator_hash,
        "wave_class": spec.wave_class,
        "require_l4_staged": bool(spec.require_l4_staged),
        "literal_base_inventory": inventory,
        "literal_base_inventory_hash": _json_hash(inventory),
        "staged_literal_base_inventory": staged_inventory,
        "staged_literal_base_inventory_hash": _json_hash(staged_inventory),
        "index_tree_hash": _index_tree_hash(repo_root),
        "staged_binary_diff_sha256": _staged_binary_diff_hash(repo_root, comparison_commit),
        "l4_contract": normalized_l4_contract,
        "l4_contract_hash": _json_hash(normalized_l4_contract),
    }


def prepare_candidate_authority(
    repo_root: Path,
    spec: CandidateAuthoritySpec,
    *,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    comparison_commit = validate_comparison_commit(repo_root, spec.comparison_commit)
    allowlist = normalize_allowlist(spec.candidate_allowlist)
    allowset = set(allowlist)

    if spec.plan_path and not spec.plan_path.startswith("<"):
        plan_path = _normalize_repo_path(spec.plan_path)
        if plan_path not in allowset:
            raise CandidateAuthorityError(
                f"plan path is outside candidate allowlist: {plan_path}"
            )
    indicator_path = ""
    if spec.indicator_artifact_ref:
        indicator_path = _normalize_repo_path(spec.indicator_artifact_ref)
        validate_indicator_declaration(
            wave_id=spec.wave_id,
            indicator_artifact_ref=indicator_path,
            indicator_collection_command=spec.indicator_collection_command,
        )
        if indicator_path not in allowset:
            raise CandidateAuthorityError(
                f"indicator artifact is outside candidate allowlist: {indicator_path}"
            )

    pre_inventory = collect_literal_base_inventory(repo_root, comparison_commit)
    _reject_outside_allowlist(pre_inventory, allowset)
    pre_staged_inventory = collect_staged_literal_base_inventory(repo_root, comparison_commit)
    _reject_outside_allowlist(pre_staged_inventory, allowset)

    stage_targets = sorted(_inventory_paths(pre_inventory) & allowset)
    _stage_paths(repo_root, sorted(set(stage_targets)))

    if indicator_path:
        _collect_indicator(
            repo_root,
            wave_id=spec.wave_id,
            indicator_artifact_ref=indicator_path,
            indicator_collection_command=spec.indicator_collection_command,
        )
        _stage_paths(repo_root, [indicator_path])

    post_inventory = collect_literal_base_inventory(repo_root, comparison_commit)
    _reject_outside_allowlist(post_inventory, allowset)
    post_staged_inventory = collect_staged_literal_base_inventory(repo_root, comparison_commit)
    _reject_outside_allowlist(post_staged_inventory, allowset)
    residue = _unstaged_allowed_residue(repo_root, allowlist)
    if residue:
        raise CandidateAuthorityError(
            "unstaged allowed-path residue remains after authority staging: "
            + ", ".join(residue)
        )
    untracked = _ls_untracked(repo_root)
    if untracked:
        raise CandidateAuthorityError(
            "non-ignored untracked residue remains after authority staging: "
            + ", ".join(untracked)
        )

    indicator_hash = (
        _read_file_hash(repo_root, spec.indicator_artifact_ref)
        if spec.indicator_artifact_ref
        else ""
    )
    l4_contract = (
        _enforce_staged_l4_contract(repo_root, wave_id=spec.wave_id, wave_class=spec.wave_class)
        if spec.require_l4_staged
        else {"status": "skipped", "reason": "spec_disabled"}
    )
    receipt = _receipt_payload(
        repo_root,
        spec,
        comparison_commit=comparison_commit,
        inventory=post_inventory,
        staged_inventory=post_staged_inventory,
        indicator_hash=indicator_hash,
        l4_contract=l4_contract,
    )
    receipt_path = receipt_path_for(
        repo_root,
        bus_dir=bus_dir,
        wave_id=spec.wave_id,
        phase=spec.phase,
        review_round=spec.review_round,
    )
    _ensure_bus_ignored(repo_root, bus_dir)
    receipt["receipt_path"] = str(receipt_path)
    _atomic_write_json(receipt_path, receipt)
    return receipt


def _receipt_verification_payload(repo_root: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    _normalize_l4_contract_result(receipt.get("l4_contract"))
    require_l4_staged = _receipt_require_l4_staged(receipt)
    spec = CandidateAuthoritySpec.from_mapping(
        {
            "wave_id": receipt.get("wave_id", ""),
            "comparison_commit": receipt.get("comparison_commit", ""),
            "candidate_allowlist": receipt.get("candidate_allowlist", []),
            "plan_path": receipt.get("plan_path", ""),
            "plan_hash": receipt.get("plan_hash", ""),
            "phase": receipt.get("phase", ""),
            "review_round": receipt.get("review_round", ""),
            "indicator_artifact_ref": receipt.get("indicator_artifact_ref", ""),
            "indicator_collection_command": "",
            "wave_class": receipt.get("wave_class", "L4_ENABLER"),
            "require_l4_staged": require_l4_staged,
        }
    )
    comparison_commit = validate_comparison_commit(repo_root, spec.comparison_commit)
    inventory = collect_literal_base_inventory(repo_root, comparison_commit)
    allowlist = normalize_allowlist(spec.candidate_allowlist)
    _reject_outside_allowlist(inventory, set(allowlist))
    staged_inventory = collect_staged_literal_base_inventory(repo_root, comparison_commit)
    _reject_outside_allowlist(staged_inventory, set(allowlist))
    residue = _unstaged_allowed_residue(repo_root, allowlist)
    if residue:
        raise CandidateAuthorityError(
            "receipt is stale: unstaged allowed-path residue exists: "
            + ", ".join(residue)
        )
    untracked = _ls_untracked(repo_root)
    if untracked:
        raise CandidateAuthorityError(
            "receipt is stale: non-ignored untracked residue exists: "
            + ", ".join(untracked)
        )
    indicator_hash = (
        _read_file_hash(repo_root, spec.indicator_artifact_ref)
        if spec.indicator_artifact_ref
        else ""
    )
    l4_contract = (
        _enforce_staged_l4_contract(repo_root, wave_id=spec.wave_id, wave_class=spec.wave_class)
        if spec.require_l4_staged
        else {"status": "skipped", "reason": "spec_disabled"}
    )
    return _receipt_payload(
        repo_root,
        spec,
        comparison_commit=comparison_commit,
        inventory=inventory,
        staged_inventory=staged_inventory,
        indicator_hash=indicator_hash,
        l4_contract=l4_contract,
    )


def verify_current_receipt(repo_root: Path, receipt_path: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    try:
        receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise CandidateAuthorityError(f"cannot read authority receipt {receipt_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CandidateAuthorityError(f"authority receipt is malformed JSON: {exc}") from exc
    if not isinstance(receipt, dict):
        raise CandidateAuthorityError("authority receipt must be a JSON object")
    if receipt.get("version") != _RECEIPT_VERSION:
        raise CandidateAuthorityError("authority receipt has unsupported version")
    receipt_wave_id = str(receipt.get("wave_id") or "")
    if f"/{receipt_wave_id}/" not in Path(receipt_path).as_posix():
        raise CandidateAuthorityError(
            "authority receipt is tampered; wave_id does not match receipt path"
        )

    expected = _receipt_verification_payload(repo_root, receipt)
    compared_keys = (
        "repository",
        "wave_id",
        "comparison_commit",
        "candidate_allowlist_hash",
        "phase",
        "review_round",
        "plan_path",
        "plan_hash",
        "indicator_artifact_ref",
        "indicator_hash",
        "wave_class",
        "require_l4_staged",
        "literal_base_inventory_hash",
        "staged_literal_base_inventory_hash",
        "index_tree_hash",
        "staged_binary_diff_sha256",
        "l4_contract",
        "l4_contract_hash",
    )
    mismatches = [
        key for key in compared_keys
        if receipt.get(key) != expected.get(key)
    ]
    if mismatches:
        raise CandidateAuthorityError(
            "authority receipt is stale or tampered; mismatched field(s): "
            + ", ".join(mismatches)
        )
    return {"status": "current", "receipt_path": str(receipt_path), "receipt": receipt}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify candidate authority receipts.")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="stage allowlist and write a current receipt")
    prepare.add_argument("--repo-root", required=True)
    prepare.add_argument("--spec", required=True)
    prepare.add_argument("--bus-dir", default=None)
    prepare.add_argument("--phase", default=None)
    prepare.add_argument("--round", dest="review_round", default=None)

    verify = sub.add_parser("verify-current", help="verify a receipt still binds current state")
    verify.add_argument("--repo-root", required=True)
    verify.add_argument("--receipt", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            spec = load_authority_spec(Path(args.spec))
            if args.phase or args.review_round:
                spec = CandidateAuthoritySpec.from_mapping(
                    {
                        **spec.to_dict(),
                        "phase": args.phase or spec.phase,
                        "review_round": args.review_round or spec.review_round,
                    }
                )
            receipt = prepare_candidate_authority(
                Path(args.repo_root),
                spec,
                bus_dir=args.bus_dir,
            )
            print(json.dumps({"status": "prepared", "receipt": receipt}, indent=2, sort_keys=True))
            return 0
        if args.command == "verify-current":
            result = verify_current_receipt(Path(args.repo_root), Path(args.receipt))
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
    except CandidateAuthorityError as exc:
        print(f"candidate_authority: {exc}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
