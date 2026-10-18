# Retail financial integrity

**Date:** 17 October 2026 UTC. **Status: PARTIAL.**

| Flow | Status | Notes |
| --- | --- | --- |
| POS cash sale | NOT TESTED this pass | 15 Oct fixture: total 220, revenue 200, tax 20, COGS 120, cash on account 1000, one balanced journal. In-memory SQLite. |
| Mobile Money and card | NOT TESTED this pass | Documented posting is bank GL 1010, not till cash 1000. Recorded tender only. No gateway capture. |
| Customer credit | NOT TESTED this pass | Override requires a reason and `credit:approve`. |
| Supplier bill from GRN | PARTIAL | API copies every accepted GRN line onto the draft invoice and rejects a second invoice for the same GRN (409). Approve, AP balance, and payment were not posted in this pass. |
| Supplier payment | NOT TESTED this pass | Cashier without `credit:read` is 403 (15 Oct). |
| Journals | NOT TESTED this pass | Debit equals credit is the service rule. Not re-measured. |
| Valuation | PARTIAL | Standard cost only. FIFO, LIFO, and average return 400. |

No production ledger was modified.
