# Offline POS (not Offline Complete)

**Status:** Offline Complete remains **MISSING**. This document describes the POS-only queue that flushes into existing `POST /api/v1/pos/sales` (`client_request_id` idempotency). There is no second sync stack, and inventory / reports / hotel are **not** offline.

## What works offline (POS only)

After a **successful online sign-in on this device**, the till may:

1. Use the **previously synced catalog and prices** for the signed-in user and assigned store.
2. **Create cash sales** and record **payment details** (method, amount, reference). Card / wallet / credit are blocked offline — the app does not pretend a provider captured funds.
3. **Queue** those sales in encrypted IndexedDB, partitioned by tenant / user / store.
4. Show **Online / Offline** and **pending-sync** counts on the POS screen, including a stale-stock warning.
5. **Flush** the queue when back online. The server revalidates prices and stock. Conflicts stay visible; sales are never silently dropped.

First-time login while offline is **not** supported. Restore of queued sales also requires an online check.

## Duration (not hardcoded 7 days in the client)

| Setting | Default | Notes |
|---------|---------|--------|
| `OFFLINE_AUTH_HOURS_DEFAULT` | **168 hours (7 days)** | Matches `REFRESH_TOKEN_EXPIRE_DAYS`. |
| Tenant override | `PATCH /tenants/me` `offline_auth_hours` (1–168) | Exposed on `GET /pos/offline-policy` and `/me`. |
| Idle session | `inactivity_timeout_minutes` (5–480, default 30) | Unchanged BR-19.3 policy for **online** tabs. |

After expiry the device locks offline selling. Reconnect online to revalidate. Queued rows are marked `expired` / `conflict` — they are not deleted.

## Isolation

- APIs use the **JWT tenant** plus **session store/branch assignment** (`UserStoreMembership`). Client `store_id` values are authorized, never trusted alone.
- Prefetch cache keys include tenant, user, and store. Logout / tenant switch / 401 clears prefetch, `/me` cache, and offline auth (pending sales are locked, not wiped).
- Location assignment does **not** add RBAC permissions.

## Tokens and storage

- Access and refresh tokens are **not** stored in `localStorage`. They sit in memory and encrypted IndexedDB (`ribdigi-session-auth`). A one-time migrate copies any legacy `localStorage` tokens then deletes them.
- Offline envelopes and sale payloads are encrypted with AES-GCM when Web Crypto is available.
- Recovery packages never include JWTs or passwords.

## Sync / conflicts

- Idempotency: unique `(tenant_id, client_request_id)` on `transactions`.
- Bounded retries: 8 (`OFFLINE_SYNC_MAX_RETRIES`).
- `409 PRICE_CONFLICT` / `409 STOCK_CONFLICT` / `403 OFFLINE_AUTH_EXPIRED` leave the local sale in queue for review.
- Server catalog and on-hand stock are the source of truth after a successful sync.
- Audit: `offline_sync_events` (offline created_at, user, device, result, conflict).

## LIMITATIONS (honest)

- **Not Offline Complete.** No offline inventory counts, reports, hotel, purchasing, or accounting.
- Cached stock is **non-authoritative**.
- Payment rails are **details only** — the product never holds or captures card/wallet funds offline.
- XSS can still read in-memory tokens; httpOnly cookies are not claimed here.
- Grandfathered users with **no** store memberships still see all tenant stores (legacy). Assigned memberships constrain access.
- Alembic `20260930_0127` (offline auth hours + `offline_sync_events`) sits in the linear chain through `20260930_0129`. Apply head; IF NOT EXISTS keeps a partial apply safe.
- POS device heartbeat (`POST /pos/devices/heartbeat`) is tenant-scoped last-seen monitoring on existing `pos_devices`. It is not a second sync engine and is not Offline Complete.
