"""
Centralized Fuzzer Configuration

Single source of truth for all fuzzer settings across the test suite.
All fuzzer tests should import settings from here to prevent drift.

Standardized 2026-01-29 per advisor agent recommendation.
"""

from hypothesis import settings, HealthCheck, Phase

# =============================================================================
# Core Fuzzer Settings
# =============================================================================

# Maximum depth for generated Mu structures
# Prevents pathological nesting after normalization (which can 4x depth)
MAX_DEPTH = 3

# Default number of examples for property tests
DEFAULT_MAX_EXAMPLES = 200

# Default deadline in milliseconds (5 seconds)
DEFAULT_DEADLINE = 5000

# =============================================================================
# Profile-Specific Settings
# =============================================================================

# Fast local iteration (use with HYPOTHESIS_PROFILE=dev)
FAST_MAX_EXAMPLES = 50
FAST_DEADLINE = 2000

# Full CI run
CI_MAX_EXAMPLES = 500
CI_DEADLINE = 10000

# Stress testing (long-running edge case exploration)
STRESS_MAX_EXAMPLES = 50
STRESS_DEADLINE = 60000  # 60 seconds

# Near-limit testing (boundary conditions)
NEAR_LIMIT_MAX_EXAMPLES = 20
NEAR_LIMIT_DEADLINE = 30000  # 30 seconds

# =============================================================================
# Health Check Suppressions
# =============================================================================

# Common suppressions for complex generators
COMMON_SUPPRESSIONS = [HealthCheck.too_slow]

# Suppressions for tests with high filter rates
FILTER_SUPPRESSIONS = [HealthCheck.too_slow, HealthCheck.filter_too_much]

# =============================================================================
# Pre-configured Settings Decorators
# =============================================================================

# Standard fuzzer settings
standard_settings = settings(
    max_examples=DEFAULT_MAX_EXAMPLES,
    deadline=DEFAULT_DEADLINE,
    suppress_health_check=COMMON_SUPPRESSIONS,
)

# Fast settings for local iteration
fast_settings = settings(
    max_examples=FAST_MAX_EXAMPLES,
    deadline=FAST_DEADLINE,
    suppress_health_check=COMMON_SUPPRESSIONS,
)

# CI settings for thorough testing
ci_settings = settings(
    max_examples=CI_MAX_EXAMPLES,
    deadline=CI_DEADLINE,
    suppress_health_check=COMMON_SUPPRESSIONS,
)

# Stress test settings
stress_settings = settings(
    max_examples=STRESS_MAX_EXAMPLES,
    deadline=STRESS_DEADLINE,
    suppress_health_check=COMMON_SUPPRESSIONS,
)

# Near-limit settings for boundary testing
near_limit_settings = settings(
    max_examples=NEAR_LIMIT_MAX_EXAMPLES,
    deadline=NEAR_LIMIT_DEADLINE,
    suppress_health_check=COMMON_SUPPRESSIONS,
)

# Settings for tests with high filter rates
filter_tolerant_settings = settings(
    max_examples=DEFAULT_MAX_EXAMPLES,
    deadline=DEFAULT_DEADLINE,
    suppress_health_check=FILTER_SUPPRESSIONS,
)

# =============================================================================
# Depth/Width Limits (matching rcx_pi constants)
# =============================================================================

# From rcx_pi/selfhost/mu_type.py
MAX_MU_DEPTH = 300
MAX_MU_WIDTH = 1000

# Safe test limits (leave room for normalization expansion)
SAFE_TEST_DEPTH = 50
SAFE_TEST_WIDTH = 100

# Near-limit test values
NEAR_LIMIT_DEPTH = 190  # Close to MAX_MU_DEPTH after normalization
NEAR_LIMIT_WIDTH = 900  # Close to MAX_MU_WIDTH

# =============================================================================
# Unicode Test Strings
# =============================================================================

# Hostile unicode strings for security testing
HOSTILE_UNICODE_STRINGS = [
    "",                          # Empty
    " ",                         # Whitespace
    "\t\n\r",                    # Control characters
    "🎉🚀💻",                    # Emoji
    "مرحبا",                     # Arabic (RTL)
    "שלום",                      # Hebrew (RTL)
    "\u200b\u200c\u200d",        # Zero-width characters
    "a\u0300",                   # Combining characters
    "\ufeff",                    # BOM
    "A" * 1000,                  # Long string
    "null",                      # JSON keyword
    "true",                      # JSON keyword
    "false",                     # JSON keyword
    "__proto__",                 # JS prototype pollution
    "constructor",              # JS prototype pollution
]

# Unicode homoglyphs for security testing
HOMOGLYPH_PAIRS = [
    ("a", "а"),   # Latin 'a' vs Cyrillic 'а'
    ("e", "е"),   # Latin 'e' vs Cyrillic 'е'
    ("o", "о"),   # Latin 'o' vs Cyrillic 'о'
    ("p", "р"),   # Latin 'p' vs Cyrillic 'р'
    ("c", "с"),   # Latin 'c' vs Cyrillic 'с'
    ("x", "х"),   # Latin 'x' vs Cyrillic 'х'
]
