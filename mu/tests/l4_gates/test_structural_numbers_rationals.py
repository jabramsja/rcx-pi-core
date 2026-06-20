"""L4 gate: StructuralNumbers exact rational reduction as RCX projections.

Stage 3 gate for ``mu/docs/core/StructuralNumbers.v0.md``. This test proves a
bounded exact-rational normalizer for the documented envelope shape:

    {"num": Z, "den": positive}

The normalizer is gate-only. It does not add a runtime rational seed, boundary
codec, substrate rule, registry entry, or production semantic path. It composes
the landed StructuralNumbers stack:

* signed ``Z`` and ``positive`` codec helpers from the foundation gate;
* the landed StructuralNumbers arithmetic projection tables as imported
  authority/tripwires for this stage;
* lifted ``COMPARE_PROJECTIONS``, ``SUB_PROJECTIONS``, and ``ADD_PROJECTIONS``
  for the test-local exact quotient machine;
* lifted ``GCD_PROJECTIONS`` and exact-quotient projections for rational
  reduction over the lean bounded corpus.

There is no landed quotient/divide projection builder. This file therefore
defines ``build_exact_quotient_projections()`` as a bounded structural state
machine. It returns a canonical ``N`` only when repeated subtraction consumes
the remainder exactly; a strict-less remainder becomes a visible
``_quot_non_exact`` failure state and is never accepted as a quotient. The
rational reducer composes landed GCD and the bounded exact quotient builder only
for divisions where exactness is expected by the oracle and then checked by the
engine result.

Host ``math.gcd`` and integer quotient operations appear only in oracle helpers
and corpus bounds. The engine path itself is projection-only and host-float-free.

Wave: structural-numbers-rationals-2026-06-19 (L4_ENABLER, target gate G8).
"""
from __future__ import annotations

import math

import pytest

from rcx_pi.selfhost.mu_type import is_mu, mu_hash
from rcx_pi.selfhost.step_mu import run_mu
from tests.helpers.projection_stepper import run_projections
from tests.l4_gates.test_structural_numbers_add import ADD_PROJECTIONS
from tests.l4_gates.test_structural_numbers_compare import COMPARE_PROJECTIONS, _v
from tests.l4_gates.test_structural_numbers_foundation import (
    decode,
    encode,
    encode_positive,
)
from tests.l4_gates.test_structural_numbers_gcd import GCD_PROJECTIONS
from tests.l4_gates.test_structural_numbers_subtract import SUB_PROJECTIONS


ZERO_N = {"_num": None}
ONE_POS = {"xH": None}
ONE_N = {"_num": ONE_POS}

MAX_STRUCTURAL_QUOTIENT = 6
MAX_STEPS_PER_QUOTIENT_ITERATION = 12000
QUOTIENT_MAX_STEPS = MAX_STRUCTURAL_QUOTIENT * MAX_STEPS_PER_QUOTIENT_ITERATION
RATIONAL_MAX_STEPS = (2 * QUOTIENT_MAX_STEPS) + MAX_STEPS_PER_QUOTIENT_ITERATION

_PLUS = {"plus": None}
_MINUS = {"minus": None}
_PHASE_QNUM = {"qnum": None}
_PHASE_QDEN = {"qden": None}

_QC_REM = "__quot_cmp_rem"
_QC_D = "__quot_cmp_d"
_QC_Q = "__quot_cmp_q"
_QS_D = "__quot_sub_d"
_QS_Q = "__quot_sub_q"
_QA_MODE = "__quot_add_mode"
_QA_REM = "__quot_add_rem"
_QA_D = "__quot_add_d"

_RG_SIGN = "__rat_gcd_sign"
_RG_ABS = "__rat_gcd_abs"
_RG_DEN = "__rat_gcd_den"
_RQ_PHASE = "__rat_quot_phase"
_RQ_SIGN = "__rat_quot_sign"
_RQ_DEN = "__rat_quot_den"
_RQ_G = "__rat_quot_g"
_RQ_NUM_RED = "__rat_quot_num_red"

_QADD_DONE = {"done": None}
_QADD_LOOP = {"loop": None}

BOUNDED_COMPARE_PROJECTION_INDEXES = (0, 3, 5, 8, 9, 11, 12)
BOUNDED_SUBTRACT_PROJECTION_INDEXES = (
    3, 5, 10, 12, 15, 16, 19, 20, 24, 28, 40, 43, 50, 51, 52, 53, 55
)
BOUNDED_ADD_PROJECTION_INDEXES = (0, 2, 23, 33, 34, 35, 37, 38)
BOUNDED_GCD_PROJECTION_INDEXES = (
    3, 4, 5, 6, 7, 8, 13, 18, 19, 21, 22, 26,
    28, 33, 38, 39, 43, 47, 66, 73, 74, 75, 76, 78,
)

BOUNDED_COMPARE_PROJECTIONS = [
    COMPARE_PROJECTIONS[index] for index in BOUNDED_COMPARE_PROJECTION_INDEXES
]
BOUNDED_SUBTRACT_PROJECTIONS = [
    SUB_PROJECTIONS[index] for index in BOUNDED_SUBTRACT_PROJECTION_INDEXES
]
BOUNDED_ADD_PROJECTIONS = [
    ADD_PROJECTIONS[index] for index in BOUNDED_ADD_PROJECTION_INDEXES
]
BOUNDED_GCD_PROJECTIONS = [
    GCD_PROJECTIONS[index] for index in BOUNDED_GCD_PROJECTION_INDEXES
]


def _positive_forms(prefix: str) -> list[tuple[dict, dict]]:
    """Return shallow positive forms with pattern vars unique to ``prefix``."""
    return [
        ({"xH": None}, {"xH": None}),
        ({"xO": _v(f"{prefix}_xo")}, {"xO": _v(f"{prefix}_xo")}),
        ({"xI": _v(f"{prefix}_xi")}, {"xI": _v(f"{prefix}_xi")}),
    ]


