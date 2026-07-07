import phonenumbers

from .errors import ApiError


def normalize(raw: str, region: str = "UZ") -> str:
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        raise ApiError("invalid_phone", f"Cannot parse: {raw}", 422)
    if not phonenumbers.is_valid_number(num):
        raise ApiError("invalid_phone", f"Invalid number: {raw}", 422)
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
