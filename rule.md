# Confirmed implementation rules

These are rules already implemented or recorded in this repository. Proposals and open decisions live in `planning.md`. Work tracking lives in `tasks.md`.

Do not treat this file as a second copy of `AGENTS.md`. `AGENTS.md` is the always-applied workspace rule. Deeper sources: `docs/ADR_001_TENANCY.md`, `docs/OFFLINE_POS.md`, `docs/RETAIL_FEATURE_MATRIX.md`, `docs/COMMERCIAL_READINESS_REPORT.md`, `docs/SAAS_BILLING.md`, `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`.

## Stack and tenancy

- Backend: FastAPI, async SQLAlchemy, Alembic. One migration head (`20261022_0142` at inspection). Apply with `alembic upgrade head` only. Do not `create_all` or stamp a live database. Keep migration history. Do not migrate live `ribdigi_erp` from this work.
- Frontend: Next.js 14 App Router (`next` 14.2.35) and React 18 (`react` 18.3.1).
- Tenancy is shared-schema. Every tenant-owned row carries `tenant_id`. The JWT tenant is the scope. `X-Tenant-ID`, when sent, must be that tenant’s UUID. Queries do not trust a client-supplied tenant. Company and Tenant are the same profile for this product. See `docs/ADR_001_TENANCY.md`.

## Retail scope and industry

- A new company can choose only `retail`, `hotel`, or `restaurant` (`VALID_INDUSTRIES` / `PROVISION_INDUSTRIES`).
- Pharmacy stays recognizable for a company that already has that industry. It is not a choice for a new company and it is not a sidebar item.
- Do not restore FMCG as a selectable industry or a sidebar module.
- Hotel and restaurant screens stay on their own industries. Retail does not show hotel floor, restaurant floor, or pharmacy prescription flows.

## Isolation, permissions, and stores

- Company data stays on the server-side tenant. Permissions are enforced on the API, not by hiding a button alone.
- Store caps use `store_entitlements`. `NULL` means unlimited. Create and activate count **active** stores. A downgrade does not delete stores; it sets `over_entitlement` and blocks further creates and activations.
- A store must not have two warehouses with the same `store_id`. Warehouse create and edit refuse a second link. `warehouse_for_store` returns one row (lowest code) if leftover duplicates exist, so a till sale does not 500.

## Payments

- Customer and POS payments are recorded tenders. They are not subscription collection.
- No repository gateway is enabled for live charges. Checkout return alone does not mark a subscription invoice paid.
- Mobile Money is a recorded tender. It posts to bank GL `1010`, not till cash `1000`.
- Gift-card and loyalty tenders debit `2150` and `2160`. A cash-account id on those tenders is ignored. Any other non-cash tender that resolves to till cash `1000` is rejected. An inactive bank account `1010` rejects card and Mobile Money. An inactive `2160` rejects a loyalty tender. Neither case is posted to till cash. Issuing a gift card still debits expense `6100` and credits `2150` because that screen does not collect cash. Loyalty issuance debits `6110` and credits `2160`. Reversing that award debits `2160` and credits `6110`.
- A gift-card or loyalty refund credits `2150` or `2160` and ignores a client account id. Any other non-cash refund that resolves to till cash `1000` is rejected. That refund journal does not put the amount back on the plastic card balance, because a return has no card code. Drawer cash includes only method `cash`.
- A subscription invoice becomes paid only when a signed webhook matches amount, currency, and tenant. Do not invent gateway secrets or call a live processor.
- Tenant ecommerce uses each company's verified hostname. Host and X-Forwarded-Host are not trusted without that mapping. The ERP catalog is opt-in. Storefront payments are recorded separately from Ribdigi subscription billing. A checkout return URL does not mark an online order paid. Offline Complete stays false. No wallet or escrow.
- Supplier payments (`POST /suppliers/{id}/payments`) require `credit:read` as well as `credit:write`. Till credit is `credit:write` only, so a cashier cannot record a supplier payment. Customer payments and POS credit stay on `credit:write` or `sales:write`.

## Offline POS

- Offline scope is supported POS workflows only (catalog already on the device, recorded cash / card / Mobile Money / bank transfer, and credit only when the grant includes it). Inventory, purchasing, accounting, reports, and hotel stay online-only.
- A closed browser cannot upload IndexedDB. The device id is not strong device binding. Clearing site data removes the browser queue. Sales already copied to the till-agent journal on this PC can be read back with the same `client_request_id`. A private window with no till-agent journal cannot recover those sales.
- Offline authorization is an expiring server grant for that device, company, and user. Passwords are not stored for offline use. Access and refresh tokens are not kept in `localStorage`.
- Unprepared device copy: “Connect to the internet and sign in to prepare this device for offline POS.”
- Expired grant copy: “Online sign-in is required before this device can sell offline again. Saved sales stay on this device.”
- Queued sales stay on the device. Sync runs by itself while the Point of Sale page is open and signed in. The cashier does not press Send. A missed response (network, 5xx, 429, 408) stays pending. A 4xx price, stock, or credit conflict stays for a manager. Do not change financial terms on sync. Do not delete the queue to “clear” an error.
- Idempotency is `(tenant_id, client_request_id)` on transactions. The same commercial request returns the original sale. A reused id with different contents is HTTP 409 `CLIENT_REQUEST_REUSED`. Quotes use the same rule for customer, quantity, an explicit price, discount, and notes. A quote retry that leaves the price off still matches the stored quote. Stock and journals stay balanced with the posted sale. Server stock and prices win after a successful sync.

## Money, UI, and safety

- Money and quantities in JSON are numbers via `honesty.money_json`, not decimal strings. Values must be finite.
- Brand green `#4AB012` stays. New UI uses the existing CSS variables. Controls that users operate need `aria-label`s. Light and dark personal theme uses `data-theme`.
- Opening a desk warms the Next.js route from the sidebar (default Link prefetch plus idle `router.prefetch`). Hover/focus also prefetches that desk’s GET lists (`navPrefetch.ts`, 45s TTL). First paint reuses `createPaintGet`; a later refresh on the same mount forces fresh data. Writes stay on `api()`.
- No secrets in source, logs, or client bundles. Do not commit `.env` or `backend/_tmp_api_log.txt`.
- No production or staging migrate, restart, password reset, real charge, queued-data deletion, push, or deploy without explicit authorization.
- Preserve unrelated user changes. Pytest from `backend` uses the in-memory SQLite fixtures, not the live `ribdigi_erp` database.
