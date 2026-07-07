from ownsms.segments import count_segments


def test_gsm7():
    assert count_segments("a" * 160) == 1
    assert count_segments("a" * 161) == 2


def test_ucs2_cyrillic():
    assert count_segments("ы" * 70) == 1
    assert count_segments("ы" * 71) == 2
