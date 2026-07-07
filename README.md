# ownsms

[![PyPI](https://img.shields.io/pypi/v/ownsms.svg)](https://pypi.org/project/ownsms/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://pypi.org/project/ownsms/)
[![Django](https://img.shields.io/badge/django-4.2%20%7C%205.0%20%7C%205.1%20%7C%205.2-0C4B33.svg)](https://www.djangoproject.com/)
[![CI](https://github.com/ownsms/django-ownsms/actions/workflows/ci.yml/badge.svg)](https://github.com/ownsms/django-ownsms/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/ownsms/django-ownsms/blob/main/LICENSE)

Send SMS through your own phone's SIM card via a simple REST API. `ownsms` is a Django app that
pairs with an Android device; the device long-polls for outbound messages and dispatches them over
its own SIM — like Eskiz or Play Mobile, but from your number, at your tariff, with no third-party
SMS gateway.

- **Documentation:** https://ownsms.omadli.uz
- **Live API demo:** https://sms.omadli.uz/api/v1/docs
- **Android sender app:** https://github.com/ownsms/ownsms-android

## Installation

```bash
pip install ownsms
```

## Usage

Add the app to `INSTALLED_APPS` and include its URLs:

```python
# settings.py
INSTALLED_APPS = [
    ...
    "ownsms",
]

# urls.py
from django.urls import include, path

urlpatterns = [
    path("", include("ownsms.urls")),
]
```

Migrate, then send an SMS with a Bearer API key:

```console
$ python manage.py migrate
```

```http
POST /api/v1/messages
Authorization: Bearer osk_<your-api-key>
Content-Type: application/json

{"to": "+998901234567", "text": "Hello from ownsms!"}
```

The paired Android device polls the server, picks up the message, and sends it over the SIM. See
the [quickstart](QUICKSTART.md) for the full register → key → send → status flow.

## Features

- **Single send** — immediate or `queued`, with per-message `from` (SIM), `ttl`, `idempotency_key`,
  `callback_url`, and `send_at` scheduling.
- **Campaigns** — one template with `{var}` placeholders + a recipients list, fail-fast validation,
  progress, and pause / resume / cancel.
- **Delivery lifecycle** — `queued → sending → sent → delivered | failed`, `expired`, `canceled`;
  at-most-once (a job left uncertain by a crash is failed, never resent).
- **Webhooks** — HMAC-signed, retried delivery on status transitions (off by default).
- **Per-SIM pacing** — rate limits, jitter, working hours, and daily quota, synced to the device.
- **Security** — API-key scopes (`send` / `read`), revocation, IP allowlist, and an audit log.
- **Sandbox** — `is_test` API keys simulate delivery without touching a device.
- **Django admin** — every model registered for management.

Full endpoint reference: Swagger UI at `/api/v1/docs`, schema at `/api/v1/openapi.yaml`.

## Compatibility

Tested on **Python 3.11 – 3.14** and **Django 4.2 – 5.2** (Django 4.2 and 5.0 require Python ≤ 3.12).
Requires Python 3.11+.

## Development

```bash
pip install -e ".[dev]"
pytest                 # tests
ruff check src tests   # lint
ruff format src tests  # format
tox                    # full Python × Django matrix
```

## License

[MIT](LICENSE)
