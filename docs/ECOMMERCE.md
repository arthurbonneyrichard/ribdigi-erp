# Tenant ecommerce

Built-in storefront plus a WooCommerce connector. Every tenant uses its own verified hostname. There is no public Ribdigi subdomain.

## Status board (21 October 2026 UTC)

| Area | Status | Notes |
| --- | --- | --- |
| Package / role / industry gates | **Completed** | `ecommerce` on trial / professional / enterprise. Starter, hotel, restaurant, and cashier stay 403. |
| Tenant admin storefront, catalog, domains, orders, gateway, Woo | **Completed** | Staff `/ecommerce` desk uses shared PageHeader, EmptyState, cards, and tables. Secrets stay encrypted and redacted. |
| Platform owner health | **Completed** | `GET /tenants/{ref}/usage` includes `ecommerce_health` without tokens or secrets. Modules stay the package entitlement. |
| Custom domain uniqueness and unknown-host 404 | **Completed** | Server-side mapping only. Host / X-Forwarded-Host is ignored unless verified. |
| Website linking (hostname or https URL) | **Completed** | `POST /ecommerce/domains` accepts `shop.example.com` or `https://shop.example.com`. Company website can be linked. Unlink is `DELETE`. Reserved Ribdigi hosts 422. |
| Domain TXT verify, primary, redirect, display states | **Completed** | pending / configuring / active / failed. Ownership loss rotates the token and requires verify again. |
| Live DNS records | **Blocked** | Owner must create A/CNAME + TXT at the tenant DNS host. |
| HTTPS certificates | **Blocked** | Terminate TLS on the reverse proxy, then mark HTTPS-ready. This tree does not issue certificates. |
| Built-in catalog, cart, guest checkout, policies, preview | **Completed** | Shared shopper chrome, hero, product page, search, category, pagination, public product images, qty/remove cart, contact / shipping / returns / privacy. |
| Storefront logo, banner, favicon | **Completed** | Staff upload on `/ecommerce` media. Public `/storefront/media/{logo\|banner\|favicon}`. Separate from ERP sidebar logo. Empty until uploaded. |
| Storefront customer accounts and order history | **Completed** | Separate shopper rows (not ERP `User`). Register / login / logout / history. Staff email 409. Guest checkout remains. |
| Variant-level online mapping | **Completed** | Catalog `variants[]`. Cart, order, and reservation lines store `variant_id`. Stock still reserved at product warehouse qty. |
| Stock reservation, expiry, cancel, POS available_qty | **Completed** | Online buffer plus active holds. Offline POS still cannot promise live stock. |
| Fulfillment packed → dispatched → delivered | **Completed** | Staff advances one step. |
| Returns and refunds | **Completed** | Posted invoice return + refund journal through existing sales return. |
| Signed webhook payment, return URL not paid | **Completed** | Amount, currency, tenant, reference, idempotent event id. Forged signature is 401. |
| Live tenant payment processor | **Blocked** | Do not put live secrets in the repo. No real charge from this tree. |
| WooCommerce product and order import | **Completed** | Unpublished catalog. Duplicate `woo:{id}` skipped. Other platforms stay 501. |
| Woo stock / fulfillment push | **Completed** | Best-effort PUT order status + product stock for `woo:{id}` only. Failures stay on `last_error`. |
| Sync jobs, retry, no duplicate running job | **Completed** | `expire_ecommerce_reservations`, `sync_ecommerce_connectors`. |
| Public storefront on a real tenant hostname | **Blocked** | Needs owner DNS + TLS + a tested webhook. Preview token is the ready path. |
| Offline Complete / wallet / escrow | **Blocked** | Out of scope. `offline_complete_claimed` stays false. |

## What is implemented

- Staff screen `/ecommerce`: enable storefront, policies, opt-in catalog, domains, orders (collect / pack / dispatch / deliver / return), encrypted gateway, WooCommerce connector, retry failed jobs, storefront logo / banner / favicon upload (not the ERP sidebar logo).
- Public storefront `/storefront`: forest/brand chrome, uploaded logo in the header, banner on the hero when present, favicon when present, published catalog with search and category, product page (`product_id` bootstrap), variant picker, cart qty/remove, guest or shopper checkout, delivery or pickup, confirmation/tracking, `/storefront/account` history, policy empty states, staff preview via `preview_token` (blank/garbage preview token is 422). Unknown hosts show “This store is not available.” Empty media slots stay empty until uploaded. Cart and checkout show a load error instead of pretending the cart is empty.
- Custom domains: unique hostname, TXT `ribdigi-site=<token>`, verified / configuring / active / failed, primary and redirect. Unknown hosts return 404.
- Stock reservations at checkout. POS `available_qty` subtracts active online holds. Online sellable qty also subtracts the listing stock buffer.
- Tenant payment gateway credentials are encrypted and separate from Ribdigi subscription billing. The return URL does not mark an order paid.
- WooCommerce product and order import, plus outbound order status and stock quantity for `woo:{id}` rows. Shopify, Squarespace, Magento, and custom stay 501.

## Pilot

A controlled preview on a disposable company is ready after Alembic `20261021_0141` on a **non-live** database. A public pilot needs owner DNS, TLS, and a tested tenant webhook.
