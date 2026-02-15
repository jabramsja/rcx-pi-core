"""
Reserved-field policy grounding for Gate 3 algorithm seeds.

This test enforces the intentional "minimal reserved set" policy:
- Kernel-reserved underscore keys are blocked globally.
- Algorithm entrypoint keys are allowed to open algorithm subtrees.
- A small explicit allowlist captures algorithm-internal underscore keys that
  remain intentionally unreserved.
"""

from __future__ import annotations

import re
from pathlib import Path

from rcx_pi.selfhost.step_mu import (
    ALGORITHM_ENTRYPOINT_KEYS,
    ALGORITHM_INTERNAL_UNRESERVED_FIELDS,
    KERNEL_RESERVED_FIELDS,
)


SEED_FILES = (
    Path("mu/closures/recurrence.v1.json"),
    Path("mu/closures/exhaustion.v1.json"),
)


def _underscore_tokens(path: Path) -> set[str]:
    text = path.read_text()
    return set(re.findall(r'"(_[A-Za-z0-9_]+)"', text))


def test_gate3_seed_underscore_fields_follow_policy():
    """All underscore tokens used by Gate 3 closure seeds must be policy-accounted."""
    tokens: set[str] = set()
    for seed in SEED_FILES:
        assert seed.exists(), f"Missing seed file: {seed}"
        tokens.update(_underscore_tokens(seed))

    allowed = (
        set(KERNEL_RESERVED_FIELDS)
        | set(ALGORITHM_ENTRYPOINT_KEYS)
        | set(ALGORITHM_INTERNAL_UNRESERVED_FIELDS)
        | {"_type"}
    )

    unknown = sorted(token for token in tokens if token not in allowed)
    assert not unknown, (
        "Gate 3 underscore token policy drift. "
        f"Unknown tokens in closure seeds: {unknown}"
    )


def test_minimal_reserved_policy_is_explicitly_documented():
    """Unreserved algorithm-internal underscore fields must stay explicit."""
    assert ALGORITHM_INTERNAL_UNRESERVED_FIELDS, (
        "ALGORITHM_INTERNAL_UNRESERVED_FIELDS must be explicit for policy clarity"
    )
    assert all(field.startswith("_") for field in ALGORITHM_INTERNAL_UNRESERVED_FIELDS)
