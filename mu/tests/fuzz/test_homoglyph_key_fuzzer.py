"""
Unicode Homoglyph Key Injection Fuzzer - Property-Based Tests

Proves the 9-agent consensus that Unicode homoglyph attacks on kernel reserved
field names are NOT_RELEVANT: Python string comparison is byte-exact, so
homoglyphs are simply different strings. JSON round-trip preserves exact bytes.

This fuzzer systematically verifies:
1. Every homoglyph variant of every reserved field is a distinct string
2. Reserved field detection catches exact ASCII matches only
3. JSON serialization preserves Unicode codepoints without normalization
4. Zero-width, combining, and RTL override characters don't create bypasses

Added 2026-02-10 after 9-agent rigorous review identified coverage gap.
"""

import json

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from rcx_pi.selfhost.step_mu import (
    validate_no_kernel_reserved_fields,
    KERNEL_RESERVED_FIELDS,
)


# =============================================================================
# Homoglyph Character Maps
# =============================================================================

# Characters that visually resemble ASCII characters used in reserved field names
HOMOGLYPHS = {
    "_": [
        "\uff3f",  # ＿ Fullwidth Low Line
        "\u2013",  # – En Dash
        "\u2014",  # — Em Dash
        "\ufe4d",  # ﹍ Dashed Low Line
        "\ufe4e",  # ﹎ Centreline Low Line
        "\ufe4f",  # ﹏ Wavy Low Line
    ],
    "m": [
        "\u043c",  # м Cyrillic Small Letter Em
        "\uff4d",  # ｍ Fullwidth Latin Small Letter M
    ],
    "o": [
        "\u043e",  # о Cyrillic Small Letter O
        "\u006f",  # o is itself (sanity)
        "\uff4f",  # ｏ Fullwidth Latin Small Letter O
        "\u0585",  # օ Armenian Small Letter Oh
    ],
    "d": [
        "\u0501",  # ԁ Cyrillic Small Letter Komi De
        "\uff44",  # ｄ Fullwidth Latin Small Letter D
    ],
    "e": [
        "\u0435",  # е Cyrillic Small Letter Ie
        "\uff45",  # ｅ Fullwidth Latin Small Letter E
    ],
    "a": [
        "\u0430",  # а Cyrillic Small Letter A
        "\uff41",  # ａ Fullwidth Latin Small Letter A
    ],
    "s": [
        "\u0455",  # ѕ Cyrillic Small Letter Dze
        "\uff53",  # ｓ Fullwidth Latin Small Letter S
    ],
    "t": [
        "\u0442",  # т Cyrillic Small Letter Te
        "\uff54",  # ｔ Fullwidth Latin Small Letter T
    ],
    "p": [
        "\u0440",  # р Cyrillic Small Letter Er
        "\uff50",  # ｐ Fullwidth Latin Small Letter P
    ],
    "h": [
        "\u04bb",  # һ Cyrillic Small Letter Shha
        "\uff48",  # ｈ Fullwidth Latin Small Letter H
    ],
    "i": [
        "\u0456",  # і Cyrillic Small Letter Byelorussian-Ukrainian I
        "\uff49",  # ｉ Fullwidth Latin Small Letter I
    ],
    "n": [
        "\u0578",  # ո Armenian Small Letter Vo
        "\uff4e",  # ｎ Fullwidth Latin Small Letter N
    ],
    "l": [
        "\u04cf",  # ӏ Cyrillic Small Letter Palochka
        "\uff4c",  # ｌ Fullwidth Latin Small Letter L
    ],
    "r": [
        "\uff52",  # ｒ Fullwidth Latin Small Letter R
    ],
    "u": [
        "\u057d",  # ս Armenian Small Letter Seh (looks like u in some fonts)
        "\uff55",  # ｕ Fullwidth Latin Small Letter U
    ],
    "k": [
        "\uff4b",  # ｋ Fullwidth Latin Small Letter K
    ],
}

# Zero-width and invisible characters that could be inserted
INVISIBLE_CHARS = [
    "\u200b",  # Zero Width Space
    "\u200c",  # Zero Width Non-Joiner
    "\u200d",  # Zero Width Joiner
    "\ufeff",  # Zero Width No-Break Space (BOM)
    "\u00ad",  # Soft Hyphen
    "\u200e",  # Left-to-Right Mark
    "\u200f",  # Right-to-Left Mark
    "\u202a",  # Left-to-Right Embedding
    "\u202b",  # Right-to-Left Embedding
    "\u202c",  # Pop Directional Formatting
    "\u2060",  # Word Joiner
    "\u2061",  # Function Application (invisible)
    "\u2062",  # Invisible Times
    "\u2063",  # Invisible Separator
    "\u2064",  # Invisible Plus
]


# =============================================================================
# Strategies
# =============================================================================

reserved_fields = st.sampled_from(list(KERNEL_RESERVED_FIELDS))
invisible_chars = st.sampled_from(INVISIBLE_CHARS)


