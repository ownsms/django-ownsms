GSM7 = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

# GSM-7 extension table: each of these encodes as ESC + char = 2 septets.
GSM7_EXT = set("[]{}\\~^|€\f")


def _septets(text: str):
    # Total GSM-7 septets, counting extension chars as 2. None if any char is
    # not GSM-7 encodable at all (forces UCS-2).
    total = 0
    for ch in text:
        if ch in GSM7:
            total += 1
        elif ch in GSM7_EXT:
            total += 2
        else:
            return None
    return total


def count_segments(text: str) -> int:
    if not text:
        return 1
    septets = _septets(text)
    if septets is not None:
        single, multi, n = 160, 153, septets
    else:
        single, multi, n = 70, 67, len(text)
    return 1 if n <= single else (n + multi - 1) // multi
