import json

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Campaign, Device, Message, Sim
from ownsms.services.dispatch import claim_jobs
from ownsms.tokens import new_api_key


@pytest.fixture
def key_header(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    return dev, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


@pytest.mark.django_db
def test_create_campaign_renders_and_creates_messages(key_header):
    dev, h = key_header
    r = Client().post(
        "/api/v1/campaigns",
        data=json.dumps(
            {
                "text": "Salom {name}",
                "recipients": [
                    {"to": "901110001", "vars": {"name": "Ali"}},
                    {"to": "901110002", "vars": {"name": "Vali"}},
                ],
            }
        ),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 202, r.content
    cid = r.json()["id"]
    assert r.json()["total"] == 2
    msgs = list(Message.objects.order_by("id"))
    assert msgs[0].text == "Salom Ali" and msgs[1].text == "Salom Vali"
    # detail progress
    g = Client().get(f"/api/v1/campaigns/{cid}", **h)
    assert g.status_code == 200 and g.json()["progress"]["queued"] == 2


@pytest.mark.django_db
def test_missing_var_fails_fast(key_header):
    dev, h = key_header
    r = Client().post(
        "/api/v1/campaigns",
        data=json.dumps({"text": "Hi {name} {amount}", "recipients": [{"to": "901110001", "vars": {"name": "Ali"}}]}),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 422
    assert r.json()["error"]["bad_rows"][0]["missing"] == ["amount"]
    assert Campaign.objects.count() == 0 and Message.objects.count() == 0


@pytest.mark.django_db
def test_pause_blocks_claim_then_resume(key_header):
    dev, h = key_header
    cid = (
        Client()
        .post(
            "/api/v1/campaigns",
            data=json.dumps({"text": "x", "recipients": [{"to": "901110001"}]}),
            content_type="application/json",
            **h,
        )
        .json()["id"]
    )
    Client().post(f"/api/v1/campaigns/{cid}/pause", **h)
    assert claim_jobs(dev, timezone.now()) == []  # paused -> nothing claimed
    Client().post(f"/api/v1/campaigns/{cid}/resume", **h)
    assert len(claim_jobs(dev, timezone.now())) == 1  # resumed -> claimable


@pytest.mark.django_db
@pytest.mark.parametrize("bad_send_at", ["not-a-date", "2030-01-01T10:00:00"])
def test_invalid_send_at_rejected(key_header, bad_send_at):
    dev, h = key_header
    r = Client().post(
        "/api/v1/campaigns",
        data=json.dumps({"text": "x", "recipients": [{"to": "901110001"}], "send_at": bad_send_at}),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 422, r.content
    assert Campaign.objects.count() == 0 and Message.objects.count() == 0


@pytest.mark.django_db
def test_rotate_sims_round_robins_across_messages(key_header):
    dev, h = key_header
    Sim.objects.create(device=dev, subscription_id=2, number="+998907778899")
    r = Client().post(
        "/api/v1/campaigns",
        data=json.dumps(
            {
                "text": "x",
                "rotate_sims": True,
                "recipients": [{"to": "901110001"}, {"to": "901110002"}, {"to": "901110003"}],
            }
        ),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 202, r.content
    sim_ids = list(Message.objects.order_by("id").values_list("sim_id", flat=True))
    # 3 messages over 2 SIMs, round-robin: [a, b, a]
    assert len(set(sim_ids)) == 2 and sim_ids[0] == sim_ids[2] and sim_ids[0] != sim_ids[1]


@pytest.mark.django_db
def test_action_response_includes_total(key_header):
    dev, h = key_header
    cid = (
        Client()
        .post(
            "/api/v1/campaigns",
            data=json.dumps({"text": "x", "recipients": [{"to": "901110001"}, {"to": "901110002"}]}),
            content_type="application/json",
            **h,
        )
        .json()["id"]
    )
    r = Client().post(f"/api/v1/campaigns/{cid}/pause", **h)
    assert r.status_code == 200 and r.json()["total"] == 2


@pytest.mark.django_db
def test_cancel_marks_messages_canceled(key_header):
    dev, h = key_header
    cid = (
        Client()
        .post(
            "/api/v1/campaigns",
            data=json.dumps({"text": "x", "recipients": [{"to": "901110001"}]}),
            content_type="application/json",
            **h,
        )
        .json()["id"]
    )
    Client().post(f"/api/v1/campaigns/{cid}/cancel", **h)
    assert Message.objects.filter(status="canceled").count() == 1
    assert claim_jobs(dev, timezone.now()) == []
