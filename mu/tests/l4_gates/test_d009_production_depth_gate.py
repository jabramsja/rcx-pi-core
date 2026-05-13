"""L4 gate: D009 production depth threading (G8 — meta-circular matching).

Proves structural depth budget works identically to integer depth in production
is_mu(), match(), and substitute(). The budget is a Mu linked-list that
represents depth as structural data rather than a host integer constant.

See mu/tests/research/test_d009_h4_depth_threading.py for the research proof.
"""
from __future__ import annotations

import subprocess

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.mu_type import (
    is_mu,
    make_depth_budget,
    consume_budget,
    _STRUCTURAL_DEPTH_BUDGET,  # ANTICHEAT_OK: gate test needs direct singleton access
    _NO_BUDGET,  # ANTICHEAT_OK: gate test needs sentinel identity check
    MAX_MU_DEPTH,
)
from rcx_pi.selfhost.eval_seed import (
    match,
    _match_inner,  # ANTICHEAT_OK: gate test needs inner match for budget-only path
    substitute,
    NO_MATCH,
)


# =============================================================================
# Test Data
# =============================================================================

SHALLOW_VALUES = [
    None,
    True,
    False,
    42,
    3.14,
    "hello",
    [1, 2, 3],
    {"a": 1, "b": "two"},
    {"nested": {"deep": [1, None, True]}},
]

PATTERNS_AND_INPUTS = [
    # (pattern, input, expected_bindings_or_NO_MATCH)
    ({"var": "x"}, 42, {"x": 42}),
    ({"var": "x"}, "hello", {"x": "hello"}),
    ({"var": "x"}, [1, 2], {"x": [1, 2]}),
    (None, None, {}),
    (42, 42, {}),
    ("hello", "hello", {}),
    (42, 99, NO_MATCH),
    ([{"var": "x"}, {"var": "y"}], [1, 2], {"x": 1, "y": 2}),
    ({"a": {"var": "x"}}, {"a": 42}, {"x": 42}),
    # Non-linear pattern (same var, same value)
    ([{"var": "x"}, {"var": "x"}], [5, 5], {"x": 5}),
    # Non-linear pattern (same var, different value)
    ([{"var": "x"}, {"var": "x"}], [5, 6], NO_MATCH),
]

SUBSTITUTE_CASES = [
    # (body, bindings, expected)
    ({"var": "x"}, {"x": 42}, 42),
    ({"a": {"var": "x"}, "b": {"var": "y"}}, {"x": 1, "y": 2}, {"a": 1, "b": 2}),
    ([{"var": "x"}, "lit", {"var": "y"}], {"x": "a", "y": "b"}, ["a", "lit", "b"]),
    (None, {}, None),
    (42, {}, 42),
    ("hello", {}, "hello"),
]


class TestIsMuWithStructuralBudget:
    """is_mu returns same results with budget vs integer depth."""

    @pytest.mark.parametrize("value", SHALLOW_VALUES)
    def test_shallow_values_parity(self, value):
        """Shallow Mu values produce identical results on both paths."""
        result_int = is_mu(value)
        result_budget = is_mu(value, _budget=_STRUCTURAL_DEPTH_BUDGET)
        assert result_int == result_budget, f"Parity mismatch for {value!r}"

    def test_deep_nesting_parity(self):
        """Deep nesting beyond budget is rejected by both paths."""
        # Build a value exactly at MAX_MU_DEPTH
        deep = 42
        for _ in range(MAX_MU_DEPTH):
            deep = {"a": deep}
        # At limit — should be True on both paths
        budget_at_limit = make_depth_budget(MAX_MU_DEPTH + 1)
        assert is_mu(deep) is True
        assert is_mu(deep, _budget=budget_at_limit) is True

    def test_exceeding_depth_parity(self):
        """Value exceeding depth limit is rejected by both paths."""
        deep = 42
        for _ in range(MAX_MU_DEPTH + 1):
            deep = {"a": deep}
        # Beyond limit — should be False on both paths
        assert is_mu(deep) is False
        assert is_mu(deep, _budget=_STRUCTURAL_DEPTH_BUDGET) is False

    def test_invalid_values_parity(self):
        """Non-Mu values are rejected by both paths."""
        invalids = [lambda: None, object(), set(), (1, 2), float('nan')]
        budget = _STRUCTURAL_DEPTH_BUDGET
        for value in invalids:
            assert is_mu(value) is False
            assert is_mu(value, _budget=budget) is False


