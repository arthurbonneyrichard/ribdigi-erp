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
15A. [Onboarding Checklist](#15a-onboarding-checklist)
15B. [Scheduled Jobs](#15b-scheduled-jobs)
15C. [Audit Logs](#15c-audit-logs)
16. [AI Business Assistant](#16-ai-business-assistant)
17. [Webhooks](#17-webhooks)
18. [Rate Limits](#18-rate-limits)
19. [Error Codes](#19-error-codes)

---

## 1. API Standards

### 1.1 Request Format
- All requests and responses use **JSON**.
- Content-Type header must be: `application/json`
- Date format: **ISO 8601** (`YYYY-MM-DDTHH:MM:SSZ`)
- Currency values are sent as **decimal strings** (e.g., `"199.99"`) to preserve precision.

### 1.2 Response Envelope
Every API response follows a standard envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully",
  "timestamp": "2026-08-07T13:51:00Z",
  "request_id": "req_8f3a9b2c1d4e"
}
```

### 1.3 Pagination
List endpoints support cursor-based pagination:

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max items per page (default: 20, max: 100) |
| `cursor` | string | Opaque cursor for next page |
| `sort` | string | Sort field (e.g., `-created_at` for descending) |

**Pagination Response:**
```json
{
  "success": true,
  "data": {
    "items": [...],
    "pagination": {
      "total_count": 150,
      "has_next": true,
      "next_cursor": "c2Nhbjs1OzM6",
      "limit": 20
    }
  }
}
```

### 1.4 HTTP Methods
| Method | Usage |
|--------|-------|
| `GET` | Retrieve resources |
| `POST` | Create resources |
| `PUT` | Full update |
| `PATCH` | Partial update |
| `DELETE` | Remove resources |

---

## 2. Authentication

RIBDIGI ERP uses **JWT (JSON Web Tokens)** with **OAuth2** flows.

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

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### 2.3 Logout
**Endpoint:** `POST /auth/logout`

**Headers:** `Authorization: Bearer <access_token>`

### 2.4 Password Reset
**Endpoint:** `POST /auth/password-reset-request`

UI: login **Forgot password?** → `/forgot-password` (workspace + email). Always returns a neutral success message (no account enumeration). Non-production may include `reset_token` for local testing. Email link opens `/reset-password?token=…`.

**Request:**
```json
{
  "email": "admin@company.com",
  "tenant_id": "acme"
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

Token is single-use and expires in 1 hour; new password must pass complexity rules.

### 2.4b Email verification (BR-19.1)
**Verify:** `POST /auth/verify-email` — `{ "token": "..." }` sets `email_verified=true` (single-use token). UI: `/verify-email?token=…` (auto-submits when token present).  
**Resend:** `POST /auth/resend-verification` — `{ "email", "tenant_id" }` neutral success; invalidates unused prior verify tokens; non-prod may echo `verification_token`.  
**Login gate:** `POST /auth/login` returns `403` with `detail.code = "EMAIL_NOT_VERIFIED"` when credentials are valid but email is unverified (no tokens issued). Login UI offers resend.

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

Client idle auto-logout uses tenant `inactivity_timeout_minutes` (default `30`, range `5`–`480`). Configure via `PATCH /tenants/me`; current value is also returned on `GET /me` and `GET /tenants/me`.

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

`industry` schema `Literal["retail","pharmacy","restaurant","bakery","wholesale","manufacturing","mart"]` (omit → `retail`; blank/invalid → **422**; case-insensitive coerce via `BeforeValidator`, e.g. `Wholesale` → `wholesale`). Service `normalize_industry` remains defense-in-depth **400**. Company page industry `<select>` matches the allow-list.

`currency` ∈ 3-letter ISO (`CurrencyCodeValue`; strip/upper; omit → `GHS`; blank/non-ISO → **422** — was free `str` with no create-path check). Same honesty on `PATCH /tenants/me`. Company **Currency** select.

`company_name` ∈ `CompanyNameValue` (strip; 2–200 chars; at least one letter/digit; no `://` / `@`); required on create; blank/`!!!`/`http://…`/`X` → **422** (was free `str` with no create-path length/content check). Same honesty on `PATCH /tenants/me` (omit/`null` → no change). Company **Company trading name** input (`aria-label`).

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
**Endpoint:** `GET /tenants/me` (own company; `company_admin` / `super_admin`)  
Also: `GET /tenants/{tenant_id}` for platform cross-tenant reads where authorized.

### 3.3 Update Tenant Profile
**Endpoint:** `PATCH /tenants/me`

**Request (partial update):**
```json
{
  "company_name": "Acme Trading",
  "legal_name": "Acme Retail Limited",
  "registration_number": "CS123456789",
  "contact_person": "Ama Mensah",
  "address": "1 Headquarters Road, Accra",
  "billing_address": "2 Billing Avenue, Accra",
  "shipping_address": "3 Warehouse Gate, Tema",
  "phone": "+233200000000",
  "email": "ops@acme.example.com",
  "website": "https://acme.example.com",
  "currency": "GHS",
  "timezone": "Africa/Accra",
  "fiscal_year_start": "01-01",
  "tax_jurisdiction": "GH",
  "tax_registration_number": "C0001234567",
  "tax_filing_period": "monthly",
  "date_format": "DD/MM/YYYY",
  "decimal_separator": ".",
  "thousand_separator": ",",
  "time_format": "24h",
  "inactivity_timeout_minutes": 30
}
```

`industry` (when sent) uses the same schema `Literal` as create (omit = no change; blank/invalid → **422**).

`currency` (when sent) same `CurrencyCodeValue` as create / FX rates (omit = no change; blank/non-ISO → **422** — was free `str` with length-only late service **400**; non-ISO could persist). Company **Currency** select.

`phone` (when sent) ∈ `E164PhoneValue` (`+` + 8–15 digits); omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`; blank silently cleared; garbage could persist). Company **Company phone** input (`aria-label`); Save omits blank phone so prior value is kept.

`website` (when sent) ∈ `WebhookUrlValue` (strip; absolute `http(s)` + netloc; `http` only for localhost/127.0.0.1/testserver/host.docker.internal); omit/`null` → no change; blank/`ftp://`/`not-a-url`/`www.x`/plain-http remote → **422** (was free `str`; blank silently cleared; garbage could persist). Company **Company website** input (`aria-label`); Save omits blank website so prior value is kept.

`tax_registration_number` (when sent) ∈ `TaxRegistrationNumberValue` (strip; alphanumeric + optional spaces/hyphens; max 40); omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently cleared TIN; garbage could persist). Company **TIN / VAT registration number** input (`aria-label`); Save omits blank TIN so prior value is kept.

`registration_number` (when sent) ∈ `RegistrationNumberValue` (strip; alphanumeric + optional spaces/hyphens; max 80); omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently cleared; garbage could persist; length>80 was late service **400**). Company **Company registration number** input (`aria-label`); Save omits blank so prior value is kept.

`contact_person` (when sent) ∈ `ContactPersonValue` (strip; 1–150 chars; at least one letter/digit; no `://` / `@`); omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently cleared; garbage could persist; length>150 was late service **400**). Company **Company contact person** input (`aria-label`); Save omits blank so prior value is kept.

`legal_name` (when sent) ∈ `LegalNameValue` (strip; 2–200 chars; at least one letter/digit; no `://` / `@`); omit/`null` → no change; blank/`!!!`/`http://…`/`X` → **422** (was free `str`; blank silently cleared; garbage could persist; len<2 or >200 was late service **400**). Company **Company legal name** input (`aria-label`); Save omits blank so prior value is kept.

`company_name` (when sent) ∈ `CompanyNameValue` (strip; 2–200 chars; at least one letter/digit; no `://` / `@`); omit/`null` → no change; blank/`!!!`/`http://…`/`X` → **422** (was free `str`; blank/`X` late service **400**; garbage could persist). Company **Company trading name** input (`aria-label`); Save always sends (required trading name).

`address` / `billing_address` / `shipping_address` (when sent) ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`); omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently cleared; garbage could persist). Company **Company headquarters address** / **Company billing address** / **Company shipping address** textareas (`aria-label`s); Save omits blank so prior value is kept.

`fiscal_year_start` (when sent) ∈ valid calendar `MM-DD` (`FiscalYearStartValue`; strip; blank/invalid/`13-01`/`02-30` → **422** — was free `str` with length-only late service **400**; garbage could persist). Company **Fiscal year start** input.

`timezone` (when sent) ∈ valid IANA key (`TimezoneValue`; strip + `ZoneInfo`; blank/`Foo/Bar`/`UTC+0` → **422** — was free `str`; blank late **400**; garbage could persist). Company **Timezone** select.

Regional / tax format fields (BR-20.2) are schema Literals on this PATCH (omit = no change; blank/invalid → **422**):
- `tax_jurisdiction` ∈ `GH` (same `TaxFilingJurisdictionValue` / `tax_filings.SUPPORTED` as filing Query; blank/unsupported → **422** — was free `str` with length-only late service **400**; unsupported codes could persist then fail later on filing). Company **Tax jurisdiction** select.
- `tax_filing_period` ∈ `monthly|quarterly`
- `date_format` ∈ `DD/MM/YYYY|MM/DD/YYYY|YYYY-MM-DD`
- `decimal_separator` ∈ `.|,`
- `thousand_separator` ∈ `,|.|space|""` (`none` coerces to `""`)
- `time_format` ∈ `12h|24h`

Company UI selects match. Service validators remain defense-in-depth **400** (and still require decimal ≠ thousand).

Company logo is managed separately via `POST|GET|DELETE /tenants/me/logo` (not a URL field on this patch).

**Print branding (BR-20.4):** `GET|PATCH /settings/print` — `{ header_text?, footer_text?, default_invoice_template?, default_receipt_paper? }`.  
`default_invoice_template` schema `Literal["a4","thermal"]` (omit = no change; blank/invalid → **422**).  
`default_receipt_paper` schema `Literal["58mm","80mm"]` (omit = no change; blank/invalid → **422**).  
Service `apply_print_branding_update` remains defense-in-depth **400**. Read path still coerces stored garbage to `a4` / `80mm`. Company page Invoice template / Receipt paper selects match.

### 3.4 Tenant Status Management
**List (platform):** `GET /tenants?status=` — Query `status` ∈ `trial`|`active`|`grace`|`suspended` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — was late **400**). Service `list_tenants` remains defense-in-depth. Platform console **Tenant status** chips (client filter over full cache; API also supports `?status=`).  
**Self-suspend:** `POST /tenants/me/suspend` — body `{ "reason" }` ∈ `TenantSuspendReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) for company_admin/super_admin; omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could persist). Stores `suspended_reason`, revokes sessions, emits `tenant.suspended`. Company page **Tenant suspend reason** (`aria-label`; no hardcoded `"Admin requested"`).  
**Suspend:** `POST /tenants/{tenant_ref}/suspend` — body `{ "reason" }` ∈ `TenantSuspendReasonValue` (same schema) → `status=suspended` + `suspended_reason`; sessions revoked; webhook `tenant.suspended`. Platform console **Tenant suspend reason** (`aria-label`; no `window.prompt`).  
**Activate:** `POST /tenants/{tenant_ref}/activate`  
(`tenant_ref` = id or slug; platform `platform_tenants:write` / legacy **super_admin** for cross-tenant)

**Allowed statuses:** `trial`, `active`, `grace`, `suspended`

### 3.4b Packages, subscription term & feature control (software owner)
**Catalog:** `GET /packages`  
**Assign term + package:** `POST /tenants/{tenant_ref}/subscription`

```json
{
  "package_code": "professional",
  "term_value": 12,
  "term_unit": "months",
  "activate": true
}
```

`package_code` schema `Literal["trial","starter","professional","enterprise"]` (strip/lower coerce; blank/invalid → **422**; no free-string accept). `term_unit` schema `Literal["months","years"]` (omit → `months`; blank/invalid → **422**; no silent months from `""`). Optional `start_at` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit/`null` → now; blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time; padded dates inconsistent). API `reports.parse_date` remains defense-in-depth. Platform **Subscription start date** input (`aria-label`); assign omits blank. Optional `max_stores_override` (int ≥ 0) sets a per-tenant store entitlement override; `clear_max_stores_override` clears it. Response includes `subscription` usage: months/years assigned, used, remaining, renewal date, effective `enabled_modules`, and store quota fields (`package_max_stores`, `effective_store_limit`, `stores_active`, …).

**Store entitlements:** Package catalog `max_stores` (`null` = unlimited). Platform `PATCH /tenants/{ref}/store-entitlement` `{ max_stores_override }` / `{ clear: true }`. Tenant admin `PATCH /tenants/me/store-limit` `{ store_limit }` (null = full entitlement; cannot exceed entitlement). `GET /stores/entitlement` returns usage. `POST /stores` and reactivate enforce active-store count (403 `STORE_LIMIT_REACHED`); downgrades never delete stores.

**Feature modules:** `PATCH /tenants/{tenant_ref}/modules`  
`{ "enabled_modules": ["dashboard","pos",...] }` or `{ "reset_to_package": true }`. `enabled_modules` items are schema `Literal` of `PACKAGEABLE_MODULES` (strip/lower; blank/unknown/`platform` → **422**). Always-on modules (`dashboard`, `notifications`, `security`) are merged by the service if omitted. Same item Literal applies on `POST /tenants/{ref}/subscription` when `enabled_modules` is sent.

**Usage detail:** `GET /tenants/{tenant_ref}/usage`  
Packages: `trial` | `starter` | `professional` | `enterprise`. Disabled modules return `403 PACKAGE_FEATURE_DISABLED`.

### 3.4c Platform staff & reports (software owner)
Platform roles: `super_admin` (legacy), `platform_owner`, `platform_admin`, `platform_support`, `platform_finance`.

**Staff:** `GET|POST /platform/staff`, `PATCH /platform/staff/{id}`, `GET /platform/roles`  
Create body `PlatformStaffCreate` (`extra=forbid`): `email` ∈ `EmailStr` (blank/`not-an-email`/`abc` → **422**; was free `str` with `min_length=3`); `full_name` ∈ `PlatformStaffFullNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str` min_length=1; whitespace/`!!!`/URL could persist; PATCH omit/`null` → no change); create/patch `role` uses the same platform-role schema `Literal` as grant (strip/lower; create omit → `platform_support`; blank/invalid → **422**; no silent support from `""` via former `role or "platform_support"`). `phone` ∈ `E164PhoneValue` (create omit/`null` → no phone; PATCH omit/`null` → no change; blank/`not-a-phone`/`123` → **422** — was free `str`; blank/garbage could persist). Platform Staff **Platform staff full name** + **Platform staff email** + **Platform staff phone** + **Create platform staff**.  
**App users (no dashboard yet):** `GET /platform/app-users`  
**Grant dashboard:** `POST /platform/staff/grant` `{ "user_id", "role": "platform_support" }` — promotes an existing workspace app user so they can open the software-owner console. `role` schema `Literal["super_admin","platform_owner","platform_admin","platform_support","platform_finance"]` (strip/lower coerce; omit → `platform_support`; blank/invalid → **422**; no silent support from `""`).  
**Revoke dashboard:** `POST /platform/staff/{id}/revoke` `{ "fallback_role": "company_admin" }` — removes platform role; account stays as an app user. `fallback_role` schema `Literal["company_admin","store_manager","sales_officer","inventory_officer","accountant","cashier"]` (strip/lower coerce; omit → `company_admin`; blank/invalid/platform → **422**; no silent company_admin from `""`).  
**Reports:** `GET /platform/reports` (bundle) or `/platform/reports/summary|subscriptions|packages|trials`

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

### 3.5z Email / SMTP settings (BR-20.3)
**Get:** `GET /settings/email` (`company_admin` / `super_admin`) — resolved status (`source`: `tenant` | `env` | `none`); never returns password (only `has_password`).  
**Patch:** `PATCH /settings/email` — typed body `EmailSettingsUpdate` (`extra=forbid`; unknown keys → **422**). Tenant SMTP override stored on `tenants.email_settings` (password encrypted as `password_enc`). Omit `password` to keep existing; `clear_password: true` removes it. Optional `from_email` ∈ `EmailStr`; omit/`null` → no change; blank/`not-an-email` → **422** (was free `str`; blank/garbage were accepted). Optional `host` ∈ `SmtpHostValue` (strip/lower; DNS hostname / IPv4 / `localhost`; no `://` / `@` / spaces); omit/`null` → no change; blank/`http://smtp…`/`not a host` → **422** (was free `str`; blank/garbage were accepted). Optional `from_name` ∈ `SmtpFromNameValue` (strip; 1–120 chars; at least one letter/digit; no `://` / `@`); omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage were accepted into tenant SMTP From display name). Optional `username` ∈ `SmtpUsernameValue` (strip; 1–200 chars; at least one letter/digit; no `://`; email-shaped logins OK); omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage were accepted into tenant SMTP username). Requires host + from_email for tenant override to take precedence over env. Company **Company SMTP host** + **Company SMTP username** + **Company from email** + **Company from name** + **Save email settings**.  
**Test:** `POST /settings/email/test` — optional `{ "to": "..." }` (`EmailStr`); uses resolved tenant/env config (console when unset).

```json
{
  "host": "smtp.example.com",
  "port": 587,
  "username": "noreply@example.com",
  "password": "secret",
  "from_email": "noreply@example.com",
  "from_name": "Acme ERP",
  "use_tls": true,
  "use_ssl": false
}
```

### 3.5z2 SMS / Twilio settings (BR-15.2)
**Get:** `GET /settings/sms` — resolved status (`source`: `tenant` | `env` | `none`); never returns auth token (only `has_auth_token`).  
**Patch:** `PATCH /settings/sms` — typed body `SmsSettingsUpdate` (`extra=forbid`; unknown keys → **422**). Tenant Twilio override on `tenants.sms_settings` (`auth_token_enc`). Omit `auth_token` to keep; `clear_auth_token: true` removes it. Optional `from_number` ∈ `E164PhoneValue` (`+` + 8–15 digits); omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`; blank/garbage were accepted). Optional `account_sid` ∈ `TwilioAccountSidValue` (strip; alphanumeric 1–64; not strict `AC`+32hex); omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage were accepted into tenant Twilio SID). Requires account_sid + from_number + token for tenant override. Company **Company SMS account SID** + **Company SMS from number** + **Save SMS settings**.  
**Test:** `POST /settings/sms/test` — optional `{ "to": "+233..." }` ∈ `E164PhoneValue` (`extra=forbid`); omit → profile phone; blank/invalid → **422**; console when unset.  
**Profile phone:** `PATCH /me` body `phone` ∈ `E164PhoneValue` (`ProfileUpdate`); omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`; blank silently cleared; garbage was late **400**). Company **Profile phone for SMS test** + **Save my phone**.

```json
{
  "account_sid": "ACxxxxxxxx",
  "auth_token": "secret",
  "from_number": "+15551234567"
}
```

### 3.5a Branches (BR-2.2)
**List:** `GET /branches` (`active_only=true` optional; `is_active=true|false` for Multi-Store manage filter)  
**Create:** `POST /branches` — `name` ∈ `BranchNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Multi-Store **Branch name** input.  
**Update:** `PATCH /branches/{branch_id}` — `name` ∈ `BranchNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**). Multi-Store **Edit branch name** input.

```json
{
  "code": "ACC",
  "name": "Accra Branch",
  "address": "Ring Road",
  "phone": "+233201111111",
  "email": "accra@example.com",
  "manager_id": "user_uuid"
}
```

