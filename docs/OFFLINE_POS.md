# Offline POS (not Offline Complete)

**Status:** The supported POS queue is **Ready**. Offline Complete remains **MISSING**. Offline Complete remains missing because the browser device id is not strong device binding, a private window with no till-agent journal on this PC cannot recover those sales, saved sales upload only while the Point of Sale page is open and signed in, and a live site has not been tested. This document describes the POS-only queue that flushes into existing `POST /api/v1/pos/sales` (`client_request_id` idempotency). There is no second sync stack, and inventory / reports / hotel are **not** offline.

## What works offline (POS only)

After a **successful online sign-in on this device**, the till may:

1. Use the **previously synced catalog and prices** for the signed-in user and assigned store.
2. **Record a sale** for cash, card, Mobile Money, or bank transfer. Those are recorded tenders; the ERP does not collect card or Mobile Money itself. Wallet, gift card, and loyalty stay online-only. Credit can be queued only when the grant includes `credit_sale`; the server rechecks the limit and holds an unsafe sale for review.
3. **Queue** those sales in encrypted IndexedDB, partitioned by tenant / user / store.
4. Show **Online / Offline** and **pending-sync** counts on the POS screen, including a stale-stock warning. While the till is online and nothing is waiting, Offline selling stays closed until the cashier opens it. A queued sale is sent on its own when this till can reach the server. The cashier does not press Send. Company admin, super admin, and store manager see each cashier on the dashboard: online or offline, how long offline, store, open shift, and sales still waiting to sync. The waiting count on an offline till is the last report from that till.
5. **Flush** the queue automatically when the server answers again, and keep retrying a missed server response while the sale is still on the device. The server revalidates prices and stock. A price, stock, or credit conflict stays for a manager and is not posted on its own. Sales are never silently dropped, and the cashier is not asked to retry them.
6. **Keep a second copy on this PC** when the till print agent is running. That copy is a file outside the browser. Clearing site data does not delete it. Opening Point of Sale after sign-in reads it back for this company and user, with the same `client_request_id`. The sale stays pending until the server returns a sale id.

- First-time use while the server cannot be reached shows: “Connect to the internet and sign in to prepare this device for offline POS.” The sign-in page clears that sentence once `GET /api/v1/health` succeeds, so a failed first check does not leave it on screen. When the till is online and a cashier is signed in, Point of Sale prepares the device (grant, catalog, and IndexedDB) without a Send, Retry, or Refresh click and without opening Offline selling. After that save succeeds, the offline status is “Offline ready”. If prepare fails, the till says what failed. That unprepared sentence stays only when there is still no grant.
- An expired or revoked grant keeps queued sales and requires online sign-in.
- The till status is **Online** only after `GET /api/v1/health` succeeds. Browser `navigator.onLine` alone is not enough. **Offline** covers lost internet and an unreachable API. **Syncing** and **Sync failed** are separate. Text is shown with the color.
- If Pay is attempted while the browser still looks online but the API does not answer, a prepared till stores the sale and prints “Offline sale — pending synchronization.”
- Wallet, gift card, and loyalty stay online-only. Cash, card, Mobile Money, and bank transfer are recorded tenders. Credit can be queued only when the grant includes `credit_sale`; the server rechecks the limit on sync and leaves an over-limit sale for a manager.

## Duration (not hardcoded 7 days in the client)

| Setting | Default | Notes |
|---------|---------|--------|
| `OFFLINE_AUTH_HOURS_DEFAULT` | **168 hours (7 days)** | Matches `REFRESH_TOKEN_EXPIRE_DAYS`. |
| Tenant override | `PATCH /tenants/me` `offline_auth_hours` (1–168) | Exposed on `GET /pos/offline-policy` and `/me`. |
| Idle session | `inactivity_timeout_minutes` (5–480, default 30) | Unchanged BR-19.3 policy for **online** tabs. |

After expiry the device locks new offline sales. Reconnect and sign in online to sell again. Queued sales stay pending; older rows stored as `expired` are put back to pending. They are not deleted.

## Isolation

- APIs use the **JWT tenant** plus **session store/branch assignment** (`UserStoreMembership`). Client `store_id` values are authorized, never trusted alone.
- Prefetch cache keys include tenant, user, and store. Logout / tenant switch / 401 clears prefetch, `/me` cache, and offline auth (pending sales are locked, not wiped).
- Location assignment does **not** add RBAC permissions.