class TestMatchWithStructuralBudget:
    """match/_match_inner returns same bindings with budget vs integer depth."""

    @pytest.mark.parametrize("pattern,input_val,expected", PATTERNS_AND_INPUTS)
    def test_match_parity(self, pattern, input_val, expected):
        """Match results identical on both paths."""
        result_int = _match_inner(pattern, input_val, 0)
        result_budget = _match_inner(pattern, input_val, 0,
                                     _budget=_STRUCTURAL_DEPTH_BUDGET)
        if expected is NO_MATCH:
            assert result_int is NO_MATCH
            assert result_budget is NO_MATCH
        else:
            assert result_int == expected
            assert result_budget == expected


class TestSubstituteWithStructuralBudget:
    """substitute returns same results with budget vs integer depth."""

    @pytest.mark.parametrize("body,bindings,expected", SUBSTITUTE_CASES)
    def test_substitute_parity(self, body, bindings, expected):
        """Substitute results identical on both paths."""
        result_int = substitute(body, bindings)
        result_budget = substitute(body, bindings,
                                   _budget=_STRUCTURAL_DEPTH_BUDGET)
        assert result_int == expected
        assert result_budget == expected


class TestBudgetExhaustionParity:
    """Exhaustion behavior matches integer depth exhaustion."""

    def test_is_mu_exhaustion(self):
        """Budget exhaustion returns False, matching integer depth exhaustion."""
        tiny = make_depth_budget(1)
        nested = {"a": {"b": 42}}
        # Integer path: passes (depth 2 <= MAX_MU_DEPTH)
        assert is_mu(nested) is True
        # Budget path: fails (budget of 1 exhausted at depth 2)
        assert is_mu(nested, _budget=tiny) is False

    def test_match_exhaustion(self):
        """Budget exhaustion returns NO_MATCH, matching integer depth behavior."""
        tiny = make_depth_budget(1)
        pattern = {"a": {"var": "x"}}
        input_val = {"a": 42}
        # Integer path: succeeds
        assert _match_inner(pattern, input_val, 0) == {"x": 42}
        # Budget path: fails (budget exhausted before reaching var site)
        assert _match_inner(pattern, input_val, 0, _budget=tiny) is NO_MATCH

    def test_substitute_exhaustion(self):
        """Budget exhaustion raises TypeError, matching integer depth behavior."""
        tiny = make_depth_budget(1)
        body = {"a": {"var": "x"}}
        bindings = {"x": 42}
        # Integer path: succeeds
        assert substitute(body, bindings) == {"a": 42}
        # Budget path: raises TypeError
        with pytest.raises(TypeError, match="budget exhausted"):
            substitute(body, bindings, _budget=tiny)

    def test_null_budget_means_exhausted(self):
        """None budget (exhausted sentinel from consume_budget) is correctly handled."""
        # Budget of 0 = None from make_depth_budget(0)
        empty = make_depth_budget(0)
        assert empty is None
        # Passing exhausted budget returns False
        assert is_mu(42, _budget=empty) is False
        assert _match_inner({"var": "x"}, 42, 0, _budget=empty) is NO_MATCH
        with pytest.raises(TypeError):
            substitute({"var": "x"}, {"x": 42}, _budget=empty)


class TestBudgetIsValidMu:
    """The budget object itself is valid Mu (structural data, not host artifact)."""

    def test_small_budget_is_mu(self):
        """A budget of depth 10 passes is_mu (integer path validates it)."""
        small = make_depth_budget(10)
        assert is_mu(small) is True

    def test_budget_structure(self):
        """Budget has the expected linked-list structure."""
        budget = make_depth_budget(3)
        assert isinstance(budget, dict)
        assert "head" in budget and "tail" in budget
        assert budget["head"] is None
        assert isinstance(budget["tail"], dict)
        assert budget["tail"]["tail"]["tail"] is None  # 3 nodes, tail of last is None


