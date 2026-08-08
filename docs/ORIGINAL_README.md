# RIBDIGI BUSINESS ERP (MVP)

> **One ERP Platform. Unlimited Business.**

Enterprise SaaS ERP Platform for Retail, Mart, Pharmacy, Restaurant, Bakery, Wholesale & Manufacturing.

---

## Table of Contents

- [Overview](#overview)
- [Supported Industries](#supported-industries)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Core Modules](#core-modules)
- [AI Business Assistant](#ai-business-assistant)
- [Installation](#installation)
- [Repository Structure](#repository-structure)
- [API Overview](#api-overview)
- [Security](#security)
- [Development Roadmap](#development-roadmap)
- [Documentation](#documentation)
- [License](#license)

---

## Overview

RIBDIGI BUSINESS ERP is a multi-tenant, cloud-native Enterprise Resource Planning platform designed specifically for small-to-medium businesses across retail, food service, pharmaceutical, and manufacturing sectors. Built as a SaaS solution, it provides comprehensive business management tools with data isolation, role-based access control, and AI-powered business intelligence.

### Vision
To deliver a unified, intelligent ERP platform that empowers businesses to streamline operations, optimize inventory, manage finances, and make data-driven decisions through a single, scalable solution.

### Mission
Provide affordable, enterprise-grade ERP capabilities to businesses traditionally underserved by complex and expensive legacy systems, with modern UX, mobile accessibility, and AI augmentation.

---

## Supported Industries

| Industry | Use Cases |
|----------|-----------|
| **Retail** | Store management, POS, inventory tracking, customer loyalty |
| **Mart / Supermarket** | Multi-category inventory, barcode management, bulk purchasing |
| **Pharmacy** | Drug inventory, expiry tracking, prescription sales, regulatory compliance |
| **Restaurant** | Table management, kitchen orders, ingredient tracking, menu engineering |
| **Bakery** | Production planning, recipe management, perishable inventory |
| **Wholesale** | B2B sales, bulk pricing, supplier management, credit tracking |
| **Manufacturing** | Bill of materials, production orders, raw material management |

---

## Key Features

- **Multi-Tenant SaaS Architecture** — Isolated tenant databases with centralized management
- **Role-Based Access Control (RBAC)** — Granular permissions across modules, menus, and records
- **Real-Time Dashboard** — Executive insights into sales, purchases, expenses, and inventory
- **Integrated POS System** — Barcode scanning, multi-payment support, receipt printing, shift management
- **Multi-Store & Warehouse Support** — Inter-store transfers, distributed inventory, centralized reporting
- **Automated Accounting** — Chart of accounts, journal entries, financial reports (P&L, Cash Flow, Trial Balance)
- **Credit Management** — Customer and supplier credit limits, outstanding balances, payment scheduling
- **Tax Engine** — VAT support, automatic tax calculation, comprehensive tax reporting
- **AI-Powered Insights** — Predictive analytics for inventory, sales forecasting, and expense optimization
- **Audit & Compliance** — Complete audit trails, backup/recovery, session management
- **Mobile Ready** — Responsive web + dedicated mobile apps (Flutter/React Native)

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| **Backend Framework** | FastAPI (Python) |
| **ORM** | SQLAlchemy 2.0 |
| **Database** | PostgreSQL |
| **Cache Layer** | Redis |
| **Task Queue** | Celery + RabbitMQ |
| **AI / ML** | Pandas, Scikit-learn, Prophet |
| **Object Storage** | S3-Compatible Storage |
| **Frontend** | React / Next.js |
| **Mobile** | Flutter / React Native |
| **Authentication** | JWT + OAuth2 |
| **Containerization** | Docker |
| **Orchestration** | Kubernetes |
| **CI/CD** | GitHub Actions |

---

## System Architecture

### Design Principles
- **Domain-Driven Design (DDD)** — Clear module boundaries, ubiquitous language, aggregate roots
- **Event-Driven Architecture** — Async communication between modules via event bus
- **SaaS Multi-Tenancy** — Tenant isolation at the database level with shared application layer
- **API-First** — RESTful APIs enabling web, mobile, and third-party integrations
- **AI-Native** — Embedded machine learning pipelines for predictive and prescriptive analytics

### Architecture Layers
```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   React Web  │  │  Mobile App  │  │  Third-Party     │   │
│  │   (Next.js)  │  │(Flutter/RN)  │  │  Integrations    │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                      API Gateway                             │
│         (Authentication, Rate Limiting, Routing)             │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  FastAPI App │  │   Celery     │  │  AI/ML Pipeline  │   │
│  │   Services   │  │   Workers    │  │  (Prophet etc.)  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                     Domain Layer                             │
│  (Inventory, Sales, Purchasing, Accounting, Credit, Tax...)  │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  PostgreSQL  │  │    Redis     │  │  S3 Storage      │   │
│  │  (Tenant DB) │  │   (Cache)    │  │  (Files/Assets)  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Tenant Isolation Strategy
- **Database-per-Tenant** with shared schema structure
- Tenant context resolution via JWT claims
- Automated tenant database initialization on registration
- Row-level security policies for additional data protection

---

## Core Modules

### 1. Multi-Tenant Management
- Company (Tenant) Registration & Profile
- Industry Selection, Currency, Time Zone, Fiscal Year
- Subscription Plans (Trial, Active, Suspended)
- Tenant Database Initialization & Data Isolation

### 2. System Administration
- Company Information & Branch Management
- Store & Warehouse Setup
- Department Configuration
- Multi-Currency & Multi-Language Support
- Tax Configuration

### 3. User Management
- User CRUD with Activate/Deactivate
- **Roles:** Super Admin, Company Admin, Store Manager, Sales Officer, Inventory Officer, Accountant, Cashier
- **Permissions:** Module, Menu, and Record-level access control

### 4. Executive Dashboard
- KPI Cards: Total Sales, Purchases, Expenses, Customers, Suppliers, Products
- Low Stock Alerts, Recent Sales, Top Products
- Daily & Monthly Revenue Charts
- Real-Time Notifications

### 5. Inventory Management
- Product Catalog: Categories, Brands, Units, Variants, SKU, Barcode, Images
- Stock Operations: In, Out, Adjustment, Transfer, Opening Stock, Stock Count
- Warehouse Management: Multiple locations with warehouse-specific stock levels
- **Low Stock Alerts:** Minimum stock, reorder levels, automated notifications
- Stock Movement History & Audit Trail

### 6. Purchasing
- Supplier Management: Profiles, contacts, balance tracking
- Procurement Workflow: Purchase Request → Purchase Order → GRN → Invoice → Return
- Supplier Credit & Payment Scheduling

### 7. Sales
- Customer Management: Profiles, groups, balance tracking
- Sales Workflow: Quotation → Sales Order → Invoice → Sales Return
- Customer Credit Limits & Outstanding Balance Tracking
- Payment Collection & Aging Reports

### 8. Point of Sale (POS)
- Barcode Scanner & Product Search
- Discounts & Promotions
- Multiple Payment Methods (Cash, Card, Digital Wallets)
- Receipt Printing & Cash Drawer Integration
- Customer Selection & Loyalty
- Shift Opening & Closing with Cash Reconciliation

### 9. Expense Management
- Expense Categories & Entry
- Approval Workflows
- Receipt Attachments
- Recurring Expenses
- Expense Summary Reports

### 10. Basic Accounting
- Chart of Accounts (COA)
- Journal Entries
- Cash & Bank Account Management
- Accounts Receivable & Payable
- **Financial Reports:** Profit & Loss, Cash Flow Statement, Trial Balance

### 11. Tax Management
- VAT & Custom Tax Rates
- Automatic Tax Calculation on Transactions
- Comprehensive Tax Reports

### 12. Multi-Store Management
- Store Creation & Manager Assignment
- Store-Level Inventory & Sales
- Inter-Store Stock Transfers
- Consolidated vs. Store-Specific Reporting

### 13. Reporting & Analytics
- **Sales:** Daily, Monthly, Product-wise Sales Reports
- **Inventory:** Stock Balance, Low Stock, Stock Movement
- **Purchase:** Purchase Summary, Supplier-wise Purchases
- **Expense:** Expense Summary
- **Financial:** Profit & Loss, Cash Flow

### 14. Notifications
- Channels: Dashboard, Email, SMS
- Triggers: Low Stock, New Orders, Purchase Received, Payment Due, Credit Limit Reached

### 15. Backup & Recovery
- Manual & Scheduled Backups
- Database Restore Capabilities
- Point-in-Time Recovery

### 16. Audit Logs
- Comprehensive tracking of: Login/Logout, Product Changes, Sales, Purchases, User Activity
- Immutable audit trails for compliance

---

## AI Business Assistant

The platform includes an embedded AI layer to augment business operations:

| AI Capability | Description |
|-------------|-------------|
| **AI ERP Chat Assistant** | Natural language interface for ERP queries and commands |
| **AI Dashboard Insight** | Automated anomaly detection and trend highlighting |
| **Smart Inventory Intelligence** | Demand forecasting and optimal stock level recommendations |
| **AI Low Stock Prediction** | Predictive alerts before stockouts occur |
| **AI Sales Analysis** | Pattern recognition, seasonality detection, revenue forecasting |
| **AI Expense Analysis** | Anomaly detection, cost categorization, budget variance alerts |
| **AI Report Generator** | Natural language to report generation |
| **AI Document Assistant** | OCR and intelligent document processing for invoices/receipts |
| **AI Customer Assistant** | Basic customer segmentation and churn prediction |
| **AI Security Monitor** | Behavioral analysis for fraud and unauthorized access detection |

---

## Installation

### Prerequisites
- Docker & Docker Compose
- Kubernetes cluster (for production)
- PostgreSQL 14+
- Redis 7+
- RabbitMQ 3.11+

### Quick Start (Docker Compose)

```bash
# Clone the repository
git clone https://github.com/your-org/ribdigi-erp.git
cd ribdigi-erp

# Copy environment variables
cp .env.example .env

# Build and start services
docker-compose up -d --build

# Run database migrations
docker-compose exec backend alembic upgrade head

# Create initial tenant & admin user
docker-compose exec backend python scripts/init_tenant.py

# Access the application
# Web App: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Production Deployment (Kubernetes)

```bash
# Configure kubectl context
kubectl config use-context production

# Apply namespace and secrets
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml

# Deploy core services
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/celery-workers.yaml

# Verify deployment
kubectl get pods -n ribdigi-erp
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@db:5432/erp` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `RABBITMQ_URL` | RabbitMQ connection string | `amqp://user:pass@rabbitmq:5672` |
| `JWT_SECRET_KEY` | Secret for JWT token signing | `your-secret-key` |
| `S3_ENDPOINT` | S3-compatible storage endpoint | `https://s3.provider.com` |
| `AI_MODEL_PATH` | Path to ML model artifacts | `/app/models` |

---

## Repository Structure

```
ribdigi-erp/
├── README.md
├── PRODUCT_OVERVIEW.md
├── BUSINESS_REQUIREMENTS_DOCUMENT.md
├── USER_MANUAL.md
├── ADMIN_MANUAL.md
├── DEVELOPER_GUIDE.md
├── API_DOCUMENTATION.md
├── SECURITY_GUIDE.md
├── DEPLOYMENT_GUIDE.md
│
├── backend/
│   ├── app/
│   │   ├── core/                 # Config, security, middleware
│   │   ├── domains/              # DDD modules
│   │   │   ├── inventory/
│   │   │   ├── sales/
│   │   │   ├── purchasing/
│   │   │   ├── accounting/
│   │   │   ├── users/
│   │   │   └── ai/
│   │   ├── api/                  # FastAPI routers
│   │   ├── models/               # SQLAlchemy models
│   │   ├── schemas/              # Pydantic schemas
│   │   ├── services/             # Business logic
│   │   ├── workers/              # Celery background tasks
│   │   └── main.py
│   ├── alembic/                  # Database migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/             # API client
│   │   ├── store/                # State management
│   │   └── App.tsx
│   ├── public/
│   ├── Dockerfile
│   └── package.json
│
├── mobile/
│   ├── android/
│   ├── ios/
│   ├── lib/
│   └── pubspec.yaml              # Flutter
│
├── ai/
│   ├── models/                   # Trained ML models
│   ├── notebooks/                # Training notebooks
│   ├── pipelines/                # Feature engineering
│   └── api/                      # AI service FastAPI app
│
├── k8s/                          # Kubernetes manifests
├── docker-compose.yml
├── Makefile
└── scripts/
    ├── init_tenant.py
    └── backup.sh
```

---

## API Overview

The platform exposes a comprehensive RESTful API:

### Authentication
- `POST /api/v1/auth/login` — JWT token generation
- `POST /api/v1/auth/refresh` — Token refresh
- `POST /api/v1/auth/password-reset` — Password reset flow
- `POST /api/v1/auth/2fa/verify` — Two-factor authentication

### Core Endpoints
| Module | Base Path |
|--------|-----------|
| Products | `/api/v1/products` |
| Inventory | `/api/v1/inventory` |
| Customers | `/api/v1/customers` |
| Suppliers | `/api/v1/suppliers` |
| Sales | `/api/v1/sales` |
| Purchases | `/api/v1/purchases` |
| POS | `/api/v1/pos` |
| Accounting | `/api/v1/accounting` |
| Reports | `/api/v1/reports` |
| AI Assistant | `/api/v1/ai` |

### API Standards
- OpenAPI 3.0 specification
- JSON request/response format
- Standard HTTP status codes
- Pagination via cursor/limit
- Rate limiting: 1000 requests/hour per tenant
- Webhook support for real-time integrations

---

## Security

### Authentication & Authorization
- JWT-based stateless authentication with OAuth2 flows
- Optional Two-Factor Authentication (2FA)
- Session management with automatic expiration
- Role-Based Access Control (RBAC) at module, menu, and record levels

### Data Protection
- AES-256 encryption at rest
- TLS 1.3 for data in transit
- Tenant database isolation
- Row-level security (RLS) policies
- Password hashing with bcrypt

### Compliance & Monitoring
- Immutable audit logs for all critical operations
- Automated security scanning in CI/CD pipeline
- AI-powered security monitor for anomaly detection
- Regular automated backups with encryption

---

## Development Roadmap

### Phase 1: Foundation (MVP)
- [x] Multi-tenant architecture
- [x] User management & RBAC
- [x] Inventory, Sales, Purchasing core modules
- [x] Basic Accounting
- [x] POS system
- [x] Dashboard & Reports

### Phase 2: Enhancement
- [ ] Advanced AI predictions & forecasting
- [ ] Mobile app (Flutter)
- [ ] Advanced analytics & BI dashboards
- [ ] E-commerce integration
- [ ] Multi-currency accounting
- [ ] Advanced workflow automation

### Phase 3: Scale
- [ ] Marketplace for third-party plugins
- [ ] Advanced manufacturing module (MRP)
- [ ] CRM integration
- [ ] Multi-country tax compliance
- [ ] White-label capabilities

---

## Documentation

| Document | Purpose |
|----------|---------|
| `PRODUCT_OVERVIEW.md` | Vision, mission, target customers, competitive positioning |
| `BUSINESS_REQUIREMENTS_DOCUMENT.md` | Functional & non-functional requirements, workflows |
| `USER_MANUAL.md` | End-user guide for dashboard, inventory, sales, POS, accounting |
| `ADMIN_MANUAL.md` | Tenant creation, user management, permissions, backups |
| `DEVELOPER_GUIDE.md` | Coding standards, folder structure, dev environment, testing |
| `API_DOCUMENTATION.md` | API standards, authentication, endpoints, webhooks, rate limits |
| `SECURITY_GUIDE.md` | Security architecture, threat model, encryption, RBAC, audit |
| `DEPLOYMENT_GUIDE.md` | Docker, Kubernetes, CI/CD, monitoring |

---

## License

Copyright © 2026 RIBDIGI. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

---

<p align="center">
  <strong>Built with modern technologies for modern businesses.</strong><br>
  <em>One ERP Platform. Unlimited Business.</em>
</p>
