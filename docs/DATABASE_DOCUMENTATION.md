# Database Documentation

## RIBDIGI BUSINESS ERP — MVP Database Design & Documentation

**Version:** 1.0.0  
**Classification:** Internal — Engineering & DBA  
**Last Updated:** August 2026  
**Applies To:** RIBDIGI ERP MVP (Version 1.0)  
**Database:** PostgreSQL 15  
**ORM:** SQLAlchemy 2.0

---

## Table of Contents

1. [Database Architecture](#1-database-architecture)
2. [Entity-Relationship Diagram (ERD)](#2-entity-relationship-diagram-erd)
3. [Tenant Isolation Strategy](#3-tenant-isolation-strategy)
4. [Core Tables by Module](#4-core-tables-by-module)
5. [SQLAlchemy 2.0 Models](#5-sqlalchemy-20-models)
6. [Relationships & Foreign Keys](#6-relationships--foreign-keys)
7. [Index Strategy](#7-index-strategy)
8. [Partition Strategy](#8-partition-strategy)
9. [Migration Strategy (Alembic)](#9-migration-strategy-alembic)
10. [Data Types & Conventions](#10-data-types--conventions)
11. [Appendix: Complete Schema Reference](#11-appendix-complete-schema-reference)

---

## 1. Database Architecture

### 1.1 Architecture Overview

RIBDIGI ERP uses **PostgreSQL 15** as the primary relational database with a **schema-per-tenant** isolation model. The architecture separates global metadata (tenant registry, system configuration) from tenant-specific business data.

```
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Cluster                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Database: ribdigi_erp                                 ││
│  │                                                         ││
│  │  ┌─────────────────────────────────────────────────┐   ││
│  │  │  Schema: public (Shared Catalog)                │   ││
│  │  │  • tenants                                      │   ││
│  │  │  • subscription_plans                           │   ││
│  │  │  • global_settings                              │   ││
│  │  │  • migration_history (alembic)                  │   ││
│  │  └─────────────────────────────────────────────────┘   ││
│  │                                                         ││
│  │  ┌─────────────────────────────────────────────────┐   ││
│  │  │  Schema: tenant_abc123 (Acme Retail)            │   ││
│  │  │  • users, roles, permissions                    │   ││
│  │  │  • products, categories, stock_movements        │   ││
│  │  │  • customers, invoices, sales_orders            │   ││
│  │  │  • suppliers, purchase_orders, grn              │   ││
│  │  │  • accounts, journal_entries                    │   ││
│  │  │  • expenses, notifications, audit_logs          │   ││
│  │  └─────────────────────────────────────────────────┘   ││
│  │                                                         ││
│  │  ┌─────────────────────────────────────────────────┐   ││
│  │  │  Schema: tenant_def456 (Beta Mart)              │   ││
│  │  │  • ... (isolated, identical structure)          │   ││
│  │  └─────────────────────────────────────────────────┘   ││
│  │                                                         ││
│  │  ┌─────────────────────────────────────────────────┐   ││
│  │  │  Schema: tenant_ghi789 (Gamma Pharmacy)         │   ││
│  │  │  • ... (isolated, identical structure)          │   ││
│  │  └─────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Connection Architecture

```
Application → SQLAlchemy Engine → PgBouncer (Connection Pool)
                                      │
                                      ▼
                              PostgreSQL Primary
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                   Read Replica 1            Read Replica 2
                   (Reports/Analytics)       (Failover)
```

**Connection Pooling (PgBouncer):**
- **Mode:** Transaction pooling
- **Max Client Connections:** 10,000
- **Default Pool Size:** 25 per database
- **Reserve Pool:** 5 connections for admin

---

## 2. Entity-Relationship Diagram (ERD)

### 2.1 Core Entity Relationships

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     Tenant      │──────▶│      User       │◀──────│      Role       │
│   (public)      │       │  (per-tenant)   │       │  (per-tenant)   │
└─────────────────┘       └────────┬────────┘       └─────────────────┘
                                   │
                                   │ owns
                                   ▼
                          ┌─────────────────┐
                          │   Permission    │
                          │  (per-tenant)   │
                          └─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         INVENTORY MODULE                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐  │
│  │   Category  │────▶│   Product   │◀────│       Brand         │  │
│  │             │     │             │     │                     │  │
│  └─────────────┘     └──────┬──────┘     └─────────────────────┘  │
│                             │                                       │
│                             │ has                                   │
│                             ▼                                       │
│                      ┌─────────────┐                                │
│                      │   Variant   │                                │
│                      │             │                                │
│                      └──────┬──────┘                                │
│                             │                                       │
│                             │ tracks                                │
│                             ▼                                       │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │  Warehouse  │◀────│  StockMovement  │────▶│   StockLevel    │   │
│  │             │     │  (in/out/adj/   │     │  (current qty   │   │
│  └─────────────┘     │   transfer)     │     │   per warehouse)│   │
│                      └─────────────────┘     └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         SALES MODULE                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐  │
│  │   Customer  │◀────│  Quotation  │────▶│    SalesOrder       │  │
│  │             │     │             │     │                     │  │
│  └─────────────┘     └─────────────┘     └──────────┬──────────┘  │
│                                                     │               │
│                                                     │ generates     │
│                                                     ▼               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐  │
│  │   Payment   │◀────│   Invoice   │────▶│    SalesReturn      │  │
│  │             │     │             │     │                     │  │
│  └─────────────┘     └──────┬──────┘     └─────────────────────┘  │
│                             │                                       │
│                             │ contains                              │
│                             ▼                                       │
│                      ┌─────────────┐                                │
│                      │ InvoiceItem │                                │
│                      │  (product   │                                │
│                      │   ref + qty)│                                │
│                      └─────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       PURCHASING MODULE                              │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │   Supplier  │◀────│  PurchaseOrder  │────▶│      GRN        │   │
│  │             │     │                 │     │  (Goods Received│   │
│  └─────────────┘     └────────┬────────┘     │    Note)        │   │
│                               │              └─────────────────┘   │
│                               │                                     │
│                               │ generates                           │
│                               ▼                                     │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │   Payment   │◀────│ PurchaseInvoice   │───▶│ PurchaseReturn  │   │
│  │             │     │                 │     │                 │   │
│  └─────────────┘     └─────────────────┘     └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       ACCOUNTING MODULE                              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────┐   │
│  │  ChartOfAccounts │────▶│  JournalEntry   │────▶│   Account   │   │
│  │  (hierarchical) │     │  (double-entry) │     │  (5 types)  │   │
│  └─────────────────┘     └─────────────────┘     └─────────────┘   │
│                                                                     │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────┐   │
│  │  CashAccount    │     │  BankAccount    │     │  TaxAccount │   │
│  └─────────────────┘     └─────────────────┘     └─────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Relationship Cardinality Summary

| Parent Entity | Child Entity | Cardinality | Relationship Type |
|---------------|--------------|-------------|-------------------|
| Tenant | User | 1:N | One tenant has many users |
| User | Role | N:1 | Many users share one role |
| Role | Permission | 1:N | One role has many permissions |
| Category | Product | 1:N | One category has many products |
| Brand | Product | 1:N | One brand has many products |
| Product | Variant | 1:N | One product has many variants |
| Product | StockMovement | 1:N | One product has many movements |
| Warehouse | StockMovement | 1:N | One warehouse has many movements |
| Customer | Invoice | 1:N | One customer has many invoices |
| Invoice | InvoiceItem | 1:N | One invoice has many items |
| Invoice | Payment | 1:N | One invoice has many payments |
| Supplier | PurchaseOrder | 1:N | One supplier has many POs |
| PurchaseOrder | GRN | 1:1 | One PO generates one GRN |
| Account | JournalEntry | 1:N | One account has many entries |
| Store | StoreInventory | 1:N | One store has many inventory records |

---

## 3. Tenant Isolation Strategy

### 3.1 Schema-Per-Tenant Implementation

Each tenant receives a dedicated PostgreSQL schema with identical table structure.

```sql
-- Global tenant registry (public schema)
CREATE TABLE public.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    industry VARCHAR(50) NOT NULL CHECK (industry IN ('retail', 'mart', 'pharmacy', 'restaurant', 'bakery', 'wholesale', 'manufacturing')),
    currency VARCHAR(3) DEFAULT 'USD',
    timezone VARCHAR(50) DEFAULT 'UTC',
    fiscal_year_start DATE DEFAULT '2026-01-01',
    subscription_plan VARCHAR(50) DEFAULT 'trial',
    status VARCHAR(20) DEFAULT 'trial' CHECK (status IN ('trial', 'active', 'suspended')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create tenant schema function
CREATE OR REPLACE FUNCTION create_tenant_schema(tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', 'tenant_' || tenant_id);
END;
$$ LANGUAGE plpgsql;
```

### 3.2 Row-Level Security (RLS) — Optional Layer

```sql
-- Enable RLS on a tenant table (defense in depth)
ALTER TABLE tenant_abc123.products ENABLE ROW LEVEL SECURITY;

-- Create policy that restricts rows based on tenant context
CREATE POLICY tenant_isolation_policy ON tenant_abc123.products
    USING (tenant_id = current_setting('app.current_tenant')::UUID);

-- Set tenant context per connection (called by application)
SET app.current_tenant = 'abc123';
```

### 3.3 SQLAlchemy Dynamic Schema Selection

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

class TenantSession(Session):
    def __init__(self, tenant_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant_id = tenant_id
        schema_name = f"tenant_{tenant_id}"
        self.execute(f"SET search_path TO {schema_name}, public")

# Engine with connection event
engine = create_engine("postgresql://user:pass@host/ribdigi_erp")
```

### 3.4 Tenant Provisioning Flow

```
1. Tenant registered in public.tenants
2. Schema tenant_{id} created via SQLAlchemy event
3. Alembic migrations applied to new schema
4. Default data seeded (roles, admin user, settings)
5. AI models initialized for tenant
6. Notification sent to tenant admin
```

---

## 4. Core Tables by Module

### 4.1 Identity & Access Module

```sql
-- Users (per-tenant schema)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    role_id UUID NOT NULL,
    branch_id UUID,
    store_id UUID,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    two_factor_secret VARCHAR(255),
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

-- Roles
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(50) NOT NULL CHECK (name IN ('super_admin', 'company_admin', 'store_manager', 'sales_officer', 'inventory_officer', 'accountant', 'cashier')),
    description TEXT,
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Permissions
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    module_permission VARCHAR(50) NOT NULL,
    menu_permission VARCHAR(50),
    record_permission VARCHAR(20) CHECK (record_permission IN ('read', 'write', 'delete', 'approve', 'export')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 Inventory Module

```sql
-- Categories
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES categories(id),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Brands
CREATE TABLE brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Units
CREATE TABLE units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(50) NOT NULL,
    symbol VARCHAR(10),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Products
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    barcode VARCHAR(100),
    category_id UUID REFERENCES categories(id),
    brand_id UUID REFERENCES brands(id),
    unit_id UUID REFERENCES units(id),
    description TEXT,
    track_inventory BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, sku)
);

-- Product Variants
CREATE TABLE product_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(100),
    sku VARCHAR(100),
    barcode VARCHAR(100),
    price DECIMAL(15,4) NOT NULL DEFAULT 0,
    cost DECIMAL(15,4) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, sku)
);

-- Product Images
CREATE TABLE product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES product_variants(id) ON DELETE CASCADE,
    image_url VARCHAR(500) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Warehouses
CREATE TABLE warehouses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20),
    location TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stock Levels (current snapshot)
CREATE TABLE stock_levels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    quantity DECIMAL(15,4) NOT NULL DEFAULT 0,
    minimum_stock DECIMAL(15,4) DEFAULT 0,
    reorder_level DECIMAL(15,4) DEFAULT 0,
    reorder_quantity DECIMAL(15,4) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, product_id, variant_id, warehouse_id)
);

-- Stock Movements (transactional history)
CREATE TABLE stock_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    movement_type VARCHAR(20) NOT NULL CHECK (movement_type IN ('stock_in', 'stock_out', 'adjustment', 'transfer_in', 'transfer_out')),
    quantity DECIMAL(15,4) NOT NULL,
    unit_cost DECIMAL(15,4),
    reference_type VARCHAR(50),
    reference_id UUID,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stock Transfers
CREATE TABLE stock_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    from_warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    to_warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    quantity DECIMAL(15,4) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_transit', 'received', 'cancelled')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stock Counts (physical inventory)
CREATE TABLE stock_counts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'in_progress', 'completed', 'cancelled')),
    counted_by UUID REFERENCES users(id),
    completed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stock_count_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    stock_count_id UUID NOT NULL REFERENCES stock_counts(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    expected_qty DECIMAL(15,4) NOT NULL,
    actual_qty DECIMAL(15,4),
    difference DECIMAL(15,4),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.3 Purchasing Module

```sql
-- Suppliers
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    tax_id VARCHAR(50),
    payment_terms VARCHAR(50),
    opening_balance DECIMAL(15,4) DEFAULT 0,
    current_balance DECIMAL(15,4) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Purchase Requests
CREATE TABLE purchase_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    request_number VARCHAR(50) NOT NULL,
    request_date DATE NOT NULL,
    required_date DATE,
    warehouse_id UUID REFERENCES warehouses(id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'converted')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, request_number)
);

CREATE TABLE purchase_request_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    purchase_request_id UUID NOT NULL REFERENCES purchase_requests(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Purchase Orders
CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    po_number VARCHAR(50) NOT NULL,
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    order_date DATE NOT NULL,
    expected_delivery DATE,
    warehouse_id UUID REFERENCES warehouses(id),
    reference VARCHAR(100),
    subtotal DECIMAL(15,4) DEFAULT 0,
    tax_amount DECIMAL(15,4) DEFAULT 0,
    discount_amount DECIMAL(15,4) DEFAULT 0,
    total_amount DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'sent', 'partially_received', 'received', 'cancelled')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, po_number)
);

CREATE TABLE purchase_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL,
    received_qty DECIMAL(15,4) DEFAULT 0,
    unit_price DECIMAL(15,4) NOT NULL,
    tax_rate DECIMAL(5,2) DEFAULT 0,
    discount DECIMAL(15,4) DEFAULT 0,
    total DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Goods Received Notes (GRN)
CREATE TABLE grns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    grn_number VARCHAR(50) NOT NULL,
    purchase_order_id UUID REFERENCES purchase_orders(id),
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    received_date DATE NOT NULL,
    warehouse_id UUID REFERENCES warehouses(id),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, grn_number)
);

CREATE TABLE grn_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    grn_id UUID NOT NULL REFERENCES grns(id) ON DELETE CASCADE,
    po_item_id UUID REFERENCES purchase_order_items(id),
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    received_qty DECIMAL(15,4) NOT NULL,
    accepted_qty DECIMAL(15,4) NOT NULL,
    rejected_qty DECIMAL(15,4) DEFAULT 0,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Purchase Invoices
CREATE TABLE purchase_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    invoice_number VARCHAR(50) NOT NULL,
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    purchase_order_id UUID REFERENCES purchase_orders(id),
    grn_id UUID REFERENCES grns(id),
    invoice_date DATE NOT NULL,
    due_date DATE,
    subtotal DECIMAL(15,4) DEFAULT 0,
    tax_amount DECIMAL(15,4) DEFAULT 0,
    total_amount DECIMAL(15,4) DEFAULT 0,
    paid_amount DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'unpaid' CHECK (status IN ('unpaid', 'partial', 'paid', 'overdue')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, invoice_number)
);

-- Purchase Returns
CREATE TABLE purchase_returns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    return_number VARCHAR(50) NOT NULL,
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    purchase_invoice_id UUID REFERENCES purchase_invoices(id),
    return_date DATE NOT NULL,
    total_amount DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'completed', 'cancelled')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, return_number)
);
```

### 4.4 Sales Module

```sql
-- Customers
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    customer_group VARCHAR(50) DEFAULT 'retail',
    credit_limit DECIMAL(15,4) DEFAULT 0,
    current_balance DECIMAL(15,4) DEFAULT 0,
    opening_balance DECIMAL(15,4) DEFAULT 0,
    tax_id VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Customer Groups
CREATE TABLE customer_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(50) NOT NULL,
    discount_percent DECIMAL(5,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Quotations
CREATE TABLE quotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    quote_number VARCHAR(50) NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    quote_date DATE NOT NULL,
    expiry_date DATE,
    subtotal DECIMAL(15,4) DEFAULT 0,
    tax_amount DECIMAL(15,4) DEFAULT 0,
    discount_amount DECIMAL(15,4) DEFAULT 0,
    total_amount DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'sent', 'accepted', 'expired', 'converted')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, quote_number)
);

CREATE TABLE quotation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    quotation_id UUID NOT NULL REFERENCES quotations(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL,
    unit_price DECIMAL(15,4) NOT NULL,
    tax_rate DECIMAL(5,2) DEFAULT 0,
    discount DECIMAL(15,4) DEFAULT 0,
    total DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sales Orders
CREATE TABLE sales_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    order_number VARCHAR(50) NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    quotation_id UUID REFERENCES quotations(id),
    order_date DATE NOT NULL,
    expected_delivery DATE,
    subtotal DECIMAL(15,4) DEFAULT 0,
    tax_amount DECIMAL(15,4) DEFAULT 0,
    discount_amount DECIMAL(15,4) DEFAULT 0,
    total_amount DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, order_number)
);

CREATE TABLE sales_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    sales_order_id UUID NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL,
    unit_price DECIMAL(15,4) NOT NULL,
    tax_rate DECIMAL(5,2) DEFAULT 0,
    discount DECIMAL(15,4) DEFAULT 0,
    total DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Invoices
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    invoice_number VARCHAR(50) NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    sales_order_id UUID REFERENCES sales_orders(id),
    invoice_date DATE NOT NULL,
    due_date DATE,
    subtotal DECIMAL(15,4) DEFAULT 0,
    tax_amount DECIMAL(15,4) DEFAULT 0,
    discount_amount DECIMAL(15,4) DEFAULT 0,
    total_amount DECIMAL(15,4) DEFAULT 0,
    paid_amount DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'unpaid' CHECK (status IN ('unpaid', 'partial', 'paid', 'overdue', 'cancelled')),
    payment_method VARCHAR(50),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, invoice_number)
);

CREATE TABLE invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL,
    unit_price DECIMAL(15,4) NOT NULL,
    tax_rate DECIMAL(5,2) DEFAULT 0,
    discount DECIMAL(15,4) DEFAULT 0,
    total DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sales Returns
CREATE TABLE sales_returns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    return_number VARCHAR(50) NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    invoice_id UUID NOT NULL REFERENCES invoices(id),
    return_date DATE NOT NULL,
    total_refund DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'completed', 'cancelled')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, return_number)
);

CREATE TABLE sales_return_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    sales_return_id UUID NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
    invoice_item_id UUID NOT NULL REFERENCES invoice_items(id),
    return_qty DECIMAL(15,4) NOT NULL,
    refund_amount DECIMAL(15,4) NOT NULL,
    reason VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.5 POS Module

```sql
-- POS Sessions (Shifts)
CREATE TABLE pos_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    store_id UUID REFERENCES stores(id),
    user_id UUID NOT NULL REFERENCES users(id),
    session_number VARCHAR(50) NOT NULL,
    opening_cash DECIMAL(15,4) NOT NULL,
    closing_cash DECIMAL(15,4),
    actual_cash DECIMAL(15,4),
    cash_difference DECIMAL(15,4),
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed', 'balanced')),
    notes TEXT,
    UNIQUE(tenant_id, session_number)
);

-- POS Sales
CREATE TABLE pos_sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    session_id UUID NOT NULL REFERENCES pos_sessions(id),
    customer_id UUID REFERENCES customers(id),
    sale_number VARCHAR(50) NOT NULL,
    subtotal DECIMAL(15,4) DEFAULT 0,
    tax_amount DECIMAL(15,4) DEFAULT 0,
    discount_total DECIMAL(15,4) DEFAULT 0,
    grand_total DECIMAL(15,4) DEFAULT 0,
    receipt_url VARCHAR(500),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, sale_number)
);

CREATE TABLE pos_sale_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pos_sale_id UUID NOT NULL REFERENCES pos_sales(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL,
    unit_price DECIMAL(15,4) NOT NULL,
    discount DECIMAL(15,4) DEFAULT 0,
    total DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pos_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pos_sale_id UUID NOT NULL REFERENCES pos_sales(id) ON DELETE CASCADE,
    payment_method VARCHAR(50) NOT NULL,
    amount DECIMAL(15,4) NOT NULL,
    reference VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.6 Expense Module

```sql
-- Expense Categories
CREATE TABLE expense_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Expenses
CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    expense_number VARCHAR(50) NOT NULL,
    category_id UUID NOT NULL REFERENCES expense_categories(id),
    amount DECIMAL(15,4) NOT NULL,
    expense_date DATE NOT NULL,
    payment_method VARCHAR(50),
    reference VARCHAR(100),
    description TEXT,
    branch_id UUID,
    attachments JSONB,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'paid')),
    is_recurring BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, expense_number)
);

-- Recurring Expenses
CREATE TABLE recurring_expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    category_id UUID NOT NULL REFERENCES expense_categories(id),
    amount DECIMAL(15,4) NOT NULL,
    frequency VARCHAR(20) NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')),
    start_date DATE NOT NULL,
    end_date DATE,
    next_run_date DATE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.7 Accounting Module

```sql
-- Chart of Accounts
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('asset', 'liability', 'equity', 'income', 'expense')),
    parent_id UUID REFERENCES accounts(id),
    is_bank_account BOOLEAN DEFAULT FALSE,
    is_cash_account BOOLEAN DEFAULT FALSE,
    opening_balance DECIMAL(15,4) DEFAULT 0,
    current_balance DECIMAL(15,4) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, account_code)
);

