# AI Business Assistant — secure packaging (MVP)

## Scope

This pack closes the **provider configured securely**, **tenant-safe access packaging**, and **audit / prompt protections** launch gates without requiring a live LLM API key.

| Capability | Status |
|------------|--------|
| Fail-closed `POST /ai/chat` without provider | Complete |
| Optional `AI_ENABLED` + `AI_PROVIDER` + `AI_API_KEY` | Complete |
| Production rejects weak/missing key and `mock` provider | Complete |
| Prompt length limit + injection deny-list | Complete |
| Tenant-scoped `ai_queries` + `audit_logs` (`module=ai`) | Complete |
| Rule-based `GET /ai/insights` (no LLM) | Complete (Partial vs full BR-21) |
| Live OpenAI / other LLM chat client | **Incomplete** (503 `provider_pending` when key set) |
| Forecast / NL reports / document AI / customer AI | **Incomplete** |

## Env

See `.env.example`:

```
AI_ENABLED=false
AI_PROVIDER=none
AI_API_KEY=
AI_MAX_MESSAGE_CHARS=16000
```

Approved production provider: `openai` only. `mock` is for non-production tests.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/ai/status` | Packaging status; never returns secrets |
| GET | `/api/v1/ai/queries` | Tenant-scoped query log (hashed/redacted prompts) |
| POST | `/api/v1/ai/chat` | Sanitize → audit → 503/400/mock |
| GET | `/api/v1/ai/insights` | Dashboard rule notes + audit |

## Honesty

Do **not** mark BR-21 chat or AI functions complete until an approved provider client is wired and acceptance criteria in the BRD are verified end-to-end with real tenant data.