def _lift_compare_into_quotient(cmp_projs: list[dict]) -> list[dict]:
    """Lift landed COMPARE projections into the quotient compare work slot."""
    lifted: list[dict] = []
    for proj in cmp_projs:
        lifted.append({
            "pattern": {
                "_quot_cmp": {
                    "work": proj["pattern"],
                    "rem": _v(_QC_REM),
                    "d": _v(_QC_D),
                    "q": _v(_QC_Q),
                }
            },
            "body": {
                "_quot_cmp": {
                    "work": proj["body"],
                    "rem": _v(_QC_REM),
                    "d": _v(_QC_D),
                    "q": _v(_QC_Q),
                }
            },
        })
    return lifted


def _lift_subtract_into_quotient(sub_projs: list[dict]) -> list[dict]:
    """Lift landed SUBTRACT projections into the quotient subtract work slot."""
    lifted: list[dict] = []
    for proj in sub_projs:
        lifted.append({
            "pattern": {
                "_quot_sub": {
                    "work": proj["pattern"],
                    "d": _v(_QS_D),
                    "q": _v(_QS_Q),
                }
            },
            "body": {
                "_quot_sub": {
                    "work": proj["body"],
                    "d": _v(_QS_D),
                    "q": _v(_QS_Q),
                }
            },
        })
    return lifted


def _lift_add_into_quotient(
    add_projs: list[dict],
    slot: str,
    carry_vars: list[tuple[str, str]],
) -> list[dict]:
    """Lift landed ADD projections into a quotient add-by-one work slot."""
    lifted: list[dict] = []
    for proj in add_projs:
        pattern_fields = {"work": proj["pattern"]}
        body_fields = {"work": proj["body"]}
        for field_name, var_name in carry_vars:
            pattern_fields[field_name] = _v(var_name)
            body_fields[field_name] = _v(var_name)
        lifted.append({
            "pattern": {slot: pattern_fields},
            "body": {slot: body_fields},
        })
    return lifted


def build_exact_quotient_projections() -> list[dict]:
    """Build bounded exact quotient projections over ``N`` by positive ``N``.

    The public ``_quot`` entry rejects zero divisors by only accepting positive
    divisor shapes. The loop measure is the non-negative remainder: strict-greater
    steps subtract a positive divisor, then increment the quotient structurally.
    A strict-less compare produces ``_quot_non_exact`` instead of floor division.
    """
    projs: list[dict] = []

    # Public entry: d must be positive. A zero divisor has no matching rule.
    for d_pat, d_body in _positive_forms("quot_seed_d"):
        projs.append({
            "pattern": {"_quot": {"n": _v("quot_seed_n"), "d": {"_num": d_pat}}},
            "body": {
                "_quot_loop": {
                    "rem": _v("quot_seed_n"),
                    "d": {"_num": d_body},
                    "q": ZERO_N,
                }
            },
        })

    # Exact zero exit: the remainder was consumed exactly, so emit q.
    projs.append({
        "pattern": {
            "_quot_loop": {
                "rem": ZERO_N,
                "d": _v("quot_zero_d"),
                "q": _v("quot_zero_q"),
            }
        },
        "body": _v("quot_zero_q"),
    })

    # Positive remainder: compare rem to d structurally.
    for rem_pat, rem_body in _positive_forms("quot_loop_rem"):
        projs.append({
            "pattern": {
                "_quot_loop": {
                    "rem": {"_num": rem_pat},
                    "d": _v("quot_loop_d"),
                    "q": _v("quot_loop_q"),
                }
            },
            "body": {
                "_quot_cmp": {
                    "work": {
                        "_cmp": {
                            "a": {"_num": rem_body},
                            "b": _v("quot_loop_d"),
                        }
                    },
                    "rem": {"_num": rem_body},
                    "d": _v("quot_loop_d"),
                    "q": _v("quot_loop_q"),
                }
            },
        })

    # Equality consumes the final divisor by one add-by-one step and emits q + 1.
    projs.append({
        "pattern": {
            "_quot_cmp": {
                "work": {"_ord": {"eq": None}},
                "rem": _v("quot_cmp_eq_rem"),
                "d": _v("quot_cmp_eq_d"),
                "q": _v("quot_cmp_eq_q"),
            }
        },
        "body": {
            "_quot_add": {
                "work": {"_add": {"a": _v("quot_cmp_eq_q"), "b": ONE_N}},
                "mode": _QADD_DONE,
                "rem": None,
                "d": None,
            }
        },
    })

    # Strict greater consumes one divisor through landed SUBTRACT, then resumes
    # after incrementing q through landed ADD. Unsupported or malformed
    # intermediate results stall visibly instead of returning floor division.
    projs.append({
        "pattern": {
            "_quot_cmp": {
                "work": {"_ord": {"gt": None}},
                "rem": _v("quot_cmp_gt_rem"),
                "d": _v("quot_cmp_gt_d"),
                "q": _v("quot_cmp_gt_q"),
            }
        },
        "body": {
            "_quot_sub": {
                "work": {
                    "_sub": {
                        "a": _v("quot_cmp_gt_rem"),
                        "b": _v("quot_cmp_gt_d"),
                    }
                },
                "d": _v("quot_cmp_gt_d"),
                "q": _v("quot_cmp_gt_q"),
            }
        },
    })

    # Strict less is visible failure, not floor division.
    projs.append({
        "pattern": {
            "_quot_cmp": {
                "work": {"_ord": {"lt": None}},
                "rem": _v("quot_cmp_lt_rem"),
                "d": _v("quot_cmp_lt_d"),
                "q": _v("quot_cmp_lt_q"),
            }
        },
        "body": {
            "_quot_non_exact": {
                "rem": _v("quot_cmp_lt_rem"),
                "d": _v("quot_cmp_lt_d"),
                "q": _v("quot_cmp_lt_q"),
            }
        },
    })

    # A strict-greater subtract must produce a positive N. Re-seed through ADD to
    # increment q; zero or negative subtract output has no rule here.
    for index in range(3):
        diff_pat, diff_body = _positive_forms(f"quot_sub_diff_{index}")[index]
        projs.append({
            "pattern": {
                "_quot_sub": {
                    "work": {"_num": diff_pat},
                    "d": _v("quot_sub_d"),
                    "q": _v("quot_sub_q"),
                }
            },
            "body": {
                "_quot_add": {
                    "work": {"_add": {"a": _v("quot_sub_q"), "b": ONE_N}},
                    "mode": _QADD_LOOP,
                    "rem": {"_num": diff_body},
                    "d": _v("quot_sub_d"),
                }
            },
        })

    # ADD-by-one always emits a positive quotient. The mode determines whether
    # equality exits immediately or a strict-greater loop resumes.
    for index in range(3):
        q_pat, q_body = _positive_forms(f"quot_add_result_{index}")[index]
        projs.append({
            "pattern": {
                "_quot_add": {
                    "work": {"_num": q_pat},
                    "mode": _QADD_DONE,
                    "rem": _v("quot_add_done_rem"),
                    "d": _v("quot_add_done_d"),
                }
            },
            "body": {"_num": q_body},
        })
        projs.append({
            "pattern": {
                "_quot_add": {
                    "work": {"_num": q_pat},
                    "mode": _QADD_LOOP,
                    "rem": _v("quot_add_loop_rem"),
                    "d": _v("quot_add_loop_d"),
                }
            },
            "body": {
                "_quot_loop": {
                    "rem": _v("quot_add_loop_rem"),
                    "d": _v("quot_add_loop_d"),
                    "q": {"_num": q_body},
                }
            },
        })

    projs.extend(_lift_compare_into_quotient(BOUNDED_COMPARE_PROJECTIONS))
    projs.extend(_lift_subtract_into_quotient(BOUNDED_SUBTRACT_PROJECTIONS))
    projs.extend(_lift_add_into_quotient(
        BOUNDED_ADD_PROJECTIONS,
        "_quot_add",
        [("mode", _QA_MODE), ("rem", _QA_REM), ("d", _QA_D)],
    ))
    return projs


