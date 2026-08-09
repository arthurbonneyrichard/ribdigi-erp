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

### 5.1 Product Categories
**List:** `GET /inventory/categories`  
**Create:** `POST /inventory/categories`  
**Update:** `PATCH /inventory/categories/{category_id}`  
**Delete:** `DELETE /inventory/categories/{category_id}`

### 5.2 Brands
**List:** `GET /inventory/brands`  
**Create:** `POST /inventory/brands`  
**Update:** `PATCH /inventory/brands/{brand_id}`

### 5.3 Units
**List:** `GET /inventory/units`  
**Create:** `POST /inventory/units`

### 5.4 Products
**List:** `GET /products?category_id=&brand_id=&low_stock=true`  
**Create:** `POST /products`  
**Get:** `GET /products/{product_id}`  
**Update:** `PATCH /products/{product_id}`  
**Delete:** `DELETE /products/{product_id}`

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

**Stock In:** `POST /inventory/stock-in`

```json
{
  "product_id": "prod_001",
  "variant_id": "var_001",
  "warehouse_id": "wh_001",
  "quantity": 100,
  "unit_cost": 8.50,
  "reference_type": "purchase",
  "reference_id": "po_001",
  "notes": "Initial stock from PO-001"
}
```

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

**Stock Adjustment:** `POST /inventory/stock-adjustments`

```json
{
  "product_id": "prod_001",
  "warehouse_id": "wh_001",
  "adjustment_qty": -2,
  "reason": "damaged",
  "notes": "Water damage during storage"
}
```

**Stock Transfer:** `POST /inventory/stock-transfers`

```json
{
  "product_id": "prod_001",
  "from_warehouse_id": "wh_001",
  "to_warehouse_id": "wh_002",
  "quantity": 50,
  "status": "pending",
  "notes": "Transfer to branch warehouse"
}
```

**Update Transfer Status:** `PATCH /inventory/stock-transfers/{transfer_id}`

### 5.6 Stock Count
**Create:** `POST /inventory/stock-counts`  
**List:** `GET /inventory/stock-counts`  
**Get:** `GET /inventory/stock-counts/{count_id}`  
**Complete:** `POST /inventory/stock-counts/{count_id}/complete`

**Request:**
```json
{
  "warehouse_id": "wh_001",
  "products": [
    {
      "product_id": "prod_001",
      "expected_qty": 100,
      "actual_qty": 98
    }
  ]
}
```

### 5.7 Stock Movement History
**Endpoint:** `GET /inventory/movements?product_id=&warehouse_id=&from_date=&to_date=`

### 5.8 Low Stock Alerts
**Endpoint:** `GET /inventory/low-stock`

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

**Create GRN:**
```json
{
  "po_id": "po_001",
  "received_date": "2026-08-10",
  "warehouse_id": "wh_001",
  "items": [
    {
      "po_item_id": "poi_001",
      "received_qty": 100,
      "accepted_qty": 98,
      "rejected_qty": 2,
      "rejection_reason": "Damaged packaging"
    }
  ],
  "notes": "Delivery received in good condition"
}
```

### 6.5 Purchase Invoice
**List:** `GET /purchasing/invoices`  
**Create:** `POST /purchasing/invoices`  
**Get:** `GET /purchasing/invoices/{invoice_id}`  

Supplier payments: `POST /suppliers/{id}/payments` (credit module). Attachment: `POST/GET/DELETE /purchasing/invoices/{invoice_id}/attachment`.

### 6.6 Purchase Return
**List:** `GET /purchasing/returns`  
**Create:** `POST /purchasing/returns`  
**Get:** `GET /purchasing/returns/{return_id}`  
**Post:** `POST /purchasing/returns/{return_id}/post`

---

## 7. Sales & Customers

### 7.1 Customers
**List:** `GET /customers`  
**Create:** `POST /customers`  
**Get:** `GET /customers/{customer_id}`  
**Update:** `PATCH /customers/{customer_id}`  
**Delete:** `DELETE /customers/{customer_id}`

**Create Customer:**
```json
{
  "name": "Walk-in Customer",
  "email": "walkin@example.com",
  "phone": "+1-555-0300",
  "address": "789 Customer Lane",
  "customer_group": "retail",
  "credit_limit": 500.00,
  "opening_balance": 0.00,
  "tax_id": ""
}
```

### 7.2 Customer Groups
**List:** `GET /customers/groups`  
**Create:** `POST /customers/groups`

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

