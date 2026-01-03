"""
RCX-Ω: Motif codec (staging)

Goal: provide a stable, machine-readable JSON encoding for rcx_pi Motifs,
WITHOUT relying on rcx_pi internal/private APIs.

Design constraints:
- π stays frozen; Ω wraps.
- Must never choke on meta/functions/etc.
- Best-effort structural introspection with safe fallbacks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

JSON = Union[None, bool, int, float, str, List["JSON"], Dict[str, "JSON"]]


def _is_json_scalar(x: Any) -> bool:
    return x is None or isinstance(x, (bool, int, float, str))


def _safe_meta(meta: Any) -> Dict[str, JSON]:
    """
    Attempt to export a JSON-safe subset of meta (if present).
    Drops non-JSON-safe entries.
    """
    if meta is None:
        return {}

    if not isinstance(meta, Mapping):
        return {}

    out: Dict[str, JSON] = {}
    for k, v in meta.items():
        if not isinstance(k, str):
            continue
        if _is_json_scalar(v):
            out[k] = v
        # allow shallow lists/dicts of scalars
        elif isinstance(v, list) and all(_is_json_scalar(i) for i in v):
            out[k] = list(v)
        elif isinstance(v, dict) and all(isinstance(kk, str) and _is_json_scalar(vv) for kk, vv in v.items()):
            out[k] = {str(kk): vv for kk, vv in v.items()}
        else:
            # skip callables / motifs / complex objects
            continue
    return out


def _children_of(m: Any) -> Tuple[Any, ...]:
    """
    Best-effort extraction of motif children across possible implementations.
    If no known child container is found, returns empty tuple.
    """
    # common patterns we might see
    for attr in ("args", "xs", "children", "_children", "items", "_items"):
        if hasattr(m, attr):
            try:
                val = getattr(m, attr)
                if isinstance(val, tuple):
                    return val
                if isinstance(val, list):
                    return tuple(val)
            except Exception:
                pass

    # Sometimes motifs store children in a method
    for meth in ("children", "to_list", "as_list"):
        if hasattr(m, meth) and callable(getattr(m, meth)):
            try:
                val = getattr(m, meth)()
                if isinstance(val, tuple):
                    return val
                if isinstance(val, list):
                    return tuple(val)
            except Exception:
                pass

    return ()


def motif_to_json_obj(
    m: Any,
    *,
    include_meta: bool = False,
    max_depth: int = 128,
    _depth: int = 0,
) -> JSON:
    """
    Encode a motif-ish object into a stable JSON object.

    Primary encoding:
      {"μ": [child0, child1, ...]}

    Optional meta:
      {"μ": [...], "meta": {...}}

    Always safe:
      - If structure can't be introspected, returns {"atom": "<str(m)>"}.
      - Never raises on unknown motif shapes.
    """
    if _depth >= max_depth:
        return {"cut": True, "repr": str(m)}

    # If it looks like a motif (or motif-like), try structural encoding
    kids = _children_of(m)

    if kids:
        base: Dict[str, JSON] = {"μ": [motif_to_json_obj(k, include_meta=include_meta, max_depth=max_depth, _depth=_depth + 1) for k in kids]}
        if include_meta:
            meta_val = None
            for meta_attr in ("meta", "_meta"):
                if hasattr(m, meta_attr):
                    try:
                        meta_val = getattr(m, meta_attr)
                    except Exception:
                        meta_val = None
                    break
            sm = _safe_meta(meta_val)
            if sm:
                base["meta"] = sm
        return base

    # Some motifs may be leaf nodes but still motifs: represent as empty μ()
    # We still use μ:[] as the canonical leaf structure.
    try:
        # If it has a recognizable motif-ish class name, treat as leaf motif.
        cls = type(m).__name__.lower()
        if "motif" in cls:
            base2: Dict[str, JSON] = {"μ": []}
            if include_meta:
                meta_val = None
                for meta_attr in ("meta", "_meta"):
                    if hasattr(m, meta_attr):
                        try:
                            meta_val = getattr(m, meta_attr)
                        except Exception:
                            meta_val = None
                        break
                sm = _safe_meta(meta_val)
                if sm:
                    base2["meta"] = sm
            return base2
    except Exception:
        pass

    # Hard fallback for unknown atoms
    return {"atom": str(m)}


def motif_to_json_str(
    m: Any,
    *,
    include_meta: bool = False,
    max_depth: int = 128,
) -> str:
    import json

    obj = motif_to_json_obj(m, include_meta=include_meta, max_depth=max_depth)
    return json.dumps(obj, indent=2, sort_keys=True)
