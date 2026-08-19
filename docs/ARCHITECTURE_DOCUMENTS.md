# Architecture Documents

## RIBDIGI BUSINESS ERP — MVP Architecture Documentation

**Version:** 1.0.0  
**Classification:** Internal — Engineering & Architecture  
**Last Updated:** August 2026  
**Applies To:** RIBDIGI ERP MVP (Version 1.0)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Domain-Driven Design (DDD)](#2-domain-driven-design-ddd)
3. [Module Boundaries & Context Mapping](#3-module-boundaries--context-mapping)
4. [Event-Driven Architecture](#4-event-driven-architecture)
5. [SaaS & Multi-Tenant Design](#5-saas--multi-tenant-design)
6. [AI Architecture](#6-ai-architecture)
7. [Integration Design](#7-integration-design)
8. [Security Architecture](#8-security-architecture)
9. [Data Architecture](#9-data-architecture)
10. [Technology Stack & Rationale](#10-technology-stack--rationale)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Scalability & Performance](#12-scalability--performance)
13. [Appendix: Decision Records](#appendix-decision-records)

---

## 1. System Overview

### 1.1 Vision

RIBDIGI BUSINESS ERP is a unified, multi-tenant SaaS platform designed to serve diverse industries—Retail, Mart, Pharmacy, Restaurant, Bakery, Wholesale, and Manufacturing—through a single codebase. The architecture prioritizes tenant isolation, modular extensibility, and AI-driven business intelligence while maintaining operational simplicity for the MVP.

**Tagline:** One ERP Platform. Unlimited Business.

### 1.2 Architectural Principles

| Principle | Description |
|-----------|-------------|
| **Single Codebase, Multiple Industries** | Industry-specific logic configured via settings and extensions, not separate deployments |
| **Tenant-First Isolation** | Data, compute, and configuration isolation at the database and application layers |
| **Event-Driven Decoupling** | Core modules communicate via events to reduce coupling and enable async processing |
| **API-First Design** | All functionality exposed via REST APIs; UI is a consumer, not the owner |
| **AI-Native** | AI capabilities are first-class citizens, not bolt-on features |
| **Cloud-Native** | Containerized, orchestrated, and horizontally scalable from day one |

### 1.3 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Web App     │  │  Mobile App  │  │  Third-Party │  │   POS Term.  │   │
│  │  (Next.js)   │  │  (Flutter)   │  │   APIs       │  │   (React)    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          └─────────────────┴─────────────────┴─────────────────┘
                              │ HTTPS / TLS 1.3
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                           API GATEWAY LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  • WAF / DDoS Protection  • Rate Limiting  • Request Routing           ││
│  │  • TLS Termination        • CORS Handling    • API Versioning          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                         APPLICATION LAYER (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│
│  │  Auth &     │  │  Business   │  │   Event     │  │   AI Services       ││
│  │  Identity   │  │  Modules    │  │   Bus       │  │   (Scikit-learn,    ││
│  │  (JWT/OAuth2)│  │  (21 mods)  │  │  (RabbitMQ) │  │    Prophet, Pandas) ││
│  └─────────────┘  └──────┬──────┘  └─────────────┘  └─────────────────────┘│
│                          │                                                  │
│  ┌───────────────────────▼─────────────────────────────────────────────────┐│
│  │                    DOMAIN SERVICES (CQRS-Ready)                        ││
│  │  Inventory │ Sales │ Purchasing │ Accounting │ POS │ Reports │ AI     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────────────┐
│                         DATA & MESSAGING LAYER                               │
│  ┌─────────────┐  ┌────────┴────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  PostgreSQL │  │     Redis       │  │  RabbitMQ   │  │  S3 Storage │   │
│  │  (Primary + │  │  (Cache +       │  │  (Task      │  │  (Documents │   │
│  │   Replicas) │  │   Sessions)     │  │   Queue)    │  │   & Images) │   │
│  └─────────────┘  └─────────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Domain-Driven Design (DDD)

### 2.1 Bounded Contexts

The ERP is decomposed into the following bounded contexts, each representing a cohesive business capability:

| Bounded Context | Description | Key Aggregates |
|-----------------|-------------|----------------|
| **Identity & Access** | Authentication, authorization, tenant management | Tenant, User, Role, Permission |
| **Inventory** | Product catalog, stock movements, warehouses | Product, StockMovement, Warehouse, Category |
| **Sales** | Quotations, orders, invoices, returns | Quotation, SalesOrder, Invoice, SalesReturn |
| **Purchasing** | Suppliers, POs, GRNs, purchase returns | Supplier, PurchaseOrder, GRN, PurchaseReturn |
| **POS** | Point-of-sale operations, shifts, receipts | POSSession, POSSale, Receipt |
| **Accounting** | Chart of accounts, journal entries, reports | Account, JournalEntry, FinancialReport |
| **Credit Management** | Customer/supplier credit, outstanding balances | CreditAccount, Payment, CreditLimit |
| **Expense Management** | Expense tracking, approvals, recurring costs | Expense, ExpenseCategory, RecurringExpense |
| **Tax Management** | Tax rates, calculations, reporting | TaxRate, TaxReport |
| **Multi-Store** | Store management, inter-store transfers | Store, StoreInventory, StoreTransfer |
| **Notifications** | Alerts, emails, SMS | Notification, NotificationPreference |
| **AI Business Assistant** | Insights, predictions, document analysis | AIQuery, AIInsight, AIDocument |

### 2.2 Ubiquitous Language

| Term | Definition | Context |
|------|------------|---------|
| **Tenant** | A registered company with isolated data and configuration | Identity |
| **Stock Movement** | Any change in inventory quantity (in, out, adjustment, transfer) | Inventory |
| **GRN** | Goods Received Note — confirmation of received purchase items | Purchasing |
| **Sales Return** | Customer return of sold goods with refund | Sales |
| **Journal Entry** | Double-entry bookkeeping record | Accounting |
| **Shift** | A cashier's work period with opening/closing cash | POS |
| **Inter-Store Transfer** | Movement of stock between retail locations | Multi-Store |

### 2.3 Aggregate Design

**Product Aggregate (Inventory Context):**
```
Product (Root)
├── ProductVariant
├── StockLevel
├── Category (Reference)
├── Brand (Reference)
└── Unit (Reference)
```

**Invoice Aggregate (Sales Context):**
```
Invoice (Root)
├── InvoiceItem
├── Payment
├── Customer (Reference)
└── SalesOrder (Reference, optional)
```

**Purchase Order Aggregate (Purchasing Context):**
```
PurchaseOrder (Root)
├── PurchaseOrderItem
├── GRN (Reference, optional)
├── Supplier (Reference)
└── PurchaseInvoice (Reference, optional)
```

### 2.4 Domain Services

Services that don't naturally belong to any single aggregate:

- **PricingService** — Calculates prices with discounts, taxes, and currency conversion
- **StockReservationService** — Reserves inventory during sales order processing
- **PaymentAllocationService** — Allocates customer payments across multiple invoices
- **TaxCalculationService** — Computes tax based on jurisdiction and product type
- **AIInsightService** — Generates business insights across domain boundaries

---

## 3. Module Boundaries & Context Mapping

### 3.1 Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    Identity & Access                         │
│              (Tenant, User, Auth, RBAC)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ All modules depend on Identity
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│ Inventory  │ │  Sales     │ │ Purchasing │
│  Module    │ │  Module    │ │  Module    │
└─────┬──────┘ └─────┬──────┘ └─────┬──────┘
      │              │              │
      └──────────────┼──────────────┘
                     ▼
            ┌────────────┐
            │ Accounting │
            │  Module    │
            └─────┬──────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐
│  POS   │ │ Credit │ │  Tax   │
│ Module │ │ Module │ │ Module │
└────────┘ └────────┘ └────────┘
      │           │           │
      └───────────┼───────────┘
                  ▼
         ┌────────────┐
         │  Reports   │
         │  Module    │
         └────────────┘
                  │
                  ▼
         ┌────────────┐
         │    AI      │
         │ Assistant  │
         └────────────┘
```

### 3.2 Context Mapping Patterns

| Relationship | Upstream | Downstream | Pattern |
|--------------|----------|------------|---------|
| Identity → All | Identity | All Modules | **Shared Kernel** (common auth middleware) |
| Inventory → Sales | Inventory | Sales | **Customer-Supplier** (Sales queries stock levels) |
| Sales → Accounting | Sales | Accounting | **Published Language** (Sales events → journal entries) |
| Purchasing → Inventory | Purchasing | Inventory | **Conformist** (GRN updates stock directly) |
| POS → Sales | POS | Sales | **Anti-Corruption Layer** (POS normalizes to Sales domain) |
| All → AI | All | AI | **Open Host Service** (AI consumes events from all contexts) |

### 3.3 Anti-Corruption Layers (ACL)

**POS → Sales ACL:**
- POS operates with its own model (quick sales, barcode scanning, cash drawer)
- ACL translates POS sales into formal Sales domain invoices
- Ensures POS simplicity doesn't pollute the Sales bounded context

**External Integrations → Core:**
- Payment gateways (Stripe, PayPal) → Internal Payment model
- SMS/Email providers → Internal Notification model
- Tax APIs → Internal TaxRate model

---

## 4. Event-Driven Architecture

### 4.1 Event Bus Design

RabbitMQ serves as the central event bus, enabling async communication between modules.

**Exchange Topology:**
```
ribdigi.events (topic exchange)
├── inventory.stock.changed → [accounting, notifications, ai]
├── sales.invoice.created → [accounting, inventory, notifications, ai]
├── sales.payment.received → [credit, accounting, notifications]
├── purchase.order.received → [inventory, accounting, notifications]
├── user.login.failed → [security, notifications]
├── tenant.created → [ai, notifications]
└── expense.approved → [accounting, notifications]
```

### 4.2 Core Domain Events

```python
class DomainEvent(BaseModel):
    event_id: str
    tenant_id: str
    timestamp: datetime
    event_type: str
    payload: dict

class StockChangedEvent(DomainEvent):
    event_type: str = "inventory.stock.changed"
    payload: StockChangedPayload

class InvoiceCreatedEvent(DomainEvent):
    event_type: str = "sales.invoice.created"
    payload: InvoiceCreatedPayload

class PaymentReceivedEvent(DomainEvent):
    event_type: str = "sales.payment.received"
    payload: PaymentReceivedPayload
```

### 4.3 Event Handlers

| Event | Publisher | Subscribers | Action |
|-------|-----------|-------------|--------|
| `inventory.stock.changed` | Inventory Module | Accounting, Notifications, AI | Update COGS, check low stock, predict demand |
| `sales.invoice.created` | Sales Module | Accounting, Inventory, AI | Create journal entry, reserve stock, analyze trend |
| `sales.payment.received` | Sales Module | Credit, Accounting | Update outstanding balance, reconcile bank |
| `purchase.order.received` | Purchasing Module | Inventory, Accounting | Update stock, create payable entry |
| `user.login.failed` | Auth Module | Security Monitor | Detect brute force, alert admin |
| `tenant.created` | Identity Module | AI, Notifications | Initialize AI models, send welcome email |

### 4.4 Saga Pattern (Distributed Transactions)

**Sales Order → Invoice → Payment Saga:**
```
1. Sales Module: Create Sales Order
2. Inventory Module: Reserve Stock (compensating action: release stock)
3. Sales Module: Generate Invoice
4. Customer: Make Payment
5. Accounting Module: Create Journal Entry
6. Inventory Module: Confirm Stock Deduction
7. Notifications Module: Send Receipt
```

If payment fails at step 4:
- Compensating action: Release stock reservation
- Compensating action: Cancel invoice
- Compensating action: Reverse journal entry

### 4.5 Outbox Pattern

To ensure event consistency with database transactions:
- Events are written to an `outbox` table within the same database transaction as the business operation
- A background Celery worker polls the outbox and publishes events to RabbitMQ
- Events are marked as `published` after successful delivery
- Guarantees at-least-once delivery with idempotent consumers

---

## 5. SaaS & Multi-Tenant Design

### 5.1 Tenant Isolation Model

**Schema-per-Tenant (Selected for MVP):**

```
Database: ribdigi_erp
├── Schema: public (tenant registry, global config)
│   ├── tenants
│   ├── subscription_plans
│   └── global_settings
├── Schema: tenant_abc123 (Acme Retail)
│   ├── users, roles, permissions
│   ├── products, categories, stock_movements
│   ├── customers, invoices, sales_orders
│   └── ... (all tenant-specific tables)
├── Schema: tenant_def456 (Beta Mart)
│   └── ... (isolated tables)
└── Schema: tenant_ghi789 (Gamma Pharmacy)
    └── ... (isolated tables)
```

**Rationale:**
- Strong data isolation (no risk of cross-tenant query leakage)
- Simpler backup/restore per tenant
- Easier schema migration per tenant
- Slightly higher operational overhead acceptable for MVP

### 5.2 Tenant Lifecycle

```
Registration → Provisioning → Active → Suspended → Deleted
     │              │            │          │          │
     ▼              ▼            ▼          ▼          ▼
  Validate     Create Schema   Billing   Block API   Soft Delete
  Domain       Seed Data       Monitor   Notify      Archive Data
  Create       Setup AI        Support   Retain      Purge After
  Admin        Send Welcome    Upsell    Logs        30 Days
```

### 5.3 Tenant Configuration

Each tenant stores configuration in a `tenant_settings` table:

```json
{
  "tenant_id": "tenant_abc123",
  "industry": "retail",
  "currency": "USD",
  "timezone": "America/New_York",
  "fiscal_year_start": "01-01",
  "features": {
    "pos_enabled": true,
    "multi_store_enabled": true,
    "ai_enabled": true,
    "advanced_accounting": false
  },
  "limits": {
    "max_users": 50,
    "max_products": 10000,
    "max_stores": 5,
    "api_rate_limit": 300
  }
}
```

### 5.4 Resource Quotas

| Plan | Max Users | Max Products | Max Stores | API Rate | Storage |
|------|-----------|--------------|------------|----------|---------|
| Trial | 5 | 1,000 | 1 | 60/min | 5 GB |
| Basic | 20 | 10,000 | 3 | 120/min | 50 GB |
| Professional | 100 | 100,000 | 10 | 300/min | 500 GB |
| Enterprise | Unlimited | Unlimited | Unlimited | Unlimited | 5 TB |

---

## 6. AI Architecture

### 6.1 AI Service Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Business Assistant                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  NLP/Chat   │  │  Predictive │  │  Document           │  │
│  │  Interface  │  │  Analytics  │  │  Intelligence       │  │
│  │             │  │             │  │                     │  │
│  │ • Chatbot   │  │ • Demand    │  │ • Invoice OCR       │  │
│  │ • Query     │  │   Forecast  │  │ • Receipt Parsing   │  │
│  │   Parsing   │  │ • Anomaly   │  │ • Data Extraction   │  │
│  │             │  │   Detection │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │               │
│         └────────────────┼────────────────────┘               │
│                          ▼                                   │
│         ┌────────────────────────────────┐                   │
│         │      AI Orchestrator           │                   │
│         │  (Pandas + Scikit-learn +      │                   │
│         │   Prophet + Custom Models)     │                   │
│         └────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 AI Capabilities by Module

| Capability | Input | Model/Method | Output |
|------------|-------|--------------|--------|
| **Smart Inventory Prediction** | Historical sales, seasonality, stock levels | Prophet (time-series) | Reorder recommendations, demand forecast |
| **AI Low Stock Prediction** | Stock movement velocity, lead times | Scikit-learn regression | Days-until-stockout per product |
| **AI Sales Analysis** | Transaction history, product mix | Pandas aggregation + clustering | Top products, trend detection, seasonality |
| **AI Expense Analysis** | Expense categories, amounts, dates | Statistical analysis + anomaly detection | Unusual spending, budget variance |
| **AI Report Generator** | User query, tenant data | Template engine + data aggregation | PDF/Excel reports with insights |
| **AI Document Assistant** | Uploaded images/PDFs | OCR (Tesseract/EasyOCR) + NLP | Structured data extraction |
| **AI Customer Assistant** | Customer query, account data | Rule-based + similarity search | Account balance, order status, recommendations |
| **AI Security Monitor** | Login patterns, API access logs | Anomaly detection (Isolation Forest) | Risk score, suspicious activity alerts |
| **AI Dashboard Insights** | Real-time metrics | Comparative analysis + thresholds | Natural language summary of business health |

### 6.3 AI Data Pipeline

```
Raw Data (PostgreSQL) → ETL (Pandas) → Feature Store (Redis/Parquet)
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
            Training Pipeline            Inference Pipeline         Monitoring
            (Batch: nightly)            (Real-time: API call)     (Continuous)
                    │                          │                          │
                    ▼                          ▼                          ▼
            Model Registry (S3)        Prediction API           Drift Detection
            (Versioned artifacts)      (FastAPI endpoints)      (Alert if accuracy drops)
```

### 6.4 Model Serving

- **Batch Predictions:** Nightly Celery jobs generate forecasts (demand, stockout)
- **Real-Time Predictions:** FastAPI endpoints serve chat responses and document analysis
- **Model Artifacts:** Stored in S3 with versioning; loaded into memory on worker startup
- **Fallback:** If AI service unavailable, system degrades gracefully to rule-based logic

---

## 7. Integration Design

### 7.1 Internal Integration Patterns

| Pattern | Use Case | Implementation |
|---------|----------|----------------|
| **REST API** | Synchronous module communication | FastAPI routers with shared Pydantic schemas |
| **Event Bus** | Async cross-module updates | RabbitMQ with topic exchanges |
| **Shared Database** | Same-module read/write | PostgreSQL with schema isolation |
| **Cache** | High-frequency reads | Redis with TTL and invalidation |
| **CQRS (Future)** | Read-heavy reporting | Separate read models in Elasticsearch |

### 7.2 External Integrations

| System | Integration Type | Data Flow | Auth |
|--------|-----------------|-----------|------|
| **Payment Gateways** | REST API | Outbound: Process payments | API Keys |
| **SMS Providers** | REST API | Outbound: Send alerts | API Keys |
| **Email Services** | SMTP/REST | Outbound: Transactional emails | SMTP creds / API Keys |
| **Tax APIs** | REST API | Outbound: Validate tax IDs, rates | OAuth2 |
| **Accounting Software** | REST API | Bidirectional: Sync journal entries | OAuth2 |
| **E-commerce Platforms** | REST API / Webhooks | Bidirectional: Sync products, orders | OAuth2 + Webhooks |
| **Barcode Scanners** | HID/USB | Inbound: POS product lookup | Device pairing |
| **Receipt Printers** | ESC/POS | Outbound: Print receipts | Network/USB |
| **Cash Drawers** | GPIO/Serial | Outbound: Trigger open | Hardware driver |

### 7.3 Webhook Architecture

```
External System → POST /webhooks/incoming/{provider}
                        │
                        ▼
               ┌─────────────────┐
               │ Webhook Handler │
               │ (Idempotency    │
               │  Key Check)     │
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ Event Normalizer│
               │ (Provider-specific│
               │  → Generic Event)│
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │  Domain Event   │
               │  Published to   │
               │  Event Bus      │
               └─────────────────┘
```

### 7.4 API Gateway Integration

- **Request Routing:** `/api/v1/*` → Backend Service, `/app/*` → Frontend Service
- **Protocol Translation:** REST ↔ gRPC for internal service calls (future)
- **Aggregation:** BFF (Backend-for-Frontend) pattern for mobile app endpoints

---

## 8. Security Architecture

### 8.1 Defense in Depth

```
Layer 1: Perimeter
├── WAF (OWASP rules)
├── DDoS protection
├── Geo-blocking (optional)
└── TLS 1.3 termination

Layer 2: API Gateway
├── Rate limiting per tenant
├── API key validation
├── Request size limits
└── CORS enforcement

Layer 3: Application
├── JWT validation
├── RBAC enforcement
├── Input sanitization
└── Output encoding

Layer 4: Data
├── Parameterized queries (SQL injection prevention)
├── Row-level security (tenant isolation)
├── Encryption at rest (AES-256)
└── Encryption in transit (TLS 1.3)

Layer 5: Infrastructure
├── Network policies (K8s)
├── Pod security standards
├── Secret management (Vault)
└── Audit logging
```

### 8.2 Authentication Flow

```
User → POST /auth/login {email, password, tenant_id}
           │
           ▼
    ┌──────────────┐
    │  bcrypt      │
    │  Verification │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  JWT Token   │
    │  Generation  │
    │  (RS256)     │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  Redis Store │
    │  (Session +  │
    │   Refresh)   │
    └──────┬───────┘
           │
           ▼
User ← {access_token, refresh_token}
```

### 8.3 Authorization Architecture

```
Request → Auth Middleware → JWT Decode → Tenant Validation
                                      │
                                      ▼
                            ┌─────────────────┐
                            │ Permission      │
                            │ Middleware      │
                            │ (Module + Menu  │
                            │  + Record)      │
                            └────────┬────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              ┌─────────┐    ┌──────────┐    ┌──────────┐
              │ Allowed │    │  Denied  │    │  Elevated│
              │ Proceed │    │  403     │    │  2FA Req │
              └─────────┘    └──────────┘    └──────────┘
```

---

## 9. Data Architecture

### 9.1 Database Schema Strategy

**Schema-per-Tenant with Shared Catalog:**

```sql
-- Public schema: Global metadata
CREATE TABLE public.tenants (
    tenant_id UUID PRIMARY KEY,
    company_name VARCHAR(255),
    industry VARCHAR(50),
    subscription_plan VARCHAR(50),
    status VARCHAR(20),
    created_at TIMESTAMP
);

-- Tenant schema: Auto-generated on tenant creation
CREATE SCHEMA tenant_abc123;

CREATE TABLE tenant_abc123.products (
    id UUID PRIMARY KEY,
    tenant_id UUID DEFAULT 'tenant_abc123',
    name VARCHAR(255),
    sku VARCHAR(100) UNIQUE,
    category_id UUID,
    created_at TIMESTAMP
);

-- Enforce tenant isolation via RLS (optional layer)
ALTER TABLE tenant_abc123.products ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenant_abc123.products
    USING (tenant_id = current_setting('app.current_tenant')::UUID);
```

### 9.2 Data Flow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   FastAPI   │────▶│  SQLAlchemy │
│  Request    │     │   Endpoint  │     │    ORM      │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                     │
                           │              ┌──────▼──────┐
                           │              │  Connection │
                           │              │   Pool      │
                           │              │  (PgBouncer)│
                           │              └──────┬──────┘
                           │                     │
                           │              ┌──────▼──────┐
                           │              │ PostgreSQL  │
                           │              │ (Tenant     │
                           │              │  Schema)    │
                           │              └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │  (Cache +   │
                    │  Sessions)  │
                    └─────────────┘
```

### 9.3 Caching Strategy

| Cache Type | Key Pattern | TTL | Invalidation |
|------------|-------------|-----|--------------|
| **Session** | `session:{jwt_jti}` | 15 min | Logout, password change |
| **User Permissions** | `perms:{user_id}` (physical: `ribdigi:cache:perms:{tenant_id}:{user_id}`) | 1 hour | Role / record_scope change; custom-role sync (Stage 7 C2) |
| **Product Catalog** | `products:{tenant_id}:{category_id}` | 10 min | Stock change, price update |
| **Dashboard Metrics** | `dashboard:{tenant_id}:{metric}` | 5 min | Transaction event |
| **Tax Rates** | `tax:{tenant_id}:{tax_id}` | 24 hours | Tax configuration change |
| **AI Predictions** | `ai:forecast:{tenant_id}:{product_id}` | 6 hours | Nightly batch refresh |

### 9.4 Storage Architecture

| Data Type | Storage | Path Pattern | Lifecycle |
|-----------|---------|--------------|-----------|
| **Product Images** | S3 | `tenants/{tenant_id}/products/{product_id}/{filename}` | 90 days versions |
| **Expense Attachments** | S3 | `tenants/{tenant_id}/expenses/{expense_id}/{filename}` | 7 years |
| **Receipts (POS)** | S3 | `tenants/{tenant_id}/receipts/{sale_id}.pdf` | 7 years |
| **AI Model Artifacts** | S3 | `ai-models/{model_name}/{version}/` | Versioned, permanent |
| **Database Backups** | S3 | `backups/{tenant_id}/{date}/` | 30 days |
| **Audit Logs** | S3 + Glacier | `audit/{tenant_id}/{year}/{month}/` | 2 years hot, 5 years cold |

---

## 10. Technology Stack & Rationale

### 10.1 Final Technical Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend Framework** | FastAPI | Async-native, automatic OpenAPI docs, Pydantic validation, high performance |
| **ORM** | SQLAlchemy 2.0 | Mature, supports async, schema-per-tenant, Alembic migrations |
| **Database** | PostgreSQL 15 | ACID compliance, JSON support, RLS, excellent relational model fit |
| **Cache** | Redis 7 | In-memory speed, pub/sub, TTL support, session storage |
| **Task Queue** | Celery + RabbitMQ | Reliable task distribution, scheduling (beat), retry logic |
| **AI/ML** | Pandas + Scikit-learn + Prophet | Mature Python ecosystem, time-series forecasting, statistical analysis |
| **Object Storage** | S3-Compatible (MinIO/AWS S3) | Industry standard, signed URLs, lifecycle policies |
| **Frontend** | React / Next.js 14 | SSR for SEO, SSG for speed, API routes for BFF, Vercel optimization |
| **Mobile** | Flutter / React Native | Cross-platform, native performance, shared business logic |
| **Authentication** | JWT + OAuth2 | Stateless, industry standard, easy integration |
| **Containerization** | Docker | Consistent environments, multi-stage builds, small images |
| **Orchestration** | Kubernetes | Auto-scaling, self-healing, rolling deployments, ecosystem maturity |
| **CI/CD** | GitHub Actions | Integrated with repo, matrix builds, secrets management |

### 10.2 Alternative Evaluations

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Backend Framework | FastAPI | Django, Flask | Async + auto-docs + type safety |
| Database | PostgreSQL | MySQL, MongoDB | ACID + RLS + relational complexity |
| Task Queue | RabbitMQ | Redis Queue, Kafka | Reliable persistence + Celery native support |
| Frontend | Next.js | Vue, Angular | SSR + React ecosystem + Vercel |
| Mobile | Flutter | Native iOS/Android | Single codebase, near-native performance |
| AI Framework | Scikit-learn | TensorFlow, PyTorch | Simpler models, faster inference, less overhead |

---

## 11. Deployment Architecture

### 11.1 Environment Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRODUCTION                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  Kubernetes Cluster (EKS/GKE/AKS)                                      ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ││
│  │  │   Ingress   │  │   Backend   │  │  Frontend   │  │   Celery    │  ││
│  │  │   (NGINX)   │  │   (5 pods)  │  │   (3 pods)  │  │   (3 pods)  │  ││
│  │  └─────────────┘  └──────┬──────┘  └─────────────┘  └─────────────┘  ││
│  │                          │                                             ││
│  │  ┌───────────────────────┼─────────────────────────────────────────┐  ││
│  │  │  Managed Services     │                                         │  ││
│  │  │  • RDS PostgreSQL    │  • ElastiCache Redis                   │  ││
│  │  │  • Amazon MQ (Rabbit)│  • S3 / MinIO                        │  ││
│  │  └───────────────────────┴─────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              STAGING                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  Kubernetes Cluster (2 nodes)                                          ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ││
│  │  │   Backend   │  │  Frontend   │  │   Celery    │  │  PostgreSQL │  ││
│  │  │   (2 pods)  │  │   (2 pods)  │  │   (2 pods)  │  │  (1 pod)    │  ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOCAL DEVELOPMENT                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  Docker Compose                                                         ││
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   ││
│  │  │Backend │ │Frontend│ │PostgreSQL│ │ Redis  │ │RabbitMQ│ │ MinIO  │   ││
│  │  │ (1)    │ │ (1)    │ │  (1)    │ │  (1)   │ │  (1)   │ │  (1)   │   ││
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Service Mesh (Future)

Istio or Linkerd will be introduced post-MVP for:
- mTLS between services
- Traffic splitting (canary deployments)
- Observability (distributed tracing)
- Circuit breaking

---

## 12. Scalability & Performance

### 12.1 Scaling Dimensions

| Dimension | Strategy | Current | Target |
|-----------|----------|---------|--------|
| **Tenants** | Schema-per-tenant + connection pooling | 1 | 1,000 |
| **Users per Tenant** | Horizontal pod scaling | 10 | 500 |
| **Transactions/Second** | Async processing + caching | 10 | 1,000 |
| **Concurrent POS Sessions** | WebSocket optimization + Redis | 5 | 200 |
| **AI Queries/Day** | Batch + caching | 100 | 50,000 |
| **Data Retention** | Tiered storage (S3 + Glacier) | 1 GB | 5 TB |

### 12.2 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Response Time (p95)** | < 200 ms | Prometheus |
| **Page Load Time** | < 2 seconds | Lighthouse |
| **POS Transaction** | < 500 ms | End-to-end timing |
| **Report Generation** | < 5 seconds | Application logs |
| **AI Insight Generation** | < 3 seconds | API response time |
| **Database Query (p95)** | < 50 ms | PostgreSQL logs |
| **Cache Hit Ratio** | > 85 % | Redis INFO |

### 12.3 Bottleneck Mitigation

| Bottleneck | Mitigation |
|------------|------------|
| **Database Connections** | PgBouncer connection pooling; read replicas for reports |
| **Slow Reports** | Materialized views; pre-aggregated tables; background generation |
| **AI Inference Latency** | Model caching in Redis; batch predictions; lightweight models |
| **File Uploads** | Direct-to-S3 signed URLs; async processing |
| **Tenant Provisioning** | Async schema creation; template databases |

---

## 13. Appendix: Decision Records

### ADR-001: Schema-per-Tenant over Database-per-Tenant

**Status:** Accepted  
**Context:** Need strong isolation without operational complexity  
**Decision:** Use PostgreSQL schema-per-tenant with shared database  
**Consequences:** (+) Easier backups, simpler connection management, lower cost. (-) Slightly higher risk of cross-tenant bugs, schema migration complexity.

### ADR-002: FastAPI over Django for Backend

**Status:** Accepted  
**Context:** Need async support, auto-generated API docs, type safety  
**Decision:** Use FastAPI with SQLAlchemy 2.0  
**Consequences:** (+) High performance, automatic OpenAPI, Pydantic validation. (-) Smaller ecosystem than Django, need to build admin UI separately.

### ADR-003: RabbitMQ over Redis for Task Queue

**Status:** Accepted  
**Context:** Need reliable task persistence and complex routing  
**Decision:** Use RabbitMQ for Celery backend; Redis for cache/sessions only  
**Consequences:** (+) Message durability, routing flexibility, priority queues. (-) Additional infrastructure component to manage.

### ADR-004: Scikit-learn over TensorFlow for AI

**Status:** Accepted  
**Context:** MVP requires statistical analysis and time-series, not deep learning  
**Decision:** Use Pandas + Scikit-learn + Prophet  
**Consequences:** (+) Faster inference, simpler deployment, smaller models. (-) Limited to traditional ML; deep learning requires migration later.

### ADR-005: Next.js over Pure React for Frontend

**Status:** Accepted  
**Context:** Need SSR for initial load, API routes for BFF pattern  
**Decision:** Use Next.js 14 with App Router  
**Consequences:** (+) SSR/SSG, API routes, image optimization. (-) Vercel lock-in concerns, server component complexity.

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Technical Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, Celery + RabbitMQ, React/Next.js, Flutter, Docker, Kubernetes  
**Owner:** Solution Architecture Team  
**Review Cycle:** Monthly or upon major feature additions
