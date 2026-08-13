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
**Suspend:** `POST /tenants/{tenant_ref}/suspend`  
**Activate:** `POST /tenants/{tenant_ref}/activate`  
(`tenant_ref` = id or slug; **super_admin** only for cross-tenant)

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

`term_unit` is `months` or `years`. Response includes `subscription` usage: months/years assigned, used, remaining, renewal date, and effective `enabled_modules`.

**Feature modules:** `PATCH /tenants/{tenant_ref}/modules`  
`{ "enabled_modules": ["dashboard","pos",...] }` or `{ "reset_to_package": true }`

**Usage detail:** `GET /tenants/{tenant_ref}/usage`  
Packages: `trial` | `starter` | `professional` | `enterprise`. Disabled modules return `403 PACKAGE_FEATURE_DISABLED`.

### 3.4c Platform staff & reports (software owner)
Platform roles: `super_admin` (legacy), `platform_owner`, `platform_admin`, `platform_support`, `platform_finance`.

**Staff:** `GET|POST /platform/staff`, `PATCH /platform/staff/{id}`, `GET /platform/roles`  
**App users (no dashboard yet):** `GET /platform/app-users`  
**Grant dashboard:** `POST /platform/staff/grant` `{ "user_id", "role": "platform_support" }` — promotes an existing workspace app user so they can open the software-owner console  
**Revoke dashboard:** `POST /platform/staff/{id}/revoke` `{ "fallback_role": "company_admin" }` — removes platform role; account stays as an app user  
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

### 4.5 Delete / Deactivate User
**Endpoint:** `DELETE /users/{user_id}`

**Endpoint:** `PATCH /users/{user_id}/status`

**Request:**
```json
{
  "status": "inactive"
}
```

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
**List:** `GET /catalog/categories`  
**Create:** `POST /catalog/categories`  
**Update:** `PATCH /catalog/categories/{category_id}`  
**Delete:** `DELETE /catalog/categories/{category_id}` (soft deactivate)

Optional `tax_rate_id` on create/update (BR-12.1 / BR-2.8). Clear with `"tax_rate_id": null`. Resolve order for product lines: product `tax_rate_id` → category (walk `parent_id`, nearest wins) → tenant default tax rate → 0%.

### 5.2 Brands
**List:** `GET /inventory/brands`  
**Create:** `POST /inventory/brands`  
**Update:** `PATCH /inventory/brands/{brand_id}`

### 5.3 Units
**List:** `GET /catalog/units`  
**Create:** `POST /catalog/units`  
**Update:** `PATCH /catalog/units/{unit_id}`  
**Convert preview:** `POST /catalog/units/convert` `{ "product_id", "quantity", "from_unit_id" }`

Create with conversion (BR-5.1): `{ "code": "CASE12", "name": "Case of 12", "base_unit_id": "<PCS id>", "conversion_ratio": 12 }`  
Meaning: 1 CASE12 = 12 × base unit. Stock ledger stays in `product.unit_id`.  
`POST /inventory/stock-in` / `stock-out` accept optional `unit_id` (entered UoM) and convert to stock units.

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
**List:** `GET /purchases/requests`  
**Create:** `POST /purchases/requests`  
**Get:** `GET /purchases/requests/{request_id}`  
**Approve:** `POST /purchases/requests/{request_id}/approve`  
**Reject:** `POST /purchases/requests/{request_id}/reject`

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
**List:** `GET /purchases/orders`  
**Create:** `POST /purchases/orders`  
**Get:** `GET /purchases/orders/{order_id}`  
**Update Status:** `PATCH /purchases/orders/{order_id}/status`

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
**List:** `GET /purchases/grn`  
**Create:** `POST /purchases/grn`  
**Get:** `GET /purchases/grn/{grn_id}`

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
**List:** `GET /purchases/invoices`  
**Create:** `POST /purchases/invoices`  
**Get:** `GET /purchases/invoices/{invoice_id}`  
**Pay:** `POST /purchases/invoices/{invoice_id}/payments`