EXACT_QUOTIENT_PROJECTIONS = build_exact_quotient_projections()


def _lift_gcd_into_rational(gcd_projs: list[dict]) -> list[dict]:
    """Lift landed GCD projections into the rational GCD work slot."""
    lifted: list[dict] = []
    for proj in gcd_projs:
        lifted.append({
            "pattern": {
                "_rat_gcd": {
                    "work": proj["pattern"],
                    "sign": _v(_RG_SIGN),
                    "abs": _v(_RG_ABS),
                    "den": _v(_RG_DEN),
                }
            },
            "body": {
                "_rat_gcd": {
                    "work": proj["body"],
                    "sign": _v(_RG_SIGN),
                    "abs": _v(_RG_ABS),
                    "den": _v(_RG_DEN),
                }
            },
        })
    return lifted


def _lift_quotient_into_rational(quot_projs: list[dict]) -> list[dict]:
    """Lift exact quotient projections into the rational quotient work slot."""
    lifted: list[dict] = []
    for proj in quot_projs:
        lifted.append({
            "pattern": {
                "_rat_quot": {
                    "work": proj["pattern"],
                    "phase": _v(_RQ_PHASE),
                    "sign": _v(_RQ_SIGN),
                    "den": _v(_RQ_DEN),
                    "g": _v(_RQ_G),
                    "num_red": _v(_RQ_NUM_RED),
                }
            },
            "body": {
                "_rat_quot": {
                    "work": proj["body"],
                    "phase": _v(_RQ_PHASE),
                    "sign": _v(_RQ_SIGN),
                    "den": _v(_RQ_DEN),
                    "g": _v(_RQ_G),
                    "num_red": _v(_RQ_NUM_RED),
                }
            },
        })
    return lifted


