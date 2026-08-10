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
  - [ ] User can register with company name, email, password, industry type
  - [ ] System validates email uniqueness
  - [ ] System auto-creates isolated tenant database/schema
  - [ ] System sends email verification link
  - [ ] Tenant status defaults to "Trial"

#### BR-1.2 Company Profile
- **Description:** Tenant administrators can configure company identity and operational settings.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Upload and display company logo
  - [ ] Edit company name, address, phone, email, website
  - [ ] Configure fiscal year start date
  - [ ] Set default currency and time zone
  - [ ] Select industry from predefined list (Retail, Pharmacy, Restaurant, Bakery, Wholesale, Manufacturing)

#### BR-1.3 Subscription Plan Management
- **Description:** Track and manage tenant subscription lifecycle.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Support statuses: Trial, Active, Suspended
  - [ ] Automatic trial expiration notification (7 days, 3 days, 1 day before)
  - [ ] Grace period handling for suspended tenants (read-only access)
  - [ ] Upgrade/downgrade plan capability

#### BR-1.4 Data Isolation
- **Description:** Ensure complete data separation between tenants.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Tenant A cannot access Tenant B data under any circumstance
  - [ ] Database-level isolation (separate schemas or databases)
  - [ ] API requests include tenant context validation
  - [ ] Backup operations are tenant-scoped

#### BR-1.5 Tenant Database Initialization
- **Description:** Automated setup of tenant-specific database with seed data.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Auto-create schema/tables on registration
  - [ ] Seed default chart of accounts based on industry
  - [ ] Seed default tax rates
  - [ ] Seed default units of measure
  - [ ] Seed default expense categories

---

### 4.2 System Administration

#### BR-2.1 Company Information
- **Description:** Centralized company details editable by Company Admin.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] CRUD operations on company legal name, registration number, tax ID
  - [ ] Multiple address support (billing, shipping, warehouse)
  - [ ] Contact person designation

#### BR-2.2 Branch Management
- **Description:** Manage multiple business branches under one tenant.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Create/edit/delete branches
  - [ ] Assign branch code and manager
  - [ ] Branch-specific address and contact
  - [ ] Deactivate branch without data loss

#### BR-2.3 Store Management
- **Description:** Configure retail/service outlets.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Create stores with name, code, location
  - [ ] Assign store manager
  - [ ] Configure store operating hours
  - [ ] Link store to branch and warehouse

#### BR-2.4 Warehouse Setup
- **Description:** Configure storage locations for inventory.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Create multiple warehouses
  - [ ] Define warehouse type (retail, bulk, cold storage, etc.)
  - [ ] Assign warehouse manager
  - [ ] Configure warehouse address and capacity

#### BR-2.5 Department Setup
- **Description:** Organizational structure configuration.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Create departments (Sales, Inventory, Accounting, etc.)
  - [ ] Assign department head
  - [ ] Department-based reporting filters

#### BR-2.6 Currency Setup
- **Description:** Multi-currency support for international operations.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Add currencies with exchange rates
  - [ ] Set base currency
  - [ ] Auto-update exchange rates (manual or API)
  - [ ] Transaction-level currency selection

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
  - [ ] Add multiple tax rates (VAT, GST, etc.)
  - [ ] Set default tax rate
  - [ ] Tax applicability by product category
  - [ ] Compound tax support

---

### 4.3 User Management

#### BR-3.1 User Account CRUD
- **Description:** Full lifecycle management of user accounts.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Create user with name, email, phone, role, branch/store assignment *(branch + department yes; dedicated user↔store membership deferred — `docs/ADR_005_USER_STORE_ASSIGNMENT.md`)*
  - [ ] Edit user details and assignments
  - [x] Soft delete (deactivate) user
  - [ ] Hard delete with data archival option *(deferred post-MVP; see `docs/ADR_003_USER_DELETE_POLICY.md`)*
  - [x] Activate/deactivate toggle
  - [x] Bulk user import via CSV

