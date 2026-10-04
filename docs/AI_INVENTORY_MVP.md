# AI Inventory Predictions — rule-based MVP (BR-21.3 / BR-21.4)

## Scope

Velocity-based forecasts from tenant sales invoices + POS transactions. **No LLM / Prophet.**

| BR | Capability | Status |
|----|------------|--------|
| 21.3 | Demand 7/30/90 | Complete (MVP): `velocity × horizon` |
| 21.3 | Optimal reorder qty | Complete (MVP): `velocity × (lead + cover) − stock` (+ reorder_qty) |
| 21.3 | Seasonality | Partial: two-window rising/falling/stable ratio |
| 21.3 | Dead stock | Complete (MVP): stock > 0 and no sales in 90 days |
| 21.4 | Stockout 7–14 days ahead | Complete (MVP): `days_to_stockout ≤ days_ahead` |
| 21.4 | Velocity / lead / confidence | Complete (MVP heuristic) |
| 21.4 | Auto purchase suggestions | Complete (MVP): draft PRs via prediction → requests |

## Endpoints

| Method | Path |
|--------|------|
| GET | `/api/v1/ai/inventory/predictions` |
| GET | `/api/v1/ai/inventory/low-stock-prediction?days_ahead=14` |
| POST | `/api/v1/ai/inventory/low-stock-prediction/requests` |

`POST` body optional: `{ "lines": [...], "days_ahead": 14, "min_confidence": 0 }`.  
If `lines` omitted, runs prediction then creates draft PRs (requires `purchasing:write`).

**UI:** `/ai` — **Inventory predictions** + **Create draft PR(s)** (uses loaded lines when available).

## Env

```
AI_INVENTORY_LOOKBACK_DAYS=28
AI_INVENTORY_DEFAULT_LEAD_DAYS=7
AI_INVENTORY_COVER_DAYS=14
```

## Honesty

Full seasonal models, supplier-specific lead times, and ML demand forecasting remain post-MVP. Chat/LLM AI functions remain Incomplete.
