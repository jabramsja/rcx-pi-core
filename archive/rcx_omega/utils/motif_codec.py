"""
RCX-Ω compatibility shim.

Historically some Ω code/tests imported:
  rcx_omega.utils.motif_codec

Canonical implementation now lives at:
  rcx_omega.core.motif_codec
"""

from __future__ import annotations

from rcx_omega.core.motif_codec import (  # noqa: F401
    JsonObj,
    json_obj_to_motif,
    motif_to_json_obj,
)