def build_rational_projections() -> list[dict]:
    """Build rational reduction projections for ``{num: Z, den: positive}``."""
    projs: list[dict] = []

    # Canonical zero: denominator is one, but only when the input denominator is
    # already a valid positive. A zero denominator has no matching rule.
    for den_pat, _den_body in _positive_forms("rat_zero_den"):
        projs.append({
            "pattern": {"_rat": {"num": ZERO_N, "den": den_pat}},
            "body": {"num": ZERO_N, "den": ONE_POS},
        })

    # Non-zero positive numerators enter the landed GCD machine with a positive
    # denominator. The denominator is stored as its bare positive shape so the
    # final rational envelope can reuse the documented `{num: Z, den: positive}`.
    for num_pat, num_body in _positive_forms("rat_pos_num"):
        for den_pat, den_body in _positive_forms("rat_pos_den"):
            projs.append({
                "pattern": {
                    "_rat": {
                        "num": {"_num": num_pat},
                        "den": den_pat,
                    },
                },
                "body": {
                    "_rat_gcd": {
                        "work": {
                            "_gcd": {
                                "a": {"_num": num_body},
                                "b": {"_num": den_body},
                            }
                        },
                        "sign": _PLUS,
                        "abs": {"_num": num_body},
                        "den": den_body,
                    }
                },
            })

    # Non-zero negative numerators carry their sign separately, then run the
    # positive magnitude through the same structural GCD path.
    for num_pat, num_body in _positive_forms("rat_neg_num"):
        for den_pat, den_body in _positive_forms("rat_neg_den"):
            projs.append({
                "pattern": {
                    "_rat": {
                        "num": {"_num": {"neg": num_pat}},
                        "den": den_pat,
                    },
                },
                "body": {
                    "_rat_gcd": {
                        "work": {
                            "_gcd": {
                                "a": {"_num": num_body},
                                "b": {"_num": den_body},
                            }
                        },
                        "sign": _MINUS,
                        "abs": {"_num": num_body},
                        "den": den_body,
                    }
                },
            })

    # GCD of a non-zero numerator and a positive denominator must be positive.
    # Zero or malformed GCD output has no reduction rule.
    for index in range(3):
        g_pat, g_body = _positive_forms(f"rat_gcd_result_{index}")[index]
        projs.append({
            "pattern": {
                "_rat_gcd": {
                    "work": {"_num": g_pat},
                    "sign": _v("rat_gcd_sign"),
                    "abs": _v("rat_gcd_abs"),
                    "den": _v("rat_gcd_den"),
                }
            },
            "body": {
                "_rat_quot": {
                    "work": {
                        "_quot": {
                            "n": _v("rat_gcd_abs"),
                            "d": {"_num": g_body},
                        }
                    },
                    "phase": _PHASE_QNUM,
                    "sign": _v("rat_gcd_sign"),
                    "den": _v("rat_gcd_den"),
                    "g": {"_num": g_body},
                    "num_red": None,
                }
            },
        })

    # First exact quotient produced the reduced positive numerator magnitude.
    for qnum_pat, qnum_body in _positive_forms("rat_qnum_result"):
        projs.append({
            "pattern": {
                "_rat_quot": {
                    "work": {"_num": qnum_pat},
                    "phase": _PHASE_QNUM,
                    "sign": _v("rat_qnum_sign"),
                    "den": _v("rat_qnum_den"),
                    "g": _v("rat_qnum_g"),
                    "num_red": _v("rat_qnum_old"),
                }
            },
            "body": {
                "_rat_quot": {
                    "work": {
                        "_quot": {
                            "n": {"_num": _v("rat_qnum_den")},
                            "d": _v("rat_qnum_g"),
                        }
                    },
                    "phase": _PHASE_QDEN,
                    "sign": _v("rat_qnum_sign"),
                    "den": _v("rat_qnum_den"),
                    "g": _v("rat_qnum_g"),
                    "num_red": {"_num": qnum_body},
                }
            },
        })

    # Second exact quotient produced the reduced denominator. Emit the envelope,
    # requiring both numerator magnitude and denominator to be positive.
    for qden_pat, qden_body in _positive_forms("rat_qden_result"):
        for qnum_pat, qnum_body in _positive_forms("rat_qden_num"):
            projs.append({
                "pattern": {
                    "_rat_quot": {
                        "work": {"_num": qden_pat},
                        "phase": _PHASE_QDEN,
                        "sign": _PLUS,
                        "den": _v("rat_qden_den"),
                        "g": _v("rat_qden_g"),
                        "num_red": {"_num": qnum_pat},
                    }
                },
                "body": {
                    "num": {"_num": qnum_body},
                    "den": qden_body,
                },
            })
            projs.append({
                "pattern": {
                    "_rat_quot": {
                        "work": {"_num": qden_pat},
                        "phase": _PHASE_QDEN,
                        "sign": _MINUS,
                        "den": _v("rat_qden_den_neg"),
                        "g": _v("rat_qden_g_neg"),
                        "num_red": {"_num": qnum_pat},
                    }
                },
                "body": {
                    "num": {"_num": {"neg": qnum_body}},
                    "den": qden_body,
                },
            })

    projs.extend(_lift_gcd_into_rational(BOUNDED_GCD_PROJECTIONS))
    projs.extend(_lift_quotient_into_rational(EXACT_QUOTIENT_PROJECTIONS))
    return projs


RATIONAL_PROJECTIONS = build_rational_projections()


QUOTIENT_CASES: list[tuple[int, int, int]] = [
    (0, 2, 0),  # zero quotient exits at rem == 0
    (2, 1, 2),  # unit divisor, bounded multi-step loop
    (4, 2, 2),  # multi-step exact quotient
    (2, 2, 1),  # equality exit
]
NON_EXACT_QUOTIENT = (3, 2)

RATIONAL_CORPUS: list[tuple[int, int]] = [
    (0, 2),    # zero numerator -> denominator one
    (1, 2),    # already-reduced positive fraction
    (2, 2),    # reducible positive fraction -> denominator one
    (-2, 4),   # reducible negative numerator
    (2, 1),    # improper fraction with positive denominator one
]
RATIONAL_ENGINE_CORPUS: list[tuple[int, int]] = [
    (0, 2),    # zero numerator -> denominator one
    (1, 2),    # already-reduced positive fraction
    (2, 2),    # reducible positive fraction -> denominator one
    (-2, 4),   # reducible negative numerator
    (2, 1),    # improper fraction with positive denominator one
]

