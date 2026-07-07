GSM7 = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)


def _is_gsm7(text: str) -> bool:
    return all(ch in GSM7 for ch in text)


def count_segments(text: str) -> int:
    if not text:
        return 1
    if _is_gsm7(text):
        single, multi = 160, 153
    else:
        single, multi = 70, 67
    n = len(text)
    return 1 if n <= single else (n + multi - 1) // multi
