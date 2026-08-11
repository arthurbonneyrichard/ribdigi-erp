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
  - [x] User can register with company name, email, password, industry type — Stage 21 T1 (`POST /tenants`; `test_tenant_lifecycle_t1.py`)
  - [x] System validates email uniqueness — Stage 21 T1 (unique tenant slug; admin email unique per tenant via `users` constraint; login is tenant-scoped)
  - [x] System auto-creates isolated tenant database/schema — Stage 21 T1 (shared-schema + `tenant_id` + `seed_tenant_defaults`; schema-per-tenant deferred ADR-001)
  - [x] System sends email verification link — Stage 21 T1 (`email_verify` token + `POST /auth/verify-email`; console/SMTP send path)
  - [x] Tenant status defaults to "Trial" — Stage 21 T1 (`status=trial` + `trial_ends_at`)

#### BR-1.2 Company Profile
- **Description:** Tenant administrators can configure company identity and operational settings.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Upload and display company logo — Stage 21 T1 (`POST/GET /tenants/me/logo`)
  - [x] Edit company name, address, phone, email, website — Stage 21 T1 (`PATCH /tenants/me`)
  - [x] Configure fiscal year start date — Stage 21 T1 (`fiscal_year_start`)
  - [x] Set default currency and time zone — Stage 21 T1 (`currency` / `timezone`)
  - [x] Select industry from predefined list (Retail, Pharmacy, Restaurant, Bakery, Wholesale, Manufacturing) — Stage 21 T1 (`VALID_INDUSTRIES`)

#### BR-1.3 Subscription Plan Management
- **Description:** Track and manage tenant subscription lifecycle.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Support statuses: Trial, Active, Suspended — Stage 21 T1 (`trial` / `active` / `suspended`; also `grace`)
  - [x] Automatic trial expiration notification (7 days, 3 days, 1 day before) — Stage 21 T1 (`process_trial_lifecycle` billing notifications)
  - [x] Grace period handling for suspended tenants (read-only access) — Stage 21 T1 (`status=grace` → `TENANT_READ_ONLY` on writes; self-activate restores access)
  - [x] Upgrade/downgrade plan capability — Stage 21 T1 (`plan_code` metadata; billing deferred ADR-002 — no payment processed)

#### BR-1.4 Data Isolation
- **Description:** Ensure complete data separation between tenants.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Tenant A cannot access Tenant B data under any circumstance — Stage 21 I1 (`test_tenant_isolation_seeds_i1.py`; product list + foreign invoice 404)
  - [x] Database-level isolation (separate schemas or databases) — Stage 21 I1 (MVP shared-schema + `tenant_id` per ADR-001; schema-per-tenant deferred)
  - [x] API requests include tenant context validation — Stage 21 I1 (JWT `tenant_id` + mismatched `X-Tenant-ID` → 403 Cross-tenant)
  - [x] Backup operations are tenant-scoped — Stage 21 I1 (`GET/POST /backup`; foreign backup id 404)

Deferred ADR honesty (Stage 31 R1): index of ADR-001–006 MVP Accepted vs post-MVP Remaining — `docs/DEFERRED_ADR_REGISTER_MVP.md`, `ops/mvp/deferred-adr-register.json` (`test_deferred_adr_register_r1.py`); not an implementation of billing / schema-per-tenant / i18n / store membership / hard-delete. Post-MVP backlog packaging (Stage 32 B1): consolidated deferred ADR + operator Remaining + product deferred index — `docs/POST_MVP_BACKLOG_MVP.md`, `ops/mvp/post-mvp-backlog.json` (`test_post_mvp_backlog_b1.py`); backlog ≠ implemented Complete.

#### BR-1.5 Tenant Database Initialization
- **Description:** Automated setup of tenant-specific database with seed data.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-create schema/tables on registration — Stage 21 I1 (`POST /tenants` → `seed_tenant_defaults` on shared schema)
  - [x] Seed default chart of accounts based on industry — Stage 21 I1 (`ensure_default_accounts`; industry-agnostic system COA for MVP)
  - [x] Seed default tax rates — Stage 21 I1 (default VAT tax rate on registration)
  - [x] Seed default units of measure — Stage 21 I1 (`ensure_default_catalog` UoM)
  - [x] Seed default expense categories — Stage 21 I1 (`ensure_default_categories`)

---

### 4.2 System Administration

#### BR-2.1 Company Information
- **Description:** Centralized company details editable by Company Admin.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] CRUD operations on company legal name, registration number, tax ID — Stage 21 C1 (`PATCH/GET /tenants/me` `legal_name`/`registration_number`/`tax_registration_number`; create via tenant registration; `test_company_currency_tax_c1.py`)
  - [x] Multiple address support (billing, shipping, warehouse) — Stage 21 C1 (typed fields `billing_address`/`shipping_address`/`warehouse_address`; not multi-row address entity CRUD)
  - [x] Contact person designation — Stage 21 C1 (`contact_person_name`/`email`/`phone`)

#### BR-2.2 Branch Management
- **Description:** Manage multiple business branches under one tenant.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create/edit/delete branches — Stage 21 O1 (`POST/PATCH /branches`; soft-deactivate via `is_active`, hard delete deferred ADR-003; `test_org_units_o1.py`)
  - [x] Assign branch code and manager — Stage 21 O1 (`code` + `manager_id`)
  - [x] Branch-specific address and contact — Stage 21 O1 (`address`, `phone`, `email`)
  - [x] Deactivate branch without data loss — Stage 21 O1 (`is_active=false` retains manager/address on list)

#### BR-2.3 Store Management
- **Description:** Configure retail/service outlets.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create stores with name, code, location — Stage 21 O1 (`POST /stores` name/code/address)
  - [x] Assign store manager — Stage 21 O1 (`manager_id`)
  - [x] Configure store operating hours — Stage 21 O1 (`operating_hours` JSON)
  - [x] Link store to branch and warehouse — Stage 21 O1 (`branch_id` + auto `warehouse_id`/`WH-{code}`)

#### BR-2.4 Warehouse Setup
- **Description:** Configure storage locations for inventory.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create multiple warehouses — Stage 21 O1 (store-linked + `POST /warehouses`; `test_org_units_o1.py`)
  - [x] Define warehouse type (retail, bulk, cold storage, etc.) — Stage 21 O1 (`warehouse_type` ∈ retail/main/cold/bulk/transit)
  - [x] Assign warehouse manager — Stage 21 O1 (`manager_id`)
  - [x] Configure warehouse address and capacity — Stage 21 O1 (`address`, `capacity`)

#### BR-2.5 Department Setup
- **Description:** Organizational structure configuration.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Create departments (Sales, Inventory, Accounting, etc.) — Stage 21 O1 (`POST /departments`)
  - [x] Assign department head — Stage 21 O1 (`head_user_id`)
  - [x] Department-based reporting filters — Stage 21 O1 (`GET /expenses?department_id=`; department record-scope elsewhere)

#### BR-2.6 Currency Setup
- **Description:** Multi-currency support for international operations.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Add currencies with exchange rates — Stage 21 C1 (`PUT /credit/exchange-rates/{code}`; `test_company_currency_tax_c1.py`)
  - [x] Set base currency — Stage 21 C1 (`PATCH /tenants/me` `currency`; listed as `base_currency` on exchange-rates)
  - [x] Auto-update exchange rates (manual or API) — Stage 21 C1 (manual PUT + `POST …/refresh` provider + `fx_auto_refresh` settings)
  - [x] Transaction-level currency selection — Stage 21 C1 (`POST /sales/invoices` `currency`/`exchange_rate`)

#### BR-2.7 Language Configuration
- **Description:** UI language preferences.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Switch UI language per user — deferred ADR-006 (i18n packs); English MVP + scaffold only
  - [ ] MVP supports English; framework for i18n — deferred ADR-006 (English shipped; pack expansion out of Stage 21)

#### BR-2.8 Tax Configuration
- **Description:** Configure tax rules applicable to the business.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Add multiple tax rates (VAT, GST, etc.) — Stage 21 C1 (`POST /tax/rates` `tax_type` vat/gst; `test_company_currency_tax_c1.py`)
  - [x] Set default tax rate — Stage 21 C1 (`POST /tax/rates/{id}/default` + `is_default` on create)
  - [x] Tax applicability by product category — Stage 21 C1 (`POST /catalog/categories` `tax_rate_id`)
  - [x] Compound tax support — Stage 21 C1 (`components` net/compound legs + `/tax/calculate`)

---

### 4.3 User Management

#### BR-3.1 User Account CRUD
- **Description:** Full lifecycle management of user accounts.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create user with name, email, phone, role, branch/store assignment — Stage 21 U1 (`POST /users` name/email/phone/role/`branch_id`/`department_id`; dedicated user↔store membership deferred — `docs/ADR_005_USER_STORE_ASSIGNMENT.md`; `test_users_roles_u1.py`)
  - [x] Edit user details and assignments — Stage 21 U1 (`PATCH /users/{id}` name/phone/role/org/`record_scope`)
  - [x] Soft delete (deactivate) user — Stage 21 U1 (`DELETE /users/{id}` → `is_active=false`; row retained)
  - [ ] Hard delete with data archival option *(deferred post-MVP; see `docs/ADR_003_USER_DELETE_POLICY.md`)*
  - [x] Activate/deactivate toggle — Stage 21 U1 (`PATCH` `is_active` + soft DELETE)
  - [x] Bulk user import via CSV — Stage 21 U1 (`GET /users/import/template` + `POST /users/import`)

#### BR-3.2 Role Management
- **Description:** Predefined and custom role definitions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Predefined roles: Super Admin, Company Admin, Store Manager, Sales Officer, Inventory Officer, Accountant, Cashier — Stage 21 U1 (`GET /roles` system catalog; `test_users_roles_u1.py`)
  - [x] Each role has default permission set — Stage 21 U1 (`ROLE_PERMISSIONS` + catalog `permissions`/`record_scope`)
  - [x] Custom role creation capability — Stage 21 U1 (`POST /roles` + `PUT /roles/{slug}/permissions`)
  - [x] Role assignment to users — Stage 21 U1 (`POST/PATCH /users` `role` = system or custom slug)

#### BR-3.3 Permission System
- **Description:** Granular access control across three dimensions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Module Permissions:** Grant/deny access to entire modules (Inventory, Sales, etc.)
  - [x] **Menu Permissions:** Control visibility of specific menu items and submenus *(Stage 1: menu item visibility = module `read`/`write`; see `docs/ADR_004_MENU_PERMISSIONS.md`)*
  - [x] **Record Permissions:** Control CRUD operations on individual records (own records, department records, all records)
  - [x] Permission inheritance from role with user-level override capability — Stage 21 U1 (role→user permission snapshot + custom-role sync; user-level `record_scope` override via `PATCH /users`; per-user module grant/deny API not shipped)

---

### 4.4 Executive Dashboard

#### BR-4.1 KPI Cards
- **Description:** At-a-glance business metrics.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Display: Total Sales, Total Purchases, Total Expenses, Total Customers, Total Suppliers, Total Products — Stage 21 V1 (`GET /dashboard`; `test_dashboard_kpis_v1.py`)
  - [x] Real-time or near-real-time updates (within 5 minutes) — Stage 21 V1 (`CACHE_DASHBOARD_TTL_SECONDS` ≤ 300 + tenant cache invalidation)
  - [x] Period comparison (Today vs Yesterday, This Month vs Last Month) — Stage 21 V1 (`daily_revenue`/`yesterday_revenue`/`dod_change_pct` + `monthly_revenue`/`prior_month_revenue`/`mom_change_pct`)
  - [x] Click-through to detailed reports — Stage 21 V1 (`kpi_links` → sales/purchasing/expenses/inventory/reports)

#### BR-4.2 Inventory Alerts
- **Description:** Visual indicators for inventory issues.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Low stock products count with quick link — Stage 21 V1 (`low_stock` + `kpi_links.low_stock`)
  - [x] Out-of-stock products count — Stage 21 V1 (`out_of_stock`)
  - [x] Expiring products (pharmacy/food) count — Stage 21 V1 (`expiring_batches` next 30 days)

#### BR-4.3 Sales Visualization
- **Description:** Charts and trends for sales performance.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Recent sales list (last 10 transactions) — Stage 21 V1 (`recent_sales` POS+invoice merge ≤10)
  - [x] Top products by revenue and quantity — Stage 21 V1 (`top_products` ranked by revenue with `quantity`/`revenue`)
  - [x] Daily revenue line chart (last 30 days) — Stage 21 V1 (`daily_revenue_series` length 30)
  - [x] Monthly revenue bar chart (last 12 months) — Stage 21 V1 (`monthly_revenue_series` length 12)

#### BR-4.4 Notifications Panel
- **Description:** Centralized notification stream.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Display unread notification count — Stage 21 N1 (`GET /notifications/unread-count`; `test_dashboard_notifications_n1.py`)
  - [x] Categorized notifications (stock, orders, payments, system) — Stage 21 N1 (`group` field + `GET /notifications?group=`)
  - [x] Mark as read/unread — Stage 21 N1 (`PATCH /notifications/{id}/read|unread`)
  - [x] Notification history (last 90 days) — Stage 21 N1 (list cutoff `HISTORY_DAYS=90`; older excluded)

Fidelity sync: Stage 21 D1 — `docs/STAGE_21_FIDELITY.md` (`test_stage21_fidelity_d1.py`).

