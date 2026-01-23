import json
from pathlib import Path


def _state_mu(s):
    # states entries may be strings OR objects like {"i": 0, "mu": "..."}
    if isinstance(s, str):
        return s
    if isinstance(s, dict):
        if "mu" in s and isinstance(s["mu"], str):
            return s["mu"]
    return None


def test_orbit_provenance_semantics():
    p = Path("docs/fixtures/orbit_provenance_v1.json")
    assert p.exists(), "orbit_provenance_v1.json missing"

    data = json.loads(p.read_text(encoding="utf-8"))

    states = data.get("states", [])
    provenance = data.get("provenance", [])

    assert isinstance(states, list)
    assert isinstance(provenance, list)

    if not provenance:
        assert states == [], "Empty provenance with non-empty states is invalid"
        return

    max_state = len(states) - 1

    def _get_from_to(entry: dict):
        # Back-compat: older schema used "from"/"to"
        if "from" in entry and "to" in entry:
            return entry["from"], entry["to"]
        # Current schema uses "pattern"/"template"
        if "pattern" in entry and "template" in entry:
            return entry["pattern"], entry["template"]
        return None

    for idx, entry in enumerate(provenance):
        assert isinstance(entry, dict), f"provenance[{idx}] must be an object"

        ft = _get_from_to(entry)
        assert ft is not None, (
            f"provenance[{idx}] must contain either ('from','to') or ('pattern','template'); "
            f"got keys={sorted(entry.keys())}"
        )
        frm, to = ft

        assert isinstance(frm, str) and frm, (
            f"provenance[{idx}] 'from/pattern' must be a non-empty string"
        )
        assert isinstance(to, str) and to, (
            f"provenance[{idx}] 'to/template' must be a non-empty string"
        )

        assert "i" in entry, f"provenance[{idx}] missing 'i'"
        assert isinstance(entry["i"], int), f"provenance[{idx}] 'i' must be int"
        assert 1 <= entry["i"] <= max_state, (
            f"provenance[{idx}] 'i' out of range: {entry['i']} (max={max_state})"
        )

        if "rule_i" in entry:
            assert isinstance(entry["rule_i"], int), (
                f"provenance[{idx}] 'rule_i' must be int"
            )
            assert entry["rule_i"] >= 0, f"provenance[{idx}] 'rule_i' must be >= 0"

        # Semantic check (when states are present):
        # provenance entry at i should explain transition from states[i-1] -> states[i]
        i = entry["i"]
        if 0 <= i - 1 < len(states) and 0 <= i < len(states):
            s_prev = _state_mu(states[i - 1])
            s_next = _state_mu(states[i])
            assert s_prev is not None, (
                f"states[{i - 1}] not a recognized state shape: {states[i - 1]!r}"
            )
            assert s_next is not None, (
                f"states[{i}] not a recognized state shape: {states[i]!r}"
            )

            assert s_prev == frm, (
                f"provenance[{idx}] mismatch: states[{i - 1}] mu={s_prev!r} != from/pattern={frm!r}"
            )
            assert s_next == to, (
                f"provenance[{idx}] mismatch: states[{i}] mu={s_next!r} != to/template={to!r}"
            )
