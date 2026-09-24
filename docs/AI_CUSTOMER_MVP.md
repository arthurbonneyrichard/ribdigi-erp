# AI Customer Assistant — rule-based MVP (BR-21.9)

## Scope

Customer intelligence from RFM (shared with sales analysis) plus Party credit balances. **No LLM.**

| AC | Status |
|----|--------|
| Customer churn risk scoring | Complete (segment + recency heuristic) |
| Best customer identification | Complete (champions/loyal / high RFM) |
| Personalized promotion suggestions | Complete (segment copy + affinity SKUs) |

Also: constrained natural-language intents (`balance`, `churn`, `best`, `promo`, `overview`) via `query` when a `customer_id` is supplied.

## Endpoint

| Method | Path |
|--------|------|
| POST | `/api/v1/ai/customer/assist` — `{customer_id?, query?}` |

Requires `ai:read`. Audits via `ai_queries` (`endpoint=customer_assist`) + standard `module=ai` patterns.

## Honesty

Not a conversational CRM bot. Churn scores are rule-based heuristics, not predictive ML. True LLM-assisted customer chat remains Incomplete (`OPENAI_API_KEY` / provider gate).
