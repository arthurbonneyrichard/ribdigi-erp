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

## AI Security Monitor (BR-21.10)

Rule-based detectors (no LLM):

| Kind | Signal |
|------|--------|
| `rapid_failed_logins` | ≥3 `login_failed` audits in 15 minutes |
| `account_locked` | User `locked_until` in the future |
| `unusual_hour_login` | Successful login 00:00–04:59 UTC with prior baseline |
| `new_ip_login` | Login IP not seen on prior `auth_sessions` |
| `http_write_burst` | ≥40 `http_write` audits in 10 minutes |
| `suspicious_mutation_burst` | ≥5 cancel/restore/delete actions in 10 minutes |
| `ai_query_burst` | ≥20 AI queries in 10 minutes |

**APIs:** `GET /ai/security/alerts` (`?scan=true`), `POST /ai/security/scan`  
**Job:** Celery `scan_ai_security_alerts` (interval `CELERY_AI_SECURITY_INTERVAL_MINUTES`)  
**Notify:** in-app `category=security` when `risk_score >= AI_SECURITY_ALERT_THRESHOLD` (default 60)

Alerts are tenant-scoped (`ai_security_alerts`); fingerprints dedupe repeats.