PATCH supports `name`, `address` ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`; omit/`null` → no change; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently cleared; garbage could persist), `phone` ∈ `E164PhoneValue` (omit/`null` → no change; blank/`not-a-phone`/`123` → **422** — was free `str`; blank silently cleared; garbage could persist), `email`, `manager_id`, `clear_manager`, `is_active`. Create `address` / `phone` same (omit/`null` → no address/phone). Multi-Store **Branch address** + **Branch phone** inputs (`aria-label`s); create/edit omit blank address; create sends `null` phone when blank; edit omits blank phone. Deactivate with `is_active: false` (soft; row retained). Code is unique per tenant and immutable after create.

### 3.5a2 Departments (BR-2.5)
**List:** `GET /departments` (`branch_id`, `active_only` optional; `is_active=true|false` for Multi-Store manage filter)  
**Create:** `POST /departments` — `name` ∈ `DepartmentNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Multi-Store **Department name** input.  
**Update:** `PATCH /departments/{department_id}` — `name` ∈ `DepartmentNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**). Multi-Store **Edit department name** input.

```json
{
  "code": "SALES",
  "name": "Sales",
  "branch_id": "branch_uuid",
  "head_user_id": "user_uuid"
}
```

PATCH supports `name`, `branch_id`, `clear_branch`, `head_user_id`, `clear_head`, `is_active`. Soft-deactivate with `is_active: false`. Code unique per tenant.

### 3.5b Warehouses (BR-2.4)
**List:** `GET /warehouses` (`is_active=true|false` optional — Multi-Store manage filter; default returns all)  
**Get:** `GET /warehouses/{warehouse_id}`  
**Create:** `POST /warehouses` — `name` ∈ `WarehouseNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Multi-Store **Warehouse name** input.  
**Update:** `PATCH /warehouses/{warehouse_id}` — `name` ∈ `WarehouseNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); partial fields also include type/manager/address/capacity/store plus soft-deactivate via `is_active` (Multi-Store **Activate** / **Deactivate**; inactive hidden from Inventory/Reports pickers; stock movements, warehouse transfers, and PO warehouse assign return 400). Multi-Store **Edit warehouse name** input.

```json
{
  "name": "Cold Room A",
  "code": "WH-COLD-A",
  "warehouse_type": "cold_storage",
  "manager_id": "user_uuid",
  "address": "Zone 3, Industrial Area",
  "capacity": 1200.5,
  "store_id": null
}
```

`warehouse_type`: `retail` | `bulk` | `cold_storage` | `other` (schema `Literal`; omit on create defaults to `retail`; blank/invalid → **422**). PATCH supports `clear_manager`, `clear_store`, `clear_capacity`, `is_active`.

`address` (when sent) ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`); create omit/`null` → no address; PATCH omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently cleared on PATCH; garbage could persist). Multi-Store **Warehouse address** input (`aria-label`); create/edit omit blank.

---

## 4. User Management

### 4.1 Create User
**Endpoint:** `POST /users`

**Request:**
```json
{
  "email": "manager@acme.com",
  "full_name": "John Doe",
  "role": "store_manager",
  "branch_id": "br_001",
  "department_id": "dept_001",
  "record_scope": "branch",
  "phone": "+1-555-0199",
  "password": "TempPass123!"
}
```

`role` ∈ role key shape (`RoleKeyValue` / `custom_roles.ROLE_KEY_RE`; strip/lower; omit → `cashier`; blank/`A`/`Cashier!` → **422** — was free `str`; blank late **400**). Unknown role still service **400**. Users **User role** select.

`full_name` ∈ `UserFullNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; empty/whitespace/`!!!`/URL could persist). Users **User full name** input (`aria-label`); create requires trim.

`phone` (when sent) ∈ `E164PhoneValue` (`+` + 8–15 digits); omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** (was free `str`; blank/garbage could persist). Users **User phone** input (`aria-label`); create sends `null` when blank.

`record_scope` schema `Literal["own","department","branch","all"]` (omit = role default; blank/invalid → **422** — no silent `all` from `""`). Response wraps `{ "user": {...}, ... }`.

### 4.2 List Users
**Endpoint:** `GET /users` — optional `?is_active=true|false` filters soft-deactivated users (omit = all; Users manage status filter All/Active/Inactive).

### 4.3 Get User
**Endpoint:** `GET /users/{user_id}`

### 4.4 Update User
**Endpoint:** `PATCH /users/{user_id}`

Supports `full_name` ∈ `UserFullNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422** — was free `str`; empty/whitespace/`!!!`/URL could persist), `phone` ∈ `E164PhoneValue` (omit/`null` → no change; blank/`not-a-phone`/`123` → **422** — was free `str`; blank silently cleared; garbage could persist), `role` (same `RoleKeyValue`; omit = no change; blank/malformed → **422**), `password`, `is_active`, `branch_id`, `clear_branch`, `department_id`, `clear_department`, `record_scope` (same `Literal`, omit = no change; blank/invalid → **422**). Users row **Change role** select (`aria-label`).

### 4.5 Delete / Deactivate User
**Endpoint:** `DELETE /users/{user_id}` (soft deactivate)

### 4.6 Roles & Permissions

**List Roles:** `GET /roles` — system roles + **active** tenant custom roles (default `record_scope` on each row). Pass `?include_inactive=true` to include soft-deactivated custom roles (Users manage UI). Custom rows include `system: false`, `is_active`, `base_role`, and `id`. Users manage **Custom role status filter** All / Active / Inactive (`roleManageFilter`; client filter over full `include_inactive` cache). Assignment pickers stay active-only (except current role).

**Get Role:** `GET /roles/{role}` — system catalog entry or custom role (inactive custom roles still resolve).

**Create Custom Role:** `POST /roles` — company_admin / super_admin; `{ key, label, base_role? }` (`label` ∈ `CustomRoleLabelValue` strip; 1–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist; Users **Custom role label** input) or explicit `permissions` + optional `record_scope` (same `Literal`; omit = base_role/own default; blank/invalid → **422**). `key` ∈ same `RoleKeyValue` shape as user assign (strip/lower; blank/malformed → **422** — was free `str`; late **400**); system-key collision / `super_*` remain service **400**. `base_role` schema `Literal` of clonable system roles (platform_* + company_admin|store_manager|sales_officer|inventory_officer|accountant|cashier; strip/lower; omit/null OK when `permissions` set; blank/unknown/`super_admin` → **422**). Clones system `base_role` permission map when provided. `permissions` map modules ∈ assignable modules with actions ∈ `read`|`write`|`approve`|`*` (`ApiKeyPermissionAction`; strip/lower; unknown module|action / empty map / `*:*` / unknown top-level keys → **422** — was late service **400**). Body `extra=forbid`. Users **Create custom role** controls (`aria-label`s).

**Update Custom Role:** `PATCH /roles/{role}` — `{ label?, permissions?, record_scope? (same Literal), is_active? }` (`label` ∈ `CustomRoleLabelValue`; omit/`null` → no change; blank/`!!!`/`http://…` → **422**) (`extra=forbid`; same `permissions` honesty when sent). Soft-deactivate with `is_active: false` (Users UI **Activate** / **Deactivate**); inactive roles leave existing assignees intact but block new assignment (400). System roles are immutable (400).
**Delete Custom Role:** `DELETE /roles/{role}` — hard delete; returns **409** while any user still has that role. Prefer soft-deactivate for retirement.

**Available system roles:**
- `super_admin`
- `company_admin`
- `store_manager`
- `sales_officer`
- `inventory_officer`
- `accountant`
- `cashier`

---

## 5. Inventory & Products

### 5.1 Product Categories
**List:** `GET /catalog/categories` — tree order with `depth` and `path` (e.g. `Food › Soft Drinks › Colas`) (BR-5.1); optional `is_active=true|false` for Catalog manage All/Active/Inactive (default all)  
**Create:** `POST /catalog/categories` (`code`, `name`, optional `parent_id`, `tax_rate_id`) — `name` ∈ `CategoryNameValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Inventory Catalog **Category name** input.  
**Update:** `PATCH /catalog/categories/{category_id}` — `name` ∈ `CategoryNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); reparent via `parent_id` (null clears to root); rejects self-parent and cycles; soft-reactivate via `is_active: true` (Inventory Catalog **Activate**)  
**Delete:** `DELETE /catalog/categories/{category_id}` (soft deactivate `is_active=false`; Inventory **Deactivate**; inactive blocked on product create/PATCH; product create category picker hides inactive)

Inventory Catalog **Category tree** UI shows indented hierarchy + reparent picker; product create category select uses `path`.

Optional `tax_rate_id` on create/update (BR-12.1 / BR-2.8). Clear with `"tax_rate_id": null`. Resolve order for product lines: product `tax_rate_id` → category (walk `parent_id`, nearest wins) → tenant default tax rate → 0%.

### 5.2 Brands
**List:** `GET /catalog/brands` (`is_active=true|false` optional — Catalog manage filter; default returns all)  
**Create:** `POST /catalog/brands` `{ "code", "name", "description"? }` — `name` ∈ `BrandNameValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Inventory Catalog **Brand name** input. Optional `description` ∈ `BrandDescriptionValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no description; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently cleared / garbage could persist). Inventory Catalog **Brand description** input.  
**Update:** `PATCH /catalog/brands/{brand_id}` — `name` ∈ `BrandNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); `description` ∈ `BrandDescriptionValue` (omit/`null` → no change; blank/invalid → **422**); partial fields also include `is_active` (Inventory Catalog **Activate** when inactive)  
**Deactivate:** `DELETE /catalog/brands/{brand_id}` (soft `is_active=false`; Inventory **Deactivate**; inactive brands cannot be assigned on product create/PATCH)  
**Logo:** `POST|GET|DELETE /catalog/brands/{brand_id}/logo` (multipart `file` on POST; image types same as company logo)

Responses include `description`, `logo_url`, and `has_logo` (BR-5.1).

### 5.3 Units
**List:** `GET /catalog/units` (`is_active=true|false` optional — Catalog manage filter; default returns all)  
**Create:** `POST /catalog/units` — `name` ∈ `UnitNameValue` (strip; 1–80; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Inventory Catalog **Unit name** input.  
**Update:** `PATCH /catalog/units/{unit_id}` — `name` ∈ `UnitNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); partial fields also include conversion fields, `is_active` (Inventory Catalog **Activate** when inactive)  
**Deactivate:** `DELETE /catalog/units/{unit_id}` (soft `is_active=false`; Inventory **Deactivate**; inactive units cannot be assigned on product create/PATCH)  
**Convert preview:** `POST /catalog/units/convert` `{ "product_id", "quantity", "from_unit_id" }`

Create with conversion (BR-5.1): `{ "code": "CASE12", "name": "Case of 12", "base_unit_id": "<PCS id>", "conversion_ratio": 12 }`  
Meaning: 1 CASE12 = 12 × base unit. Stock ledger stays in `product.unit_id`.  
`POST /inventory/stock-in` / `stock-out` accept optional `unit_id` (entered UoM) and convert to stock units.

### 5.4 Products
**List:** `GET /products?category_id=&brand_id=&low_stock=true&is_active=true|false` — optional `is_active` filters soft-deactivated products (Inventory manage All / Active / Inactive UI; default returns all)  
**Create:** `POST /products` — `name` ∈ `ProductNameValue` (strip; 1–200; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Inventory **Product name** input. Optional `barcode` ∈ `ProductBarcodeValue` (strip + upper; `^[A-Za-z0-9\-._]{4,48}$`; omit/`null` → no barcode; blank/`!!!!`/`http://…`/`ab` → **422** — was free `str`; blank silently cleared; garbage late service **400**). Inventory **Product barcode** input. Optional `description` ∈ `ProductDescriptionValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no description; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently cleared / garbage could persist). Inventory **Product description** input. `tax_supply_class` schema `Literal["standard","zero_rated","exempt"]` (omit → `standard`; blank/invalid → **422**; no silent standard from garbage). `tax_exempt` is aligned to `exempt` class on write.  
**Get:** `GET /products/{product_id}`  
**Update:** `PATCH /products/{product_id}` — partial fields include `name` ∈ `ProductNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**), `sku`, `barcode` ∈ `ProductBarcodeValue` (omit/`null` → no change; blank/invalid → **422**), `description` ∈ `ProductDescriptionValue` (omit/`null` → no change; blank/invalid → **422**), prices, physical dims, tax flags (`tax_supply_class` same `Literal`, omit = no change; blank/invalid → **422**), and soft-deactivate via `is_active` (false hides from POS search and blocks new sale/PR/PO/PI lines; Inventory UI **Activate** / **Deactivate** + manage status filter; stock ops still allowed)  
**Delete:** `DELETE /products/{product_id}`

**Create Product Request:**
```json
{
  "name": "Organic Wheat Flour",
  "sku": "WF-ORG-5KG",
  "barcode": "8901234567890",
  "description": "Premium organic wheat flour",
  "category_id": "cat_001",
  "brand_id": "brand_001",
  "unit_id": "unit_001",
  "cost_price": 8.50,
  "selling_price": 12.99,
  "weight": 5.0,
  "length": 30,
  "width": 20,
  "height": 10,
  "tax_supply_class": "standard",
  "tracks_batches": false
}
```

`sku` is optional on create: omit or blank to auto-allocate `SKU-YYYY-NNNN` unique per tenant (products + variants). Explicit SKU is uppercased and must be unique (409 on clash). Same auto/manual rules apply to `POST /products/{id}/variants`.

**Variants:** `POST /products/{id}/variants` — `name` ∈ `VariantNameValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Inventory Variants **Variant name** input. Optional `barcode` ∈ `ProductBarcodeValue` (same pattern as product barcode; Inventory **Variant barcode** input). `PATCH /products/{id}/variants/{vid}` — `name` ∈ `VariantNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); `barcode` ∈ `ProductBarcodeValue` (omit/`null` → no change; blank/invalid → **422**).

Variant attributes (BR-5.1): `size`, `color`, `flavor`, `dosage` on `POST|PATCH /products/{id}/variants` (set to `null` on PATCH to clear). Soft-deactivate via `DELETE /products/{id}/variants/{vid}`; reactivate via `PATCH …/variants/{vid}` `{ is_active: true }` (Inventory Variants **Activate** / **Deactivate** + manage status filter All/Active/Inactive; `GET /products/{id}/variants?is_active=true|false` optional — omit = all; inactive variants excluded from sale/stock pickers).

Optional physical fields: `weight` (kg), `length` / `width` / `height` (cm). Also accepted on `PATCH /products/{id}` and CSV import columns.

Product responses include `stock_qty`, `reorder_level`, plus traffic-light fields `stock_status` (`green`|`yellow`|`red`) and `stock_status_label` (`ok`|`near_reorder`|`low`|`out_of_stock`) for Inventory list badges (BR-5.5). Rules: **red** when on-hand ≤ 0 or (reorder > 0 and on-hand ≤ reorder); **yellow** when reorder > 0 and on-hand ≤ reorder × 1.5; otherwise **green**.

**Barcode symbology (BR-5.1):**  
- `POST /products/{id}/barcode/generate?symbology=code128|ean13|upca&force=false` — Code 128 from SKU; EAN-13 / UPC-A allocate unique internal GTINs (prefixes `200` / `2`) with valid check digits. Response includes `symbology`. Query `symbology` is OpenAPI `Literal` (+ strip/lower); omit on generate → `code128`; blank/unknown → **422** (no silent `code128` from `""`). Service `normalize_symbology` remains defense-in-depth (**400**).  
- `GET /products/{id}/barcode.png?symbology=` — PNG render (auto-detects EAN-13/UPC-A from digits when omitted). Same Literal when provided.  
- `GET /products/{id}/barcode/label?copies=&symbology=` — printable HTML labels.  
- Variant equivalents: `POST|GET /products/{pid}/variants/{vid}/barcode/generate|png|label` (same symbology query params). Inventory Variants tab: barcode column + Generate/Label.  
Barcodes are unique across **products and variants** in the tenant (409 on clash). Assigning a 12/13-digit barcode via create/PATCH validates the check digit.

### 5.5 Stock Operations

**Stock In:** `POST /inventory/stock-in`

```json
{
  "product_id": "prod_001",
  "quantity": 12,
  "warehouse_id": "wh_001",
  "variant_id": "var_001",
  "unit_id": "unit_001",
  "notes": "Receive to main warehouse",
  "batch_number": "LOT-001",
  "manufacturing_date": "2026-01-01",
  "expiry_date": "2026-12-31"
}
```

Optional `warehouse_id` / `variant_id`. Optional `notes` ∈ `StockInNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist). Inventory Batches **Stock-in notes** input. Inventory Batches UI sends these; batch row persists warehouse + variant. Opening stock lines also accept `variant_id`.

```json
{
  "product_id": "prod_001",
  "variant_id": "var_001",
  "warehouse_id": "wh_001",
  "quantity": 100,
  "batch_number": "LOT-001",
  "manufacturing_date": "2026-07-01",
  "expiry_date": "2027-07-01",
  "notes": "Initial stock from PO-001"
}
```

Batch fields (`batch_number`, optional `manufacturing_date` / `expiry_date` ∈ `IsoDateQueryValue` — strip; `YYYY-MM-DD` or ISO datetime; omit/`null` → no batch dates; blank/`not-a-date`/`01/02/2024` → **422** — was free `datetime`; OpenAPI date-time; padded dates inconsistent) create/update a `product_batches` row; response includes serialized `batch`. Same date honesty on `POST /inventory/opening-stock` lines. API `reports.parse_date` remains defense-in-depth. Inventory **Stock-in manufacturing date** / **Stock-in expiry date** + **Opening stock manufacturing date** / **Opening stock expiry date** inputs (`aria-label`s); post sends `null` when blank.

**Stock Out:** `POST /inventory/stock-out`

```json
{
  "product_id": "prod_001",
  "variant_id": "var_001",
  "warehouse_id": "wh_001",
  "quantity": 5,
  "reference_type": "sale",
  "reference_id": "inv_001",
  "notes": "Sold via invoice INV-001"
}
```

`reference_type` required ∈ `{sale, transfer, adjustment, damage, internal, other}` (schema `StockOut` + `Literal`; no silent default to `other`; omit/blank/invalid → **422**). Inventory UI **Select reference type**. Optional `notes` ∈ `StockOutNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist). Inventory Stock Out **Stock-out notes** input. Optional `reference_id`, `warehouse_id`, `variant_id`, `unit_id`, `batch_id` (otherwise FEFO). Persists `stock_movements.reference_type` / `reference_id` with `movement_type=stock_out`. Inventory UI **Stock Out** tab.

**Warehouse Stock (BR-5.4):** `GET /inventory/warehouse-stock?warehouse_id=&include_zero=false` — per-warehouse on-hand + reorder policy (`inventory:read`). Response `items[]` include `quantity`, `reorder_level`, `reorder_qty`, `below_reorder`, `suggested_order_qty`, `consolidated_stock`. Inventory **Warehouse stock** tab.

**Warehouse reorder:** `PUT /inventory/warehouse-stock/reorder`

```json
{
  "warehouse_id": "wh_001",
  "product_id": "prod_001",
  "reorder_level": 10,
  "reorder_qty": 25
}
```

Creates/updates `warehouse_stocks` reorder fields for that warehouse (`inventory:write`). Store-scoped alias remains `PUT /stores/{store_id}/reorder-policy`.

**Stock Adjustment:** `POST /inventory/adjust/{product_id}` (BR-5.2)

```json
{
  "quantity": -2,
  "reason": "damage",
  "warehouse_id": "wh_001",
  "notes": "Water damage during storage"
}
```

