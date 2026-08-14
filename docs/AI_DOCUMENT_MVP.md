# AI Document Assistant — rule-based OCR MVP (BR-21.8)

## Scope

Unified `POST /ai/documents/analyze` over the shared `expense_ocr` engine (PDF text + Tesseract images). **No LLM.** Analyze is suggest-only. Explicit create endpoints write drafts only after human review:

- `POST /ai/documents/create-expense` — pending expense from reviewed fields (Save as Expense)
- `POST /ai/documents/create-purchase-invoice` — draft PI by copying lines from a matched PO (Save as Purchase Invoice, MVP)

| AC | Status |
|----|--------|
| OCR extraction from invoices, receipts, purchase orders | Complete (MVP): same field parser; `document_type` receipt/invoice/purchase_order/auto |
| Auto-match extracted data to system records | Complete (MVP): party name similarity + PO number substring match; receipt category keywords |
| Data validation and discrepancy flagging | Complete (MVP): missing fields, low confidence, expected amount mismatch, duplicate refs, PO amount mismatch, no match |
| Save as Expense | Complete (MVP): `POST /ai/documents/create-expense` + AI UI **Create draft expense** after Analyze |
| Save as Purchase Invoice (PO-matched) | Complete (MVP): `POST /ai/documents/create-purchase-invoice` + AI UI **Create draft purchase invoice** when Analyze returns a PO match; copies PO lines (no line-item OCR) |

Module OCR (`/expenses/{id}/ocr-suggest`, `/purchasing/invoices/{id}/ocr-suggest`) remains for in-context apply flows.

## Endpoints

| Method | Path |
|--------|------|
| POST | `/api/v1/ai/documents/analyze` — multipart `file` + form `document_type` (default `auto`) + optional `expected_amount` (`ai:write`) |
| POST | `/api/v1/ai/documents/create-expense` — JSON `{ amount, payee?, description?, reference?, category_id?, expense_date?, payment_method? }` (`expenses:write`) |
| POST | `/api/v1/ai/documents/create-purchase-invoice` — JSON `{ purchase_order_id, supplier_id?, supplier_invoice_number?, notes?, invoice_date?, is_reverse_charge? }` (`purchasing:write`) |

Analyze audits via `ai_queries` (`endpoint=documents_analyze`). Create-expense audits `documents_create_expense`. Create-purchase-invoice audits `documents_create_purchase_invoice`.

## Honesty

Not EasyOCR/NLP ML. Line-item OCR and auto-create of POs remain Incomplete. Standalone PI from OCR without a PO match is Incomplete. Draft expense / draft PI require an explicit button/API call after human review.