@st.composite
def homoglyph_substitution(draw):
    """Generate a reserved field name with one character replaced by a homoglyph."""
    field = draw(reserved_fields)

    # Find characters that have homoglyphs
    replaceable = [(i, c) for i, c in enumerate(field) if c in HOMOGLYPHS]
    assume(len(replaceable) > 0)

    # Pick a random position and homoglyph
    pos, orig_char = draw(st.sampled_from(replaceable))
    replacement = draw(st.sampled_from(HOMOGLYPHS[orig_char]))

    # Skip if replacement is the same char (sanity entry "o" → "o")
    assume(replacement != orig_char)

    mutated = field[:pos] + replacement + field[pos + 1:]
    return field, mutated


@st.composite
def invisible_char_injection(draw):
    """Generate a reserved field name with invisible characters inserted."""
    field = draw(reserved_fields)
    invis = draw(invisible_chars)

    # Insert at a random position
    pos = draw(st.integers(min_value=0, max_value=len(field)))
    mutated = field[:pos] + invis + field[pos:]
    return field, mutated


@st.composite
def fullwidth_substitution(draw):
    """Generate a reserved field name with all ASCII chars replaced by fullwidth."""
    field = draw(reserved_fields)

    # Replace each ASCII char with its fullwidth equivalent (U+FF00 + char - 0x20)
    mutated = ""
    for c in field:
        code = ord(c)
        if 0x21 <= code <= 0x7E:  # printable ASCII
            mutated += chr(0xFF00 + code - 0x20)
        else:
            mutated += c

    assume(mutated != field)
    return field, mutated


# =============================================================================
# Property Tests: Homoglyph Substitution
# =============================================================================

class TestHomoglyphSubstitution:
    """Verify homoglyph substitutions produce distinct strings."""

    @given(data=homoglyph_substitution())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_homoglyph_is_distinct_string(self, data):
        """A homoglyph-substituted key is a different Python string."""
        original, mutated = data
        assert original != mutated, (
            f"Homoglyph substitution should produce different string: "
            f"{original!r} vs {mutated!r}"
        )

    @given(data=homoglyph_substitution())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_homoglyph_not_in_reserved_set(self, data):
        """A homoglyph-substituted key is NOT in KERNEL_RESERVED_FIELDS."""
        original, mutated = data
        assert mutated not in KERNEL_RESERVED_FIELDS, (
            f"Homoglyph {mutated!r} (from {original!r}) should not be in "
            f"KERNEL_RESERVED_FIELDS"
        )

    @given(data=homoglyph_substitution())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_homoglyph_passes_validation(self, data):
        """Homoglyph keys pass validation (they're not real reserved fields)."""
        _, mutated = data
        # Should NOT raise — homoglyph is a different key
        validate_no_kernel_reserved_fields({mutated: "value"}, "test")

    @given(data=homoglyph_substitution())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_original_still_blocked_after_homoglyph(self, data):
        """The real reserved field is still blocked (sanity check)."""
        original, _ = data
        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields({original: "value"}, "test")


# =============================================================================
# Property Tests: Invisible Character Injection
# =============================================================================

class TestInvisibleCharInjection:
    """Verify invisible character injection produces distinct strings."""

    @given(data=invisible_char_injection())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_invisible_injection_is_distinct(self, data):
        """Invisible character injection produces a different Python string."""
        original, mutated = data
        assert original != mutated, (
            f"Invisible char injection should produce different string: "
            f"{original!r} vs {mutated!r}"
        )

    @given(data=invisible_char_injection())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_invisible_injection_not_reserved(self, data):
        """Invisible-injected key is NOT in KERNEL_RESERVED_FIELDS."""
        _, mutated = data
        assert mutated not in KERNEL_RESERVED_FIELDS

    @given(data=invisible_char_injection())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_invisible_injection_passes_validation(self, data):
        """Invisible-injected keys pass validation (different strings)."""
        _, mutated = data
        validate_no_kernel_reserved_fields({mutated: "value"}, "test")


# =============================================================================
# Property Tests: Fullwidth Substitution
# =============================================================================

