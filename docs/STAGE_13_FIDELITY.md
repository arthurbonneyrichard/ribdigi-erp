# Stage 13 Fidelity Notes — POS Sale Execution Chain

**Status:** Open (D1); closes with Stage 13 exit  
**Chain:** POS → Sale → Payment → Inventory deduction → Receipt → Accounting → Audit

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| Stock-fail on POS sale | Authoritative stock-out mid-handler; orphans only avoided by uncommitted rollback (unproven) | Fail-fast `assert_outbound_lines_stock_available` (aggregated qty) → `409 INSUFFICIENT_STOCK`; proven no `Transaction` / `PosPayment` / `pos_sale` JE / session delta (`test_pos_sale_atomicity_h1.py`) |
| Multi-tender E2E | Split tender unit/API tests; cash-only Stage 12 C2 chain | Full closeout: cash+card+wallet+credit → stock → receipt → journal → session buckets → close (`test_pos_execution_chain_h2.py`) |
| Digital receipt send audit | Send succeeded without domain audit | `pos_receipt_sent` on successful email/SMS send |
| Drawer on split | Pulse when primary method forced to cash via `has_cash_tender` | Proven: drawer pulses when split includes cash; skipped for card+wallet-only |
| API receipt docs | Incomplete send route; outdated receipt query params | `POST .../receipt/send`; `format`/`paper` documented |
| BR-8 / BR-18.4 / launch / readiness | Stage 12 cash-path notes only | Stage 13 H1/H2 evidence linked |

## Evidence tests

- `backend/tests/test_pos_sale_atomicity_h1.py`
- `backend/tests/test_pos_execution_chain_h2.py`
- `backend/tests/test_stage13_fidelity_d1.py`

## Spec sync targets

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md` — BR-8.1 / BR-8.2 / BR-18.4
- `docs/API_DOCUMENTATION.md` — §8 POS
- `docs/LAUNCH_CHECKLIST.md` — §4 POS smoke
- `PRODUCTION_READINESS.md` — POS bullet
- `docs/USER_MANUAL.md` — §5 POS notes
- `docs/DEVELOPMENT_ROADMAP.md` — Phase 3 POS deliverable note

## Deferred (not Stage 13)

Vendor USB/serial POS drivers beyond TCP ESC/POS / browser bridge; Open Banking; FIFO/LIFO/WA; K8s/WAL/PITR; pen test; percentage discount UI polish.