#### BR-3.2 Role Management
- **Description:** Predefined and custom role definitions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Predefined roles: Super Admin, Company Admin, Store Manager, Sales Officer, Inventory Officer, Accountant, Cashier
  - [ ] Each role has default permission set
  - [ ] Custom role creation capability
  - [ ] Role assignment to users

#### BR-3.3 Permission System
- **Description:** Granular access control across three dimensions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [x] **Module Permissions:** Grant/deny access to entire modules (Inventory, Sales, etc.)
  - [x] **Menu Permissions:** Control visibility of specific menu items and submenus *(Stage 1: menu item visibility = module `read`/`write`; see `docs/ADR_004_MENU_PERMISSIONS.md`)*
  - [x] **Record Permissions:** Control CRUD operations on individual records (own records, department records, all records)
  - [ ] Permission inheritance from role with user-level override capability

---

### 4.4 Executive Dashboard

#### BR-4.1 KPI Cards
- **Description:** At-a-glance business metrics.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Display: Total Sales, Total Purchases, Total Expenses, Total Customers, Total Suppliers, Total Products
  - [ ] Real-time or near-real-time updates (within 5 minutes)
  - [ ] Period comparison (Today vs Yesterday, This Month vs Last Month)
  - [ ] Click-through to detailed reports

#### BR-4.2 Inventory Alerts
- **Description:** Visual indicators for inventory issues.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Low stock products count with quick link
  - [ ] Out-of-stock products count
  - [ ] Expiring products (pharmacy/food) count

#### BR-4.3 Sales Visualization
- **Description:** Charts and trends for sales performance.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Recent sales list (last 10 transactions)
  - [ ] Top products by revenue and quantity
  - [ ] Daily revenue line chart (last 30 days)
  - [ ] Monthly revenue bar chart (last 12 months)

#### BR-4.4 Notifications Panel
- **Description:** Centralized notification stream.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Display unread notification count
  - [ ] Categorized notifications (stock, orders, payments, system)
  - [ ] Mark as read/unread
  - [ ] Notification history (last 90 days)

---

### 4.5 Inventory Management

#### BR-5.1 Product Catalog
- **Description:** Comprehensive product information management.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] **Categories:** Hierarchical category tree (parent/child), category code
  - [ ] **Brands:** Brand name, logo, description
  - [ ] **Units:** Unit of measure (piece, kg, liter, box, etc.) with conversion ratios
  - [ ] **Product Variants:** Size, color, flavor, dosage (pharmacy) variants with unique SKUs
  - [ ] **SKU:** Auto-generated or manual SKU assignment
  - [ ] **Barcode:** Support for EAN, UPC, Code 128; barcode generation for products without barcodes
  - [ ] **Images:** Multiple product images with primary image designation
  - [ ] **Product Details:** Name, description, cost price, selling price, tax rate, category, brand, unit, weight, dimensions
  - [ ] **Batch/Expiry:** Batch number, manufacturing date, expiry date (critical for pharmacy and food)

#### BR-5.2 Stock Operations
- **Description:** All inventory movement transactions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] **Stock In:** Record incoming stock with reference (purchase order, transfer, adjustment), quantity, batch, expiry, warehouse
  - [ ] **Stock Out:** Record outgoing stock with reference (sales, transfer, adjustment, damage), quantity, warehouse
  - [ ] **Stock Adjustment:** Correct stock discrepancies with reason (damage, theft, expiry, found, lost)
  - [ ] **Stock Transfer:** Move stock between warehouses with transfer note, approval workflow
  - [ ] **Opening Stock:** Initialize stock levels for new products or fiscal year start
  - [ ] **Stock Count:** Physical count reconciliation with system stock; variance report generation

#### BR-5.3 Stock Movement History
- **Description:** Complete audit trail of all inventory changes.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Log every stock change with timestamp, user, transaction type, quantity before/after
  - [ ] Filter by date range, product, warehouse, transaction type
  - [ ] Export to CSV/PDF
  - [ ] Immutable records (no deletion allowed)

#### BR-5.4 Warehouse Stock
- **Description:** Warehouse-specific inventory visibility.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] View stock levels per warehouse
  - [ ] Warehouse-specific reorder levels
  - [ ] Transfer stock between warehouses
  - [x] Warehouse-wise stock valuation (Stage 9 R2 — qty × `cost_price`)

