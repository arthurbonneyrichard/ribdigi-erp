# AI Report Generator — constrained NL MVP (BR-21.7)

## Scope

Maps natural-language prompts to existing `EXPORTABLE` report types and reuses `report_export` (csv/pdf/xlsx). **No LLM.**

| AC | Status |
|----|--------|
| Generate from text prompts | Complete (MVP keyword/period parser) |
| Export generated reports | Complete (`POST /ai/reports/export`) |
| Save templates for reuse | Complete (`ai_report_templates` CRUD) |

## Endpoints

| Method | Path |
|--------|------|
| POST | `/api/v1/ai/reports/generate` — `{prompt}` or `{report_type,period,format}` or `{template_id}` |
| POST | `/api/v1/ai/reports/export` — same body → file download |
| GET/POST/DELETE | `/api/v1/ai/reports/templates` |

Example prompts: `monthly sales for Q2 2026`, `low stock`, `expense summary last month as pdf`.

## Honesty

Not open-domain NL. Unmapped prompts → 422 with supported types. True LLM report authoring remains Incomplete.