`reason` required ∈ `{damage, theft, expiry, found, lost}` (schema `Literal`; no silent default to `damage`; omit/blank/invalid → **422**). Inventory UI **Select reason**. Optional `notes` ∈ `StockAdjustNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist). Inventory Adjust **Stock adjustment notes** input. Persists `stock_movements.reason` with `movement_type=adjustment`. Optional warehouse scope. Inventory UI **Adjust** tab. Filter movements with `reason=` on `/inventory/movements` and `/reports/inventory/movements` (Query `Literal`; blank/invalid → **422**).

**Stock Transfer (BR-5.2 / BR-5.4):** `POST /inventory/stock-transfers` (also `POST /stores/transfers`)

```json
{
  "from_warehouse_id": "wh_001",
  "to_warehouse_id": "wh_002",
  "submit": true,
  "notes": "Transfer to branch warehouse",
  "items": [{ "product_id": "prod_001", "quantity": 50 }]
}
```

Warehouse pair preferred for Inventory UI. Both warehouses must be linked to a store. Same-store warehouse pairs use **1-step** approval; different stores keep **dual** manager approval (BR-13.2). Store-only create still requires different `from_store_id` / `to_store_id` (warehouses derived). Optional `notes` ∈ `StockTransferNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist). Inventory Transfers **Stock transfer notes** input. Lifecycle: `submit` → `approve` (×1 or ×2) → `ship` → `receive` (also `reject` / `cancel`). **Reject / Cancel:** `POST /inventory/stock-transfers/{id}/reject|cancel` (and `/stores/transfers/{id}/…`) body `{ "reason" }` ∈ `StockTransferRejectReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) → status `cancelled` + `rejection_reason`. Omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could persist). Inventory + Multi-Store **Stock transfer reject reason** (`aria-label`; shared reject/cancel input). Inventory aliases under `/inventory/stock-transfers*` use `inventory:read|write`. Inventory **Transfers** tab. **Manage list status:** `GET /inventory/stock-transfers` + `GET /stores/transfers` optional Query `status` ∈ `draft`|`requested`|`in_transit`|`received`|`cancelled` (same `TransferReportStatusValue` as transfer report; omit → all; blank/invalid → **422**). Inventory + Multi-Store **Stock transfer status filter** (`transferManageFilter`; client filter over full cache).

### 5.6 Stock Count
**Create:** `POST /inventory/stock-counts` — optional `notes` ∈ `StockCountNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist). Inventory Counts **Stock count notes** input.  
**List:** `GET /inventory/stock-counts` — optional Query `status` ∈ `draft`|`completed`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Inventory Counts **Stock count status filter** All / Draft / Completed / Cancelled (`countManageFilter`; client filter over full cache).  
**Get:** `GET /inventory/stock-counts/{count_id}`  
**Update lines:** `PATCH /inventory/stock-counts/{count_id}/items` — body `{ "items": [{ "product_id", "counted_qty", "notes"? }] }` (`StockCountItemsUpdate` / `StockCountItemUpdate`). Optional line `notes` ∈ `StockCountItemNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit → no change; `null` → clear; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped via strip-to-None / garbage could persist; PATCH `exclude_unset` so omit ≠ null). Inventory Counts active draft **Stock count line notes** inputs.  
**Cancel:** `POST /inventory/stock-counts/{count_id}/cancel` `{ "reason": "..." }` — **reason** ∈ `StockCountCancelReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/blank/`!!!`/`http://…` → **422** (was free `str` `min_length=1` only — whitespace still reached service **400**; garbage could be appended to count `notes` / audit). Appended to count `notes` as `Cancel: …` and stored in audit `stock_count_cancelled.details.reason`; draft only → `cancelled` (`can_cancel`); no variance movements. Inventory Counts **Stock count cancel reason** (`aria-label`) + `Cancel stock count ${id}`.  
**Complete:** `POST /inventory/stock-counts/{count_id}/complete` — posts warehouse/product variance adjustments (`movement_type=adjustment`).

**Variance report (BR-5.2):** `GET /reports/inventory/stock-counts?from_date=&to_date=&warehouse_id=&store_id=&variance_only=true&status=completed` — completed counts with line variances (`expected_qty` / `counted_qty` / `variance`); default `variance_only=true` omits zero lines. Query `status` ∈ `draft`|`completed`|`cancelled` (schema Query `Literal` + strip/lower; omit → `completed`; blank/invalid → **422** — no silent empty filter or blank→all). Flat `lines[]` for export. Export type `inventory_stock_counts`. Reports Inventory **Count status** select.

**Request:**
```json
{
  "warehouse_id": "wh_001",
  "notes": "Month-end cycle count",
  "product_ids": ["prod_001"]
}
```

### 5.6a Opening Stock
**Create:** `POST /inventory/opening-stock`  
**List movements:** `GET /inventory/opening-stock`

Multi-line go-live / fiscal-year stock init with optional warehouse/batch/unit/`unit_cost` and optional Dr 1200 / Cr 3000 journal (`post_journal`). Optional `reference` ∈ `OpeningStockReferenceValue` (strip; 1–100; ≥1 letter/digit; no `://`/`@`; omit/`null` → auto `OS-YYYY-NNNN`; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently auto-numbered / garbage could persist). Optional header `notes` and per-line `OpeningStockLine.notes` ∈ `OpeningStockNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist); header + line notes merge onto movement notes. Inventory **Opening stock reference** / **Opening stock notes** / **Opening stock line notes** inputs.

**Numbering:** `GET|PATCH /inventory/settings` exposes `opening_stock_numbering` alongside `stock_transfer_numbering` / `stock_count_numbering`. Create allocates `{PREFIX}-{YYYY}-{NNNN}` (default `OS`) when `reference` is omitted; explicit references are kept. Allocated label is returned on the response, stored on the audit event, and used as the journal `reference` when a GL entry is posted (BR-5.2 / BR-20.4).

### 5.7 Stock Movement History
**Endpoint:** `GET /inventory/movements?product_id=&warehouse_id=&store_id=&movement_type=&created_by=&reason=&from_date=&to_date=`

Immutable audit trail (BR-5.3). No DELETE. Same payload shape as `GET /reports/inventory/movements` (`inventory:read`): each movement includes `product_sku` / `product_name`, `quantity_before` / `quantity_after`, `reason` (coded adjustment), and `created_by` / `created_by_name` / `created_by_email`. Query `movement_type` ∈ `stock_in`|`stock_out`|`opening_stock`|`adjustment`|`transfer_out`|`transfer_in`|`transfer_cancel` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — no silent empty filter). Query `reason` ∈ `damage`|`theft`|`expiry`|`found`|`lost` (same Literal pattern; omit → all; blank/invalid → **422**). Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Inventory UI **Movements** type + reason selects + **From/To date** controls.

### 5.8 Low Stock Alerts
**Endpoint:** `GET /inventory/low-stock` (also `GET /reports/inventory/low-stock` with optional `store_id` / `warehouse_id`)

Product + warehouse policy scans create `low_stock` notifications (`scan_low_stock` Celery job / stock-out hooks). Emails go to `inventory_officer`, `store_manager`, `company_admin`, and `super_admin` (default `low_stock.email=true`; opt out in notification settings). Per-store warehouse reorder: `PUT /stores/{store_id}/reorder-policy` (`reorder_level`, `reorder_qty`).

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "product_id": "prod_001",
        "product_name": "Organic Wheat Flour",
        "current_stock": 5,
        "minimum_stock": 20,
        "reorder_level": 30,
        "warehouse_id": "wh_001"
      }
    ]
  }
}
```

### 5.9 Set Stock Levels
**Endpoint:** `PATCH /products/{product_id}/stock-levels`

```json
{
  "warehouse_id": "wh_001",
  "minimum_stock": 20,
  "reorder_level": 30,
  "reorder_quantity": 100
}
```

---

## 6. Purchasing & Suppliers

### 6.1 Suppliers
**List:** `GET /suppliers`  
**Create:** `POST /suppliers` — required `name` ∈ `PartyNameValue` (strip; 1–180 chars; ≥1 letter/digit; no `://` / `@`); blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist). Purchasing **Supplier name** input (`aria-label`); create trims. `profile_type` schema `Literal` union (`registered|trade|manufacturer|service|other` for suppliers; blank/invalid → **422**; omit → `registered`). Kind allow-list still enforces supplier set (e.g. `walk_in` → **400**). `status` schema `Literal["active","inactive"]` (omit → `active`; blank/invalid → **422**). `phone` ∈ `E164PhoneValue` (omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** — was free `str`; blank/garbage could persist). Purchasing **Supplier phone** input (`aria-label`); create sends `null` when blank. `address` ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`; omit/`null` → no address; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Purchasing **Supplier address** input (`aria-label`); create sends `null` when blank.  
**Get:** `GET /suppliers/{supplier_id}`  
**Update:** `PATCH /suppliers/{supplier_id}` — partial fields include `name`, `status` (`active`|`inactive`), contacts profile (`profile_type` / `status` same Literals, omit = no change; blank → **422**; no silent `registered`); `phone` ∈ `E164PhoneValue` (omit/`null` → no change; blank/garbage → **422**); `address` ∈ `AddressValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); soft-deactivate via `status=inactive` (Purchasing **Activate** / **Deactivate**; inactive blocked on new PO / preferred-supplier PR / standalone PI; GRN/PO-linked invoices may still settle)  
**Delete:** `DELETE /suppliers/{supplier_id}`

List supports optional `?status=active|inactive` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — no late **400**). Purchasing Manage supplier filters All / Active / Inactive; PO/PR/PI pickers stay active-only. Party `code` is unique per tenant when set.
**Create Supplier:**
```json
{
  "name": "Global Supplies Inc",
  "code": "SUP-001",
  "profile_type": "manufacturer",
  "category": "packaging",
  "status": "active",
  "email": "jane@globalsupplies.com",
  "phone": "+1-555-0200",
  "address": "456 Supply Ave, Industrial City",
  "latitude": 5.6698,
  "longitude": -0.0166,
  "payment_terms_days": 30,
  "credit_limit": 0
}
```

List supports optional `?status=active|inactive` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Party `code` is unique per tenant when set.

**Contacts (BR-6.1):**  
`GET|POST /suppliers/{supplier_id}/contacts` — `name` ∈ `PartyContactNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Purchasing **Party contact name** input.  
`PATCH|DELETE /suppliers/{supplier_id}/contacts/{contact_id}` — PATCH `name` ∈ `PartyContactNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**)  

`phone` ∈ `E164PhoneValue` (omit/`null` → no phone on create / no change on PATCH; blank/`not-a-phone`/`123` → **422** — was free `str`; blank/garbage could persist). Purchasing **Party contact phone** input (`aria-label`); create sends `null` when blank.

`designation` ∈ `PartyContactDesignationValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; omit/`null` → no designation on create / no change on PATCH; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently None / garbage could persist). Purchasing **Party contact designation** input (`aria-label`); create sends `null` when blank.

```json
{ "name": "Ada Buyer", "phone": "+233200000001", "email": "ada@acme.example.com", "designation": "Purchasing", "is_primary": true }
```

First contact becomes primary; setting `is_primary` clears other primaries and syncs party `email`/`phone`. `GET /suppliers/{id}` includes `contacts`.

### 6.2 Purchase Request
**List:** `GET /purchasing/requests` — optional Query `status` ∈ `draft`|`pending`|`approved`|`rejected`|`converted` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Purchasing Requests **Purchase request status filter** (`prManageFilter`; client filter over full cache).  
**Create:** `POST /purchasing/requests` — optional `required_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit/`null` → no needed-by date; blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time; padded dates inconsistent). API `reports.parse_date` remains defense-in-depth. Optional header `notes` and per-line `PurchaseRequestItemCreate.notes` ∈ `PurchaseRequestNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist on PREQ / line notes). Purchasing **Purchase request required date** + **Purchase request notes** + **Purchase request line notes** inputs (`aria-label`s); create sends `null` when blank.  
**From low-stock suggestions:** `POST /purchasing/requests/from-low-stock` — typed body `LowStockSuggestionsCreate` `{ lines[], notes?, department?, include_open? }`. Header + nested `LowStockSuggestionLine.notes` ∈ `PurchaseRequestNotesValue` (omit/`null` → service default header note / no line notes; blank/`!!!`/`http://…` → **422** — was free `str`). Reports Inventory **Low-stock suggestion notes** + **Create draft PR from low-stock suggestions** (`aria-label`s; blank omitted as `null`).  
**Get:** `GET /purchasing/requests/{request_id}`  
**Approve:** `POST /purchasing/requests/{request_id}/approve`  
**Reject:** `POST /purchasing/requests/{request_id}/reject` — body `{ "reason" }` ∈ `PurchaseRequestRejectReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) → `rejection_reason` + audit `pr_rejected.details.reason`. Omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could persist). Purchasing UI **Purchase request reject reason** (`aria-label`; no hardcoded string) (BR-6.2).

**Numbering:** `GET|PATCH /purchasing/settings` exposes `purchase_request_numbering`. Create allocates `{PREFIX}-{YYYY}-{NNNN}` (default `PREQ`) — not a daily `R{yymmdd}-NNN` stamp (BR-6.2 / BR-20.4).

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
**List:** `GET /purchasing/orders` — optional Query `status` ∈ `draft`|`sent`|`partially_received`|`received`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Purchasing Orders **Purchase order status filter** (`poManageFilter`; client filter over full cache).  
**Create:** `POST /purchasing/orders`  
**Get:** `GET /purchasing/orders/{order_id}`  
**Update Status:** `PATCH /purchasing/orders/{order_id}/status`

**Create PO** (`POST /purchasing/orders`):
```json
{
  "supplier_id": "sup_001",
  "warehouse_id": "wh_001",
  "delivery_address": "Gate B, Tema Wharf",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 100,
      "unit_price": 8.50,
      "tax_rate": 10.0,
      "discount": 25.0
    }
  ],
  "notes": "Standard monthly order"
}
```

Optional `delivery_address` ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`); create omit/`null` → no ship-to; blank/`!!!`/`http://…` → **422** (was free `str`; blank silent→null; garbage could persist). Stored on the PO, returned on GET/list/serialize, amendable via `POST /purchasing/orders/{id}/amend`, and included in supplier email bodies when set (BR-6.3). Purchasing **PO delivery address** input (`aria-label`); create sends `null` when blank.

Optional `notes` ∈ `PurchaseOrderNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; create omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Amend uses the same type (`null` clears). Purchasing **PO notes** / **PO amend notes** inputs.

Per-line `discount` (≥0, cannot exceed qty×unit_price) is applied after tax on the line (same order as PI). `line_total` and PO `total_amount` reflect discounts; serialize/email include `discount`. Amend via `POST /purchasing/orders/{id}/amend`. Alembic `20260814_0096` (BR-6.3).

Omit `tax_rate` on a line to auto-resolve **product → category (parents) → tenant default** (same as sales; BR-12.2). Explicit `tax_rate` (including `0`) wins. Resolved `%` is snapshotted on the PO/PI line.

**Status Flow:** `draft` → `sent` → `partially_received` → `received` (Fully Received); branch to `cancelled`

**Cancel:** `POST /purchasing/orders/{po_id}/cancel` `{ "reason" }` ∈ `PurchaseOrderCancelReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Appended to PO `notes` as `Cancel: …` and stored in audit `po_cancelled.details.reason`; allowed for draft/sent with no receipts; blocked after any `received_qty` or when already `received`/`cancelled`. Serialize includes `can_cancel` + `notes`. Purchasing Orders **Purchase order cancel reason** (`aria-label`; BR-6.3).

**Send / resend:** `POST /purchasing/orders/{po_id}/send` — emails supplier (SMTP/console); draft → `sent`. Optional Query `to` ∈ `EmailStr`; omit → supplier email; blank/`not-an-email` → **422** (blank was silent fallthrough; garbage was accepted). Purchasing **Purchase order email override to** + **Email purchase order** / **Resend purchase order email**.

**Amend:** `POST /purchasing/orders/{po_id}/amend` — body may include `items` / `notes` / `delivery_address` ∈ `AddressValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently cleared; garbage could persist; Purchasing **PO amend delivery address** omits blank) / optional `due_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime; omit/`null` → no change; `clear_due_date=true` clears; blank/`not-a-date`/`01/02/2024` → **422** — was free `datetime`; OpenAPI date-time; padded dates inconsistent; Purchasing **PO amend due date** `aria-label`; amend omits blank; API `reports.parse_date` defense-in-depth) / `notify_supplier` / optional `to` ∈ `EmailStr` (blank/invalid → **422** when present); **`reason` required** (non-empty) → stored on `purchase_order_amendments.reason` + audit `po_amended.details.reason`. Purchasing Orders **Required amendment reason** UI + **PO amend email override to** (BR-6.3). Omit/blank reason → 422/400.

### 6.4 Goods Received Note (GRN)
**List:** `GET /purchases/grn`  
**Create:** `POST /purchases/grn` — optional `notes` ∈ `GrnNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist on GRN). Purchasing Orders receive **GRN notes** input (`aria-label`); Post GRN / Receive all send `null` when blank.  
**Get:** `GET /purchases/grn/{grn_id}`

Accepted lines stock via `stock_in_with_batch`. Optional per-line `batch_number`, `manufacturing_date` / `expiry_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit/`null` → no batch dates; blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time; padded dates inconsistent). Batch number required when the product `tracks_batches`. API `reports.parse_date` remains defense-in-depth. Serialize echoes batch fields from the GRN’s stock movements / `product_batches` (not stored on `goods_receipt_items`). Purchasing Orders receive UI **GRN manufacturing date** / **GRN expiry date** inputs (`aria-label`s; BR-6.4); post omits blank dates.

