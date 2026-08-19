# Stage 11 Fidelity Notes — Purchase-to-Pay Chain

**Status:** Closed with Stage 11 exit  
**Chain:** Purchase Order → Goods Received → Inventory → Supplier Balance → Accounting → Audit Trail

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| GRN AP valuation | `qty × unit_price × (1+tax%)` ignored line discount | `_calc_partial_po_line_amounts` (discount scaled + tax on net) |
| PI line totals | Tax before discount; line discount dropped from invoice total | Same PO math via `_prepare_invoice_lines` |
| PI from GRN | Line `discount: 0` | Proportional PO line discount |
| AP aging (uninvoiced PO) | Full `po.total_amount` | `po_received_accepted_value` (0 if nothing received) |
| GRN-linked RC PI | Skipped all journals | Self-assess Dr 1300 / Cr 2100 only (`skip_inventory_ap`) |
| Domain audit | Payment/PI cancel missing; GRN lacked balance delta | `supplier_payment_recorded`, `purchase_invoice_cancelled`; richer `grn_posted` |
| API GRN example | `po_id` | `purchase_order_id` |
| BR-6.x checkboxes | Unchecked despite shipped paths | Marked complete with Stage 11 notes |

## Evidence tests

- `backend/tests/test_purchasing_chain_c1.py`
- `backend/tests/test_grn_linked_rc_c2.py`
- `backend/tests/test_purchasing_audit_a1.py`

## Deferred (not Stage 11)

PO Kanban, multi-GRN partial-invoice aging edge cases beyond “any PI skips PO fallback”, Open Banking, FIFO/LIFO, tax e-file, K8s/WAL/PITR.