#### BR-5.5 Low Stock Management
- **Description:** Proactive inventory replenishment alerts.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Set minimum stock level per product per warehouse
  - [ ] Set reorder level (trigger point for purchase)
  - [ ] Visual indicators on product list (green/yellow/red status)
  - [ ] Automated low-stock notifications to Inventory Officer and Store Manager
  - [ ] Generate purchase suggestions based on reorder levels

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

#### BR-7.5 Sales Return
- **Description:** Customer returns and refunds.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Create return referencing original invoice
  - [x] Record return reason and condition
  - [x] Restock or discard returned items
  - [x] Generate credit note
  - [x] Refund or adjust customer balance

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
  - [x] **Multiple Payment Methods:** Cash, Card, Digital Wallet, Credit (for registered customers); split tender
  - [x] **Receipt Printing:** Thermal printer support; digital receipt via email/SMS
  - [x] **Cash Drawer:** Auto-open on cash payment; manual open with reason

#### BR-8.2 Shift Management
- **Description:** Cashier accountability and reconciliation.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] **Shift Opening:** Record opening cash float, timestamp, cashier (Stage 12 A1 audit)
  - [x] **Shift Closing:** Record closing cash, card total, other payments
  - [x] **Cash Reconciliation:** System sales vs actual cash; variance reporting
  - [x] **Shift Report:** Sales summary, payment breakdown (`GET .../report`; Stage 12 C2)
  - [x] Prevent new transactions until shift is opened

---

### 4.9 Expense Management

#### BR-9.1 Expense Categories
- **Description:** Classify business expenditures.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Predefined categories (Rent, Utilities, Salaries, Transportation, Marketing, etc.)
  - [ ] Custom category creation
  - [ ] Category-based budget allocation

#### BR-9.2 Expense Entry
- **Description:** Record business expenses.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Expense date, category, amount, payment method, reference number
  - [ ] Payee name
  - [ ] Description/notes
  - [ ] Assign to branch/department
  - [ ] Link to chart of accounts for auto-posting

#### BR-9.3 Expense Approval
- **Description:** Control spending through approval workflows.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Configurable approval thresholds (e.g., >$100 requires manager approval)
  - [ ] Multi-level approval chain
  - [ ] Approval/rejection with comments
  - [ ] Email notification to approvers

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
  - [ ] Set frequency (daily, weekly, monthly, yearly)
  - [ ] Auto-generate expense entries
  - [ ] Notification before auto-generation
  - [ ] Skip or modify individual occurrences

---

### 4.10 Basic Accounting

#### BR-10.1 Chart of Accounts (COA)
- **Description:** Financial account structure.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Predefined COA based on industry template
  - [ ] Account types: Asset, Liability, Equity, Income, Expense
  - [ ] Account code hierarchy (e.g., 1000-Assets, 1100-Current Assets)
  - [ ] Add/edit accounts (non-system accounts)
  - [ ] Opening balance entry

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
  - [ ] Create cash accounts (petty cash, main cash)
  - [ ] Create bank accounts with bank name, account number, branch
  - [ ] Record deposits, withdrawals, transfers between accounts
  - [ ] Bank reconciliation (system balance vs statement)
  - [ ] Cheque management (issue, deposit, bounce tracking)

#### BR-10.4 Accounts Receivable (AR)
- **Description:** Track money owed by customers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Auto-generation from sales invoices
  - [ ] Customer aging report (0-30, 31-60, 61-90, 90+ days)
  - [ ] Payment recording against invoices
  - [ ] Partial payment support
  - [ ] Overdue notification automation

#### BR-10.5 Accounts Payable (AP)
- **Description:** Track money owed to suppliers.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Auto-generation from purchase invoices
  - [ ] Supplier aging report
  - [ ] Payment recording against bills
  - [ ] Partial payment support
  - [ ] Due date notifications