**Create GRN:**
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
      "batch_number": "LOT-2026-01",
      "manufacturing_date": "2026-01-15",
      "expiry_date": "2027-01-15"
    }
  ],
  "notes": "Delivery received in good condition"
}
```

`accepted_qty + rejected_qty` must equal `received_qty` (rejected may be inferred when omitted and accepted < received). `rejection_reason` is **required** when `rejected_qty > 0` (or inferred reject) — schema `model_validator` → **422** on omit/blank; service still 400 if reached. Only accepted qty is stocked; full `received_qty` reduces PO outstanding (BR-6.4).

### 6.5 Purchase Invoice
**List:** `GET /purchasing/invoices` — optional Query `status` ∈ `draft`|`unpaid`|`partial`|`paid`|`overdue`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Purchasing Invoices **Purchase invoice status filter** (`piManageFilter`; client filter over full cache).  
**Create:** `POST /purchasing/invoices` — optional `notes` ∈ `PurchaseInvoiceNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist). Purchasing **Purchase invoice notes** inputs (`aria-label`; from-GRN + manual); Draft sends `null` when blank.  
**Get:** `GET /purchasing/invoices/{invoice_id}`  
**Update draft:** `PATCH /purchasing/invoices/{invoice_id}` — draft only (409 otherwise). Body `PurchaseInvoiceUpdate` may include `supplier_invoice_number`, optional `notes` ∈ `PurchaseInvoiceNotesValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently cleared / garbage could persist), optional `invoice_date` / `due_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit/`null` → no change; blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time; padded dates inconsistent). API `reports.parse_date` remains defense-in-depth. Purchasing **Supplier invoice OCR** **Purchase invoice OCR date** + **Purchase invoice OCR notes** inputs (`aria-label`s); Apply omits blank date/notes.  
**Pay:** `POST /purchasing/invoices/{invoice_id}/payments`  
**Cancel:** `POST /purchasing/invoices/{invoice_id}/cancel` `{ "reason" }` ∈ `PurchaseInvoiceCancelReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Appended to invoice `notes` as `Cancel: …` and stored in audit `pi_cancelled.details.reason`; already-cancelled is idempotent; allowed for `draft` / `unpaid` / `overdue` when `paid_amount` is zero; reverses AP if posted. Serialize includes `can_cancel` + `notes`. Purchasing Invoices **Purchase invoice cancel reason** (`aria-label`; BR-6.5).

**Numbering:** `GET|PATCH /purchasing/settings` exposes `purchase_invoice_numbering` (`prefix`, `next_number`, `preview`) alongside PO/GRN. Create allocates `{PREFIX}-{YYYY}-{NNNN}` (default `PINV`) — not a timestamp (BR-6.5 / BR-20.4).

Create accepts header `discount_amount` and per-line `discount` (≥0). Line tax is computed on qty×unit_price before line discount; invoice `total_amount` subtracts header discount from gross (or from subtotal when reverse charge). Purchasing create forms + invoice detail show discounts (BR-6.5). PATCH does not update discounts.

Optional create `currency` ∈ 3-letter ISO (`CurrencyCodeValue | null`; strip/upper) — omit/`null` → tenant base via `resolve_rate`; blank/`EURO`/`gh` → **422** (was free `str`; blank silently became base). Optional `exchange_rate` (>0) pairs with non-base currency. Purchasing Invoices **Currency** input (`aria-label="Purchase invoice currency"`).

Manual PI lines omit `tax_rate` for catalog auto-resolve (BR-12.2); GRN-sourced invoices copy the PO line snapshot including proportional `items[].discount` (`accepted_qty / ordered_qty × PO line discount`). When header `discount_amount` is omitted/0 on from-GRN create, it defaults to the sum of those line discounts so `total_amount` matches negotiated PO economics; an explicit header discount overrides that default while line discounts still appear on lines (BR-6.5 / BR-6.3).

Response lines include `line_subtotal`, `line_tax`, and optional `tax_components`. Header includes `tax_amount` plus `tax_breakdown` (`by_rate`, `by_component`, `lines`) for display (BR-12.2). Purchasing → Invoices UI shows per-line tax and by-rate totals when an invoice number is selected.

### 6.6 Purchase Return
**List:** `GET /purchasing/returns` — optional Query `status` ∈ `draft`|`posted`|`cancelled` (same `ReturnReportStatusValue` as return report; omit → all; blank/invalid → **422**). Purchasing **Purchase return status filter** (`returnManageFilter`; client filter over full cache).  
**Create:** `POST /purchasing/returns` — body requires `goods_receipt_id`, coded `reason` ∈ `damaged` | `wrong_item` | `expiry` | `quality` | `other` (schema `Literal`; omit/blank/invalid → **422**), `items[]` with `goods_receipt_item_id` + qty, optional `notes` ∈ `PurchaseReturnNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Purchasing **Purchase return notes** input (`aria-label`); Draft return sends `null` when blank.  
**Get:** `GET /purchasing/returns/{return_id}`  
**Post:** `POST /purchasing/returns/{return_id}/post` — draft only; stock/AP/journal on post.  
**Cancel:** `POST /purchasing/returns/{return_id}/cancel` — body `{ "reason" }` ∈ `PurchaseReturnCancelReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Draft only → `status=cancelled`; appends `Cancel: …` to `notes` + audit `purchase_return_cancelled.details.reason`. Serialize includes `can_cancel`. Purchasing **Purchase return cancel reason** (`aria-label`; BR-6.6). No stock/AP on cancel.

**Create** requires `reason` ∈ `damaged` | `wrong_item` | `expiry` | `quality` | `other` (schema `Literal`; no silent default to `other`). Omit/blank/invalid → **422**; service still rejects unknown codes as defense in depth. Purchasing UI uses Select reason (BR-6.6).

**Numbering:** `GET|PATCH /purchasing/settings` exposes `purchase_return_numbering` and `debit_note_numbering`. Create allocates `{PREFIX}-{YYYY}-{NNNN}` for `return_number` (default `PR`); post allocates series `debit_note_number` (default `DN`, unique per tenant). Alembic `20260814_0097` (BR-6.6 / BR-20.4).

Line credits inherit proportional PO line discount (`return_qty / ordered_qty × PO line discount`, tax before discount). Serialize exposes `items[].discount` and header `discount_amount`; `total_amount` (and post AP/journal) uses the discounted credit. Purchasing Returns shows Discount (BR-6.6 / BR-6.3).

---

## 7. Sales & Customers

### 7.1 Customers
**List:** `GET /customers`  
**Create:** `POST /customers` — required `name` ∈ `PartyNameValue` (strip; 1–180 chars; ≥1 letter/digit; no `://` / `@`); blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist). Sales **Customer name** input (`aria-label`); create trims. `profile_type` schema `Literal` union (`walk_in|registered` for customers; blank/invalid → **422**; omit → `registered`). Kind allow-list still enforces customer set (e.g. `trade` → **400**). `status` schema `Literal["active","inactive"]` (omit → `active`; blank/invalid → **422**). `phone` ∈ `E164PhoneValue` (omit/`null` → no phone; blank/`not-a-phone`/`123` → **422** — was free `str`; blank/garbage could persist). Sales **Customer phone** input (`aria-label`); create sends `null` when blank. `address` ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`; omit/`null` → no address; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Sales **Customer address** input (`aria-label`); create sends `null` when blank.  
**Get:** `GET /customers/{customer_id}`  
**Update:** `PATCH /customers/{customer_id}` — partial fields include `name` ∈ `PartyNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); profile + `status` (`active`|`inactive`) (`profile_type` / `status` same Literals, omit = no change; blank → **422**; no silent `registered`); `phone` ∈ `E164PhoneValue` (omit/`null` → no change; blank/garbage → **422**); `address` ∈ `AddressValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**); soft-deactivate via `status=inactive` (Sales **Activate** / **Deactivate**; inactive blocked on new QT/SO/INV/POS; existing docs can still settle)  
**Delete:** `DELETE /customers/{customer_id}`

**Create Customer:**
```json
{
  "name": "Walk-in Customer",
  "code": "CUST-001",
  "profile_type": "walk_in",
  "status": "active",
  "email": "walkin@example.com",
  "phone": "+1-555-0300",
  "address": "789 Customer Lane",
  "latitude": 5.6037,
  "longitude": -0.187,
  "customer_group_id": null,
  "credit_limit": 500.00,
  "payment_terms_days": 30
}
```

List supports optional `?status=active|inactive` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — no late **400**). Sales Manage customer filters All / Active / Inactive; Sale/POS pickers stay active-only. Party `code` is unique per tenant when set.

**Contacts (BR-6.1):** same nested `/customers/{customer_id}/contacts` routes as suppliers; `GET /customers/{id}` includes `contacts`. Contact `name` ∈ `PartyContactNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist); PATCH omit/`null` → no change. Contact `phone` ∈ `E164PhoneValue` (omit/`null` OK; blank/garbage → **422**). Contact `designation` ∈ `PartyContactDesignationValue` (omit/`null` OK; blank/garbage → **422**). Sales/Purchasing **Party contact name** + **Party contact phone** + **Party contact designation** inputs (`aria-label`s); create sends trimmed name and `null` phone/designation when blank.

### 7.2 Customer Groups
**List:** `GET /customers/groups` (seeds Retail / Wholesale / VIP defaults; `is_active=true|false` optional — Sales manage All/Active/Inactive; default returns all)  
**Create:** `POST /customers/groups` — `name` ∈ `CustomerGroupNameValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Sales **Customer group name** input.  
**Update:** `PATCH /customers/groups/{group_id}` — `{ name?, discount_percent?, is_active? }` (`name` ∈ `CustomerGroupNameValue`; omit/`null` → no change; blank/`!!!`/`http://…` → **422**; soft-deactivate via `is_active=false`; Sales UI **Activate** / **Deactivate** + **Save discount** + manage status filter)
**Assign on customer:** `POST /customers` / `PATCH /customers/{customer_id}` with `customer_group_id` (inactive group → 400)  
**Preview price:** `GET /products/{product_id}/price?customer_id=&variant_id=`

When a sale/quote/order/POS line omits `unit_price`, list (or variant) price is used and the customer group's `discount_percent` is applied (active groups only). An explicit `unit_price` is treated as a cashier override.

### 7.3 Quotations
**List:** `GET /sales/quotations` — optional Query `status` ∈ `draft`|`sent`|`accepted`|`rejected`|`expired`|`converted` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Sales Quotations **Quotation status filter** (`quotationManageFilter`; client filter over full cache).  
**Create:** `POST /sales/quotations` — optional `notes` ∈ `SalesDocumentNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist). Sales **Sales document notes** input (`aria-label`); Create quotation sends `null` when blank.  
**Get:** `GET /sales/quotations/{quote_id}`  
**Send / resend:** `POST /sales/quotations/{quote_id}/send` — emails customer (SMTP/console); status → `sent`. Optional Query `to` ∈ `EmailStr`; omit → customer email; blank/`not-an-email` → **422** (blank was silent fallthrough; garbage was accepted). Sales **Document email override to** + **Email quotation** / **Resend quotation email**.
**Accept:** `POST /sales/quotations/{quote_id}/accept` — draft/sent only → `accepted`  
**Reject:** `POST /sales/quotations/{quote_id}/reject` — body `{ "reason" }` ∈ `SalesQuotationRejectReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) → `rejected` + `rejection_reason`. Omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could persist). Sales Quotations **Quotation reject reason** (`aria-label`; 409 if already accepted/rejected/converted/expired).  
**Convert to Order:** `POST /sales/quotations/{quote_id}/convert-order`  
**Convert to Invoice:** `POST /sales/quotations/{quote_id}/convert-invoice`

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

Create accepts header `discount_amount` and per-line `items[].discount` (≥0). Line tax is computed on qty×unit_price before line discount; document `total_amount` subtracts header discount. Sales **Create sale** UI exposes Line discount + Header discount for quotations, orders, and invoices; detail shows Discount column + KPI (BR-7.2 / BR-7.3 / BR-7.4).

### 7.4 Sales Orders
**List:** `GET /sales/orders` — optional Query `status` ∈ `draft`|`confirmed`|`processing`|`shipped`|`delivered`|`invoiced`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Sales Orders **Sales order status filter** (`orderManageFilter`; client filter over full cache).  
**Create:** `POST /sales/orders` — optional `notes` ∈ `SalesDocumentNotesValue` (same honesty as quotations/invoices; omit/`null` → no notes; blank/garbage → **422**). Sales **Sales document notes** input; Create order sends `null` when blank.  
**Get:** `GET /sales/orders/{order_id}`  
**Update Status:** `PATCH /sales/orders/{order_id}/status`  
**Convert to Invoice:** `POST /sales/orders/{order_id}/convert-to-invoice`

Optional create/confirm `delivery_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); create omit/`null` → no promised date; confirm omit/`null` → no change; blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time; padded dates inconsistent). API `reports.parse_date` remains defense-in-depth. Sales **SO delivery date** input (`aria-label`); create/confirm send `null` when blank.

Optional create/confirm `delivery_address` ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`); create omit/`null` → no ship-to; confirm omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank silent→null; garbage could persist). Sales **SO delivery address** input (`aria-label`); create sends `null` when blank; confirm omits blank. Confirm: `POST /sales/orders/{order_id}/confirm`.

**Numbering:** `GET|PATCH /sales/settings` exposes `sales_order_numbering`. Create (and quotation convert) allocates `{PREFIX}-{YYYY}-{NNNN}` (default `SO`) — not a timestamp stamp (BR-7.3 / BR-20.4).

**Cancel:** `POST /sales/orders/{order_id}/cancel` `{ "reason" }` ∈ `SalesOrderCancelReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Appended to order `notes` as `Cancel: …` and stored in audit `so_cancelled.details.reason`; allowed for `draft` / `confirmed` / `processing` (`can_cancel`); releases soft reservations; blocked after ship/deliver/invoiced. Sales Orders **Sales order cancel reason** (`aria-label`; BR-7.3).

**Status Flow:** `draft` → `confirmed` → `processing` → `shipped` → `delivered` → `invoiced`; branch to `cancelled`

### 7.5 Invoices
**List:** `GET /sales/invoices` — optional Query `status` ∈ `draft`|`posted`|`sent`|`partial`|`paid`|`overdue`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Sales Invoices **Sales invoice status filter** (`invoiceManageFilter`; client filter over full cache).  
**Create:** `POST /sales/invoices` — optional `notes` ∈ `SalesDocumentNotesValue` (same honesty as quotations/orders; omit/`null` → no notes; blank/garbage → **422**). Sales **Sales document notes** input; Create invoice sends `null` when blank.  
**Get:** `GET /sales/invoices/{invoice_id}`  
**Pay:** `POST /sales/invoices/{invoice_id}/payments`  
**Print:** `GET /sales/invoices/{invoice_id}/print` — query `template` ∈ a4|thermal (omit → company print branding default; blank/invalid → **422**); `format` ∈ pdf|text|json (omit → `pdf`; blank/invalid → **422**); `paper` ∈ 58mm|80mm for thermal (omit → branding default; blank/invalid → **422**, no silent branding fallback for garbage). Sales Print A4 / thermal controls.

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

Create accepts header `discount_amount` and per-line `items[].discount` (≥0) with the same tax-before-line-discount order as quotations/orders. Sales UI Create sale + invoice detail show discounts (BR-7.4).

**Send / resend:** `POST /sales/invoices/{invoice_id}/send` — emails customer (SMTP/console) for posted/sent/partial/paid/overdue; stamps `emailed_at`/`emailed_to`; unpaid → `sent` on first email. Optional Query `to` ∈ `EmailStr`; omit → customer email; blank/`not-an-email` → **422** (blank was silent fallthrough; garbage was accepted). Sales **Document email override to** + **Email invoice** / **Resend invoice email**.

Optional create `currency` ∈ 3-letter ISO (`CurrencyCodeValue | null`; strip/upper) — omit/`null` → tenant base via `resolve_rate`; blank/`EURO`/`gh` → **422** (was free `str`; blank silently became base). Optional `exchange_rate` (>0) pairs with non-base currency. Sales **Currency** input (`aria-label="Sales invoice currency"`).

**Cancel:** `POST /sales/invoices/{invoice_id}/cancel` `{ "reason" }` ∈ `SalesInvoiceCancelReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Appended to invoice `notes` as `Cancel: …` and stored in audit `invoice_cancelled.details.reason`; **draft only** (posted/sent/paid → 409). Sales Invoices **Sales invoice cancel reason** (`aria-label`; BR-7.4).

Optional header `is_reverse_charge: true` forces reverse-charge memo for all lines (tax excluded from customer total / `tax_amount`; stored on `reverse_charge_tax` and `sales_invoices.is_reverse_charge`). Same pattern as purchase invoices; Create sale checkbox. Rate-level RC still applies when header is false.

Response lines include `line_subtotal`, `line_tax`, optional `tax_components`, and `is_reverse_charge`. Header includes `tax_amount`, `reverse_charge_tax`, `is_reverse_charge`, plus `tax_breakdown` (`by_rate`, `by_component`, `lines`) for display (BR-12.2). Print JSON/PDF includes per-line tax amounts.

### 7.6 Sales Return
**List:** `GET /sales/returns` — optional Query `status` ∈ `draft`|`posted`|`cancelled` (same `ReturnReportStatusValue` as return report; omit → all; blank/invalid → **422**). Sales **Sales return status filter** (`returnManageFilter`; client filter over full cache).  
**Create:** `POST /sales/returns` — body requires `sales_invoice_id`, coded `reason` ∈ `damaged` | `wrong_item` | `defective` | `customer_change` | `other` (schema `Literal`; no silent default to `other`; omit/blank/invalid → **422**), `items[]` each with required `condition` ∈ `sellable` | `discard` (schema `Literal`; no silent default from `restock`; omit/blank/invalid → **422**), optional `restock`, optional `notes` ∈ `SalesReturnNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Restock on post only when `restock` and line `condition=sellable`. Sales UI uses **Select reason** + **Select condition** + **Sales return notes** (BR-7.5).  
**Get:** `GET /sales/returns/{return_id}`  
**Post:** `POST /sales/returns/{return_id}/post` — draft only; body optional `settlement_method` schema `Literal["adjust","refund"]` (omit OK — defaults to `adjust` when return ≤ open AR; blank/invalid → **422**; when return exceeds open AR, service still requires one of these → **400** `SETTLEMENT_REQUIRED`), `payment_method` schema `Literal["cash","bank_transfer","card","cheque"]` (omit → `cash`; blank/invalid → **422**), `liquid_account_id`. Sales UI **Post credit** / **Post + refund**.  
**Cancel:** `POST /sales/returns/{return_id}/cancel` — body `{ "reason" }` ∈ `SalesReturnCancelReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Draft only → `status=cancelled`; appends `Cancel: …` to `notes` + audit `sales_return_cancelled.details.reason`. Serialize includes `can_cancel`. Sales **Sales return cancel reason** (`aria-label`; BR-7.5).

**Numbering:** `GET|PATCH /sales/settings` exposes `sales_return_numbering` and `credit_note_numbering`. Create allocates `{PREFIX}-{YYYY}-{NNNN}` for `return_number` (default `SR`); post allocates series `credit_note_number` (default `CN`, unique per tenant). Sales Document numbering UI (BR-7.5 / BR-20.4).

**Create Return:**
```json
{
  "sales_invoice_id": "inv_001",
  "reason": "damaged",
  "restock": true,
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 1,
      "condition": "discard"
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

**Close Shift:** `POST /pos/sessions/{session_id}/close` — required `actual_cash` (≥0); optional `notes` ∈ `PosSessionCloseNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist on shift notes). POS **POS shift close notes** input (`aria-label`); Close shift sends `null` when blank.

```json
{
  "closing_cash": 850.50,
  "actual_cash": 845.00,
  "notes": "Minor discrepancy"
}
```

**Get Current Session:** `GET /pos/sessions/current`

**List Sessions:** `GET /pos/sessions` — optional Query `status` ∈ `open`|`closed` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). POS **POS shift status filter** All / Open / Closed (`shiftManageFilter`; client filter over full list cache).

**Shift Report:** `GET /pos/sessions/{session_id}/report` — sales list, `payment_breakdown`, `summary` (sale_count, subtotal, tax, discounts, net_sales, return_count, return_total, net_after_returns), and `returns[]` for the cashier/store during the shift window (BR-8.2).

### 8.2 POS Sale
**Create Sale:** `POST /pos/sales` — optional `customer_name` ∈ `PosCustomerNameValue` (strip; 1–180; ≥1 letter/digit; no `://`/`@`; omit/`null` → walk-in; blank/`!!!`/`http://…` → **422** — was free `str` max 180; blank/garbage could persist). POS **POS customer name** input. `payment_method` schema `Literal["cash","card","wallet","credit","other","split"]` (omit → `cash`; blank/invalid → **422**; no silent `other`). Wallet aliases `digital_wallet` / `mobile_money` / `momo` coerce to `wallet` before Literal check. Tender lines use `PosPaymentLine.payment_method` without `split`. Optional per-tender `PosPaymentLine.reference` ∈ `PaymentReferenceValue` (strip; 1–100; ≥1 letter/digit; no `://`/`@`; omit/`null` → no reference; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). POS **POS payment reference** input (`aria-label`; blank omitted; non-blank wraps the tender in `payments[]`). Service `normalize_payment_method` is strict by default (defense-in-depth **400**). `status` schema `Literal["completed"]` (omit → `completed`; blank/invalid → **422**; no garbage persist on `transactions.status`).

```json
{
  "session_id": "sess_001",
  "customer_id": "cust_001",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 2,
      "unit_price": 12.99,
      "discount": 0.50
    }
  ],
  "payment_method": "cash",
  "payments": [
    {
      "payment_method": "cash",
      "amount": 20.00
    },
    {
      "payment_method": "card",
      "amount": 5.48
    }
  ],
  "discount_total": 1.00,
  "tax_total": 2.49,
  "grand_total": 25.48,
  "notes": ""
}
```

