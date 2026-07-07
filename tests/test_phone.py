import pytest

from ownsms.errors import ApiError
from ownsms.phone import normalize


def test_normalizes_uz_local():
    assert normalize("901112233") == "+998901112233"
    assert normalize("+998 90 111 22 33") == "+998901112233"


def test_rejects_invalid():
    with pytest.raises(ApiError) as e:
        normalize("12345")
    assert e.value.code == "invalid_phone"
    assert e.value.status == 422
