# Retail offline POS status

**Date:** 17 October 2026 UTC. **Status: BLOCKED** for Offline Complete. The supported queue is **PARTIAL** relative to a live till.

`offline_complete_claimed` stays false. See `docs/OFFLINE_POS.md`.

## What the product can do

A prepared Point of Sale can queue cash, card, Mobile Money, bank transfer, and granted credit. Wallet, gift card, and loyalty stay online. Inventory, purchasing, accounting, reports, hotel, and restaurant stay online. The same `client_request_id` must create one sale.

15 October 2026: `frontend` `npm run test:offline` **21 passed**. That run was not repeated on 17 October.

## Limits that stay

- The browser device id is not strong device binding.
- A private window with no till-agent journal on that PC cannot recover those sales.
- Clearing site data drops the IndexedDB queue.
- Saved sales upload only while the Point of Sale page is open and the cashier is signed in.
- A live site has not been certified.
- A sale whose first response was lost was not replayed in this pass (workflow J).

Indicators and queue durability were not clicked in a browser on 17 October.
