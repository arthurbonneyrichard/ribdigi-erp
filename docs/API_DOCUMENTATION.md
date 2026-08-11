# API Documentation

## RIBDIGI BUSINESS ERP — MVP API Reference

**Version:** 1.0.0  
**Base URL:** `https://api.ribdigi.com/v1`  
**Protocol:** REST / JSON  
**Authentication:** JWT + OAuth2  
**Backend:** FastAPI  
**Last Updated:** August 2026

---

## Table of Contents

1. [API Standards](#1-api-standards)
2. [Authentication](#2-authentication)
3. [Tenant Management](#3-tenant-management)
4. [User Management](#4-user-management)
5. [Inventory & Products](#5-inventory--products)
6. [Purchasing & Suppliers](#6-purchasing--suppliers)
7. [Sales & Customers](#7-sales--customers)
8. [Point of Sale (POS)](#8-point-of-sale-pos)
9. [Expense Management](#9-expense-management)
10. [Accounting](#10-accounting)
11. [Credit Management](#11-credit-management)
12. [Tax Management](#12-tax-management)
13. [Multi-Store Management](#13-multi-store-management)
14. [Reports](#14-reports)
15. [Notifications](#15-notifications)
16. [AI Business Assistant](#16-ai-business-assistant)
17. [Webhooks](#17-webhooks)
18. [Caching](#18-caching-stage-6-p2)
19. [Rate Limits](#19-rate-limits)
20. [Error Codes](#20-error-codes)

---

## 1. API Standards

Stage 19 A1 proves live standards under `/api/v1` — `test_api_standards_a1.py` (BR-18.6). Stage 19 D1 fidelity sync: `docs/STAGE_19_FIDELITY.md` (`test_stage19_fidelity_d1.py`) — BR-18–20 + LAUNCH §5. Stage 20 D1 AI fidelity sync: `docs/STAGE_20_FIDELITY.md` (`test_stage20_fidelity_d1.py`) — BR-21. Stage 21 D1/H21x tenant/org/dashboard fidelity + exit: `docs/STAGE_21_FIDELITY.md` (`test_stage21_fidelity_d1.py`), `docs/STAGE_21_EXIT_CRITERIA.md`, ADR-048 (`test_stage21_exit_h21x.py`) — BR-1–4. Stage 22 D1/H22x expenses/ledger/credit/tax fidelity + exit: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`), `docs/STAGE_22_EXIT_CRITERIA.md`, ADR-050 (`test_stage22_exit_h22x.py`) — BR-9–12. Stage 23 D1/H23x reports-dimension & MVP-gate fidelity + exit: `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`), `docs/STAGE_23_EXIT_CRITERIA.md`, ADR-052 (`test_stage23_exit_h23x.py`) — BR-14 (historical open ADR-051). Stage 24 D1/H24x commerce & ops gate fidelity + exit: `docs/STAGE_24_FIDELITY.md` (`test_stage24_fidelity_d1.py`; N1 `test_document_numbering_n1.py`; G1 `test_commerce_gate_closure_g1.py`; O1 `test_ops_ai_gate_closure_o1.py`), `docs/STAGE_24_EXIT_CRITERIA.md`, ADR-054 (`test_stage24_exit_h24x.py`) — BR-20.4 (historical open ADR-053 / `docs/STAGE_24_PLAN.md`). Stage 25 D1/H25x actuals → AI → insights fidelity + exit: `docs/STAGE_25_FIDELITY.md` (`test_stage25_fidelity_d1.py`; P1 `test_ai_purchases_analysis_p1.py`; X1 `test_ai_cross_domain_x1.py`; B1 `test_ai_business_insights_b1.py`; U1 `test_ai_ui_fidelity_u1.py`), `docs/STAGE_25_EXIT_CRITERIA.md`, ADR-056 (`test_stage25_exit_h25x.py`) — BR-21.2 / 21.11 / 21.12 (historical open ADR-055 / `docs/STAGE_25_PLAN.md`). Stage 26 closed (ADR-058): Production Platform & Ops Fidelity — `docs/STAGE_26_PLAN.md`, `docs/STAGE_26_EXIT_CRITERIA.md` (historical open ADR-057; `test_stage26_open.py`). Stage 26 M1 monitoring scrape/alerts/log-ship: `ops/prometheus/`, `ops/logging/`, `docs/OPS_MONITORING_MVP.md` (`test_ops_monitoring_m1.py`). Stage 26 W1 WAL/PITR + S3 offsite strategy: `docs/DR_WAL_PITR_RUNBOOK.md`, `ops/postgres/`, `ops/backup/` (`test_wal_pitr_w1.py`). Stage 26 K1 Kubernetes/Helm deploy fidelity: `helm/ribdigi/`, `k8s/`, `docs/K8S_DEPLOY_MVP.md` (`test_k8s_deploy_k1.py`). Stage 26 C1 load capacity evidence: `docs/LOAD_CAPACITY_MVP.md`, `backend/loadtest/` (`test_load_capacity_c1.py`). Stage 26 D1 production platform fidelity: `docs/STAGE_26_FIDELITY.md` (`test_stage26_fidelity_d1.py`) — BR-16 / NFR ops evidence lock; public API contracts unchanged. Stage 26 H26x exit + freeze: `docs/STAGE_26_EXIT_CRITERIA.md`, ADR-058 (`test_stage26_exit_h26x.py`). Stage 27 closed (ADR-060): Commercial MVP Release Fidelity — `docs/STAGE_27_PLAN.md`, `docs/STAGE_27_EXIT_CRITERIA.md` (historical open ADR-059; `test_stage27_open.py`) Stage 27 B1 offsite upload (`test_backup_offsite_b1.py`); P1 PgBouncer (`docs/PGBOUNCER_MVP.md`, `test_pgbouncer_p1.py`); S1 security scan (`docs/SECURITY_SCAN_MVP.md`, `test_security_scan_s1.py`); L1 launch cert (`docs/LAUNCH_CERT_MVP.md`, `test_launch_cert_l1.py`). Stage 27 D1 release fidelity: `docs/STAGE_27_FIDELITY.md` (`test_stage27_fidelity_d1.py`). Stage 27 H27x exit + freeze: `docs/STAGE_27_EXIT_CRITERIA.md`, ADR-060 (`test_stage27_exit_h27x.py`). Stage 28 open (ADR-061): Staging Certification Fidelity — `docs/STAGE_28_PLAN.md` (`test_stage28_open.py`). Stage 28 R1 PITR drill pack: `docs/PITR_DRILL_PACK_MVP.md` (`test_pitr_drill_pack_r1.py`). Stage 28 G1 staging GHA: `docs/STAGING_GHA_MVP.md` (`test_staging_gha_g1.py`). Stage 28 A1 Grafana pack: `docs/GRAFANA_PACK_MVP.md` (`test_grafana_pack_a1.py`). Stage 28 C1 1000-VU cert pack: `docs/LOAD_CERT_PACK_MVP.md` (`test_load_cert_pack_c1.py`). Stage 28 D1 staging certification fidelity: `docs/STAGE_28_FIDELITY.md` (`test_stage28_fidelity_d1.py`). Stage 28 H28x exit + freeze: `docs/STAGE_28_EXIT_CRITERIA.md`, ADR-062 (`test_stage28_exit_h28x.py`). Stage 29 open (ADR-063): Operator Hardening & Production Cutover Fidelity — `docs/STAGE_29_PLAN.md` (`test_stage29_open.py`). Stage 29 V1 pen-test pack: `docs/PENTEST_PACK_MVP.md` (`test_pentest_pack_v1.py`). Stage 29 B2 PgBouncer soak pack: `docs/PGBOUNCER_SOAK_PACK_MVP.md` (`test_pgbouncer_soak_b2.py`). Stage 29 T1 TLS ingress pack: `docs/TLS_INGRESS_PACK_MVP.md` (`test_tls_ingress_t1.py`). Stage 29 X1 production cutover pack: `docs/CUTOVER_PACK_MVP.md` (`test_cutover_pack_x1.py`). Stage 29 D1 operator hardening & cutover fidelity: `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`) — V1–X1 evidence lock; public API contracts unchanged. Stage 29 H29x exit + freeze: `docs/STAGE_29_EXIT_CRITERIA.md`, ADR-064 (`test_stage29_exit_h29x.py`). Stage 30 open (ADR-065): Go-Live Support Fidelity — `docs/STAGE_30_PLAN.md` (`test_stage30_open.py`). Stage 30 L1 evidence ledger: `docs/EVIDENCE_LEDGER_MVP.md` (`test_evidence_ledger_l1.py`). Stage 30 I1 incident pack: `docs/INCIDENT_PACK_MVP.md` (`test_incident_pack_i1.py`). Stage 30 S1 support/Admin fidelity: `docs/SUPPORT_RUNBOOK_MVP.md` (`test_support_runbook_s1.py`). Stage 30 A1 attestation matrix: `docs/ATTESTATION_PACK_MVP.md` (`test_attestation_pack_a1.py`). Stage 30 D1 go-live support fidelity: `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`) — L1–A1 evidence lock; public API contracts unchanged. Stage 30 H30x exit + freeze: `docs/STAGE_30_EXIT_CRITERIA.md`, ADR-066 (`test_stage30_exit_h30x.py`). Stage 31 open (ADR-067): Commercial MVP Closeout Fidelity — `docs/STAGE_31_PLAN.md` (`test_stage31_open.py`). Stage 31 G1 MVP gate honesty matrix: `docs/MVP_GATE_MATRIX_MVP.md` (`test_mvp_gate_matrix_g1.py`). Stage 31 R1 deferred ADR register: `docs/DEFERRED_ADR_REGISTER_MVP.md` (`test_deferred_adr_register_r1.py`). Stage 31 O1 operator Remaining register: `docs/OPERATOR_REMAINING_MVP.md` (`test_operator_remaining_o1.py`). Stage 31 C1 commercial MVP declaration: `docs/MVP_DECLARATION_MVP.md` (`test_mvp_declaration_c1.py`). Stage 31 D1 closeout fidelity: `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`) — G1–C1 evidence lock; public API contracts unchanged. Stage 31 H31x exit + freeze: `docs/STAGE_31_EXIT_CRITERIA.md`, ADR-068 (`test_stage31_exit_h31x.py`). Stage 32 open (ADR-069): Commercial MVP Handoff Fidelity — `docs/STAGE_32_PLAN.md` (`test_stage32_open.py`). Stage 32 A1 MVP acceptance archive: `docs/ACCEPTANCE_ARCHIVE_MVP.md` (`test_acceptance_archive_a1.py`). Stage 32 H1 operator handoff: `docs/OPERATOR_HANDOFF_MVP.md` (`test_operator_handoff_h1.py`). Stage 32 N1 commercial release notes: `docs/RELEASE_NOTES_MVP.md` (`test_release_notes_n1.py`). Stage 32 B1 post-MVP backlog: `docs/POST_MVP_BACKLOG_MVP.md` (`test_post_mvp_backlog_b1.py`). Stage 32 D1 handoff fidelity: `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`) — A1–B1 evidence lock; public API contracts unchanged. Stage 32 H32x exit + freeze: `docs/STAGE_32_EXIT_CRITERIA.md`, ADR-070 (`test_stage32_exit_h32x.py`). Stage 33 open (ADR-071): Commercial MVP Continuity Fidelity — `docs/STAGE_33_PLAN.md` (`test_stage33_open.py`). Stage 33 K1 residual risk register: `docs/RESIDUAL_RISK_MVP.md` (`test_residual_risk_k1.py`). Stage 33 C1 compliance readiness: `docs/COMPLIANCE_READINESS_MVP.md` (`test_compliance_readiness_c1.py`). Stage 33 F1 first-tenant onboarding: `docs/FIRST_TENANT_ONBOARDING_MVP.md` (`test_first_tenant_onboarding_f1.py`). Stage 33 T1 knowledge transfer: `docs/KNOWLEDGE_TRANSFER_MVP.md` (`test_knowledge_transfer_t1.py`).

### 1.1 Request Format
- All requests and responses use **JSON**.
- Content-Type header must be: `application/json`
- Date format: **ISO 8601** (`YYYY-MM-DDTHH:MM:SSZ`)
- Currency values are sent as **decimal strings** or numbers; prefer decimal strings for money fields where schemas require them.

### 1.2 Response Envelope
Successful handlers return the `env()` envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}
```

HTTP errors typically use FastAPI’s `{"detail": "..."}` (string) or structured `{"detail": {"code": "...", "message": "..."}}` for gated auth cases. Rate-limit `429` responses use an envelope with `success: false`, `detail: "RATE_LIMIT_EXCEEDED"`, and `Retry-After` / `X-RateLimit-*` headers. Correlation for ops logs uses `X-Request-ID` (Stage 18 L1) — not a field inside `env()`.

### 1.3 Pagination
Most catalog/party list endpoints return the full array in `data` (MVP-sized tenants). High-volume / filtered lists support an optional **`limit`** query parameter (examples: `GET /audit-logs?limit=200`, AI history, some reports). Cursor/`page` pagination is **deferred** post-MVP.

### 1.4 Versioning & OpenAPI
- All routes are mounted under **`/api/v1`**.
- OpenAPI is auto-generated by FastAPI: `GET /openapi.json`, interactive `GET /docs` / `GET /redoc` when `APP_ENV` is not `production` (disabled in production — Stage 5 S1).
- Webhooks: HMAC-signed outbound subscriptions under `/api/v1/webhooks` (Stage 6 W1; Stage 19 A1 regression).

---

### 1.5 HTTP Methods
| Method | Usage |
|--------|-------|
| `GET` | Retrieve resources |
| `POST` | Create resources |
| `PUT` | Full update (rarely used; prefer PATCH) |
| `PATCH` | Partial update |
| `DELETE` | Soft-delete / remove resources where supported |

---

## 2. Authentication

RIBDIGI ERP uses **JWT (JSON Web Tokens)** with password-grant login (OAuth2 resource-owner style). Stage 19 K1 proves `POST /auth/login`, `POST /auth/refresh` (rotation), API keys, and rate-limit headers (`test_auth_api_fidelity_k1.py`).

### 2.1 Login
**Endpoint:** `POST /auth/login`

**Request:**
```json
{
  "email": "admin@company.com",
  "password": "SecurePass123!",
  "tenant_id": "tenant_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "id": "usr_001",
      "email": "admin@company.com",
      "role": "company_admin",
      "tenant_id": "tenant_abc123"
    }
  }
}
```

### 2.2 Refresh Token
**Endpoint:** `POST /auth/refresh`

Rotates the session: validates the refresh token hash against `auth_sessions`, revokes the old session, and issues a new access + refresh pair. Reusing the old refresh token returns `401`. (Stage 19 K1)

**Request:**
```json
{
  "refresh_token": "…"
}
```

### 2.3 Logout
**Endpoint:** `POST /auth/logout`

**Headers:** `Authorization: Bearer <access_token>`

### 2.4 Password Reset
**Endpoint:** `POST /auth/password-reset-request`

**Request:**
```json
{
  "email": "admin@company.com"
}
```

**Endpoint:** `POST /auth/password-reset`

**Request:**
```json
{
  "token": "reset_token_from_email",
  "new_password": "NewSecurePass456!"
}
```

### 2.5 Two-Factor Authentication (Optional)
**Endpoint:** `POST /auth/2fa/enable`

**Endpoint:** `POST /auth/2fa/verify`

**Request:**
```json
{
  "code": "123456"
}
```

### 2.6 Session Management
**Endpoint:** `GET /auth/sessions`

**Endpoint:** `DELETE /auth/sessions/{session_id}`

### 2.7 API Keys (Stage 6 K1 / Stage 7 K2 / BR-18.1)
Tenant admins manage integration keys. The raw secret is returned **once** on create.

| Method | Endpoint | Notes |
|--------|----------|-------|
| `GET` | `/api-keys` | List keys (prefix + metadata; no secret). Includes `request_count`, `last_used_at`. |
| `POST` | `/api-keys` | Create (`name`, optional `permissions`, `expires_at`) |
| `GET` | `/api-keys/{id}` | Get metadata |
| `GET` | `/api-keys/{id}/usage` | Stage 7 K2 — usage stats (`days` query, default 30, max 90): `total_requests`, `period_requests`, zero-filled `series[{date,requests}]` |
| `DELETE` | `/api-keys/{id}` | Revoke |

**Authenticate requests** with either:
- Header `X-API-Key: rdk_…`
- Header `Authorization: Bearer rdk_…`

Optional `X-Tenant-ID` must match the key’s tenant when present. Permissions are a module→actions map (defaults: inventory/sales/purchasing/customers/reports `read`). Each successful authentication increments lifetime and daily request counters (stored in `api_key_usage_daily`).

---

## 3. Tenant Management

### 3.1 Register Company (Tenant)
**Endpoint:** `POST /tenants`

**Request:**
```json
{
  "company_name": "Acme Retail Ltd",
  "industry": "retail",
  "currency": "USD",
  "timezone": "America/New_York",
  "fiscal_year_start": "2026-01-01",
  "admin_email": "admin@acme.com",
  "admin_password": "SecurePass123!",
  "subscription_plan": "trial"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "tenant_id": "tenant_abc123",
    "company_name": "Acme Retail Ltd",
    "status": "trial",
    "api_key": "rk_live_...",
    "created_at": "2026-08-07T13:51:00Z"
  }
}
```

### 3.2 Get Tenant Profile
**Endpoint:** `GET /tenants/{tenant_id}`

**Current tenant (Stage 21 T1/C1):** `GET /tenants/me` / `PATCH /tenants/me` — company admin / super_admin profile (legal name, registration/tax IDs, billing/shipping/warehouse addresses, contact person, currency, logo via `/tenants/me/logo`). `document_numbering` + `document_numbering_preview` cover sales/purchase series including order, return, credit note, debit note (Stage 24 N1: `test_document_numbering_n1.py`). Evidence: `test_tenant_lifecycle_t1.py`, `test_company_currency_tax_c1.py`.

### 3.3 Update Tenant Profile
**Endpoint:** `PATCH /tenants/{tenant_id}`

**Request:**
```json
{
  "company_name": "Acme Retail Ltd",
  "logo_url": "https://cdn.ribdigi.com/logos/acme.png",
  "settings": {
    "currency": "USD",
    "timezone": "America/New_York",
    "date_format": "MM/DD/YYYY",
    "number_format": "#,##0.00"
  }
}
```

### 3.4 Tenant Status Management
**Endpoint:** `PATCH /tenants/{tenant_id}/status`

**Request:**
```json
{
  "status": "active"
}
```

**Allowed statuses:** `trial`, `active`, `suspended`

### 3.4a Onboarding Checklist (Stage 6 N2)

Authenticated users can read progress; `company_admin` / `super_admin` may skip steps or dismiss the banner (≥80% progress).

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/onboarding/checklist` | Auto-detected steps + progress |
| `POST` | `/onboarding/checklist/steps/{step_id}/skip` | Admin |
| `POST` | `/onboarding/checklist/steps/{step_id}/unskip` | Admin |
| `POST` | `/onboarding/checklist/dismiss` | Admin; requires ≥80% |
| `POST` | `/onboarding/checklist/restore` | Admin |

Steps: `setup_company`, `add_products`, `create_supplier`, `stock_ready`, `first_sale`.

### 3.5 Company Setup
**Endpoint:** `POST /tenants/{tenant_id}/setup`

**Request:**
```json
{
  "branches": [
    {
      "name": "Main Branch",
      "address": "123 Main St",
      "phone": "+1-555-0100"
    }
  ],
  "warehouses": [
    {
      "name": "Central Warehouse",
      "location": "Warehouse District"
    }
  ],
  "departments": ["Sales", "Inventory", "Accounting"],
  "tax_config": {
    "vat_enabled": true,
    "default_tax_rate": 10.0
  }
}
```

---

## 4. User Management

### 4.1 Create User
**Endpoint:** `POST /users`

**Request:**
```json
{
  "email": "manager@acme.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "store_manager",
  "branch_id": "br_001",
  "store_id": "st_001",
  "phone": "+1-555-0199",
  "password": "TempPass123!"
}
```

### 4.2 List Users
**Endpoint:** `GET /users?role=store_manager&status=active`

### 4.3 Get User
**Endpoint:** `GET /users/{user_id}`

### 4.4 Update User
**Endpoint:** `PATCH /users/{user_id}`

### 4.5 Deactivate User (soft delete)
**Endpoint:** `DELETE /users/{user_id}`

Deactivates the user (`is_active=false`), revokes sessions, and audits `user_deactivated`. The user row is **not** removed (ADR-003). Reactivate with `PATCH /users/{user_id}` and `{"is_active": true}`.

There is no hard-delete endpoint and no `PATCH /users/{user_id}/status` shortcut.

### 4.6 Roles & Permissions

**List Roles:** `GET /roles`

**Get Role Permissions:** `GET /roles/{role_id}/permissions`

**Update Permissions:** `PUT /roles/{role_id}/permissions`

**Request:**
```json
{
  "module_permissions": ["inventory", "sales", "pos"],
  "menu_permissions": ["products", "stock_in", "stock_out"],
  "record_permissions": {
    "products": ["read", "write", "delete"],
    "sales": ["read", "write"]
  }
}
```

**Available Roles:**
- `super_admin`
- `company_admin`
- `store_manager`
- `sales_officer`
- `inventory_officer`
- `accountant`
- `cashier`

---

## 5. Inventory & Products

Stage 17 C1 proves catalog fidelity for BR-5.1 (categories tree, brands+logo, UoM conversion, variants, barcode generate, multi-image primary, batch/expiry via stock-in) — `test_catalog_fidelity_c1.py`; plan `docs/STAGE_17_PLAN.md`.

### 5.1 Product Categories
**List:** `GET /catalog/categories` (`?tree=true` for nested tree)  
**Create:** `POST /catalog/categories` — body `{ code, name, parent_id?, tax_rate_id? }`  
**Update:** `PATCH /catalog/categories/{category_id}` — may set/clear `tax_rate_id`  
**Delete:** `DELETE /catalog/categories/{category_id}` (soft deactivate)

Stage 10 T1: optional `tax_rate_id` on the category. Tax resolution for a product line is exempt → line override → product `tax_rate_id` → category rate (walks parents) → tenant default.

### 5.2 Brands
**List:** `GET /catalog/brands`  
**Create:** `POST /catalog/brands`  
**Update:** `PATCH /catalog/brands/{brand_id}`

### 5.3 Units
**List:** `GET /catalog/units`  
**Create:** `POST /catalog/units`

### 5.4 Products
**List:** `GET /products`  
**Create:** `POST /products`  
**Get:** `GET /products/{product_id}`  
**Update:** `PATCH /products/{product_id}` (set `is_active=false` to soft-deactivate)  
**Import:** `GET /products/import/template`, `POST /products/import?dry_run=true|false`  
**Warehouse stock:** `GET /products/{product_id}/warehouse-stock`  
**Barcode lookup:** `GET /inventory/products/lookup?q=&barcode=`

Stage 19 P1 proves products/catalog CRUD + import + stock/barcode surfaces via JWT and X-API-Key reads — `test_products_customers_api_p1.py` (BR-18.2). Dedicated catalog CSV export deferred (list/report packaging covers export needs for MVP).

Stage 17 A1 domain audit (`module=inventory`): `product_create` (details.after snapshot); `product_update` / soft-delete `product_deactivate` with `before`/`after` field diffs; stock ops emit `stock_{movement_type}` with qty before/after. Evidence: `test_inventory_audit_a1.py`.

**Create Product Request:**
```json
{
  "name": "Organic Wheat Flour",
  "sku": "WF-ORG-5KG",
  "barcode": "8901234567890",
  "category_id": "cat_001",
  "brand_id": "brand_001",
  "unit_id": "unit_001",
  "variants": [
    {
      "name": "5kg Pack",
      "sku": "WF-ORG-5KG",
      "price": 12.99,
      "cost": 8.50,
      "barcode": "8901234567890"
    }
  ],
  "description": "Premium organic wheat flour",
  "images": ["https://cdn.ribdigi.com/products/wf1.jpg"],
  "track_inventory": true,
  "is_active": true
}
```

### 5.5 Stock Operations

Stage 17 S1 proves stock-in → warehouse qty + `stock_movements`, adjustment reason codes, and opening stock — `test_stock_ops_chain_s1.py`.

**Stock In:** `POST /inventory/stock-in` — body `{ product_id, quantity, warehouse_id?, notes?, variant_id?, batch_number?, manufacturing_date?, expiry_date? }`

**Stock Out:** `POST /inventory/stock-out` — same shape; optional `batch_id` (FEFO if omitted)

**Stock Adjustment:** `POST /inventory/adjust/{product_id}` — body `{ quantity` (signed delta), `reason` (`damage|theft|expiry|found|lost|other`), `notes?`, `warehouse_id?` }. Invalid reason → `400 INVALID_ADJUSTMENT_REASON`.

**Opening Stock:** `POST /inventory/opening-stock` — single or `items[]`; `mode=add|set`; writes `movement_type=opening_stock` / `reference_type=opening_stock`.

**Warehouse stock view:** `GET /products/{product_id}/warehouse-stock`

**Stock Transfer:** `POST /inventory/stock-transfers`

Stage 17 W1: inter-warehouse create → submit/ship → receive updates `WarehouseStock` and writes `transfer_out`/`transfer_in` movements (`reference_type=stock_transfer`). Per-product grid: `GET /products/{id}/warehouse-stock`. Insufficient source qty on ship → `409 INSUFFICIENT_WAREHOUSE_STOCK` (stays `requested`). Evidence: `test_warehouse_transfer_chain_w1.py`.

```json
{
  "from_warehouse_id": "wh_001",
  "to_warehouse_id": "wh_002",
  "submit": true,
  "notes": "Transfer to branch warehouse",
  "items": [{ "product_id": "prod_001", "quantity": 50 }]
}
```

**List:** `GET /inventory/stock-transfers` (filters: `status`, `store_id`, dates, `scope`, `limit`)  
**Submit / Ship / Receive / Cancel:** `POST /inventory/stock-transfers/{transfer_id}/submit|ship|receive|cancel`  
(No status PATCH — use action POSTs.)

**Update Transfer Status:** `PATCH /inventory/stock-transfers/{transfer_id}` — **deprecated / not implemented**; use action POSTs above.
### 5.6 Stock Count

Stage 17 S2 proves create → enter counted qty → complete (posts `adjustment` movements with `reference_type=stock_count`) → variance report export — `test_stock_count_chain_s2.py`.

**Create:** `POST /inventory/stock-counts` — `{ warehouse_id, notes?, product_ids? }` → `status=draft`  
**List:** `GET /inventory/stock-counts`  
**Get:** `GET /inventory/stock-counts/{count_id}` — includes items + line `variance`  
**Update counts:** `PATCH /inventory/stock-counts/{count_id}/items` — `{ items: [{ product_id, counted_qty, notes? }] }` (draft only)  
**Complete:** `POST /inventory/stock-counts/{count_id}/complete` — posts non-zero variances; `status=completed`  
**Cancel:** `POST /inventory/stock-counts/{count_id}/cancel` — draft only → `cancelled`  
**Variance report:** `GET /inventory/stock-counts/{count_id}/variance-report?format=csv|pdf|json` — requires `completed` (`409 COUNT_NOT_COMPLETED` otherwise)

### 5.7 Stock Movement History
**Endpoint:** `GET /inventory/movements?product_id=&warehouse_id=&movement_type=&from_date=&to_date=`  
**Report / export:** `GET /reports/inventory/movements` · export `report_type=inventory_movements` (CSV/PDF)

Stage 17 D1: movements are append-only (`quantity_before` / `quantity_after`, `created_by`); filters cover product, warehouse, type, dates; no delete API. Evidence: `test_stock_integrity_i5.py`, `docs/STAGE_17_FIDELITY.md`.

### 5.8 Low Stock Alerts
**Endpoint:** `GET /inventory/low-stock`  
**Reorder PO:** `POST /inventory/low-stock/reorder-po` (requires `purchasing:write`)

Stage 17 L1: traffic-light `stock_status` (`green`/`yellow`/`red`), `suggested_order_qty`, product + warehouse scopes; draft PO from suggestion. Warehouse thresholds via `PUT /stores/{store_id}/reorder-policy`. Evidence: `test_low_stock_reorder_l1.py`.

**Low-stock list response (`data` is an array):**
```json
{
  "success": true,
  "data": [
    {
      "id": "prod_001",
      "sku": "FLOUR-01",
      "name": "Organic Wheat Flour",
      "stock_qty": 5,
      "minimum_stock": 20,
      "reorder_level": 30,
      "stock_status": "red",
      "suggested_order_qty": 25,
      "scope": "product",
      "warehouse_id": null
    }
  ]
}
```

**Create draft reorder PO:**
```json
{
  "product_id": "prod_001",
  "supplier_id": "sup_001",
  "quantity": 25,
  "warehouse_id": null,
  "unit_price": null,
  "notes": null
}
```
Omitting `quantity` uses the product suggested order qty; omitting `unit_price` uses `cost_price`. Cross-tenant supplier → `404`.

### 5.9 Set Stock Levels
**Product:** `PATCH /products/{product_id}` with `minimum_stock` / `reorder_level`  
**Warehouse (store-linked):** `PUT /stores/{store_id}/reorder-policy`

```json
{
  "product_id": "prod_001",
  "minimum_stock": 20,
  "reorder_level": 30,
  "reorder_qty": 100
}
```

---

## 6. Purchasing

Stage 19 S1 purchasing fidelity: `test_sales_purchases_api_s1.py` (BR-18.5).
 & Suppliers

### 6.1 Suppliers
**List:** `GET /suppliers`  
**Create:** `POST /suppliers`  
**Get:** `GET /suppliers/{supplier_id}`  
**Update:** `PATCH /suppliers/{supplier_id}`  
**Delete:** `DELETE /suppliers/{supplier_id}`

**Create Supplier:**
```json
{
  "name": "Global Supplies Inc",
  "contact_person": "Jane Smith",
  "email": "jane@globalsupplies.com",
  "phone": "+1-555-0200",
  "address": "456 Supply Ave, Industrial City",
  "tax_id": "TAX123456",
  "payment_terms": "net_30",
  "opening_balance": 0.00,
  "status": "active"
}
```

### 6.2 Purchase Request
**List:** `GET /purchasing/requests`  
**Create:** `POST /purchasing/requests`  
**Get:** `GET /purchasing/requests/{request_id}`  
**Approve:** `POST /purchasing/requests/{request_id}/approve`  
**Reject:** `POST /purchasing/requests/{request_id}/reject`

**Create Request:**
```json
{
  "request_date": "2026-08-07",
  "required_date": "2026-08-14",
  "warehouse_id": "wh_001",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 100,
      "notes": "Urgent restock"
    }
  ],
  "notes": "Monthly inventory replenishment"
}
```

### 6.3 Purchase Order
**List:** `GET /purchasing/orders`  
**Create:** `POST /purchasing/orders`  
**Get:** `GET /purchasing/orders/{order_id}`  
**Send:** `POST /purchasing/orders/{order_id}/send`  
**Cancel:** `POST /purchasing/orders/{order_id}/cancel`

**Create PO:**
```json
{
  "supplier_id": "sup_001",
  "order_date": "2026-08-07",
  "expected_delivery": "2026-08-14",
  "warehouse_id": "wh_001",
  "reference": "PO-2026-001",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 100,
      "unit_price": 8.50,
      "tax_rate": 10.0,
      "discount": 0.0
    }
  ],
  "notes": "Standard monthly order"
}
```

**Status Flow:** `draft` → `sent` → `partially_received` → `received` → `cancelled`

### 6.4 Goods Received Note (GRN)
**List:** `GET /purchasing/grn`  
**Create:** `POST /purchasing/grn`  
**Get:** `GET /purchasing/grn/{grn_id}`

**Create GRN** (posts immediately — stock ↑, supplier balance ↑, Dr 1200 / Cr 2000):
```json
{
  "purchase_order_id": "po_001",
  "warehouse_id": "wh_001",
  "items": [
    {
      "po_item_id": "poi_001",
      "received_qty": 100,
      "accepted_qty": 98,
      "rejected_qty": 2,
      "rejection_reason": "Damaged packaging",
      "batch_number": "LOT-1",
      "expiry_date": "2027-01-01T00:00:00"
    }
  ],
  "notes": "Delivery received in good condition"
}
```

Accepted value uses PO line discount + tax math (Stage 11 C1). Uninvoiced AP aging uses received value, not full PO total.

### 6.5 Purchase Invoice
**List:** `GET /purchasing/invoices`  
**Create:** `POST /purchasing/invoices`  
**Get:** `GET /purchasing/invoices/{invoice_id}`  

Supplier payments: `POST /suppliers/{id}/payments` (credit module). Attachment: `POST/GET/DELETE /purchasing/invoices/{invoice_id}/attachment`.

**OCR suggest:** `POST /purchasing/invoices/{invoice_id}/ocr-suggest` — requires `purchasing:write`  
**OCR apply (Stage 10 A1):** `POST /purchasing/invoices/{invoice_id}/ocr-apply` — requires `purchasing:write`

```json
{
  "confirm": true,
  "supplier_invoice_number": "SUP-42",
  "notes": "From OCR",
  "invoice_date": "2026-03-10T00:00:00",
  "due_date": null
}
```

`confirm` must be `true`. Applies only while the invoice is `draft` (409 otherwise). Suggest remains read-only; there is no silent auto-write from OCR.

### 6.6 Purchase Return
**List:** `GET /purchasing/returns`  
**Create:** `POST /purchasing/returns`  
**Get:** `GET /purchasing/returns/{return_id}`  
**Post:** `POST /purchasing/returns/{return_id}/post`

---

## 7. Sales & Customers

Stage 19 S1 proves sales quotations/orders/invoices/payments/returns/POS and purchasing suppliers/PR/PO/GRN/PI/payments via JWT (+ X-API-Key reads) — `test_sales_purchases_api_s1.py` (BR-18.4–18.5).


### 7.1 Customers
**List:** `GET /customers`  
**Create:** `POST /customers`  
**Get:** `GET /customers/{customer_id}` (includes `balance`)  
**Update:** `PATCH /customers/{customer_id}`  
**Delete:** `DELETE /customers/{customer_id}` (soft-deactivate → `status=inactive`)  
**History:** `GET /customers/{customer_id}/history`  
**Outstanding:** `GET /customers/{customer_id}/outstanding` (`credit:read`)

Stage 19 P1 proves customers/groups CRUD + balance + history via JWT and X-API-Key sales reads — `test_products_customers_api_p1.py` (BR-18.3).

**Create Customer:**
```json
{
  "name": "Walk-in Customer",
  "email": "walkin@example.com",
  "phone": "+1-555-0300",
  "address": "789 Customer Lane",
  "party_type": "registered",
  "customer_group_id": "group_uuid",
  "credit_limit": 500.00
}
```

### 7.2 Customer Groups
**List:** `GET /customers/groups`  
**Create:** `POST /customers/groups`  
**Get:** `GET /customers/groups/{group_id}`  
**Update:** `PATCH /customers/groups/{group_id}`  
**Delete:** `DELETE /customers/groups/{group_id}`

### 7.3 Quotations
**List:** `GET /sales/quotations`  
**Create:** `POST /sales/quotations`  
**Get:** `GET /sales/quotations/{quote_id}`  
**Convert to Order:** `POST /sales/quotations/{quote_id}/convert-to-order`

**Create Quotation:**
```json
{
  "customer_id": "cust_001",
  "quote_date": "2026-08-07",
  "expiry_date": "2026-08-14",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 2,
      "unit_price": 12.99,
      "discount": 1.00,
      "tax_rate": 10.0
    }
  ],
  "notes": "Special pricing for bulk order"
}
```

### 7.4 Sales Orders
**List:** `GET /sales/orders`  
**Create:** `POST /sales/orders`  
**Get:** `GET /sales/orders/{order_id}`  
**Update Status:** `PATCH /sales/orders/{order_id}/status`  
**Convert to Invoice:** `POST /sales/orders/{order_id}/convert-to-invoice`

**Status Flow:** `draft` → `confirmed` → `processing` → `shipped` → `delivered` → `cancelled`

### 7.5 Invoices
**List:** `GET /sales/invoices`  
**Create:** `POST /sales/invoices`  
**Get:** `GET /sales/invoices/{invoice_id}`  
**Post:** `POST /sales/invoices/{invoice_id}/post`  
**Pay:** `POST /sales/invoices/{invoice_id}/payments`  
**Print:** `GET /sales/invoices/{invoice_id}/print`

**Post stock integrity (Stage 15 H1):** Aggregated line quantities are checked before stock-out / AR / journal. Insufficient available stock → `409` with `detail.code = INSUFFICIENT_STOCK`; invoice stays `draft` (no movements, AR bump, or JE).

**Post GL (Stage 15 I1):** Auto journal debits AR `1100`, credits Revenue `4000` (+ Tax `2100` when applicable), and when standard cost > 0 also Dr COGS `5000` / Cr Inventory `1200` (qty × product/variant `cost_price`). Same COGS helper applies to POS sale journals.

**Post audit (Stage 15 A1):** Domain audit `invoice_posted` (`module=sales`) includes tax, stock qty out, customer balance, currency/FX, store.

**Post (credit-limit override):** When posting would push customer AR over `credit_limit`, the API returns `409` with `detail.code=CREDIT_LIMIT_EXCEEDED` and projection fields. Callers with `credit:approve` may retry with:

```json
{
  "credit_limit_override": true,
  "credit_override_reason": "Approved by store manager — VIP order"
}
```

Reason must be at least 3 characters (`400 CREDIT_OVERRIDE_REASON_REQUIRED`). Missing permission → `403 CREDIT_OVERRIDE_FORBIDDEN`. Successful override writes audit action `credit_limit_override` and sets invoice `credit_limit_overridden` / `credit_override_reason` / `credit_override_by` / `credit_override_at`.

**Create Invoice:**
```json
{
  "customer_id": "cust_001",
  "order_id": "so_001",
  "invoice_date": "2026-08-07",
  "due_date": "2026-08-14",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 2,
      "unit_price": 12.99,
      "discount": 1.00,
      "tax_rate": 10.0
    }
  ],
  "payment_method": "cash",
  "notes": "Thank you for your business"
}
```

### 7.6 Sales Return
**List:** `GET /sales/returns`  
**Create:** `POST /sales/returns`  
**Get:** `GET /sales/returns/{return_id}`  
**Post:** `POST /sales/returns/{return_id}/post`

**Post (Stage 15 R1/A1):** Restock sellable lines into the original invoice’s store warehouse when `store_id` is set. Customer balance and return journal amounts use `to_base` via the invoice `exchange_rate` (document `paid_amount` stays in doc currency). Journal includes tax reverse `2100`, COGS/Inventory reverse when restocked, and `store_id`. Allocates credit note number. Domain audit `sales_return_posted`.

**Create Return:**
```json
{
  "sales_invoice_id": "inv_001",
  "reason": "defective",
  "restock": true,
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 1,
      "condition": "sellable"
    }
  ]
}
```

---

## 8. Point of Sale (POS)

### 8.1 POS Session
**Open Shift:** `POST /pos/sessions/open`

```json
{
  "store_id": "st_001",
  "opening_cash": 200.00,
  "user_id": "usr_001"
}
```

**Close Shift:** `POST /pos/sessions/{session_id}/close`

```json
{
  "closing_cash": 850.50,
  "actual_cash": 845.00,
  "notes": "Minor discrepancy"
}
```

**Get Current Session:** `GET /pos/sessions/current`

### 8.2 POS Sale
**Create Sale:** `POST /pos/sales` — requires `pos:write`

Single tender: set `payment_method` (`cash`|`card`|`wallet`|`credit`|`other`).  
Split tender: set `payments[]` with `{ "payment_method", "amount", "reference?", "liquid_account_id?" }` summing to the computed sale total (`PAYMENT_TOTAL_MISMATCH` if not). Response includes `payments` rows and `payment_method` (`split` when multiple). Credit portion only increases customer AR balance.

Credit tender (full or split portion) enforces the same credit-limit gate as invoice post. Optional body fields: `credit_limit_override` (bool), `credit_override_reason` (string). Same `CREDIT_LIMIT_*` error codes and audit action apply.

**Stock integrity (Stage 13 H1):** Aggregated line quantities are checked before the sale transaction is created. Insufficient available stock returns `409` with `detail.code = INSUFFICIENT_STOCK`. No `Transaction`, `PosPayment`, or `pos_sale` journal is committed; open session totals are unchanged.

**Drawer (Stage 13 H2):** When any tender is `cash` (`has_cash_tender`), the response may include `drawer` (mock/network/browser_bridge pulse per store settings). Card/wallet-only splits omit `drawer`.

**Domain audit:** successful sale records `pos_sale_completed`.

```json
{
  "session_id": "sess_001",
  "party_id": "cust_001",
  "discount_amount": 1.00,
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 2,
      "discount": 0.50
    }
  ],
  "payments": [
    { "payment_method": "cash", "amount": 20.00 },
    { "payment_method": "card", "amount": 5.48 }
  ]
}
```

### 8.3 Product Search
**Endpoint:** `GET /pos/products/search?q=flour&barcode=8901234567890`

### 8.4 Receipt Printing & Send
**Get receipt:** `GET /pos/sales/{sale_id}/receipt` — requires `pos:read`

**Query Params:** `format=json|text|pdf` (default `json`); `paper=thermal_80|thermal_58` (tenant default when omitted). JSON includes thermal `text` plus ESC/POS drawer kick bytes (`drawer_kick_base64` / `drawer_kick_hex`).

**Send digital receipt (Stage 13 H2):** `POST /pos/sales/{sale_id}/receipt/send` — requires `pos:write`

**Query Params:** `channel=email|sms` (default `email`); `to` optional recipient (defaults to cashier email/phone); `paper` optional.

Successful send records domain audit `pos_receipt_sent` (`module=pos`, `entity=pos_sale`). Email/SMS uses SMTP/Twilio when configured, otherwise console mode in non-production.

### 8.5 Cash Drawer
**Summary:** `GET /pos/sessions/{session_id}/drawer` — requires `pos:read`  
**Manual open:** `POST /pos/sessions/{session_id}/drawer/open` — requires `pos:write`  
**Store settings:** `PATCH /stores/{store_id}/drawer` — `drawer_mode` `none|mock|network|browser_bridge`, `drawer_open_on_cash`, optional `drawer_host`/`drawer_port`

---

## 9. Expense Management

Stage 22 D1 fidelity for BR-9: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

### 9.1 Expense Categories
**List:** `GET /expenses/categories`  
**Create:** `POST /expenses/categories`  
**Update:** `PATCH /expenses/categories/{category_id}`  
**Budgets (Stage 22 E1):** `GET /expenses/budgets`

Create/update accept optional `account_id` (tenant expense-type COA; Stage 14 E1) and `budget_amount` (Stage 22 E1). Serialize includes `account_id`, `account_code`, `account_name`. Clear mapping with `clear_account: true` on PATCH. Invalid non-expense account → `400 INVALID_EXPENSE_ACCOUNT`.

### 9.2 Expenses
**List:** `GET /expenses?store_id=&department_id=`  
**Create:** `POST /expenses`  
**Get:** `GET /expenses/{expense_id}`  
**Update:** `PATCH /expenses/{expense_id}`  
**Approve:** `POST /expenses/{expense_id}/approve`  
**Reject:** `POST /expenses/{expense_id}/reject` — body `{ "reason" }`  
**Delete:** `DELETE /expenses/{expense_id}`  
**Approval settings (Stage 22 A1):** `GET/PATCH /expenses/settings` — levels, thresholds, role gates (expense approval matrix)  
**OCR suggest:** `POST /expenses/{expense_id}/ocr-suggest` — requires `expenses:write`  
**OCR apply (Stage 10 A1):** `POST /expenses/{expense_id}/ocr-apply` — requires `expenses:write`

Create/update accept optional `store_id`, `department_id`, `payee` (Stage 14 E2). Foreign store/department → `404`. Approve/reject emit domain audit `expense_approved` / `expense_rejected` (`module=expenses`); submit pending → `expense_submitted`; under-threshold → `expense_auto_approved`; mid-level → `expense_level_approved` (Stage 14 A3). Final/auto approve also posts `journal_posted` with `source_type=expense`.

```json
{
  "confirm": true,
  "amount": 75.5,
  "payee": "Office Depot",
  "description": "Receipt — Office Depot",
  "reference": "R-9",
  "expense_date": "2026-04-01T00:00:00",
  "category_id": null,
  "payment_method": null
}
```

`confirm` must be `true`. Applies only to `pending`/`rejected` expenses (same gate as `PATCH`). Suggest remains read-only; human review is required before apply.

**Create Expense:**
```json
{
  "category_id": "exp_cat_001",
  "amount": 150.00,
  "expense_date": "2026-08-07",
  "payment_method": "bank_transfer",
  "reference": "UTIL-001",
  "payee": "City Power",
  "description": "Monthly electricity bill",
  "store_id": "store_001",
  "department_id": "dept_001"
}
```

### 9.3 Recurring Expenses
**List:** `GET /expenses/recurring`  
**Create:** `POST /expenses/recurring`  
**Update:** `PATCH /expenses/recurring/{id}`  
**Generate (Stage 22 A1):** `POST /expenses/recurring/generate`

Templates carry optional `store_id` / `department_id` into generated expenses (Stage 14 E2). `PATCH` supports `skip_next`, `next_amount`, `next_description` (Stage 22 A1).

**Create Recurring:**
```json
{
  "category_id": "exp_cat_001",
  "amount": 150.00,
  "frequency": "monthly",
  "start_date": "2026-08-01",
  "end_date": "2026-12-31",
  "description": "Recurring utility payment"
}
```

---

## 10. Accounting

Stage 22 D1 fidelity for BR-10: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`). Seeded system COA is industry-agnostic for MVP (Stage 22 C1).

### 10.1 Chart of Accounts
**List:** `GET /accounting/accounts` (`tree=true` for nested children; `active_only` default true)  
**Create:** `POST /accounting/accounts`  
**Get:** `GET /accounting/accounts/{account_id}`  
**Update:** `PATCH /accounting/accounts/{account_id}`  
**Opening balance:** `POST /accounting/accounts/{account_id}/opening-balance`

**Account Types:** `asset`, `liability`, `equity`, `income`, `expense`

**Create body:** `{ "code", "name", "account_type", "parent_id?" }` — non-system accounts only. Parent must share `account_type`; cycles rejected.

**Opening balance body:** `{ "amount", "description?" }` — natural-side amount (assets/expenses debit; liability/equity/income credit). Posts balanced journal against system account `3900` Opening Balances Equity (`source_type=opening_balance`). Duplicate posted opening balance → `409 OPENING_BALANCE_EXISTS`.

### 10.2 Journal Entries
**List:** `GET /accounting/journal-entries?store_id=`  
**Create:** `POST /accounting/journal-entries`  
**Get:** `GET /accounting/journal-entries/{entry_id}`  
**Unpost:** `POST /accounting/journal-entries/{entry_id}/unpost`  
**Upload attachment (Stage 9 J1):** `POST /accounting/journal-entries/{entry_id}/attachment` (multipart `file`) — requires `accounting:write`  
**Download attachment:** `GET /accounting/journal-entries/{entry_id}/attachment` — requires `accounting:read`  
**Delete attachment:** `DELETE /accounting/journal-entries/{entry_id}/attachment` — requires `accounting:write`  

Journal payloads include `attachment_url`, `has_attachment`, and optional `store_id` (Stage 14 A1). Manual create accepts `store_id` (tenant-scoped 404). Auto-post from expense / sales invoice / POS sets store when known. Sales invoice / POS / sales return journals include standard-cost COGS↔Inventory lines when cost > 0 (Stage 15 I1); returns also carry invoice `store_id` (Stage 15 R1). List filter `store_id` returns matching entries only. Upload replaces any prior stored object for the entry. Download returns `404` when none is stored.

Unpost reverses account balances and sets status `unposted`. Allowed only when `entry_date` is in the tenant’s open fiscal year (`fiscal_year_start` MM-DD). Returns `409` with `FISCAL_PERIOD_CLOSED`, `JOURNAL_NOT_POSTED`, or `JOURNAL_RECONCILED` when blocked.

**Create Journal Entry:**
```json
{
  "date": "2026-08-07",
  "reference": "JE-001",
  "description": "Adjusting entry for depreciation",
  "entries": [
    {
      "account_id": "acc_001",
      "debit": 100.00,
      "credit": 0.00
    },
    {
      "account_id": "acc_002",
      "debit": 0.00,
      "credit": 100.00
    }
  ]
}
```

### 10.3 Cash & Bank Accounts / Account ledger
**Liquid accounts (Stage 22 B1):** `GET/POST /accounting/liquid-accounts`, `PATCH /accounting/liquid-accounts/{account_id}` — cash/bank with optional `bank_name` / `account_number` / `bank_branch`  
**Liquid transfers:** `POST /accounting/liquid-transfers` — `deposit` / `withdrawal` / `transfer`  
**Bank statements / recon:** `GET/POST /accounting/bank-statements`, `POST .../import`, match/ignore/complete lines (Open Banking adapters deferred)  
**Cheques:** `GET/POST /accounting/cheques` + issue/deposit/bounce/clear lifecycle  
**List (COA filter):** `GET /accounting/accounts?type=asset&sub_type=cash`  
**Create:** `POST /accounting/accounts`  
**Get Transactions (Stage 8 A1):** `GET /accounting/accounts/{account_id}/transactions`

Query: `from_date`, `to_date` (ISO date), `include_unposted` (default false). Returns account metadata, `opening_balance` (activity before `from_date`), `closing_balance`, `total_debit` / `total_credit`, and `transactions[]` with `entry_number`, `entry_date`, debit/credit, and running `balance` on the account’s natural side (assets/expenses: debit−credit; liability/equity/income: credit−debit). Requires `accounting:read`.

### 10.4 Financial Reports
**Profit & Loss:** `GET /reports/profit-loss?from_date=&to_date=&store_id=&branch_id=&compare=` (also `GET /accounting/profit-loss`)  

Returns period totals from **posted** journal lines: `revenue`, `cogs`, `gross_profit`, `operating_expenses`, `other_income`, `income`, `expense`, `net_profit`, plus per-account `bucket`. Optional `store_id` / `branch_id` filter journals by store dimension (Stage 14 A1 store; Stage 23 F1 branch). Foreign store/branch → `404`. Store not in branch → `400 STORE_BRANCH_MISMATCH`. Stage 23 C1: `compare=true` adds `comparison` with equal-length prior period + per-metric `current` / `prior` / `change_pct` (defaults to current calendar month when dates omitted).

**Cash Flow:** `GET /reports/cash-flow?from_date=&to_date=&store_id=&branch_id=&compare=`  

Liquid (cash/bank) movements classified as `operating` / `investing` / `financing` / `transfer` by journal `source_type`. Includes `opening_cash`, `closing_cash`, `net_change` (excludes cash↔bank transfers). Optional `store_id` / `branch_id` (Stage 14 A1 / Stage 23 F1). Stage 23 C1: `compare=true` prior-period `comparison` block (same semantics as P&L).

**Trial Balance:** `GET /reports/trial-balance?as_of_date=` (also `GET /accounting/trial-balance`)  

When `as_of_date` is set, balances are rebuilt from **posted** journal lines with `entry_date` through that day; omit for live account balances. Response includes `as_of` (Stage 14 A2).

**Balance Sheet (Stage 23 F1/C1):** `GET /reports/balance-sheet?as_of_date=&store_id=&branch_id=&compare=`  

Same `as_of_date` semantics as trial balance; response includes `as_of`, `store_id`, `branch_id`, assets/liabilities/equity, and `balanced`. With store/branch filters, balances rebuild from posted journals (tenant live balances are not store-scoped). Empty branch (no stores) returns a zeroed balanced sheet. Stage 23 C1: `compare=true` compares against the same calendar day one month earlier (`comparison.mode=prior_as_of`).

**Export (Stage 22 P1 / Stage 23 F1/C1):** `GET /reports/export?report_type=profit_loss|trial_balance|balance_sheet|cash_flow&format=pdf|xlsx` (also CSV where supported) with optional `store_id` / `branch_id` / `compare`. AR/AP aging via `GET /credit/aging?kind=receivable|payable`.

---

## 11. Credit Management

Stage 22 D1 fidelity for BR-11: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

### 11.1 Customer Credit
**Get Credit Info:** use customer `balance` on `GET /customers/{customer_id}` plus `GET /credit/customers/{customer_id}/statement` (`credit:read`) — there is no `GET /customers/{customer_id}/credit` route.  
**Aging:** `GET /credit/aging?kind=receivable|payable`  
**Credit limit (Stage 22 R1):** `PATCH /customers/{customer_id}/credit-limit` — block on exceed (`CREDIT_LIMIT_EXCEEDED`); override with `credit_limit_override` + reason + `credit:approve`

**Response:**
```json
{
  "success": true,
  "data": {
    "credit_limit": 500.00,
    "outstanding_balance": 350.00,
    "available_credit": 150.00,
    "credit_sales": [
      {
        "invoice_id": "inv_001",
        "amount": 200.00,
        "due_date": "2026-08-14",
        "status": "outstanding"
      }
    ]
  }
}
```

**Get Outstanding Bills (Stage 8 S2):** `GET /customers/{customer_id}/outstanding`

Returns open AR invoices (`posted` / `partial` / `sent` / `overdue` with balance > 0): `{ invoice_id, invoice_number, amount, due_date, status, document_type: "sales_invoice" }`. Requires `credit:read`; 404 if customer missing.

**Record Payment:** `POST /customers/{customer_id}/payments` (alias `POST /sales/payments`)

```json
{
  "customer_id": "cust_001",
  "amount": 100.00,
  "payment_method": "cash",
  "sales_invoice_id": "inv_001",
  "reference": "RCP-001",
  "notes": "Partial payment for INV-001"
}
```

Optional `sales_invoice_id` allocates to that invoice only; omit to auto-allocate oldest-first (Stage 14 R1 Credit UI). Wrong customer → `400`.

### 11.2 Supplier Credit
**Get Outstanding Bills (Stage 8 S2):** `GET /suppliers/{supplier_id}/outstanding`

**Payment Schedule (Stage 8 S1 / BR-11.2):** `GET /suppliers/{supplier_id}/payment-schedule`

Returns `{ supplier_id, supplier_name, as_of, total_due, overdue_total, upcoming_total, early_pay, items[] }`. Each item includes `document_type` (`purchase_invoice` | `purchase_order`), amount, `due_date`, `days_until_due`, `schedule_bucket` (`overdue` | `due_today` | `upcoming` | `unscheduled`), and `early_discount` quote for open purchase invoices. Sorted overdue → due today → upcoming. Requires `credit:read`.

**Record Payment:** `POST /suppliers/{supplier_id}/payments`

Optional `purchase_invoice_id` and/or `purchase_order_id`; omit both to auto-allocate oldest open bills then POs (Stage 14 R1).

---

## 12. Tax Management

Stage 22 D1 fidelity for BR-12: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

### 12.1 Tax Rates
**List:** `GET /tax/rates?active_only=` (alias `GET /taxes/rates`)  
**Create:** `POST /tax/rates`  
**Get:** `GET /tax/rates/{rate_id}`  
**Update (Stage 14 T1):** `PATCH /tax/rates/{rate_id}` — name/rate/type/mode/components/flags; `is_active: false` deactivates and clears default  
**Set default:** `POST /tax/rates/{rate_id}/default`  
**Calculate (Stage 22 T1):** `POST /tax/calculate` — inclusive/exclusive pricing mode + compound components (`basis: compound`)

**Create Tax Rate:**
```json
{
  "name": "Standard VAT",
  "rate": 10.0,
  "tax_type": "vat",
  "pricing_mode": "exclusive",
  "is_default": true,
  "is_active": true
}
```

### 12.2 Tax Reports
**Endpoint:** `GET /reports/tax?from_date=&to_date=&period=&year=&month=&quarter=`  
**Filing pack:** `GET /reports/tax/filing?from_date=&to_date=&period=&year=&month=&quarter=&jurisdiction=` — jurisdiction-neutral boxes plus optional government mapping when supported (`GH`, `NG`, `KE`)  

`period=monthly|quarterly|annually` resolves bounds from `year` / `month` / `quarter` (defaults to current UTC period). Response includes `period`, `period_year`, `period_month`, `period_quarter` when a preset is used (Stage 14 T1). Explicit `from_date`/`to_date` still work when `period` is omitted.

**Exports:** `tax`, `tax_filing`, `tax_filing_gh`, `tax_filing_ng`, `tax_filing_ke` via `/reports/export` (also surfaced on Reports → Tax UI — Stage 16 R2)  

Government templates are **manual filing workbooks only** — they do not e-file to GRA, FIRS, or KRA iTax portals (Stage 10 T2).

### 12.3 Credit aging export (Stage 16 R2)
**Export:** `GET /reports/export?report_type=credit_aging&format=csv|xlsx|pdf&kind=receivable|payable&as_of_date=`  

Packages existing `/credit/aging` into the Reports export surface (no parallel Credit engine). Default `kind=receivable`. Reports UI Credit tab links to `/credit`.

### 12.4 Transfer history export (Stage 16 M2)
**Report:** `GET /reports/transfers`  
**Export:** `GET /reports/export?report_type=transfer_history&format=csv|xlsx|pdf&status=&store_id=&scope=all|inter_store|warehouse&from_date=&to_date=&limit=`  

Consolidated inter-store + warehouse transfer history (same `StockTransfer` records as `/stores/transfers`). Reports UI **Transfers** tab.

---

## 13. Multi-Store Management

### 13.1 Stores
**List:** `GET /stores`  
**Create:** `POST /stores`  
**Get:** `GET /stores/{store_id}`  
**Update:** `PATCH /stores/{store_id}`

**Create Store:**
```json
{
  "name": "Downtown Store",
  "code": "DT-01",
  "address": "100 Main St",
  "phone": "+1-555-0400",
  "manager_id": "usr_002",
  "warehouse_id": "wh_002",
  "status": "active"
}
```

### 13.2 Store Inventory
**Endpoint:** `GET /stores/{store_id}/inventory`

### 13.3 Store Sales
**Endpoint:** `GET /stores/{store_id}/sales`

Query params: `from_date`, `to_date`, `recent_limit` (default 50, max 200).

Returns store metadata, aggregated `summary` (invoice/POS counts and revenue), and `recent` sale lines (`source` = `invoice`|`pos`). Tenant-scoped; unknown/foreign store → 404. Requires `stores:read`.

Global UI store context (Shell switcher) is client-side only (`localStorage` key `selected_store_id`); it does not send a store header to the API.

### 13.4 Inter-Store Transfers
**List:** `GET /stores/transfers` — optional filters: `status`, `store_id` (from or to), `from_date`, `to_date`, `scope=all|inter_store|warehouse`, `limit` (Stage 16 M2)  
**Create:** `POST /stores/transfers`  
**Get:** `GET /stores/transfers/{transfer_id}`  
**Submit:** `POST /stores/transfers/{transfer_id}/submit`  
**Ship:** `POST /stores/transfers/{transfer_id}/ship`  
**Receive:** `POST /stores/transfers/{transfer_id}/receive`  
**Cancel:** `POST /stores/transfers/{transfer_id}/cancel`

**Transfer history report (Stage 16 M2):** `GET /reports/transfers?status=&store_id=&from_date=&to_date=&scope=all|inter_store|warehouse&limit=` — consolidated counts/`by_status`/qty totals + serialized transfers. Export: `report_type=transfer_history` via `/reports/export`. Reports UI **Transfers** tab.

Status flow: `draft` → `requested` → `in_transit` → `received` (or `cancelled`).

**Dual-manager approval (Stage 4 T1 / BR-13.2):** When the source store has `manager_id`, only that user may ship (`403 TRANSFER_SHIP_FORBIDDEN` otherwise). When the destination store has `manager_id`, only that user may receive (`403 TRANSFER_RECEIVE_FORBIDDEN`). `company_admin` / `super_admin` may override either action; override writes audit action `transfer_manager_override`. Warehouse-only transfers (null store ids) skip this gate. Serialized transfers include `from_store_manager_id` / `to_store_manager_id`.

**Stock chain (Stage 16 M1):** Ship deducts source warehouse stock and writes `stock_movements` (`transfer_out`, `reference_type=stock_transfer`). Receive adds destination warehouse stock (`transfer_in`). Insufficient source qty → `409 INSUFFICIENT_WAREHOUSE_STOCK`; transfer stays `requested` with no movements. Evidence: `test_multistore_transfer_chain_m1.py`.

**Create Transfer:**
```json
{
  "from_store_id": "st_001",
  "to_store_id": "st_002",
  "submit": true,
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 20
    }
  ],
  "notes": "Stock rebalancing"
}
```

---

## 14. Reports

Stage 23 D1 fidelity for BR-14.5 financial filters/comparative + MVP gate docs: `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`). Financial endpoints also documented under §10.4.

### 14.1 Sales Reports
**Daily Sales:** `GET /reports/sales/daily?date=` — includes `previous_day_revenue` and `change_pct` vs prior day.  
**Monthly Sales:** `GET /reports/sales/monthly?month=&year=` — includes `previous_month_revenue` and `change_pct`.  
**Product Sales:** `GET /reports/sales/products?from_date=&to_date=&store_id=&category_id=`  
**Customer Sales:** `GET /reports/sales/customers?from_date=&to_date=&limit=` — top customers by revenue and frequency (invoice + POS).  
**Salesperson:** `GET /reports/sales/salesperson?from_date=&to_date=`  
**By Store:** `GET /reports/sales/by-store?from_date=&to_date=`

Export type `sales_customers` is available on `/reports/export`. Product export honors `store_id` / `category_id`.

### 14.2 Inventory Reports
**Stock Balance:** `GET /reports/inventory/balance?warehouse_id=`  
**Stock Movement:** `GET /reports/inventory/movements?product_id=&from_date=&to_date=`  
**Low Stock:** `GET /reports/inventory/low-stock?store_id=&warehouse_id=`  
**Expiry:** `GET /reports/inventory/expiry?days=30`  
**Stock Valuation (Stage 9 R2):** `GET /reports/inventory/valuation?warehouse_id=&store_id=`  

Valuation uses **standard cost** only: `value = quantity × product.cost_price`. Response includes `costing_method` (`standard_cost`), `costing_method_note`, line items, `by_warehouse` totals, and overall `total_value`. FIFO/LIFO/weighted average are **not** implemented. Export type: `inventory_valuation`. Requires `reports:read`. See also `docs/STAGE_9_FIDELITY.md`.

### 14.3 Purchase Reports
**Purchase Summary:** `GET /reports/purchases/summary?from_date=&to_date=`  
**Supplier Purchases:** `GET /reports/purchases/suppliers?supplier_id=&from_date=&to_date=`  
**Pending Orders (Stage 9 R1):** `GET /reports/purchases/pending-orders?supplier_id=&from_date=&to_date=` — issued POs in `sent` or `partially_received` with ordered/received/open quantities  
**Purchase Return Summary (Stage 9 R1):** `GET /reports/purchases/returns?supplier_id=&from_date=&to_date=` — returns by reason/supplier with posted totals  

Export types: `purchases_pending_orders`, `purchases_returns` (plus existing `purchases_summary` / `purchases_suppliers`). Requires `reports:read`.

### 14.4 Expense Reports
**Expense Summary:** `GET /reports/expenses/summary?from_date=&to_date=&category_id=`

### 14.5 Financial Reports (Stage 23 F1/C1)
See §10.4 for `GET /reports/profit-loss`, `/reports/cash-flow`, `/reports/balance-sheet`, `/reports/trial-balance` with `store_id` / `branch_id` / `compare` and export packaging.

---

## 15. Notifications

Stage 21 N1/D1 proves BR-4.4 panel fidelity — unread count, groups, mark read/unread, 90-day history (`test_dashboard_notifications_n1.py`; `docs/STAGE_21_FIDELITY.md`). WebSocket realtime remains deferred.

### 15.1 List Notifications
**Endpoint:** `GET /notifications?status=unread&category=&group=`

Groups: `stock`, `orders`, `payments`, `system`. Category `new_order` (Stage 4 N1 / BR-15.1) belongs to group `orders` and is emitted when a sales order is created or confirmed. List applies a **90-day** `created_at` cutoff (`HISTORY_DAYS`).

**Unread count:** `GET /notifications/unread-count` → `{ count }`.

### 15.2 Mark as Read
**Endpoint:** `PATCH /notifications/{notification_id}/read`  
**Mark unread:** `PATCH /notifications/{notification_id}/unread`  
**Mark all read:** `POST /notifications/read-all`

### 15.3 Notification Settings
**Endpoint:** `GET /notifications/settings`  
**Update:** `PATCH /notifications/settings`

Preference keys include `new_order`, `low_stock`, `purchase_received`, `payment_due`, `credit_limit`, `shift_variance`, `transfer`, and other default categories. Each key has `dashboard` / `email` / `sms` booleans.

```json
{
  "low_stock": { "dashboard": true, "email": false, "sms": false },
  "new_order": { "dashboard": true, "email": false, "sms": false },
  "payment_due": { "dashboard": true, "email": true, "sms": false },
  "credit_limit": { "dashboard": true, "email": false, "sms": false }
}
```

Outline alert categories (`low_stock`, `new_order`, `credit_limit`, `purchase_received`, `shift_variance`, `transfer`) default **email/sms false**; enable per user via this API. `payment_due` / `expense_approval` default email on.

**Channel delivery (Stage 16 N2):** After the dashboard notification is written, `create_notification` best-effort sends email/SMS to recipients with that channel enabled for the category. Broadcast alerts (`user_id` null) target active `company_admin` / `super_admin`. SMTP unset → email `mode=console` outbox attempt; Twilio unset → SMS `mode=console`. Carrier `delivered` is only recorded for real SMTP/Twilio sends.
---

## 16. AI Business Assistant

Stage 20 D1 proves BR-21 commercial-MVP AI fidelity on rule-based `/ai/*` engines — `docs/STAGE_20_FIDELITY.md` (`test_stage20_fidelity_d1.py`). External LLM / Prophet upgrades remain deferred.

### 16.1 AI ERP Chat Assistant
**Endpoint:** `POST /ai/chat`  
**History:** `GET /ai/chat/history`  
**Permission:** `ai:read` (commands that write require the matching module write, e.g. `purchasing:write` for draft PO)

**Request:**
```json
{
  "message": "What are my top selling products this month?",
  "context": "dashboard",
  "conversation_id": "conv_001"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "reply": "Your top selling products this month are: 1. Organic Wheat Flour (245 units), 2. Sugar 1kg (189 units), 3. Rice 5kg (156 units).",
    "suggested_actions": [
      { "type": "navigate", "label": "View Sales Report", "url": "/reports/sales/products" }
    ]
  }
}
```

### 16.2 AI Dashboard Insights
**Endpoint:** `GET /ai/insights`  
Returns anomaly / restock / purchase cards with per-card `domains` cites (Inventory, Sales, Purchases, Expenses). Also returns `actuals`, `actuals_covered`, and `note` (Stage 25 B1). Weekly digest via Celery/`publish_insights` when email prefs allow. Evidence: `test_ai_insights_fidelity_i1.py`, `test_ai_business_insights_b1.py`.

### 16.3 Smart Inventory Intelligence
**Endpoints:**  
- `GET /ai/inventory/predictions` — combined forecast + low-stock summary  
- `GET /ai/inventory/demand-forecast` — 7/30/90 demand + reorder + seasonality  
- `GET /ai/inventory/dead-stock` — idle stock identification

### 16.4 AI Low Stock Prediction
**Endpoint:** `GET /ai/inventory/low-stock-prediction?horizon_days=14&lead_time_days=7&lookback_days=30&at_risk_only=true`

### 16.5 AI Sales Analysis
**Endpoint:** `GET /ai/sales/analysis?from_date=&to_date=&lookback_days=90`  
Returns `trend` (incl. 7/14/30 forecast), `rfm`, `product_affinity`, `peaks`.

### 16.6 AI Expense Analysis
**Endpoint:** `GET /ai/expenses/analysis?from_date=&to_date=`

### 16.6a AI Purchases Analysis (Stage 25 P1 / BR-21.11)
**Endpoint:** `GET /ai/purchases/analysis?from_date=&to_date=&lookback_days=90`  
Returns `trend` (incl. 7/14/30 forecast from posted PI totals), `suppliers` (spend share), `purchase_orders` (status/fill), `goods_receipts`, `purchase_invoices.overdue`, and `suggestions`. Method `rules_v1` (not Prophet). Evidence: `test_ai_purchases_analysis_p1.py`. Stage 25 U1 wires this on `frontend/app/ai/page.tsx` (`test_ai_ui_fidelity_u1.py`).

### 16.6b Cross-Domain AI Analysis (Stage 25 X1 / BR-21.12)
**Endpoint:** `GET /ai/cross-domain/analysis?from_date=&to_date=&lookback_days=90`  
Orchestrates inventory / sales / purchases / expenses analyzers. Returns `domains` (per-domain summaries + endpoint cites) and `cross_signals` (multi-domain synthesis). Method `rules_v1`. Evidence: `test_ai_cross_domain_x1.py`. Stage 25 U1 wires this on `frontend/app/ai/page.tsx`.

### 16.7 AI Report Generator
**Endpoint:** `POST /ai/reports/generate` (optional `?export=true` for file download)  
**Templates:** `GET/POST /ai/reports/templates`, `DELETE /ai/reports/templates/{template_id}`

```json
{
  "prompt": "Show me monthly sales for Q2 2026",
  "format": "csv"
}
```

Reuse a saved template with `{ "template_id": "…" }`. Export sets `Content-Disposition` attachment.

### 16.8 AI Document Assistant
**Endpoint:** `POST /ai/documents/analyze`

**Content-Type:** `multipart/form-data` (`file` + query/form `document_type`)

```json
{
  "file": "<uploaded_file>",
  "document_type": "invoice"
}
```

Human-confirmed OCR apply to expense/PI drafts uses the Stage 10 `ocr-apply` paths (`confirm: true`); PO OCR apply remains deferred. Stage 25 U1 wires suggest-only analyze on `frontend/app/ai/page.tsx` (`test_ai_ui_fidelity_u1.py`).

### 16.9 AI Customer Assistant
**Endpoints:**  
- `POST /ai/customer/assist` — NL assist for a customer or portfolio query  
- `GET /ai/customers/insights` — `best_customers`, `churn_risks`, `promotion_suggestions`

```json
{
  "customer_id": "cust_001",
  "query": "What is my current outstanding balance?"
}
```

### 16.10 AI Security Monitor
**Endpoint:** `GET /ai/security/alerts?lookback_hours=72&notify=false`  
`notify=true` creates unread `category=security` notifications for high-score alerts. Requires `security:read`.

---

## 17. Webhooks

RIBDIGI ERP supports webhook subscriptions for real-time event notifications.

### 17.1 Manage Webhooks
**List:** `GET /webhooks`  
**Create:** `POST /webhooks`  
**Get:** `GET /webhooks/{webhook_id}`  
**Update:** `PATCH /webhooks/{webhook_id}`  
**Delete:** `DELETE /webhooks/{webhook_id}`

**Create Webhook:**
```json
{
  "url": "https://your-app.com/webhooks/ribdigi",
  "events": ["sale.created", "stock.low", "payment.received"],
  "secret": "whsec_your_secret",
  "is_active": true
}
```

### 17.2 Available Events

| Event | Description |
|-------|-------------|
| `sale.created` | New sale/invoice created |
| `sale.paid` | Invoice payment received |
| `stock.low` | Product reached low stock level |
| `stock.in` | Stock received into warehouse |
| `purchase.order.created` | New PO created |
| `purchase.grn.received` | GRN recorded |
| `customer.created` | New customer added |
| `expense.approved` | Expense approved |
| `user.login` | User logged in |
| `tenant.suspended` | Tenant account suspended |

### 17.3 Webhook Payload
```json
{
  "event": "sale.created",
  "timestamp": "2026-08-07T13:51:00Z",
  "tenant_id": "tenant_abc123",
  "data": {
    "invoice_id": "inv_001",
    "amount": 250.00,
    "customer_id": "cust_001"
  }
}
```

### 17.4 Signature verification (Stage 6 W1)
Each delivery includes header `X-Ribdigi-Signature` with value `t=<unix_ts>,v1=<hex>` where `v1` is HMAC-SHA256 of `{t}.{raw_body}` using the webhook signing secret (`whsec_…`, shown once on create). Reject if timestamp skew exceeds 5 minutes. Test ping: `POST /webhooks/{id}/test` (`webhook.test` event). Invoice post emits `sale.created`.

### 17.5 Delivery retries (Stage 7 W2)
Non-2xx or transport errors set delivery status to `pending_retry` with `next_retry_at` using exponential backoff (`WEBHOOK_RETRY_BASE_SECONDS` × 5^(attempt−1), capped at 1 hour). Celery beat job `retry_due_webhooks` (also `POST /jobs/retry_due_webhooks/run`) re-signs the stored payload with a fresh timestamp and re-POSTs. After `WEBHOOK_MAX_ATTEMPTS` (default 5) the delivery is terminal `failed`. Successful retry → `delivered` and clears `next_retry_at`.

---

## 18. Caching (Stage 6 P2 / Stage 7 C2)

Read models and resolved permissions may be served from Redis (`CACHE_BACKEND=auto|redis|memory`) with soft fallback:

| Endpoint / path | Key pattern | TTL |
|-----------------|-------------|-----|
| `GET /dashboard` | `ribdigi:cache:dashboard:{tenant_id}:summary` | 5 min |

**Executive dashboard (Stage 21 V1/D1):** `GET /dashboard` returns KPI totals, inventory alerts (`low_stock` / `out_of_stock` / `expiring_batches`), period compare (`daily_revenue` / `yesterday_revenue` / `dod_change_pct` + MoM), `recent_sales` (≤10), `top_products`, `daily_revenue_series` (30) / `monthly_revenue_series` (12), and `kpi_links`. Evidence: `test_dashboard_kpis_v1.py`.

| `GET /products` | `ribdigi:cache:products:{tenant_id}:all` | 10 min |
| `GET /catalog/categories` | `…:categories:flat` / `…:categories:tree` | 10 min |
| Auth claims / `GET /me` | `ribdigi:cache:perms:{tenant_id}:{user_id}` | 1 hour (`CACHE_PERMISSIONS_TTL_SECONDS`) |

Dashboard/catalog invalidated on product/catalog/stock mutations, POS sale, invoice post, and expense approval. Permissions invalidated on user role/`record_scope` change and custom-role updates that sync assigned users. Disable with `CACHE_ENABLED=false`.

## 19. Rate Limits

API requests are rate-limited with a sliding window (Stage 5 S1 / Stage 19 K1). Keys are `{client_ip}:{auth|api}:{X-Tenant-ID|anon}` so tenants sharing an egress IP do not share the same bucket. Caps come from env (`RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_AUTH_PER_MINUTE`); subscription plan-tier tables are deferred post-MVP.

Auth-class paths (stricter `RATE_LIMIT_AUTH_PER_MINUTE`) include login, refresh, 2FA verify, password-reset, email verify, and tenant registration.

**Rate Limit Headers:**
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Backend: memory|redis
```

On `429 RATE_LIMIT_EXCEEDED`, responses also include `Retry-After`. Evidence: `test_production_security_s1.py`, `test_auth_api_fidelity_k1.py`.

---

## 20. Error Codes

### HTTP Status Codes
| Code | Meaning |
|------|---------|
| `200` | OK — Success |
| `201` | Created — Resource created |
| `400` | Bad Request — Invalid input |
| `401` | Unauthorized — Authentication required |
| `403` | Forbidden — Insufficient permissions |
| `404` | Not Found — Resource doesn't exist |
| `409` | Conflict — Resource conflict |
| `422` | Unprocessable Entity — Validation error |
| `429` | Too Many Requests — Rate limit exceeded |
| `500` | Internal Server Error |

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Email is required"
      }
    ]
  },
  "request_id": "req_8f3a9b2c1d4e"
}
```

### Common Error Codes
| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Input validation failed |
| `AUTHENTICATION_FAILED` | Invalid credentials |
| `TOKEN_EXPIRED` | JWT token has expired |
| `INSUFFICIENT_PERMISSIONS` | User lacks required role/permission |
| `TENANT_SUSPENDED` | Tenant account is suspended |
| `RESOURCE_NOT_FOUND` | Requested resource not found |
| `INSUFFICIENT_STOCK` | Not enough stock for operation |
| `CREDIT_LIMIT_EXCEEDED` | Customer credit limit reached |
| `DUPLICATE_ENTRY` | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | Too many requests |

---

## Backup & Logical Restore

Stage 5 / 10 / 18 / 23 B1 — encrypted tenant `.ribbak` archives. Requires `company_admin` or `super_admin`. Runbook: `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`. Stage 23 D1 cite: `docs/STAGE_23_FIDELITY.md`.

**Settings:** `GET/PATCH /backup/settings` — `enabled`, `frequency` (`daily`|`weekly`), `retention_count`, `hour_utc`  
**Create:** `POST /backup` — returns `id`, `checksum_sha256`, `filename`  
**List / get / download:** `GET /backup`, `GET /backup/{backup_id}`, `GET /backup/{backup_id}/download` (`X-Checksum-SHA256`)  
**Run due:** `POST /backup/run-due` — schedule runner (`ran` / `reason`; never fake success on failure)  
**Verify:** `POST /backup/{backup_id}/verify` — integrity proof vs live data  
**Restore:** `POST /backup/{backup_id}/restore`  
- Dry-run: `{"dry_run": true}`  
- Apply: `{"dry_run": false, "confirm": true, "confirm_text": "RESTORE"}` (any other `confirm_text` → `400`)  
Foreign-tenant `backup_id` → `404`. WAL / pg_dump / S3 PITR deferred post-MVP. Evidence: `test_logical_dr_drill_b1.py`.

---

## Appendix A: Data Types

| Type | Format | Example |
|------|--------|---------|
| `id` | string | `usr_001`, `prod_abc123` |
| `decimal` | string | `"199.99"` |
| `date` | ISO 8601 | `2026-08-07` |
| `datetime` | ISO 8601 | `2026-08-07T13:51:00Z` |
| `currency` | ISO 4217 | `USD`, `EUR`, `NGN` |
| `status` | string enum | `active`, `inactive`, `pending` |

## Appendix B: Multi-Tenant Headers

All API requests (except tenant registration) must include:

```
X-Tenant-ID: tenant_abc123
Authorization: Bearer <jwt_token>
```

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Technical Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, JWT + OAuth2