#### BR-10.6 Financial Reports
- **Description:** Standard financial statements.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] **Profit & Loss:** Revenue, COGS, gross profit, operating expenses, net profit; filterable by date range, branch
  - [ ] **Cash Flow:** Operating, investing, financing activities
  - [ ] **Trial Balance:** All accounts with debit/credit balances; validation that total debits = total credits
  - [ ] Export to PDF and Excel

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
  - [ ] Allocate payments to specific invoices or auto-allocate (oldest first)
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
  - [ ] Configure tax rates (percentage)
  - [ ] Set tax applicability (inclusive/exclusive pricing)
  - [x] Product-category-specific tax rules (Stage 10 T1 — category `tax_rate_id`, parent walk)
  - [ ] Compound tax (tax on tax) support

#### BR-12.2 Automatic Tax Calculation
- **Description:** Real-time tax computation on transactions.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Auto-calculate tax on sales invoices, purchase invoices, POS transactions
  - [ ] Display tax breakdown per line item and total
  - [ ] Handle tax exemptions (zero-rated, exempt products)
  - [ ] Reverse charge mechanism support

#### BR-12.3 Tax Reports
- **Description:** Compliance and filing support.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Output tax summary (tax collected on sales)
  - [ ] Input tax summary (tax paid on purchases)
  - [ ] Net tax payable/refundable
  - [ ] Tax report by period (monthly, quarterly, annually)
  - [x] Export in government filing format (manual GH GRA / NG FIRS / KE KRA workbooks; portal e-file deferred — Stage 10 T2)

---

### 4.13 Multi-Store Management

#### BR-13.1 Store Operations
- **Description:** Manage multiple retail/service locations.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Create stores with unique code, name, location
  - [ ] Assign store manager and staff
  - [ ] Store-specific inventory view
  - [ ] Store-specific sales reporting
  - [ ] Consolidated reporting across all stores

#### BR-13.2 Inter-Store Transfers
- **Description:** Move stock between stores.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Create transfer request with source store, destination store, products, quantities
  - [ ] Approval workflow (source store manager → destination store manager)
  - [ ] Track transfer status: Draft, Requested, In Transit, Received, Cancelled
  - [ ] Auto-update inventory at both stores on receipt confirmation
  - [ ] Transfer history and reporting

---

### 4.14 Reports & Analytics

#### BR-14.1 Sales Reports
- **Description:** Comprehensive sales analysis.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] **Daily Sales:** Date, invoice count, total revenue, tax, discounts, net sales
  - [ ] **Monthly Sales:** Monthly aggregation with trend comparison
  - [ ] **Product Sales:** Product-wise quantity and revenue; filter by date, store, category
  - [ ] **Customer Sales:** Top customers by revenue and frequency
  - [ ] **Salesperson Performance:** Sales by user/role

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
  - [ ] Expense summary by category and period
  - [ ] Budget vs actual comparison
  - [ ] Top expense categories

#### BR-14.5 Financial Reports
- **Description:** Business financial health.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Profit & Loss Statement
  - [ ] Cash Flow Statement
  - [ ] Balance Sheet (Assets = Liabilities + Equity)
  - [ ] All reports filterable by date range, branch, store
  - [ ] Comparative reports (current period vs previous period)

---

### 4.15 Notifications

#### BR-15.1 Notification Types
- **Description:** Automated alerts for business events.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] **Low Stock:** When product reaches reorder level
  - [ ] **New Orders:** When sales order is created
  - [ ] **Purchase Received:** When GRN is approved
  - [ ] **Payment Due:** When invoice/bill approaches due date
  - [ ] **Credit Limit Reached:** When customer exceeds credit threshold
  - [ ] **Shift Variance:** When cash reconciliation shows discrepancy
  - [ ] **Expense Approval Required:** When expense exceeds threshold

#### BR-15.2 Notification Channels
- **Description:** Multi-channel alert delivery.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] **Dashboard:** In-app notification bell with badge count
  - [ ] **Email:** SMTP integration; HTML email templates
  - [ ] **SMS:** SMS gateway integration (Twilio, regional providers)
  - [ ] User preference for channel per notification type

---

### 4.16 Backup & Recovery

