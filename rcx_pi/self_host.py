# rcx_pi/self_host.py
"""
RCX-π self-hosting starter skeleton.

Goal:
  - Represent rewrite rules as *motifs*.
  - Provide a tiny interpreter that walks a motif tree and applies
    those rules structurally.

This is intentionally minimal and conservative. It does NOT replace the
existing PureEvaluator. Think of it as "RCX-π learning to talk to itself".
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .core.motif import Motif, μ


# -------------------------------------------------------------------
# 1. Rule encoding
# -------------------------------------------------------------------

@dataclass(frozen=True)
class MotifRule:
    """
    Simple rule: pattern -> replacement, both motifs.

    NOTE: Matching is exact structural equality at this stage.
    No wildcards / capture variables yet.
    """
    pattern: Motif
    replacement: Motif


def rule(pattern: Motif, replacement: Motif) -> MotifRule:
    """Tiny convenience constructor."""
    return MotifRule(pattern=pattern, replacement=replacement)


# -------------------------------------------------------------------
# 2. Apply rules (top-down, recursive)
# -------------------------------------------------------------------

def _apply_rule_to_node(node: Motif, r: MotifRule) -> Optional[Motif]:
    """
    If `node` matches r.pattern exactly, return r.replacement.
    Otherwise return None.
    """
    if node.structurally_equal(r.pattern):
        return r.replacement
    return None


def _rewrite_once(node: Motif, rules: List[MotifRule]) -> Tuple[Motif, bool]:
    """
    Try to rewrite `node` or any of its children exactly once.

    Returns (new_node, changed_flag).
    """
    # Try rule at this node
    for r in rules:
        rep = _apply_rule_to_node(node, r)
        if rep is not None:
            return rep, True

    # Otherwise, recurse into children
    if not node.structure:
        return node, False

    new_children = []
    changed_any = False

    for child in node.structure:
        if isinstance(child, Motif):
            new_child, changed = _rewrite_once(child, rules)
            new_children.append(new_child)
            changed_any = changed_any or changed
        else:
            new_children.append(child)

    if changed_any:
        return μ(*new_children), True
    return node, False


def rewrite_fixpoint(root: Motif, rules: List[MotifRule], max_steps: int = 10_000) -> Motif:
    """
    Repeatedly apply rules until no more changes or max_steps is hit.

    This is a structural, self-contained rewriter that uses only:
      - Motif
      - structural_equal
      - pure re-µ construction

    It does NOT call PureEvaluator and does NOT know about your
    existing `rules_pure.py`. It's a parallel "toy" lane for
    experimenting with self-hosted encodings.
    """
    cur = root
    for _ in range(max_steps):
        cur, changed = _rewrite_once(cur, rules)
        if not changed:
            break
    return cur