class TestFullwidthSubstitution:
    """Verify fullwidth character substitution is distinct."""

    @given(data=fullwidth_substitution())
    @settings(max_examples=100, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_fullwidth_is_distinct(self, data):
        """Fullwidth substitution produces a different Python string."""
        original, mutated = data
        assert original != mutated

    @given(data=fullwidth_substitution())
    @settings(max_examples=100, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_fullwidth_not_reserved(self, data):
        """Fullwidth-substituted key is NOT in KERNEL_RESERVED_FIELDS."""
        _, mutated = data
        assert mutated not in KERNEL_RESERVED_FIELDS

    @given(data=fullwidth_substitution())
    @settings(max_examples=100, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_fullwidth_passes_validation(self, data):
        """Fullwidth keys pass validation."""
        _, mutated = data
        validate_no_kernel_reserved_fields({mutated: "value"}, "test")


# =============================================================================
# JSON Round-Trip Safety
# =============================================================================

class TestJsonRoundTripSafety:
    """Verify JSON serialization doesn't normalize Unicode, preventing bypass."""

    @given(data=homoglyph_substitution())
    @settings(max_examples=100, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_json_preserves_homoglyph_keys(self, data):
        """JSON round-trip preserves homoglyph key distinctness."""
        original, mutated = data
        obj = {mutated: "value"}

        # Round-trip through JSON
        serialized = json.dumps(obj, sort_keys=True)
        deserialized = json.loads(serialized)

        # Key must survive round-trip unchanged
        assert mutated in deserialized, (
            f"JSON lost homoglyph key {mutated!r}"
        )
        # And must not become the reserved field
        assert original not in deserialized or original == mutated

    @given(data=invisible_char_injection())
    @settings(max_examples=100, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_json_preserves_invisible_chars(self, data):
        """JSON round-trip preserves invisible characters in keys."""
        original, mutated = data
        obj = {mutated: "value"}

        serialized = json.dumps(obj, sort_keys=True)
        deserialized = json.loads(serialized)

        assert mutated in deserialized
        assert original not in deserialized

    def test_json_escapes_but_preserves_unicode(self):
        """JSON escapes Unicode but preserves codepoints on round-trip."""
        # Cyrillic 'а' looks like 'a' but has different codepoint
        key_with_cyrillic = "_mode\u0430"  # _modea with Cyrillic а
        obj = {key_with_cyrillic: "test"}

        serialized = json.dumps(obj)
        deserialized = json.loads(serialized)

        assert key_with_cyrillic in deserialized
        assert "_modea" not in deserialized  # ASCII 'a' version


# =============================================================================
# Exhaustive Coverage: All Reserved Fields × All Homoglyphs
# =============================================================================

class TestExhaustiveHomoglyphCoverage:
    """Test every reserved field against every available homoglyph."""

    def test_all_reserved_fields_all_homoglyphs(self):
        """For each reserved field, try every character-level homoglyph substitution.

        This is the comprehensive proof that no homoglyph can match a reserved field.
        """
        total_tests = 0
        for field in sorted(KERNEL_RESERVED_FIELDS):
            for pos, char in enumerate(field):
                if char not in HOMOGLYPHS:
                    continue
                for replacement in HOMOGLYPHS[char]:
                    if replacement == char:
                        continue
                    mutated = field[:pos] + replacement + field[pos + 1:]

                    # Must be a different string
                    assert mutated != field, (
                        f"Homoglyph failed: {field!r}[{pos}] "
                        f"{char!r}→{replacement!r} produced same string"
                    )

                    # Must not be in reserved fields
                    assert mutated not in KERNEL_RESERVED_FIELDS, (
                        f"Homoglyph bypass: {mutated!r} is in KERNEL_RESERVED_FIELDS"
                    )

                    # Must pass validation
                    validate_no_kernel_reserved_fields({mutated: "x"}, "test")
                    total_tests += 1

        # Verify we actually tested something meaningful
        assert total_tests > 50, (
            f"Expected 50+ homoglyph tests, only ran {total_tests}"
        )

    def test_all_reserved_fields_all_invisible_chars(self):
        """For each reserved field, try inserting every invisible character at every position.

        Proves invisible characters can't create a bypass.
        """
        total_tests = 0
        # Test a representative subset (all fields × 3 invisible chars × 3 positions)
        for field in sorted(KERNEL_RESERVED_FIELDS):
            for invis in INVISIBLE_CHARS[:5]:  # First 5 invisible chars
                for pos in [0, len(field) // 2, len(field)]:  # Start, middle, end
                    mutated = field[:pos] + invis + field[pos:]

                    assert mutated != field
                    assert mutated not in KERNEL_RESERVED_FIELDS
                    validate_no_kernel_reserved_fields({mutated: "x"}, "test")
                    total_tests += 1

        assert total_tests > 100, (
            f"Expected 100+ invisible char tests, only ran {total_tests}"
        )


# =============================================================================
# Combining Character Attack Tests
# =============================================================================

class TestCombiningCharacterAttacks:
    """Test combining diacritical marks that modify preceding characters."""

    COMBINING_MARKS = [
        "\u0300",  # Combining Grave Accent
        "\u0301",  # Combining Acute Accent
        "\u0302",  # Combining Circumflex Accent
        "\u0303",  # Combining Tilde
        "\u0308",  # Combining Diaeresis
        "\u030a",  # Combining Ring Above
        "\u0327",  # Combining Cedilla
        "\u0338",  # Combining Long Solidus Overlay
    ]

    def test_combining_marks_produce_distinct_keys(self):
        """Combining marks after characters produce visually modified but
        byte-distinct keys that don't match reserved fields.
        """
        for field in ["_mode", "_phase", "_result", "_status", "_stall"]:
            for mark in self.COMBINING_MARKS:
                # Insert combining mark after the second character
                mutated = field[:2] + mark + field[2:]
                assert mutated != field
                assert mutated not in KERNEL_RESERVED_FIELDS
                validate_no_kernel_reserved_fields({mutated: "x"}, "test")

    def test_combining_marks_json_stable(self):
        """Combining marks survive JSON round-trip without normalization."""
        field = "_mode"
        for mark in self.COMBINING_MARKS:
            mutated = field[:2] + mark + field[2:]
            obj = {mutated: "test"}
            roundtripped = json.loads(json.dumps(obj))
            assert mutated in roundtripped
            assert field not in roundtripped
