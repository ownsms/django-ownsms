# ownsms — Quickstart

Send your first SMS in four steps. Examples use the live demo host
`https://sms.omadli.uz`; replace it with your own deployment.

All requests authenticate with `Authorization: Bearer <token>`. There are two token types:

- **API key** (`osk_...`) — for you, the developer, to send and read messages.
- **Device token** — for the Android sender app to poll and report. You never use this directly.

---

## 1. Get an API key

**Easiest:** install the [ownsms Android app](https://github.com/ownsms/ownsms-android), enter your
server URL (`https://sms.omadli.uz`), and register. Open **Settings → Account** and copy the API key.

**Or via the API** (creates an account + device and returns the key **once**):

```bash
curl -X POST https://sms.omadli.uz/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{"device_name":"My phone"}'
```

```json
{ "account_id": 1, "device_id": 1, "device_token": "…", "api_key": "osk_…" }
```

Keep `api_key`. Pair the Android app to this account with a code from
`POST /api/v1/devices/pairing-code`, or just register from the app as above.

## 2. Make sure a phone is online

The API only queues messages — a **paired Android phone** running the sender app dispatches them
over its SIM. Check it:

```bash
curl https://sms.omadli.uz/api/v1/device \
  -H "Authorization: Bearer osk_YOUR_KEY"
```

```json
{ "online": true, "status": "active", "today_sent": 0, "sims": [ … ] }
```

## 3. Send an SMS

```bash
curl -X POST https://sms.omadli.uz/api/v1/messages \
  -H "Authorization: Bearer osk_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"to":"+998901234567","text":"Salom from ownsms!"}'
```

```json
{ "id": "msg_1", "status": "queued", "to": "+998901234567", "text": "Salom from ownsms!",
  "from": "+998901112233", "segments": 1, "error_code": null, "created_at": "…" }
```

Only `to` and `text` are required. Optional: `from` (a specific SIM number), `queued`
(`true` = wait for the phone to come online), `ttl`, `send_at` (schedule), `idempotency_key`,
`callback_url` (per-message webhook).

## 4. Check the status

```bash
curl https://sms.omadli.uz/api/v1/messages/msg_1 \
  -H "Authorization: Bearer osk_YOUR_KEY"
```

### Status lifecycle

```
queued  →  sending  →  sent  →  delivered
                         └────→  failed | expired | canceled
```

| Status | Meaning |
|-----------|---------|
| `queued`  | Accepted, waiting for the phone. |
| `sending` | Handed to the phone; being sent over the SIM. |
| `sent`    | **Accepted by the carrier — treat this as success.** |
| `delivered` | The operator returned a delivery report. A bonus — many networks never send one, so **don't wait on it**. |
| `failed`  | Could not be sent (see `error_code`). |
| `expired` | TTL passed before the phone could send it. |
| `canceled`| Canceled while still `queued`. |

> **Important:** `sent` is the practical success state, exactly like Eskiz / Playmobile / Twilio
> on many networks. `delivered` depends entirely on the mobile operator and may never arrive.

## More

- Full reference: `https://sms.omadli.uz/api/v1/docs` (Swagger UI) · schema at `/api/v1/openapi.yaml`
- Bulk sends (campaigns), webhooks, API-key scopes & IP allowlist, audit log — see the reference.
