# Stage 12 Fidelity Notes — Order-to-Cash & POS

**Status:** Closed with Stage 12 exit  
**Chain:** Customers → Sales → Sales Items → Invoices → Payments → POS

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| Quote/order/invoice line tax | Tax on gross, then subtract discount | `calc_sale_line_amounts` — tax on net after line discount (aligns POS / Stage 11 PO) |
| OTC E2E proof | Fragmented tests only | `test_sales_chain_c1.py` |
| POS E2E proof | Fragmented cart/split/drawer tests | `test_pos_chain_c2.py` (open→sale→receipt→stock→close) |
| POS domain audit | Mostly drawer + credit override | `pos_session_opened`, `pos_sale_completed`, `pos_session_closed` |
| BR-7/8 + launch checklist | Unchecked | Marked complete with Stage 12 evidence |

## Evidence tests

- `backend/tests/test_sales_chain_c1.py`
- `backend/tests/test_pos_chain_c2.py`
- `backend/tests/test_pos_audit_a1.py`

## Deferred (not Stage 12)

Percentage discount UI polish, vendor USB/serial POS drivers, Open Banking, FIFO/LIFO, K8s/WAL/PITR, pen test.