-- Journal Entries
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entry_number VARCHAR(50) NOT NULL,
    entry_date DATE NOT NULL,  -- implemented as TIMESTAMPTZ/DateTime in ORM
    reference VARCHAR(100),
    description TEXT,
    source_type VARCHAR(50),   -- e.g. manual, opening_balance, grn, expense
    source_id UUID,
    total_debit DECIMAL(15,4) NOT NULL,
    total_credit DECIMAL(15,4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'posted',  -- posted | unposted
    -- is_balanced is computed in API serialize (balanced flag); not all DBs keep generated column
    attachment_url TEXT,  -- Stage 9 J1: storage key or external URL for supporting document
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, entry_number)
);

CREATE TABLE journal_entry_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts(id),
    debit DECIMAL(15,4) DEFAULT 0,
    credit DECIMAL(15,4) DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT check_debit_credit CHECK (debit > 0 OR credit > 0)
);
```

### 4.8 Tax Module

```sql
-- Tax Rates
CREATE TABLE tax_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    rate DECIMAL(5,2) NOT NULL,
    tax_type VARCHAR(20) DEFAULT 'vat' CHECK (tax_type IN ('vat', 'gst', 'sales_tax', 'custom')),
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.9 Multi-Store Module

```sql
-- Stores
CREATE TABLE stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20),
    address TEXT,
    phone VARCHAR(20),
    manager_id UUID REFERENCES users(id),
    warehouse_id UUID REFERENCES warehouses(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Store Inventory
CREATE TABLE store_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    store_id UUID NOT NULL REFERENCES stores(id),
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, store_id, product_id, variant_id)
);

-- Inter-Store Transfers
CREATE TABLE store_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    transfer_number VARCHAR(50) NOT NULL,
    from_store_id UUID NOT NULL REFERENCES stores(id),
    to_store_id UUID NOT NULL REFERENCES stores(id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_transit', 'received', 'cancelled')),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, transfer_number)
);

CREATE TABLE store_transfer_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    store_transfer_id UUID NOT NULL REFERENCES store_transfers(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    variant_id UUID REFERENCES product_variants(id),
    quantity DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.10 Notification & Audit Module

```sql
-- Notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id),
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    data JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    channel VARCHAR(20) DEFAULT 'dashboard' CHECK (channel IN ('dashboard', 'email', 'sms')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    event_type VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    action VARCHAR(20) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    outcome VARCHAR(20) DEFAULT 'success',
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notification Preferences
CREATE TABLE notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    notification_type VARCHAR(50) NOT NULL,
    dashboard_enabled BOOLEAN DEFAULT TRUE,
    email_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, user_id, notification_type)
);
```

### 4.11 Credit Management Module

```sql
-- Customer Payments
CREATE TABLE customer_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    payment_number VARCHAR(50) NOT NULL,
    amount DECIMAL(15,4) NOT NULL,
    payment_method VARCHAR(50),
    payment_date DATE NOT NULL,
    reference VARCHAR(100),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, payment_number)
);

