# Restaurant production readiness

**Date:** 30 October 2026 UTC.

**Verdict: Ready to sell to restaurants once this work passes CI and is promoted to `production`. Verified by evidence, not certified.** The same two owner actions as retail remain before anyone may call it certified (external penetration test, production restore drill).

Restaurant front of house is its own desk, isolated from retail and hotel (`RESTAURANT_FRONT_OF_HOUSE_SPLIT.md`). The back office (ingredient stock, purchasing, accounting, tax, reports) is the shared engine, kept per company by `tenant_id`.

| Gate | Status | Evidence |
| --- | --- | --- |
| Own till, shifts and cash drawer | done | `/restaurant/till`; `restaurant_till_shifts`, `restaurant_till_cash_moves`; `tests/test_restaurant_till_shift.py` |
| Own Orders, Bills and Guests screens | done | `/restaurant/orders`, `/restaurant/bills`, `/restaurant/guests`; `tests/test_restaurant_till_isolated.py` |
| Retail till refused for restaurants | done | `/pos/*` → 403 for a restaurant company; sidebar has no `/pos`, `/sales`, `/customers` |
| Restaurant, POS, hotel test files | pass | 294 passed locally (30 Oct) plus the new shift / guest / isolation tests (11 passed) |
| Migrations | pass | `20261030_0150` + `20261030_0151` up, down, up on a local database |
| Signed-in browser walk (desktop 1440×900 and tablet 820×1180) | pass | Open shift with GH₵200 float → dine-in with an extra and a kitchen note, sent → takeaway paid cash with change → cash in GH₵50 → Orders board → pay from Orders by card → Bills, refund → Till shifts → Guests → count and close (GH₵330.50 expected, short GH₵30.50 shown). No page errors; no failed API calls. |
| Full backend suite and frontend build | CI | Runs on the push to `main` |
| Restore drill on production (RPO/RTO) | owner | Not done |
| External penetration test | owner | Not done |

## What a restaurant gets

- **Till:** dine-in by table, takeaway and delivery; extras and kitchen notes; send to kitchen; pay by cash (quick amounts, change), card, Mobile Money or wallet. Money is only taken with an open shift.
- **Shift and drawer:** opening float, cash in and cash out with a reason, live "cash in drawer", count and close with over / short. Cash refunds come out of the drawer.
- **Orders:** a live board (not sent yet, in the kitchen, ready to serve) with wait timers, allergy and rush flags, and one-tap send, add dishes, take payment, cancel or void. Seat, course and pager details stay in the full order editor.
- **Bills:** takings by day and payment method, refunds, and every till shift with its count.
- **Guests:** built from orders and bookings: visits, spend, favourite dish, allergy, bill history.

## Known limits to tell customers

- Card, Mobile Money and wallet are recorded, not charged through a gateway.
- Restaurant till sales made before the split (on the old shared till) stay as read-only history in reports.
- Split payment of one bill across two methods is not offered on the restaurant till; take one method per bill.
- The Orders board refreshes every 20 seconds; it is not push-live.