class TestProductionCallersBackwardCompat:
    """Existing callers without budget still work (default _budget=_NO_BUDGET)."""

    def test_is_mu_default(self):
        """is_mu with no budget argument works as before."""
        assert is_mu(42) is True
        assert is_mu({"a": [1, 2]}) is True
        assert is_mu(lambda: None) is False

    def test_match_default(self):
        """match with no budget argument works as before."""
        result = match({"var": "x"}, 42)
        assert result == {"x": 42}

    def test_substitute_default(self):
        """substitute with no budget argument works as before."""
        result = substitute({"var": "x"}, {"x": "hello"})
        assert result == "hello"


class TestBudgetSingletonIntegrity:
    """Shared _STRUCTURAL_DEPTH_BUDGET not mutated after production calls."""

    def test_singleton_structure_preserved(self):
        """Budget singleton has expected structure after multiple calls."""
        # Use the budget in multiple calls
        is_mu({"a": [1, 2, 3]}, _budget=_STRUCTURAL_DEPTH_BUDGET)
        _match_inner({"var": "x"}, 42, 0, _budget=_STRUCTURAL_DEPTH_BUDGET)
        substitute({"var": "x"}, {"x": "hello"}, _budget=_STRUCTURAL_DEPTH_BUDGET)

        # Verify structure is intact
        budget = _STRUCTURAL_DEPTH_BUDGET
        assert isinstance(budget, dict)
        assert budget["head"] is None
        # Walk a few levels to verify chain is intact
        level = budget
        for _ in range(10):
            assert isinstance(level, dict)
            assert "head" in level and "tail" in level
            assert level["head"] is None
            level = level["tail"]

    def test_singleton_id_stability(self):
        """Budget node ids remain stable across calls."""
        id_before = id(_STRUCTURAL_DEPTH_BUDGET)
        id_tail_before = id(_STRUCTURAL_DEPTH_BUDGET["tail"])

        # Use the budget
        is_mu([1, 2, 3], _budget=_STRUCTURAL_DEPTH_BUDGET)

        id_after = id(_STRUCTURAL_DEPTH_BUDGET)
        id_tail_after = id(_STRUCTURAL_DEPTH_BUDGET["tail"])

        assert id_before == id_after
        assert id_tail_before == id_tail_after


class TestBudgetMemoKeyUniqueness:
    """id(budget) at each depth level is unique and stable."""

    def test_unique_ids_per_level(self):
        """Each budget node has a distinct id (for memo key uniqueness)."""
        budget = _STRUCTURAL_DEPTH_BUDGET
        ids = set()
        level = budget
        count = 0
        while level is not None and count < 50:
            node_id = id(level)
            assert node_id not in ids, f"Duplicate id at depth {count}"
            ids.add(node_id)
            level = level["tail"]
            count += 1
        assert count == 50  # We checked 50 levels

    def test_stable_ids_across_calls(self):
        """The same budget node returns the same id on repeated access."""
        id1 = id(_STRUCTURAL_DEPTH_BUDGET)
        id2 = id(_STRUCTURAL_DEPTH_BUDGET)
        assert id1 == id2

        # Walk 5 levels
        level = _STRUCTURAL_DEPTH_BUDGET
        for _ in range(5):
            level = level["tail"]
        id_deep1 = id(level)

        # Walk again
        level2 = _STRUCTURAL_DEPTH_BUDGET
        for _ in range(5):
            level2 = level2["tail"]
        id_deep2 = id(level2)
        assert id_deep1 == id_deep2