### 8.3 Product Search
**Endpoint:** `GET /pos/products/search?q=flour&barcode=8901234567890`

### 8.4 Receipt Printing
**Endpoint:** `GET /pos/sales/{sale_id}/receipt`  
Query `format` ∈ json|text|pdf (omit → `json`; blank/invalid → **422**); `paper` ∈ 58mm|80mm (omit → company print branding default; blank/invalid → **422**). POS paper select.

**Send:** `POST /pos/sales/{sale_id}/receipt/send` — query `channel` ∈ email|sms (omit → `email`; blank/invalid → **422**; no silent email from `""`); `paper` ∈ 58mm|80mm (omit → `80mm`; blank/invalid → **422**); optional Query `to` typed by channel — email → `EmailStr`; sms → `E164PhoneValue`; omit → cashier email/phone; blank/`not-an-email`/`not-a-phone` → **422** (blank was silent fallthrough; garbage was accepted until soft send failure). POS **POS receipt override to** + Email / SMS buttons.

**Query Params (legacy note):** `?format=pdf&paper=80mm`

### 8.5 Cash Drawer
**Store settings:** `PATCH /stores/{store_id}/drawer` — body `StoreDrawerSettingsUpdate` `{ drawer_mode?, drawer_host?, drawer_port?, drawer_open_on_cash? }`. `drawer_mode` schema `Literal["none","mock","network","browser_bridge"]` (omit = no change; blank/invalid → **422**; no silent `none` from `""`). `drawer_host` ∈ `SmtpHostValue` (strip/lower; DNS hostname / IPv4 / `localhost`; no `://` / `@` / spaces); omit/`null` OK; blank/`http://…`/`not a host` → **422** (was free `str`; blank silent→null; garbage could persist). Service still requires host for `network` mode (**400**). Service `normalize_mode` remains defense-in-depth **400**. Multi-Store **Cash drawer host** input (`aria-label`; shown when Mode = network).  
**Get:** `GET /pos/sessions/{session_id}/drawer`  
**Open (manual):** `POST /pos/sessions/{session_id}/drawer/open` — body `{ "reason" }` required (min 3 chars; rejects placeholders like `manual` / `n/a`); POS **Drawer reason** input (no `window.prompt`). Auto-open on cash sale uses internal `pos_sale:{id}` reason.

---

## 9. Expense Management

### 9.1 Expense Categories
**List:** `GET /expenses/categories` (`is_active=true|false` optional — Expenses manage All/Active/Inactive; default returns all)  
**Create:** `POST /expenses/categories` — body `{ code, name, budget_amount?, account_id? }` (`name` ∈ `ExpenseCategoryNameValue` strip; 1–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Expenses **Expense category name** input. Response includes `budget_amount` / `is_active` / `account_id` / `account_code` / `account_name`  
**Update:** `PATCH /expenses/categories/{category_id}` — partial `{ name?, budget_amount?, is_active?, account_id?, clear_account? }` (`name` ∈ `ExpenseCategoryNameValue`; omit/`null` → no change; blank/`!!!`/`http://…` → **422**; monthly budget; optional expense-type GL for auto-post; soft-deactivate via `is_active=false`; BR-9.1 / BR-9.2). Approved expenses debit the category GL (else default `6000`). Inactive categories remain listed for reactivation (manage status filter); creating expenses/recurring with an inactive `category_id` returns 400. Expenses UI **Activate** / **Deactivate** + manage status filter.

### 9.2 Expenses
**List:** `GET /expenses` — optional Query `status` ∈ `pending`|`approved`|`rejected` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Expenses **Expense status filter** All / Pending / Approved / Rejected (`expenseManageFilter`; client filter over full `GET /expenses` cache).  
**Create:** `POST /expenses` — `payment_method` schema `Literal["cash","bank_transfer","card","cheque"]` (omit → `cash`; blank/invalid → **422**; aliases `check`→`cheque`, `credit_card`/`debit_card`→`card`, `bank`/`transfer`→`bank_transfer`). Service `normalize_expense_payment_method` remains defense-in-depth **400**. Expenses UI payment Method select matches. Optional `description` ∈ `ExpenseDescriptionValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → empty; blank/`!!!`/`http://…` → **422** — was free `str` default `""`; blank/garbage could persist). Expenses **Expense description** input. Optional `payee` ∈ `ExpensePayeeValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; omit/`null` OK; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Expenses **Expense payee** input. Optional `reference` ∈ `ExpenseReferenceValue` (strip; 1–100; ≥1 letter/digit; no `://`/`@`; omit/`null` → auto EXP-YYYY-NNNN; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently auto-numbered / garbage could persist). Expenses **Expense reference** input. Optional `expense_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit/`null` → today; blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time; padded dates inconsistent). API `reports.parse_date` remains defense-in-depth. Expenses **Expense date** input (`aria-label`); create sends `null` when blank.  
**Get:** `GET /expenses/{expense_id}`  
**Update:** `PATCH /expenses/{expense_id}` — pending or rejected only (409 if approved). Body may include `amount`, `payee` ∈ `ExpensePayeeValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**), `description` ∈ `ExpenseDescriptionValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**), `reference` ∈ `ExpenseReferenceValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**), `expense_date` ∈ `IsoDateQueryValue` (omit/`null` → no change; blank/`not-a-date`/`01/02/2024` → **422**), `payment_method` (same `Literal`, omit = no change; blank/invalid → **422**), `category_id` / `category`, org dims. Amount cannot change after a human approval step is recorded. Expenses UI **Edit** opens these fields (OCR **Apply to expense** uses the same PATCH; **Expense OCR date** `aria-label`; blank date omitted).

Optional org dims (`branch_id`, `department_id`; BR-9.2). Department must belong to the selected branch when both are set. `PATCH /expenses/{id}` accepts the same fields plus `clear_branch` / `clear_department`. Receipts use separate upload endpoints (not inline attachments on create).

**Attachments (BR-9.4):** `POST|GET|DELETE /expenses/{expense_id}/attachment` — multipart upload (PDF/image); GET returns file bytes (`Content-Disposition: attachment`). Expenses UI **Preview** loads the blob into an image/PDF modal (object URL); Download still forces save. Same Preview pattern on purchase-invoice and journal-entry attachments. OCR: `POST /expenses/{expense_id}/ocr-suggest`.

Pending expenses notify current-step matrix roles (BR-9.3): in-app `expense_approval` plus email (default on; opt out via notification preferences). Creator is excluded from the email fan-out. Advancing a level re-notifies the next step's roles.

**Approval settings:** `GET|PATCH /expenses/settings` — thresholds + `levels[]` (`ApprovalLevelUpdate`: `min_amount`, `roles[]`, `label?`). `roles[]` items ∈ system roles (`SystemRoleValue` / `rbac.VALID_ROLES`; strip/lower; blank/unknown → **422** — was late service **400**). Optional `label` ∈ `ApprovalLevelLabelValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; omit/`null` → no label; blank/`!!!`/`http://…` → **422** — was free `str`). Body `extra=forbid`. Expenses **Approval matrix** roles + label inputs (`aria-label`s + system-role datalist; blank label → `null`). Same `SystemRoleValue` + `ApprovalLevelLabelValue` honesty on `PATCH /purchasing/requests/settings` PR matrix (`PurchaseApprovalLevelUpdate`).

**Approve:** `POST /expenses/{expense_id}/approve` — body `{ "comment"? }` optional `comment` ∈ `ExpenseApproveCommentValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null`/empty body → no typed comment (service may still set a level-awaiting system note); blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist on `approval_comment`). Expenses UI **Expense approve comment** input (`aria-label`); Approve omits blank (no hardcoded `"Approved"`) → advances approval step or final `approved` + journal; no self-approve (except `super_admin`).  
**Reject:** `POST /expenses/{expense_id}/reject` — body `{ "reason" }` ∈ `ExpenseRejectReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) → `rejected` + `rejection_reason`. Omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could persist). Expenses UI **Expense reject reason** (`aria-label`; no hardcoded `"Rejected"`). Role-gated to the awaiting matrix step.

### 9.3 Recurring Expenses
**List:** `GET /expenses/recurring` — optional `?is_active=true|false` filters soft-deactivated schedules (omit = all; Expenses manage status filter).  
**Create:** `POST /expenses/recurring` — `payment_method` same expense `Literal` (omit → `bank_transfer`; blank/invalid → **422**). Optional `description` ∈ `ExpenseDescriptionValue` (omit/`null` → empty; blank/`!!!`/`http://…` → **422**). Optional `payee` ∈ `ExpensePayeeValue` (omit/`null` OK; blank/`!!!`/`http://…` → **422**). Expenses **Recurring description** + **Recurring payee** inputs.  
**Update:** `PATCH /expenses/recurring/{id}` — activate/deactivate (`is_active`) and/or edit template fields: `amount`, `payee` ∈ `ExpensePayeeValue` (+ `clear_payee`; omit/`null` → no change unless clear; blank/`!!!`/`http://…` → **422**), `description` ∈ `ExpenseDescriptionValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**), `payment_method` (same `Literal`, omit = no change; blank/invalid → **422**), `frequency`, `category_id` / `category`, org dims (`branch_id` / `department_id` + clear flags). Expenses UI **Edit schedule**. Existing generated expenses are unchanged; next Generate uses the updated template.  
**Skip next:** `POST /expenses/recurring/{id}/skip-next` — body `{ "reason" }` ∈ `RecurringSkipReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) → advance `next_run_at` by one frequency period without creating an expense; audit `recurring_expense_skipped` with `details.reason` (+ previous/new `next_run_at`). Omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could persist on audit). Reason is audit-only (schedule `description` unchanged). Inactive → 400; past `end_date` after skip deactivates. Expenses UI **Skip next reason** (`aria-label`).  
**Generate due:** `POST /expenses/recurring/generate` — creates expenses for active schedules with `next_run_at <= now` (also Celery beat `generate_recurring_expenses`)

**Create Recurring:**
```json
{
  "category_id": "exp_cat_001",
  "amount": 150.00,
  "frequency": "monthly",
  "description": "Recurring utility payment",
  "branch_id": "br_001",
  "department_id": "dept_001"
}
```

`frequency` ∈ `daily|weekly|monthly|yearly` (schema `Literal`; omit on create defaults to `monthly`; blank/invalid → **422**). Org dims on templates are copied onto expenses generated from the schedule. Generated expenses omit a forced reference so `expense_numbering` allocates `{PREFIX}-{YYYY}-{NNNN}` (default `EXP`); description is tagged `(recurring)` when needed. Expenses UI: Recurring expenses card (BR-9.5 / BR-9.2 / BR-20.4) including **Skip next** (typed reason required) and manage status filter All / Active / Inactive (`recurringManageFilter`; Generate remains active-only).

---

## 10. Accounting

### 10.1 Chart of Accounts
**List:** `GET /accounting/accounts` — optional `?is_active=true|false` (omit = all; Accounting manage status filter).  
**Create:** `POST /accounting/accounts`  
**Get:** `GET /accounting/accounts/{account_id}`  
**Update:** `PATCH /accounting/accounts/{account_id}` — partial fields include `name`, bank metadata, and soft-deactivate via `is_active` (Accounting COA **Activate** / **Deactivate**; inactive blocked on new journal lines, cash transfers, opening balances, expense-category GL, and liquid pickers).

**Account Types:** `asset`, `liability`, `equity`, `income`, `expense`

**COA opening balances (BR-10.1):** `POST /accounting/opening-balances` — body `{ "lines": [{ "account_id"|"account_code", "amount" }], "reference"?, "notes"? }`. Optional `reference` ∈ `OpeningBalanceReferenceValue` (strip; 1–100; ≥1 letter/digit; no `://`/`@`; omit/`null` → auto `COA-OPEN-YYYYMMDD`; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently auto-labeled / garbage could persist on journal `reference`). Optional `notes` ∈ `OpeningBalanceNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → default journal description; blank/`!!!`/`http://…` → **422** — was free `str`; blank fell through to default / garbage could persist on `JournalEntry.description`). Accounting Ledger **Opening balance reference** / **Opening balance notes** inputs. Status: `GET /accounting/opening-balances` (`posted` once per tenant; equity plug to 3000).

### 10.2 Journal Entries
**List:** `GET /accounting/journal-entries` — optional Query `status` ∈ `posted`|`unposted` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Accounting Ledger **Journal status filter** All / Posted / Unposted (`journalManageFilter`; client filter over full cache).  
**Create:** `POST /accounting/journal-entries` — body `description` ∈ `JournalDescriptionValue` (strip; 2–500 chars; ≥1 letter/digit; no `://` / `@`); blank/`!!!`/`http://…` → **422** (was free `str`; empty/garbage could persist on the ledger). Optional `reference` ∈ `JournalReferenceValue` (strip; 1–100; ≥1 letter/digit; no `://`/`@`; omit/`null` → no reference; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist). Optional body `entry_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit/`null` → now; blank/`not-a-date`/`01/02/2024` → **422** (was free `date`; OpenAPI date; padded dates inconsistent). API `reports.parse_date` remains defense-in-depth. Nested `lines[].description` ∈ `JournalLineDescriptionValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no line narrative; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist on `JournalEntryLine.description`). Accounting **Journal description** / **Journal reference** / **Journal entry date** / **Journal line N description** inputs (`aria-label`s); create sends `null` reference/entry_date/line description when blank.  
**Unpost:** `POST /accounting/journal-entries/{entry_id}/unpost` `{ "reason" }` ∈ `JournalUnpostReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Manual journals only; reverses account balances; appended to journal `description` as `Unpost: …` and stored in audit `journal_unposted.details.reason`; allowed only when `entry_date` is in the tenant’s current fiscal period (`tenants.fiscal_year_start` MM-DD) **and** not on/before `books_closed_through`. Auto-posted sources (`sales_invoice`, `coa_opening`, `cash_transfer`, …) are rejected. Accounting **Journal unpost reason** (`aria-label`; BR-10.2).  
**Attachment:** `POST|GET|DELETE /accounting/journal-entries/{entry_id}/attachment` — multipart `file` upload (PDF/image); tenant-scoped media key on `journal_entries.attachment_url`.

**Period close (BR-10.2):**
- `GET /accounting/period` — `fiscal_year_start`, current fiscal bounds, `books_closed_through`
- `POST /accounting/period/close` `{ "through_date": "YYYY-MM-DD", "reason": "..." }` — inclusive close; cannot be future; cannot move earlier (use reopen); **reason** ∈ `PeriodCloseReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/blank/`!!!`/`http://…` → **422** (was free `str` `min_length=1` only — whitespace still reached service **400**; garbage could land in audit `period_closed.details.reason`). Body `through_date` ∈ `IsoDateQueryValue` (required; strip; `YYYY-MM-DD` or ISO datetime); blank/`not-a-date`/`01/02/2024` → **422** (was bare `date`; OpenAPI date; padded dates inconsistent). API `reports.parse_date` + `as_calendar_date` defense-in-depth. Accounting **Period close through date** + **Period close or reopen reason** + **Close books** (`aria-label`s).
- `POST /accounting/period/reopen` `{ "through_date": null | "YYYY-MM-DD", "reason": "..." }` — clear or move closed-through earlier; **reason** ∈ `PeriodCloseReasonValue` (same honesty as close → **422** on blank/garbage); audit `period_reopened.details.reason`. Optional `through_date` ∈ `IsoDateQueryValue`; omit/`null` → clear; blank/invalid → **422**. Accounting **Reopen books** (`aria-label`).

Posting a journal (`POST /accounting/journal-entries`) rejects `entry_date` (default: now) on or before `books_closed_through` with **400**.

**Create Journal Entry:**
```json
{
  "reference": "JE-001",
  "description": "Adjusting entry for depreciation",
  "entry_date": "2026-08-01",
  "lines": [
    { "account_code": "6000", "debit": 40.00, "credit": 0.00 },
    { "account_code": "5000", "debit": 60.00, "credit": 0.00 },
    { "account_code": "1000", "debit": 0.00, "credit": 100.00 }
  ]
}
```

`lines` requires **≥2** rows; each line must have `account_id` or `account_code`, a non-zero debit **or** credit (not both), and Σ debit = Σ credit within ±0.01. Accounting Manual journal UI supports Add/Remove lines (default two) with live balance (BR-10.2). **Journal description** (`aria-label`) posts the typed narrative; optional **Journal entry date** (`aria-label`) posts `entry_date` or `null` when blank; optional per-line **Journal line N description** (`aria-label`) posts `lines[].description` or `null` when blank.

### 10.3 Cash & Bank Accounts
**List liquid:** `GET /accounting/liquid-accounts`  
**Create account:** `POST /accounting/accounts` — required `code` ∈ `AccountCodeValue` (strip; 1–30 chars; `^[A-Za-z0-9][A-Za-z0-9_-]{0,29}$`; no forced upper); blank/`!!!`/`a b`/`http://…` → **422** (was free `str`; blank late service **400**; garbage could persist as COA identity). Required `name` ∈ `AccountNameValue` (strip; 1–150 chars; ≥1 letter/digit; no `://` / `@`); blank/`!!!`/`http://…` → **422** (was free `str`; blank late service **400**; garbage could persist on COA). `account_type` schema `Literal["asset","liability","equity","income","expense"]` (omit → `asset`; blank/invalid → **422**); `liquid_kind` schema `Literal["cash","bank"] | null` (omit/null = non-liquid; blank/invalid → **422**; when set, account is forced to `asset`); optional `bank_name` ∈ `BankNameValue` (strip; 1–120 chars; at least one letter/digit; no `://` / `@`); omit/`null` OK; blank/`!!!`/`http://…` → **422** (was free `str`; blank silent→null then late service **400** when bank). Service still requires `bank_name` for bank accounts (**400**). Optional `account_number` ∈ `BankAccountNumberValue` (strip; alphanumeric + optional spaces/hyphens; max 64); omit/`null` OK; blank/`not-an-account`/`http://…` → **422** (was free `str`; blank silent→null; garbage could persist). Optional `bank_branch` ∈ `BankBranchValue` (strip; 1–120 chars; at least one letter/digit; no `://` / `@`); omit/`null` OK; blank/`!!!`/`http://…` → **422** (was free `str`; blank silent→null; garbage could persist). Accounting **Account code** + **Account name** + **Bank name** + **Bank account number** + **Bank branch** inputs (`aria-label`s; bank fields shown when Kind = bank); create omits blank bank_name / sends `null` account_number/branch when blank. PATCH `name` same honesty (omit/`null` → no change). Accounting **Edit account name** input (`aria-label`).  
```json
{ "code": "1001", "name": "Petty Cash", "liquid_kind": "cash" }
```
Bank example: `{ "code": "1011", "name": "Savings", "liquid_kind": "bank", "bank_name": "Acme Bank", "account_number": "123", "bank_branch": "Main" }`  
Expense example: `{ "code": "6100", "name": "Misc Expense", "account_type": "expense" }`

