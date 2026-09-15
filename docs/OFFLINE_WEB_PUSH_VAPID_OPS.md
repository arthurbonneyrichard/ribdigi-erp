# Offline Web Push VAPID ops (remote wipe delivery)

**Status:** Push delivery remains **PARTIAL**. This doc does **not** claim Offline Complete,
push-delivery Complete, or 7-day VERIFIED.

Web Push is an optional faster path for remote IndexedDB wipe. Soft lockdown + wipe queue +
online poll /ack always remain the source of truth when push is unavailable.

## Fail-closed / unconfigured behavior

| Condition | Wipe queued? Soft lockdown? | Push status | Client path |
|-----------|-----------------------------|-------------|-------------|
| `OFFLINE_PUSH_ENABLED=false` | Yes | `disabled` | Online poll `wipe_pending` → clear IndexedDB → `POST .../wipe/ack` |
| VAPID public or private key empty | Yes | `skipped_unconfigured` | Same poll path |
| Enabled + keys, no device subscription | Yes | `skipped_no_subscription` | Same poll path |
| Enabled + keys + subscription | Yes | `delivered` / `failed` | SW `push` handler **or** poll |
| Push service returns **404/410** | Yes | `failed` + subscription **revoked** | Poll until browser **rebinds** |

Never treat a skipped/disabled/failed push as wipe completion. Completion is client IndexedDB
clear + wipe/ack only.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OFFLINE_PUSH_ENABLED` | Master switch. Production template defaults `false` until keys are set. |
| `OFFLINE_PUSH_VAPID_PUBLIC_KEY` | Browser `applicationServerKey` (URL-safe base64, no padding OK). |
| `OFFLINE_PUSH_VAPID_PRIVATE_KEY` | PEM private key (or path accepted by `pywebpush`). |
| `OFFLINE_PUSH_VAPID_SUBJECT` | VAPID `sub` claim, e.g. `mailto:ops@your-domain`. |
| `OFFLINE_PUSH_MAX_ATTEMPTS` | Sync retries on transient failures (default `3`, capped at 10). |
| `OFFLINE_PUSH_RETRY_DELAY_MS` | Delay between sync retries (default `50`–`100`). |

Templates: `.env.example` (dev) and `.env.production.example` (fail-closed defaults).

## Generate VAPID keys

From a machine with backend deps (or any env with `py_vapid` / `cryptography`):

```bash
cd backend
python - <<'PY'
from base64 import urlsafe_b64encode
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

v = Vapid()
v.generate_keys()
pub = v.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
print("OFFLINE_PUSH_VAPID_PUBLIC_KEY=" + urlsafe_b64encode(pub).decode().rstrip("="))
pem = v.private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
print("OFFLINE_PUSH_VAPID_PRIVATE_KEY=<<PEM below — store as one line with \\n or multiline secret>>")
print(pem.decode())
PY
```

Store the private key in your secret manager / compose secrets — **never commit real keys**.

## Enable path (ops)

1. Generate keys; set `OFFLINE_PUSH_VAPID_PUBLIC_KEY` and `OFFLINE_PUSH_VAPID_PRIVATE_KEY`.
2. Set `OFFLINE_PUSH_VAPID_SUBJECT` to a real contact `mailto:`.
3. Set `OFFLINE_PUSH_ENABLED=true`.
4. Restart API workers.
5. Confirm `GET /api/v1/offline/push/vapid-public-key` returns `configured: true`, `enabled: true`
   (authenticated POS/company role). Public key only — no private material.
6. On each till: Company → Offline devices → **Bind browser** (registers / rebinds subscription).
7. Test wipe on a non-production device: wipe response `push_delivery.status` should be
   `delivered` when subscribed; otherwise an honest skip/fail status. Confirm IndexedDB clear + ack.

## Hardening notes (PARTIAL)

- Transient HTTP (`408/429/5xx`) and common network errors retry up to `OFFLINE_PUSH_MAX_ATTEMPTS`.
- HTTP **404/410** revokes the stored subscription; UI asks for rebind; wipe stays pending via poll.
- Client always re-PUTs the current PushManager subscription on bind (rebind); `forceResubscribe`
  is available after key rotation / gone endpoints.

## Automated evidence vs operator proof

| Layer | Where | Marks Complete? |
|-------|--------|-----------------|
| Automated wipe-via-push evidence (generated VAPID, subscribe, wipe payload, 410, mock `pywebpush`) | `backend/tests/test_offline_wipe_push_vapid_evidence.py` | **No** — keeps PARTIAL |
| Related delivery / wipe unit tests | `test_offline_push_delivery.py`, `test_offline_remote_wipe.py` | **No** |
| Operator real-browser staging checklist | `docs/offline_wipe_push_staging_checklist.md` | **No** alone — required before any push-delivery Complete claim; Offline Complete still separate |

Automated evidence ≠ push-delivery Complete. Physical/browser ops cannot be
skipped for Complete.

**Cloud Agent note (2026-09-15):** A local Chrome CDP attempt with generated VAPID
keys reached SW ready + device bind, but `PushManager.subscribe` timed out (no
usable FCM endpoint in that desktop). That attempt is documented as a **blocker**,
not proof — do not treat it as push-delivery Complete. Retry on a normal staging
till browser per `docs/offline_wipe_push_staging_checklist.md`.

**Local alternative:** When FCM is blocked, prove wipe via the poll path
(`docs/OFFLINE_WIPE_POLL_LOCAL_ALTERNATIVE.md`) — engineering-ready, Completes still
MISSING. Client bind now times out subscribe (`subscribe_timeout`) and Shell polls
wipe every ~45s while online.

## Honesty

- Remote wipe = **PARTIAL** (poll-path **engineering-ready**; push still PARTIAL)
- Push delivery = **PARTIAL** (ops VAPID + browser proof still required for Complete)
- Offline Complete / 7-day VERIFIED = **MISSING**
- Owner-alert push channel remains deferred (email/dashboard only)
- 7-day evidence template: `docs/OFFLINE_7DAY_EVIDENCE_TEMPLATE.md`
