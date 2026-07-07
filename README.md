# ownsms

[![CI](https://github.com/ownsms/django-ownsms/actions/workflows/ci.yml/badge.svg)](https://github.com/ownsms/django-ownsms/actions/workflows/ci.yml)

Send SMS through your own phone's SIM card via a simple REST API. An Android device paired to
your Django backend long-polls for outbound messages and dispatches them over its SIM — no
third-party SMS gateway required.

## Install

```
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

```
python manage.py migrate
```

**4. Send an SMS** (Bearer API key):

```
POST /api/v1/messages
Authorization: Bearer osk_<your-api-key>
Content-Type: application/json

{ "to": "+998901234567", "text": "Hello from ownsms!" }
```

The paired Android device polls the server, picks up the message, and sends it via the SIM.

## Features

- **Single send** — immediate or `queued` (send when the device is online), per-message `from`
  (SIM), `ttl`, `idempotency_key`, `callback_url`, and `send_at` scheduling.
- **Campaigns (rassilka)** — one template with `{var}` placeholders + a recipients list, fail-fast
  validation, progress, and pause / resume / cancel.
- **Delivery lifecycle** — `queued → dispatched → sent → delivered | failed`, `expired`, `canceled`;
  at-most-once (a job uncertain across a crash is failed, never resent).
- **Webhooks** — HMAC-signed, retried delivery on status transitions; off by default, configurable.
- **Per-SIM pacing config** — rate limits, jitter, working hours, daily quota (synced to the device).
- **Security** — API-key scopes (`send` / `read`), revoke, **IP allowlist**, **audit log**.
- **Sandbox** — `is_test` API keys simulate delivery without touching a device.
- **Device protocol** — register, long-poll, report status, heartbeat, config sync, pairing.
- **Django admin** — all models registered for management.

## Key endpoints

```
POST   /api/v1/register                  # create account+device, get device token + API key
POST   /api/v1/register/pair             # join an account with a pairing code
POST   /api/v1/devices/pairing-code      # (device) issue a pairing code

POST   /api/v1/messages                  # send one SMS
GET    /api/v1/messages | /{id}          # list (cursor pagination + filters) / fetch status
POST   /api/v1/messages/{id}/cancel      # cancel a queued message
POST   /api/v1/campaigns                 # bulk campaign
GET    /api/v1/campaigns/{id}            # progress
GET    /api/v1/campaigns/{id}/messages   # recipients + statuses
POST   /api/v1/campaigns/{id}/{pause|resume|cancel}

GET/POST /api/v1/keys                    # list / create API keys
POST   /api/v1/keys/{id}/revoke          # revoke a key
GET    /api/v1/devices                   # list devices
POST   /api/v1/devices/{id}/{activate|deactivate}
GET/PUT /api/v1/webhook                  # configure webhooks
GET    /api/v1/webhook/deliveries        # webhook delivery log
GET    /api/v1/device                    # device status
GET    /api/v1/audit                     # audit log
GET    /api/v1/docs                      # Swagger UI  ·  /api/v1/openapi.yaml (schema)

# device protocol (device token auth): /api/v1/device/{register,poll,jobs/{id}/status,heartbeat,config}
```

## Housekeeping (run periodically — cron / systemd timer)

```
python manage.py ownsms_housekeeping     # expire TTL-passed messages, reclaim timed-out leases
python manage.py ownsms_webhooks         # deliver pending webhooks with retry
```

## Compatibility

Verified against a CI matrix (`tox.ini` + GitHub Actions):

| Python | Django 4.2 | 5.0 | 5.1 | 5.2 |
|--------|:----------:|:---:|:---:|:---:|
| 3.11   |     ✓      |  ✓  |  ✓  |  ✓  |
| 3.12   |     ✓      |  ✓  |  ✓  |  ✓  |
| 3.13   |     —      |  —  |  ✓  |  ✓  |

Django 4.2 and 5.0 don't support Python 3.13.

## Development

```
pip install -e ".[dev]"
pytest                 # unit + integration tests
ruff check src tests   # lint
ruff format src tests  # format
tox                    # full Python x Django matrix
```

### Quality checks

- **Lint** — `ruff check src tests` (E, F, I rules)
- **Format** — `ruff format src tests` (enforced in CI)
- **Types** — `mypy src/ownsms` (required; passes clean with django-stubs + mypy_django_plugin)
- **Security** — `bandit -r src/ownsms -ll -c pyproject.toml` + `pip-audit` (CVE scan)
- **Coverage** — `pytest --cov=ownsms --cov-report=term-missing` (floor: 80%)
- **Property tests** — Hypothesis (`tests/test_properties.py`) checks segment counts + phone normalization
- **Migration guard** — `django makemigrations ownsms --check --dry-run --skip-checks` ensures no missing migrations
- **Packaging** — `python -m build && twine check dist/*` + clean-install smoke test
- **pre-commit** — `.pre-commit-config.yaml` wires ruff + ruff-format + standard file hooks
- **Dependabot** — `.github/dependabot.yml` tracks pip + GitHub Actions deps weekly
- **CodeQL** — `.github/workflows/codeql.yml` runs Python static analysis on every push + weekly

**CI/CD** (GitHub Actions):
- `ci.yml` runs the test matrix (Py 3.11–3.13 × Django 4.2–5.2) + lint + format + typecheck
  (advisory) + security + migration guard + coverage + packaging smoke on every push / PR.
- `publish.yml` builds and publishes to PyPI via **Trusted Publishing** when a GitHub Release is
  published (no API token needed — configure the trusted publisher on PyPI once).

Cut a release: bump `version` in `pyproject.toml` + `src/ownsms/__init__.py`, tag `vX.Y.Z`, and
publish a GitHub Release.

## Status

Beta — full send + campaign + webhook + device pipeline implemented, 47 tests. Not yet
production-hardened (cloud quota and a separate scalable deployment are out of scope for the
self-host package). API may still change before 1.0.