**Transfers / deposits / withdrawals:**  
- `GET /accounting/transfers` — optional Query `kind` ∈ `transfer`|`deposit`|`withdrawal` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Accounting Cash & Bank **Cash transfer kind filter** All / Transfer / Deposit / Withdrawal (`xferKindManageFilter`; client filter over full cache).  
- `POST /accounting/transfers` `{ "kind": "transfer|deposit|withdrawal", "from_account_id", "to_account_id", "amount", "reference", "notes" }` — `kind` schema `Literal` (omit → `transfer`; blank/invalid → **422**). Optional `reference` ∈ `CashTransferReferenceValue` (strip; 1–80; ≥1 letter/digit; no `://`/`@`; omit/`null` → auto `XFER-YYYY-NNNN`; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently auto-numbered / garbage could persist). Optional `notes` ∈ `CashTransferNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped / garbage could persist). Accounting **Cash transfer reference** / **Cash transfer notes** inputs.  
- `GET /accounting/transfers/{id}`  

**Numbering:** `GET|PATCH /accounting/settings` exposes `cash_transfer_numbering` alongside `journal_numbering`. Create allocates `{PREFIX}-{YYYY}-{NNNN}` (default `XFER`) when `reference` is omitted; explicit references are kept. Journal line `reference` uses the same value (BR-10.3 / BR-20.4). Nested `prefix` ∈ `DocumentPrefixValue` (strip + upper; `^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$`); blank/`!!!`/`JE!`/`a b` → **422** (was free `str`; service `normalize_prefix` late **400**). Accounting **Journal number prefix** / **Cash transfer number prefix** inputs (`aria-label`s).

`transfer` requires two distinct liquid accounts (Dr destination / Cr source).  
`deposit` credits Owner's Equity `3000` into a liquid account; `withdrawal` is the reverse.

**Cheques (BR-10.4):**  
**List:** `GET /accounting/cheques` — optional Query `direction` ∈ `received`|`issued`; `status` ∈ `pending`|`deposited`|`cleared`|`bounced`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — no silent empty list from garbage). Accounting Cheques **Direction** / **Status** filters.  
**Deposit / Clear:** `POST /accounting/cheques/{id}/deposit|clear`  
**Bounce / Cancel:** `POST /accounting/cheques/{id}/bounce|cancel` — body `{ "reason" }` ∈ `ChequeLifecycleReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) — omit/blank/`!!!`/`http://…` → **422** (was free `str` with `min_length=1` only; whitespace still reached service **400**; garbage could be appended). Appended to notes (`Bounce:` / `Cancel:`) + journal description. Accounting Cheques **Cheque bounce cancel reason** (`aria-label`; BR-10.4).

**Bank feed connections (reconcile):**  
**List:** `GET /accounting/bank-connections` — optional `?is_active=true|false` filters soft-deactivated connections (omit = all; Accounting Reconcile manage status filter).  
**Create:** `POST /accounting/bank-connections` — `{ account_id, provider: mock|http_json, display_name?, external_account_id?, feed_url?, access_token?, auto_sync?, auto_match_after_sync?, sync_lookback_days? }` — optional `display_name` ∈ `BankConnectionDisplayNameValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; omit/`null` OK; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Accounting Reconcile **Bank connection display name** input. `provider` schema `Literal` (omit → `mock`; blank/invalid → **422**; `mock` blocked in production at service layer); optional `feed_url` ∈ `WebhookUrlValue` (absolute `http(s)`; `http` only for localhost; omit/`null` OK for `mock`; blank/`ftp://`/`not-a-url`/plain-http remote → **422** — was free `str`; garbage could persist; `http_json` still requires URL at service **400**). Accounting Reconcile **Bank feed URL** input.  
**Update:** `PATCH /accounting/bank-connections/{connection_id}` — partial fields include display/feed settings (`provider` same `Literal`, omit = no change; blank/invalid → **422**; `feed_url` same `WebhookUrlValue` honesty, omit/`null` = no change) and soft-deactivate via `is_active` (Accounting Reconcile **Activate** / **Deactivate** + manage status filter All/Active/Inactive; inactive connections skip Celery auto-sync and Sync returns **400**) Optional `display_name` ∈ `BankConnectionDisplayNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422`).
**Delete:** `DELETE /accounting/bank-connections/{connection_id}` — hard remove  
**Sync:** `POST /accounting/bank-connections/{connection_id}/sync` — imports into a reconcilable bank statement (dedupe by external ref); rejected when connection is inactive  
**Auto-clear:** `POST /accounting/bank-statements/{statement_id}/auto-clear` — body `{ "min_confidence"?, "date_window_days"? }`. `min_confidence` schema `Literal["high","medium","low"]` (strip/lower; omit → `high`; blank/invalid → **422**; no silent high from `""`/garbage). Service `apply_auto_matches` remains defense-in-depth (**400**). Accounting Reconcile **Auto-clear high confidence** / **medium+** buttons.  
**Match line:** `POST /accounting/bank-statements/{statement_id}/lines/{line_id}/match` — typed body `BankStatementMatchBody` `{ "journal_line_id" }` (`extra=forbid`; blank/omit/unknown keys → **422** — was free `dict` that turned omit/`""` into late **404**). Service `match_line` remains defense-in-depth.  
**Clear group:** `POST /accounting/bank-statements/{statement_id}/clear-group` — typed body `BankClearGroupBody` `{ "statement_line_ids", "journal_line_ids", "notes"? }` (`extra=forbid`; empty either id list / unknown keys → **422** — was late **400**). Optional `notes` ∈ `BankClearGroupNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist on clearing group). Accounting Reconcile **Clear-group notes** input. Service `create_clearing_group` remains defense-in-depth.  
**Create statement:** `POST /accounting/bank-statements` — typed body `BankStatementCreateBody` `{ "account_id", "statement_date"?, "opening_balance"?, "closing_balance"?, "notes"?, "lines"? }` (`extra=forbid`; nested `BankStatementLineCreate` also `extra=forbid`). Blank/omit `account_id` / unknown keys / zero line `amount` → **422** (was free `dict` with late **404**/**400**). Optional `statement_date` + line `txn_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → today / line default; blank/invalid → **422** — blank was silent default; invalid was uncaught **500**). Optional `notes` ∈ `BankStatementNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped via strip-to-None / garbage could persist). Optional line `description` ∈ `BankStatementLineDescriptionValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no description; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped via strip-to-None / garbage could persist). Optional line `external_ref` ∈ `BankStatementLineExternalRefValue` (strip; 1–120; ≥1 letter/digit; no `://`/`@`; omit/`null` → no ref; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently dropped via strip-to-None / garbage could persist; max 120 matches column). Accounting Reconcile **Create bank statement** controls (`aria-label` account/opening/closing/statement date/line amount/description/external ref/notes/txn date/create).  
**Import statement:** `POST /accounting/bank-statements/import?account_id=&opening_balance=&closing_balance=&statement_date=` + multipart `file` — Query `statement_date` ∈ `IsoDateQueryValue` (omit → max line txn date / today; blank/invalid → **422** — invalid was uncaught **500**). Accounting Reconcile import file control.  
**List statements:** `GET /accounting/bank-statements` — optional Query `status` ∈ `draft`|`in_progress`|`reconciled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Accounting Reconcile **Bank statement status filter** All / Draft / In progress / Reconciled (`statementManageFilter`; client filter over full cache).

### 10.4 Financial Reports
**Profit & Loss:** `GET /accounting/profit-loss` (also `/reports/profit-loss`) — returns `revenue`, `cogs` (account 5000), `gross_profit`, `operating_expenses`, `expense` (total), `net_profit`. COGS is posted automatically on sales invoice post / POS sale (Dr 5000 / Cr 1200 at standard `cost_price` × stock qty); restocked sales returns reverse COGS. Optional query params: `from_date`, `to_date`, `store_id`, `branch_id`. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Accounting **P&L From/To date** + Reports shared **Report From/To date** controls. With no filters, response uses lifetime income/expense account balances (`mode=balances`). With any filter, aggregates posted journal lines (`mode=journals`); store/branch keep only attributable `sales_invoice` / `pos_sale` / `expense` / `sales_return` journals.

**Balance Sheet:** `GET /reports/balance-sheet` (also `/accounting/balance-sheet`) — assets / liabilities / equity + computed retained earnings; `balanced` when Assets = Liabilities + Equity. Optional `as_of` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → live balances; blank/invalid → **422** — blank was silent live; invalid was late service **400**). Optional `compare` ∈ prior_period|prior_year (schema Query `Literal` + strip/lower; omit → no compare; blank/invalid → **422**). Adds prior balances and deltas on each row plus summary `compare.deltas`. Same `compare` Literal on `GET /reports/export?report_type=balance_sheet`. Reports **Report as of date** + Balance sheet compare select.  
**Cash Flow:** `GET /reports/cash-flow?from_date=&to_date=&store_id=&branch_id=` — liquid cash/bank GL movements with back-compat `inflows`/`outflows`/`net` plus sections `operating` / `investing` / `financing` / `transfers` (each `{inflows,outflows,net}`). Lines include `activity`. Classification by journal `source_type` (`cash_transfer` deposit/withdrawal → financing; liquid↔liquid transfer → `transfers`; payments/POS/expenses → operating; `coa_opening` → financing). Investing reserved for future CapEx sources. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Optional `store_id` / `branch_id` keep attributable journals only (expenses / POS / sales returns / customer payments on store invoices); HQ `cash_transfer` / `coa_opening` omitted when filtered. Response echoes `store_id`/`branch_id`/`mode`. Export `cash_flow` accepts the same filters. Reports shared **Report From/To date** controls. 
**Trial Balance:** `GET /accounting/trial-balance` (also `/reports/trial-balance`) — optional `as_of` ∈ `IsoDateQueryValue` (same honesty as Balance Sheet; omit → live balances; blank/invalid → **422**). Response includes `as_of`, `mode`, `rows`, `total_debit`, `total_credit`, `balanced`. Accounting **Trial balance as of date** + Reports **Report as of date** controls. Export: `report_type=trial_balance` with the same `as_of` (or `to_date`/`date`).

---

## 11. Credit Management

**Aging:** `GET /credit/aging` — Query `kind` ∈ `receivable`|`payable` (schema Query `Literal` + strip/lower; omit → `receivable`; blank/invalid → **422** — no silent AR aging for `Payable`/`""`/garbage). Returns bucketed totals + rows for AR or AP. Credit UI **Receivables** / **Payables** toggle. Requires `credit:read`.

**Exchange rates (BR-2.6):** `GET /credit/exchange-rates`; `PUT /credit/exchange-rates/{currency_code}` body `{ currency_code, rate_to_base }` (`extra=forbid`); `DELETE /credit/exchange-rates/{currency_code}`; `POST /credit/exchange-rates/refresh` optional `{ currencies[] }`; `PATCH /credit/exchange-rates/settings`. Path + body `currency_code` (and refresh list items) ∈ 3-letter ISO (`CurrencyCodeValue`; strip/upper; blank/non-ISO → **422** — was late service **400**). Credit **Exchange rates** controls (`aria-label`s).

### 11.1 Customer Credit
**Get Credit Info:** `GET /customers/{customer_id}/credit` — `credit_limit`, `outstanding_balance`, `available_credit` (`null` when unlimited/`credit_limit<=0`), `is_over_limit`, `credit_sales[]` open invoices. Requires `credit:read`.

**Credit limit enforcement / override (BR-11.1):** posting a sales invoice, POS credit checkout, or legacy `POST /sales` that would push `balance + amount` above `credit_limit` returns `409` with `detail.code = CREDIT_LIMIT_EXCEEDED` (includes `over_by`, balances). Retry with body:
```json
{ "override_credit_limit": true, "override_reason": "Approved by store manager" }
```
Requires `credit:approve` (store_manager, accountant, company_admin / `*`). Otherwise `403` `CREDIT_OVERRIDE_FORBIDDEN`. When `override_credit_limit` is true, **`override_reason` is required** (non-empty) — schema `model_validator` → **422** on omit/blank; service still returns `400` `CREDIT_OVERRIDE_REASON_REQUIRED` if reached. Successful overrides set `credit_limit_overridden: true` and write audit `credit_limit_override` with `details.reason`. Sales Invoices + POS UIs require a typed **Credit override reason** (no canned `window.prompt` default).

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

**Record Payment:** `POST /customers/{customer_id}/payments` — `payment_method` schema `Literal["cash","bank_transfer","card","cheque"]` (omit → `cash`; blank/invalid → **422**; same aliases as expenses). Optional `reference` ∈ `PaymentReferenceValue` (strip; 1–100; ≥1 letter/digit; no `://`/`@`); omit/`null` → no reference; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist on `CustomerPayment.reference`). Optional `notes` ∈ `PaymentNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null` → no notes; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist on `CustomerPayment.notes`). Optional `cheque_number` ∈ `ChequeNumberValue` (strip; alphanumeric + optional spaces/hyphens; max 50); omit/`null` → service falls back to reference/payment_number; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist). Optional `bank_name` ∈ `BankNameValue` (strip; 1–120 chars; at least one letter/digit; no `://` / `@`); omit/`null` OK; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist). Optional `cheque_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit/`null` OK; blank/`not-a-date`/`01/02/2024` → **422** — was free `datetime`; padded dates rejected; Credit UI never set → always null). Optional `currency` ∈ 3-letter ISO (`CurrencyCodeValue | null`; omit/`null` → invoice/base via `resolve_rate`; blank/non-ISO → **422** — was free `str`; blank silently base). Also `POST /sales/payments` with the same `CustomerPaymentCreate` body. Credit UI Method select matches; **Payment reference** + **Payment notes** inputs (`aria-label`s); **Payment cheque number** + **Payment cheque bank name** + **Payment cheque date** when Method = cheque; **Record payment** sends `null` when blank. Service `normalize_expense_payment_method` / `normalize_currency` remain defense-in-depth **400**; API `reports.parse_date` for cheque_date.  
**Customer History:** `GET /customers/{customer_id}/history?from_date=&to_date=` — purchase history (sales invoices + POS), returns, and payments with `summary` totals (BR-7.1). Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Credit **History From/To date** inputs (`aria-label`s).

```json
{
  "amount": 100.00,
  "payment_method": "cash",
  "date": "2026-08-07",
  "reference": "RCP-001",
  "notes": "Partial payment for INV-001"
}
```

### 11.2 Supplier Credit
**Get Credit / Balance:** `GET /suppliers/{supplier_id}/credit` — `outstanding_balance`, `open_bills[]` (PIs + uninvoiced POs). Requires `credit:read`.  
**Get Outstanding Bills:** `GET /suppliers/{supplier_id}/outstanding`  
**Supplier History:** `GET /suppliers/{supplier_id}/history?from_date=&to_date=` — purchase history (POs + purchase invoices), returns, and payments with `summary` totals (BR-6.1). Same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty. Credit **History From/To date** inputs (`aria-label`s).

**Payment Schedule:** `GET /suppliers/{supplier_id}/payment-schedule` — open purchase invoices + uninvoiced POs sorted by `due_date` ascending; each row includes `balance_due`, `days_until_due`, `days_overdue`, optional `early_discount` quote when tenant early-pay settings apply. Response also has `total_due`, `upcoming_count`, `overdue_count`. Requires `credit:read`.

**Due notifications:** Celery / `POST /notifications/scan-due` runs `scan_payment_due` for both AR sales invoices and AP purchase invoices within the horizon (default 3 days), creating `payment_due` notifications (`entity_type=purchase_invoice` for bills), `scan_quotation_expiry` for draft/sent quotations with `valid_until` within 1 day (category `quotation_expiry`, `entity_type=sales_quotation`; past-due rows are flipped to `status=expired`), and `scan_recurring_expense_due` for active recurring schedules with `next_run_at` within 1 day (category `recurring_expense_due`, `entity_type=recurring_expense`; BR-9.5).

**Record Payment:** `POST /suppliers/{supplier_id}/payments` — `payment_method` schema `Literal["cash","bank_transfer","card","cheque"]` (omit → `bank_transfer`; blank/invalid → **422**; same aliases). Optional `reference` ∈ `PaymentReferenceValue` (omit/`null` → no reference; blank/garbage → **422**; same honesty as customer payments). Optional `notes` ∈ `PaymentNotesValue` (omit/`null` → no notes; blank/garbage → **422**; same honesty as customer payments). Optional `cheque_number` ∈ `ChequeNumberValue` (omit/`null` OK; blank/garbage → **422**; same honesty as customer payments). Optional `bank_name` ∈ `BankNameValue` (omit/`null` OK; blank/garbage → **422**; same honesty as customer payments). Optional `cheque_date` ∈ `IsoDateQueryValue` (omit/`null` OK; blank/garbage → **422**; same honesty as customer payments). Optional `currency` ∈ 3-letter ISO (`CurrencyCodeValue | null`; omit/`null` → invoice/base; blank/non-ISO → **422** — was free `str`; blank silently base). Credit UI Method select matches; **Payment reference** + **Payment notes**; **Payment cheque number** + **Payment cheque bank name** + **Payment cheque date** when Method = cheque; **Record payment** sends `null` when blank.

---

## 12. Tax Management

