# AI Document Assistant — rule-based OCR MVP (BR-21.8)

## Scope

Unified `POST /ai/documents/analyze` over the shared `expense_ocr` engine (PDF text + Tesseract images). **No LLM.** Suggest-only — does not create expenses, invoices, or POs.

| AC | Status |
|----|--------|
| OCR extraction from invoices, receipts, purchase orders | Complete (MVP): same field parser; `document_type` receipt/invoice/purchase_order/auto |
| Auto-match extracted data to system records | Complete (MVP): party name similarity + PO number substring match; receipt category keywords |
| Data validation and discrepancy flagging | Complete (MVP): missing fields, low confidence, expected amount mismatch, duplicate refs, PO amount mismatch, no match |

Module OCR (`/expenses/{id}/ocr-suggest`, `/purchasing/invoices/{id}/ocr-suggest`) remains for in-context apply flows.

## Endpoint

| Method | Path |
|--------|------|
| POST | `/api/v1/ai/documents/analyze` — multipart `file` + form `document_type` (default `auto`) + optional `expected_amount` |

Requires `ai:write`. Audits via `ai_queries` (`endpoint=documents_analyze`).

## Honesty

Not EasyOCR/NLP ML. Line-item OCR and auto-create of business records remain Incomplete. Human confirmation required before applying fields.