## Tokens and storage

- Access and refresh tokens are **not** stored in `localStorage`. They sit in memory and encrypted IndexedDB (`ribdigi-session-auth`). A one-time migrate copies any legacy `localStorage` tokens then deletes them.
- Offline envelopes and sale payloads are encrypted with AES-GCM when Web Crypto is available.
- Recovery packages never include JWTs or passwords.

## Sync / conflicts

- Idempotency: unique `(tenant_id, client_request_id)` on `transactions`. The same commercial request returns the original sale. A reused id with different contents is HTTP 409 `CLIENT_REQUEST_REUSED`. On 2026-10-14 the in-memory replay, existing idempotent sale, and offline quote tests passed: 7 passed in 32.03s.
- A missed response (network, 5xx, 429, or 408) stays pending and retries while the Point of Sale page is open and signed in. A price, stock, or credit conflict stays for a manager. `OFFLINE_SYNC_MAX_RETRIES` is not a stop.
- `409 PRICE_CONFLICT` / `409 STOCK_CONFLICT` / `403 OFFLINE_AUTH_EXPIRED` leave the local sale in queue for review.
- Server catalog and on-hand stock are the source of truth after a successful sync.
- Audit: `offline_sync_events` (offline created_at, user, device, result, conflict).

## LIMITATIONS (honest)

- **Not Offline Complete.** No offline inventory counts, reports, hotel, purchasing, or accounting. `offline_complete_claimed` stays false (`backend/app/offline_pos.py`). On 2026-10-14, `tests/test_pos_offline_journal_r1.py --noconftest` passed 4 tests in 0.70s: the file keeps the original `client_request_id` and payload, and a later write does not change those terms. That test calls the journal module. It does not prove a closed browser uploads. The same evening, `frontend` `npm run test:offline` passed **20** tests. On 15 October 2026 UTC the same command passed **21** tests, 0 failed, exit 0. The added test prepares a grant, queues a cash sale, closes IndexedDB, reads the sale back, and flushes twice: the fake API is called once with the same `client_request_id`. That is not a live API and not the drill cashier. It does not prove a closed browser uploads, a private window recovers a sale with no till-agent journal, or strong device binding. The service worker still returns before caching `/api/`. Wallet, gift card, and loyalty stay online-only. Credit stays on the server-reviewed queue.
- The device id is a random value stored in IndexedDB. A legacy `localStorage` id is copied once and then removed. That id is **not** strong device binding.
- IndexedDB does not survive clearing site data. Recovery uses the till print agent journal on this PC, not the browser store. The agent listens on `127.0.0.1` only (default port `8765`) and writes `RIBDIGI_OFFLINE_JOURNAL`, or `%LOCALAPPDATA%\Ribdigi\pos-offline-journal.json` on Windows. Each queued sale is copied there when it is saved. Passwords and tokens are not written. After site data is cleared, Point of Sale reads that file for the signed-in company and user and keeps the same `client_request_id`. A sale is not marked synced until the server confirms it. Financial terms on that copy do not change. A private window, or a till where the agent was not running when the sale was saved, has no outside copy and cannot recover the sale. This is not a cloud backup.
- Local browser check on 2026-10-13, company `offline-drill-oct13` only, local database `ribdigi_erp`: signed in online, cut the network, sold one cash item, reloaded while offline, restored the network, and the queue synced. Server result: one completed sale `POS20260001`, one `client_request_id`, stock 8 to 7, one stock-out, one balanced journal (cash 11.50, revenue 10.00, tax 1.50, COGS 2.00, inventory 2.00), one cash tender of 11.50, open shift `SHIFT-2026-0001` with sale count 1 and expected cash 11.50. The existing demo till was not used. This does not certify offline mode.
- Cached stock is **non-authoritative**.
- Payment rails are **details only** — the product never holds or captures card/wallet funds offline.
- XSS can still read in-memory tokens; httpOnly cookies are not claimed here.
- Grandfathered users with **no** store memberships still see all tenant stores (legacy). Assigned memberships constrain access.
- Alembic `20260930_0127` (offline auth hours + `offline_sync_events`) sits in the linear chain through `20260930_0129`. Apply head; IF NOT EXISTS keeps a partial apply safe.
- POS device heartbeat (`POST /pos/devices/heartbeat`) is tenant-scoped last-seen monitoring on existing `pos_devices`. It is not a second sync engine and is not Offline Complete.