### 12.1 Tax Rates
**List:** `GET /tax/rates` (`is_active=true|false` optional — Tax manage All/Active/Inactive; default returns all)  
**Create:** `POST /tax/rates` — `name` ∈ `TaxRateNameValue` (strip; 1–80; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Tax **Tax rate name** input. `tax_type` schema `Literal["vat","gst","sales_tax","custom"]` (omit → `vat`; blank/invalid → **422**); `pricing_mode` schema `Literal["exclusive","inclusive"]` (omit → `exclusive`; blank/invalid → **422**; no silent exclusive for unknown modes). Optional `components[]` typed `TaxComponent` (`extra=forbid`; `rate` ≥0; `basis` ∈ `net`|`compound` strip/lower, omit→`net`; optional `code`/`name`; blank/invalid basis / unknown keys → **422** — was free `list[dict]`; blank basis silently `net`; bad basis late **400**). Tax **Tax rate components JSON** textarea.  
**Get:** `GET /tax/rates/{rate_id}`  
**Update:** `PATCH /tax/rates/{rate_id}` — `{ name?, rate?, tax_type?, pricing_mode?, components?, is_reverse_charge?, is_active? }` (`name` ∈ `TaxRateNameValue`; omit/`null` → no change; blank/`!!!`/`http://…` → **422**; `tax_type` / `pricing_mode` same Literals, omit = no change; blank/invalid → **422**; same `TaxComponent` honesty when `components` sent; soft-deactivate via `is_active=false` clears `is_default`; Tax UI **Activate** / **Deactivate**)  
**Set default:** `POST /tax/rates/{rate_id}/default` (rejects inactive rates)  
**Calculate:** `POST /tax/calculate` — `pricing_mode` same `Literal` (omit → exclusive; blank/invalid → **422**); optional `components[]` same `TaxComponent` honesty.

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

**Category mapping:** assign rates via `POST|PATCH /catalog/categories` `tax_rate_id` (see §5.1).

### 12.2 Tax Reports
**Endpoint:** `GET /reports/tax?from_date=&to_date=&store_id=` — output/input/net VAT summary; optional `store_id` (invoices by invoice store, POS by session store, input via PO/GRN warehouse→store). Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Response echoes `store_id`/`store_name`. Tax UI **Tax From/To date** controls.  
**Filing pack:** `GET /reports/tax/filing?from_date=&to_date=&store_id=&jurisdiction=` — same store scope + same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty; export `tax` / `tax_filing` / `tax_filing_gh` pass `store_id`. Query `jurisdiction` ∈ `GH` (schema Query `Literal` + strip/upper; keep aligned with `tax_filings.SUPPORTED`; omit → tenant `tax_jurisdiction` with neutral pack when unsupported; blank/unsupported → **422** — blank was silent omit; unsupported was late service **400**). Same Query Literal on `GET /reports/export` (omit → export default; `tax_filing_gh` still defaults to GH). Tax UI (`/tax`) **Tax filing jurisdiction filter** (`filingJurisdictionFilter`) + period store picker + **Tax From/To date**.

## 13. Multi-Store Management

### 13.1 Stores
**List:** `GET /stores` (`is_active=true|false` optional — Multi-Store manage All/Active/Inactive; default returns all)  
**Create:** `POST /stores` — `name` ∈ `StoreNameValue` (strip; 1–150; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str`; blank/garbage could persist). Multi-Store **Store name** input.  
**Get:** `GET /stores/{store_id}`  
**Update:** `PATCH /stores/{store_id}` — `name` ∈ `StoreNameValue` (omit/`null` → no change; blank/`!!!`/`http://…` → **422**). Multi-Store **Edit store name** input.

**Create Store:**
```json
{
  "name": "Downtown Store",
  "code": "DT-01",
  "address": "100 Main St",
  "phone": "+1-555-0400",
  "manager_id": "usr_002",
  "branch_id": null,
  "operating_hours": {
    "mon": { "open": "09:00", "close": "18:00" },
    "tue": { "open": "09:00", "close": "18:00" },
    "wed": { "open": "09:00", "close": "18:00" },
    "thu": { "open": "09:00", "close": "18:00" },
    "fri": { "open": "09:00", "close": "17:00" },
    "sat": { "closed": true },
    "sun": { "closed": true }
  }
}
```

`operating_hours` typed `StoreOperatingHours` (`extra=forbid`; keys ∈ `mon`…`sun` only; each day `StoreDayHours` with `closed` or `open`/`close` as `HH:MM` 24h, open before close). Unknown day keys / bad times / open≥close → **422** (was late service **400**). Returned on list/GET; update via `PATCH /stores/{store_id}` (BR-2.3). Creating a store still auto-creates a linked warehouse. Multi-Store **Operating hours** editor (`aria-label`s).

`phone` (when sent) ∈ `E164PhoneValue` (`+` + 8–15 digits); create omit/`null` → no phone; PATCH omit/`null` → no change; blank/`not-a-phone`/`123` → **422** (was free `str`; blank silently cleared on PATCH; garbage could persist). Multi-Store **Store phone** input (`aria-label`); create sends `null` when blank; edit omits blank phone.

`address` (when sent) ∈ `AddressValue` (strip; 1–500 chars; at least one letter/digit; no `://` / `@`); create omit/`null` → no address; PATCH omit/`null` → no change; blank/`!!!`/`http://…` → **422** (was free `str`; blank silently cleared on PATCH; garbage could persist). Multi-Store **Store address** input (`aria-label`); create/edit omit blank.

**Update fields:** `name` ∈ `StoreNameValue` (same rules as create), `address` ∈ `AddressValue` (same rules), `phone` ∈ `E164PhoneValue` (same rules), `manager_id`, `clear_manager`, `branch_id`, `clear_branch`, `is_active`, `operating_hours` (same typed map). Soft-deactivate with `is_active: false` (row retained; Multi-Store UI **Activate** / **Deactivate**; inactive excluded from POS `/pos/stores`, Shell switcher, and new sales/expense pickers; POS open / sales invoice create / expense store assign return 400). Assigned `manager_id` is enforced for inter-store transfer dual approval when set.

**Cash drawer:** `PATCH /stores/{store_id}/drawer` — see §8.5 (`drawer_mode` OpenAPI `Literal`; blank/invalid → **422**).

### 13.2 Store Inventory
**Endpoint:** `GET /stores/{store_id}/inventory`

### 13.3 Store Sales
**Endpoint:** `GET /stores/{store_id}/sales`

### 13.4 Inter-Store Transfers
**List:** `GET /stores/transfers` — optional Query `status` ∈ `draft`|`requested`|`in_transit`|`received`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Same filter on Inventory alias `GET /inventory/stock-transfers`. Inventory + Multi-Store **Stock transfer status filter** All / Draft / Requested / In transit / Received / Cancelled (`transferManageFilter`; client filter over full cache).  
**Create:** `POST /stores/transfers`  
**Get:** `GET /stores/transfers/{transfer_id}`  
**Update Status:** `PATCH /stores/transfers/{transfer_id}/status`  
**Reject (BR-13.2):** `POST /stores/transfers/{transfer_id}/reject` — body `{ "reason" }` ∈ `StockTransferRejectReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; **required**) → status `cancelled` + `rejection_reason`. Omit/blank/`!!!`/`http://…` → **422**. Multi-Store **Stock transfer reject reason** (`aria-label`). Same helper as `POST /inventory/stock-transfers/{id}/reject`.  
**Cancel:** `POST /stores/transfers/{transfer_id}/cancel` — body `{ "reason" }` ∈ `StockTransferRejectReasonValue` (same Value type) → status `cancelled` + `rejection_reason` (also Inventory `/inventory/stock-transfers/{id}/cancel`). Reject / Cancel share the same reason input in UI.

**Create Transfer:**
```json
{
  "from_store_id": "st_001",
  "to_store_id": "st_002",
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

### 14.1 Sales Reports
**Daily Sales:** `GET /reports/sales/daily?date=&store_id=` — day totals (invoices + POS); optional `store_id` (invoice store / POS session store). Optional Query `date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → today UTC; blank/invalid → **422** — blank was silent today; invalid was late service **400**). Response echoes `store_id`/`store_name`/`date`. Export `sales_daily` (passes `store_id`). Reports Sales uses shared **Report To date** (fallback **From**) as `date` (`aria-label`s).  
**Monthly Sales:** `GET /reports/sales/monthly?month=&year=&store_id=` — month totals (invoices + POS); optional `store_id`. Response echoes `store_id`/`store_name`. Export `sales_monthly` (passes `store_id`).  
**Product Sales:** `GET /reports/sales/products?from_date=&to_date=&store_id=&category_id=` — product qty/revenue (invoices + POS); optional store (invoice `store_id` / POS session store) and category filters; rows include `category_id`/`category_name`. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Export `sales_products` (passes `store_id`/`category_id`). Reports shared **Report From/To date** controls.  
**Customer Sales:** `GET /reports/sales/customers?from_date=&to_date=&store_id=&limit=` — top customers by revenue (posted invoices + POS); includes walk-in bucket; optional `store_id` (invoice store / POS session store) and `limit` for top-N. Same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty. Response echoes `store_id`. Export `sales_customers` (passes `store_id`).  
**Sales Returns:** `GET /reports/sales/returns?from_date=&to_date=&customer_id=&reason=&status=&store_id=` — return summary with `by_reason` / `by_customer` / line list; optional `store_id` filters via original invoice store; reasons `damaged|wrong_item|defective|customer_change|other`. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Query `reason` ∈ that set (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — was late **400**). Query `status` ∈ `draft`|`posted`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — was late **400**). Response echoes `store_id`/`store_name`. Export `sales_returns` (passes `store_id`). Reports Sales **Return status** / **Return reason** selects + shared **Report From/To date** controls.  
**Salesperson:** `GET /reports/sales/salesperson?from_date=&to_date=&department_id=&store_id=` — sales by user (invoices + POS); optional `department_id` and `store_id` (invoice store / POS session store). Same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty. Response echoes `store_id`/`store_name`. Export `sales_salesperson` accepts the same filters. Reports **Salespeople** tab uses shared **Report From/To date** inputs.  
**By store:** `GET /reports/sales/by-store?from_date=&to_date=&department_id=` — optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Reports **Stores** tab uses shared **Report From/To date** controls.  
**By department (BR-2.5):** `GET /reports/sales/by-department?from_date=&to_date=&department_id=` — buckets by seller `users.department_id` (invoice `created_by` / POS session user); optional filter; export type `sales_by_department`. Same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty. Reports **Departments** tab uses shared **Report From/To date** inputs.

### 14.2 Inventory Reports
**Stock Balance:** `GET /reports/inventory/balance?warehouse_id=&store_id=` — current stock; optional warehouse/store (store expands to linked warehouses). Response echoes location fields. Export `inventory_balance`.  
**Stock Movement:** `GET /reports/inventory/movements?product_id=&from_date=&to_date=&warehouse_id=&store_id=&movement_type=&created_by=&reason=` — recent stock movements with product sku/name, optional coded `reason`, and acting user; optional warehouse/store (via warehouse store link), movement type, and `created_by`. Query `movement_type` same `Literal` as `/inventory/movements` (omit → all; blank/invalid → **422**). Query `reason` ∈ damage|theft|expiry|found|lost (`Literal` + strip/lower; omit → all; blank/invalid → **422**). Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (same honesty as `/inventory/movements`; omit → no bound; blank/invalid → **422**). Response echoes location fields. Export `inventory_movements` (passes location filters; rows include user attribution + reason).
**Low Stock:** `GET /reports/inventory/low-stock?store_id=&warehouse_id=` — product + warehouse reorder breaches; optional location filters. Export `inventory_low_stock`.  
**Stock Valuation:** `GET /reports/inventory/valuation?method=standard&warehouse_id=&store_id=` — standard-cost valuation (qty × `products.cost_price`). Query `method` ∈ `standard` only (schema Query `Literal` + strip/lower; omit → `standard`; blank/`fifo`/`lifo`/`average`/`weighted_average`/invalid → **422** — no silent `standard` from `""`). Optional `warehouse_id` / `store_id` (same location resolver as balance). Response: `method`, location fields, `items[]` (`product_id`, `sku`, `name`, `warehouse_id`, `quantity`, `unit_cost`, `cost_price`, `value`), `total_quantity`, `total_value`. Export: `POST /reports/export` with `report_type: "inventory_valuation"` (hardcodes standard). Reports Inventory **Valuation method** select.  
**Expiry Report:** `GET /reports/inventory/expiry?days=30&warehouse_id=&store_id=` — batches with quantity > 0 and `expiry_date` within horizon (includes already expired); rows include `sku`/`name`/`days_until_expiry`/`is_expired`; optional warehouse/store filter. Export `inventory_expiry` (optional `days`, location filters).  
**Inter-Store Transfers:** `GET /reports/inventory/transfers?from_date=&to_date=&status=&from_store_id=&to_store_id=&store_id=` — transfer history with `by_status` / `by_route` aggregates (BR-13.2). Optional `store_id` matches source **or** destination store. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Query `status` ∈ `draft`|`requested`|`in_transit`|`received`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — no silent empty filter; was late **400**). Response echoes `store_id`/`store_name`. Export `inventory_transfers` (passes `store_id`). Reports Inventory **Transfer status** select + shared **Report From/To date** controls.
**Stock Count Variances:** `GET /reports/inventory/stock-counts?from_date=&to_date=&warehouse_id=&store_id=&variance_only=true&status=completed` — physical count variance report (BR-5.2); same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty; Query `status` ∈ draft|completed|cancelled (`Literal` + strip/lower; omit → `completed`; blank/invalid → **422**); `counts[]` + flat `lines[]`; default variance-only. Export `inventory_stock_counts`. Reports Inventory **Count status** select.

### 14.3 Purchase Reports
**Purchase Summary:** `GET /reports/purchases/summary?from_date=&to_date=&warehouse_id=&store_id=` — PO totals by period; optional warehouse (PO `warehouse_id`) or store (warehouses linked to store). Echoes `warehouse_name`/`store_name`. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Export `purchases_summary`. Reports shared **Report From/To date** controls.  
**Supplier Purchases:** `GET /reports/purchases/suppliers?supplier_id=&from_date=&to_date=&warehouse_id=&store_id=` — same location filters. Same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty. Export `purchases_suppliers`.  
**Pending Orders:** `GET /reports/purchases/pending-orders?from_date=&to_date=&supplier_id=&status=&warehouse_id=&store_id=` — POs not fully received (`draft` / `sent` / `partially_received`); optional `status` + location filters; returns outstanding qty + amount. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Query `status` ∈ `draft`|`sent`|`partially_received` (schema Query `Literal` + strip/lower; omit → all pending; blank/`received`/`cancelled`/invalid → **422** — was late **400**). Export `purchases_pending_orders`. Reports Purchases **Pending status** select + shared **Report From/To date** controls.  
**Purchase Returns:** `GET /reports/purchases/returns?from_date=&to_date=&supplier_id=&reason=&status=&warehouse_id=&store_id=` — return summary with `by_reason` / `by_supplier` / line list; optional `warehouse_id` / `store_id` (return warehouse); reasons `damaged|wrong_item|expiry|quality|other`. Same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty. Query `reason` ∈ that set (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — was late **400**). Query `status` ∈ `draft`|`posted`|`cancelled` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — was late **400**). Response echoes location fields. Export `purchases_returns` (passes location filters). Reports Purchases **Return status** / **Return reason** selects.

### 14.4 Expense Reports
**Expense Summary:** `GET /reports/expenses/summary?from_date=&to_date=&category_id=&branch_id=&department_id=&store_id=` — optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Reports shared **Report From/To date** controls.  
**Budget vs Actual:** `GET /reports/expenses/budget-vs-actual?from_date=&to_date=&category_id=&branch_id=&department_id=&store_id=` — same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty; scales each category's monthly `budget_amount` by `period_days/30` against approved spend (org filters apply to actuals); returns `rows`, `top_categories`, totals, echo `branch_name`/`department_name`/`store_name`, and status `over_budget|under_budget|on_budget|no_budget`. Export types `expenses_summary` / `expenses_budget_vs_actual` accept the same org params.

### 14.5 Email report schedules (BR-14)
**List:** `GET /reports/schedules` — optional Query `enabled` ∈ `true`|`false` (omit → all; invalid → **422**); optional Query `frequency` ∈ `daily`|`weekly` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Reports Email schedules **Report schedule enabled filter** / **frequency filter** (`scheduleManageFilter` / `scheduleFrequencyFilter`; client filter over full list cache).  
**Create:** `POST /reports/schedules` — body `name` ∈ `ReportScheduleNameValue` (strip; 2–120 chars; ≥1 letter/digit; no `://` / `@`); blank/`!!!`/`http://…` → **422** (was free `str` min_length=2; whitespace late service **400**; punctuation/URL could persist). Body `recipients` ∈ `ReportScheduleRecipientsValue` (`list[EmailStr]` or comma/`;`-separated string); required ≥1; blank/`bad`/`ops@x.com, bad` → **422**. Service strip/`_normalize_recipients` remain defense-in-depth (**400**). Reports **Report schedule name** + **Report schedule recipients** inputs (`aria-label`s).  
**Update:** `PATCH /reports/schedules/{schedule_id}` — optional `name` / `recipients` same honesty; omit/`null` → no change; blank/invalid → **422**.  
**Delete:** `DELETE /reports/schedules/{schedule_id}`  
**Run now:** `POST /reports/schedules/{schedule_id}/run?force=true`  
**Run due (tenant):** `POST /reports/schedules/run-due`

`report_type` ∈ `EXPORTABLE` (schema `Literal` + strip/lower; same set as export — e.g. `summary`, `sales_daily`, `profit_loss`, …). Blank/unknown → **422**. `frequency` ∈ `daily|weekly`; `format` ∈ `csv|pdf|xlsx` (same Literal honesty). Service checks remain defense-in-depth (**400**). Reports UI **Email schedules** select.

### 14.6 One-shot export (BR-14)
**Export:** `GET /reports/export?report_type=&format=csv`  
**Catalog:** `GET /reports/exportable`

Query `report_type` ∈ `EXPORTABLE` (`Literal` + strip/lower; required). Query `format` ∈ csv|pdf|xlsx (`Literal` + strip/lower; omit → `csv`; blank/invalid → **422**; no silent csv from `""`). Optional `from_date` / `to_date` / `date` / `as_of` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound / live as_of fallbacks; blank/invalid → **422** — blank was silent omit; invalid was late service **400**). Same aliases as Email schedules. Reports Export CSV/Excel/PDF buttons + shared **Report From/To/as of date** controls.

---

## 15. Notifications

### 15.1 List Notifications
**Endpoint:** `GET /notifications?status=unread&category=&limit=100`  
Query `status` ∈ unread|read (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**).  
Query `category` ∈ `VALID_CATEGORIES` / preference keys (same Literal; omit → all; blank/invalid → **422**). Notifications UI Unread/All + category chips. Shell Alerts uses `status=unread`.

### 15.2 Mark as Read
**Endpoint:** `PATCH /notifications/{notification_id}/read`

### 15.3 Notification Settings
**Endpoint:** `GET /notifications/settings`  
**Update:** `PATCH /notifications/settings` — body `{ "preferences": { "<category>": { "dashboard"?, "email"?, "sms"? } } }`. Schema `NotificationPreferencesMap` (`extra=forbid` on known categories) + `NotificationChannelPrefs` (`extra=forbid` on dashboard|email|sms). Unknown category/channel → **422** (was silent ignore via merge). Service `update_preferences` remains defense-in-depth. Notifications **Channel preferences** toggles.

Categories include `low_stock` (BR-5.5 — default email **on**; emails `inventory_officer` + `store_manager` + admins via `roles`), `payment_due`, `quotation_expiry` (BR-7.2 — T−1 day before `valid_until`; past-due draft/sent auto-`expired`), `recurring_expense_due` (BR-9.5 — T−1 day before recurring `next_run_at`; default email **on**), `purchase_received`, `expense_approval` (BR-9.3 — default email **on**; role-targeted when expense notify passes `roles`), `credit_limit`, `shift_variance`, `new_order` (BR-15.1 — emitted on sales order create/confirm), `transfer`, `billing`, `security`, `system`. Each maps to dashboard/email/sms preference channels.

```json
{
  "low_stock": { "dashboard": true, "email": true, "sms": false },
  "new_order": { "dashboard": true, "email": true, "sms": false },
  "payment_due": { "dashboard": true, "email": true, "sms": true },
  "credit_limit": { "dashboard": true, "email": true, "sms": true }
}
```

---

## 15A. Onboarding Checklist

First-run tenant checklist (Stage 6 N2). Auto-detects company profile, products, supplier, stock on hand, and first sale. Skip/dismiss/restore require `company_admin` or `super_admin`.

### 15A.1 Get checklist
**Endpoint:** `GET /onboarding/checklist`

**Response `data`:** `steps[]` (`id`, `title`, `description`, `href`, `completed`, `auto_completed`, `skipped`), `completed_count`, `total_count`, `progress_pct`, `dismissed`, `dismissible`, `visible`, `dismiss_threshold_pct` (80).

### 15A.2 Skip / unskip step
**Endpoint:** `POST /onboarding/checklist/steps/{step_id}/skip`  
**Endpoint:** `POST /onboarding/checklist/steps/{step_id}/unskip`  

Path `step_id` schema `Literal` of checklist steps (`OnboardingStepIdValue` + strip/lower): `setup_company` | `add_products` | `create_supplier` | `stock_ready` | `first_sale`. Blank/unknown → **422** (was late service **400**). Service `VALID_STEP_IDS` remains defense-in-depth. Shell Getting started **Skip** / **Undo skip** (`aria-label`s per step).
### 15A.3 Dismiss / restore
**Endpoint:** `POST /onboarding/checklist/dismiss` — requires `progress_pct >= 80` (or all complete).  
**Endpoint:** `POST /onboarding/checklist/restore` — clears dismiss so the Shell banner returns.

UI: persistent **Getting started** banner in the tenant Shell (`OnboardingChecklist`).

---

## 15B. Scheduled Jobs

Celery reliability admin surface (see `docs/CELERY_RELIABILITY_RUNBOOK.md`).

### 15B.1 List jobs
**Endpoint:** `GET /jobs`  
**Roles:** `company_admin`, `super_admin`, `platform_owner`

Returns `celery_enabled`, broker/result URLs, `task_always_eager`, sorted handler names in `jobs`, and beat interval map in `beat`.

### 15B.2 Run job
**Endpoint:** `POST /jobs/{job_name}/run` — Path `job_name` schema `Literal` of `JOB_HANDLERS` keys (`JobNameValue` + strip/lower; blank/unknown → **422** — was late **404**). Allow-list defense-in-depth if Literal and handlers drift.  
**Query:** `enqueue=true` to push to Celery (requires `CELERY_ENABLED`)  
**Roles:** `super_admin`, `platform_owner`

