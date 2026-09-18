# AGENTS.md — RIBDIGI BUSINESS ERP agent guidance

## Product hierarchy (permanent)

```text
RIBDIGI HOUSE (Platform Owner)
      ↓
Subscription Plan / Tenant.max_* entitlements
      ↓
Tenant (SaaS customer account)
      ↓
Company (operating business)
      ↓
Store / Branch / Warehouse
      ↓
Users + RBAC
```

## Subscription-Based Multi-Store Architecture

RIBDIGI HOUSE controls the maximum subscription entitlement for a Tenant
(`Tenant.max_stores`, optional `Tenant.max_stores_override`, synced from
`PLAN_CATALOG.soft_limits.stores` when a plan changes and no override is set).

Tenant Admin controls how available Store capacity is allocated to Companies
(`Company.store_limit`) via tenant-workspace APIs. Allocations must never exceed
the Tenant entitlement.

Companies can only create (or reactivate) Stores within their allocated allowance
**and** while the Tenant still has remaining entitlement. Enforcement lives in
`backend/app/store_entitlements.py` and is called from `stores.create_store` /
store activation — never frontend-only.

### Permanent rules

1. **Backend enforcement is mandatory.** Disabling a UI button is not sufficient.
2. **Never delete business data** because a subscription is downgraded. Preserve
   Stores, sales, inventory, payments, accounting, reports, and audit history.
   While over entitlement, block new creates / reactivation; surface
   `over_entitlement` on the tenant dashboard.
3. **Tenant isolation** remains shared-schema + `tenant_id` (ADR-001). Stores
   belong to one Company and therefore one Tenant.
4. **Unlimited** uses integer `-1` (enterprise catalog `None` maps to `-1`).
5. **Live billing / checkout Completes remain deferred** (ADR-002). Caps are real
   gates on tenant columns, not fabricated MRR.
6. **User↔store membership** remains deferred (ADR-005). Do not invent parallel
   membership tables unless that ADR is intentionally opened.
7. Reuse `stores` RBAC module actions (`read`/`write`) and tenant-admin roles for
   allocation; do not invent dotted permission strings unless the RBAC system is
   extended project-wide.

### Key modules

| Concern | Module |
|---------|--------|
| Entitlement math + locks | `backend/app/store_entitlements.py` |
| Store create/activate | `backend/app/stores.py` |
| Tenant dashboard payload | `backend/app/companies.py` |
| Plan catalog soft limits | `backend/app/tenants.py` (`PLAN_CATALOG`) |
| Platform override API | `PATCH /api/v1/platform/tenants/{id}/store-entitlement` |
| Tenant allocation API | `PATCH /api/v1/companies/{id}/store-limit` |

### Do not claim Completes

Offline Complete, paid billing Completes, ADR-005 membership Completes, go-live,
and attestation Completes remain **MISSING** unless separately delivered with
evidence.

## Smart Business Intelligence (Layer 1)

Deterministic, offline-capable insights engine. **No OpenAI / Gemini / Anthropic /
external LLM.** Calculations use Ribdigi ERP DB data only (sales, inventory,
purchases, expenses, credit, expiry, etc.) with tenant/company/store RBAC.

| Concern | Module |
|---------|--------|
| Orchestrator | `backend/app/bi_service.py` (`BusinessIntelligenceService`) |
| Metrics | `backend/app/bi_metrics.py` (`BusinessMetricsService`) |
| Rules | `backend/app/bi_rules.py` (`InsightRulesService`) |
| Priority | `backend/app/bi_priority.py` |
| Recommendations | `backend/app/bi_recommendations.py` |
| Defaults / formulas | `backend/app/bi_defaults.py` |
| API | `backend/app/bi_api.py` → `/api/v1/business-insights/*` |
| UI | `frontend/app/business-insights/page.tsx` |
| Migration | `backend/alembic/versions/20260816_0105_business_insights.py` |
| Tests | `backend/tests/test_business_intelligence.py` |

RBAC module: `business_insights` (`read` / `write`). Financial/credit sections
also require existing `accounting`/`reports`/`credit` permissions. Layer 2
generative AI adapters are out of scope; Layer 1 must remain fully usable alone.

`POST /api/v1/business-insights/reorder-requests` (requires `purchasing:write` +
`business_insights:read`) converts Smart Reorder Recommendation lines into draft
purchase requests, grouped by last PO supplier or an explicit `supplier_id`.
Products with no supplier, zero qty, or an existing open PR are skipped. The
existing `generate_ai_insights` job also persists Layer 1 CRITICAL/WARNING rows
per company (duplicate unread notifications are suppressed). The Insights UI
exposes history (acknowledge/dismiss), company threshold settings, and formula
docs. Recommended reorder qty subtracts remaining qty on sent / partially
received purchase orders.