-- Payment Allocations (link payments to invoices)
CREATE TABLE payment_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    customer_payment_id UUID NOT NULL REFERENCES customer_payments(id),
    invoice_id UUID NOT NULL REFERENCES invoices(id),
    amount DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Supplier Payments
CREATE TABLE supplier_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    payment_number VARCHAR(50) NOT NULL,
    amount DECIMAL(15,4) NOT NULL,
    payment_method VARCHAR(50),
    payment_date DATE NOT NULL,
    reference VARCHAR(100),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, payment_number)
);
```

---

## 5. SQLAlchemy 2.0 Models

### 5.1 Base Model & Mixins

```python
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import uuid

class Base(DeclarativeBase):
    pass

class TenantMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        nullable=False, 
        index=True
    )

class TimestampMixin:
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )

class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 5.2 Product Model Example

```python
from sqlalchemy import ForeignKey, String, Text, Boolean, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional

class Product(Base, TenantMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        {"schema": "tenant_dynamic"},  # Set dynamically per tenant
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("categories.id"), 
        nullable=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("brands.id"), 
        nullable=True
    )
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("units.id"), 
        nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    track_inventory: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    brand: Mapped[Optional["Brand"]] = relationship(back_populates="products")
    variants: Mapped[List["ProductVariant"]] = relationship(
        back_populates="product", 
        cascade="all, delete-orphan"
    )
    stock_levels: Mapped[List["StockLevel"]] = relationship(
        back_populates="product", 
        cascade="all, delete-orphan"
    )
```

