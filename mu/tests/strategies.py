"""
Shared Hypothesis strategies for RCX fuzzer tests.

Extracted from agent findings #1017-#1021 fuzzer files to eliminate
duplication (expert finding, 9-agent review 2026-02-08).
"""
import hypothesis.strategies as st


# Base Mu primitives (no floats — safe for equality testing)
simple_mu = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.text(max_size=20),
)

# Mu primitives including floats (for broader coverage)
simple_mu_with_floats = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=20),
)

# Values suitable for non-linear pattern testing (need equality comparison)
hashable_mu = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-100, max_value=100),
    st.text(max_size=10),
)
