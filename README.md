<div align="center">

# ownsms

**Send SMS through your own phone's SIM — over a simple REST API.**

An Android device paired to your Django backend long-polls for outbound messages and dispatches
them over its own SIM. Like Eskiz or Play Mobile, but from *your* number, at *your* tariff — no
third-party SMS gateway.

[![CI](https://github.com/ownsms/django-ownsms/actions/workflows/ci.yml/badge.svg)](https://github.com/ownsms/django-ownsms/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%20|%203.12%20|%203.13%20|%203.14-3776AB?logo=python&logoColor=white)](#compatibility)
[![Django](https://img.shields.io/badge/Django-4.2%20|%205.0%20|%205.1%20|%205.2-092E20?logo=django&logoColor=white)](#compatibility)
[![License: MIT](https://img.shields.io/badge/License-MIT-16C784)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-2952E3)](https://github.com/astral-sh/ruff)

[Live demo](https://sms.omadli.uz/api/v1/docs) · [Docs](https://ownsms.omadli.uz) · [Quickstart](QUICKSTART.md)

</div>

---

## Install

```bash
pip install ownsms
```

## Quickstart

**1. Add to `INSTALLED_APPS`:**

```python
INSTALLED_APPS = [
    ...
    "ownsms",
]
```

**2. Wire up URLs** (root `urls.py`):

```python
from django.urls import path, include

urlpatterns = [
    path("", include("ownsms.urls")),
]
```

**3. Migrate:**

```bash
python manage.py migrate
```

**4. Send an SMS** (Bearer API key):

```http
POST /api/v1/messages
Authorization: Bearer osk_<your-api-key>
Content-Type: application/json

{ "to": "+998901234567", "text": "Hello from ownsms!" }
```

The paired Android device polls the server, picks up the message, and sends it via the SIM.
See **[QUICKSTART.md](QUICKSTART.md)** for the full register → key → send → status flow.

## How it works

```
your API request  →  Django backend (queues)  →  Android app (long-poll)  →  SMS from your SIM
```

The backend only queues; a paired phone running the [sender app](https://github.com/ownsms/ownsms-android)
dispatches each message over its SIM and reports status back.

## Features

- **Single send** — immediate or `queued` (send when the device is online), per-message `from`
  (SIM), `ttl`, `idempotency_key`, `callback_url`, and `send_at` scheduling.
- **Campaigns (rassilka)** — one template with `{var}` placeholders + a recipients list, fail-fast
  validation, progress, and pause / resume / cancel.
- **Delivery lifecycle** — `queued → sending → sent → delivered | failed`, `expired`, `canceled`;
  at-most-once (a job uncertain across a crash is failed, never resent).
- **Webhooks** — HMAC-signed, retried delivery on status transitions; off by default, configurable.
- **Per-SIM pacing** — rate limits, jitter, working hours, daily quota (synced to the device).
- **Security** — API-key scopes (`send` / `read`), revoke, **IP allowlist**, **audit log**.
- **Sandbox** — `is_test` API keys simulate delivery without touching a device.
- **Device protocol** — register, long-poll, report status, heartbeat, config sync, pairing.
- **Django admin** — all models registered for management.

## Key endpoints

```
POST   /api/v1/register                  # create account+device, get device token + API key
POST   /api/v1/messages                  # send one SMS
GET    /api/v1/messages | /{id}          # list (cursor pagination + filters) / fetch status
POST   /api/v1/messages/{id}/cancel      # cancel a queued message
POST   /api/v1/campaigns                 # bulk campaign
GET    /api/v1/campaigns/{id}            # progress
GET/POST /api/v1/keys                    # list / create API keys
GET    /api/v1/device                    # device status + today_sent
GET/PUT /api/v1/webhook                  # configure webhooks
GET    /api/v1/audit                     # audit log
GET    /api/v1/docs                      # Swagger UI  ·  /api/v1/openapi.yaml (schema)
```

## Status lifecycle

```
queued  →  sending  →  sent  →  delivered
                        └────→  failed | expired | canceled
```

`sent` = **accepted by the carrier — the practical success state** (exactly like Eskiz / Twilio on
many networks). `delivered` is a bonus that only arrives if the operator returns a delivery report,
which many networks never do — so **don't block on `delivered`**.

## Compatibility

Every ✅ combination is exercised on each push by the [CI matrix](.github/workflows/ci.yml).

| Python \ Django | 4.2 LTS | 5.0 | 5.1 | 5.2 LTS |
|-----------------|:-------:|:---:|:---:|:-------:|
| **3.11**        |   ✅    | ✅  | ✅  |   ✅    |
| **3.12**        |   ✅    | ✅  | ✅  |   ✅    |
| **3.13**        |   —     |  —  | ✅  |   ✅    |
| **3.14** 🧪     |   —     |  —  | 🧪  |   🧪    |

✅ tested in CI · — Django release doesn't support that Python · 🧪 experimental (allowed to fail)

Django 4.2 and 5.0 don't support Python 3.13; Python 3.14 support is tested forward-looking.
Requires Python ≥ 3.11.

## Housekeeping

Run periodically (cron / systemd timer):

```bash
python manage.py ownsms_housekeeping   # expire TTL-passed messages, reclaim timed-out leases
python manage.py ownsms_webhooks       # deliver pending webhooks with retry
```

## Development

```bash
pip install -e ".[dev]"
pytest                 # unit + integration tests
ruff check src tests   # lint
ruff format src tests  # format
tox                    # full Python × Django matrix
```

Quality gates run in CI on every push / PR: **tests** (matrix above), **ruff** lint + format,
**mypy** (django-stubs), **bandit** + **pip-audit** security, a **migration guard**, **coverage**
(floor 80%), and a **packaging** build + clean-install smoke test. Releases publish to PyPI via
**Trusted Publishing** when a GitHub Release is cut.

## License

[MIT](LICENSE)