---

### 4.5 Inventory Management

#### BR-5.1 Product Catalog
- **Description:** Comprehensive product information management.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Categories:** Hierarchical category tree (parent/child), category code — Stage 17 C1 (`GET /catalog/categories?tree=true`)
  - [x] **Brands:** Brand name, logo, description — Stage 17 C1 (`POST /catalog/brands`, logo upload)
  - [x] **Units:** Unit of measure (piece, kg, liter, box, etc.) with conversion ratios — Stage 17 C1 / Stage 2 I6 (`/catalog/units/convert`)
  - [x] **Product Variants:** Size, color, flavor, dosage (pharmacy) variants with unique SKUs — Stage 17 C1
  - [x] **SKU:** Auto-generated or manual SKU assignment — Stage 17 C1 (manual SKU on create/variant)
  - [x] **Barcode:** Support for EAN, UPC, Code 128; barcode generation for products without barcodes — Stage 17 C1 (`/barcode/generate`)
  - [x] **Images:** Multiple product images with primary image designation — Stage 17 C1 (`/products/{id}/images`)
  - [x] **Product Details:** Name, cost price, selling price, tax rate, category, brand, unit, weight, dimensions — Stage 17 C1 (create with FKs + weight/dims; Stage 2 I6)
  - [x] **Batch/Expiry:** Batch number, manufacturing date, expiry date (critical for pharmacy and food) — Stage 17 C1 (`POST /inventory/stock-in` + `/products/{id}/batches`)

#### BR-5.2 Stock Operations
- **Description:** All inventory movement transactions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Stock In:** Record incoming stock with reference (purchase order, transfer, adjustment), quantity, batch, expiry, warehouse — Stage 17 S1 (`POST /inventory/stock-in` → warehouse qty + `stock_movements`; GRN sets `reference_type=grn`)
  - [x] **Stock Out:** Record outgoing stock with reference (sales, transfer, adjustment, damage), quantity, warehouse — Stage 15 C1/H1 sales invoice `stock_movements` (`reference_type=sales_invoice`); aggregated post preflight
  - [x] **Stock Adjustment:** Correct stock discrepancies with reason (damage, theft, expiry, found, lost) — Stage 17 S1 / Stage 2 I2 (`POST /inventory/adjust/{id}`; `INVALID_ADJUSTMENT_REASON`)
  - [x] **Stock Transfer:** Move stock between warehouses with transfer note, approval workflow — Stage 17 W1 (`POST /inventory/stock-transfers` → ship/receive; `transfer_out`/`transfer_in` movements)
  - [x] **Opening Stock:** Initialize stock levels for new products or fiscal year start — Stage 17 S1 (`POST /inventory/opening-stock`; `movement_type=opening_stock`)
  - [x] **Stock Count:** Physical count reconciliation with system stock; variance report generation — Stage 17 S2 (`POST /inventory/stock-counts` → patch items → complete posts `adjustment` movements; `GET .../variance-report`)

#### BR-5.3 Stock Movement History
- **Description:** Complete audit trail of all inventory changes.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Log every stock change with timestamp, user, transaction type, quantity before/after — Stage 17 D1 / Stage 2 I5 (`stock_movements` via `apply_stock_change`; `GET /inventory/movements`)
  - [x] Filter by date range, product, warehouse, transaction type — Stage 17 D1 (`GET /inventory/movements?product_id=&warehouse_id=&movement_type=&from_date=&to_date=`)
  - [x] Export to CSV/PDF — Stage 17 D1 (`report_type=inventory_movements` / `GET /reports/inventory/movements`)
  - [x] Immutable records (no deletion allowed) — Stage 17 D1 (append-only `stock_movements`; no delete API)

#### BR-5.4 Warehouse Stock
- **Description:** Warehouse-specific inventory visibility.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] View stock levels per warehouse — Stage 17 W1 (`GET /products/{id}/warehouse-stock`)
  - [x] Warehouse-specific reorder levels — Stage 17 L1 (`PUT /stores/{id}/reorder-policy` → `WarehouseStock` min/reorder/reorder_qty; low-stock `scope=warehouse`)
  - [x] Transfer stock between warehouses — Stage 17 W1 (ship/receive qty + movements)
  - [x] Warehouse-wise stock valuation (Stage 9 R2 — qty × `cost_price`)

#### BR-5.5 Low Stock Management
- **Description:** Proactive inventory replenishment alerts.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Set minimum stock level per product per warehouse — Stage 17 L1 (`PUT /stores/{id}/reorder-policy`; product-level via `PATCH /products/{id}`)
  - [x] Set reorder level (trigger point for purchase) — Stage 17 L1 (`PATCH /products/{id}` `reorder_level` / store reorder policy)
  - [x] Visual indicators on product list (green/yellow/red status) — Stage 17 L1 (`stock_status` on products + `GET /inventory/low-stock`)
  - [x] Automated low-stock notifications to Inventory Officer and Store Manager — Stage 16 N1 (`scan_low_stock` / `low_stock`)
  - [x] Generate purchase suggestions based on reorder levels — Stage 17 L1 (`suggested_order_qty` + `POST /inventory/low-stock/reorder-po` draft PO)

---

### 4.6 Purchasing

#### BR-6.1 Supplier Management
- **Description:** Vendor relationship and information management.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Supplier Profile:** Name, code, type, category, status
  - [x] **Contact Details:** Multiple contacts with name, phone, email, designation
  - [x] **Supplier Balance:** Real-time outstanding payable balance (Stage 11 C1: GRN discount/tax-aware)
  - [x] **Payment Terms:** Credit period, discount terms
  - [x] **Supplier History:** Purchase history, return history, payment history

#### BR-6.2 Purchase Request (PR)
- **Description:** Internal requisition for goods.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create PR with product, quantity, preferred supplier, required date, requesting department
  - [x] PR approval workflow (Inventory Officer → Store Manager → Company Admin)
  - [x] Status tracking: Draft, Pending, Approved, Rejected, Converted to PO
  - [x] Convert approved PR to Purchase Order with one click

#### BR-6.3 Purchase Order (PO)
- **Description:** Formal order placed with suppliers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create PO from PR or directly
  - [x] PO number auto-generation with configurable prefix
  - [x] Product lines with quantity, unit price, tax, discount, total
  - [x] Supplier selection and delivery address
  - [x] PO status: Draft, Sent, Partially Received, Fully Received, Cancelled
  - [x] Print/email PO to supplier
  - [x] PO amendment tracking

#### BR-6.4 Goods Received Note (GRN)
- **Description:** Record goods received against PO.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create GRN referencing PO
  - [x] Record received quantity (may differ from ordered)
  - [x] Record batch numbers and expiry dates
  - [x] Handle partial receipts (multiple GRNs per PO)
  - [x] Auto-update inventory on GRN post (create posts immediately; no separate draft approval)
  - [x] Handle rejected/damaged goods with reason

#### BR-6.5 Purchase Invoice
- **Description:** Supplier billing and payable recording.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create invoice from GRN or manually
  - [x] Invoice number, date, due date
  - [x] Line items with quantity, rate, tax, discount (Stage 11 C1 tax-on-net-after-discount)
  - [x] Attach supplier invoice document (PDF/image)
  - [x] Status: Draft, Approved, Paid, Partially Paid, Overdue
  - [x] Auto-update Accounts Payable (GRN posts AP; GRN-linked PI does not double-post; Stage 11 C2 RC self-assess)

#### BR-6.6 Purchase Return
- **Description:** Return goods to suppliers.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create return referencing original PO/GRN
  - [x] Record return reason (damaged, wrong item, expiry, quality issue)
  - [x] Deduct returned quantity from inventory
  - [x] Generate debit note
  - [x] Update supplier balance

---

### 4.7 Sales

#### BR-7.1 Customer Management
- **Description:** Customer relationship and information management.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Customer Profile:** Name, code, type (walk-in/registered), status
  - [x] **Contact Details:** Phone, email, address, GPS coordinates
  - [x] **Customer Groups:** Wholesale, Retail, VIP, etc. with group-based pricing
  - [x] **Customer Balance:** Real-time outstanding receivable balance
  - [x] **Credit Limit:** Per-customer credit limit with enforcement
  - [x] **Customer History:** Purchase history, return history, payment history

#### BR-7.2 Quotation
- **Description:** Pre-sales price quotes for customers.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Create quotation with product, quantity, price, validity period
  - [x] Quotation number auto-generation
  - [x] Print/email quotation to customer
  - [x] Convert quotation to sales order
  - [x] Expiry notification before validity ends

#### BR-7.3 Sales Order
- **Description:** Customer order confirmation before invoicing.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create order from quotation or directly
  - [x] Reserve inventory (soft allocation)
  - [x] Order status: Draft, Confirmed, Processing, Shipped, Delivered, Cancelled
  - [x] Delivery date and address
  - [x] Convert to invoice with one click

#### BR-7.4 Sales Invoice
- **Description:** Official billing document.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Create invoice from sales order or directly
  - [x] Invoice number auto-generation with configurable prefix and series
  - [x] Product lines with quantity, unit price, tax, discount, total (Stage 12 C1 tax-on-net-after-discount)
  - [x] Customer selection with auto-filled details
  - [x] Multiple print templates (A4, thermal receipt)
  - [x] Status: Draft, Approved, Sent, Paid, Partially Paid, Overdue, Cancelled
  - [x] Auto-update Accounts Receivable
  - [x] Support credit sales with credit limit check
  - [x] Post atomicity: insufficient stock → `409 INSUFFICIENT_STOCK`; no partial AR/JE (Stage 15 H1)
  - [x] Auto-post journal includes standard-cost COGS `5000` / Inventory `1200` when `cost_price` > 0 (Stage 15 I1)
  - [x] Domain audit `invoice_posted` with stock/tax/AR details (Stage 15 A1)

#### BR-7.5 Sales Return
- **Description:** Customer returns and refunds.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create return referencing original invoice
  - [x] Record return reason and condition
  - [x] Restock or discard returned items — Stage 15 R1 restock to invoice store warehouse
  - [x] Generate credit note
  - [x] Refund or adjust customer balance — FX-safe `to_base` via invoice exchange rate (Stage 15 R1)
  - [x] Return journal: tax reverse, COGS reverse, `store_id`; audit `sales_return_posted` (Stage 15 R1/A1)

---

### 4.8 Point of Sale (POS)

#### BR-8.1 POS Transaction
- **Description:** Fast, intuitive retail checkout experience.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Barcode Scanner:** Support USB and Bluetooth barcode scanners (wedge + camera; vendor USB/serial drivers post-MVP)
  - [x] **Product Search:** Search by name, SKU, barcode with autocomplete
  - [x] **Cart Management:** Add, remove, update quantity, apply discounts
  - [x] **Discounts:** Fixed amount per-item or cart-level (percentage UI polish deferred)
  - [x] **Customer Selection:** Quick customer lookup or walk-in default
  - [x] **Multiple Payment Methods:** Cash, Card, Digital Wallet, Credit (for registered customers); split tender (Stage 13 H2 multi-tender E2E)
  - [x] **Receipt Printing:** Thermal printer support; digital receipt via email/SMS (`pos_receipt_sent` audit — Stage 13 H2)
  - [x] **Cash Drawer:** Auto-open on cash payment or any cash tender in a split; manual open with reason (Stage 13 H2)
  - [x] **Atomic stock guard:** Insufficient stock → `409 INSUFFICIENT_STOCK`; no orphan sale/payment/journal (Stage 13 H1)

#### BR-8.2 Shift Management
- **Description:** Cashier accountability and reconciliation.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Shift Opening:** Record opening cash float, timestamp, cashier (Stage 12 A1 audit)
  - [x] **Shift Closing:** Record closing cash, card total, other payments
  - [x] **Cash Reconciliation:** System sales vs actual cash; variance reporting
  - [x] **Shift Report:** Sales summary, payment breakdown (`GET .../report`; Stage 12 C2)
  - [x] Prevent new transactions until shift is opened
  - [x] Failed sale (e.g. insufficient stock) leaves session totals unchanged (Stage 13 H1)

---

### 4.9 Expense Management

#### BR-9.1 Expense Categories
- **Description:** Classify business expenditures.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Predefined categories (Rent, Utilities, Salaries, Transportation, Marketing, etc.) — Stage 22 E1 (`ensure_default_categories` RENT/UTIL/SAL/TRANS/MKT/SUP/MISC; `test_expense_categories_entry_e1.py`)
  - [x] Custom category creation — Stage 22 E1 (`POST /expenses/categories`)
  - [x] Category-based budget allocation — Stage 22 E1 (`PATCH` `budget_amount` + `GET /expenses/budgets`)

#### BR-9.2 Expense Entry
- **Description:** Record business expenses.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Expense date, category, amount, payment method, reference number — Stage 22 E1 (`POST /expenses` `expense_date`/`category_id`/`amount`/`payment_method`/`reference`; `test_expense_categories_entry_e1.py`)
  - [x] Payee name — Stage 22 E1 (`payee`)
  - [x] Description/notes — Stage 22 E1 (`description` field; no separate notes column)
  - [x] Assign to store/department (Stage 14 E2 — `store_id` + `department_id` on expenses and recurring templates; list filters)
  - [x] Link to chart of accounts for auto-posting (Stage 14 E1 — `expense_categories.account_id`; fallback Operating Expenses `6000`)