### 5.3 Invoice Model Example

```python
class Invoice(Base, TenantMixin, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id"), 
        nullable=False
    )
    sales_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sales_orders.id"), 
        nullable=True
    )
    invoice_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    status: Mapped[str] = mapped_column(String(20), default="unpaid")
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), 
        nullable=True
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="invoices")
    items: Mapped[List["InvoiceItem"]] = relationship(
        back_populates="invoice", 
        cascade="all, delete-orphan"
    )
    payments: Mapped[List["PaymentAllocation"]] = relationship(
        back_populates="invoice"
    )
```

### 5.4 Dynamic Schema Configuration

```python
from sqlalchemy import event
from sqlalchemy.orm import Session

def set_tenant_schema(session: Session, tenant_id: str):
    schema_name = f"tenant_{tenant_id}"
    session.execute(f"SET search_path TO {schema_name}, public")

class ProductRepository:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        set_tenant_schema(db, tenant_id)

    def get_by_sku(self, sku: str):
        return self.db.query(Product).filter(Product.sku == sku).first()
```

---

## 6. Relationships & Foreign Keys

### 6.1 Foreign Key Constraints Summary

| Child Table | Parent Table | Column | On Delete | On Update |
|-------------|--------------|--------|-----------|-----------|
| users | roles | role_id | RESTRICT | CASCADE |
| permissions | roles | role_id | CASCADE | CASCADE |
| products | categories | category_id | SET NULL | CASCADE |
| products | brands | brand_id | SET NULL | CASCADE |
| products | units | unit_id | SET NULL | CASCADE |
| product_variants | products | product_id | CASCADE | CASCADE |
| product_images | products | product_id | CASCADE | CASCADE |
| stock_levels | products | product_id | CASCADE | CASCADE |
| stock_levels | warehouses | warehouse_id | CASCADE | CASCADE |
| stock_movements | products | product_id | RESTRICT | CASCADE |
| stock_movements | warehouses | warehouse_id | RESTRICT | CASCADE |
| stock_transfers | products | product_id | RESTRICT | CASCADE |
| stock_transfers | warehouses | from_warehouse_id | RESTRICT | CASCADE |
| stock_transfers | warehouses | to_warehouse_id | RESTRICT | CASCADE |
| purchase_requests | warehouses | warehouse_id | SET NULL | CASCADE |
| purchase_request_items | purchase_requests | purchase_request_id | CASCADE | CASCADE |
| purchase_orders | suppliers | supplier_id | RESTRICT | CASCADE |
| purchase_order_items | purchase_orders | purchase_order_id | CASCADE | CASCADE |
| grns | purchase_orders | purchase_order_id | SET NULL | CASCADE |
| grns | suppliers | supplier_id | RESTRICT | CASCADE |
| grn_items | grns | grn_id | CASCADE | CASCADE |
| purchase_invoices | suppliers | supplier_id | RESTRICT | CASCADE |
| purchase_invoices | purchase_orders | purchase_order_id | SET NULL | CASCADE |
| purchase_returns | suppliers | supplier_id | RESTRICT | CASCADE |
| purchase_returns | purchase_invoices | purchase_invoice_id | SET NULL | CASCADE |
| quotations | customers | customer_id | RESTRICT | CASCADE |
| quotation_items | quotations | quotation_id | CASCADE | CASCADE |
| sales_orders | customers | customer_id | RESTRICT | CASCADE |
| sales_orders | quotations | quotation_id | SET NULL | CASCADE |
| sales_order_items | sales_orders | sales_order_id | CASCADE | CASCADE |
| invoices | customers | customer_id | RESTRICT | CASCADE |
| invoices | sales_orders | sales_order_id | SET NULL | CASCADE |
| invoice_items | invoices | invoice_id | CASCADE | CASCADE |
| sales_returns | customers | customer_id | RESTRICT | CASCADE |
| sales_returns | invoices | invoice_id | RESTRICT | CASCADE |
| pos_sessions | stores | store_id | SET NULL | CASCADE |
| pos_sessions | users | user_id | RESTRICT | CASCADE |
| pos_sales | pos_sessions | session_id | RESTRICT | CASCADE |
| pos_sales | customers | customer_id | SET NULL | CASCADE |
| pos_sale_items | pos_sales | pos_sale_id | CASCADE | CASCADE |
| expenses | expense_categories | category_id | RESTRICT | CASCADE |
| recurring_expenses | expense_categories | category_id | RESTRICT | CASCADE |
| journal_entry_lines | journal_entries | journal_entry_id | CASCADE | CASCADE |
| journal_entry_lines | accounts | account_id | RESTRICT | CASCADE |
| store_inventory | stores | store_id | CASCADE | CASCADE |
| store_inventory | products | product_id | CASCADE | CASCADE |
| store_transfers | stores | from_store_id | RESTRICT | CASCADE |
| store_transfers | stores | to_store_id | RESTRICT | CASCADE |
| notifications | users | user_id | CASCADE | CASCADE |
| customer_payments | customers | customer_id | RESTRICT | CASCADE |
| payment_allocations | customer_payments | customer_payment_id | CASCADE | CASCADE |
| payment_allocations | invoices | invoice_id | RESTRICT | CASCADE |
| supplier_payments | suppliers | supplier_id | RESTRICT | CASCADE |

