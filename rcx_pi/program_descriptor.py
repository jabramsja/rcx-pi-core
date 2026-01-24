from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA_TAG = "rcx-program-descriptor.v1"
SCHEMA_DOC = "docs/program_descriptor_schema.md"


def _find_repo_root(start: Path) -> Optional[Path]:
    cur = start.resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".git").exists():
            return p
    return None


def _module_repo_root() -> Path:
    # rcx_pi/program_descriptor.py -> rcx_pi -> repo_root guess
    here = Path(__file__).resolve()
    guess = here.parents[1]
    rr = _find_repo_root(guess)
    return rr if rr is not None else guess


def _resolve_mu_program(program: str, cwd_base: Path) -> Path:
    """
    Resolve a Mu program using stable anchors:
      1) cwd/<program> (relative) or <program> (absolute)
      2) repo_root/<program> (if user passed rcx_pi_rust/mu_programs/rcx_core.mu)
      3) repo_root/mu_programs/<name>.mu (legacy slot)
      4) repo_root/rcx_pi_rust/mu_programs/<name>.mu (current slot)
    """
    repo_root = _module_repo_root()
    p = Path(program)

    candidates: list[Path] = []

    # 1) direct path relative to cwd
    candidates.append((p if p.is_absolute() else (cwd_base / p)).resolve())

    # 2) same relative path, but anchored at repo root
    if not p.is_absolute():
        candidates.append((repo_root / p).resolve())

    # name for "<name>.mu" fallback
    name = p.stem if p.suffix else program

    # 3) legacy location
    candidates.append((repo_root / "mu_programs" / f"{name}.mu").resolve())

    # 4) current location (your layout)
    candidates.append(
        (repo_root / "rcx_pi_rust" / "mu_programs" / f"{name}.mu").resolve()
    )

    for c in candidates:
        if c.exists() and c.is_file():
            return c

    tried = "\n  - ".join(str(x) for x in candidates)
    raise FileNotFoundError(
        f"Could not resolve Mu program '{program}'. Tried:\n  - {tried}"
    )


def describe_program(program: str) -> Dict[str, Any]:
    """
    Produce a stable JSON-serializable descriptor for a Mu program.
    Metadata only (no interpretation).
    """
    mu_path = _resolve_mu_program(program, cwd_base=Path.cwd())

    return {
        "schema": SCHEMA_TAG,
        "schema_doc": SCHEMA_DOC,
        "program": program,
        "resolved_path": str(mu_path),
        "name": mu_path.stem,
        "format": "mu",
        "bytes": mu_path.stat().st_size,
    }