**Create Return:**
```json
{
  "invoice_id": "inv_001",
  "return_date": "2026-08-07",
  "items": [
    {
      "invoice_item_id": "invi_001",
      "return_qty": 1,
      "reason": "defective",
      "refund_amount": 12.99
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
**Create Sale:** `POST /pos/sales`

Single tender: set `payment_method` (`cash`|`card`|`wallet`|`credit`|`other`).  
Split tender: set `payments[]` with `{ "payment_method", "amount", "reference?", "liquid_account_id?" }` summing to the computed sale total (`PAYMENT_TOTAL_MISMATCH` if not). Response includes `payments` rows and `payment_method` (`split` when multiple). Credit portion only increases customer AR balance.

Credit tender (full or split portion) enforces the same credit-limit gate as invoice post. Optional body fields: `credit_limit_override` (bool), `credit_override_reason` (string). Same `CREDIT_LIMIT_*` error codes and audit action apply.

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

### 8.4 Receipt Printing
**Endpoint:** `GET /pos/sales/{sale_id}/receipt`

**Query Params:** `?template=thermal&format=pdf`

### 8.5 Cash Drawer
**Endpoint:** `GET /pos/sessions/{session_id}/drawer`

---

## 9. Expense Management

### 9.1 Expense Categories
**List:** `GET /expenses/categories`  
**Create:** `POST /expenses/categories`

### 9.2 Expenses
**List:** `GET /expenses`  
**Create:** `POST /expenses`  
**Get:** `GET /expenses/{expense_id}`  
**Update:** `PATCH /expenses/{expense_id}`  
**Approve:** `POST /expenses/{expense_id}/approve`  
**Delete:** `DELETE /expenses/{expense_id}`

**Create Expense:**
```json
{
  "category_id": "exp_cat_001",
  "amount": 150.00,
  "date": "2026-08-07",
  "payment_method": "bank_transfer",
  "reference": "UTIL-001",
  "description": "Monthly electricity bill",
  "attachments": ["https://cdn.ribdigi.com/docs/bill.pdf"],
  "branch_id": "br_001",
  "recurring": false
}
```

### 9.3 Recurring Expenses
**List:** `GET /expenses/recurring`  
**Create:** `POST /expenses/recurring`

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
**List:** `GET /accounting/journal-entries`  
**Create:** `POST /accounting/journal-entries`  
**Get:** `GET /accounting/journal-entries/{entry_id}`  
**Unpost:** `POST /accounting/journal-entries/{entry_id}/unpost`  
**Upload attachment (Stage 9 J1):** `POST /accounting/journal-entries/{entry_id}/attachment` (multipart `file`) — requires `accounting:write`  
**Download attachment:** `GET /accounting/journal-entries/{entry_id}/attachment` — requires `accounting:read`  
**Delete attachment:** `DELETE /accounting/journal-entries/{entry_id}/attachment` — requires `accounting:write`  

Journal payloads include `attachment_url` and `has_attachment`. Upload replaces any prior stored object for the entry. Download returns `404` when none is stored.

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
**List:** `GET /accounting/accounts?type=asset&sub_type=cash`  
**Create:** `POST /accounting/accounts`  
**Get Transactions (Stage 8 A1):** `GET /accounting/accounts/{account_id}/transactions`

Query: `from_date`, `to_date` (ISO date), `include_unposted` (default false). Returns account metadata, `opening_balance` (activity before `from_date`), `closing_balance`, `total_debit` / `total_credit`, and `transactions[]` with `entry_number`, `entry_date`, debit/credit, and running `balance` on the account’s natural side (assets/expenses: debit−credit; liability/equity/income: credit−debit). Requires `accounting:read`.

### 10.4 Financial Reports
**Profit & Loss:** `GET /reports/profit-loss?from_date=&to_date=` (also `GET /accounting/profit-loss`)  

Returns period totals from **posted** journal lines: `revenue`, `cogs`, `gross_profit`, `operating_expenses`, `other_income`, `income`, `expense`, `net_profit`, plus per-account `bucket`.

**Cash Flow:** `GET /reports/cash-flow?from_date=&to_date=`  

Liquid (cash/bank) movements classified as `operating` / `investing` / `financing` / `transfer` by journal `source_type`. Includes `opening_cash`, `closing_cash`, `net_change` (excludes cash↔bank transfers).

**Trial Balance:** `GET /reports/trial-balance?as_of_date=`

---

## 11. Credit Management

### 11.1 Customer Credit
**Get Credit Info:** `GET /customers/{customer_id}/credit`

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

**Record Payment:** `POST /customers/{customer_id}/payments`

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
**Get Outstanding Bills (Stage 8 S2):** `GET /suppliers/{supplier_id}/outstanding`

**Payment Schedule (Stage 8 S1 / BR-11.2):** `GET /suppliers/{supplier_id}/payment-schedule`

Returns `{ supplier_id, supplier_name, as_of, total_due, overdue_total, upcoming_total, early_pay, items[] }`. Each item includes `document_type` (`purchase_invoice` | `purchase_order`), amount, `due_date`, `days_until_due`, `schedule_bucket` (`overdue` | `due_today` | `upcoming` | `unscheduled`), and `early_discount` quote for open purchase invoices. Sorted overdue → due today → upcoming. Requires `credit:read`.

**Record Payment:** `POST /suppliers/{supplier_id}/payments`

---

## 12. Tax Management

### 12.1 Tax Rates
**List:** `GET /taxes/rates`  
**Create:** `POST /taxes/rates`  
**Get:** `GET /taxes/rates/{rate_id}`

**Create Tax Rate:**
```json
{
  "name": "Standard VAT",
  "rate": 10.0,
  "type": "vat",
  "is_default": true,
  "is_active": true
}
```

### 12.2 Tax Reports
**Endpoint:** `GET /reports/tax?from_date=&to_date=&tax_type=vat`

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
**List:** `GET /stores/transfers`  
**Create:** `POST /stores/transfers`  
**Get:** `GET /stores/transfers/{transfer_id}`  
**Submit:** `POST /stores/transfers/{transfer_id}/submit`  
**Ship:** `POST /stores/transfers/{transfer_id}/ship`  
**Receive:** `POST /stores/transfers/{transfer_id}/receive`  
**Cancel:** `POST /stores/transfers/{transfer_id}/cancel`

Status flow: `draft` → `requested` → `in_transit` → `received` (or `cancelled`).

**Dual-manager approval (Stage 4 T1 / BR-13.2):** When the source store has `manager_id`, only that user may ship (`403 TRANSFER_SHIP_FORBIDDEN` otherwise). When the destination store has `manager_id`, only that user may receive (`403 TRANSFER_RECEIVE_FORBIDDEN`). `company_admin` / `super_admin` may override either action; override writes audit action `transfer_manager_override`. Warehouse-only transfers (null store ids) skip this gate. Serialized transfers include `from_store_manager_id` / `to_store_manager_id`.

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

---

## 15. Notifications

### 15.1 List Notifications
**Endpoint:** `GET /notifications?status=unread&category=&group=`

Groups: `stock`, `orders`, `payments`, `system`. Category `new_order` (Stage 4 N1 / BR-15.1) belongs to group `orders` and is emitted when a sales order is created or confirmed.

### 15.2 Mark as Read
**Endpoint:** `PATCH /notifications/{notification_id}/read`

### 15.3 Notification Settings
**Endpoint:** `GET /notifications/settings`  
**Update:** `PATCH /notifications/settings`

Preference keys include `new_order`, `low_stock`, `purchase_received`, `payment_due`, `credit_limit`, and other default categories. Each key has `dashboard` / `email` / `sms` booleans.

```json
{
  "low_stock": { "dashboard": true, "email": true, "sms": false },
  "new_order": { "dashboard": true, "email": false, "sms": false },
  "payment_due": { "dashboard": true, "email": true, "sms": true },
  "credit_limit": { "dashboard": true, "email": true, "sms": true }
}
```

---

## 16. AI Business Assistant

### 16.1 AI ERP Chat Assistant
**Endpoint:** `POST /ai/chat`

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

### 16.4 AI Low Stock Prediction
**Endpoint:** `GET /ai/inventory/low-stock-prediction?days_ahead=30`

### 16.5 AI Sales Analysis
**Endpoint:** `GET /ai/sales/analysis?from_date=&to_date=`

### 16.6 AI Expense Analysis
**Endpoint:** `GET /ai/expenses/analysis?from_date=&to_date=`

### 16.7 AI Report Generator
**Endpoint:** `POST /ai/reports/generate`

```json
{
  "report_type": "sales",
  "period": "last_month",
  "format": "pdf",
  "filters": {
    "store_id": "st_001",
    "category_id": "cat_001"
  }
}
```

### 16.8 AI Document Assistant
**Endpoint:** `POST /ai/documents/analyze`

**Content-Type:** `multipart/form-data`

```json
{
  "file": "<uploaded_file>",
  "document_type": "invoice"
}
```

### 16.9 AI Customer Assistant
**Endpoint:** `POST /ai/customer/assist`

```json
{
  "customer_id": "cust_001",
  "query": "What is my current outstanding balance?"
}
```

### 16.10 AI Security Monitor
**Endpoint:** `GET /ai/security/alerts`

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
| `GET /products` | `ribdigi:cache:products:{tenant_id}:all` | 10 min |
| `GET /catalog/categories` | `…:categories:flat` / `…:categories:tree` | 10 min |
| Auth claims / `GET /me` | `ribdigi:cache:perms:{tenant_id}:{user_id}` | 1 hour (`CACHE_PERMISSIONS_TTL_SECONDS`) |

Dashboard/catalog invalidated on product/catalog/stock mutations, POS sale, invoice post, and expense approval. Permissions invalidated on user role/`record_scope` change and custom-role updates that sync assigned users. Disable with `CACHE_ENABLED=false`.

## 19. Rate Limits

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