### 6.6 Purchase Return
**List:** `GET /purchases/returns`  
**Create:** `POST /purchases/returns`  
**Get:** `GET /purchases/returns/{return_id}`

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
**List:** `GET /customers/groups` (seeds Retail / Wholesale / VIP defaults)  
**Create:** `POST /customers/groups`  
**Update:** `PATCH /customers/groups/{group_id}`  
**Assign on customer:** `POST /customers` / `PATCH /customers/{customer_id}` with `customer_group_id`  
**Preview price:** `GET /products/{product_id}/price?customer_id=&variant_id=`

When a sale/quote/order/POS line omits `unit_price`, list (or variant) price is used and the customer group's `discount_percent` is applied. An explicit `unit_price` is treated as a cashier override.

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
**Pay:** `POST /sales/invoices/{invoice_id}/payments`  
**Print:** `GET /sales/invoices/{invoice_id}/print`

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
  "payments": [
    {
      "method": "cash",
      "amount": 20.00
    },
    {
      "method": "card",
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

**Query Params:** `?template=thermal&format=pdf`

### 8.5 Cash Drawer
**Endpoint:** `GET /pos/sessions/{session_id}/drawer`

---

## 9. Expense Management

### 9.1 Expense Categories
**List:** `GET /expenses/categories`  
**Create:** `POST /expenses/categories` — body `{ code, name, budget_amount? }`; response includes `budget_amount` / `is_active`  
**Update:** `PATCH /expenses/categories/{category_id}` — partial `{ name?, budget_amount?, is_active? }` (monthly budget; BR-9.1)

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
**List:** `GET /accounting/accounts`  
**Create:** `POST /accounting/accounts`  
**Get:** `GET /accounting/accounts/{account_id}`

**Account Types:** `asset`, `liability`, `equity`, `income`, `expense`

### 10.2 Journal Entries
**List:** `GET /accounting/journal-entries`  
**Create:** `POST /accounting/journal-entries`  
**Unpost:** `POST /accounting/journal-entries/{entry_id}/unpost` — manual journals only; reverses account balances; allowed only when `entry_date` is in the tenant’s current fiscal period (`tenants.fiscal_year_start` MM-DD). Auto-posted sources (`sales_invoice`, `coa_opening`, `cash_transfer`, …) are rejected.  
**Attachment:** `POST|GET|DELETE /accounting/journal-entries/{entry_id}/attachment` — multipart `file` upload (PDF/image); tenant-scoped media key on `journal_entries.attachment_url`.

**Create Journal Entry:**
```json
{
  "reference": "JE-001",
  "description": "Adjusting entry for depreciation",
  "lines": [
    { "account_code": "6000", "debit": 100.00, "credit": 0.00 },
    { "account_code": "1000", "debit": 0.00, "credit": 100.00 }
  ]
}
```

### 10.3 Cash & Bank Accounts
**List liquid:** `GET /accounting/liquid-accounts`  
**Create account:** `POST /accounting/accounts`  
```json
{ "code": "1001", "name": "Petty Cash", "liquid_kind": "cash" }
```
Bank example: `{ "code": "1011", "name": "Savings", "liquid_kind": "bank", "bank_name": "Acme Bank", "account_number": "123", "bank_branch": "Main" }`

**Transfers / deposits / withdrawals:**  
- `GET /accounting/transfers`  
- `POST /accounting/transfers` `{ "kind": "transfer|deposit|withdrawal", "from_account_id", "to_account_id", "amount", "reference", "notes" }`  
- `GET /accounting/transfers/{id}`  

`transfer` requires two distinct liquid accounts (Dr destination / Cr source).  
`deposit` credits Owner's Equity `3000` into a liquid account; `withdrawal` is the reverse.

### 10.4 Financial Reports
**Profit & Loss:** `GET /accounting/profit-loss` (also `/reports/profit-loss`) — returns `revenue`, `cogs` (account 5000), `gross_profit`, `operating_expenses`, `expense` (total), `net_profit`. COGS is posted automatically on sales invoice post / POS sale (Dr 5000 / Cr 1200 at standard `cost_price` × stock qty); restocked sales returns reverse COGS. Optional query params: `from_date`, `to_date`, `store_id`, `branch_id`. With no filters, response uses lifetime income/expense account balances (`mode=balances`). With any filter, aggregates posted journal lines (`mode=journals`); store/branch keep only attributable `sales_invoice` / `pos_sale` / `expense` / `sales_return` journals.

**Balance Sheet:** `GET /reports/balance-sheet` (also `/accounting/balance-sheet`) — assets / liabilities / equity + computed retained earnings; `balanced` when Assets = Liabilities + Equity. Optional `as_of=YYYY-MM-DD` reconstructs from posted journal lines through that date (`mode=journals`); omit for live `Account.balance` (`mode=balances`). Optional `compare=prior_period|prior_year` adds prior balances and deltas on each row plus summary `compare.deltas`.  
**Cash Flow:** `GET /reports/cash-flow?from_date=&to_date=` — liquid cash/bank GL movements with back-compat `inflows`/`outflows`/`net` plus sections `operating` / `investing` / `financing` / `transfers` (each `{inflows,outflows,net}`). Lines include `activity`. Classification by journal `source_type` (`cash_transfer` deposit/withdrawal → financing; liquid↔liquid transfer → `transfers`; payments/POS/expenses → operating; `coa_opening` → financing). Investing reserved for future CapEx sources.  
**Trial Balance:** `GET /accounting/trial-balance` (also `/reports/trial-balance`)

---

## 11. Credit Management

### 11.1 Customer Credit
**Get Credit Info:** `GET /customers/{customer_id}/credit`

**Credit limit enforcement / override (BR-11.1):** posting a sales invoice, POS credit checkout, or legacy `POST /sales` that would push `balance + amount` above `credit_limit` returns `409` with `detail.code = CREDIT_LIMIT_EXCEEDED` (includes `over_by`, balances). Retry with body:
```json
{ "override_credit_limit": true, "override_reason": "Approved by store manager" }
```
Requires `credit:approve` (store_manager, accountant, company_admin / `*`). Otherwise `403` `CREDIT_OVERRIDE_FORBIDDEN`. Successful overrides set `credit_limit_overridden: true` and write audit `credit_limit_override`.

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
**Get Outstanding Bills:** `GET /suppliers/{supplier_id}/outstanding`

**Payment Schedule:** `GET /suppliers/{supplier_id}/payment-schedule` — open purchase invoices + uninvoiced POs sorted by `due_date` ascending; each row includes `balance_due`, `days_until_due`, `days_overdue`, optional `early_discount` quote when tenant early-pay settings apply. Response also has `total_due`, `upcoming_count`, `overdue_count`. Requires `credit:read`.

**Due notifications:** Celery / `POST /notifications/scan-due` runs `scan_payment_due` for both AR sales invoices and AP purchase invoices within the horizon (default 3 days), creating `payment_due` notifications (`entity_type=purchase_invoice` for bills).

**Record Payment:** `POST /suppliers/{supplier_id}/payments`

---

## 12. Tax Management

### 12.1 Tax Rates
**List:** `GET /tax/rates`  
**Create:** `POST /tax/rates`  
**Get:** `GET /tax/rates/{rate_id}`  
**Set default:** `POST /tax/rates/{rate_id}/default`

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

### 13.4 Inter-Store Transfers
**List:** `GET /stores/transfers`  
**Create:** `POST /stores/transfers`  
**Get:** `GET /stores/transfers/{transfer_id}`  
**Update Status:** `PATCH /stores/transfers/{transfer_id}/status`

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
**Daily Sales:** `GET /reports/sales/daily?date=`  
**Monthly Sales:** `GET /reports/sales/monthly?month=&year=`  
**Product Sales:** `GET /reports/sales/products?from_date=&to_date=`

### 14.2 Inventory Reports
**Stock Balance:** `GET /reports/inventory/balance?warehouse_id=`  
**Stock Movement:** `GET /reports/inventory/movements?product_id=&from_date=&to_date=`  
**Low Stock:** `GET /reports/inventory/low-stock`

### 14.3 Purchase Reports
**Purchase Summary:** `GET /reports/purchases/summary?from_date=&to_date=`  
**Supplier Purchases:** `GET /reports/purchases/suppliers?supplier_id=&from_date=&to_date=`

### 14.4 Expense Reports
**Expense Summary:** `GET /reports/expenses/summary?from_date=&to_date=&category_id=`  
**Budget vs Actual:** `GET /reports/expenses/budget-vs-actual?from_date=&to_date=&category_id=` — scales each category's monthly `budget_amount` by `period_days/30` against approved spend; returns `rows`, `top_categories`, totals, and status `over_budget|under_budget|on_budget|no_budget`. Export type `expenses_budget_vs_actual`.

---

## 15. Notifications

### 15.1 List Notifications
**Endpoint:** `GET /notifications?status=unread`

### 15.2 Mark as Read
**Endpoint:** `PATCH /notifications/{notification_id}/read`

### 15.3 Notification Settings
**Endpoint:** `GET /notifications/settings`  
**Update:** `PATCH /notifications/settings`

```json
{
  "low_stock": { "dashboard": true, "email": true, "sms": false },
  "new_orders": { "dashboard": true, "email": true, "sms": false },
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

Rule-based velocity forecasts (7/30/90), reorder qty, dead stock, seasonality hint. See `docs/AI_INVENTORY_MVP.md`.

### 16.4 AI Low Stock Prediction
**List:** `GET /ai/inventory/low-stock-prediction?days_ahead=14`  
**Create draft PRs:** `POST /ai/inventory/low-stock-prediction/requests`

```json
{ "days_ahead": 14, "min_confidence": 0.3, "lines": null }
```

Omitting `lines` runs prediction then creates draft purchase requests (`purchasing:write`).

### 16.5 AI Sales Analysis
**Endpoint:** `GET /ai/sales/analysis?from_date=&to_date=`

Rule-based trend forecast, RFM segments, product affinity, peak hours/days. See `docs/AI_SALES_EXPENSE_MVP.md`.

### 16.6 AI Expense Analysis
**Endpoint:** `GET /ai/expenses/analysis?from_date=&to_date=`

Budget variance, unusual/duplicate detection, cost-optimization suggestions; OCR may suggest category keywords.

### 16.7 AI Report Generator
**Generate (JSON preview):** `POST /ai/reports/generate`  
**Export file:** `POST /ai/reports/export`  
**Templates:** `GET|POST /ai/reports/templates`, `DELETE /ai/reports/templates/{id}`

```json
{ "prompt": "Show me monthly sales for Q2 2026", "format": "csv" }
```

Also accepts structured `{ "report_type": "sales", "period": "last_month", "format": "pdf" }` (mapped onto EXPORTABLE types). Constrained NL — see `docs/AI_REPORT_GENERATOR_MVP.md`.

### 16.8 AI Document Assistant
**Endpoint:** `POST /ai/documents/analyze`

**Content-Type:** `multipart/form-data`

```json
{
  "file": "<uploaded_file>",
  "document_type": "invoice"
}
```

Form fields: `file` (required), `document_type` (`receipt`|`invoice`|`purchase_order`|`auto`), optional `expected_amount`. Returns extracted fields, party/PO matches, and discrepancy flags. Suggest-only — see `docs/AI_DOCUMENT_MVP.md`.

### 16.9 AI Customer Assistant
**Endpoint:** `POST /ai/customer/assist`

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
| `CREDIT_LIMIT_EXCEEDED` | Customer credit limit reached (override via `override_credit_limit` + `credit:approve`) |
| `CREDIT_OVERRIDE_FORBIDDEN` | Credit limit override attempted without `credit:approve` |
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
