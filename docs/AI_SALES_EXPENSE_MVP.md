# AI Sales & Expense Analysis — rule-based MVP (BR-21.5 / BR-21.6)

## Scope

Heuristic analytics from tenant sales invoices, POS transactions, and approved expenses. **No LLM.**

### BR-21.5 Sales

| Criterion | Status |
|-----------|--------|
| Sales trend forecasting | Complete (MVP): monthly series + ratio next-month forecast |
| Customer RFM segmentation | Complete (MVP): quintile R/F/M + named segments |
| Product affinity | Complete (MVP): co-purchase pair counts |
| Peak hour/day | Complete (MVP): histograms from invoice/POS timestamps |

### BR-21.6 Expenses

| Criterion | Status |
|-----------|--------|
| Expense categorization from receipt OCR | Partial/Complete (MVP): keyword → category suggest on OCR; human PATCH required |
| Budget variance alerts | Complete (MVP): scaled monthly `budget_amount` vs spend |
| Unusual expense patterns | Complete (MVP): 2σ / 3× median + duplicate payee/amount/day |
| Cost optimization suggestions | Complete (MVP): rule strings from alerts |

## Endpoints

| Method | Path |
|--------|------|
| GET | `/api/v1/ai/sales/analysis?from_date=&to_date=` |
| GET | `/api/v1/ai/expenses/analysis?from_date=&to_date=` |

Default window: last 90 days.

## Honesty

Not Prophet/ML clustering. OCR category is keyword suggest only. Full NLP report generation remains Incomplete (BR-21.7).
