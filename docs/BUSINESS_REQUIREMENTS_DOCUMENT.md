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
  - [ ] Set per-customer credit limit
  - [ ] Block sales that exceed credit limit (with override permission)
  - [ ] Display outstanding balance on customer profile
  - [ ] Record payment collections with date, amount, method, reference
  - [x] Allocate payments to specific invoices or auto-allocate (oldest first) — Stage 14 R1 Credit UI + API `sales_invoice_id` / supplier `purchase_invoice_id`
  - [ ] Customer statement generation (all transactions + balance)

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
  - [ ] Add tax types (VAT, GST, Sales Tax, etc.)
  - [x] Configure tax rates (percentage) — create + Stage 14 T1 `PATCH /tax/rates/{id}` edit/deactivate (`is_active`; clears default)
  - [ ] Set tax applicability (inclusive/exclusive pricing)
  - [x] Product-category-specific tax rules (Stage 10 T1 — category `tax_rate_id`, parent walk)
  - [ ] Compound tax (tax on tax) support

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
  - [ ] All reports filterable by date range, branch, store — Partial: date on sales/P&L/cash-flow; store on P&L/cash-flow/JE; balance sheet store/branch filters deferred
  - [x] Comparative reports (current period vs previous period) — Stage 4/16 R1 sales daily/monthly `change_pct` / prior period; full financial comparative deferred

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
  - [ ] Backup storage to S3-compatible storage — deferred post-MVP (local `BACKUP_DIR` for `.ribbak`; WAL/S3 PITR out of Stage 18)
  - [x] Failure alerts to admin — Stage 18 B1 (`Backup failed` system notification; no fake success on schedule failure)

#### BR-16.3 Database Restore
- **Description:** Disaster recovery capability.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Restore from backup archive (guarded `confirm_text=RESTORE`; media rehydrate Stage 10 B1) — Stage 18 D1 / Stage 5 B1
  - [ ] Restore to new tenant (for testing) — blocked by design for MVP (cross-tenant restore denied)
  - [x] Restore validation (checksum verification + integrity proof)
  - [ ] Point-in-time recovery (if WAL archiving enabled) — deferred post-MVP

Fidelity sync: Stage 18 D1 — `docs/STAGE_18_FIDELITY.md`.

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
  - [x] Receipt template selection and customization — Stage 19 C1 (`receipt_print_template` thermal_80/thermal_58; richer WYSIWYG designer deferred)
  - [x] Invoice template selection and customization — Stage 19 C1 (`invoice_print_template` a4/thermal_*)
  - [x] Header/footer customization with company branding — Stage 19 C1 (`document_header` / `document_footer`)

Fidelity sync: Stage 19 D1 — `docs/STAGE_19_FIDELITY.md`.

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

Fidelity sync: Stage 20 D1 — `docs/STAGE_20_FIDELITY.md` (`test_stage20_fidelity_d1.py`).

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