#### BR-9.3 Expense Approval
- **Description:** Control spending through approval workflows.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Configurable approval thresholds (e.g., >$100 requires manager approval) — Stage 22 A1 (`PATCH /expenses/settings` levels / thresholds; `test_expense_approval_recurring_a1.py`)
  - [x] Multi-level approval chain — Stage 22 A1 (`approval_steps_required` + L1/L2 `POST /expenses/{id}/approve`)
  - [x] Approval/rejection with comments — Stage 22 A1 (`comment` on approve; `reason`/`comment` on reject; `approval_actions`)
  - [x] Email notification to approvers — Stage 22 A1 (in-app `expense_approval` on submit) + `test_expense_approval_notify.py` (email channel)

#### BR-9.4 Expense Attachments
- **Description:** Digital receipt storage.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Upload receipt images/PDFs
  - [x] OCR extraction of amount, date, vendor (AI-assisted; Stage 10 A1 human-confirmed `ocr-apply`)
  - [x] Attachment preview and download

#### BR-9.5 Recurring Expenses
- **Description:** Automate regular payments.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Set frequency (daily, weekly, monthly, yearly) — Stage 22 A1 (`POST /expenses/recurring` `frequency`; `test_expense_approval_recurring_a1.py`)
  - [x] Auto-generate expense entries — Stage 22 A1 (`POST /expenses/recurring/generate`)
  - [x] Notification before auto-generation — Stage 22 A1 (`POST /notifications/scan-due` → `recurring_expense`)
  - [x] Skip or modify individual occurrences — Stage 22 A1 (`skip_next` / `next_amount` / `next_description` on `PATCH /expenses/recurring/{id}`)

---

### 4.10 Basic Accounting

#### BR-10.1 Chart of Accounts (COA)
- **Description:** Financial account structure.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Predefined COA based on industry template — Stage 22 C1 (`GET /accounting/accounts` seeds `DEFAULT_ACCOUNTS`; industry-agnostic system COA for MVP — same seed for all industries; `test_coa_fidelity_c1.py`)
  - [x] Account types: Asset, Liability, Equity, Income, Expense — Stage 22 C1 (`ACCOUNT_TYPES` on seeded + custom accounts)
  - [x] Account code hierarchy (e.g., 1000-Assets, 1100-Current Assets) — Stage 22 C1 (code bands + `parent_id` / `?tree=true`)
  - [x] Add/edit accounts (non-system accounts) — Stage 22 C1 (`POST`/`PATCH /accounting/accounts`; system accounts `409 SYSTEM_ACCOUNT`)
  - [x] Opening balance entry — Stage 22 C1 (`POST /accounting/accounts/{id}/opening-balance`)

#### BR-10.2 Journal Entries
- **Description:** Manual accounting transactions.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Double-entry journal with debit and credit lines
  - [x] Auto-balancing validation
  - [x] Journal number auto-generation
  - [x] Attach supporting documents (Stage 9 J1)
  - [x] Post/unpost capability (unpost only within same fiscal period; Stage 3 A1)

#### BR-10.3 Cash & Bank Accounts
- **Description:** Track liquid assets.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create cash accounts (petty cash, main cash) — Stage 22 B1 (`POST /accounting/liquid-accounts` kind=cash; system `1000`; `test_cash_bank_recon_b1.py`)
  - [x] Create bank accounts with bank name, account number, branch — Stage 22 B1 (`kind=bank` + `bank_name`/`account_number`/`bank_branch`)
  - [x] Record deposits, withdrawals, transfers between accounts — Stage 22 B1 (`POST /accounting/liquid-transfers` deposit/withdrawal/transfer)
  - [x] Bank reconciliation (system balance vs statement) — Stage 22 B1 (`POST /accounting/bank-statements` → match → complete; Open Banking adapters deferred)
  - [x] Cheque management (issue, deposit, bounce tracking) — Stage 22 B1 (issued clear + received deposit/bounce via `/accounting/cheques/{id}/*`)

#### BR-10.4 Accounts Receivable (AR)
- **Description:** Track money owed by customers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-generation from sales invoices — Stage 22 P1 (`POST /sales/invoices/{id}/post` → AR journal `sales_invoice`; `test_ar_ap_export_p1.py`)
  - [x] Customer aging report (0-30, 31-60, 61-90, 90+ days) — Stage 22 P1 (`GET /credit/aging?kind=receivable` buckets `current`/`1_30`/`31_60`/`61_90`/`90_plus`)
  - [x] Payment recording against invoices — Stage 22 P1 (`POST /sales/payments` + `sales_invoice_id`)
  - [x] Partial payment support — Stage 22 P1 (partial `paid_amount` / status)
  - [x] Overdue notification automation — Stage 22 P1 (`POST /notifications/scan-due` → `payment_due` on sales invoices)

#### BR-10.5 Accounts Payable (AP)
- **Description:** Track money owed to suppliers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-generation from purchase invoices — Stage 22 P1 (GRN AP journal + PI from GRN; `test_ar_ap_export_p1.py`)
  - [x] Supplier aging report — Stage 22 P1 (`GET /credit/aging?kind=payable`)
  - [x] Payment recording against bills — Stage 22 P1 (`POST /suppliers/{id}/payments` + `purchase_invoice_id`)
  - [x] Partial payment support — Stage 22 P1 (partial bill `paid_amount`)
  - [x] Due date notifications — Stage 22 P1 (`scan_payment_due` includes purchase invoices → `payment_due` / `purchase_invoice`; + payment-schedule)

#### BR-10.6 Financial Reports
- **Description:** Standard financial statements.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Profit & Loss:** Revenue, COGS, gross profit, operating expenses, net profit; filterable by date range and store (Stage 14 A1 — `store_id` on journals / P&L; Stage 15 I1 sale COGS posts to `5000`)
  - [x] **Cash Flow:** Operating, investing, financing activities (Stage 3 A3 + Stage 14 A1 store filter)
  - [x] **Trial Balance:** All accounts with debit/credit balances; validation that total debits = total credits; point-in-time `as_of_date` (Stage 14 A2; balance sheet same)
  - [x] Export to PDF and Excel — Stage 22 P1 (`GET /reports/export` `profit_loss`/`trial_balance` as `pdf` + `xlsx`; `test_ar_ap_export_p1.py`)

---

### 4.11 Credit Management

#### BR-11.1 Customer Credit
- **Description:** Manage customer credit sales and collections.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Set per-customer credit limit — Stage 22 R1 (`PATCH /customers/{id}/credit-limit`; `test_customer_credit_r1.py`)
  - [x] Block sales that exceed credit limit (with override permission) — Stage 22 R1 (`CREDIT_LIMIT_EXCEEDED` on invoice post; override via `credit_limit_override` + reason + `credit:approve`)
  - [x] Display outstanding balance on customer profile — Stage 22 R1 (`GET /customers/{id}` `balance`; `/customers/{id}/outstanding`)
  - [x] Record payment collections with date, amount, method, reference — Stage 22 R1 (`POST /customers/{id}/payments` amount/method/reference)
  - [x] Allocate payments to specific invoices or auto-allocate (oldest first) — Stage 14 R1 Credit UI + API `sales_invoice_id` / supplier `purchase_invoice_id`
  - [x] Customer statement generation (all transactions + balance) — Stage 22 R1 (`GET /credit/customers/{id}/statement` invoices + payments + balance)

#### BR-11.2 Supplier Credit
- **Description:** Manage supplier payable tracking.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Track outstanding bills per supplier
  - [x] Payment schedule view (upcoming due dates) — Stage 8 S1: `GET /suppliers/{id}/payment-schedule` + Credit UI
  - [x] Early payment discount calculation
  - [x] Supplier statement generation

---

### 4.12 Tax Management

#### BR-12.1 Tax Configuration
- **Description:** Define and apply tax rules.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Add tax types (VAT, GST, Sales Tax, etc.) — Stage 22 T1 (`POST /tax/rates` `tax_type`; `test_tax_config_fidelity_t1.py`)
  - [x] Configure tax rates (percentage) — create + Stage 14 T1 `PATCH /tax/rates/{id}` edit/deactivate (`is_active`; clears default)
  - [x] Set tax applicability (inclusive/exclusive pricing) — Stage 22 T1 (`pricing_mode` on rates + `POST /tax/calculate`)
  - [x] Product-category-specific tax rules (Stage 10 T1 — category `tax_rate_id`, parent walk)
  - [x] Compound tax (tax on tax) support — Stage 22 T1 (`components` with `basis: compound` on rates / calculate)

#### BR-12.2 Automatic Tax Calculation
- **Description:** Real-time tax computation on transactions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Auto-calculate tax on sales invoices, purchase invoices, POS transactions
  - [x] Display tax breakdown per line item and total
  - [x] Handle tax exemptions (zero-rated, exempt products) — Stage 15 T1 live filing supply splits
  - [x] Reverse charge mechanism support — Stage 15 T1 sales RC memo → filing box 2a from live post

#### BR-12.3 Tax Reports
- **Description:** Compliance and filing support.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Output tax summary (tax collected on sales) — Stage 15 T1 live invoice → `/reports/tax`
  - [x] Input tax summary (tax paid on purchases)
  - [x] Net tax payable/refundable
  - [x] Tax report by period (monthly, quarterly, annually) — Stage 14 T1 `period` + `year`/`month`/`quarter` on `/reports/tax` and filing
  - [x] Export in government filing format (manual GH GRA / NG FIRS / KE KRA workbooks; portal e-file deferred — Stage 10 T2)