#### BR-16.1 Manual Backup
- **Description:** On-demand data protection.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] One-click backup initiation by Super Admin
  - [x] Backup includes database, uploaded files, configurations (Stage 10 B1: `.ribbak` `media` map for tenant-scoped uploads)
  - [x] Download backup archive
  - [x] Backup encryption

#### BR-16.2 Scheduled Backup
- **Description:** Automated data protection.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Configurable schedule (daily, weekly)
  - [ ] Retention policy (keep last N backups)
  - [ ] Backup storage to S3-compatible storage
  - [ ] Failure alerts to admin

#### BR-16.3 Database Restore
- **Description:** Disaster recovery capability.
- **Priority:** High
- **Acceptance Criteria:**
  - [x] Restore from backup archive (guarded `confirm_text=RESTORE`; media rehydrate Stage 10 B1)
  - [ ] Restore to new tenant (for testing) — blocked by design for MVP (cross-tenant restore denied)
  - [x] Restore validation (checksum verification + integrity proof)
  - [ ] Point-in-time recovery (if WAL archiving enabled) — deferred post-MVP

---

### 4.17 Audit Logs

#### BR-17.1 Activity Tracking
- **Description:** Immutable record of system activities.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] **Login/Logout:** Timestamp, IP address, device, success/failure
  - [ ] **Product Changes:** Create, update, delete with before/after values
  - [ ] **Sales:** Invoice creation, modification, cancellation
  - [ ] **Purchases:** PO, GRN, invoice changes
  - [ ] **User Activity:** Permission changes, role assignments, deletions
  - [ ] **Financial:** Journal entry posting, account modifications

#### BR-17.2 Audit Log Management
- **Description:** Search and retention of audit data.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Filter by user, module, action type, date range
  - [ ] Export audit logs (CSV, PDF)
  - [ ] Tamper-proof storage (append-only, hashed)
  - [ ] Retention policy: minimum 7 years for financial records

---

### 4.18 API

#### BR-18.1 Authentication API
- **Description:** Secure API access.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] OAuth2 / JWT token generation
  - [ ] Token refresh endpoint
  - [x] API key support for service integrations (Stage 6 K1: `POST/GET/DELETE /api-keys`, `X-API-Key` auth)
  - [ ] Rate limiting per tenant

#### BR-18.2 Products API
- **Description:** Product data access and management.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] CRUD operations for products, categories, brands, units
  - [ ] Bulk import/export
  - [ ] Stock level queries
  - [ ] Barcode lookup

#### BR-18.3 Customers API
- **Description:** Customer data access.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] CRUD operations for customers and customer groups
  - [ ] Balance inquiry
  - [ ] Purchase history

#### BR-18.4 Sales API
- **Description:** Sales transaction API.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Create quotations, sales orders, invoices
  - [ ] Record payments
  - [ ] Sales return processing
  - [ ] POS transaction submission

#### BR-18.5 Purchases API
- **Description:** Procurement API.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Create purchase requests, orders, GRNs, invoices
  - [ ] Supplier management
  - [ ] Payment recording

#### BR-18.6 API Standards
- **Description:** Consistent API design.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] RESTful design with standard HTTP methods
  - [ ] JSON request/response format
  - [ ] Standard error response structure
  - [ ] Pagination for list endpoints
  - [ ] Versioning (/api/v1/)
  - [ ] OpenAPI/Swagger documentation auto-generated
  - [x] Webhook support for event subscriptions (Stage 6 W1: HMAC-signed outbound webhooks)

---

### 4.19 Authentication & Security

#### BR-19.1 Authentication
- **Description:** Secure user access.
- **Priority:** Critical
- **Acceptance Criteria:**
  - [ ] Email/password login with bcrypt hashing
  - [ ] Password complexity requirements (min 8 chars, mixed case, number, symbol)
  - [ ] Account lockout after 5 failed attempts (30-minute cooldown)
  - [ ] Email verification before first login
  - [ ] Password reset via secure token link (expires in 1 hour)