### 6.2 Self-Referencing Relationships

| Table | Column | Purpose |
|-------|--------|---------|
| categories | parent_id | Hierarchical category tree |
| accounts | parent_id | Chart of accounts hierarchy |
| products | category_id, brand_id, unit_id | Product classification |

---

## 7. Index Strategy

### 7.1 Primary Indexes

All primary keys use UUID with gen_random_uuid() default, indexed automatically by PostgreSQL.

### 7.2 Performance Indexes

```sql
-- Tenant isolation (on every tenant table)
CREATE INDEX idx_products_tenant ON products(tenant_id);
CREATE INDEX idx_invoices_tenant ON invoices(tenant_id);
CREATE INDEX idx_stock_movements_tenant ON stock_movements(tenant_id);

-- Lookup indexes
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_barcode ON products(barcode);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_active ON products(is_active) WHERE is_active = TRUE;

-- Invoice queries
CREATE INDEX idx_invoices_customer ON invoices(customer_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_date ON invoices(invoice_date);
CREATE INDEX idx_invoices_due_date ON invoices(due_date) WHERE status IN ('unpaid', 'partial');

-- Stock movement queries
CREATE INDEX idx_stock_movements_product ON stock_movements(product_id);
CREATE INDEX idx_stock_movements_warehouse ON stock_movements(warehouse_id);
CREATE INDEX idx_stock_movements_type ON stock_movements(movement_type);
CREATE INDEX idx_stock_movements_created ON stock_movements(created_at);

-- Sales & POS queries
CREATE INDEX idx_pos_sales_session ON pos_sales(session_id);
CREATE INDEX idx_pos_sales_created ON pos_sales(created_at);
CREATE INDEX idx_sales_orders_customer ON sales_orders(customer_id);
CREATE INDEX idx_sales_orders_status ON sales_orders(status);

-- Audit & notification queries
CREATE INDEX idx_audit_logs_tenant_event ON audit_logs(tenant_id, event_type);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;

-- Full-text search (product names)
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);

-- Composite indexes for common query patterns
CREATE INDEX idx_stock_levels_product_warehouse ON stock_levels(product_id, variant_id, warehouse_id);
CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id, product_id);
CREATE INDEX idx_purchase_order_items_po ON purchase_order_items(purchase_order_id, product_id);
```

