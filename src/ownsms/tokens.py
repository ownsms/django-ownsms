import hashlib
import secrets


def hash_token(full: str) -> str:
    return hashlib.sha256(full.encode()).hexdigest()


def new_api_key():
    full = "osk_" + secrets.token_urlsafe(24)[:32]
    return full, full[:8], hash_token(full)


def new_device_token():
    full = secrets.token_urlsafe(32)[:43]
    return full, hash_token(full)