Sync run returns handler result payload. Jobs UI **Run sync** / **Enqueue** (`aria-label`s per job).

**UI:** Shell → **Jobs** (`/jobs`).

---

## 15C. Audit Logs

Append-only hash-chained audit trail (BR-17.1–17.2).

### 15C.1 Query / verify / export
**List:** `GET /audit-logs?module=&action=&user_id=&entity=&from_date=&to_date=&limit=` — optional Query `module` ∈ `AuditModuleValue` / `audit.AUDIT_MODULES` (strip/lower; omit → all; blank/unknown → **422** — blank was silent omit; unknown returned empty). Optional Query `action` ∈ `AuditActionValue` (strip/lower; snake_case shape; digit-start OK for `2fa_*`; omit → all; blank/`login!`/`A` → **422** — blank was silent omit; malformed returned empty). Unknown well-shaped actions still return empty. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → no bound; blank/invalid → **422** — blank was silent omit; invalid was **500**). Audit **Audit module filter** + **Audit action filter** + **From/To date** controls.  
**Verify chain:** `GET /audit-logs/verify`  
**Export CSV:** `GET /audit-logs/export` (same filters; same `module` / `action` / date honesty)

### 15C.2 Retention & cold archive
**Policy:** `GET /audit-logs/retention` — `retention_years` (≥7), `cold_archive_after_days`, `purge_allowed=false`  
**Archives:** `GET /audit-logs/archives` — company_admin / super_admin  
**Archive now:** `POST /audit-logs/archive-cold?older_than_days=` — copies aged rows to checksummed JSONL, sets `archived_at`, never deletes

**UI:** Shell → **Audit** retention card + archives table + **Archive cold now** + date filters.

---

## 16. AI Business Assistant

### 16.1 AI ERP Chat Assistant
**Endpoint:** `POST /ai/chat`

Typed body `AiChatBody` `{ "message" | "prompt", "context"?, "conversation_id"? }` (`extra=forbid`; blank/omit message+prompt / unknown keys → **422** — blank was late service **400**). Service `parse_chat_message` / injection checks remain defense-in-depth. AI UI **Ask AI chat** (`aria-label` message + Ask).

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
**Endpoint:** `GET /ai/insights?type=sales&period=monthly`

### 16.3 Smart Inventory Intelligence
**Endpoint:** `GET /ai/inventory/predictions`

Rule-based velocity forecasts (7/30/90), reorder qty, dead stock, seasonality hint. See `docs/AI_INVENTORY_MVP.md`.

### 16.4 AI Low Stock Prediction
**List:** `GET /ai/inventory/low-stock-prediction?days_ahead=14`  
**Create draft PRs:** `POST /ai/inventory/low-stock-prediction/requests` — typed body `AiLowStockPredictionRequestsBody` `{ "lines"?, "days_ahead"?, "min_confidence"?, "notes"?, "include_open"? }` (`extra=forbid`; `days_ahead` 1–365 omit→14; `min_confidence` 0–1 omit→0; blank/non-numeric days/confidence / unknown keys → **422** — was free `dict` with silent blank→default and possible **500** on garbage). Optional header `notes` + nested line `notes` ∈ `PurchaseRequestNotesValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/`null` → no notes; blank/`!!!`/`http://…` → **422** — was free `str` silently stripped to null). Nested `lines[]` are `AiLowStockPredictionLine` (`extra=forbid`; required non-blank `product_id`; optional `confidence` 0–1, `suggested_order_qty`/`recommended_order_qty` ≥0, `warehouse_id`/`preferred_supplier_id`/`notes`; optional `risk_reason` ∈ `AiPredictionRiskReasonValue` — omit/`null` → service defaults generated line note to `at_risk`; blank/`!!!`/`http://…` → **422** — was free `str` stripped to null; unknown line keys / blank `product_id` / bad qty|confidence → **422** — was free `list[dict]`). Omit/`null`/`[]` `lines` re-runs prediction. AI UI **Create draft purchase requests from predictions** + **AI low-stock prediction notes** + **AI prediction risk reason** + **Include open purchase requests** (`aria-label`s; blank notes/risk_reason omitted as `null`).

```json
{ "days_ahead": 14, "min_confidence": 0.3, "lines": null }
```

Omitting `lines` runs prediction then creates draft purchase requests (`purchasing:write`).

**UI:** AI page (`/ai`) — **Inventory predictions** then **Create draft PR(s)** (BR-21.4). Uses loaded at-risk lines when present; otherwise re-runs prediction. Open Purchasing → Requests to submit.

### 16.5 AI Sales Analysis
**Endpoint:** `GET /ai/sales/analysis?from_date=&to_date=`

Rule-based trend forecast, RFM segments, product affinity, peak hours/days. Optional `from_date` / `to_date` ∈ `IsoDateQueryValue` (`YYYY-MM-DD` or ISO; omit → service default ~90d window; blank/invalid → **422** — blank was silent default; invalid was late service **400**). AI **Analysis From/To date** inputs (`aria-label`s). See `docs/AI_SALES_EXPENSE_MVP.md`.

### 16.6 AI Expense Analysis
**Endpoint:** `GET /ai/expenses/analysis?from_date=&to_date=`

Budget variance, unusual/duplicate detection, cost-optimization suggestions; OCR may suggest category keywords. Same `from_date` / `to_date` ∈ `IsoDateQueryValue` honesty.

### 16.7 AI Report Generator
**Generate (JSON preview):** `POST /ai/reports/generate` — typed body `AiReportsGenerateBody` `{ "prompt"? | "template_id"? | "report_type"?, "format"?, "period"?, "filters"?|"params"? }` (`extra=forbid`; must provide prompt/template_id/report_type; invalid `format` ∈ csv|pdf|xlsx or `report_type` ∈ EXPORTABLE → **422** — format garbage was silently remapped to csv; unknown report_type was late **400**). AI UI **Generate AI report** (`aria-label`).  
**Export file:** `POST /ai/reports/export` — typed body `AiReportsExportBody` `{ "prompt"? | "template_id"? | "report_type"?, "format"?, "filters"?|"params"? }` (`extra=forbid`; must provide prompt/template_id/report_type; `format` omit → **csv**; blank/invalid format|type / unknown keys → **422** — was free `dict` with `or "csv"`). AI UI **Export AI report** (`aria-label` Export CSV).  
**Templates:** `GET|POST /ai/reports/templates`, `DELETE /ai/reports/templates/{id}` — create body typed `AiReportTemplateCreateBody` `{ "name", "prompt", "format"? }` (`extra=forbid`; `name` ∈ `AiReportTemplateNameValue` strip; 1–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…` → **422** — was free `str` min_length=1; punctuation/URL could persist; blank/omit prompt / unknown keys / bad format → **422**). AI UI **AI report template name** + **Save AI report template** (`aria-label`s; Save gated on trim).

```json
{ "prompt": "Show me monthly sales for Q2 2026", "format": "csv" }
```

Also accepts structured `{ "report_type": "sales_monthly", "period": "last_month", "format": "pdf" }` (EXPORTABLE types). Constrained NL — see `docs/AI_REPORT_GENERATOR_MVP.md`.

### 16.8 AI Document Assistant
**Endpoint:** `POST /ai/documents/analyze`

**Content-Type:** `multipart/form-data`

```json
{
  "file": "<uploaded_file>",
  "document_type": "invoice"
}
```

Form fields: `file` (required), `document_type` ∈ `receipt`|`invoice`|`purchase_order`|`auto` (`Literal` + strip/lower; omit/`null` → `auto`; blank/`""`/invalid → **422** — no silent `auto` from empty Form field or garbage), optional `expected_amount`. Returns extracted fields, party/PO matches, and discrepancy flags. Analyze is suggest-only — see `docs/AI_DOCUMENT_MVP.md`. AI UI **Document type** select.

**Create draft expense:** `POST /ai/documents/create-expense` — typed body `AiDocumentExpenseCreate` `{ amount, payee?, description?, reference?, category_id?, category?, expense_date?, payment_method?, store_id?, branch_id?, department_id? }` (`extra=forbid`; `expenses:write`; `payment_method` same expense `Literal`, omit → `cash`; blank/invalid → **422**). Optional `description` ∈ `ExpenseDescriptionValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`); omit/`null` → no description; blank/`!!!`/`http://…` → **422** (was free `str`; blank/garbage could persist). Optional `expense_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit → service default (today); blank/`not-a-date`/`01/02/2024` → **422** (blank was silent default; invalid was late service **400**). Creates a normal pending/auto-approved expense from reviewed OCR fields (defaults category to MISC when omitted); AI UI **Create draft expense** + **AI document draft date** + **AI document expense description** (`aria-label`; blank omitted as `null`).

**Create draft purchase invoice (PO-matched):** `POST /ai/documents/create-purchase-invoice` — typed body `AiDocumentPurchaseInvoiceCreate` `{ purchase_order_id, supplier_id?, supplier_invoice_number?, notes?, invoice_date?, is_reverse_charge? }` (`extra=forbid`; `purchasing:write`). Optional `invoice_date` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit → service default; blank/`not-a-date`/`01/02/2024` → **422** (blank was silent default; invalid was late service **400**). Copies active PO lines into a draft PI; AI UI **Create draft purchase invoice** when Analyze returns a PO match. See `docs/AI_DOCUMENT_MVP.md`.

### 16.9 AI Customer Assistant
**Endpoint:** `POST /ai/customer/assist`

Typed body `AiCustomerAssistBody` `{ "customer_id"?, "query"? | "message"? }` (`extra=forbid`; unknown keys → **422**; omit/`{}` → overview). Blank strings coerce to omit. AI UI **Customer assist** (`aria-label`).

```json
{
  "customer_id": "cust_001",
  "query": "What is my current outstanding balance?"
}
```

Rule-based churn, best customers, promotions, and balance overview (RFM + credit). See `docs/AI_CUSTOMER_MVP.md`.

### 16.10 AI Security Monitor
**List:** `GET /ai/security/alerts`  
Query: `limit`, `min_score`, `scan=true` (optional inline rescan)

**Scan now:** `POST /ai/security/scan`

Returns tenant-scoped alerts with `kind`, `risk_score`, `user_id`, `evidence`, `created_at`. Rule-based MVP (no LLM). See `docs/AI_SECURITY_MVP.md`.

---

## 17. Webhooks

RIBDIGI ERP supports webhook subscriptions for real-time event notifications.
Company admins can also manage endpoints in the **Integrations** UI (`/integrations`).

### 17.1 Manage Webhooks
**List:** `GET /webhooks` — optional `?is_active=true|false` (or `active_only=true`) filters disabled endpoints (omit = all; Integrations manage status filter).  
**Create:** `POST /webhooks` — `url` ∈ absolute `http(s)` (`WebhookUrlValue`; strip; blank/`ftp://`/`not-a-url`/remote `http` → **422** — was free `str`; late service **400**; `http` allowed only for localhost). `events[]` ∈ `VALID_EVENTS` (blank/unknown/empty → **422**). Optional `description` ∈ `WebhookDescriptionValue` (strip; 1–255; ≥1 letter/digit; no `://`/`@`; omit/`null` OK; blank/`!!!`/`http://…` → **422** — was free `str`; blank silently None / garbage could persist). Integrations **Webhook endpoint URL** + **Webhook description** inputs.  
**Get:** `GET /webhooks/{webhook_id}`  
**Update:** `PATCH /webhooks/{webhook_id}` (same `WebhookUrlValue` when `url` sent; `description` ∈ `WebhookDescriptionValue` omit/`null` → no change; blank/`!!!`/`http://…` → **422**; set `rotate_secret: true` to issue a new `whsec_…`; soft-disable via `is_active: false` — Integrations **Disable** / **Enable** + manage status filter All/Active/Inactive)  
**Delete:** `DELETE /webhooks/{webhook_id}`  
**Test:** `POST /webhooks/{webhook_id}/test` (delivers signed `webhook.test`)  
**Deliveries:** `GET /webhooks/{webhook_id}/deliveries?limit=50` — optional Query `status` ∈ `pending`|`pending_retry`|`delivered`|`failed` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422**). Integrations **Webhook delivery status filter** All / Pending / Pending retry / Delivered / Failed (`deliveryStatusFilter`; client filter over loaded delivery cache).  
**Retry delivery:** `POST /webhooks/{webhook_id}/deliveries/{delivery_id}/retry` (pending_retry or failed)

`events` on create/update is OpenAPI `list[Literal[…]]` of known event names (aligned with Integrations checkboxes / `VALID_EVENTS`). Unknown or blank items → **422**; empty list → **422** (`min_length=1` on create). Case is coerced (e.g. `Sale.Created` → `sale.created`). Service `normalize_events` remains defense-in-depth (**400**). HTTPS required for remote URLs (localhost http allowed).

**Create Webhook:**
```json
{
  "url": "https://your-app.com/webhooks/ribdigi",
  "events": ["sale.created", "stock.low", "webhook.test"],
  "secret": "whsec_your_secret",
  "is_active": true
}
```

Signing secret is returned **once** on create/rotate (`secret_shown_once`). Deliveries include `X-Ribdigi-Signature: t=<unix>,v1=<hmac-sha256>`.

### 17.2 Available Events

| Event | Description |
|-------|-------------|
| `sale.created` | New sale/invoice created (invoice post or POS checkout) |
| `sale.paid` | Invoice payment received, or POS sale fully settled at till (no credit tender) |
| `stock.low` | Product reached low stock level |
| `stock.in` | Stock received into warehouse |
| `stock.out` | Stock issued from warehouse (manual / non-POS-invoice outbound) |
| `purchase.order.created` | New PO created |
| `purchase.grn.received` | GRN recorded |
| `customer.created` | New customer added |
| `supplier.created` | New supplier added |
| `expense.approved` | Expense approved |
| `user.login` | Successful interactive login (password / TOTP / WebAuthn; not refresh) |
| `tenant.suspended` | Tenant account suspended |
| `webhook.test` | Manual test ping from admin UI / `POST .../test` |

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

### 17.4 Signature verification (subscribers)

Every delivery includes header **`X-Ribdigi-Signature`** with format:

```text
t=<unix_seconds>,v1=<hmac_sha256_hex>
```

Signed bytes are: `f"{t}.".encode("utf-8") + raw_body` (raw JSON body **exactly** as received — do not re-serialize).

Rules:

1. Parse `t` and `v1` from the header.
2. Reject if `|now - t| > 300` seconds (replay window).
3. Recompute HMAC-SHA256 with your `whsec_…` secret; compare with `hmac.compare_digest`.
4. Secrets are shown **once** on create/rotate in Integrations — store them in your vault.

**Live events today:** `webhook.test` (Integrations **Test**), `sale.created` (invoice post **or** POS checkout), `sale.paid` (customer payment **or** POS sale with no credit tender), `customer.created`, `supplier.created`, `purchase.order.created`, `purchase.grn.received`, `expense.approved` (final approval), `stock.low` (when a new low-stock notification is created), `stock.in` (inbound `stock_in` movements except `reference_type=grn`, which fans out only as `purchase.grn.received`), `stock.out` (outbound `stock_out` movements except `pos_sale` / `sales_invoice` — those use `sale.created`), `tenant.suspended` (self-suspend, platform suspend, or trial-grace expiry — first delivery is best-effort; Celery retries skip suspended tenants), and `user.login` (successful interactive login via password / TOTP / WebAuthn; **not** token refresh — higher volume; payload may include email + IP).

**Golden fixture** (matches `tests/test_webhooks_w1.py`):

| Field | Value |
|-------|--------|
| Secret | `whsec_demo_secret_123456` |
| Body | `{"event":"webhook.test","timestamp":"2026-08-15T07:00:00Z","tenant_id":"demo","data":{"message":"ping"}}` |
| Timestamp `t` | `1723705200` |
| Header | `t=1723705200,v1=8ba12e1df3b867331f2ccf13f760ace4afd370df9d542012046eb4aba49bb2e2` |

**Python:**

```python
import hashlib, hmac, time

def verify_ribdigi_signature(secret: str, body: bytes, header: str, skew: int = 300) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts = int(parts.get("t", "0"))
    expected = parts.get("v1", "")
    if abs(int(time.time()) - ts) > skew:
        return False
    signed = f"{ts}.".encode() + body
    got = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(got, expected)
```

**Node.js:**

```js
const crypto = require("crypto");

function verifyRibdigiSignature(secret, bodyBuf, header, skew = 300) {
  const parts = Object.fromEntries(
    header.split(",").map((c) => c.trim().split("="))
  );
  const ts = Number(parts.t || 0);
  const expected = parts.v1 || "";
  if (Math.abs(Math.floor(Date.now() / 1000) - ts) > skew) return false;
  const signed = Buffer.concat([Buffer.from(`${ts}.`), bodyBuf]);
  const got = crypto.createHmac("sha256", secret).update(signed).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(got), Buffer.from(expected));
}
```

See also Integrations UI **Verify signature** panel and `docs/SECURITY_GUIDE.md` §8.5.

---

## 17A. API Keys

Service integrations authenticate with tenant API keys (BR-18.1). Manage via `GET|POST|DELETE /api-keys` or the **Integrations** UI.

**List:** `GET /api-keys` — optional Query `status` ∈ `active`|`revoked`|`expired` (schema Query `Literal` + strip/lower; omit → all; blank/invalid → **422** — was late **400**). Optional `active_only=true` keeps active keys only. Integrations **API key status filter** All / Active / Revoked / Expired (`apiKeyManageFilter`; client filter over full cache).  
**Create:** `POST /api-keys` — typed body `ApiKeyCreate` `{ "name", "permissions"?, "expires_at"? }` (`extra=forbid`; `name` ∈ `ApiKeyNameValue` strip; 2–120; ≥1 letter/digit; no `://`/`@`; blank/`!!!`/`http://…`/`x` → **422** — was free `str` min_length=2; punctuation/URL could persist; Integrations **API key name** input). Unknown keys / unknown permission module|action → **422** — was late **400** via free `dict`). Optional `expires_at` ∈ `IsoDateQueryValue` (strip; `YYYY-MM-DD` or ISO datetime); omit/`null` → no expiry; blank/`not-a-date`/`01/02/2024` → **422** (was free `datetime`; OpenAPI date-time; padded dates inconsistent). API `reports.parse_datetime` keeps clock time (defense-in-depth). Omit/`{}` `permissions` → default read map. Returns `api_key` once (`rdk_…`). Integrations **API key expiry** input (`aria-label`); create omits blank.  
**Get / usage:** `GET /api-keys/{id}`, `GET /api-keys/{id}/usage`  
**Revoke:** `DELETE /api-keys/{id}`

**Auth headers:** `X-API-Key: rdk_…` or `Authorization: Bearer rdk_…` (plus `X-Tenant-ID` when required).

Default permissions (if omitted): read on `inventory`, `sales`, `purchasing`, `customers`, `reports`.

---

## 18. Rate Limits

API requests are rate-limited per tenant:

| Tier | Requests/Minute | Requests/Hour | Burst |
|------|----------------|---------------|-------|
| Trial | 60 | 1,000 | 10 |
| Basic | 120 | 5,000 | 20 |
| Professional | 300 | 15,000 | 50 |
| Enterprise | Unlimited | Unlimited | 100 |

**Rate Limit Headers:**
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1691415060
```

---

## 19. Error Codes

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
| `CREDIT_LIMIT_EXCEEDED` | Customer credit limit reached (override via `override_credit_limit` + required `override_reason` + `credit:approve`) |
| `CREDIT_OVERRIDE_FORBIDDEN` | Credit limit override attempted without `credit:approve` |
| `CREDIT_OVERRIDE_REASON_REQUIRED` | `override_credit_limit=true` without a non-empty `override_reason` |
| `DUPLICATE_ENTRY` | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | Too many requests |

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
