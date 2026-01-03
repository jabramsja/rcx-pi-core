"""
RCX-Ω: Motif codec (staging)

Purpose:
- Provide a stable-ish JSON-ish representation of π Motifs
- WITHOUT depending on private π APIs too tightly
- While still correctly preserving μ-tree arity (e.g., μ(μ()) has one child)

Design:
- Encode a Motif as {"μ": [child1, child2, ...]}
- Encode "atoms" (strings/ints/etc) as themselves
- This is for debug/inspection and later bridge tooling, not a canonical format yet.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


def _looks_like_children(seq: Any) -> bool:
    if not isinstance(seq, (list, tuple)):
        return False
    # children can be empty, but if non-empty, they should be "motif-ish" or nested structures
    # avoid treating meta dicts / random lists as children when possible
    return True


def _children_of_motif(m: Any) -> Tuple[Any, ...]:
    """
    Best-effort extraction of motif children without assuming a specific internal field name.

    Strategy order:
    1) If it's a dataclass: scan fields for a tuple/list that is NOT meta-like.
    2) Scan vars(m) for tuple/list that is NOT meta-like.
    3) Common attribute names.
    4) Fallback: no children.
    """
    # 1) dataclass fields
    if hasattr(m, "__dataclass_fields__"):
        try:
            for name in m.__dataclass_fields__.keys():  # type: ignore[attr-defined]
                if name.lower() in ("meta", "_meta"):
                    continue
                try:
                    v = getattr(m, name)
                except Exception:
                    continue
                if _looks_like_children(v):
                    return tuple(v)
        except Exception:
            pass

    # 2) vars() scan
    try:
        for name, v in vars(m).items():
            if name.lower() in ("meta", "_meta"):
                continue
            if _looks_like_children(v):
                return tuple(v)
    except Exception:
        pass

    # 3) common names (property or method)
    for name in ("children", "args", "items", "elems", "nodes", "parts"):
        if not hasattr(m, name):
            continue
        try:
            v = getattr(m, name)
        except Exception:
            continue

        # property-like
        if _looks_like_children(v):
            return tuple(v)

        # zero-arg method-like
        if callable(v):
            try:
                out = v()
                if _looks_like_children(out):
                    return tuple(out)
            except TypeError:
                # not zero-arg
                pass
            except Exception:
                pass

    return ()


def motif_to_json_obj(x: Any) -> Any:
    """
    Convert a π motif (or nested structure) to a JSON-serializable object.
    Motifs become {"μ": [...]} trees.
    """
    # already JSON-friendly primitives
    if x is None or isinstance(x, (bool, int, float, str)):
        return x

    # lists/tuples: encode as JSON list
    if isinstance(x, (list, tuple)):
        return [motif_to_json_obj(v) for v in x]

    # dicts: encode keys as strings
    if isinstance(x, dict):
        out: Dict[str, Any] = {}
        for k, v in x.items():
            out[str(k)] = motif_to_json_obj(v)
        return out

    # Motif-like: encode as μ node
    # We avoid importing Motif directly here to keep Ω from binding tightly to π internals.
    cls_name = x.__class__.__name__.lower()
    if "motif" in cls_name:
        kids = _children_of_motif(x)
        return {"μ": [motif_to_json_obj(c) for c in kids]}

    # fallback: stringify unknown objects
    return {"$repr": repr(x)}
