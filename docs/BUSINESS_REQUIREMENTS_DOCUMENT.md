# RIBDIGI BUSINESS ERP — Business Requirements Document (BRD)

> **Document Version:** 1.0  
> **Product:** RIBDIGI BUSINESS ERP (MVP)  
> **Status:** Draft  
> **Date:** August 2026

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Project Scope](#2-project-scope)
3. [Stakeholders](#3-stakeholders)
4. [Functional Requirements](#4-functional-requirements)
   - 4.1 Multi-Tenant Management
   - 4.2 System Administration
   - 4.3 User Management
   - 4.4 Executive Dashboard
   - 4.5 Inventory Management
   - 4.6 Purchasing
   - 4.7 Sales
   - 4.8 Point of Sale (POS)
   - 4.9 Expense Management
   - 4.10 Basic Accounting
   - 4.11 Credit Management
   - 4.12 Tax Management
   - 4.13 Multi-Store Management
   - 4.14 Reports & Analytics
   - 4.15 Notifications
   - 4.16 Backup & Recovery
   - 4.17 Audit Logs
   - 4.18 API
   - 4.19 Authentication & Security
   - 4.20 System Settings
   - 4.21 AI Business Assistant
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [User Roles & Permissions](#6-user-roles--permissions)
7. [Business Workflows](#7-business-workflows)
8. [Data Requirements](#8-data-requirements)
9. [Integration Requirements](#9-integration-requirements)
10. [Compliance & Regulatory Requirements](#10-compliance--regulatory-requirements)
11. [Appendix](#11-appendix)

---

## 1. Introduction

### 1.1 Purpose
This Business Requirements Document (BRD) defines the functional and non-functional requirements for the **RIBDIGI BUSINESS ERP (MVP)** platform. It serves as the authoritative reference for development, testing, and stakeholder alignment throughout the product lifecycle.

### 1.2 Product Overview
RIBDIGI BUSINESS ERP is a cloud-native, multi-tenant SaaS platform designed for SMEs across Retail, Mart, Pharmacy, Restaurant, Bakery, Wholesale, and Manufacturing industries. It unifies inventory, sales, purchasing, accounting, POS, and AI-powered business intelligence into a single scalable solution.

### 1.3 Document Objectives
- Define all functional requirements per module
- Establish non-functional requirements (performance, security, scalability)
- Document user roles and permission matrices
- Map core business workflows
- Set compliance and regulatory boundaries

### 1.4 Definitions & Acronyms

| Term | Definition |
|------|------------|
| **ERP** | Enterprise Resource Planning |
| **SaaS** | Software as a Service |
| **MVP** | Minimum Viable Product |
| **POS** | Point of Sale |
| **GRN** | Goods Received Note |
| **SKU** | Stock Keeping Unit |
| **RBAC** | Role-Based Access Control |
| **VAT** | Value Added Tax |
| **BOM** | Bill of Materials |
| **P&L** | Profit & Loss |
| **COA** | Chart of Accounts |
| **AR** | Accounts Receivable |
| **AP** | Accounts Payable |
| **2FA** | Two-Factor Authentication |
| **JWT** | JSON Web Token |
| **RLS** | Row-Level Security |

---

## 2. Project Scope

### 2.1 In-Scope (MVP)
All modules listed in Section 4 are within MVP scope, including:
- Multi-tenant SaaS architecture with tenant isolation
- Core business modules: Inventory, Sales, Purchasing, POS, Accounting
- User management with RBAC
- Executive dashboard with real-time KPIs
- AI Business Assistant (basic capabilities)
- Mobile-responsive web interface
- RESTful API with authentication
- Backup, recovery, and audit logging

### 2.2 Out-of-Scope (Post-MVP)
- Advanced Manufacturing (MRP, production scheduling)
- E-commerce integrations (Shopify, WooCommerce)
- Dedicated CRM module
- IoT device integration
- Embedded fintech services
- Advanced BI with custom report builder
- Multi-country tax engines beyond VAT

### 2.3 Assumptions
- Target users have basic digital literacy and internet access
- Primary market operates in English (Phase 1); localization for additional languages in Phase 2
- Internet connectivity is available for cloud operations
- Customers will use modern browsers (Chrome, Firefox, Safari, Edge — last 2 versions)

### 2.4 Constraints
- MVP must be deployable within 6 months
- Budget constraints limit AI model complexity in Phase 1
- Mobile apps (Flutter/React Native) will follow web MVP by 2–3 months

---

## 3. Stakeholders

| Stakeholder | Role | Interest |
|-------------|------|----------|
| **Product Owner** | Defines roadmap, prioritizes features | Market fit, revenue, user adoption |
| **Business Analysts** | Requirements gathering, documentation | Clear, testable requirements |
| **Development Team** | Backend, frontend, mobile, AI engineers | Technical feasibility, architecture |
| **QA Team** | Testing, validation | Requirement traceability, test coverage |
| **DevOps Team** | Infrastructure, deployment, monitoring | Scalability, reliability, security |
| **End Users** | Store managers, cashiers, accountants, inventory officers | Usability, efficiency, accuracy |
| **Company Admins** | Business owners, ERP administrators | Control, visibility, compliance |
| **Reseller Partners** | White-label distributors | Customization, margin, support |

---

## 4. Functional Requirements

### 4.1 Multi-Tenant Management

#### BR-1.1 Tenant Registration
- **Description:** Allow new companies to register as tenants on the platform.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] User can register with company name, email, password, industry type (`POST /tenants` + Platform **Create tenant**; `industry` normalized via `normalize_industry` / `VALID_INDUSTRIES`)
  - [x] System validates email uniqueness
    - Complete (MVP): unique `(tenant_id, email)` on `User`; login is tenant-scoped (`tenant_id` + email). Cross-tenant duplicate emails allowed by design.
  - [x] System auto-creates isolated tenant database/schema
    - Complete (MVP): shared-schema + `tenant_id` row isolation per `docs/ADR_001_TENANCY.md` (schema-per-tenant deferred post-MVP); registration creates tenant + seeds defaults
  - [x] System sends email verification link (`purpose=email_verify` AuthToken + `send_verification_email` on register/user create; `/verify-email`)
  - [x] Tenant status defaults to "Trial" (`status=trial` + `trial_ends_at` on `POST /tenants`)

#### BR-1.2 Company Profile
- **Description:** Tenant administrators can configure company identity and operational settings.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Upload and display company logo (`POST|GET|DELETE /tenants/me/logo`; Company UI)
  - [x] Edit company name, address, phone, email, website (`PATCH /tenants/me`; Company profile form)
  - [x] Configure fiscal year start date (`fiscal_year_start` on tenant + Company UI)
  - [x] Set default currency and time zone (`currency` / `timezone` on create + `PATCH /tenants/me`; Company UI)
  - [x] Select industry from predefined list (Retail, Pharmacy, Restaurant, Bakery, Wholesale, Manufacturing) (`VALID_INDUSTRIES` + create/PATCH validation; Platform + Company selects; also `mart`)

#### BR-1.3 Subscription Plan Management
- **Description:** Track and manage tenant subscription lifecycle.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Support statuses: Trial, Active, Suspended
    - Complete (MVP): also `grace`; platform list/filter + suspend/activate with required **Suspend reason** (`POST /tenants/{ref}/suspend` `{ reason }` → `suspended_reason`; Platform console input — no `window.prompt`) + Company self-suspend reason (`POST /tenants/me/suspend` required reason; Company page input — no hardcoded `"Admin requested"`)
  - [x] Automatic trial expiration notification (7 days, 3 days, 1 day before)
    - Complete (MVP): Celery `scan_trial_lifecycle` + in-app billing notices
  - [x] Grace period handling for suspended tenants (read-only access)
    - Complete (MVP): `status=grace` → `read_only` claims (writes blocked)
  - [x] Upgrade/downgrade plan capability
    - Complete (MVP): software owner assigns `package_code` + term (months/years), usage/remaining, and per-tenant `enabled_modules`; see `POST /tenants/{ref}/subscription`, `PATCH /tenants/{ref}/modules`

#### BR-1.4 Data Isolation
- **Description:** Ensure complete data separation between tenants.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Tenant A cannot access Tenant B data under any circumstance (queries filter JWT `tenant_id`; cross-tenant API/attachment tests)
  - [x] Database-level isolation (separate schemas or databases)
    - Complete (MVP): shared schema + mandatory `tenant_id` filters per `docs/ADR_001_TENANCY.md`; physical schema-per-tenant deferred
  - [x] API requests include tenant context validation (JWT `tenant_id`; mismatched `X-Tenant-ID` → 403)
  - [x] Backup operations are tenant-scoped (`collect_tenant_payload` / backup get by tenant; cross-tenant backup ids 404)

#### BR-1.5 Tenant Database Initialization
- **Description:** Automated setup of tenant-specific database with seed data.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-create schema/tables on registration
    - Complete (MVP): shared tables already migrated; `POST /tenants` runs `seed_tenant_defaults` for the new `tenant_id`
  - [ ] Seed default chart of accounts based on industry
    - Partial (MVP): single default COA via `ensure_default_accounts`; industry-specific packs deferred
  - [x] Seed default tax rates (VAT 15% in `seed_tenant_defaults`)
  - [x] Seed default units of measure (`catalog_meta.ensure_default_catalog` / `DEFAULT_UNITS`)
  - [x] Seed default expense categories (`expenses.ensure_default_categories`)

---

### 4.2 System Administration

#### BR-2.1 Company Information
- **Description:** Centralized company details editable by Company Admin.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] CRUD operations on company legal name, registration number, tax ID (`legal_name`, `registration_number`, `tax_registration_number` via `GET|PATCH /tenants/me`; Company UI)
  - [x] Multiple address support (billing, shipping, warehouse) — HQ `address` + `billing_address` / `shipping_address` on tenant; warehouse addresses on warehouse records (BR-2.4)
  - [x] Contact person designation (`contact_person` on tenant profile)

#### BR-2.2 Branch Management
- **Description:** Manage multiple business branches under one tenant.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create/edit/delete branches (`GET|POST /branches`, `PATCH /branches/{id}`; soft-deactivate via `is_active`; Multi-Store Branches UI)
  - [x] Assign branch code and manager (`code` unique per tenant; `manager_id`)
  - [x] Branch-specific address and contact (`address`, `phone`, `email`)
  - [x] Deactivate branch without data loss (`is_active=false`; row retained for store/org links)

#### BR-2.3 Store Management
- **Description:** Configure retail/service outlets.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create stores with name, code, location
  - [x] Assign store manager (`manager_id` on create/`PATCH /stores/{id}`; Multi-Store UI; dual-approval uses assigned manager)
  - [x] Configure store operating hours (`stores.operating_hours` weekly map; create/`PATCH /stores/{id}`; Multi-Store UI)
  - [x] Link store to branch and warehouse (`branch_id` on store; create auto-creates linked warehouse; warehouse `store_id` link in Multi-Store UI)
  - [x] Deactivate store without data loss (`PATCH /stores/{id}` `{ is_active: false }`; Multi-Store **Activate** / **Deactivate**; inactive hidden from POS list, Shell switcher, and new sales/expense/tax/report store pickers; POS open + sales invoice + expense store assign reject inactive)

#### BR-2.4 Warehouse Setup
- **Description:** Configure storage locations for inventory.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create multiple warehouses (`POST /warehouses`; unique `code` per tenant)
  - [x] Define warehouse type (retail, bulk, cold storage, etc.) (`warehouse_type`)
  - [x] Assign warehouse manager (`manager_id` tenant user)
  - [x] Configure warehouse address and capacity (`address`, `capacity`; PATCH + Stores UI)
  - [x] Deactivate warehouse without data loss (`PATCH /warehouses/{id}` `{ is_active: false }`; Multi-Store **Activate** / **Deactivate**; inactive hidden from Inventory/Reports warehouse pickers; stock movements + warehouse transfers + PO warehouse assign reject inactive)

#### BR-2.5 Department Setup
- **Description:** Organizational structure configuration.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Create departments (Sales, Inventory, Accounting, etc.) (`GET|POST|PATCH /departments`; Multi-Store Departments UI; soft `is_active`)
  - [x] Assign department head (`head_user_id`; optional `branch_id` link)
  - [x] Department-based reporting filters (`GET /reports/sales/by-department` + `department_id` on salesperson/by-store; Reports UI Departments tab)

#### BR-2.6 Currency Setup
- **Description:** Multi-currency support for international operations.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Add currencies with exchange rates (`GET|PUT|DELETE /credit/exchange-rates/{code}`; Credit → Exchange rates UI)
  - [x] Set base currency (`tenants.currency` on Platform create + Company `PATCH /tenants/me`; Credit rates list shows `base_currency`)
  - [x] Auto-update exchange rates (manual or API) (`POST /credit/exchange-rates/refresh`; `fx_auto_refresh` via `PATCH /credit/exchange-rates/settings`; Celery `refresh_fx_rates`; `FX_PROVIDER`)
  - [x] Transaction-level currency selection (sales invoice/payment + purchase invoice/supplier payment `currency`/`exchange_rate`; Sales + Purchasing create UIs; Credit settle FX + gain/loss)
#### BR-2.7 Language Configuration
- **Description:** UI language preferences.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Switch UI language per user
  - [ ] MVP supports English; framework for i18n

#### BR-2.8 Tax Configuration
- **Description:** Configure tax rules applicable to the business.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Add multiple tax rates (VAT, GST, etc.)
  - [x] Set default tax rate
  - [x] Soft-deactivate tax rates without data loss (`PATCH /tax/rates/{id}` `{ is_active }`; Tax UI **Activate** / **Deactivate**; inactive blocked on category assign; cannot set inactive as default)
  - [x] Tax applicability by product category
  - [x] Compound tax support

---

### 4.3 User Management

#### BR-3.1 User Account CRUD
- **Description:** Full lifecycle management of user accounts.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create user with name, email, phone, role, branch/store assignment (`branch_id` / `department_id` on `POST /users`; Users UI; store assignment via role/store session, not a user FK)
  - [x] Edit user details and assignments (`PATCH /users/{id}` role, phone, branch/department, `record_scope`; Users UI)
  - [x] Soft delete (deactivate) user (`DELETE /users/{id}` or `is_active=false`)
  - [ ] Hard delete with data archival option
  - [x] Activate/deactivate toggle (Users UI)
  - [x] Bulk user import via CSV

#### BR-3.2 Role Management
- **Description:** Predefined and custom role definitions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Predefined roles: Super Admin, Company Admin, Store Manager, Sales Officer, Inventory Officer, Accountant, Cashier
  - [x] Each role has default permission set
  - [x] Custom role creation capability
  - [x] Role assignment to users

#### BR-3.3 Permission System
- **Description:** Granular access control across three dimensions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Module Permissions:** Grant/deny access to entire modules (Inventory, Sales, etc.) — role permission maps + route `require_permission`
  - [x] **Menu Permissions:** Control visibility of specific menu items and submenus — Shell filters from `/me` permissions
  - [x] **Record Permissions:** Control CRUD operations on individual records (own records, department records, all records) — `record_scope` own|department|branch|all; Users UI override
  - [x] Permission inheritance from role with user-level override capability (`record_scope` + custom role permission maps)

---

### 4.4 Executive Dashboard

#### BR-4.1 KPI Cards
- **Description:** At-a-glance business metrics.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Display: Total Sales, Total Purchases, Total Expenses, Total Customers, Total Suppliers, Total Products
  - [x] Real-time or near-real-time updates (within 5 minutes) — live `GET /dashboard` on page load
  - [x] Period comparison (Today vs Yesterday, This Month vs Last Month) via `comparisons` on `/dashboard`
  - [x] Click-through to detailed reports (KPI cards + inventory alerts link to module/report pages)

#### BR-4.2 Inventory Alerts
- **Description:** Visual indicators for inventory issues.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Low stock products count with quick link
  - [x] Out-of-stock products count
  - [x] Expiring products (pharmacy/food) count (`expiring_soon` batches within 30 days)

#### BR-4.3 Sales Visualization
- **Description:** Charts and trends for sales performance.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Recent sales list (last 10 transactions)
  - [x] Top products by revenue and quantity (30-day window)
  - [x] Daily revenue line chart (last 30 days)
  - [x] Monthly revenue bar chart (last 12 months)

#### BR-4.4 Notifications Panel
- **Description:** Centralized notification stream.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Display unread notification count (`GET /notifications/unread-count`; Shell bell badge + sidebar count)
  - [x] Categorized notifications (stock, orders, payments, system) (`GET /notifications?category=`; Notifications page category chips)
  - [x] Mark as read/unread (`PATCH /notifications/{id}/read|unread`; Shell panel + Notifications page)
  - [x] Notification history (last 90 days) (`list_notifications` cutoff; All (90 days) filter)

---

### 4.5 Inventory Management

#### BR-5.1 Product Catalog
- **Description:** Comprehensive product information management.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Categories:** Hierarchical category tree (parent/child), category code (`GET /catalog/categories` returns tree order with `depth`/`path`; create/PATCH reparent; cycle guard; Inventory Catalog Category tree UI + product picker paths; soft-deactivate via `DELETE` / reactivate via `PATCH { is_active: true }`; inactive blocked on product create/assign)
  - [x] **Brands:** Brand name, logo, description (`brands.logo_url` + description; `POST|GET|DELETE /catalog/brands/{id}/logo`; Inventory Catalog UI; soft-deactivate via `DELETE` / reactivate via `PATCH { is_active: true }`; inactive blocked on product create/assign)
  - [x] **Units:** Unit of measure (piece, kg, liter, box, etc.) with conversion ratios; soft-deactivate via `DELETE` / reactivate via `PATCH { is_active: true }`; inactive blocked on product create/assign; product create pickers hide inactive brands/units
  - [x] **Product Variants:** Size, color, flavor, dosage (pharmacy) variants with unique SKUs (`product_variants` attrs + auto/manual SKU; Inventory Variants UI; `POST|PATCH /products/{id}/variants`; soft-deactivate via `DELETE` / reactivate via `PATCH { is_active: true }`)
  - [x] **SKU:** Auto-generated or manual SKU assignment (omit/blank `sku` on product/variant create → `SKU-YYYY-NNNN`; explicit SKU still wins; unique across products+variants)
  - [x] **Barcode:** Support for EAN, UPC, Code 128; barcode generation for products without barcodes (`POST /products/{id}/barcode/generate?symbology=code128|ean13|upca`; PNG/label; Inventory picker; variant generate/label + uniqueness across products/variants; internal GTIN prefixes `200` / `2`)
  - [x] **Images:** Multiple product images with primary image designation (`product_images` max 5; `GET|POST /products/{id}/images` + `PATCH|DELETE .../images/{id}` set primary; Inventory gallery)
  - [x] **Product Details:** Name, description, cost price, selling price, tax rate, category, brand, unit, weight, dimensions (`products.description` / `weight` / `length`/`width`/`height`; create/PATCH + CSV import; Inventory UI)
  - [x] **Soft-deactivate:** Hide from sales/purchasing/POS without data loss (`PATCH /products/{id}` `{ is_active }`; Inventory **Deactivate** / **Activate**; inactive blocked on new sale/PR/PO/PI lines; POS search already active-only)
  - [x] **Batch/Expiry:** Batch number, manufacturing date, expiry date (critical for pharmacy and food) — `POST /inventory/stock-in` + opening-stock lines; Inventory Batches/Opening UI; FEFO stock-out

#### BR-5.2 Stock Operations
- **Description:** All inventory movement transactions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Stock In:** Record incoming stock with reference (purchase order, transfer, adjustment), quantity, batch, expiry, warehouse (`POST /inventory/stock-in` + Inventory Batches UI warehouse/variant/notes; Opening stock variant optional)
  - [x] **Stock Out:** Record outgoing stock with reference (sales, transfer, adjustment, damage), quantity, warehouse (`POST /inventory/stock-out` requires `reference_type` ∈ sale|transfer|adjustment|damage|internal|other + optional `reference_id`/`warehouse_id`/`variant_id`/`batch_id`; Inventory Stock Out **Select reference type** — no silent default to `other`; FEFO when batch omitted)
  - [x] **Stock Adjust:** Coded reason required (`POST /inventory/adjust/{id}` ∈ damage|theft|expiry|found|lost; Inventory Adjust **Select reason** — no silent default to `damage`)
  - [x] **Stock Adjustment:** Correct stock discrepancies with reason (damage, theft, expiry, found, lost) (`POST /inventory/adjust/{product_id}` requires coded `reason`; `stock_movements.reason`; optional `warehouse_id`; Inventory Adjust tab; movements `reason=` filter)
  - [x] **Stock Transfer:** Move stock between warehouses with transfer note, approval workflow (`POST /inventory/stock-transfers` accepts `from_warehouse_id`/`to_warehouse_id`; same-store = 1-step approval, inter-store = dual; ship/receive; **Reject / Cancel reason** via `POST .../reject|cancel` `{ reason }` ∈ `StockTransferRejectReasonValue` (strip; 1–500; ≥1 letter/digit; no `://`/`@`; omit/blank/garbage → **422**) → `rejection_reason` + status `cancelled`; Inventory + Multi-Store Transfers tabs (**Stock transfer reject reason** `aria-label`); aliases under `/inventory/stock-transfers*` and `/stores/transfers*`; `transfer_number` via tenant series `GET|PATCH /inventory/settings` → `stock_transfer_numbering`; default `TR`)
  - [x] **Opening Stock:** Initialize stock levels for new products or fiscal year start (`POST /inventory/opening-stock`, optional equity journal; `reference` via tenant series `GET|PATCH /inventory/settings` → `opening_stock_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `OS` when omitted; Inventory Document numbering Opening stock row)
  - [x] **Stock Count:** Physical count reconciliation with system stock; variance report generation (`GET|POST /inventory/stock-counts` + complete posts variances; draft **Cancel** via `POST /inventory/stock-counts/{id}/cancel` `{ reason }` required → notes + audit; Inventory **Cancel reason** UI; `GET /reports/inventory/stock-counts` variance report + export `inventory_stock_counts`; Reports Inventory panel; `count_number` via tenant series `GET|PATCH /inventory/settings` → `stock_count_numbering`; default `SC`; Inventory Document numbering UI)

#### BR-5.3 Stock Movement History
- **Description:** Complete audit trail of all inventory changes.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Log every stock change with timestamp, user, transaction type, quantity before/after (`stock_movements.created_by` + before/after qty; exposed on `/reports/inventory/movements` + `/inventory/movements` as `created_by` / `created_by_name` / `created_by_email`)
  - [x] Filter by date range, product, warehouse, transaction type (`GET /reports/inventory/movements` + `/inventory/movements`; `warehouse_id` / `store_id` / `movement_type` / `created_by` / dates / product)
  - [x] Export to CSV/PDF (export type `inventory_movements` includes user + product columns)
  - [x] Immutable records (no deletion allowed) (no DELETE endpoint; Inventory Movements UI notes immutability)

#### BR-5.4 Warehouse Stock
- **Description:** Warehouse-specific inventory visibility.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **View stock levels per warehouse** (`GET /inventory/warehouse-stock?warehouse_id=`; Inventory Warehouse stock tab; `inventory:read`)
  - [x] **Warehouse-specific reorder levels** (`PUT /inventory/warehouse-stock/reorder`; Inventory Warehouse stock tab; also `PUT /stores/{id}/reorder-policy`)
  - [x] **Transfer stock between warehouses** (`POST /inventory/stock-transfers` with warehouse IDs; approve → ship → receive; Inventory Transfers tab)
  - [x] Warehouse-wise stock valuation (`/reports/inventory/valuation?warehouse_id=`)

#### BR-5.5 Low Stock Management
- **Description:** Proactive inventory replenishment alerts.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Set minimum stock level per product per warehouse (`warehouse_stocks.reorder_level` via `PUT /stores/{id}/reorder-policy`; Multi-Store inventory policy UI)
  - [x] Set reorder level (trigger point for purchase) (product `reorder_level` + per-warehouse `reorder_level` / `reorder_qty`)
  - [x] Visual indicators on product list (green/yellow/red status) (`stock_status` / `stock_status_label` on product serialize; Inventory products Stock badge; red = ≤0 or ≤ reorder, yellow = ≤ reorder×1.5, green = OK)
  - [x] Automated low-stock notifications to Inventory Officer and Store Manager (`scan_low_stock` / stock-out hooks; emails `inventory_officer` + `store_manager` (+ admins); default `low_stock.email=true`)
  - [x] Generate purchase suggestions based on reorder levels

---

### 4.6 Purchasing

#### BR-6.1 Supplier Management
- **Description:** Vendor relationship and information management.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Supplier Profile:** Name, code, type, category, status (`parties.code` / `profile_type` / `category` / `status`; create/PATCH/GET `/suppliers`; Purchasing **Deactivate** / **Activate**; inactive blocked on new PO / preferred-supplier PR / standalone PI)
  - [x] **Contact Details:** Multiple contacts with name, phone, email, designation (`GET|POST|PATCH|DELETE /suppliers/{id}/contacts` + `/customers/{id}/contacts`; primary syncs party phone/email; Alembic `20260813_0090`)
  - [x] **Soft-deactivate:** Hide from new purchasing docs without data loss (`status=inactive` via `PATCH /suppliers/{id}`; existing PO/GRN/PI can still settle)
  - [x] **Supplier Balance:** Real-time outstanding payable balance (`GET /suppliers/{id}/credit`; Credit UI Balance)
  - [x] **Payment Terms:** Credit period (`payment_terms_days` / Net N) drives PO and purchase-invoice due dates; early-pay discount remains tenant-level
  - [x] **Supplier History:** Purchase history, return history, payment history (`GET /suppliers/{id}/history`; Credit UI)

#### BR-6.2 Purchase Request (PR)
- **Description:** Internal requisition for goods.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create PR with product, quantity, preferred supplier, required date, requesting department (`request_number` via tenant series `GET|PATCH /purchasing/settings` → `purchase_request_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `PREQ`; Purchasing Document numbering UI)
  - [x] PR approval workflow (Inventory Officer → Store Manager → Company Admin)
  - [x] Status tracking: Draft, Pending, Approved, Rejected, Converted to PO (`rejection_reason` on reject via `POST /purchasing/requests/{id}/reject` `{ reason }` **required**; blank/omit → 422/400; Purchasing Reject reason field — no hardcoded UI reason)
  - [x] Convert approved PR to Purchase Order with one click

#### BR-6.3 Purchase Order (PO)
- **Description:** Formal order placed with suppliers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create PO from PR or directly (`POST /purchasing/orders`; `POST /purchasing/requests/{id}/convert` + Purchasing **Convert to PO**)
  - [x] PO number auto-generation with configurable prefix (`GET|PATCH /purchasing/settings`)
  - [x] Product lines with quantity, unit price, tax, discount, total (`items[].discount` on create/amend; tax before discount; Purchasing create/amend/detail; Alembic `20260814_0096`)
  - [x] Supplier selection and delivery address (`purchase_orders.delivery_address` on create/amend/serialize + supplier email; Purchasing UI)
  - [x] PO status: Draft, Sent, Partially Received, Fully Received (`received`), Cancelled (`POST /purchasing/orders/{id}/cancel` `{ reason }` required → notes + audit; `can_cancel`; Purchasing **Cancel reason** UI; blocked after any receipt)
  - [x] Print/email PO to supplier
  - [x] PO amendment tracking (`POST /purchasing/orders/{id}/amend` `{ reason }` **required** → amendment row + audit `po_amended.details.reason`; Purchasing **Required amendment reason** UI; blocked after any receipt)

#### BR-6.4 Goods Received Note (GRN)
- **Description:** Record goods received against PO.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create GRN referencing PO (`POST /purchasing/grn` with `purchase_order_id`; Purchasing receive UI)
  - [x] Record received quantity (may differ from ordered) (`received_qty` / `accepted_qty` / `rejected_qty` vs outstanding; Purchasing line receive inputs)
  - [x] Record batch numbers and expiry dates (`batch_number` / `manufacturing_date` / `expiry_date` on `POST /purchasing/grn` lines → `stock_in_with_batch`; required when `tracks_batches`; Purchasing receive UI; serialize echoes from stock movements)
  - [x] Handle partial receipts (multiple GRNs per PO) (`po_item.received_qty` accumulates; PO → `partially_received` / `received`; Receive remains while partial)
  - [x] Auto-update inventory on GRN approval
    - Complete (MVP): GRN posts on create (`status=posted`) → `stock_in_with_batch` + `post_grn_journal` (no separate draft→approve step)
  - [x] Handle rejected/damaged goods with reason (`rejected_qty` + required `rejection_reason` on GRN lines; only accepted stocked; Purchasing receive UI)

#### BR-6.5 Purchase Invoice
- **Description:** Supplier billing and payable recording.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create invoice from GRN or manually (`POST /purchasing/invoices` with `goods_receipt_id` or manual `items`+`supplier_id`; Purchasing **Draft invoice from GRN** + create)
  - [x] Invoice number, date, due date (tenant series `GET|PATCH /purchasing/settings` → `purchase_invoice_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `PINV`; date/due via party payment terms)
  - [x] Line items with quantity, rate, tax, discount (`items[].discount` + header `discount_amount` on create; from-GRN inherits proportional PO line discount; Purchasing create + detail UI; tax before line discount)
  - [x] Attach supplier invoice document (PDF/image) (`POST|GET|DELETE /purchasing/invoices/{id}/attachment`; Purchasing Upload/Preview)
  - [x] Status: Draft, Approved (`unpaid`), Paid, Partially Paid, Overdue, Cancelled (`POST /purchasing/invoices/{id}/cancel` `{ reason }` required → notes + audit; `can_cancel` when unpaid with zero payments; Purchasing **Cancel reason** UI)
  - [x] Auto-update Accounts Payable
    - Complete (MVP): GRN path posts AP via `post_grn_journal` + supplier balance; manual PI posts AP on approve (skips double-post when from GRN)

#### BR-6.6 Purchase Return
- **Description:** Return goods to suppliers.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create return referencing original PO/GRN (`POST /purchasing/returns` requires `goods_receipt_id`; stores `purchase_order_id` from GRN; Purchasing Returns UI)
  - [x] Record return reason (damaged, wrong item, expiry, quality issue) (`reason` required on `POST /purchasing/returns` ∈ damaged|wrong_item|expiry|quality|other; no silent default; Purchasing Select reason UI)
  - [x] Deduct returned quantity from inventory (`post_purchase_return` → `apply_stock_change` negative qty + AP/inventory journal)
  - [x] Generate debit note (`debit_note_number` allocated on post via tenant series `GET|PATCH /purchasing/settings` → `debit_note_numbering`; return `return_number` series on create; unique per tenant; Purchasing Document numbering UI)
  - [x] Update supplier balance (post credits AP using return `total_amount`, which inherits proportional PO line discount: `accepted return_qty / ordered × PO discount`; tax before discount; Purchasing Returns Discount column)
  - [x] Cancel draft return with required reason (`POST /purchasing/returns/{id}/cancel` `{ reason }` → `status=cancelled`; appends to `notes` + audit `purchase_return_cancelled`; Purchasing **Cancel reason** UI; no stock/AP change; cancelled excluded from returned-qty)

---

### 4.7 Sales

#### BR-7.1 Customer Management
- **Description:** Customer relationship and information management.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Customer Profile:** Name, code, type (walk-in/registered), status (`parties.code` / `profile_type` / `status`; create/PATCH/GET `/customers`; Sales **Deactivate** / **Activate**; inactive blocked on new QT/SO/INV/POS)
  - [x] **Contact Details:** Phone, email, address, GPS coordinates (`parties.phone` / `email` / `address` / `latitude` / `longitude`)
  - [x] **Soft-deactivate:** Hide from new sales docs without data loss (`status=inactive` via `PATCH /customers/{id}`; existing invoices/orders can still settle)
  - [x] **Customer Groups:** Wholesale, Retail, VIP, etc. with group-based pricing (`GET|POST|PATCH /customers/groups`; Sales UI create + **Save discount** + soft **Deactivate** / **Activate**; inactive blocked on customer assign; pricing ignores inactive groups)
  - [x] **Customer Balance:** Real-time outstanding receivable balance (`GET /customers/{id}/credit`; Credit UI Balance)
  - [x] **Credit Limit:** Per-customer credit limit with enforcement (`GET /customers/{id}/credit` + post/POS override; see BR-11.1)
  - [x] **Payment Terms:** Per-customer Net N (`payment_terms_days`) sets sales-invoice due date on post
  - [x] **Customer History:** Purchase history, return history, payment history (`GET /customers/{id}/history`; invoices+POS, returns, payments; Credit UI)

#### BR-7.2 Quotation
- **Description:** Pre-sales price quotes for customers.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Create quotation with product, quantity, price, validity period (`valid_days` → `valid_until`; Sales UI)
  - [x] Line + header discounts on create (`items[].discount` + `discount_amount`; tax before line discount; Sales Create sale UI + detail)
  - [x] Quotation number auto-generation (configurable series via `/sales/settings`)
  - [x] Print/email quotation to customer (`POST /sales/quotations/{id}/send`)
  - [x] Convert quotation to sales order (`POST /sales/quotations/{id}/convert`)
  - [x] Reject with required reason (`POST /sales/quotations/{id}/reject` `{ reason }` → `rejection_reason`; Sales Reject reason field; Alembic `20260815_0103`)
  - [x] Expiry notification before validity ends (`scan_quotation_expiry` Celery job + `POST /notifications/scan-due`; category `quotation_expiry`; T−1 day window; past-due `draft`/`sent` auto-flip to `expired`)

#### BR-7.3 Sales Order
- **Description:** Customer order confirmation before invoicing.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create order from quotation or directly (order_number via tenant series `GET|PATCH /sales/settings` → `sales_order_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `SO`; Sales Document numbering UI)
  - [x] Line + header discounts on create (`items[].discount` + `discount_amount`; Sales Create sale UI + detail)
  - [x] Reserve inventory (soft allocation) on confirm against store warehouse (`stock_reservations`); cancel releases; invoice post consumes then hard stock-out
  - [x] Order status: Draft, Confirmed, Processing, Shipped, Delivered, Cancelled (plus `invoiced` after convert-to-invoice; cancel allowed through processing; required typed `reason` on `POST /sales/orders/{id}/cancel` → notes + audit; Sales **Cancel reason** UI)
  - [x] Delivery date and address
  - [x] Convert to invoice with one click

#### BR-7.4 Sales Invoice
- **Description:** Official billing document.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create invoice from sales order or directly
  - [x] Invoice number auto-generation with configurable prefix and series (`GET|PATCH /sales/settings`; `{PREFIX}-{YYYY}-{NNNN}`, year-scoped next counter)
  - [x] Product lines with quantity, unit price, tax, discount, total (`items[].discount` + header `discount_amount` on create; Sales Create sale + detail KPI; tax before line discount)
  - [x] Customer selection with auto-filled details
  - [x] Multiple print templates (A4, thermal receipt) via `GET /sales/invoices/{id}/print?template=a4|thermal`
  - [x] Status: Draft, Posted (approved), Sent (emailed), Partial, Paid, Overdue, Cancelled (`POST /sales/invoices/{id}/cancel` `{ reason }` required for draft → notes + audit; Sales **Cancel reason** UI; overdue derived from due date; payment-due scan refreshes overdue)
  - [x] Auto-update Accounts Receivable
  - [x] Support credit sales with credit limit check
  - [x] Email posted/sent/partial/paid/overdue invoice to customer (SMTP/console) with optional `to=` override; stamp `emailed_at`/`emailed_to`; unpaid → `sent` on first email; resend without changing payment status

#### BR-7.5 Sales Return
- **Description:** Customer returns and refunds.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create return referencing original invoice
  - [x] Record return reason and condition (`reason` required on `POST /sales/returns` ∈ damaged|wrong_item|defective|customer_change|other; no silent default to `other`; Sales Select reason UI; `items[].condition` required ∈ sellable|discard — no silent default from Restock; Sales Select condition UI)
  - [x] Restock or discard returned items
  - [x] Generate credit note (`credit_note_number` on post via tenant series `GET|PATCH /sales/settings` → `credit_note_numbering`; return `return_number` series on create; unique per tenant; Sales Document numbering UI)
  - [x] Refund or adjust customer balance (`settlement_method=adjust|refund`; refund required/optional when return exceeds open invoice AR; cash/bank refund journal)
  - [x] Cancel draft return with required reason (`POST /sales/returns/{id}/cancel` `{ reason }` → `status=cancelled`; appends to `notes` + audit `sales_return_cancelled`; Sales **Cancel reason** UI; no stock/AR change)

---

### 4.8 Point of Sale (POS)

#### BR-8.1 POS Transaction
- **Description:** Fast, intuitive retail checkout experience.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Barcode Scanner:** Support USB and Bluetooth barcode scanners (wedge scan → Enter on POS search; `GET /pos/products/search?barcode=`)
  - [x] **Product Search:** Search by name, SKU, barcode with autocomplete (POS search tiles + barcode exact match)
  - [x] **Cart Management:** Add, remove, update quantity, apply discounts (POS cart UI)
  - [x] **Discounts:** Percentage or fixed amount; per-item or cart-level (line `discount` + cart `discount_amount`; customer group %)
  - [x] **Customer Selection:** Quick customer lookup or walk-in default (Walk-in / none; credit requires customer)
  - [x] **Multiple Payment Methods:** Cash, Card, Digital Wallet, Credit (for registered customers) (`cash`/`card`/`wallet`/`credit` + split cash+card; aliases `digital_wallet`/`mobile_money` → `wallet`)
  - [x] **Receipt Printing:** Thermal printer support; digital receipt via email/SMS
  - [x] Sale reference auto-generation (`Transaction.reference` via tenant series `GET|PATCH /pos/settings` → `pos_sale_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `POS`; POS Document numbering UI)
  - [x] **Cash Drawer:** Auto-open on cash payment; manual open with required specific reason (`POST /pos/sessions/{id}/drawer/open`; rejects blank/placeholder; POS **Drawer reason** input — no `window.prompt`)

#### BR-8.2 Shift Management
- **Description:** Cashier accountability and reconciliation.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Shift Opening:** Record opening cash float, timestamp, cashier (`POST /pos/sessions/open`; `session_number` via tenant series `GET|PATCH /pos/settings` → `pos_session_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `SHIFT`; POS Document numbering Shift row)
  - [x] **Shift Closing:** Record closing cash, card total, other payments (`POST /pos/sessions/{id}/close`; card/other from session tender totals)
  - [x] **Cash Reconciliation:** System sales vs actual cash; variance reporting (expected vs actual + `shift_variance` notification)
  - [x] **Shift Report:** Sales summary, returns, discounts, payment breakdown (`GET /pos/sessions/{id}/report` with `summary` / `returns`)
  - [x] Prevent new transactions until shift is opened

---

### 4.9 Expense Management

#### BR-9.1 Expense Categories
- **Description:** Classify business expenditures.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Predefined categories (Rent, Utilities, Salaries, Transportation, Marketing, etc.)
  - [x] Custom category creation
  - [x] Category-based budget allocation (`budget_amount` monthly; `PATCH /expenses/categories/{id}`; Expenses UI)
  - [x] Soft-deactivate without data loss (`is_active=false` via `PATCH /expenses/categories/{id}`; Expenses **Deactivate** / **Activate**; inactive blocked on new expense/recurring create)

#### BR-9.2 Expense Entry
- **Description:** Record business expenses.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Expense date, category, amount, payment method, reference number (`reference` auto-allocated via tenant series `GET|PATCH /expenses/settings` → `expense_numbering` when omitted; `{PREFIX}-{YYYY}-{NNNN}` default `EXP`; explicit vendor refs preserved; Expenses Document numbering UI)
  - [x] Payee name (`payee` on create + **Edit** / OCR apply via `PATCH /expenses/{id}` for pending/rejected)
  - [x] Description/notes (`description` on create + **Edit** / OCR apply)
  - [x] Assign to branch/department (`branch_id` / `department_id` on expenses + recurring; Expenses UI; Alembic `20260813_0091`)
  - [x] Link to chart of accounts for auto-posting (`expense_categories.account_id`; debit linked GL or default `6000`; Expenses category GL picker; Alembic `20260813_0092`)

#### BR-9.3 Expense Approval
- **Description:** Control spending through approval workflows.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Configurable approval thresholds (e.g., >$100 requires manager approval) (`expense_approval_matrix` / `expense_approval_threshold`)
  - [x] Multi-level approval chain (N-level role gates; action log; no self-approve / no duplicate-step actor)
  - [x] Approval/rejection with comments (optional typed `comment` on approve → `approval_comment`, Expenses **Approve comment** — no hardcoded `"Approved"`; required `reason` on reject → `rejection_reason`; Expenses **Reject reason** input — no hardcoded `"Rejected"`)
  - [x] Email notification to approvers (current-step matrix roles via `create_notification(..., roles=...)`; default `expense_approval.email=true`; creator excluded; console/SMTP)

#### BR-9.4 Expense Attachments
- **Description:** Digital receipt storage.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Upload receipt images/PDFs (`POST /expenses/{id}/attachment`; Expenses Upload)
  - [x] OCR extraction of amount, date, vendor (AI-assisted) (`POST /expenses/{id}/ocr-suggest`; Expenses OCR)
  - [x] Attachment preview and download (`GET /expenses/{id}/attachment`; Expenses **Preview** modal for image/PDF + Download; same Preview on PI + JE attachments)

#### BR-9.5 Recurring Expenses
- **Description:** Automate regular payments.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Set frequency (daily, weekly, monthly, yearly) — `POST /expenses/recurring`; Expenses → Recurring UI
  - [x] Auto-generate expense entries — Celery `generate_recurring_expenses` + `POST /expenses/recurring/generate`; allocates `EXP-YYYY-NNNN` via expense numbering when blank; Expenses UI Generate due
  - [x] Notification before auto-generation — category `recurring_expense_due` T−1 on `next_run_at` via Celery `scan_recurring_expense_due` + `POST /notifications/scan-due`; Notifications preferences
  - [x] Skip next occurrence — `POST /expenses/recurring/{id}/skip-next` `{ reason }` required (audit `recurring_expense_skipped.details.reason`; does not mutate schedule description); Expenses UI **Skip next reason**
  - [x] Edit schedule template (amount/payee/description/frequency/category/payment/org) — `PATCH /expenses/recurring/{id}`; Expenses **Edit schedule**; future Generate uses new values (existing expenses unchanged). Per-occurrence still via pending expense **Edit**.

---

### 4.10 Basic Accounting

#### BR-10.1 Chart of Accounts (COA)
- **Description:** Financial account structure.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Predefined COA based on industry template
    - Complete (MVP): shared default COA via `ensure_default_accounts`; industry-specific packs remain open under BR-1.5
  - [x] Account types: Asset, Liability, Equity, Income, Expense
  - [x] Account code hierarchy (e.g., 1000-Assets, 1100-Current Assets) — flat coded template (parent_id deferred)
  - [x] Add/edit accounts (create + `PATCH` name/bank fields; system seed codes flagged)
  - [x] Opening balance entry (`POST /accounting/opening-balances`, equity plug to 3000)

#### BR-10.2 Journal Entries
- **Description:** Manual accounting transactions.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Double-entry journal with debit and credit lines
  - [x] Auto-balancing validation
  - [x] Journal number auto-generation (`entry_number` via tenant series `GET|PATCH /accounting/settings` → `journal_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `JE`; Accounting Document numbering UI; shared by manual + auto-posted journals)
  - [x] Attach supporting documents
  - [x] Post/unpost capability (unpost only within same fiscal period; required typed `reason` on `POST .../unpost` → description + audit; Accounting **Unpost reason**)
  - [x] **Period close / books lock:** `tenants.books_closed_through`; `GET|POST /accounting/period` close/reopen; blocks post & unpost on/before closed date; **close/reopen reason required** (`{ reason }` → audit `period_closed` / `period_reopened` `details.reason`; Accounting UI typed reason) (Accounting UI)

#### BR-10.3 Cash & Bank Accounts
- **Description:** Track liquid assets.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create cash accounts (petty cash, main cash)
  - [x] Create bank accounts with bank name, account number, branch
  - [x] Record deposits, withdrawals, transfers between accounts (`reference` via tenant series `GET|PATCH /accounting/settings` → `cash_transfer_numbering`; `{PREFIX}-{YYYY}-{NNNN}` default `XFER` when omitted; Accounting Document numbering Transfer/XFER row)
  - [x] Bank reconciliation (system balance vs statement)
  - [x] Cheque management (issue, deposit, bounce tracking) (`POST /accounting/cheques/{id}/bounce|cancel` `{ reason }` **required**; omit/empty → 422; Accounting Cheques Bounce/Cancel reason field → notes + journal description)

#### BR-10.4 Accounts Receivable (AR)
- **Description:** Track money owed by customers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-generation from sales invoices
  - [x] Customer aging report (0-30, 31-60, 61-90, 90+ days)
  - [x] Payment recording against invoices (`payment_number` via tenant series `GET|PATCH /sales/settings` → `payment_receipt_numbering`; default `RCP`; Sales Document numbering Receipt row)
  - [x] Partial payment support
  - [x] Overdue notification automation

#### BR-10.5 Accounts Payable (AP)
- **Description:** Track money owed to suppliers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-generation from purchase invoices
  - [x] Supplier aging report
  - [x] Payment recording against bills (`payment_number` via tenant series `GET|PATCH /purchasing/settings` → `supplier_payment_numbering`; default `SPY`; Purchasing Document numbering SPY row)
  - [x] Partial payment support
  - [x] Due date notifications

#### BR-10.6 Financial Reports
- **Description:** Standard financial statements.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Profit & Loss:** Revenue, COGS, gross profit, operating expenses, net profit (standard-cost COGS via Dr 5000 / Cr 1200 on invoice/POS; restock returns reverse); `from_date`/`to_date`/`store_id`/`branch_id` filters on journal activity
  - [x] **Cash Flow:** Operating, investing, financing activities
  - [x] **Trial Balance:** All accounts with debit/credit balances; validation that total debits = total credits; `as_of` reconstructs from posted journals (`GET /accounting/trial-balance` / `/reports/trial-balance`)
  - [x] Export to PDF and Excel

---

### 4.11 Credit Management

#### BR-11.1 Customer Credit
- **Description:** Manage customer credit sales and collections.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Set per-customer credit limit
  - [x] Block sales that exceed credit limit (with override permission) (`override_credit_limit` + required `override_reason` on Sales Post / POS credit; API `400 CREDIT_OVERRIDE_REASON_REQUIRED` when override without reason; no canned `window.prompt` default; audit `credit_limit_override`)
  - [x] Display outstanding balance on customer profile
  - [x] Record payment collections with date, amount, method, reference
  - [x] Allocate payments to specific invoices or auto-allocate (oldest first)
  - [x] Customer statement generation (all transactions + balance)

#### BR-11.2 Supplier Credit
- **Description:** Manage supplier payable tracking.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Track outstanding bills per supplier
  - [x] Payment schedule view (upcoming due dates)
  - [x] Early payment discount calculation
  - [x] Supplier statement generation

---

### 4.12 Tax Management

#### BR-12.1 Tax Configuration
- **Description:** Define and apply tax rules.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Add tax types (VAT, GST, Sales Tax, etc.)
  - [x] Configure tax rates (percentage)
  - [x] Soft-deactivate obsolete rates (`PATCH /tax/rates/{id}` `{ is_active=false }` clears default flag; Tax UI **Deactivate** / **Activate**; category tax pickers stay active-only)
  - [x] Set tax applicability (inclusive/exclusive pricing)
  - [x] Product-category-specific tax rules
  - [x] Compound tax (tax on tax) support

#### BR-12.2 Automatic Tax Calculation
- **Description:** Real-time tax computation on transactions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-calculate tax on sales invoices, purchase invoices, POS transactions (PO/PI omit `tax_rate` → product → category → tenant default via `resolve_product_tax`; explicit rate incl. 0 wins)
  - [x] Display tax breakdown per line item and total (`line_tax` / `tax_components` / `tax_breakdown` on sales invoices; Sales UI + print; Alembic `20260813_0093`; purchase invoices + Purchasing UI; Alembic `20260813_0094`)
  - [x] Handle tax exemptions (zero-rated, exempt products)
  - [x] Reverse charge mechanism support (tax-rate `is_reverse_charge` memo on sales/POS/PI; purchase invoice header override; **sales invoice header** `is_reverse_charge` on `POST /sales/invoices` + Create sale checkbox — tax memo only, not charged to customer; Alembic `20260815_0101`)

#### BR-12.3 Tax Reports
- **Description:** Compliance and filing support.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Output tax summary (tax collected on sales) (`GET /reports/tax`; optional `store_id`)
  - [x] Input tax summary (tax paid on purchases) (PI preferred, PO fallback; store via warehouse)
  - [x] Net tax payable/refundable
  - [x] Tax report by period (monthly, quarterly, annually) (`from_date`/`to_date`; Tax UI period + store picker)
  - [x] Export in government filing format (`tax_filing` / `tax_filing_gh`; store filter passed through)

---

### 4.13 Multi-Store Management

#### BR-13.1 Store Operations
- **Description:** Manage multiple retail/service locations.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create stores with unique code, name, location (`GET|POST|PATCH /stores`; Multi-Store UI)
  - [x] Assign store manager and staff (`manager_id`; Multi-Store UI)
  - [x] Store-specific inventory view (warehouse stock + report filters; Shell store context)
  - [x] Store-specific sales reporting (`store_id` on sales reports + Shell store context)
  - [x] Consolidated reporting across all stores (omit `store_id` / header **All stores**)

#### BR-13.2 Inter-Store Transfers
- **Description:** Move stock between stores.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create transfer request with source store, destination store, products, quantities
  - [x] Approval workflow (source store manager → destination store manager)
  - [x] Track transfer status: Draft, Requested, In Transit, Received, Cancelled
  - [x] Reject with required reason (`POST /stores/transfers/{id}/reject` `{ reason }` → `rejection_reason` + status `cancelled`; Multi-Store Transfers Reject reason field)
  - [x] Cancel with required reason (`POST /stores/transfers/{id}/cancel` `{ reason }` → `rejection_reason` + status `cancelled`; same Reject / Cancel reason input)
  - [x] Auto-update inventory at both stores on receipt confirmation
  - [x] Transfer history and reporting (`GET /reports/inventory/transfers`; by status/route; optional `store_id` either-side; Reports Inventory tab + export `inventory_transfers`)

---

### 4.14 Reports & Analytics

#### BR-14.1 Sales Reports
- **Description:** Comprehensive sales analysis.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Daily Sales:** Date, invoice count, total revenue, tax, discounts, net sales (`GET /reports/sales/daily`; optional `store_id`; Reports Sales tab)
  - [x] **Monthly Sales:** Monthly aggregation with trend comparison (`GET /reports/sales/monthly`; optional `store_id`; Reports Sales tab)
  - [x] **Product Sales:** Product-wise quantity and revenue; filter by date, store, category (`GET /reports/sales/products?store_id=&category_id=`; Reports Sales tab + export `sales_products`)
  - [x] **Customer Sales:** Top customers by revenue and frequency (`GET /reports/sales/customers`; invoices + POS; optional `store_id`; Reports Customers tab + export `sales_customers`)
  - [x] **Sales Return Summary:** Returns by reason/customer (`GET /reports/sales/returns`; optional `store_id` via original invoice store; Reports Sales tab + export `sales_returns`)
  - [x] **Salesperson Performance:** Sales by user/role (`GET /reports/sales/salesperson`; optional `store_id` + `department_id`; Reports Salespeople tab + export `sales_salesperson`)

#### BR-14.2 Inventory Reports
- **Description:** Stock visibility and analysis.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Stock Balance:** Current stock per product per warehouse (`GET /reports/inventory/balance`; optional `warehouse_id` / `store_id`; Reports Inventory tab)
  - [x] **Low Stock:** Products below reorder level (`GET /reports/inventory/low-stock`; optional `store_id` / `warehouse_id`; Reports Inventory tab)
  - [x] **Stock Movement:** All in/out/adjustment/transfer transactions (`GET /reports/inventory/movements`; optional `warehouse_id` / `store_id` / `movement_type`; Reports Inventory tab + export)
  - [x] **Stock Valuation:** Standard cost via `GET /reports/inventory/valuation?method=standard` (qty × `product.cost_price`; optional `warehouse_id` / `store_id`); FIFO/LIFO/weighted average deferred (API returns 400)
  - [x] **Expiry Report:** Products nearing expiry (pharmacy/food) (`GET /reports/inventory/expiry?days=&warehouse_id=&store_id=`; Reports Inventory tab + export `inventory_expiry`)

#### BR-14.3 Purchase Reports
- **Description:** Procurement analysis.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] **Purchase Summary:** Total purchases by period (`GET /reports/purchases/summary`; optional `warehouse_id` / `store_id`; Reports Purchases tab)
  - [x] **Supplier Purchases:** Purchase volume and value per supplier (`GET /reports/purchases/suppliers`; optional `warehouse_id` / `store_id`)
  - [x] **Pending Orders:** POs not yet received (`GET /reports/purchases/pending-orders`; draft/sent/partially_received; optional `warehouse_id` / `store_id`; Reports Purchases tab + export)
  - [x] **Purchase Return Summary** (`GET /reports/purchases/returns`; by reason/supplier; optional `warehouse_id` / `store_id`; Reports Purchases tab + export `purchases_returns`)

#### BR-14.4 Expense Reports
- **Description:** Expenditure analysis.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Expense summary by category and period (`GET /reports/expenses/summary`)
  - [x] Budget vs actual comparison (`GET /reports/expenses/budget-vs-actual`; monthly budget scaled by period days / 30)
  - [x] Top expense categories (top 5 by actual on budget-vs-actual)
  - [x] Filter by branch/department/store (`branch_id` / `department_id` / `store_id` on summary + budget-vs-actual + export; Reports Expenses tab)

#### BR-14.5 Financial Reports
- **Description:** Business financial health.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Profit & Loss Statement (`GET /accounting/profit-loss` + `/reports/profit-loss` with date/store/branch filters)
  - [x] Cash Flow Statement (O/I/F + internal transfers; date range; liquid GL direct method; optional `store_id`/`branch_id` for attributable operating cash)
  - [x] Balance Sheet (Assets = Liabilities + Equity; `as_of` reconstructs from posted journals; computed retained earnings)
  - [x] All reports filterable by date range, branch, store (P&L + cash-flow + **BS + TB** support date/`as_of`/store/branch via attributable journals; daily/monthly/product/customer/salesperson/returns sales support `store_id`; purchase summary/suppliers/pending/returns support `store_id`/`warehouse_id`; inventory balance/valuation/expiry/movements/low-stock/transfers support `store_id`/`warehouse_id`; tax report/filing support `store_id`; expense summary/budget-vs-actual support `branch_id`/`department_id`/`store_id`)
  - [x] Comparative reports (current period vs previous period) — BS `compare=prior_period|prior_year`

---

### 4.15 Notifications

#### BR-15.1 Notification Types
- **Description:** Automated alerts for business events.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Low Stock:** When product reaches reorder level (`low_stock` scan / alerts; emails inventory_officer + store_manager + admins)
  - [x] **New Orders:** When sales order is created (`new_order` on create + confirm; preferences channel)
  - [x] **Purchase Received:** When GRN is approved (`purchase_received` on GRN post)
  - [x] **Payment Due:** When invoice/bill approaches due date (`payment_due` scan)
  - [x] **Credit Limit Reached:** When customer exceeds credit threshold (`credit_limit` notification at ≥80% utilization / override on invoice post)
  - [x] **Shift Variance:** When cash reconciliation shows discrepancy (`shift_variance` on close)
  - [x] **Expense Approval Required:** When expense exceeds threshold (`expense_approval`)

#### BR-15.2 Notification Channels
- **Description:** Multi-channel alert delivery.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Dashboard:** In-app notification bell with badge count (Shell dropdown panel + unread badge; `/notifications` center)
  - [x] **Email:** SMTP integration; HTML email templates (`emailer.render_branded_html` wraps outbound HTML with company name, optional logo + print header/footer; tenant SMTP overrides; console fallback in dev)
  - [x] **SMS:** SMS gateway integration (Twilio, regional providers) (`GET|PATCH /settings/sms` tenant Twilio overrides → env `TWILIO_*` → console; `POST /settings/sms/test`; auth token encrypted; notifications + POS receipt SMS use tenant config)
  - [x] User preference for channel per notification type (`GET|PATCH /notifications/settings`; dashboard/email/sms toggles per category)

---

### 4.16 Backup & Recovery

#### BR-16.1 Manual Backup
- **Description:** On-demand data protection.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] One-click backup initiation by Super Admin (`POST /backup`; Backup UI; company_admin / super_admin)
  - [x] Backup includes database, uploaded files, configurations (encrypted `.ribbak` with tenant config snapshot + business datasets incl. product image rows; binary media blob packaging / restore-to-new-tenant remain follow-ups — see `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`)
  - [x] Download backup archive (`GET /backup/{id}/download` + `X-Checksum-SHA256`)
  - [x] Backup encryption (Fernet envelope via `BACKUP_ENCRYPTION_KEY` or derived key)

#### BR-16.2 Scheduled Backup
- **Description:** Automated data protection.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Configurable schedule (daily, weekly) (`GET|PATCH /backup/settings`; Celery `run_due_backups` / `POST /backup/run-due`)
  - [x] Retention policy (keep last N backups) (`retention_count` 1–365; prune after success)
  - [ ] Backup storage to S3-compatible storage (MVP writes local `BACKUP_DIR`; ops offsite sync / in-app upload remain packaging follow-ups)
  - [x] Failure alerts to admin (`BackupJob.status=failed` + in-app **Backup failed** system notification for schedule/create failures and non-writable backup dir)

#### BR-16.3 Database Restore
- **Description:** Disaster recovery capability.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Restore from backup archive (`POST /backup/{id}/restore` dry-run + `confirm_text=RESTORE` apply; Backup UI)
  - [ ] Restore to new tenant (for testing) (explicitly out of scope for logical MVP — cross-tenant restore blocked)
  - [x] Restore validation (checksum verification) (`POST /backup/{id}/verify` + restore proof / checksum guards)
  - [ ] Point-in-time recovery (if WAL archiving enabled) (ops WAL/PITR strategy — `docs/DR_WAL_PITR_RUNBOOK.md`; not part of logical `.ribbak` MVP)

---

### 4.17 Audit Logs

#### BR-17.1 Activity Tracking
- **Description:** Immutable record of system activities.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Login/Logout:** Timestamp, IP address, device, success/failure (`module=auth` login/logout (+ failed login); `user_agent` / `ip_address` on `AuditLog`)
  - [x] **Product Changes:** Create, update, delete with before/after values (`inventory` domain events + HTTP mutation middleware; `product_update` details include `changes.{field}.{before,after}`)
  - [x] **Sales:** Invoice creation, modification, cancellation (`module=sales` domain audits + middleware on `/sales/*`)
  - [x] **Purchases:** PO, GRN, invoice changes (`module=purchasing` domain audits + middleware)
  - [x] **User Activity:** Permission changes, role assignments, deletions (`module=users` role/permission/active audits)
  - [x] **Financial:** Journal entry posting, account modifications (`module=accounting` journal/account audits + middleware)

#### BR-17.2 Audit Log Management
- **Description:** Search and retention of audit data.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Filter by user, module, action type, date range
  - [x] Export audit logs (CSV, PDF)
  - [x] Tamper-proof storage (append-only, hashed)
  - [x] Retention policy: minimum 7 years for financial records (cold archive JSONL + `archived_at`; Audit UI retention card / Archive cold now; never purged)

---

### 4.18 API

#### BR-18.1 Authentication API
- **Description:** Secure API access.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] OAuth2 / JWT token generation
  - [x] Token refresh endpoint
  - [x] API key support for service integrations (Integrations UI `/integrations`: create/revoke/usage)
  - [x] Rate limiting per tenant

#### BR-18.2 Products API
- **Description:** Product data access and management.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] CRUD operations for products, categories, brands, units (`GET|POST|PATCH /products`; soft-deactivate via `is_active`; `GET|POST|PATCH|DELETE /catalog/categories|brands|units`)
  - [x] Bulk import/export
    - Complete (MVP): `GET|POST /products/import[/template]`; dedicated `GET /products/export` (same CSV columns); also `GET /products` + `POST /reports/export` (`inventory_balance` / related)
  - [x] Stock level queries (`product.stock_qty`; `GET /inventory/warehouse-stock`; `GET /products/{id}/warehouse-stock`; `GET /inventory/low-stock`; `GET /reports/inventory/balance`; Inventory **Lookup** tab)
  - [x] Barcode lookup (`GET /inventory/products/lookup?barcode=` / `?q=`; Inventory **Lookup** UI; also `GET /pos/products/search?barcode=` for POS)

#### BR-18.3 Customers API
- **Description:** Customer data access.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] CRUD operations for customers and customer groups
  - [x] Balance inquiry (`balance` on party serialize; `GET /customers/{id}/credit` + `/outstanding`)
  - [x] Purchase history (`GET /customers/{id}/history` — invoices/POS, returns, payments)

#### BR-18.4 Sales API
- **Description:** Sales transaction API.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create quotations, sales orders, invoices (`POST /sales/quotations|orders|invoices` + list/get/confirm/post flows)
  - [x] Record payments (`POST /sales/payments` / Credit customer pay)
  - [x] Sales return processing (`POST /sales/returns` + credit-note flows)
  - [x] POS transaction submission (`POST /pos/sessions/open`; `POST /pos/sales`)

#### BR-18.5 Purchases API
- **Description:** Procurement API.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create purchase requests, orders, GRNs, invoices (`POST /purchasing/requests|orders|grn|invoices` + convert/send/approve flows)
  - [x] Supplier management (`GET|POST|PATCH /suppliers` + soft status)
  - [x] Payment recording (`POST /suppliers/{id}/payments` / Credit supplier pay)

#### BR-18.6 API Standards
- **Description:** Consistent API design.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] RESTful design with standard HTTP methods
  - [x] JSON request/response format
  - [x] Standard error response structure
  - [x] Pagination for list endpoints
  - [x] Versioning (/api/v1/)
  - [x] OpenAPI/Swagger documentation auto-generated
  - [x] Webhook support for event subscriptions (Integrations UI: create/test/rotate/disable/delete; delivery history `GET /webhooks/{id}/deliveries` + manual `POST .../deliveries/{id}/retry`; Celery `retry_due_webhooks`; live emits `sale.created`/`sale.paid` (invoice+POS)/`customer.created`/`supplier.created`/`purchase.order.created`/`purchase.grn.received`/`expense.approved`/`stock.low`/`stock.in` (non-GRN inbound)/`stock.out` (non-POS/invoice outbound)/`tenant.suspended`/`user.login` (interactive)/`webhook.test`; subscriber HMAC verify samples API docs §17.4 + Integrations **Verify signature**)

---

### 4.19 Authentication & Security

#### BR-19.1 Authentication
- **Description:** Secure user access.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Email/password login with bcrypt hashing (`POST /auth/login`; `hash_password` / `verify_password`)
  - [x] Password complexity requirements (min 8 chars, mixed case, number, symbol) (`validate_password_strength` on register/user create/reset)
  - [x] Account lockout after 5 failed attempts (30-minute cooldown) (`failed_login_attempts` / `locked_until`)
  - [x] Email verification before first login (`POST /auth/login` returns `403 EMAIL_NOT_VERIFIED` until verified; `POST /auth/verify-email`; `POST /auth/resend-verification`; login resend UX + `/verify-email`)
  - [x] Password reset via secure token link (expires in 1 hour) (`POST /auth/password-reset-request` + `POST /auth/password-reset`; login **Forgot password?** → `/forgot-password`; confirm `/reset-password?token=`; console/SMTP email)

#### BR-19.2 Two-Factor Authentication (2FA)
- **Description:** Enhanced account security.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Optional TOTP-based 2FA (Google Authenticator, Authy) (`/auth/2fa/*`; gated by `LOGIN_2FA_ENABLED`; Security UI)
  - [x] QR code setup for 2FA (`POST /auth/2fa/setup` → `qr_png_base64` / otpauth URI; confirm enroll)
  - [x] Backup recovery codes (`POST /auth/2fa/backup-codes`; hashed; usable as second factor)
  - [x] Enforce 2FA for Super Admin and Company Admin roles (`TOTP_ENFORCED_ROLES` + `must_enroll_2fa` when `LOGIN_2FA_ENABLED`; passkeys also satisfy MFA)

#### BR-19.3 Session Management
- **Description:** Control active user sessions.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] JWT token with configurable expiry (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 15 minutes; refresh via `REFRESH_TOKEN_EXPIRE_DAYS`)
  - [x] Refresh token rotation (`POST /auth/refresh` revokes prior refresh and issues a new session)
  - [x] View active sessions per user (`GET /auth/sessions` self-scoped; Security UI)
  - [x] Remote session termination (`DELETE /auth/sessions/{id}`; Security UI)
  - [x] Auto-logout on inactivity (client idle logout; tenant `inactivity_timeout_minutes` via Company / `PATCH /tenants/me`, default 30, range 5–480; exposed on `GET /me`; Alembic `20260813_0089`)

---

### 4.20 System Settings

#### BR-20.1 Company Information
- **Description:** Global company settings.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Edit legal name, address, contact, tax ID (`legal_name`, HQ/billing/shipping addresses, `contact_person`, `tax_registration_number` via Company profile)
  - [x] Upload company logo (used on invoices, receipts)

#### BR-20.2 Formatting
- **Description:** Regional display preferences.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Date format selection (DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD) (`tenants.date_format`; Company UI; Alembic `20260813_0088`)
  - [x] Number format (decimal separator, thousand separator) (`decimal_separator` / `thousand_separator`; Sales totals use prefs)
  - [x] Time format (12h / 24h) (`tenants.time_format`; Company preview + `frontend/lib/format.ts`)

#### BR-20.3 Email Settings
- **Description:** SMTP configuration for outbound emails.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] SMTP host, port, username, password (`tenants.email_settings` JSON; `GET|PATCH /settings/email`; password encrypted as `password_enc`, never returned — `has_password` only; Company UI)
  - [x] TLS/SSL encryption (`use_tls` / `use_ssl` mutually exclusive; tenant override → env `SMTP_*` → console)
  - [x] Test email functionality (`POST /settings/email/test` uses resolved tenant/env config)
  - [x] Default sender name and email (`from_name` / `from_email` on tenant settings + env fallback)

#### BR-20.4 Numbering & Templates
- **Description:** Document customization.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Configure invoice numbering prefix and series (e.g., INV-2026-0001) via Sales settings
  - [x] Configure PO, GRN, purchase invoice, purchase request, purchase return, debit note, supplier payment, quotation, sales order, sales return, credit note, payment receipt, journal, cash/bank transfer, POS sale/shift, stock transfer/count, opening stock, expense numbering (`GET|PATCH /purchasing/settings` for PO/GRN/PI/PREQ/PR/DN/SPY; `GET|PATCH /sales/settings` for INV/QT/SO/SR/CN/RCP; `GET|PATCH /accounting/settings` for JE + XFER; `GET|PATCH /pos/settings` for POS sale + SHIFT session; `GET|PATCH /inventory/settings` for TR + SC + OS; `GET|PATCH /expenses/settings` for EXP)
  - [x] Receipt template selection and customization (default paper via `GET|PATCH /settings/print`; per-request `paper=`)
  - [x] Invoice template selection and customization (default a4|thermal via `/settings/print`; per-request `template=`)
  - [x] Header/footer customization with company branding (logo on PDFs + header/footer text)

---

### 4.21 AI Business Assistant

#### BR-21.1 AI ERP Chat Assistant
- **Description:** Natural language interface for ERP operations.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Accept natural language queries ("What is my top selling product this month?")
  - [ ] Execute commands via chat ("Create a purchase order for 50 units of Product X")
  - [ ] Context-aware responses based on user role and permissions
  - [ ] Chat history persistence

#### BR-21.2 AI Dashboard Insight
- **Description:** Automated anomaly detection and recommendations.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Highlight unusual sales drops or spikes (`GET /ai/insights` composed rules: today/yesterday, MTD/prior month, and 7d vs prior 7d ≥25%; also included in weekly digest)
  - [x] Flag expense anomalies (budget overage, statistical outliers, duplicate payee/amount day — via expense analysis rules composed into insights/digest)
  - [x] Suggest actions ("Restock Product Y — sales up 40% this week") (rising-velocity + at-risk stock from inventory forecasts → action signals)
  - [x] Weekly insight digest email (tenant-scoped composed-rule digest to active company/super admins via `send_weekly_ai_insight_digest`, Celery beat Monday 07:00 UTC; `POST /ai/insights/digest` emails the signed-in user's preview; Jobs console exposes schedule/manual trigger)

#### BR-21.3 Smart Inventory Intelligence
- **Description:** AI-powered inventory optimization.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Demand forecasting per product (7-day, 30-day, 90-day)
    - Complete (MVP rule-based): `velocity × horizon` from invoices+POS (`docs/AI_INVENTORY_MVP.md`)
  - [x] Optimal reorder quantity recommendations
    - Complete (MVP): cover+lead target vs on-hand
  - [x] Seasonality detection
    - Partial: rising/falling/stable vs prior window (not full seasonal model)
  - [x] Dead stock identification
    - Complete (MVP): on-hand with no sales in 90 days

#### BR-21.4 AI Low Stock Prediction
- **Description:** Predictive stockout prevention.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Predict stockouts 7–14 days in advance
    - Complete (MVP): `days_to_stockout` vs `days_ahead`
  - [x] Consider sales velocity, seasonality, lead time
    - Complete (MVP heuristic); supplier-specific lead time post-MVP
  - [x] Confidence score on predictions
  - [x] Auto-generate purchase suggestions
    - Complete (MVP): `POST /ai/inventory/low-stock-prediction/requests` → draft PRs; AI page **Create draft PR(s)** UI

#### BR-21.5 AI Sales Analysis
- **Description:** Deep sales pattern recognition.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Sales trend forecasting
    - Complete (MVP heuristic): monthly series + next-month ratio forecast (`docs/AI_SALES_EXPENSE_MVP.md`)
  - [x] Customer segmentation (RFM analysis)
    - Complete (MVP quintile RFM segments)
  - [x] Product affinity analysis (frequently bought together)
    - Complete (MVP pair counts)
  - [x] Peak hour/day predictions
    - Complete (MVP histograms)

#### BR-21.6 AI Expense Analysis
- **Description:** Intelligent cost management.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Expense categorization from receipt OCR
    - Complete (MVP): keyword category suggest on OCR; human apply via PATCH
  - [x] Budget variance alerts
  - [x] Unusual expense pattern detection
  - [x] Cost optimization suggestions
    - Complete (MVP rule strings)

#### BR-21.7 AI Report Generator
- **Description:** Natural language to report.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Generate reports from text prompts ("Show me monthly sales for Q2")
    - Complete (MVP constrained parser → EXPORTABLE types; `docs/AI_REPORT_GENERATOR_MVP.md`)
  - [x] Export generated reports
    - Complete (MVP): csv/pdf/xlsx via `POST /ai/reports/export`
  - [x] Save report templates for reuse
    - Complete (MVP): `ai_report_templates` + CRUD

#### BR-21.8 AI Document Assistant
- **Description:** Intelligent document processing.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] OCR extraction from invoices, receipts, purchase orders
    - Complete (MVP): unified `POST /ai/documents/analyze` reuses pypdf/Tesseract parser; see `docs/AI_DOCUMENT_MVP.md`
  - [x] Auto-match extracted data to system records
    - Complete (MVP): party name similarity + purchase-order number match; receipt category keyword suggest
  - [x] Data validation and discrepancy flagging
    - Complete (MVP): missing fields, low confidence, amount/PO mismatches, duplicate supplier/expense references
  - [x] Save reviewed extract as draft expense
    - Complete (MVP): `POST /ai/documents/create-expense` + AI **Create draft expense**; requires `expenses:write`; analyze remains suggest-only
  - [x] Save reviewed extract as draft purchase invoice (PO-matched)
    - Complete (MVP): `POST /ai/documents/create-purchase-invoice` + AI **Create draft purchase invoice**; copies PO lines; requires `purchasing:write`; no line-item OCR

#### BR-21.9 AI Customer Assistant (Basic)
- **Description:** Customer intelligence.
- **Priority:** Low
- **Acceptance Criteria:**
  - [x] Customer churn risk scoring
    - Complete (MVP rule-based): RFM segment + recency → `churn_risk` / `risk_level`; see `docs/AI_CUSTOMER_MVP.md`
  - [x] Best customer identification
    - Complete (MVP): champions/loyal or high RFM composite
  - [x] Personalized promotion suggestions
    - Complete (MVP): segment promo copy + affinity partner SKUs

#### BR-21.10 AI Security Monitor (Basic)
- **Description:** Behavioral security analysis.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Detect unusual login patterns (time, location, device)
    - Complete (MVP rule-based): unusual hour + new IP; device fingerprinting remains post-MVP
  - [x] Flag suspicious transaction patterns
    - Complete (MVP rule-based): HTTP write bursts + cancel/restore/delete bursts + AI query bursts
  - [x] Alert admins on potential fraud indicators
    - Complete (MVP): in-app `security` notifications when risk_score ≥ threshold; `GET /ai/security/alerts`

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Requirement | Target |
|-------------|--------|
| Page Load Time | < 2 seconds (p95) |
| API Response Time | < 200ms for simple queries; < 1s for complex reports |
| POS Transaction Completion | < 3 seconds from scan to receipt |
| Dashboard Data Refresh | < 5 minutes for KPIs |
| Concurrent Users | Support 500+ concurrent users per tenant |
| Report Generation | < 10 seconds for standard reports; < 60 seconds for complex analytics |
| Search Response | < 500ms for product/customer search |

### 5.2 Scalability

| Requirement | Target |
|-------------|--------|
| Tenants | Support 10,000+ tenants |
| Products per Tenant | Support 100,000+ products |
| Transactions per Day | Support 1,000,000+ transactions platform-wide |
| Database | Horizontal scaling via read replicas |
| File Storage | Auto-scaling S3-compatible storage |
| Auto-Scaling | Kubernetes HPA for backend and worker pods |

### 5.3 Availability & Reliability

| Requirement | Target |
|-------------|--------|
| Uptime SLA | 99.9% (excluding scheduled maintenance) |
| Scheduled Maintenance | < 4 hours/month, announced 72 hours in advance |
| Backup Frequency | Daily automated backups; real-time WAL archiving |
| Recovery Time Objective (RTO) | < 4 hours |
| Recovery Point Objective (RPO) | < 15 minutes |
| Disaster Recovery | Multi-region failover capability |

### 5.4 Security

| Requirement | Target |
|-------------|--------|
| Data Encryption at Rest | AES-256 |
| Data Encryption in Transit | TLS 1.3 |
| Password Storage | bcrypt with salt (cost factor 12+) |
| API Authentication | JWT with RS256; OAuth2 flows |
| Session Security | HttpOnly cookies, CSRF protection, XSS prevention |
| Tenant Isolation | Database-level + application-level validation |
| Audit Logging | Immutable, append-only logs with integrity hashing |
| Vulnerability Scanning | Weekly automated scans; immediate patching for critical CVEs |
| Penetration Testing | Annual third-party penetration test |

### 5.5 Usability

| Requirement | Target |
|-------------|--------|
| Browser Support | Chrome, Firefox, Safari, Edge (last 2 versions) |
| Mobile Responsiveness | Fully functional on tablets and phones |
| Accessibility | WCAG 2.1 Level AA compliance |
| Onboarding Time | New user productive within 30 minutes |
| Training Material | In-app tooltips, guided tours, help center |
| Language Support | English (MVP); i18n framework for future localization |

### 5.6 Maintainability

| Requirement | Target |
|-------------|--------|
| Code Coverage | > 80% unit test coverage |
| API Documentation | Auto-generated OpenAPI/Swagger |
| Database Migrations | Versioned, reversible migrations (Alembic) |
| Logging | Structured JSON logging with correlation IDs |
| Monitoring | Application metrics, error tracking, performance monitoring |
| CI/CD | Automated testing, building, and deployment via GitHub Actions |

### 5.7 Compliance

| Requirement | Target |
|-------------|--------|
| Data Privacy | GDPR-ready (right to erasure, data portability, consent management) |
| Financial Audit | GAAP/IFRS-compliant reporting structure |
| Tax Compliance | VAT/GST reporting with audit trail |
| Retention Policy | Financial records: 7+ years; operational logs: 2 years |

---

## 6. User Roles & Permissions

### 6.1 Role Definitions

| Role | Description | Typical Users |
|------|-------------|---------------|
| **Super Admin** | Platform-level administrator with access to all tenants and system settings | RIBDIGI internal staff |
| **Company Admin** | Full control over one tenant; manages users, branches, settings, billing | Business owner, CEO, CFO |
| **Store Manager** | Manages store operations, inventory, sales, and staff within assigned store(s) | Store manager, branch head |
| **Sales Officer** | Handles sales transactions, quotations, orders, and customer management | Sales representative |
| **Inventory Officer** | Manages stock, purchasing, suppliers, and warehouse operations | Warehouse manager, procurement |
| **Accountant** | Manages accounting, financial reports, tax, and expense approvals | Bookkeeper, accountant |
| **Cashier** | Operates POS, processes sales, handles cash, opens/closes shifts | Front-desk cashier |

### 6.2 Permission Matrix (Simplified)

| Module | Super Admin | Company Admin | Store Manager | Sales Officer | Inventory Officer | Accountant | Cashier |
|--------|:-----------:|:-------------:|:-------------:|:-------------:|:-----------------:|:----------:|:-------:|
| Tenant Management | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| User Management | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Dashboard | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Product Catalog | ✅ | ✅ | View | View | ✅ | View | View |
| Stock Operations | ✅ | ✅ | View | ❌ | ✅ | View | ❌ |
| Purchasing | ✅ | ✅ | View | ❌ | ✅ | View | ❌ |
| Sales | ✅ | ✅ | ✅ | ✅ | View | View | View |
| POS | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Expense Entry | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Expense Approval | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Accounting | ✅ | ✅ | View | ❌ | ❌ | ✅ | ❌ |
| Financial Reports | ✅ | ✅ | View | ❌ | ❌ | ✅ | ❌ |
| Credit Management | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Tax Configuration | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Reports | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | View |
| System Settings | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Backup & Restore | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Audit Logs | ✅ | ✅ | View Own | View Own | View Own | View Own | View Own |

> **Legend:** ✅ = Full Access | View = Read-only | View Own = Can only view records they created | ❌ = No Access

---

## 7. Business Workflows

### 7.1 Purchase-to-Pay Workflow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Purchase Request│───▶│ Purchase Order  │───▶│      GRN      │
│   (Internal)    │    │  (To Supplier)  │    │ (Goods Receipt) │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                              ┌────────────────────────┘
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │Purchase Invoice │───▶│  Payment to     │
                       │  (Payable)      │    │    Supplier     │
                       └─────────────────┘    └─────────────────┘
```

**Process Steps:**
1. Inventory Officer identifies low stock and creates Purchase Request
2. Store Manager approves Purchase Request
3. Inventory Officer converts PR to Purchase Order and sends to Supplier
4. Supplier delivers goods; Inventory Officer creates GRN referencing PO
5. Supplier sends invoice; Accountant creates Purchase Invoice from GRN
6. Accountant schedules/records payment; system updates AP and cash/bank

### 7.2 Order-to-Cash Workflow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Quotation     │───▶│   Sales Order   │───▶│  Sales Invoice  │
│  (Optional)     │    │  (Reservation)  │    │   (Billing)     │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                              ┌────────────────────────┘
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Payment from    │───▶│  Sales Return   │
                       │   Customer      │    │  (If needed)    │
                       └─────────────────┘    └─────────────────┘
```

**Process Steps:**
1. Sales Officer creates Quotation for customer (optional)
2. Customer confirms; Sales Officer converts to Sales Order
3. Inventory is reserved; order is processed and packed
4. Sales Officer generates Sales Invoice
5. Customer pays (cash, card, credit, digital wallet)
6. Payment is recorded; system updates AR and cash/bank
7. If return occurs, Sales Return is processed with credit note

### 7.3 POS Transaction Workflow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Shift Open     │───▶│  Scan/Search    │───▶│  Apply Discount │
│ (Cash Float)    │    │     Product     │    │  & Select Cust  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                              ┌────────────────────────┘
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Process Payment │───▶│  Print Receipt  │
                       │ (Multi-method)  │    │  & Close Sale   │
                       └─────────────────┘    └─────────────────┘
                                                       │
                              ┌────────────────────────┘
                              ▼
                       ┌─────────────────┐
                       │  Shift Close    │
                       │ (Reconciliation)│
                       └─────────────────┘
```

**Process Steps:**
1. Cashier opens shift with starting cash float
2. Products are scanned or searched and added to cart
3. Discounts applied; customer selected (or walk-in)
4. Payment processed (cash, card, wallet, credit)
5. Receipt printed or emailed; sale recorded
6. At shift end, cashier counts cash and reconciles with system
7. Shift report generated with sales, returns, discounts, variance

### 7.4 Expense Approval Workflow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Expense Entry  │───▶│ Manager Review  │───▶│  Accountant     │
│  + Attachment   │    │  (If >$100)     │    │  Post to Books  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Process Steps:**
1. Employee enters expense with category, amount, receipt attachment
2. If amount exceeds threshold, manager receives notification for approval
3. Manager approves/rejects with comments
4. Approved expense is posted to chart of accounts by Accountant
5. Payment is scheduled/recorded

### 7.5 Inter-Store Transfer Workflow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Transfer Request │───▶│ Source Approval │───▶│  Ship Goods     │
│  (Create)       │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                              ┌────────────────────────┘
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Dest. Approval  │───▶│  Receive &      │
                       │                 │    │  Update Stock   │
                       └─────────────────┘    └─────────────────┘
```

**Process Steps:**
1. Source store creates transfer request with products and quantities
2. Source store manager approves and ships goods
3. Goods in transit status updated
4. Destination store receives and confirms quantity
5. Stock deducted at source; stock added at destination

---

## 8. Data Requirements

### 8.1 Data Retention

| Data Type | Retention Period | Action After Retention |
|-----------|-----------------|----------------------|
| Financial Transactions | 7 years | Archive to cold storage |
| Audit Logs | 7 years | Archive to cold storage |
| Sales/Purchase Documents | 7 years | Archive to cold storage |
| Product Data | Indefinite | Soft delete only |
| Customer/Supplier Data | Indefinite | Anonymize on request (GDPR) |
| User Session Logs | 2 years | Delete |
| Notification History | 90 days | Delete |
| Backup Archives | 30 days | Delete per retention policy |

### 8.2 Data Volume Estimates (Per Tenant)

| Entity | Initial Volume | Growth Rate (Monthly) |
|--------|---------------|----------------------|
| Products | 500–5,000 | +50–200 |
| Customers | 100–1,000 | +20–100 |
| Suppliers | 10–100 | +1–5 |
| Sales Transactions | 1,000–10,000 | +500–3,000 |
| Purchase Transactions | 100–1,000 | +50–200 |
| Inventory Movements | 5,000–50,000 | +1,000–5,000 |
| Users | 3–20 | +0–2 |

---

## 9. Integration Requirements

### 9.1 External Integrations (MVP)

| Integration | Purpose | Priority |
|-------------|---------|----------|
| **SMTP Provider** | Email notifications (SendGrid, AWS SES) | Critical |
| **SMS Gateway** | SMS alerts (Twilio, regional providers) | High |
| **S3-Compatible Storage** | File uploads, backups (AWS S3, MinIO) | Critical |
| **Payment Gateway** | Card/wallet payments (Stripe, PayPal) | High |
| **Barcode Hardware** | USB/Bluetooth scanner support | High |
| **Thermal Printer** | Receipt printing (ESC/POS protocol) | High |

### 9.2 Future Integrations (Post-MVP)

| Integration | Purpose |
|-------------|---------|
| E-commerce (Shopify, WooCommerce) | Sync online and offline inventory/sales |
| Accounting Software (QuickBooks, Xero) | Bi-directional sync |
| CRM (HubSpot, Salesforce) | Customer data sync |
| Payroll (Gusto, ADP) | Employee cost integration |
| Shipping (FedEx, UPS) | Delivery tracking |
| IoT Sensors | Temperature, stock level monitoring |

---

## 10. Compliance & Regulatory Requirements

### 10.1 Data Protection
- **GDPR (EU):** Right to access, rectification, erasure, portability; consent management; DPO contact
- **PCI-DSS:** If handling card data directly (prefer tokenization via payment gateway)
- **Local Data Laws:** Compliance with data residency requirements per market

### 10.2 Financial Compliance
- **GAAP/IFRS:** Standard chart of accounts structure; accrual accounting support
- **Tax Compliance:** VAT/GST calculation and reporting; audit trail for tax authorities
- **Audit Requirements:** Immutable transaction logs; tamper-evident records

### 10.3 Industry-Specific Compliance
- **Pharmacy:** Drug expiry tracking; batch traceability; prescription record retention
- **Food Service:** Ingredient traceability; temperature logging (future); allergen tracking
- **Manufacturing:** BOM tracking; production batch records; quality control documentation

---

## 11. Appendix

### A. Glossary
See Section 1.4 for acronym definitions.

### B. Reference Documents
- `README.md` — Product introduction and technical overview
- `PRODUCT_OVERVIEW.md` — Vision, mission, and business model
- `USER_MANUAL.md` — End-user operational guide
- `ADMIN_MANUAL.md` — System administration guide
- `DEVELOPER_GUIDE.md` — Coding standards and development environment
- `API_DOCUMENTATION.md` — API standards and endpoint reference
- `SECURITY_GUIDE.md` — Security architecture and threat model
- `DEPLOYMENT_GUIDE.md` — Docker, Kubernetes, and CI/CD guide

### C. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | August 2026 | Product Team | Initial MVP requirements |

---

<p align="center">
  <strong>RIBDIGI BUSINESS ERP</strong><br>
  <em>One ERP Platform. Unlimited Business.</em><br><br>
  © 2026 RIBDIGI. All rights reserved.
</p>
