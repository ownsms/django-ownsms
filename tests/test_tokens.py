from ownsms.tokens import hash_token, new_api_key, new_device_token


def test_api_key_shape_and_hash():
    full, prefix, key_hash = new_api_key()
    assert full.startswith("osk_")
    assert prefix == full[:8]
    assert key_hash == hash_token(full)
    assert len(key_hash) == 64


def test_device_token_roundtrip():
    full, token_hash = new_device_token()
    assert token_hash == hash_token(full)