assert MAX_STRUCTURAL_QUOTIENT == 6
assert QUOTIENT_CASES == [(0, 2, 0), (2, 1, 2), (4, 2, 2), (2, 2, 1)]
assert NON_EXACT_QUOTIENT == (3, 2)
assert RATIONAL_CORPUS == [(0, 2), (1, 2), (2, 2), (-2, 4), (2, 1)]
assert RATIONAL_ENGINE_CORPUS == RATIONAL_CORPUS
assert set(RATIONAL_ENGINE_CORPUS) <= set(RATIONAL_CORPUS)
assert all(n >= 0 and d > 0 for n, d, _expected in QUOTIENT_CASES)
assert all(expected <= MAX_STRUCTURAL_QUOTIENT for _n, _d, expected in QUOTIENT_CASES)
assert all(n <= MAX_STRUCTURAL_QUOTIENT * d for n, d, _expected in QUOTIENT_CASES)
assert all(n == d * expected for n, d, expected in QUOTIENT_CASES)
assert NON_EXACT_QUOTIENT[0] <= MAX_STRUCTURAL_QUOTIENT * NON_EXACT_QUOTIENT[1]
assert NON_EXACT_QUOTIENT[0] > NON_EXACT_QUOTIENT[1]
assert NON_EXACT_QUOTIENT[0] != NON_EXACT_QUOTIENT[1]
assert NON_EXACT_QUOTIENT[0] % NON_EXACT_QUOTIENT[1] != 0
assert all(den > 0 for _num, den in RATIONAL_CORPUS)
assert all(abs(num) <= MAX_STRUCTURAL_QUOTIENT and den <= MAX_STRUCTURAL_QUOTIENT
           for num, den in RATIONAL_CORPUS)
assert all(num == 0 or math.gcd(abs(num), den) > 0 for num, den in RATIONAL_CORPUS)
assert all(num == 0 or abs(num) % math.gcd(abs(num), den) == 0
           for num, den in RATIONAL_CORPUS)
assert all(num == 0 or den % math.gcd(abs(num), den) == 0
           for num, den in RATIONAL_CORPUS)


def _oracle_reduced_pair(num: int, den: int) -> tuple[int, int]:
    """Oracle-only rational reduction for expected test values."""
    assert den > 0
    if num == 0:
        return 0, 1
    gcd_value = math.gcd(abs(num), den)
    assert gcd_value > 0
    assert abs(num) % gcd_value == 0
    assert den % gcd_value == 0
    return num // gcd_value, den // gcd_value


def _oracle_rational(num: int, den: int) -> dict:
    """Oracle-only canonical rational envelope."""
    reduced_num, reduced_den = _oracle_reduced_pair(num, den)
    return {"num": encode(reduced_num), "den": encode_positive(reduced_den)}


assert all(max(abs(_oracle_reduced_pair(num, den)[0]),
               _oracle_reduced_pair(num, den)[1]) <= MAX_STRUCTURAL_QUOTIENT
           for num, den in RATIONAL_CORPUS)
assert any(_oracle_reduced_pair(num, den)[1] == 1 for num, den in RATIONAL_CORPUS)
assert any(abs(num) > den for num, den in RATIONAL_CORPUS)
assert any(num < 0 for num, _den in RATIONAL_CORPUS)

def run_exact_quotient(n: int, d: int) -> tuple[dict, int, bool]:
    """Run the bounded exact quotient projection table."""
    assert n >= 0 and d > 0
    assert n <= MAX_STRUCTURAL_QUOTIENT * d
    state = {"_quot": {"n": encode(n), "d": encode(d)}}
    # SPEED_OK: quotient corpus and loop count are capped by MAX_STRUCTURAL_QUOTIENT.
    result, trace, stalled = run_mu(
        EXACT_QUOTIENT_PROJECTIONS,
        state,
        max_steps=QUOTIENT_MAX_STEPS,
    )
    return result, len(trace), stalled


def run_raw_quotient_state(state: dict) -> tuple[dict, int, bool]:
    """Run a quotient control state that may intentionally stall."""
    # SPEED_OK: control cases use tiny bounded operands and exercise stall states.
    result, trace, stalled = run_mu(
        EXACT_QUOTIENT_PROJECTIONS,
        state,
        max_steps=QUOTIENT_MAX_STEPS,
    )
    return result, len(trace), stalled


def run_rational_reduce(num: int, den: int) -> tuple[dict, int, bool]:
    """Run rational normalization through the composed projection table."""
    assert den > 0
    reduced_num, reduced_den = _oracle_reduced_pair(num, den)
    assert max(abs(reduced_num), reduced_den) <= MAX_STRUCTURAL_QUOTIENT
    state = {"_rat": {"num": encode(num), "den": encode_positive(den)}}
    # SPEED_OK: rational corpus is bounded; quotient run_mu subcases separately
    # exercise exact division, while this wrapper uses the repo's test stepper to
    # avoid meta-kernel blowup on already-landed GCD rows.
    result, steps, stalled = run_projections(
        RATIONAL_PROJECTIONS,
        state,
        max_steps=RATIONAL_MAX_STEPS,
        terminal_value=None,
    )
    return result, steps, stalled


def run_raw_rational_state(state: dict) -> tuple[dict, int, bool]:
    """Run a rational control state that may intentionally stall."""
    # SPEED_OK: raw rational control cases are tiny and intentionally exercise stalls.
    result, steps, stalled = run_projections(
        RATIONAL_PROJECTIONS,
        state,
        max_steps=RATIONAL_MAX_STEPS,
        terminal_value=None,
    )
    return result, steps, stalled


_QUOTIENT_CACHE: dict[tuple[int, int], tuple[dict, int, bool]] | None = None
_NON_EXACT_QUOTIENT_CACHE: tuple[dict, int, bool] | None = None
_QUOTIENT_ZERO_DIVISOR_CACHE: tuple[dict, int, bool] | None = None
_RATIONAL_CACHE: dict[tuple[int, int], tuple[dict, int, bool]] | None = None
_RATIONAL_ZERO_DEN_CACHE: tuple[dict, int, bool] | None = None


def _quotient_results() -> dict[tuple[int, int], tuple[dict, int, bool]]:
    global _QUOTIENT_CACHE
    if _QUOTIENT_CACHE is None:
        _QUOTIENT_CACHE = {
            (n, d): run_exact_quotient(n, d)
            for n, d, _expected in QUOTIENT_CASES
        }
    return _QUOTIENT_CACHE


