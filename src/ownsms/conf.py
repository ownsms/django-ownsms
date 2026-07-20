from django.conf import settings

DEFAULTS = {
    "DEVICE_ONLINE_SECONDS": 60,
    "POLL_TIMEOUT_SECONDS": 30,
    "POLL_INTERVAL_SECONDS": 1,
    # Batch + lease must match device pacing: the device sends the handed-out jobs one by one with
    # anti-spam jitter (~2-5s each, capped by the per-SIM rate). A big batch with a short lease means
    # jobs still waiting in the paced queue get their lease reclaimed as "failed" before the device
    # can send them. Keep the batch small (a minute or two of sending) and the lease generous so a
    # handed-out job is only reclaimed when the device is genuinely dead.
    "POLL_BATCH_SIZE": 25,
    "LEASE_SECONDS": 300,
    "DEFAULT_TTL_SECONDS": 24 * 3600,
}


def get(name):
    return getattr(settings, "OWNSMS", {}).get(name, DEFAULTS[name])