### 7.3 Partial Indexes

```sql
-- Only index active records for common lookups
CREATE INDEX idx_products_active_name ON products(name) WHERE is_active = TRUE;
CREATE INDEX idx_customers_active ON customers(name) WHERE is_active = TRUE;
CREATE INDEX idx_suppliers_active ON suppliers(name) WHERE is_active = TRUE;

-- Overdue invoices (critical for credit management)
CREATE INDEX idx_invoices_overdue ON invoices(due_date) 
    WHERE status IN ('unpaid', 'partial') AND due_date < CURRENT_DATE;

-- Low stock alerts
CREATE INDEX idx_stock_levels_low ON stock_levels(quantity, minimum_stock) 
    WHERE quantity <= minimum_stock;
```

### 7.4 Index Maintenance

```sql
-- Reindex during low-traffic hours (weekly)
REINDEX INDEX CONCURRENTLY idx_products_sku;
REINDEX INDEX CONCURRENTLY idx_invoices_customer;

-- Analyze tables for query planner
ANALYZE products;
ANALYZE invoices;
ANALYZE stock_movements;
```

---

## 8. Partition Strategy

### 8.1 Partitioned Tables

For MVP, the following tables are candidates for future partitioning as data volume grows:

| Table | Partition Key | Strategy | Rationale |
|-------|---------------|----------|-----------|
| stock_movements | created_at | Monthly RANGE | High write volume; historical queries by month |
| audit_logs | created_at | Monthly RANGE | Very high write volume; retention by month |
| pos_sales | created_at | Monthly RANGE | High transaction volume; reporting by month |
| journal_entry_lines | created_at | Monthly RANGE | Financial audit trails; fiscal year queries |
| notifications | created_at | Monthly RANGE | High volume; cleanup of old notifications |

