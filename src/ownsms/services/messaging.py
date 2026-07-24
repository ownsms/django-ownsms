from django.db import IntegrityError
from django.utils import timezone

from .. import conf, phone, segments
from ..errors import ApiError
from ..models import Message


def _resolve_sim(device, from_):
    if from_:
        e164 = phone.normalize(from_)
        sim = device.sims.filter(number=e164).first()
        if not sim:
            raise ApiError("invalid_from", f"{e164} is not a registered number", 422)
        return sim, e164
    sim = device.sims.filter(is_default=True).first() or device.sims.first()
    if not sim:
        raise ApiError("no_sim", "Device has no SIM", 422)
    return sim, sim.number


def create_message(
    key, *, to, text, from_=None, queued=False, ttl=None, idempotency_key="", callback_url="", send_at=None
):
    if not isinstance(text, str) or not text.strip():
        raise ApiError("invalid_text", "text is required", 422)
    device = key.device
    if idempotency_key:
        existing = Message.objects.filter(account=key.account, idempotency_key=idempotency_key).first()
        if existing:
            if existing.to != phone.normalize(to) or existing.text != text:
                raise ApiError("idempotency_conflict", "Key reused with different payload", 409)
            return existing, False
    to_e164 = phone.normalize(to)
    sim, _ = _resolve_sim(device, from_)
    ttl_v = ttl if ttl is not None else conf.get("DEFAULT_TTL_SECONDS")

    # Sandbox: a test key simulates the full lifecycle instantly; never dispatched to a device.
    if key.is_test:
        now = timezone.now()
        msg = Message.objects.create(
            account=key.account,
            device=device,
            sim=sim,
            to=to_e164,
            text=text,
            status="delivered",
            queued=queued,
            ttl=ttl_v,
            segments=segments.count_segments(text),
            idempotency_key=idempotency_key or "",
            callback_url=callback_url or "",
            is_test=True,
            sent_at=now,
            delivered_at=now,
        )
        return msg, True

    if not queued and not device.is_online(timezone.now()):
        raise ApiError("device_offline", "Device is offline; immediate send rejected", 409)
    try:
        msg = Message.objects.create(
            account=key.account,
            device=device,
            sim=sim,
            to=to_e164,
            text=text,
            status="queued",
            queued=queued,
            ttl=ttl_v,
            segments=segments.count_segments(text),
            idempotency_key=idempotency_key or "",
            callback_url=callback_url or "",
            scheduled_at=send_at,
        )
        return msg, True
    except IntegrityError:
        existing = Message.objects.filter(account=key.account, idempotency_key=idempotency_key).first()
        if existing and existing.to == to_e164 and existing.text == text:
            return existing, False
        raise ApiError("idempotency_conflict", "Key reused with different payload", 409)
