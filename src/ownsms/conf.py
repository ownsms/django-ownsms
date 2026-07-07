from django.conf import settings

DEFAULTS = {
    "DEVICE_ONLINE_SECONDS": 60,
    "POLL_TIMEOUT_SECONDS": 30,
    "POLL_INTERVAL_SECONDS": 1,
    "POLL_BATCH_SIZE": 100,
    "LEASE_SECONDS": 60,
    "DEFAULT_TTL_SECONDS": 24 * 3600,
}


def get(name):
    return getattr(settings, "OWNSMS", {}).get(name, DEFAULTS[name])
