from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from .. import conf, phone, segments
from ..errors import ApiError
from ..models import Campaign, Message
from . import messaging, templating


class CampaignValidation(Exception):
    def __init__(self, bad):
        self.bad = bad


@transaction.atomic
def create_campaign(
    key,
    *,
    text,
    recipients,
    from_=None,
    send_at=None,
    queued=True,
    rotate_sims=False,
    callback_url="",
    idempotency_key="",
):
    device = key.device
    if not isinstance(text, str) or not text.strip():
        raise ApiError("invalid_text", "text is required", 422)
    if not recipients:
        raise ApiError("no_recipients", "recipients is empty", 422)
    # Idempotent retry: a re-POSTed campaign returns the original instead of double-sending.
    # ponytail: unlike single-send, we don't 409 on key-reused-with-different-payload — spec is lenient here.
    if idempotency_key:
        existing = Campaign.objects.filter(account=key.account, idempotency_key=idempotency_key).first()
        if existing:
            return existing
    sim, _ = messaging._resolve_sim(device, from_)
    bad, rendered = [], []
    for i, r in enumerate(recipients):
        to = (r or {}).get("to")
        if not to:
            bad.append({"index": i, "error": "missing_to"})
            continue
        try:
            to_e164 = phone.normalize(to)
        except ApiError:
            bad.append({"index": i, "error": "invalid_phone", "to": to})
            continue
        body, missing = templating.render(text, r.get("vars"))
        if missing:
            bad.append({"index": i, "error": "missing_vars", "missing": missing})
            continue
        rendered.append((to_e164, body))
    if bad:
        raise CampaignValidation(bad)

    ttl = conf.get("DEFAULT_TTL_SECONDS")
    # rotate_sims: round-robin each message across the device's SIMs; otherwise all share the resolved SIM.
    sims = list(device.sims.all()) if rotate_sims else None
    try:
        # Savepoint so a losing IntegrityError race rolls back cleanly and we can re-query below.
        with transaction.atomic():
            campaign = Campaign.objects.create(
                account=key.account,
                device=device,
                sim=sim,
                text=text,
                from_number=from_ or "",
                rotate_sims=rotate_sims,
                send_at=send_at,
                queued=queued,
                callback_url=callback_url or "",
                status="scheduled" if send_at else "running",
                total=len(rendered),
                idempotency_key=idempotency_key or None,  # constraint is isnull-based: never store ""
            )
            Message.objects.bulk_create(
                [
                    Message(
                        account=key.account,
                        device=device,
                        sim=sims[i % len(sims)] if sims else sim,
                        to=to,
                        text=body,
                        status="queued",
                        queued=queued,
                        ttl=ttl,
                        segments=segments.count_segments(body),
                        campaign=campaign,
                        scheduled_at=send_at,
                    )
                    for i, (to, body) in enumerate(rendered)
                ]
            )
    except IntegrityError:
        existing = Campaign.objects.filter(account=key.account, idempotency_key=idempotency_key).first()
        if existing:
            return existing
        raise
    return campaign


def progress(campaign):
    counts = {row["status"]: row["n"] for row in campaign.messages.values("status").annotate(n=Count("id"))}
    # Surface the internal "dispatched" handoff state as "sending" (matches the public message API).
    public = [
        ("queued", "queued"),
        ("sending", "dispatched"),
        ("sent", "sent"),
        ("delivered", "delivered"),
        ("failed", "failed"),
        ("expired", "expired"),
        ("canceled", "canceled"),
    ]
    return {name: counts.get(internal, 0) for name, internal in public}


def _maybe_complete(campaign):
    if campaign.status in ("running", "scheduled"):
        active = campaign.messages.filter(status__in=["queued", "dispatched", "sent"]).exists()
        if not active and campaign.total > 0:
            campaign.status = "completed"
            campaign.save(update_fields=["status"])


def control(campaign, action):
    if action == "pause":
        campaign.status = "paused"
    elif action == "resume":
        campaign.status = "scheduled" if (campaign.send_at and campaign.send_at > timezone.now()) else "running"
    elif action == "cancel":
        campaign.status = "canceled"
        campaign.messages.filter(status="queued").update(status="canceled")
    else:
        raise ApiError("bad_action", f"Unknown action {action}", 400)
    campaign.save(update_fields=["status"])
    return campaign