Fidelity sync: Stage 22 D1 — `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

---

### 4.13 Multi-Store Management

#### BR-13.1 Store Operations
- **Description:** Manage multiple retail/service locations.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create stores with unique code, name, location — Stage 1 C8 / `POST /stores`
  - [ ] Assign store manager and staff — Partial: `stores.manager_id` assigned; dedicated user↔store staff membership deferred (ADR-005)
  - [x] Store-specific inventory view — Stage 16 M1 (`GET /stores/{id}/inventory`)
  - [x] Store-specific sales reporting — Stage 4 M1 (`GET /stores/{id}/sales`)
  - [x] Consolidated reporting across all stores — Stage 4/16 (`GET /reports/sales/by-store`; Stage 16 M2 `GET /reports/transfers`)

#### BR-13.2 Inter-Store Transfers
- **Description:** Move stock between stores.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create transfer request with source store, destination store, products, quantities — Stage 4 T1 / Stage 16 M1 (`POST /stores/transfers`)
  - [x] Approval workflow (source store manager → destination store manager) — Stage 4 T1 (`TRANSFER_SHIP_FORBIDDEN` / `TRANSFER_RECEIVE_FORBIDDEN`)
  - [x] Track transfer status: Draft, Requested, In Transit, Received, Cancelled — Stage 2/4 / Stage 16 M1
  - [x] Auto-update inventory at both stores on receipt confirmation — Stage 16 M1 (warehouse qty + `stock_movements` `transfer_out`/`transfer_in`)
  - [x] Transfer history and reporting — Stage 16 M2 (`GET /reports/transfers`, list filters on `/stores/transfers` + `/inventory/stock-transfers`, export `transfer_history`, Reports → Transfers)

---

### 4.14 Reports & Analytics

#### BR-14.1 Sales Reports
- **Description:** Comprehensive sales analysis.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Daily Sales:** Date, invoice count, total revenue, tax, discounts, net sales — Stage 16 R1 (`GET /reports/sales/daily`)
  - [x] **Monthly Sales:** Monthly aggregation with trend comparison — Stage 16 R1 / Stage 4 R1
  - [x] **Product Sales:** Product-wise quantity and revenue; filter by date, store, category — Stage 4 R1
  - [x] **Customer Sales:** Top customers by revenue and frequency — Stage 4 R1
  - [x] **Salesperson Performance:** Sales by user/role — Stage 16 R1 (`GET /reports/sales/salesperson`)

#### BR-14.2 Inventory Reports
- **Description:** Stock visibility and analysis.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Stock Balance:** Current stock per product per warehouse (`GET /reports/inventory/balance`)
  - [x] **Low Stock:** Products below reorder level (`GET /reports/inventory/low-stock`)
  - [x] **Stock Movement:** All in/out/adjustment/transfer transactions (`GET /reports/inventory/movements`)
  - [x] **Stock Valuation:** quantity × product `cost_price` (standard cost; Stage 9 R2). FIFO/LIFO/WA deferred.
  - [x] **Expiry Report:** Products nearing expiry (`GET /reports/inventory/expiry`)

#### BR-14.3 Purchase Reports
- **Description:** Procurement analysis.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] **Purchase Summary:** Total purchases by period
  - [x] **Supplier Purchases:** Purchase volume and value per supplier
  - [x] **Pending Orders:** POs not yet received (Stage 9 R1 — `sent` / `partially_received`)
  - [x] **Purchase Return Summary** (Stage 9 R1)

#### BR-14.4 Expense Reports
- **Description:** Expenditure analysis.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Expense summary by category and period — Stage 16 R1 (`GET /reports/expenses/summary`)
  - [x] Budget vs actual comparison — Stage 16 R1 (`budgets` embedded in expenses summary)
  - [x] Top expense categories — Stage 16 R1 (`by_category` sorted)

#### BR-14.5 Financial Reports
- **Description:** Business financial health.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Profit & Loss Statement** — Stage 16 R1 (`GET /reports/profit-loss`; store filter Stage 14 A1)
  - [x] **Cash Flow Statement** — Stage 16 R1 (`GET /reports/cash-flow`)
  - [x] **Balance Sheet (Assets = Liabilities + Equity)** — Stage 16 R1 (`GET /reports/balance-sheet`; `as_of_date` Stage 14 A2)
  - [x] All reports filterable by date range, branch, store — Stage 23 F1 (`store_id`/`branch_id` on `GET /reports/balance-sheet`, P&L, cash-flow + Reports UI; `test_financial_report_filters_f1.py`); date on sales/P&L/cash-flow already Stage 14/16
  - [x] Comparative reports (current period vs previous period) — Stage 4/16 R1 sales daily/monthly `change_pct` / prior period; Stage 23 C1 financial `compare=true` on P&L / cash-flow / balance sheet (`test_financial_comparative_c1.py`)

Fidelity sync: Stage 16 R1 suite — prior BR-14.1/14.4/14.5. Stage 23 D1/H23x — `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`), exit `docs/STAGE_23_EXIT_CRITERIA.md`, freeze ADR-052 for BR-14.5 filters/comparative + commercial MVP gate docs.

---

### 4.15 Notifications

#### BR-15.1 Notification Types
- **Description:** Automated alerts for business events.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Low Stock:** When product reaches reorder level — Stage 16 N1 (`scan_low_stock` / `low_stock`)
  - [x] **New Orders:** When sales order is created — Stage 16 N1 / Stage 4 N1 (`new_order`)
  - [x] **Purchase Received:** When GRN is approved — Stage 16 N1 (`purchase_received` on GRN post)
  - [x] **Payment Due:** When invoice/bill approaches due date — Stage 1 `scan_payment_due` + Celery `/notifications/scan-due`
  - [x] **Credit Limit Reached:** When customer exceeds credit threshold — Stage 16 N1 (`credit_limit` on invoice post ≥80% utilization)
  - [x] **Shift Variance:** When cash reconciliation shows discrepancy — Stage 16 N1 (`shift_variance`; prefs suppress)
  - [x] **Expense Approval Required:** When expense exceeds threshold — `expense_approval` (`test_expense_approval_notify.py`)

#### BR-15.2 Notification Channels
- **Description:** Multi-channel alert delivery.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Dashboard:** In-app notification bell with badge count — Stage 1 / Stage 16 N1
  - [x] **Email:** SMTP integration; HTML email templates — Stage 16 N2 (`create_notification` → `send_notification_email`; console when SMTP unset)
  - [x] **SMS:** SMS gateway integration (Twilio, regional providers) — Stage 16 N2 (`send_notification_sms`; console when Twilio unset)
  - [x] User preference for channel per notification type — Stage 16 N2 (`GET/PATCH /notifications/settings`; outline categories opt-in)

---

### 4.16 Backup & Recovery

#### BR-16.1 Manual Backup
- **Description:** On-demand data protection.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] One-click backup initiation by Super Admin — Stage 18 D1 / Stage 5 B1
  - [x] Backup includes database, uploaded files, configurations (Stage 10 B1: `.ribbak` `media` map for tenant-scoped uploads)
  - [x] Download backup archive
  - [x] Backup encryption

#### BR-16.2 Scheduled Backup
- **Description:** Automated data protection.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Configurable schedule (daily, weekly) — Stage 18 B1 (`PATCH /backup/settings` + `POST /backup/run-due` + Celery `run-due-backups`)
  - [x] Retention policy (keep last N backups) — Stage 18 B1 (`prune_retention` after successful create)
  - [x] Backup storage to S3-compatible storage — Stage 26 W1 offsite mirror strategy (`ops/backup/sync-ribbak-offsite.sh.example`, `docs/DR_WAL_PITR_RUNBOOK.md`) + Stage 27 B1 opt-in in-app upload after `create_backup` (`BACKUP_OFFSITE_UPLOAD_ENABLED`, `BACKUP_OFFSITE_S3_BUCKET` / `BACKUP_OFFSITE_S3_PREFIX`; `test_backup_offsite_b1.py`); local `BACKUP_DIR` remains primary write path; upload failure → `Backup failed` (no fake success); operator sync script retained
  - [x] Failure alerts to admin — Stage 18 B1 (`Backup failed` system notification; no fake success on schedule failure)

#### BR-16.3 Database Restore
- **Description:** Disaster recovery capability.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Restore from backup archive (guarded `confirm_text=RESTORE`; media rehydrate Stage 10 B1) — Stage 18 D1 / Stage 5 B1
  - [ ] Restore to new tenant (for testing) — blocked by design for MVP (cross-tenant restore denied; Stage 23 B1 foreign backup → 404)
  - [x] Restore validation (checksum verification + integrity proof)
  - [x] Point-in-time recovery (if WAL archiving enabled) — Stage 26 W1 strategy Complete (MVP): `docs/DR_WAL_PITR_RUNBOOK.md`, `ops/postgres/` (`test_wal_pitr_w1.py`); Stage 28 R1 operator drill pack Complete (MVP): `docs/PITR_DRILL_PACK_MVP.md` (`test_pitr_drill_pack_r1.py`); operator staging PITR drill **execution** Remaining
  - [x] Logical DR drill automation evidence (Stage 23 B1: `test_logical_dr_drill_b1.py` / `stage23_b1_logical_drill.json`)

Fidelity sync: Stage 18 D1 — `docs/STAGE_18_FIDELITY.md`. Stage 23 B1 DR drill gate — `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`. Stage 23 D1 — `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`). Stage 26 W1 WAL/PITR + S3 offsite — `docs/DR_WAL_PITR_RUNBOOK.md` (`test_wal_pitr_w1.py`). Stage 26 D1 ops platform fidelity — `docs/STAGE_26_FIDELITY.md` (`test_stage26_fidelity_d1.py`; M1–C1). Stage 27 B1 auto `.ribbak` offsite — `test_backup_offsite_b1.py`. Stage 27 D1 release fidelity — `docs/STAGE_27_FIDELITY.md` (`test_stage27_fidelity_d1.py`; B1–L1). Stage 28 R1 PITR drill pack — `docs/PITR_DRILL_PACK_MVP.md` (`test_pitr_drill_pack_r1.py`). Stage 28 D1 staging certification fidelity — `docs/STAGE_28_FIDELITY.md` (`test_stage28_fidelity_d1.py`; R1–C1). Stage 29 V1–X1 operator hardening packs — `docs/PENTEST_PACK_MVP.md` / `docs/PGBOUNCER_SOAK_PACK_MVP.md` / `docs/TLS_INGRESS_PACK_MVP.md` / `docs/CUTOVER_PACK_MVP.md`. Stage 29 D1 operator hardening & cutover fidelity — `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`; V1–X1). Stage 29 H29x exit + freeze — `docs/STAGE_29_EXIT_CRITERIA.md`, ADR-064 (`test_stage29_exit_h29x.py`). Stage 30 L1–A1 go-live support packs — `docs/EVIDENCE_LEDGER_MVP.md` / `docs/INCIDENT_PACK_MVP.md` / `docs/SUPPORT_RUNBOOK_MVP.md` / `docs/ATTESTATION_PACK_MVP.md`. Stage 30 D1 go-live support fidelity — `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`; L1–A1). Stage 30 H30x exit + freeze — `docs/STAGE_30_EXIT_CRITERIA.md`, ADR-066 (`test_stage30_exit_h30x.py`). Stage 31 G1–C1 + D1 commercial MVP closeout fidelity — `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`; G1–C1); no go-live signed claim. Stage 31 H31x exit + freeze — `docs/STAGE_31_EXIT_CRITERIA.md`, ADR-068 (`test_stage31_exit_h31x.py`). Stage 32 A1–B1 + D1 commercial MVP handoff fidelity — `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`; A1–B1); no go-live signed claim. Stage 32 H32x exit + freeze — `docs/STAGE_32_EXIT_CRITERIA.md`, ADR-070 (`test_stage32_exit_h32x.py`). Stage 33 K1–T1 + D1 commercial MVP continuity fidelity — `docs/STAGE_33_FIDELITY.md` (`test_stage33_fidelity_d1.py`; K1–T1); no go-live signed claim. Stage 33 H33x exit + freeze — `docs/STAGE_33_EXIT_CRITERIA.md`, ADR-072 (`test_stage33_exit_h33x.py`). Stage 34 A1–C1 + D1 commercial customer assurance fidelity — `docs/STAGE_34_FIDELITY.md` (`test_stage34_fidelity_d1.py`; A1–C1; S1/B1 deferred); no go-live signed claim. Stage 35 T1–R1 + D1 commercial E2E operational smoke fidelity — `docs/STAGE_35_FIDELITY.md` (`test_stage35_fidelity_d1.py`; T1–R1); no live E2E smoke / go-live signed claim. Stage 35 H35x exit + freeze — `docs/STAGE_35_EXIT_CRITERIA.md`, ADR-076 (`test_stage35_exit_h35x.py`). Stage 36 S1–B1 + D1 commercial assurance completion fidelity — `docs/STAGE_36_FIDELITY.md` (`test_stage36_fidelity_d1.py`; S1–B1); no live SLA / paid billing / go-live signed claim. Stage 36 H36x exit + freeze — `docs/STAGE_36_EXIT_CRITERIA.md`, ADR-078 (`test_stage36_exit_h36x.py`). Stage 37 open — `docs/STAGE_37_PLAN.md`, ADR-079 (`test_stage37_open.py`). Stage 37 P1 data portability — `docs/DATA_PORTABILITY_MVP.md` (`test_data_portability_p1.py`). Stage 37 E1 erasure honesty — `docs/ERASURE_HONESTY_MVP.md` (`test_erasure_honesty_e1.py`). Stage 37 D1 commercial data protection fidelity — `docs/STAGE_37_FIDELITY.md` (`test_stage37_fidelity_d1.py`; P1–E1). Stage 37 H37x exit + freeze — `docs/STAGE_37_EXIT_CRITERIA.md`, ADR-080 (`test_stage37_exit_h37x.py`). Stage 38 open — `docs/STAGE_38_PLAN.md`, ADR-081 (`test_stage38_open.py`). Stage 38 V1 vulnerability disclosure — `docs/VULN_DISCLOSURE_MVP.md` (`test_vuln_disclosure_v1.py`). Stage 38 B1 breach notification — `docs/BREACH_NOTIFICATION_MVP.md` (`test_breach_notification_b1.py`). Stage 38 D1 commercial security disclosure fidelity — `docs/STAGE_38_FIDELITY.md` (`test_stage38_fidelity_d1.py`; V1–B1). Stage 38 H38x exit + freeze — `docs/STAGE_38_EXIT_CRITERIA.md`, ADR-082 (`test_stage38_exit_h38x.py`). Stage 39 open — `docs/STAGE_39_PLAN.md`, ADR-083 (`test_stage39_open.py`). Stage 39 P1 DPA / subprocessor — `docs/DPA_SUBPROCESSOR_MVP.md` (`test_dpa_subprocessor_p1.py`). Stage 39 A1 MSA security addendum — `docs/MSA_ADDENDUM_MVP.md` (`test_msa_addendum_a1.py`). Stage 39 D1 commercial contract evidence fidelity — `docs/STAGE_39_FIDELITY.md Stage 40 D1 availability & supply-chain fidelity — `docs/STAGE_40_FIDELITY.md Stage 41 D1 accessibility & change governance fidelity — `docs/STAGE_41_FIDELITY.md Stage 42 D1 AI transparency fidelity — `docs/STAGE_42_FIDELITY.md Stage 42 exit met — `docs/STAGE_42_EXIT_CRITERIA.md`, ADR-090 (`test_stage42_exit_h42x.py`) Stage 43 open: `docs/STAGE_43_PLAN.md`, ADR-091 (`test_stage43_open.py`). Stage 43 T1 ToS / AUP honesty Complete (MVP) — `docs/TOS_AUP_MVP.md`, `ops/mvp/tos-aup.json` (`test_tos_aup_t1.py`). Stage 43 C1 Cookie / privacy notice honesty Complete (MVP) — `docs/COOKIE_PRIVACY_NOTICE_MVP.md`, `ops/mvp/cookie-privacy-notice.json` (`test_cookie_privacy_notice_c1.py`). Stage 43 D1 commercial legal notice fidelity Complete (MVP) — `docs/STAGE_43_FIDELITY.md` (`test_stage43_fidelity_d1.py`). Stage 43 exit met — `docs/STAGE_43_EXIT_CRITERIA.md`, ADR-092 (`test_stage43_exit_h43x.py`). Stage 44 open: `docs/STAGE_44_PLAN.md`, ADR-093 (`test_stage44_open.py`). Stage 44 R1 data residency / localization honesty Complete (MVP) — `docs/DATA_RESIDENCY_MVP.md`, `ops/mvp/data-residency.json` (`test_data_residency_r1.py`). Stage 44 E1 encryption / key-management honesty Complete (MVP) — `docs/ENCRYPTION_KMS_MVP.md`, `ops/mvp/encryption-kms.json` (`test_encryption_kms_e1.py`). Stage 44 D1 commercial data trust fidelity Complete (MVP) — `docs/STAGE_44_FIDELITY.md` (`test_stage44_fidelity_d1.py`). Stage 44 exit met — `docs/STAGE_44_EXIT_CRITERIA.md`, ADR-094 (`test_stage44_exit_h44x.py`). Stage 45 open: `docs/STAGE_45_PLAN.md`, ADR-095 (`test_stage45_open.py`). Stage 45 O1 RTO / RPO recovery objectives honesty Complete (MVP) — `docs/RTO_RPO_MVP.md`, `ops/mvp/rto-rpo.json` (`test_rto_rpo_o1.py`). Stage 45 T1 data retention / return honesty Complete (MVP) — `docs/DATA_RETENTION_RETURN_MVP.md`, `ops/mvp/data-retention-return.json` (`test_data_retention_return_t1.py`). Stage 45 D1 commercial continuity & exit fidelity Complete (MVP) — `docs/STAGE_45_FIDELITY.md` (`test_stage45_fidelity_d1.py`). Stage 45 exit met — `docs/STAGE_45_EXIT_CRITERIA.md`, ADR-096 (`test_stage45_exit_h45x.py`). Stage 46 open: `docs/STAGE_46_PLAN.md`, ADR-097 (`test_stage46_open.py`). Stage 46 L1 limitation of liability / indemnity honesty Complete (MVP) — `docs/LIABILITY_INDEMNITY_MVP.md`, `ops/mvp/liability-indemnity.json` (`test_liability_indemnity_l1.py`). Stage 46 W1 service credit / warranty honesty Complete (MVP) — `docs/SERVICE_CREDIT_WARRANTY_MVP.md`, `ops/mvp/service-credit-warranty.json` (`test_service_credit_warranty_w1.py`). Stage 46 D1 commercial liability & remedy fidelity Complete (MVP) — `docs/STAGE_46_FIDELITY.md` (`test_stage46_fidelity_d1.py`). Stage 46 exit met — `docs/STAGE_46_EXIT_CRITERIA.md`, ADR-098 (`test_stage46_exit_h46x.py`). Stage 47 open: `docs/STAGE_47_PLAN.md`, ADR-099 (`test_stage47_open.py`). Stage 47 I1 cyber insurance / COI honesty Complete (MVP) — `docs/CYBER_INSURANCE_MVP.md`, `ops/mvp/cyber-insurance.json` (`test_cyber_insurance_i1.py`). Stage 47 A1 customer audit rights honesty Complete (MVP) — `docs/CUSTOMER_AUDIT_RIGHTS_MVP.md`, `ops/mvp/customer-audit-rights.json` (`test_customer_audit_rights_a1.py`). Stage 47 D1 commercial insurance & audit fidelity Complete (MVP) — `docs/STAGE_47_FIDELITY.md` (`test_stage47_fidelity_d1.py`). Stage 47 exit met — `docs/STAGE_47_EXIT_CRITERIA.md`, ADR-100 (`test_stage47_exit_h47x.py`). Stage 48 open: `docs/STAGE_48_PLAN.md`, ADR-101 (`test_stage48_open.py`). Stage 48 P1 professional services / SOW honesty Complete (MVP) — `docs/PROFESSIONAL_SERVICES_SOW_MVP.md`, `ops/mvp/professional-services-sow.json` (`test_professional_services_sow_p1.py`). Stage 48 T1 customer training / certification honesty Complete (MVP) — `docs/CUSTOMER_TRAINING_CERT_MVP.md`, `ops/mvp/customer-training-cert.json` (`test_customer_training_cert_t1.py`). Stage 48 D1 commercial services fidelity Complete (MVP) — `docs/STAGE_48_FIDELITY.md` (`test_stage48_fidelity_d1.py`). Stage 48 exit met — `docs/STAGE_48_EXIT_CRITERIA.md`, ADR-102 (`test_stage48_exit_h48x.py`). Stage 49 open: `docs/STAGE_49_PLAN.md`, ADR-103 (`test_stage49_open.py`). Stage 49 R1 partner / reseller terms honesty Complete (MVP) — `docs/PARTNER_RESELLER_MVP.md`, `ops/mvp/partner-reseller.json` (`test_partner_reseller_r1.py`). Stage 49 L1 pricing transparency honesty Complete (MVP) — `docs/PRICING_TRANSPARENCY_MVP.md`, `ops/mvp/pricing-transparency.json`; evidence `/opt/cursor/artifacts/launch/stage49_l1_pricing_transparency.json` (`test_pricing_transparency_l1.py`). Stage 49 D1 commercial channel & pricing fidelity Complete (MVP) — `docs/STAGE_49_FIDELITY.md` (`test_stage49_fidelity_d1.py`). Stage 49 exit met — `docs/STAGE_49_EXIT_CRITERIA.md`, ADR-104 (`test_stage49_exit_h49x.py`). Stage 50 open: `docs/STAGE_50_PLAN.md`, ADR-105 (`test_stage50_open.py`). Stage 50 R1 referral program honesty Complete (MVP) — `docs/REFERRAL_PROGRAM_MVP.md`, `ops/mvp/referral-program.json` (`test_referral_program_r1.py`). Stage 50 F1 freemium trial honesty Complete (MVP) — `docs/FREEMIUM_TRIAL_MVP.md`, `ops/mvp/freemium-trial.json`; evidence `/opt/cursor/artifacts/launch/stage50_f1_freemium_trial.json` (`test_freemium_trial_f1.py`). Stage 50 D1 commercial acquisition & trial fidelity Complete (MVP) — `docs/STAGE_50_FIDELITY.md` (`test_stage50_fidelity_d1.py`). Stage 50 exit met — `docs/STAGE_50_EXIT_CRITERIA.md`, ADR-106 (`test_stage50_exit_h50x.py`). Stage 51 open: `docs/STAGE_51_PLAN.md`, ADR-107 (`test_stage51_open.py`). Stage 51 M1 marketplace presence honesty Complete (MVP) — `docs/MARKETPLACE_PRESENCE_MVP.md`, `ops/mvp/marketplace-presence.json` (`test_marketplace_presence_m1.py`). Stage 51 A1 add-on services honesty Complete (MVP) — `docs/ADDON_SERVICES_MVP.md`, `ops/mvp/addon-services.json`; evidence `/opt/cursor/artifacts/launch/stage51_a1_addon_services.json` (`test_addon_services_a1.py`). Stage 51 D1 commercial marketplace & add-ons fidelity Complete (MVP) — `docs/STAGE_51_FIDELITY.md` (`test_stage51_fidelity_d1.py`). Stage 51 exit met — `docs/STAGE_51_EXIT_CRITERIA.md`, ADR-108 (`test_stage51_exit_h51x.py`). Stage 52 open: `docs/STAGE_52_PLAN.md`, ADR-109 (`test_stage52_open.py`). Stage 52 I1 industry partnerships honesty Complete (MVP) — `docs/INDUSTRY_PARTNERSHIPS_MVP.md`, `ops/mvp/industry-partnerships.json` (`test_industry_partnerships_i1.py`). Stage 52 R1 subscription renewal / annual discount honesty Complete (MVP) — `docs/SUBSCRIPTION_RENEWAL_MVP.md`, `ops/mvp/subscription-renewal.json`; evidence `/opt/cursor/artifacts/launch/stage52_r1_subscription_renewal.json` (`test_subscription_renewal_r1.py`). Stage 52 D1 commercial partnerships & renewal fidelity Complete (MVP) — `docs/STAGE_52_FIDELITY.md` (`test_stage52_fidelity_d1.py`). Stage 52 exit met — `docs/STAGE_52_EXIT_CRITERIA.md`, ADR-110 (`test_stage52_exit_h52x.py`). Stage 53 open: `docs/STAGE_53_PLAN.md`, ADR-111 (`test_stage53_open.py`). Stage 53 A1 API & integration commercial honesty Complete (MVP) — `docs/API_INTEGRATION_COMMERCIAL_MVP.md`, `ops/mvp/api-integration-commercial.json` (`test_api_integration_commercial_a1.py`). Stage 53 C1 cancellation / refund / churn policy honesty Complete (MVP) — `docs/CANCELLATION_CHURN_MVP.md`, `ops/mvp/cancellation-churn.json`; evidence `/opt/cursor/artifacts/launch/stage53_c1_cancellation_churn.json` (`test_cancellation_churn_c1.py`). Stage 53 D1 commercial API & lifecycle fidelity Complete (MVP) — `docs/STAGE_53_FIDELITY.md` (`test_stage53_fidelity_d1.py`). Stage 53 exit met — `docs/STAGE_53_EXIT_CRITERIA.md`, ADR-112 (`test_stage53_exit_h53x.py`). Stage 54 open: `docs/STAGE_54_PLAN.md`, ADR-113 (`test_stage54_open.py`). Stage 54 M1 digital marketing / case studies / testimonials honesty Complete (MVP) — `docs/DIGITAL_MARKETING_MVP.md`, `ops/mvp/digital-marketing.json` (`test_digital_marketing_m1.py`). Stage 54 S1 direct sales honesty Complete (MVP) — `docs/DIRECT_SALES_MVP.md`, `ops/mvp/direct-sales.json`; evidence `/opt/cursor/artifacts/launch/stage54_s1_direct_sales.json` (`test_direct_sales_s1.py`). Stage 54 D1 commercial go-to-market fidelity Complete (MVP) — `docs/STAGE_54_FIDELITY.md` (`test_stage54_fidelity_d1.py`). Stage 54 exit met — `docs/STAGE_54_EXIT_CRITERIA.md`, ADR-114 (`test_stage54_exit_h54x.py`). Stage 55 open: `docs/STAGE_55_PLAN.md`, ADR-115 (`test_stage55_open.py`). Stage 55 W1 white-label licensing commercial honesty Complete (MVP) — `docs/WHITE_LABEL_LICENSING_MVP.md`, `ops/mvp/white-label-licensing.json` (`test_white_label_licensing_w1.py`). Stage 55 U1 unit economics / competitive positioning honesty Complete (MVP) — `docs/UNIT_ECONOMICS_POSITIONING_MVP.md`, `ops/mvp/unit-economics-positioning.json`; evidence `/opt/cursor/artifacts/launch/stage55_u1_unit_economics_positioning.json` (`test_unit_economics_positioning_u1.py`). Stage 55 D1 commercial licensing & positioning fidelity Complete (MVP) — `docs/STAGE_55_FIDELITY.md` (`test_stage55_fidelity_d1.py`). Stage 55 exit met — `docs/STAGE_55_EXIT_CRITERIA.md`, ADR-116 (`test_stage55_exit_h55x.py`). Stage 56 open: `docs/STAGE_56_PLAN.md`, ADR-117 (`test_stage56_open.py`). Stage 56 O1 implementation & onboarding commercial honesty Complete (MVP) — `docs/IMPLEMENTATION_ONBOARDING_MVP.md`, `ops/mvp/implementation-onboarding.json` (`test_implementation_onboarding_o1.py`). Stage 56 G1 geographic expansion honesty Complete (MVP) — `docs/GEOGRAPHIC_EXPANSION_MVP.md`, `ops/mvp/geographic-expansion.json` (`test_geographic_expansion_g1.py`). Stage 56 D1 commercial onboarding & expansion fidelity Complete (MVP) — `docs/STAGE_56_FIDELITY.md` (`test_stage56_fidelity_d1.py`). Stage 56 exit met — `docs/STAGE_56_EXIT_CRITERIA.md`, ADR-118 (`test_stage56_exit_h56x.py`). Stage 57 open: `docs/STAGE_57_PLAN.md`, ADR-119 (`test_stage57_open.py`). Stage 57 A1 mobile app GTM honesty Complete (MVP) — `docs/MOBILE_APP_GTM_MVP.md`, `ops/mvp/mobile-app-gtm.json` (`test_mobile_app_gtm_a1.py`). Stage 57 K1 success metrics honesty Complete (MVP) — `docs/SUCCESS_METRICS_MVP.md`, `ops/mvp/success-metrics.json` (`test_success_metrics_k1.py`). Stage 57 D1 commercial mobile & metrics fidelity Complete (MVP) — `docs/STAGE_57_FIDELITY.md` (`test_stage57_fidelity_d1.py`). Stage 57 exit met — `docs/STAGE_57_EXIT_CRITERIA.md`, ADR-120 (`test_stage57_exit_h57x.py`). Stage 58 open: `docs/STAGE_58_PLAN.md`, ADR-121 (`test_stage58_open.py`). Stage 58 B1 business metrics honesty Complete (MVP) — `docs/BUSINESS_METRICS_MVP.md`, `ops/mvp/business-metrics.json` (`test_business_metrics_b1.py`). Stage 58 I1 AI metrics honesty Complete (MVP) — `docs/AI_METRICS_MVP.md`, `ops/mvp/ai-metrics.json` (`test_ai_metrics_i1.py`). Stage 58 D1 commercial business & AI metrics fidelity Complete (MVP) — `docs/STAGE_58_FIDELITY.md` (`test_stage58_fidelity_d1.py`). Stage 58 exit met — `docs/STAGE_58_EXIT_CRITERIA.md`, ADR-122 (`test_stage58_exit_h58x.py`). Stage 59 open: `docs/STAGE_59_PLAN.md`, ADR-123 (`test_stage59_open.py`). Stage 59 E1 e-commerce integration honesty Complete (MVP) — `docs/ECOMMERCE_INTEGRATION_MVP.md`, `ops/mvp/ecommerce-integration.json` (`test_ecommerce_integration_e1.py`). Stage 59 C1 CRM commercial honesty Complete (MVP) — `docs/CRM_COMMERCIAL_MVP.md`, `ops/mvp/crm-commercial.json` (`test_crm_commercial_c1.py`). Stage 59 D1 commercial channel extensions fidelity Complete (MVP) — `docs/STAGE_59_FIDELITY.md` (`test_stage59_fidelity_d1.py`). Stage 59 exit met — `docs/STAGE_59_EXIT_CRITERIA.md`, ADR-124 (`test_stage59_exit_h59x.py`). Stage 60 open: `docs/STAGE_60_PLAN.md`, ADR-125 (`test_stage60_open.py`). Stage 60 M1 advanced manufacturing honesty Complete (MVP) — `docs/ADVANCED_MANUFACTURING_MVP.md`, `ops/mvp/advanced-manufacturing.json` (`test_advanced_manufacturing_m1.py`). Stage 60 T1 multi-country tax honesty Complete (MVP) — `docs/MULTI_COUNTRY_TAX_MVP.md`, `ops/mvp/multi-country-tax.json` (`test_multi_country_tax_t1.py`). Stage 60 D1 commercial manufacturing & tax fidelity Complete (MVP) — `docs/STAGE_60_FIDELITY.md` (`test_stage60_fidelity_d1.py`). Stage 60 exit met — `docs/STAGE_60_EXIT_CRITERIA.md`, ADR-126 (`test_stage60_exit_h60x.py`). Stage 61 open: `docs/STAGE_61_PLAN.md`, ADR-127 (`test_stage61_open.py`). Stage 61 F1 embedded fintech honesty Complete (MVP) — `docs/EMBEDDED_FINTECH_MVP.md`, `ops/mvp/embedded-fintech.json` (`test_embedded_fintech_f1.py`). Stage 61 S1 supply chain integration honesty Complete (MVP) — `docs/SUPPLY_CHAIN_INTEGRATION_MVP.md`, `ops/mvp/supply-chain-integration.json` (`test_supply_chain_integration_s1.py`). Stage 61 D1 commercial fintech & supply-chain fidelity Complete (MVP) — `docs/STAGE_61_FIDELITY.md` (`test_stage61_fidelity_d1.py`). Stage 61 exit met — `docs/STAGE_61_EXIT_CRITERIA.md`, ADR-128 (`test_stage61_exit_h61x.py`). Stage 62 open: `docs/STAGE_62_PLAN.md`, ADR-129 (`test_stage62_open.py`). Stage 62 I1 IoT integration honesty Complete (MVP) — `docs/IOT_INTEGRATION_MVP.md`, `ops/mvp/iot-integration.json` (`test_iot_integration_i1.py`). Stage 62 A1 AI model marketplace honesty Complete (MVP) — `docs/AI_MODEL_MARKETPLACE_MVP.md`, `ops/mvp/ai-model-marketplace.json` (`test_ai_model_marketplace_a1.py`). Stage 62 D1 commercial IoT & AI marketplace fidelity Complete (MVP) — `docs/STAGE_62_FIDELITY.md` (`test_stage62_fidelity_d1.py`). Stage 62 exit met — `docs/STAGE_62_EXIT_CRITERIA.md`, ADR-130 (`test_stage62_exit_h62x.py`). Stage 63 open: `docs/STAGE_63_PLAN.md`, ADR-131 (`test_stage63_open.py`). Stage 63 P1 IPO readiness honesty Complete (MVP) — `docs/IPO_READINESS_MVP.md`, `ops/mvp/ipo-readiness.json` (`test_ipo_readiness_p1.py`). Stage 63 G1 global scale honesty Complete (MVP) — `docs/GLOBAL_SCALE_MVP.md`, `ops/mvp/global-scale.json` (`test_global_scale_g1.py`). Stage 63 D1 commercial capital & scale fidelity Complete (MVP) — `docs/STAGE_63_FIDELITY.md` (`test_stage63_fidelity_d1.py`). Stage 63 exit met — `docs/STAGE_63_EXIT_CRITERIA.md`, ADR-132 (`test_stage63_exit_h63x.py`). Stage 64 open: `docs/STAGE_64_PLAN.md`, ADR-133 (`test_stage64_open.py`). Stage 64 B1 Advanced BI honesty Complete (MVP) — `docs/ADVANCED_BI_MVP.md`, `ops/mvp/advanced-bi.json` (`test_advanced_bi_b1.py`). Stage 64 F1 Franchise & chain enterprise honesty Complete (MVP) — `docs/FRANCHISE_CHAIN_MVP.md`, `ops/mvp/franchise-chain.json` (`test_franchise_chain_f1.py`). Stage 64 D1 commercial analytics & franchise fidelity Complete (MVP) — `docs/STAGE_64_FIDELITY.md` (`test_stage64_fidelity_d1.py`). Stage 64 exit met — `docs/STAGE_64_EXIT_CRITERIA.md`, ADR-134 (`test_stage64_exit_h64x.py`). Stage 65 open: `docs/STAGE_65_PLAN.md`, ADR-135 (`test_stage65_open.py`). Stage 65 R1 Release pipeline honesty Complete (MVP) — `docs/RELEASE_PIPELINE_MVP.md`, `ops/mvp/release-pipeline.json` (`test_release_pipeline_r1.py`). Stage 65 P1 Controlled business pilot honesty Complete (MVP) — `docs/BUSINESS_PILOT_MVP.md`, `ops/mvp/business-pilot.json` (`test_business_pilot_p1.py`). Stage 65 D1 MVP release-candidate fidelity Complete (MVP) — `docs/STAGE_65_FIDELITY.md` (`test_stage65_fidelity_d1.py`). Stage 66 open: `docs/STAGE_66_PLAN.md`, ADR-138 (`test_stage66_open.py`). Stage 66 L1 Production launch honesty Complete (MVP) — `docs/PRODUCTION_LAUNCH_MVP.md`, `ops/mvp/production-launch.json` (`test_production_launch_l1.py`). Stage 66 T1 First tenant go-live honesty Complete (MVP) — `docs/FIRST_TENANT_GOLIVE_MVP.md`, `ops/mvp/first-tenant-golive.json` (`test_first_tenant_golive_t1.py`). Stage 66 D1 MVP production-launch fidelity Complete (MVP) — `docs/STAGE_66_FIDELITY.md` (`test_stage66_fidelity_d1.py`). Stage 66 H66x exit + freeze: `docs/STAGE_66_EXIT_CRITERIA.md`, ADR-139 (`test_stage66_exit_h66x.py`). Stage 67 open: `docs/STAGE_67_PLAN.md`, ADR-140 (`test_stage67_open.py`). Stage 67 H1 Production hypercare honesty Complete (MVP) — `docs/PRODUCTION_HYPERCARE_MVP.md`, `ops/mvp/production-hypercare.json` (`test_production_hypercare_h1.py`). Stage 67 C1 Post-launch continuity honesty Complete (MVP) — `docs/POST_LAUNCH_CONTINUITY_MVP.md`, `ops/mvp/post-launch-continuity.json` (`test_post_launch_continuity_c1.py`). Stage 67 D1 MVP post-launch continuity fidelity Complete (MVP) — `docs/STAGE_67_FIDELITY.md` (`test_stage67_fidelity_d1.py`). Stage 67 H67x exit + freeze: `docs/STAGE_67_EXIT_CRITERIA.md`, ADR-141 (`test_stage67_exit_h67x.py`). Stage 68 open: `docs/STAGE_68_PLAN.md`, ADR-142 (`test_stage68_open.py`). Stage 68 H1 Ribdigi House console honesty Complete (MVP) — `docs/RIBDIGI_HOUSE_CONSOLE_MVP.md`, `ops/mvp/ribdigi-house-console.json` (`test_ribdigi_house_console_h1.py`). Stage 68 T1 Tenant Company console honesty Complete (MVP) — `docs/TENANT_COMPANY_CONSOLE_MVP.md`, `ops/mvp/tenant-company-console.json` (`test_tenant_company_console_t1.py`). Stage 68 D1 Platform ↔ Tenant console fidelity Complete (MVP) — `docs/STAGE_68_FIDELITY.md` (`test_stage68_fidelity_d1.py`). Stage 68 H68x exit + freeze: `docs/STAGE_68_EXIT_CRITERIA.md`, ADR-143 (`test_stage68_exit_h68x.py`). Stage 69 open: `docs/STAGE_69_PLAN.md`, ADR-144 (`test_stage69_open.py`). Stage 69 V1 Pre-flight verification honesty Complete (MVP) — `docs/PREFLIGHT_VERIFICATION_MVP.md`, `ops/mvp/preflight-verification.json` (`test_preflight_verification_v1.py`). Stage 69 A1 Go-live attestation honesty Complete (MVP) — `docs/GOLIVE_ATTESTATION_MVP.md`, `ops/mvp/golive-attestation.json` (`test_golive_attestation_a1.py`). Honesty: `section_7_signed` / `attestation_claimed` / `go_live_claimed` remain false (packaging ≠ §7 signed). Stage 69 D1 Commercial Go-Live fidelity Complete (MVP) — `docs/STAGE_69_FIDELITY.md` (`test_stage69_fidelity_d1.py`); maps V1–A1. Stage 69 H69x exit + freeze Complete (MVP) — `docs/STAGE_69_EXIT_CRITERIA.md`, ADR-145 (`test_stage69_exit_h69x.py`). Stage 70 open: `docs/STAGE_70_PLAN.md`, ADR-146 (`test_stage70_open.py`). Stage 70 F1 First commercial day ops honesty Complete (MVP) — `docs/FIRST_COMMERCIAL_DAY_MVP.md`, `ops/mvp/first-commercial-day.json` (`test_first_commercial_day_f1.py`). Honesty: `first_commercial_day_claimed` / `commercial_day_ops_live_claimed` remain false (packaging ≠ first-day live). Stage 70 G1 Commercial go-live closeout honesty Complete (MVP) — `docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md`, `ops/mvp/commercial-golive-closeout.json` (`test_commercial_golive_closeout_g1.py`). Honesty: `go_live_claimed` / `commercial_golive_closeout_claimed` remain false (packaging ≠ go-live). Stage 70 D1 First Commercial Day fidelity Complete (MVP) — `docs/STAGE_70_FIDELITY.md` (`test_stage70_fidelity_d1.py`); maps F1–G1. Stage 70 H70x exit + freeze Complete (MVP) — `docs/STAGE_70_EXIT_CRITERIA.md`, ADR-147 (`test_stage70_exit_h70x.py`). Stage 71 open: `docs/STAGE_71_PLAN.md`, ADR-148 (`test_stage71_open.py`). Stage 71 S1 Steady-state commercial ops honesty Complete (MVP) — `docs/STEADY_STATE_OPS_MVP.md`, `ops/mvp/steady-state-ops.json` (`test_steady_state_ops_s1.py`). Honesty: `steady_state_ops_claimed` / `commercial_acceptance_claimed` remain false (packaging ≠ steady-state live). Stage 71 A1 Commercial acceptance gate honesty Complete (MVP) — `docs/COMMERCIAL_ACCEPTANCE_MVP.md`, `ops/mvp/commercial-acceptance.json` (`test_commercial_acceptance_a1.py`). Honesty: `commercial_acceptance_claimed` / `go_live_claimed` remain false (packaging ≠ acceptance Complete). Stage 71 D1 Commercial Steady-State fidelity Complete (MVP) — `docs/STAGE_71_FIDELITY.md` (`test_stage71_fidelity_d1.py`); maps S1–A1. Stage 71 H71x exit + freeze Complete (MVP) — `docs/STAGE_71_EXIT_CRITERIA.md`, ADR-149 (`test_stage71_exit_h71x.py`). Stage 72 open: `docs/STAGE_72_PLAN.md`, ADR-150 (`test_stage72_open.py`). Stage 72 R1 Commercial residual remaining honesty Complete (MVP) — `docs/COMMERCIAL_RESIDUAL_MVP.md`, `ops/mvp/commercial-residual.json` (`test_commercial_residual_r1.py`). Stage 72 P1 Commercial packaging archive honesty Complete (MVP) — `docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md`, `ops/mvp/commercial-packaging-archive.json` (`test_commercial_packaging_archive_p1.py`). Stage 72 D1 Commercial Packaging Closeout fidelity Complete (MVP) — `docs/STAGE_72_FIDELITY.md` (`test_stage72_fidelity_d1.py`); maps R1–P1. Stage 72 H72x exit + freeze Complete (MVP) — `docs/STAGE_72_EXIT_CRITERIA.md`, ADR-151 (`test_stage72_exit_h72x.py`). Stage 73 open: `docs/STAGE_73_PLAN.md`, ADR-152 (`test_stage73_open.py`). Stage 73 E1 Commercial evidence chain honesty Complete (MVP) — `docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md`, `ops/mvp/commercial-evidence-chain.json` (`test_commercial_evidence_chain_e1.py`). Stage 73 A1 Commercial assurance boundary honesty Complete (MVP) — `docs/COMMERCIAL_ASSURANCE_MVP.md`, `ops/mvp/commercial-assurance.json` (`test_commercial_assurance_a1.py`). Stage 73 D1 Commercial Assurance fidelity Complete (MVP) — `docs/STAGE_73_FIDELITY.md` (`test_stage73_fidelity_d1.py`); maps E1–A1. Stage 73 H73x exit + freeze Complete (MVP) — `docs/STAGE_73_EXIT_CRITERIA.md`, ADR-153 (`test_stage73_exit_h73x.py`). Stage 74 open: `docs/STAGE_74_PLAN.md`, ADR-154 (`test_stage74_open.py`). Stage 74 S1 Commercial support boundary honesty Complete (MVP) — `docs/COMMERCIAL_SUPPORT_MVP.md`, `ops/mvp/commercial-support.json` (`test_commercial_support_s1.py`). Stage 74 U1 Commercial status boundary honesty Complete (MVP) — `docs/COMMERCIAL_STATUS_MVP.md`, `ops/mvp/commercial-status.json` (`test_commercial_status_u1.py`). Stage 74 D1 Commercial Operator Boundary fidelity Complete (MVP) — `docs/STAGE_74_FIDELITY.md` (`test_stage74_fidelity_d1.py`); maps S1–U1. Stage 74 H74x exit + freeze Complete (MVP) — `docs/STAGE_74_EXIT_CRITERIA.md`, ADR-155 (`test_stage74_exit_h74x.py`). Stage 75 C1 commercial security contact honesty Complete (MVP) — `docs/COMMERCIAL_SECURITY_CONTACT_MVP.md`, `ops/mvp/commercial-security-contact.json` (`test_commercial_security_contact_c1.py`); security contact live Remaining. Stage 75 P1 commercial privacy notice honesty Complete (MVP) — `docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md`, `ops/mvp/commercial-privacy-notice.json` (`test_commercial_privacy_notice_p1.py`); privacy notice live Remaining. Stage 75 D1 Commercial Trust Boundary fidelity Complete (MVP) — `docs/STAGE_75_FIDELITY.md` (`test_stage75_fidelity_d1.py`); maps C1–P1. Stage 75 H75x exit + freeze Complete (MVP) — `docs/STAGE_75_EXIT_CRITERIA.md`, ADR-157 (`test_stage75_exit_h75x.py`). Stage 76 T1 commercial terms honesty Complete (MVP) — `docs/COMMERCIAL_TERMS_MVP.md`, `ops/mvp/commercial-terms.json` (`test_commercial_terms_t1.py`); signed ToS Remaining. Stage 76 B1 commercial billing deferred honesty Complete (MVP) — `docs/COMMERCIAL_BILLING_DEFERRED_MVP.md`, `ops/mvp/commercial-billing-deferred.json` (`test_commercial_billing_deferred_b1.py`); paid billing Remaining. Stage 76 D1 Commercial Contract Boundary fidelity Complete (MVP) — `docs/STAGE_76_FIDELITY.md` (`test_stage76_fidelity_d1.py`); maps T1–B1. Stage 76 H76x exit + freeze Complete (MVP) — `docs/STAGE_76_EXIT_CRITERIA.md`, ADR-159 (`test_stage76_exit_h76x.py`). Stage 77 A1 commercial DPA honesty Complete (MVP) — `docs/COMMERCIAL_DPA_MVP.md`, `ops/mvp/commercial-dpa.json` (`test_commercial_dpa_a1.py`); signed DPA Remaining. Stage 77 L1 commercial liability honesty Complete (MVP) — `docs/COMMERCIAL_LIABILITY_MVP.md`, `ops/mvp/commercial-liability.json` (`test_commercial_liability_l1.py`); liability cap signed Remaining. Stage 77 D1 Commercial Legal Envelope fidelity Complete (MVP) — `docs/STAGE_77_FIDELITY.md` (`test_stage77_fidelity_d1.py`); maps A1–L1. Stage 77 H77x exit + freeze Complete (MVP) — `docs/STAGE_77_EXIT_CRITERIA.md`, ADR-161 (`test_stage77_exit_h77x.py`). Stage 78 P1 commercial pricing honesty Complete (MVP) — `docs/COMMERCIAL_PRICING_MVP.md`, `ops/mvp/commercial-pricing.json` (`test_commercial_pricing_p1.py`); public pricing portal Remaining. Stage 78 S1 commercial professional services honesty Complete (MVP) — `docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md`, `ops/mvp/commercial-professional-services.json` (`test_commercial_professional_services_s1.py`); signed SOW Remaining. Stage 78 D1 Commercial Procurement Boundary fidelity Complete (MVP) — `docs/STAGE_78_FIDELITY.md` (`test_stage78_fidelity_d1.py`); maps P1–S1. Stage 78 H78x exit + freeze Complete (MVP) — `docs/STAGE_78_EXIT_CRITERIA.md`, ADR-163 (`test_stage78_exit_h78x.py`).  Stages 1–42 frozen for Stage 42 scope; external LLM / AI certification Remaining.` (`test_stage42_fidelity_d1.py`; A1–P1). Stage 41 exit met — `docs/STAGE_41_EXIT_CRITERIA.md`, ADR-088 (`test_stage41_exit_h41x.py`) Stage 42 open: `docs/STAGE_42_PLAN.md`, ADR-089 (`test_stage42_open.py`). Stage 42 A1 AI use disclosure honesty Complete (MVP) Stage 42 P1 AI model/provider boundary honesty Complete (MVP) — `docs/AI_PROVIDER_BOUNDARY_MVP.md`, `ops/mvp/ai-provider-boundary.json` (`test_ai_provider_boundary_p1.py`); external LLM Remaining. — `docs/AI_USE_DISCLOSURE_MVP.md`, `ops/mvp/ai-use-disclosure.json` (`test_ai_use_disclosure_a1.py`); AI certification Remaining.; Stages 1–41 frozen for Stage 41 scope; WCAG AA audit / public change calendar Remaining.` (`test_stage41_fidelity_d1.py`; A1–C1). Stage 40 exit met — `docs/STAGE_40_EXIT_CRITERIA.md`, ADR-086 (`test_stage40_exit_h40x.py`) Stage 41 open: `docs/STAGE_41_PLAN.md`, ADR-087 (`test_stage41_open.py`). Stage 41 A1 accessibility statement honesty Complete (MVP) Stage 41 C1 change/maintenance governance honesty Complete (MVP) — `docs/CHANGE_GOVERNANCE_MVP.md`, `ops/mvp/change-governance.json` (`test_change_governance_c1.py`); public change calendar Remaining. — `docs/ACCESSIBILITY_STATEMENT_MVP.md`, `ops/mvp/accessibility-statement.json` (`test_accessibility_statement_a1.py`); WCAG AA audit Remaining.; Stages 1–40 frozen for Stage 40 scope; live status page / SBOM pipeline Remaining.` (`test_stage40_fidelity_d1.py`; U1–S1).` (`test_stage39_fidelity_d1.py`; P1–A1). Stage 39 H39x exit + freeze — `docs/STAGE_39_EXIT_CRITERIA.md Stage 40 open: `docs/STAGE_40_PLAN.md`, ADR-085 (`test_stage40_open.py`). Stage 40 U1: `docs/STATUS_UPTIME_MVP.md` (`test_status_uptime_u1.py`). Stage 40 S1 SBOM/dependency disclosure honesty Complete (MVP) — `docs/SBOM_DISCLOSURE_MVP.md`, `ops/mvp/sbom-disclosure.json` (`test_sbom_disclosure_s1.py`); live SBOM pipeline Remaining.`, ADR-084 (`test_stage39_exit_h39x.py`). Stage 34 H34x exit + freeze — `docs/STAGE_34_EXIT_CRITERIA.md`, ADR-074 (`test_stage34_exit_h34x.py`).

---

### 4.17 Audit Logs

#### BR-17.1 Activity Tracking
- **Description:** Immutable record of system activities.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Login/Logout:** Timestamp, IP address, device, success/failure — Stage 18 A1 (`login` / `login_failed` / `logout` / `idle_logout`; `module=auth`)
  - [x] **Product Changes:** Create, update, delete with before/after values — Stage 17 A1 (`product_create` / `product_update` / soft-delete `product_deactivate`; stock mutations `stock_*` with before/after qty)
  - [x] **Sales:** Invoice creation, modification, cancellation — Stage 15 A1 enriched `invoice_posted` + `sales_return_posted`
  - [x] **Purchases:** PO, GRN, invoice changes — Stage 18 A1 / Stage 11 A1 (`po_created` / `grn_posted` / PI approve; hash-chained)
  - [x] **User Activity:** Permission changes, role assignments, deletions — Stage 18 A1 (`user_created` / `user_updated` role / `user_deactivated`)
  - [x] **Financial:** Journal entry posting, account modifications — Stage 18 A1 / Stage 1 financial ops (`journal_posted` + hash verify)

#### BR-17.2 Audit Log Management
- **Description:** Search and retention of audit data.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Filter by user, module, action type, date range — Stage 18 A1 (`GET /audit-logs` params)
  - [x] Export audit logs (CSV, PDF) — Stage 18 A1 (`GET /audit-logs/export`)
  - [x] Tamper-proof storage (append-only, hashed) — Stage 18 A1 / Stage 1 G19 (`GET /audit-logs/verify`)
  - [x] Retention policy: minimum 7 years for financial records — Stage 18 A1 / Stage 1 G20 (`GET /audit-logs/retention`)

Fidelity sync: Stage 18 D1 — `docs/STAGE_18_FIDELITY.md`.

---

### 4.18 API

#### BR-18.1 Authentication API
- **Description:** Secure API access.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] OAuth2 / JWT token generation — Stage 19 K1 (`POST /auth/login` → Bearer JWT access + refresh; `test_auth_api_fidelity_k1.py`)
  - [x] Token refresh endpoint — Stage 19 K1 (`POST /auth/refresh` rotates session; old refresh → 401)
  - [x] API key support for service integrations (Stage 6 K1: `POST/GET/DELETE /api-keys`, `X-API-Key` auth; Stage 19 K1 regression)
  - [x] Rate limiting per tenant — Stage 19 K1 / Stage 5 S1: sliding-window by client IP + auth|api class + `X-Tenant-ID` scope; `X-RateLimit-Limit`/`Remaining`/`Backend` (+ `Retry-After` on 429); plan-tier caps deferred

#### BR-18.2 Products API
- **Description:** Product data access and management.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] CRUD operations for products, categories, brands, units — Stage 19 P1 (`/products`, `/catalog/categories|brands|units`; product soft-deactivate via `PATCH is_active=false`; `test_products_customers_api_p1.py`)
  - [x] Bulk import/export — Stage 19 P1: CSV import (`GET/POST /products/import[/template]`); list/report packaging (`GET /products`, inventory report exports); dedicated catalog CSV export deferred
  - [x] Stock level queries — Stage 19 P1 (`GET /products/{id}` `stock_qty`, `GET /products/{id}/warehouse-stock`, low-stock/report surfaces)
  - [x] Barcode lookup — Stage 19 P1 (`GET /inventory/products/lookup`)

#### BR-18.3 Customers API
- **Description:** Customer data access.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] CRUD operations for customers and customer groups — Stage 19 P1 (`/customers`, `/customers/groups`; soft-deactivate via `DELETE`)
  - [x] Balance inquiry — Stage 19 P1 (`balance` on customer GET/list; deeper credit statement/outstanding under `credit:read`)
  - [x] Purchase history — Stage 19 P1 (`GET /customers/{id}/history`)

#### BR-18.4 Sales API
- **Description:** Sales transaction API.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create quotations, sales orders, invoices — Stage 19 S1 / Stage 12 C1 (`/sales/quotations` → `convert-order` → confirm → `convert-invoice` → post; `test_sales_purchases_api_s1.py`)
  - [x] Record payments — Stage 19 S1 / Stage 12 C1 (`POST /sales/payments`)
  - [x] Sales return processing — Stage 19 S1 / Stage 15 R1 (`POST /sales/returns`; post chain in `test_sales_return_chain_r1.py`)
  - [x] POS transaction submission — Stage 19 S1 / Stage 12 C2 / Stage 13 H1–H2 (`POST /pos/sessions/open`, `POST /pos/sales`)

#### BR-18.5 Purchases API
- **Description:** Procurement API.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create purchase requests, orders, GRNs, invoices — Stage 19 S1 / Stage 11 C1 (`/purchasing/requests` → convert, `/purchasing/orders` → send → GRN → PI approve; `test_sales_purchases_api_s1.py`)
  - [x] Supplier management — Stage 19 S1 (`GET/POST/PATCH /suppliers`)
  - [x] Payment recording — Stage 19 S1 / Stage 11 C1 (`POST /suppliers/{id}/payments`)

#### BR-18.6 API Standards
- **Description:** Consistent API design.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] RESTful design with standard HTTP methods — Stage 19 A1 (`GET/POST/PATCH` under `/api/v1`; `test_api_standards_a1.py`)
  - [x] JSON request/response format — Stage 19 A1 (`application/json` + `env()` success envelope)
  - [x] Standard error response structure — Stage 19 A1 (FastAPI `detail` + rate-limit envelope; see API_DOCUMENTATION §1.2)
  - [x] Pagination for list endpoints — Stage 19 A1 (`limit` on high-volume lists e.g. audit-logs; full-array lists for catalog/parties; cursor deferred)
  - [x] Versioning (/api/v1/) — Stage 19 A1 (router prefix `/api/v1`)
  - [x] OpenAPI/Swagger documentation auto-generated — Stage 19 A1 (`/openapi.json`, `/docs` when not production)
  - [x] Webhook support for event subscriptions (Stage 6 W1: HMAC-signed outbound webhooks; Stage 19 A1 regression)

---

### 4.19 Authentication & Security

#### BR-19.1 Authentication
- **Description:** Secure user access.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] Email/password login with bcrypt hashing — Stage 19 U1 (`POST /auth/login`; password hashes `$2b$…`; `test_auth_session_br19_u1.py`)
  - [x] Password complexity requirements (min 8 chars, mixed case, number, symbol) — Stage 19 U1 (`validate_password_strength` / change-password reject)
  - [x] Account lockout after 5 failed attempts (30-minute cooldown) — Stage 19 U1 (`423` + `locked_until` ≈ +30m)
  - [x] Email verification before first login — Stage 19 U1 (`EMAIL_NOT_VERIFIED`; also `test_email_verification_gate.py`)
  - [x] Password reset via secure token link (expires in 1 hour) — Stage 19 U1 (`issue_one_time_token` 1h; `POST /auth/password-reset*`)

#### BR-19.2 Two-Factor Authentication (2FA)
- **Description:** Enhanced account security.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Optional TOTP-based 2FA (Google Authenticator, Authy) — Stage 19 U1 (`POST /auth/2fa/setup` + `confirm`; WebAuthn in `test_webauthn.py`)
  - [x] QR code setup for 2FA — Stage 19 U1 (`otpauth_url` + `qr_png_base64`)
  - [x] Backup recovery codes — Stage 19 U1 (returned once on confirm)
  - [x] Enforce 2FA for Super Admin and Company Admin roles — Stage 19 U1 (`must_enroll_2fa` on login; `role_requires_2fa`)

#### BR-19.3 Session Management
- **Description:** Control active user sessions.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] JWT token with configurable expiry (default: 24 hours) — Stage 19 U1: configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (engine default **15** minutes; `expires_in` matches config)
  - [x] Refresh token rotation — Stage 19 U1 / Stage 19 K1 (`POST /auth/refresh` invalidates old refresh)
  - [x] View active sessions per user — Stage 19 U1 (`GET /auth/sessions`)
  - [x] Remote session termination — Stage 19 U1 (`DELETE /auth/sessions/{id}`)
  - [x] Auto-logout on inactivity (configurable timeout) — Stage 19 U1 (`POST /auth/idle-logout`; tenant inactivity setting)

---

### 4.20 System Settings

#### BR-20.1 Company Information
- **Description:** Global company settings.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Edit legal name, address, contact, tax ID — Stage 19 C1 (`PATCH /tenants/me` legal/address/contact/`tax_registration_number`; `test_company_settings_br20_c1.py`)
  - [x] Upload company logo (used on invoices, receipts) — Stage 19 C1 (`POST/GET /tenants/me/logo`)

#### BR-20.2 Formatting
- **Description:** Regional display preferences.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Date format selection (DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD) — Stage 19 C1 (`tenants.date_format`)
  - [x] Number format (decimal separator, thousand separator) — Stage 19 C1 (`1,234.56` / `1.234,56` / `1 234.56`)
  - [x] Time format (12h / 24h) — Stage 19 C1 (`tenants.time_format`)

#### BR-20.3 Email Settings
- **Description:** SMTP configuration for outbound emails.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] SMTP host, port, username, password — Stage 19 C1 (`PATCH /settings/email`; password encrypted, never returned)
  - [x] TLS/SSL encryption — Stage 19 C1 (`smtp_use_tls` / `smtp_use_ssl`)
  - [x] Test email functionality — Stage 19 C1 (`POST /settings/email/test`)
  - [x] Default sender name and email — Stage 19 C1 (`smtp_from_name` / `smtp_from_email`)

#### BR-20.4 Numbering & Templates
- **Description:** Document customization.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Configure invoice numbering prefix and series (e.g., INV-2026-0001) — Stage 19 C1 (`document_numbering` + preview)
  - [x] Configure PO, GRN, quotation numbering — Stage 19 C1 (`purchase_order` / `goods_receipt` / `sales_quotation` series)
  - [x] Configure sales order, sales return, credit note, purchase return, debit note series — Stage 24 N1 (`sales_order` / `sales_return` / `sales_credit_note` / `purchase_return` / `purchase_debit_note`; live allocate proof `test_document_numbering_n1.py`)
  - [x] Receipt template selection and customization — Stage 19 C1 (`receipt_print_template` thermal_80/thermal_58; richer WYSIWYG designer deferred)
  - [x] Invoice template selection and customization — Stage 19 C1 (`invoice_print_template` a4/thermal_*)
  - [x] Header/footer customization with company branding — Stage 19 C1 (`document_header` / `document_footer`)

Fidelity sync: Stage 19 D1 — `docs/STAGE_19_FIDELITY.md`. Stage 24 N1 shared series + Stage 24 D1/H24x commerce/ops gate docs — `docs/STAGE_24_FIDELITY.md` (`test_document_numbering_n1.py`, `test_stage24_fidelity_d1.py`); exit `docs/STAGE_24_EXIT_CRITERIA.md`, ADR-054 (`test_stage24_exit_h24x.py`).

---

### 4.21 AI Business Assistant

#### BR-21.1 AI ERP Chat Assistant
- **Description:** Natural language interface for ERP operations.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Accept natural language queries ("What is my top selling product this month?") — Stage 20 C1 (`POST /ai/chat` rules_v1; `test_ai_chat_fidelity_c1.py`; also `test_ai_chat.py`)
  - [x] Execute commands via chat ("Create a purchase order for 50 units of Product X") — Stage 20 C1 (draft PO only via `purchasing:write`; no silent send)
  - [x] Context-aware responses based on user role and permissions — Stage 20 C1 (`ai:read` gate; module read checks; purchasing write deny)
  - [x] Chat history persistence — Stage 20 C1 (`GET /ai/chat/history` → `AiQuery` per user/tenant)

#### BR-21.2 AI Dashboard Insight
- **Description:** Automated anomaly detection and recommendations.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Highlight unusual sales drops or spikes — Stage 20 I1 (`sales_wow` / `sales_mom` cards; `GET /ai/insights`; `test_ai_insights_fidelity_i1.py`)
  - [x] Flag expense anomalies — Stage 20 I1 (`expense_spike` / `expense_vs_sales`)
  - [x] Suggest actions ("Restock Product Y — sales up 40% this week") — Stage 20 I1 (`restock_suggestion` / card `action`)
  - [x] Weekly insight digest email — Stage 20 I1 (`publish_insights` → `Weekly AI Insight Digest` + `ai_insight` email prefs; Celery `generate_ai_insights`)
  - [x] Business insights cite Inventory + Sales + Purchases + Expenses actuals — Stage 25 B1 (`domains` / `actuals_covered`; purchase spend WoW, overdue bills, draft PO backlog; `test_ai_business_insights_b1.py`)

#### BR-21.3 Smart Inventory Intelligence
- **Description:** AI-powered inventory optimization.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Demand forecasting per product (7-day, 30-day, 90-day) — Stage 20 V1 (`GET /ai/inventory/demand-forecast`; `test_ai_inventory_intel_v1.py`)
  - [x] Optimal reorder quantity recommendations — Stage 20 V1 (`optimal_reorder_qty` on forecast rows)
  - [x] Seasonality detection — Stage 20 V1 (`seasonality` / `seasonality_factor`; sales_velocity_v1)
  - [x] Dead stock identification — Stage 20 V1 (`GET /ai/inventory/dead-stock`)

#### BR-21.4 AI Low Stock Prediction
- **Description:** Predictive stockout prevention.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Predict stockouts 7–14 days in advance — Stage 20 L1 (`GET /ai/inventory/low-stock-prediction` `horizon_days=14`; `test_ai_low_stock_prediction_l1.py`)
  - [x] Consider sales velocity, seasonality, lead time — Stage 20 L1 (`velocity_per_day` / `seasonality_factor` / `lead_time_days`)
  - [x] Confidence score on predictions — Stage 20 L1 (`confidence` on prediction rows)
  - [x] Auto-generate purchase suggestions — Stage 20 L1 (`suggested_order_qty`; also notify path in `test_ai_low_stock_prediction.py`)

#### BR-21.5 AI Sales Analysis
- **Description:** Deep sales pattern recognition.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Sales trend forecasting — Stage 20 S1 (`GET /ai/sales/analysis` `trend.forecast_totals` 7/14/30; `test_ai_sales_analysis_s1.py`)
  - [x] Customer segmentation (RFM analysis) — Stage 20 S1 (`rfm.customers` / `segment_counts`)
  - [x] Product affinity analysis (frequently bought together) — Stage 20 S1 (`product_affinity.pairs`)
  - [x] Peak hour/day predictions — Stage 20 S1 (`peaks.peak_hour` / `peak_weekday`)

#### BR-21.6 AI Expense Analysis
- **Description:** Intelligent cost management.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Expense categorization from receipt OCR (suggest + Stage 10 A1 confirmed apply) — Stage 20 D1 regression (`GET /ai/expenses/analysis`; `test_ai_sales_expenses.py`)
  - [x] Budget variance alerts — Stage 10 / Stage 20 D1
  - [x] Unusual expense pattern detection — Stage 10 / Stage 20 D1
  - [x] Cost optimization suggestions — Stage 10 / Stage 20 D1

#### BR-21.7 AI Report Generator
- **Description:** Natural language to report.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Generate reports from text prompts ("Show me monthly sales for Q2") — Stage 20 R1 (`POST /ai/reports/generate`; `test_ai_report_generator_r1.py`)
  - [x] Export generated reports — Stage 20 R1 (`POST /ai/reports/generate?export=true` csv/pdf)
  - [x] Save report templates for reuse — Stage 20 R1 (`POST/GET /ai/reports/templates` + generate via `template_id`)

#### BR-21.8 AI Document Assistant
- **Description:** Intelligent document processing.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] OCR extraction from invoices, receipts (suggest + Stage 10 A1 confirmed apply to expense/PI draft; PO OCR deferred) — Stage 20 D1 regression
  - [x] Auto-match extracted data to system records (`/ai/documents/analyze`) — Stage 10 / Stage 20 D1
  - [x] Data validation and discrepancy flagging — Stage 10 / Stage 20 D1

#### BR-21.9 AI Customer Assistant (Basic)
- **Description:** Customer intelligence.
- **Priority:** Low
- **Acceptance Criteria:**
  - [x] Customer churn risk scoring — Stage 20 U1 (`GET /ai/customers/insights` `churn_risks`; `test_ai_customer_security_u1.py`)
  - [x] Best customer identification — Stage 20 U1 (`best_customers`)
  - [x] Personalized promotion suggestions — Stage 20 U1 (`promotion_suggestions`; also `POST /ai/customer/assist`)

#### BR-21.10 AI Security Monitor (Basic)
- **Description:** Behavioral security analysis.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Detect unusual login patterns (time, location, device) — Stage 20 U1 (`GET /ai/security/alerts` `unusual_login_ip` / `unusual_login_device`)
  - [x] Flag suspicious transaction patterns — Stage 20 U1 (`suspicious_transaction_burst`)
  - [x] Alert admins on potential fraud indicators — Stage 20 U1 (`notify=true` → security `Notification`)

#### BR-21.11 AI Purchases Analysis
- **Description:** Basic purchasing pattern recognition over live PO / GRN / purchase-invoice actuals.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Purchase spend trend + short-horizon forecast — Stage 25 P1 (`GET /ai/purchases/analysis` `trend`; `test_ai_purchases_analysis_p1.py`)
  - [x] Supplier concentration / spend share — Stage 25 P1 (`suppliers.rows` / `top_spend_share`)
  - [x] PO fill / open backlog signals — Stage 25 P1 (`purchase_orders.fill` + draft/partial counts)
  - [x] Overdue purchase-invoice + optimization suggestions — Stage 25 P1 (`purchase_invoices.overdue` / `suggestions`)
  - Remaining post-MVP: external LLM / Prophet upgrades (not Stage 25)

#### BR-21.12 Cross-Domain AI Analysis
- **Description:** Orchestrate Inventory + Sales + Purchases + Expenses analyzers into one basic analysis contract with synthesis signals.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Single endpoint returns per-domain summaries — Stage 25 X1 (`GET /ai/cross-domain/analysis` `domains`; `test_ai_cross_domain_x1.py`)
  - [x] Cross-domain synthesis signals (multi-domain kinds) — Stage 25 X1 (`cross_signals`)
  - [x] Extends proven `ai_inventory` / `ai_sales` / `ai_purchases` / `ai_expenses` — no parallel stack
  - Remaining post-MVP: external LLM / Prophet upgrades (not Stage 25)

Fidelity sync: Stage 20 D1 — `docs/STAGE_20_FIDELITY.md` (`test_stage20_fidelity_d1.py`). Stage 25 P1/X1/B1/U1 + Stage 25 D1/H25x commerce actuals AI docs — `docs/STAGE_25_FIDELITY.md`, exit `docs/STAGE_25_EXIT_CRITERIA.md`, freeze ADR-056 (`test_ai_purchases_analysis_p1.py`, `test_ai_cross_domain_x1.py`, `test_ai_business_insights_b1.py`, `test_ai_ui_fidelity_u1.py`, `test_stage25_fidelity_d1.py`, `test_stage25_exit_h25x.py`).

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

Stage **26** **M1**/**C1**/**D1** ops evidence: `docs/OPS_MONITORING_MVP.md`, `docs/LOAD_CAPACITY_MVP.md`, `docs/STAGE_26_FIDELITY.md` (`test_stage26_fidelity_d1.py`).

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