### 8.2 Partition Implementation (Example)

```sql
-- Create partitioned stock_movements table (future migration)
CREATE TABLE stock_movements_partitioned (
    id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    product_id UUID NOT NULL,
    variant_id UUID,
    warehouse_id UUID NOT NULL,
    movement_type VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    unit_cost DECIMAL(15,4),
    reference_type VARCHAR(50),
    reference_id UUID,
    notes TEXT,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE stock_movements_2026_01 PARTITION OF stock_movements_partitioned
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE stock_movements_2026_02 PARTITION OF stock_movements_partitioned
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
-- auto-create via cron job

-- Attach default partition for overflow
CREATE TABLE stock_movements_default PARTITION OF stock_movements_partitioned DEFAULT;
```

### 8.3 Partition Management

```sql
-- Automated partition creation (run monthly via cron/Celery beat)
CREATE OR REPLACE FUNCTION create_monthly_partition(
    table_name TEXT,
    year INT,
    month INT
) RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    partition_name := table_name || '_' || year || '_' || LPAD(month::TEXT, 2, '0');
    start_date := make_date(year, month, 1);
    end_date := start_date + INTERVAL '1 month';

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
        partition_name, table_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;
```

---

## 9. Migration Strategy (Alembic)

### 9.1 Alembic Configuration

```python
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql://user:pass@localhost/ribdigi_erp

[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -l 88 REVISION_SCRIPT_FILENAME
```

```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import create_engine, pool, event
from alembic import context
from app.models import Base

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def get_tenant_schemas(connection):
    result = connection.execute("SELECT id FROM public.tenants WHERE status != 'deleted'")
    return [f"tenant_{row[0]}" for row in result]

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(config.get_main_option("sqlalchemy.url"), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # Migrate public schema
        context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True)
        with context.begin_transaction():
            context.execute("SET search_path TO public")
            context.run_migrations()

        # Migrate each tenant schema
        tenant_schemas = get_tenant_schemas(connection)
        for schema in tenant_schemas:
            context.configure(
                connection=connection, 
                target_metadata=target_metadata,
                version_table_schema=schema,
                include_schemas=True
            )
            with context.begin_transaction():
                context.execute(f"SET search_path TO {schema}")
                context.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 9.2 Migration Best Practices

1. Always generate migrations from models:
   ```bash
   alembic revision --autogenerate -m "add_pos_sessions"
   ```

2. Review autogenerated migrations before committing:
   - Verify column types and constraints
   - Check foreign key references
   - Ensure indexes are created explicitly

3. Backward-compatible changes first:
   - Migration 1: Add new column (nullable)
   - Migration 2: Backfill data
   - Migration 3: Add NOT NULL constraint

4. Never modify existing migrations after deployment to staging/production

5. Test migrations on a copy of production data before deployment

### 9.3 Multi-Tenant Migration Workflow

```bash
# 1. Generate migration from model changes
alembic revision --autogenerate -m "add_credit_limit_to_customers"

# 2. Review generated script
# alembic/versions/20260807_add_credit_limit_to_customers.py

# 3. Apply to local development
alembic upgrade head

# 4. Apply to staging (all tenant schemas)
alembic upgrade head --env staging

# 5. Apply to production (rolling deployment)
# - Run during maintenance window
# - Backup database before migration
# - Monitor migration duration
alembic upgrade head --env production

