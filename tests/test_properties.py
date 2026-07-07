"""Property-based tests using Hypothesis."""

from hypothesis import given, settings
from hypothesis import strategies as st

from ownsms.segments import count_segments


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=500))
def test_gsm7_segments_are_consistent(text):
    """All-ASCII-lowercase text is GSM7; segment count must match the formula."""
    n = count_segments(text)
    assert n >= 1
    assert n == (1 if len(text) <= 160 else (len(text) + 152) // 153)


@given(st.integers(min_value=1, max_value=999999999))
def test_uz_local_number_normalizes_to_e164(num):
    """9-digit UZ numbers that are valid must produce an E.164 +998 string."""
    from ownsms.errors import ApiError
    from ownsms.phone import normalize

    raw = f"9{num:08d}"[:9]  # 9 digits starting with 9
    try:
        out = normalize(raw)
        assert out.startswith("+998")
    except ApiError:
        pass  # invalid combinations are allowed to raise


@given(st.text(min_size=1, max_size=200))
@settings(max_examples=200)
def test_count_segments_always_positive(text):
    """count_segments must never return zero or negative for any non-empty text."""
    assert count_segments(text) >= 1


@given(st.text(min_size=1, max_size=160))
def test_short_text_fits_one_segment(text):
    """Any text up to 70 chars always fits in exactly 1 SMS segment."""
    if len(text) <= 70:
        assert count_segments(text) == 1
