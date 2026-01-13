from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib


SCHEMA_TAG = "rcx-program-descriptor.v1"
SCHEMA_DOC = "docs/program_descriptor_schema.md"


@dataclass(frozen=True)
class ProgramDescriptor:
    """
    Minimal, machine-readable descriptor for an RCX program artifact.

    IMPORTANT: Pure metadata. No execution, no interpretation, no Rust calls.
    """
    schema: str
    schema_doc: str
    kind: str
    name: str
    language: str
    source_path: str
    source_sha256: str
    entrypoint: str
    determinism: Dict[str, Any]
    version: str = "v1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_mu_program(name_or_path: str, repo_root: Optional[Path] = None) -> ProgramDescriptor:
    """
    Resolve a Mu program by:
      - direct file path, OR
      - known world name (tries common locations)

    Returns a ProgramDescriptor without running anything.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]  # rcx_pi/ -> repo root

    cand: Optional[Path] = None
    raw = name_or_path.strip()

    # Direct path?
    p = (repo_root / raw) if not Path(raw).is_absolute() else Path(raw)
    if p.exists() and p.is_file():
        cand = p

    # Try known world-name locations
    if cand is None:
        world = raw
        candidates = [
            repo_root / "mu_programs" / f"{world}.mu",
            repo_root / "rcx_pi" / "worlds" / f"{world}.mu",
            repo_root / "rcx_pi" / "worlds" / "mu_programs" / f"{world}.mu",
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                cand = c
                break

    if cand is None:
        raise FileNotFoundError(
            f"Could not resolve Mu program '{raw}'. Tried direct path and common locations like "
            f"mu_programs/{raw}.mu"
        )

    rel = cand.relative_to(repo_root)
    file_hash = _sha256_file(cand)

    return ProgramDescriptor(
        schema=SCHEMA_TAG,
        schema_doc=SCHEMA_DOC,
        kind="mu_program",
        name=raw if not cand.name.endswith(".mu") else cand.stem,
        language="mu",
        source_path=str(rel),
        source_sha256=file_hash,
        entrypoint="world_trace_cli",
        determinism={
            "claim": "deterministic_given_inputs_and_fixed_runtime",
            "inputs": ["world", "seed", "max_steps"],
            "content_hash": {"algo": "sha256", "field": "source_sha256"},
        },
    )