#### BR-19.2 Two-Factor Authentication (2FA)
- **Description:** Enhanced account security.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Optional TOTP-based 2FA (Google Authenticator, Authy)
  - [ ] QR code setup for 2FA
  - [ ] Backup recovery codes
  - [ ] Enforce 2FA for Super Admin and Company Admin roles

#### BR-19.3 Session Management
- **Description:** Control active user sessions.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] JWT token with configurable expiry (default: 24 hours)
  - [ ] Refresh token rotation
  - [ ] View active sessions per user
  - [ ] Remote session termination
  - [ ] Auto-logout on inactivity (configurable timeout)

---

### 4.20 System Settings

#### BR-20.1 Company Information
- **Description:** Global company settings.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Edit legal name, address, contact, tax ID
  - [ ] Upload company logo (used on invoices, receipts)

#### BR-20.2 Formatting
- **Description:** Regional display preferences.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Date format selection (DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD)
  - [ ] Number format (decimal separator, thousand separator)
  - [ ] Time format (12h / 24h)

#### BR-20.3 Email Settings
- **Description:** SMTP configuration for outbound emails.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] SMTP host, port, username, password
  - [ ] TLS/SSL encryption
  - [ ] Test email functionality
  - [ ] Default sender name and email

#### BR-20.4 Numbering & Templates
- **Description:** Document customization.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Configure invoice numbering prefix and series (e.g., INV-2026-0001)
  - [ ] Configure PO, GRN, quotation numbering
  - [ ] Receipt template selection and customization
  - [ ] Invoice template selection and customization
  - [ ] Header/footer customization with company branding

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
  - [ ] Highlight unusual sales drops or spikes
  - [ ] Flag expense anomalies
  - [ ] Suggest actions ("Restock Product Y — sales up 40% this week")
  - [ ] Weekly insight digest email

#### BR-21.3 Smart Inventory Intelligence
- **Description:** AI-powered inventory optimization.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Demand forecasting per product (7-day, 30-day, 90-day)
  - [ ] Optimal reorder quantity recommendations
  - [ ] Seasonality detection
  - [ ] Dead stock identification

#### BR-21.4 AI Low Stock Prediction
- **Description:** Predictive stockout prevention.
- **Priority:** High
- **Acceptance Criteria:**
  - [ ] Predict stockouts 7–14 days in advance
  - [ ] Consider sales velocity, seasonality, lead time
  - [ ] Confidence score on predictions
  - [ ] Auto-generate purchase suggestions

#### BR-21.5 AI Sales Analysis
- **Description:** Deep sales pattern recognition.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Sales trend forecasting
  - [ ] Customer segmentation (RFM analysis)
  - [ ] Product affinity analysis (frequently bought together)
  - [ ] Peak hour/day predictions

#### BR-21.6 AI Expense Analysis
- **Description:** Intelligent cost management.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] Expense categorization from receipt OCR (suggest + Stage 10 A1 confirmed apply)
  - [x] Budget variance alerts
  - [x] Unusual expense pattern detection
  - [x] Cost optimization suggestions

#### BR-21.7 AI Report Generator
- **Description:** Natural language to report.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Generate reports from text prompts ("Show me monthly sales for Q2")
  - [ ] Export generated reports
  - [ ] Save report templates for reuse

#### BR-21.8 AI Document Assistant
- **Description:** Intelligent document processing.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [x] OCR extraction from invoices, receipts (suggest + Stage 10 A1 confirmed apply to expense/PI draft; PO OCR deferred)
  - [x] Auto-match extracted data to system records (`/ai/documents/analyze`)
  - [x] Data validation and discrepancy flagging

#### BR-21.9 AI Customer Assistant (Basic)
- **Description:** Customer intelligence.
- **Priority:** Low
- **Acceptance Criteria:**
  - [ ] Customer churn risk scoring
  - [ ] Best customer identification
  - [ ] Personalized promotion suggestions

#### BR-21.10 AI Security Monitor (Basic)
- **Description:** Behavioral security analysis.
- **Priority:** Medium
- **Acceptance Criteria:**
  - [ ] Detect unusual login patterns (time, location, device)
  - [ ] Flag suspicious transaction patterns
  - [ ] Alert admins on potential fraud indicators

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