def _non_exact_quotient_result() -> tuple[dict, int, bool]:
    global _NON_EXACT_QUOTIENT_CACHE
    if _NON_EXACT_QUOTIENT_CACHE is None:
        n, d = NON_EXACT_QUOTIENT
        state = {"_quot": {"n": encode(n), "d": encode(d)}}
        _NON_EXACT_QUOTIENT_CACHE = run_raw_quotient_state(state)
    return _NON_EXACT_QUOTIENT_CACHE


def _quotient_zero_divisor_result() -> tuple[dict, int, bool]:
    global _QUOTIENT_ZERO_DIVISOR_CACHE
    if _QUOTIENT_ZERO_DIVISOR_CACHE is None:
        state = {"_quot": {"n": encode(1), "d": encode(0)}}
        _QUOTIENT_ZERO_DIVISOR_CACHE = run_raw_quotient_state(state)
    return _QUOTIENT_ZERO_DIVISOR_CACHE


def _rational_results() -> dict[tuple[int, int], tuple[dict, int, bool]]:
    global _RATIONAL_CACHE
    if _RATIONAL_CACHE is None:
        _RATIONAL_CACHE = {
            (num, den): run_rational_reduce(num, den)
            for num, den in RATIONAL_ENGINE_CORPUS
        }
    return _RATIONAL_CACHE


def _rational_zero_denominator_result() -> tuple[dict, int, bool]:
    global _RATIONAL_ZERO_DEN_CACHE
    if _RATIONAL_ZERO_DEN_CACHE is None:
        state = {"_rat": {"num": encode(1), "den": None}}
        _RATIONAL_ZERO_DEN_CACHE = run_raw_rational_state(state)
    return _RATIONAL_ZERO_DEN_CACHE


def _collect_vars(node, out: list[str]) -> None:
    if isinstance(node, dict):
        if set(node) == {"var"} and isinstance(node["var"], str):
            out.append(node["var"])
            return
        for child in node.values():
            _collect_vars(child, out)


def _contains_state_key(value, state_keys: set[str]) -> bool:
    if isinstance(value, dict):
        if any(key in state_keys for key in value):
            return True
        return any(_contains_state_key(child, state_keys) for child in value.values())
    return False


def _is_positive(value) -> bool:
    if not isinstance(value, dict) or len(value) != 1:
        return False
    key, child = next(iter(value.items()))
    if key == "xH":
        return child is None
    if key in {"xO", "xI"}:
        return _is_positive(child)
    return False


def _is_canonical_n_numeral(value) -> bool:
    if not isinstance(value, dict) or set(value) != {"_num"}:
        return False
    inner = value["_num"]
    if inner is None:
        return True
    return _is_positive(inner) and value == encode(decode(value))


def _is_canonical_z_numeral(value) -> bool:
    if not isinstance(value, dict) or set(value) != {"_num"}:
        return False
    inner = value["_num"]
    if inner is None:
        return True
    if not isinstance(inner, dict) or len(inner) != 1:
        return False
    if "neg" in inner:
        return _is_positive(inner["neg"]) and value == encode(decode(value))
    return _is_positive(inner) and value == encode(decode(value))


def _is_canonical_rational(value) -> bool:
    if not isinstance(value, dict) or set(value) != {"num", "den"}:
        return False
    if not _is_canonical_z_numeral(value["num"]):
        return False
    if not _is_positive(value["den"]):
        return False
    if value["num"] == ZERO_N:
        return value["den"] == ONE_POS
    return True


def _decode_rational(value: dict) -> tuple[int, int]:
    return decode(value["num"]), decode({"_num": value["den"]})


