"""
RCX-Ω JSON versioning helper (opt-in only).

Default behavior: producer output is unchanged.
Enable injection via:
  RCX_OMEGA_ADD_SCHEMA_FIELDS=1

Optional override:
  RCX_OMEGA_SCHEMA_VERSION=1.0.0

Fields are OPTIONAL by policy. Consumers must not require them.
"""

from __future__ import annotations

import os
from typing import Any, Dict

ENV_ENABLE = "RCX_OMEGA_ADD_SCHEMA_FIELDS"
ENV_VERSION = "RCX_OMEGA_SCHEMA_VERSION"
DEFAULT_SCHEMA_VERSION = "1.0.0"


def _enabled() -> bool:
    v = os.getenv(ENV_ENABLE, "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _schema_version() -> str:
    v = os.getenv(ENV_VERSION, "").strip()
    return v or DEFAULT_SCHEMA_VERSION


def maybe_add_schema_fields(payload: Any, *, kind: str) -> Any:
    """
    If enabled AND payload is a dict, inject optional fields:
      - kind
      - schema_version

    Never overwrites existing keys.
    """
    if not _enabled():
        return payload
    if not isinstance(payload, dict):
        return payload
    out: Dict[str, Any] = dict(payload)
    out.setdefault("kind", kind)
    out.setdefault("schema_version", _schema_version())
    return out
