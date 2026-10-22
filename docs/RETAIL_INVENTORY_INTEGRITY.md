# Retail inventory integrity

**Date:** 17 October 2026 UTC. **Status: PARTIAL.**

| Movement | Status | Rule in code | This pass |
| --- | --- | --- | --- |
| Stock in, out, adjust, opening | NOT TESTED | Movement row plus balance update | Not executed |
| GRN accept | PARTIAL | Only `accepted_qty` increases stock | Not executed against a database |
| GRN reject | PARTIAL | Rejected quantity does not enter sellable stock; reason required | Not executed |
| Partial PO | PARTIAL | Outstanding is ordered minus received. Amend is blocked after any receipt | Not executed |
| Sale and return | NOT TESTED | POS fixture on 15 Oct reduced stock 20 to 18 for a quantity of 2 | Not re-run |
| Count variance | NOT TESTED | Complete posts adjustments. Cancel needs a reason and posts nothing | Not executed |
| Transfer | NOT TESTED | Inter-store approval before ship | Not executed |
| Unit conversion | NOT TESTED | `to_stock_qty` converts document units to the product stock unit | Carton example not run |
| Valuation | PARTIAL | Standard cost. Other methods 400 | Not executed |

Duplicate GRN posting was not concurrency-tested.