class TestCrossSubstrateBudgetParity:
    """Python and JS produce identical results with structural budget."""

    def test_js_budget_parity(self):
        """JS budget threading produces same results as Python."""
        js_code = """
        'use strict';
        const { isValidMu, makeDepthBudget, consumeBudget, _STRUCTURAL_DEPTH_BUDGET } = require('./mu/host/js/core/types');
        const muContainers = require('./mu/host/js/core/container_factory');
        const { match, substitute, NO_MATCH } = require('./mu/host/js/core/bootstrap_core');
        function trustMu(value) {
          if (Array.isArray(value)) {
            return muContainers.list(value.map(item => trustMu(item)));
          }
          if (value !== null && typeof value === 'object') {
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }
          return value;
        }

        const results = {};

        // is_mu parity
        results.is_mu_shallow = isValidMu(trustMu({a: [1, 2, 3]}), 0, undefined, _STRUCTURAL_DEPTH_BUDGET);
        results.is_mu_invalid = isValidMu(undefined, 0, undefined, _STRUCTURAL_DEPTH_BUDGET);

        // match parity
        const m1 = match(trustMu({var: 'x'}), 42, 0, false, _STRUCTURAL_DEPTH_BUDGET);
        results.match_var = JSON.stringify(m1);
        const m2 = match(trustMu([{var: 'x'}, {var: 'y'}]), trustMu([1, 2]), 0, false, _STRUCTURAL_DEPTH_BUDGET);
        results.match_list = JSON.stringify(m2);
        const m3 = match(42, 99, 0, false, _STRUCTURAL_DEPTH_BUDGET);
        results.match_fail = m3 === NO_MATCH ? 'NO_MATCH' : JSON.stringify(m3);

        // substitute parity
        const s1 = substitute(trustMu({result: {var: 'x'}}), {x: 'hello'}, 0, _STRUCTURAL_DEPTH_BUDGET);
        results.subst = JSON.stringify(s1);

        // exhaustion parity
        const tiny = makeDepthBudget(1);
        results.exhaust_is_mu = isValidMu(trustMu({a: {b: 42}}), 0, undefined, tiny);
        const mexh = match(trustMu({a: {var: 'x'}}), trustMu({a: 42}), 0, false, tiny);
        results.exhaust_match = mexh === NO_MATCH ? 'NO_MATCH' : JSON.stringify(mexh);

        // budget is valid Mu
        const small = makeDepthBudget(10);
        results.budget_is_mu = isValidMu(small);

        console.log(JSON.stringify(results));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
        )
        assert result.returncode == 0, f"JS failed:\n{result.stderr}"
        import json
        js_results = json.loads(result.stdout.strip())

        # Compare with Python
        from rcx_pi.selfhost.mu_type import is_mu as py_is_mu
        assert js_results["is_mu_shallow"] == py_is_mu({"a": [1, 2, 3]}, _budget=_STRUCTURAL_DEPTH_BUDGET)
        assert js_results["is_mu_invalid"] is False

        py_match_var = _match_inner({"var": "x"}, 42, 0, _budget=_STRUCTURAL_DEPTH_BUDGET)
        assert js_results["match_var"] == '{"x":42}'
        assert py_match_var == {"x": 42}

        py_match_list = _match_inner([{"var": "x"}, {"var": "y"}], [1, 2], 0, _budget=_STRUCTURAL_DEPTH_BUDGET)
        assert py_match_list == {"x": 1, "y": 2}

        assert js_results["match_fail"] == "NO_MATCH"

        py_subst = substitute({"result": {"var": "x"}}, {"x": "hello"}, _budget=_STRUCTURAL_DEPTH_BUDGET)
        assert py_subst == {"result": "hello"}

        # Exhaustion parity
        tiny_py = make_depth_budget(1)
        assert js_results["exhaust_is_mu"] is False
        assert py_is_mu({"a": {"b": 42}}, _budget=tiny_py) is False

        assert js_results["exhaust_match"] == "NO_MATCH"
        assert _match_inner({"a": {"var": "x"}}, {"a": 42}, 0, _budget=tiny_py) is NO_MATCH

        assert js_results["budget_is_mu"] is True


class TestJSMuHostObjectBoundaryGate:
    """JS Mu boundary rejects host artifacts in both validation paths."""

    def test_js_host_artifacts_reject_before_budget_or_hash_semantics(self):
        js_code = """
        'use strict';
        const t = require('./mu/host/js/core/types');
        const { containers } = t;
        const muContainers = require('./mu/host/js/core/container_factory');
        const { match } = require('./mu/host/js/core/bootstrap_core');
        const { normalizeProjection } = require('./mu/host/js/core/normalize');
        const { deriveEngineExitReason } = require('./mu/host/js/core/terminal_classification');
        function trustMu(value) {
          if (Array.isArray(value)) {
            return muContainers.list(value.map(item => trustMu(item)));
          }
          if (value !== null && typeof value === 'object') {
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }
          return value;
        }

        class EmptyClass {}
        class KeyedClass { constructor() { this.a = 1; } }
        class ArraySubclass extends Array {}

        const customProto = Object.create({ inherited: true });
        customProto.a = 1;

        const hiddenToJSON = { a: 2 };
        Object.defineProperty(hiddenToJSON, 'toJSON', {
          enumerable: false,
          value() { return { a: 1 }; },
        });

        const arraySubclass = new ArraySubclass(1);
        const keyedArraySubclass = new ArraySubclass(1);
        keyedArraySubclass.extra = 2;
        const keyedArray = [1];
        keyedArray.extra = 2;
        const proxyThrowRecord = new Proxy({}, {
          getPrototypeOf() { throw new Error('host trap'); },
        });
        const proxyThrowArray = new Proxy([1], {
          getPrototypeOf() { throw new Error('host trap'); },
        });
        const proxyTrapRecord = new Proxy({}, {
          getPrototypeOf() { throw new Error('host trap'); },
          ownKeys() { return ['a']; },
          getOwnPropertyDescriptor(_target, key) {
            if (key === 'a') return { value: 1, enumerable: true, configurable: true };
          },
          get(_target, key) { return key === 'a' ? 1 : undefined; },
        });
        const transparentProxyRecord = new Proxy({a: 1}, {});
        const transparentProxyArray = new Proxy([1], {});

        const cases = [
          ['date', new Date('2026-05-08T00:00:00Z'), trustMu({}), trustMu({})],
          ['map', new Map([['a', 1]]), trustMu({}), trustMu({})],
          ['empty_class', new EmptyClass(), trustMu({}), trustMu({})],
          ['keyed_class', new KeyedClass(), trustMu({ a: 1 }), trustMu({ a: { var: 'x' } })],
          ['custom_proto', customProto, trustMu({ a: 1 }), trustMu({ a: { var: 'x' } })],
          ['hidden_to_json', hiddenToJSON, trustMu({ a: 2 }), trustMu({ a: { var: 'x' } })],
          ['array_subclass', arraySubclass, trustMu([1]), trustMu([{ var: 'x' }])],
          ['keyed_array_subclass', keyedArraySubclass, trustMu([1]), trustMu([{ var: 'x' }])],
          ['keyed_array', keyedArray, trustMu([1]), trustMu([{ var: 'x' }])],
          ['bigint', 1n, trustMu({}), trustMu({})],
          ['proxy_throw_record', proxyThrowRecord, trustMu({ a: 1 }), trustMu({ a: { var: 'x' } })],
          ['proxy_throw_array', proxyThrowArray, trustMu([1]), trustMu([{ var: 'x' }])],
          ['proxy_trap_record', proxyTrapRecord, trustMu({ a: 1 }), trustMu({ a: { var: 'x' } })],
          ['transparent_proxy_record', transparentProxyRecord, trustMu({ a: 1 }), trustMu({ a: { var: 'x' } })],
          ['transparent_proxy_array', transparentProxyArray, trustMu([1]), trustMu([{ var: 'x' }])],
        ];

        const hashFns = ['muHash', 'muHashCached', 'muHashControl', 'muHashControlCached'];
        function hashOutcome(fn, value) {
          try {
            t[fn](value, 'l4_host_object_boundary_gate');
            return { rejected: false, error_code: null };
          } catch (err) {
            return { rejected: true, error_code: err.error_code || null };
          }
        }
        function matchOutcome(pattern, input, budgeted) {
          try {
            const result = budgeted
              ? match(pattern, input, 0, false, t._STRUCTURAL_DEPTH_BUDGET)
              : match(pattern, input);
            return { rejected: false, result };
          } catch (err) {
            return { rejected: true, error_code: err.error_code || null };
          }
        }
        function publicConstructorOutcome(kind, argument) {
          if (typeof t.containers[kind] !== 'function') return { available: false };
          try {
            const candidate = t.containers[kind](argument);
            return {
              available: true,
              defaultValid: t.isValidMu(candidate),
              hash: hashOutcome('muHash', candidate),
            };
          } catch (err) {
            return { available: true, threw: true, error_code: err.error_code || null };
          }
        }

        const accepted = trustMu({ a: [1, { b: false }], c: null });
        const acceptedPattern = trustMu({ a: { var: 'x' }, c: null });
        const normalizedProjection = normalizeProjection(trustMu({
          pattern: { op: 'ok', value: { var: 'x' } },
          body: { result: { var: 'x' } },
        }));
        const terminalResult = trustMu({
          closure_detected: false,
          exhaustion_detected: false,
          stall: false,
        });
        console.log(JSON.stringify({
          publicExports: {
            trustedSet: t._TRUSTED_MU_CONTAINERS === undefined,
            symbolProvenance: t[Symbol.for('rcx.mu.internalProvenance')] === undefined,
            markTrustedMuContainer: t.markTrustedMuContainer === undefined,
            markTrustedMuTree: t.markTrustedMuTree === undefined,
            containerAdd: t.containers.add === undefined,
            containerJson: t.containers.json === undefined,
            containerList: t.containers.list === undefined,
            containerRecord: t.containers.record === undefined,
            containerKeys: JSON.stringify(Object.keys(t.containers)) === '["has"]',
            enumerableTrustKeys: Object.keys(t).filter(k => /trust|provenance/i.test(k)).length === 0,
          },
          publicLaunder: {
            recordFromProxyEntries: publicConstructorOutcome('record', Object.entries(transparentProxyRecord)),
            listFromProxyArray: publicConstructorOutcome('list', transparentProxyArray),
          },
          producerOutputs: {
            normalizedProjectionValid: t.isValidMu(normalizedProjection),
            normalizedProjectionHash: hashOutcome('muHash', normalizedProjection),
            engineExitReason: deriveEngineExitReason(terminalResult),
          },
          rejected: cases.map(([name, value, validPeer, patternForInvalidInput]) => ({
            name,
            defaultValid: t.isValidMu(value),
            budgetValid: t.isValidMu(value, 0, undefined, t._STRUCTURAL_DEPTH_BUDGET),
            hashes: Object.fromEntries(hashFns.map(fn => [fn, hashOutcome(fn, value)])),
            matches: {
              defaultPattern: matchOutcome(value, validPeer, false),
              budgetPattern: matchOutcome(value, validPeer, true),
              defaultInput: matchOutcome(patternForInvalidInput, value, false),
              budgetInput: matchOutcome(patternForInvalidInput, value, true),
            },
          })),
          accepted: {
            defaultValid: t.isValidMu(accepted),
            budgetValid: t.isValidMu(accepted, 0, undefined, t._STRUCTURAL_DEPTH_BUDGET),
            hash: t.muHash(accepted),
            cached: t.muHashCached(accepted),
            matchDefault: matchOutcome(acceptedPattern, accepted, false),
            matchBudget: matchOutcome(acceptedPattern, accepted, true),
          },
        }));
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=30,
        )
        assert result.returncode == 0, f"JS failed:\n{result.stderr}"

        import json
        results = json.loads(result.stdout.strip())
        assert results["publicExports"] == {
            "trustedSet": True,
            "symbolProvenance": True,
            "markTrustedMuContainer": True,
            "markTrustedMuTree": True,
            "containerAdd": True,
            "containerJson": True,
            "containerList": True,
            "containerRecord": True,
            "containerKeys": True,
            "enumerableTrustKeys": True,
        }
        assert results["publicLaunder"] == {
            "recordFromProxyEntries": {"available": False},
            "listFromProxyArray": {"available": False},
        }
        assert results["producerOutputs"] == {
            "normalizedProjectionValid": True,
            "normalizedProjectionHash": {"rejected": False, "error_code": None},
            "engineExitReason": "completed",
        }
        assert {row["name"] for row in results["rejected"]} == {
            "date",
            "map",
            "empty_class",
            "keyed_class",
            "custom_proto",
            "hidden_to_json",
            "array_subclass",
            "keyed_array_subclass",
            "keyed_array",
            "bigint",
            "proxy_throw_record",
            "proxy_throw_array",
            "proxy_trap_record",
            "transparent_proxy_record",
            "transparent_proxy_array",
        }
        for row in results["rejected"]:
            assert row["defaultValid"] is False, row
            assert row["budgetValid"] is False, row
            for outcome in row["hashes"].values():
                assert outcome == {"rejected": True, "error_code": "input.invalid_type"}
            for outcome in row["matches"].values():
                assert outcome == {"rejected": True, "error_code": "input.invalid_type"}

        assert results["accepted"]["defaultValid"] is True
        assert results["accepted"]["budgetValid"] is True
        assert results["accepted"]["hash"] == results["accepted"]["cached"]
        assert results["accepted"]["matchDefault"] == {
            "rejected": False,
            "result": {"x": [1, {"b": False}]},
        }
        assert results["accepted"]["matchBudget"] == results["accepted"]["matchDefault"]