class TestProjectionScaffolding:
    """Fast structural checks for the quotient and rational projection tables."""

    def test_projection_counts(self):
        assert len(COMPARE_PROJECTIONS) == 13
        assert len(ADD_PROJECTIONS) == 39
        assert len(SUB_PROJECTIONS) == 57
        assert len(GCD_PROJECTIONS) == 80
        assert len(BOUNDED_COMPARE_PROJECTIONS) == len(BOUNDED_COMPARE_PROJECTION_INDEXES) == 7
        assert len(BOUNDED_SUBTRACT_PROJECTIONS) == len(BOUNDED_SUBTRACT_PROJECTION_INDEXES) == 17
        assert len(BOUNDED_ADD_PROJECTIONS) == len(BOUNDED_ADD_PROJECTION_INDEXES) == 8
        assert len(BOUNDED_GCD_PROJECTIONS) == len(BOUNDED_GCD_PROJECTION_INDEXES) == 24
        assert len(EXACT_QUOTIENT_PROJECTIONS) == (
            19
            + len(BOUNDED_COMPARE_PROJECTIONS)
            + len(BOUNDED_SUBTRACT_PROJECTIONS)
            + len(BOUNDED_ADD_PROJECTIONS)
        )
        assert len(EXACT_QUOTIENT_PROJECTIONS) == 51
        assert len(RATIONAL_PROJECTIONS) == (
            45 + len(BOUNDED_GCD_PROJECTIONS) + len(EXACT_QUOTIENT_PROJECTIONS)
        )
        assert len(RATIONAL_PROJECTIONS) == 120

    def test_bounded_projection_subsets_are_landed_rows(self):
        assert BOUNDED_COMPARE_PROJECTIONS == [
            COMPARE_PROJECTIONS[index] for index in BOUNDED_COMPARE_PROJECTION_INDEXES
        ]
        assert BOUNDED_SUBTRACT_PROJECTIONS == [
            SUB_PROJECTIONS[index] for index in BOUNDED_SUBTRACT_PROJECTION_INDEXES
        ]
        assert BOUNDED_ADD_PROJECTIONS == [
            ADD_PROJECTIONS[index] for index in BOUNDED_ADD_PROJECTION_INDEXES
        ]
        assert BOUNDED_GCD_PROJECTIONS == [
            GCD_PROJECTIONS[index] for index in BOUNDED_GCD_PROJECTION_INDEXES
        ]

    def test_every_projection_has_pattern_and_body(self):
        for projection_table in (EXACT_QUOTIENT_PROJECTIONS, RATIONAL_PROJECTIONS):
            for proj in projection_table:
                assert set(proj) == {"pattern", "body"}

    def test_all_patterns_are_linear(self):
        for projection_table in (EXACT_QUOTIENT_PROJECTIONS, RATIONAL_PROJECTIONS):
            for proj in projection_table:
                names: list[str] = []
                _collect_vars(proj["pattern"], names)
                assert len(names) == len(set(names)), (
                    f"non-linear pattern (variable repeated): {proj['pattern']}"
                )

    def test_quotient_composes_landed_compare_subtract_and_add(self):
        for cmp_proj, lifted_proj in zip(
            BOUNDED_COMPARE_PROJECTIONS,
            _lift_compare_into_quotient(BOUNDED_COMPARE_PROJECTIONS),
        ):
            assert lifted_proj["pattern"]["_quot_cmp"]["work"] == cmp_proj["pattern"]
            assert lifted_proj["body"]["_quot_cmp"]["work"] == cmp_proj["body"]
            assert lifted_proj in EXACT_QUOTIENT_PROJECTIONS

        for sub_proj, lifted_proj in zip(
            BOUNDED_SUBTRACT_PROJECTIONS,
            _lift_subtract_into_quotient(BOUNDED_SUBTRACT_PROJECTIONS),
        ):
            assert lifted_proj["pattern"]["_quot_sub"]["work"] == sub_proj["pattern"]
            assert lifted_proj["body"]["_quot_sub"]["work"] == sub_proj["body"]
            assert lifted_proj in EXACT_QUOTIENT_PROJECTIONS

        lifted_add = _lift_add_into_quotient(
            BOUNDED_ADD_PROJECTIONS,
            "_quot_add",
            [("mode", _QA_MODE), ("rem", _QA_REM), ("d", _QA_D)],
        )
        for add_proj, lifted_proj in zip(BOUNDED_ADD_PROJECTIONS, lifted_add):
            assert lifted_proj["pattern"]["_quot_add"]["work"] == add_proj["pattern"]
            assert lifted_proj["body"]["_quot_add"]["work"] == add_proj["body"]
            assert lifted_proj in EXACT_QUOTIENT_PROJECTIONS

    def test_quotient_strict_greater_uses_subtract_then_add(self):
        strict_gt = [
            proj for proj in EXACT_QUOTIENT_PROJECTIONS
            if proj["pattern"].get("_quot_cmp", {}).get("work") == {"_ord": {"gt": None}}
        ]
        assert len(strict_gt) == 1
        assert strict_gt[0]["body"]["_quot_sub"]["work"]["_sub"]

        subtract_exits = [
            proj for proj in EXACT_QUOTIENT_PROJECTIONS
            if "_quot_sub" in proj["pattern"]
            and proj["pattern"]["_quot_sub"].get("work", {}).get("_num") is not None
        ]
        assert len(subtract_exits) == 3
        for proj in subtract_exits:
            assert proj["body"]["_quot_add"]["mode"] == _QADD_LOOP
            assert proj["body"]["_quot_add"]["work"]["_add"]["b"] == ONE_N

        add_done = [
            proj for proj in EXACT_QUOTIENT_PROJECTIONS
            if "_quot_add" in proj["pattern"]
            and proj["pattern"]["_quot_add"].get("mode") == _QADD_DONE
        ]
        add_loop = [
            proj for proj in EXACT_QUOTIENT_PROJECTIONS
            if "_quot_add" in proj["pattern"]
            and proj["pattern"]["_quot_add"].get("mode") == _QADD_LOOP
        ]
        assert len(add_done) == 3
        assert len(add_loop) == 3

    def test_rational_composes_landed_gcd_and_exact_quotient(self):
        for gcd_proj, lifted_proj in zip(
            BOUNDED_GCD_PROJECTIONS,
            _lift_gcd_into_rational(BOUNDED_GCD_PROJECTIONS),
        ):
            assert lifted_proj["pattern"]["_rat_gcd"]["work"] == gcd_proj["pattern"]
            assert lifted_proj["body"]["_rat_gcd"]["work"] == gcd_proj["body"]
            assert lifted_proj in RATIONAL_PROJECTIONS

        for quot_proj, lifted_proj in zip(
            EXACT_QUOTIENT_PROJECTIONS,
            _lift_quotient_into_rational(EXACT_QUOTIENT_PROJECTIONS),
        ):
            assert lifted_proj["pattern"]["_rat_quot"]["work"] == quot_proj["pattern"]
            assert lifted_proj["body"]["_rat_quot"]["work"] == quot_proj["body"]
            assert lifted_proj in RATIONAL_PROJECTIONS

    def test_rational_nonzero_entries_run_gcd_before_quotient(self):
        nonzero_entries = [
            proj for proj in RATIONAL_PROJECTIONS
            if "_rat" in proj["pattern"] and "_rat_gcd" in proj["body"]
        ]
        assert len(nonzero_entries) == 18
        for proj in nonzero_entries:
            assert proj["body"]["_rat_gcd"]["work"]["_gcd"]

        gcd_exits = [
            proj for proj in RATIONAL_PROJECTIONS
            if "_rat_gcd" in proj["pattern"]
            and proj["pattern"]["_rat_gcd"].get("work", {}).get("_num") is not None
        ]
        assert len(gcd_exits) == 3
        for proj in gcd_exits:
            assert proj["body"]["_rat_quot"]["work"]["_quot"]

    def test_strict_less_quotient_path_is_visible_failure(self):
        failures = [
            proj for proj in EXACT_QUOTIENT_PROJECTIONS
            if proj["body"].keys() == {"_quot_non_exact"}
        ]
        assert len(failures) == 1
        failure = failures[0]
        assert failure["pattern"]["_quot_cmp"]["work"] == {"_ord": {"lt": None}}

    def test_corpus_and_step_bounds_are_locked(self):
        assert QUOTIENT_MAX_STEPS == MAX_STRUCTURAL_QUOTIENT * MAX_STEPS_PER_QUOTIENT_ITERATION
        assert RATIONAL_MAX_STEPS == (2 * QUOTIENT_MAX_STEPS) + MAX_STEPS_PER_QUOTIENT_ITERATION
        for n, d, expected in QUOTIENT_CASES:
            assert n >= 0 and d > 0
            assert expected <= MAX_STRUCTURAL_QUOTIENT
            assert n <= MAX_STRUCTURAL_QUOTIENT * d
        for num, den in RATIONAL_CORPUS:
            reduced_num, reduced_den = _oracle_reduced_pair(num, den)
            assert den > 0
            assert max(abs(reduced_num), reduced_den) <= MAX_STRUCTURAL_QUOTIENT
        for num, den in RATIONAL_ENGINE_CORPUS:
            assert (num, den) in RATIONAL_CORPUS

    def test_oracle_rational_envelope_shape(self):
        assert _oracle_rational(0, 2) == {"num": ZERO_N, "den": ONE_POS}
        for num, den in RATIONAL_CORPUS:
            expected = _oracle_rational(num, den)
            assert set(expected) == {"num", "den"}
            assert _is_canonical_z_numeral(expected["num"])
            assert _is_positive(expected["den"])
            assert _is_canonical_rational(expected)


