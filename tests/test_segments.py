from ownsms.segments import count_segments


def test_gsm7():
    assert count_segments("a" * 160) == 1
    assert count_segments("a" * 161) == 2


def test_ucs2_cyrillic():
    assert count_segments("ы" * 70) == 1
    assert count_segments("ы" * 71) == 2


def test_gsm7_extension_chars_stay_gsm7():
    # '[' is a GSM-7 extension char (2 septets), not UCS-2.
    assert count_segments("[hello]") == 1
    # 80 brackets = 160 septets = still one GSM-7 segment; 81 spills over.
    assert count_segments("[" * 80) == 1
    assert count_segments("[" * 81) == 2


def test_euro_is_gsm7():
    assert count_segments("€5") == 1


def test_extension_septets_beat_ucs2_budget():
    # 71 '{' chars = 142 GSM-7 septets = 1 segment; as UCS-2 it'd be 2.
    assert count_segments("{" * 71) == 1