# 6. Rollback if needed
alembic downgrade -1
```

### 9.4 Migration Template

```python
# add_credit_limit_to_customers
# Revision ID: abc123
# Revises: prev456
# Create Date: 2026-08-07

from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = 'prev456'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add column as nullable first
    op.add_column('customers', sa.Column('credit_limit', sa.Numeric(15, 4), nullable=True))

    # Backfill existing rows
    op.execute("UPDATE customers SET credit_limit = 0 WHERE credit_limit IS NULL")

    # Add constraint
    op.alter_column('customers', 'credit_limit', nullable=False)

    # Add index
    op.create_index('idx_customers_credit_limit', 'customers', ['credit_limit'])

def downgrade() -> None:
    op.drop_index('idx_customers_credit_limit', table_name='customers')
    op.drop_column('customers', 'credit_limit')
```

---

## 10. Data Types & Conventions

### 10.1 Standard Data Types

| Purpose | PostgreSQL Type | SQLAlchemy Type | Notes |
|---------|----------------|-----------------|-------|
| Primary Key | UUID | UUID(as_uuid=True) | gen_random_uuid() default |
| Tenant ID | UUID | UUID(as_uuid=True) | Part of every tenant table |
| Names | VARCHAR(255) | String(255) | UTF-8 support |
| Codes/SKUs | VARCHAR(100) | String(100) | Unique per tenant |
| Descriptions | TEXT | Text | Unlimited length |
| Monetary | DECIMAL(15,4) | Numeric(15, 4) | 4 decimal places for precision |
| Percentages | DECIMAL(5,2) | Numeric(5, 2) | e.g., 10.50% |
| Quantities | DECIMAL(15,4) | Numeric(15, 4) | Supports fractional units |
| Status | VARCHAR(20) | String(20) | CHECK constraint for enum values |
| Dates | DATE | Date | Business dates |
| Timestamps | TIMESTAMPTZ | DateTime(timezone=True) | UTC with timezone |
| JSON | JSONB | JSONB | Flexible metadata, notifications |
| Boolean | BOOLEAN | Boolean | Flags, status indicators |
| IP Address | INET | INET | Audit logs |

### 10.2 Naming Conventions

| Object | Convention | Example |
|--------|------------|---------|
| Tables | snake_case, plural | stock_movements, purchase_orders |
| Columns | snake_case | created_at, total_amount |
| Primary Keys | id (UUID) | id UUID PRIMARY KEY |
| Foreign Keys | {table}_id | customer_id, warehouse_id |
| Indexes | idx_{table}_{column(s)} | idx_invoices_customer_date |
| Constraints | chk_{table}_{rule} | chk_invoices_status |
| Sequences | {table}_{column}_seq | invoices_id_seq |

### 10.3 Column Conventions

Every tenant table includes:
- id UUID PRIMARY KEY DEFAULT gen_random_uuid()
- tenant_id UUID NOT NULL (isolation)
- created_at TIMESTAMPTZ DEFAULT NOW()
- updated_at TIMESTAMPTZ DEFAULT NOW()

Optional audit columns:
- created_by UUID REFERENCES users(id)
- updated_by UUID REFERENCES users(id)
- deleted_at TIMESTAMPTZ (soft delete)
- is_deleted BOOLEAN DEFAULT FALSE

---

## 11. Appendix: Complete Schema Reference

### 11.1 Table Count by Module

| Module | Tables | Key Tables |
|--------|--------|------------|
| Identity & Access | 3 | users, roles, permissions |
| Inventory | 10 | products, variants, stock_levels, stock_movements, stock_transfers, stock_counts |
| Purchasing | 10 | suppliers, purchase_requests, purchase_orders, grns, purchase_invoices, purchase_returns |
| Sales | 10 | customers, quotations, sales_orders, invoices, sales_returns |
| POS | 4 | pos_sessions, pos_sales, pos_sale_items, pos_payments |
| Expense | 3 | expense_categories, expenses, recurring_expenses |
| Accounting | 3 | accounts, journal_entries, journal_entry_lines |
| Tax | 1 | tax_rates |
| Multi-Store | 4 | stores, store_inventory, store_transfers, store_transfer_items |
| Credit | 3 | customer_payments, payment_allocations, supplier_payments |
| Notification | 3 | notifications, notification_preferences, audit_logs |
| **Total** | **54** | — |

### 11.2 Schema Size Estimates

| Object Type | Per Tenant | 1000 Tenants |
|-------------|------------|--------------|
| Tables | 54 | 54,000 |
| Indexes | ~120 | 120,000 |
| Constraints | ~80 | 80,000 |
| Estimated Storage (empty) | 50 MB | 50 GB |
| Estimated Storage (populated) | 500 MB – 5 GB | 500 GB – 5 TB |

### 11.3 Database Maintenance Schedule

| Task | Frequency | Tool | Impact |
|------|-----------|------|--------|
| VACUUM ANALYZE | Daily (auto) | PostgreSQL autovacuum | Low |
| REINDEX CONCURRENTLY | Weekly | pg_reindex | Low |
| Backup (Full) | Daily | pg_basebackup | Low |
| Backup (Incremental/WAL) | Continuous | WAL archiving | None |
| Partition Creation | Monthly | Cron / Celery | None |
| Old Partition Archival | Quarterly | pg_dump + S3 | Low |
| Statistics Update | Daily | ANALYZE | Low |
| Connection Pool Tuning | Monthly | PgBouncer config | Low |

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Database:** PostgreSQL 15  
**ORM:** SQLAlchemy 2.0  
**Migration Tool:** Alembic  
**Owner:** Database Engineering Team  
**Review Cycle:** Monthly or upon schema changes