@pytest.mark.l4_expensive
@pytest.mark.slow
class TestExactQuotientEngine:
    """The bounded exact quotient machine never returns floor division."""

    def test_exact_quotient_results_are_canonical_n(self):
        results = _quotient_results()
        for n, d, expected_value in QUOTIENT_CASES:
            result, _steps, stalled = results[(n, d)]
            expected = encode(expected_value)
            assert stalled is True
            assert result == expected
            assert mu_hash(result) == mu_hash(expected)
            assert is_mu(result)
            assert _is_canonical_n_numeral(result)

    def test_exact_quotient_decode_supporting(self):
        results = _quotient_results()
        for n, d, expected_value in QUOTIENT_CASES:
            result, _steps, _stalled = results[(n, d)]
            assert decode(result) == expected_value

    def test_non_exact_quotient_stalls_as_failure_state(self):
        result, _steps, stalled = _non_exact_quotient_result()
        assert stalled is True
        assert set(result) == {"_quot_non_exact"}
        assert not _is_canonical_n_numeral(result)
        assert result != encode(1)

    def test_zero_divisor_is_rejected(self):
        result, _steps, stalled = _quotient_zero_divisor_result()
        assert stalled is True
        assert set(result) == {"_quot"}
        assert not _is_canonical_n_numeral(result)


@pytest.mark.l4_expensive
@pytest.mark.slow
class TestRationalReductionEngine:
    """The composed reducer emits canonical reduced rational envelopes."""

    def test_canonical_structural_equality(self):
        results = _rational_results()
        for num, den in RATIONAL_ENGINE_CORPUS:
            result, _steps, _stalled = results[(num, den)]
            expected = _oracle_rational(num, den)
            assert result == expected, (
                f"rational reduction diverged for {num}/{den}: got {result}, expected {expected}"
            )

    def test_content_hash_equality(self):
        results = _rational_results()
        for num, den in RATIONAL_ENGINE_CORPUS:
            result, _steps, _stalled = results[(num, den)]
            expected = _oracle_rational(num, den)
            assert mu_hash(result) == mu_hash(expected)

    def test_result_shape_denominator_positive_and_zero_canonical(self):
        results = _rational_results()
        for num, den in RATIONAL_ENGINE_CORPUS:
            result, _steps, _stalled = results[(num, den)]
            assert is_mu(result)
            assert _is_canonical_rational(result)
            reduced_num, reduced_den = _decode_rational(result)
            assert reduced_den > 0
            if reduced_num == 0:
                assert result["den"] == ONE_POS

    def test_engine_reaches_stall_fixpoint(self):
        results = _rational_results()
        forbidden = {
            "_rat",
            "_rat_gcd",
            "_rat_quot",
            "_gcd",
            "_gcd_cmp",
            "_gcd_sub",
            "_quot",
            "_quot_loop",
            "_quot_cmp",
            "_quot_sub",
            "_quot_add",
            "_quot_non_exact",
        }
        for num, den in RATIONAL_ENGINE_CORPUS:
            result, steps, stalled = results[(num, den)]
            assert stalled is True, f"run_mu did not stall for {num}/{den} (steps={steps})"
            assert not _contains_state_key(result, forbidden)

    def test_decode_to_host_supporting(self):
        results = _rational_results()
        for num, den in RATIONAL_ENGINE_CORPUS:
            result, _steps, _stalled = results[(num, den)]
            assert _decode_rational(result) == _oracle_reduced_pair(num, den)

    def test_zero_denominator_stalls_without_valid_envelope(self):
        result, _steps, stalled = _rational_zero_denominator_result()
        assert stalled is True
        assert set(result) == {"_rat"}
        assert not _is_canonical_rational(result)
