# RIBDIGI BUSINESS ERP — Developer Guide

> **Version:** 1.0 (MVP)  
> **Last Updated:** August 2026  
> **For:** Backend, Frontend, Mobile, AI/ML, and DevOps Engineers  
> **Status:** Living Document — Subject to Team Review

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Technology Stack](#2-technology-stack)
3. [Development Environment Setup](#3-development-environment-setup)
4. [Project Structure](#4-project-structure)
5. [Coding Standards](#5-coding-standards)
6. [Git Workflow](#6-git-workflow)
7. [Architecture Overview](#7-architecture-overview)
8. [Backend Development](#8-backend-development)
9. [Frontend Development](#9-frontend-development)
10. [AI/ML Pipeline Development](#10-aiml-pipeline-development)
11. [Database & Migrations](#11-database--migrations)
12. [Testing Strategy](#12-testing-strategy)
13. [Docker & Local Development](#13-docker--local-development)
14. [API Development Standards](#14-api-development-standards)
15. [Authentication & Authorization](#15-authentication--authorization)
16. [Background Jobs & Queues](#16-background-jobs--queues)
17. [Caching Strategy](#17-caching-strategy)
18. [Observability & Logging](#18-observability--logging)
19. [Troubleshooting](#19-troubleshooting)
20. [Appendix](#20-appendix)

---

## 1. Introduction

### 1.1 Purpose

This Developer Guide establishes the technical standards, workflows, and conventions for all engineers contributing to the RIBDIGI BUSINESS ERP platform. It ensures code consistency, maintainability, and scalability across the distributed development team.

### 1.2 Target Audience

| Role | Primary Sections |
|------|-----------------|
| **Backend Engineers** | Sections 3, 4, 5, 7, 8, 11, 12, 14, 15, 16, 17 |
| **Frontend Engineers** | Sections 3, 4, 5, 7, 9, 12 |
| **Mobile Engineers** | Sections 3, 4, 5, 7, 12 |
| **AI/ML Engineers** | Sections 3, 4, 5, 7, 10, 12 |
| **DevOps Engineers** | Sections 3, 4, 6, 13, 18 |
| **QA Engineers** | Sections 6, 12, 19 |

### 1.3 Development Philosophy

- **Domain-Driven Design (DDD):** Code structure mirrors business domains
- **API-First:** All features start with API contract definition
- **Test-Driven Development (TDD):** Write tests before or alongside feature code
- **12-Factor App:** Stateless, configurable, portable, scalable
- **Security by Design:** Authentication, authorization, and audit are never afterthoughts

---

## 2. Technology Stack

### 2.1 Core Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Backend Framework** | FastAPI | 0.110+ | High-performance async Python API framework |
| **ORM** | SQLAlchemy | 2.0+ | Database abstraction and query building |
| **Database** | PostgreSQL | 16+ | Primary transactional database |
| **Cache** | Redis | 7+ | Session store, query cache, rate limiting |
| **Task Queue** | Celery | 5.3+ | Background job processing |
| **Message Broker** | RabbitMQ | 3.12+ | Celery task routing and queuing |
| **AI/ML** | Pandas, Scikit-learn, Prophet | Latest stable | Data processing, forecasting, classification |
| **Object Storage** | MinIO / AWS S3 | Latest | File uploads, backups, assets |
| **Frontend** | React + Next.js | 14+ (App Router) | Server-side rendering, SPA capabilities |
| **Mobile** | Flutter | 3.19+ | Cross-platform native mobile apps |
| **Auth** | JWT + OAuth2 | RFC 7519 | Stateless authentication |
| **Container** | Docker | 24+ | Application containerization |
| **Orchestration** | Kubernetes | 1.29+ | Container orchestration |
| **CI/CD** | GitHub Actions | N/A | Automated testing and deployment |

### 2.2 Development Tools

| Tool | Purpose | Configuration File |
|------|---------|-------------------|
| **Ruff** | Python linting and formatting | `pyproject.toml` |
| **Black** | Python code formatting (fallback) | `pyproject.toml` |
| **Mypy** | Python static type checking | `pyproject.toml` |
| **ESLint** | JavaScript/TypeScript linting | `.eslintrc.json` |
| **Prettier** | Code formatting (JS/TS/CSS) | `.prettierrc` |
| **Pytest** | Python testing framework | `pyproject.toml` |
| **Playwright** | E2E testing | `playwright.config.ts` |
| **Alembic** | Database migrations | `alembic.ini` |
| **Pre-commit** | Git hook automation | `.pre-commit-config.yaml` |

---

## 3. Development Environment Setup

### 3.1 Prerequisites

Before starting, ensure you have:

| Tool | Minimum Version | Installation |
|------|----------------|--------------|
| Python | 3.11 | [python.org](https://python.org) or `pyenv` |
| Node.js | 20 LTS | [nodejs.org](https://nodejs.org) or `nvm` |
| Flutter | 3.19 | [flutter.dev](https://flutter.dev) (mobile dev) |
| Docker | 24.0 | [docker.com](https://docker.com) |
| Docker Compose | 2.20 | Included with Docker Desktop |
| Git | 2.40 | [git-scm.com](https://git-scm.com) |
| Make | 4.3 | System package manager |
| PostgreSQL Client | 16 | `psql` for local debugging |
| Redis CLI | 7 | For cache inspection |

### 3.2 Repository Clone

```bash
# Clone the monorepo
git clone git@github.com:ribdigi/ribdigi-erp.git
cd ribdigi-erp

# Initialize git hooks
make init
```

### 3.3 Backend Environment Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment file
cp .env.example .env

# Edit .env with your local settings
# See Section 3.5 for required variables

# Install pre-commit hooks
pre-commit install
```

### 3.4 Frontend Environment Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Run development server
npm run dev
```

### 3.5 Required Environment Variables

Create `.env` files in respective directories:

**Backend (`backend/.env`):**
```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ribdigi_dev
DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/ribdigi_test

# Redis
REDIS_URL=redis://localhost:6379/0

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672

# Security
JWT_SECRET_KEY=dev-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Storage
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=ribdigi-dev

# AI
AI_MODEL_PATH=./ai/models

# App
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

**Frontend (`frontend/.env.local`):**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=RIBDIGI ERP
NEXT_PUBLIC_APP_VERSION=1.0.0
```

### 3.6 Docker Compose (Full Stack)

For the fastest setup, use Docker Compose to run all infrastructure:

```bash
# From project root
docker-compose -f docker-compose.dev.yml up -d

# Services started:
# - PostgreSQL on port 5432
# - Redis on port 6379
# - RabbitMQ on port 5672 (management: 15672)
# - MinIO on port 9000 (console: 9001)
```

**Verify services:**
```bash
make healthcheck
# Or manually:
docker-compose -f docker-compose.dev.yml ps
```

---

## 4. Project Structure

### 4.1 Monorepo Layout

```
ribdigi-erp/
├── README.md
├── Makefile                          # Common development commands
├── docker-compose.yml                # Production orchestration
├── docker-compose.dev.yml            # Local development stack
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Pull request checks
│       ├── backend-deploy.yml        # Backend deployment
│       ├── frontend-deploy.yml       # Frontend deployment
│       └── release.yml               # Release automation
│
├── backend/                          # FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # Application entry point
│   │   ├── config.py                 # Pydantic settings management
│   │   ├── dependencies.py           # FastAPI dependencies (DB, auth, tenant)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── security.py           # JWT, password hashing, encryption
│   │   │   ├── middleware.py         # Tenant resolution, logging, CORS
│   │   │   ├── exceptions.py         # Custom exception classes
│   │   │   └── logging.py            # Structured JSON logging
│   │   ├── domains/                  # DDD modules (one per business domain)
│   │   │   ├── __init__.py
│   │   │   ├── inventory/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── models.py         # SQLAlchemy models
│   │   │   │   ├── schemas.py        # Pydantic request/response schemas
│   │   │   │   ├── repository.py     # Data access layer
│   │   │   │   ├── service.py        # Business logic
│   │   │   │   ├── router.py         # FastAPI route definitions
│   │   │   │   ├── tasks.py          # Celery background tasks
│   │   │   │   └── constants.py      # Domain constants
│   │   │   ├── sales/
│   │   │   ├── purchasing/
│   │   │   ├── accounting/
│   │   │   ├── users/
│   │   │   ├── pos/
│   │   │   └── ai/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   └── router.py         # API version aggregator
│   │   │   └── deps.py               # Shared API dependencies
│   │   ├── models/                   # Cross-domain base models
│   │   │   ├── __init__.py
│   │   │   └── base.py               # Base SQLAlchemy declarative base
│   │   ├── schemas/                  # Shared Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── common.py             # Pagination, response wrappers
│   │   │   └── enums.py              # Shared enumerations
│   │   ├── services/                 # Cross-domain services
│   │   │   ├── __init__.py
│   │   │   ├── email.py              # Email service
│   │   │   ├── storage.py            # S3/MinIO file storage
│   │   │   └── notification.py       # Multi-channel notifications
│   │   └── workers/
│   │       ├── __init__.py
│   │       └── celery_app.py         # Celery application factory
│   ├── alembic/                      # Database migrations
│   │   ├── versions/                 # Migration scripts
│   │   ├── env.py                    # Alembic environment
│   │   └── script.py.mako            # Migration template
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py               # Pytest fixtures and configuration
│   │   ├── unit/                     # Unit tests (no DB)
│   │   ├── integration/              # Integration tests (with DB)
│   │   └── e2e/                      # End-to-end API tests
│   ├── ai/
│   │   ├── models/                   # Serialized ML models
│   │   ├── pipelines/                # Feature engineering scripts
│   │   ├── notebooks/                # Jupyter exploration (not in prod)
│   │   └── api/                      # AI service FastAPI sub-app
│   ├── scripts/
│   │   ├── init_tenant.py            # Tenant database initialization
│   │   ├── seed_data.py              # Development seed data
│   │   └── backup.py                 # Backup utility
│   ├── Dockerfile
│   ├── requirements.txt              # Production dependencies
│   ├── requirements-dev.txt          # Development dependencies
│   └── pyproject.toml                # Project metadata, tool configs
│
├── frontend/                         # Next.js application
│   ├── src/
│   │   ├── app/                      # Next.js App Router
│   │   │   ├── (auth)/               # Auth group routes
│   │   │   ├── (dashboard)/          # Main app routes
│   │   │   ├── api/                  # Next.js API routes (proxies)
│   │   │   └── layout.tsx            # Root layout
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui components
│   │   │   ├── forms/                # Reusable form components
│   │   │   ├── tables/               # Data table components
│   │   │   └── charts/               # Recharts/D3 visualizations
│   │   ├── hooks/
│   │   │   ├── useAuth.ts            # Authentication hook
│   │   │   ├── useApi.ts             # API client hook
│   │   │   └── useTenant.ts          # Tenant context hook
│   │   ├── lib/
│   │   │   ├── api-client.ts         # Axios/Fetch API client
│   │   │   ├── utils.ts              # Utility functions
│   │   │   └── constants.ts          # Frontend constants
│   │   ├── stores/                   # Zustand state management
│   │   │   ├── authStore.ts
│   │   │   ├── tenantStore.ts
│   │   │   └── uiStore.ts
│   │   ├── types/
│   │   │   └── index.ts              # TypeScript type definitions
│   │   └── styles/
│   │       └── globals.css
│   ├── public/
│   ├── tests/
│   │   ├── unit/
│   │   └── e2e/                      # Playwright tests
│   ├── Dockerfile
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── package.json
│
├── mobile/                           # Flutter application
│   ├── android/
│   ├── ios/
│   ├── lib/
│   │   ├── main.dart
│   │   ├── app.dart
│   │   ├── core/
│   │   │   ├── constants.dart
│   │   │   ├── theme.dart
│   │   │   └── router.dart
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── dashboard/
│   │   │   ├── inventory/
│   │   │   ├── sales/
│   │   │   └── pos/
│   │   ├── models/
│   │   ├── services/
│   │   │   └── api_service.dart
│   │   └── widgets/
│   ├── test/
│   └── pubspec.yaml
│
├── k8s/                              # Kubernetes manifests
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secret-template.yaml
│   │   ├── postgres.yaml
│   │   ├── redis.yaml
│   │   ├── rabbitmq.yaml
│   │   ├── backend.yaml
│   │   ├── frontend.yaml
│   │   ├── celery-worker.yaml
│   │   ├── celery-beat.yaml
│   │   └── ingress.yaml
│   └── overlays/
│       ├── development/
│       ├── staging/
│       └── production/
│
└── docs/                             # Additional documentation
    ├── architecture/
    ├── database/
    └── api/
```

### 4.2 Domain-Driven Design (DDD) Structure

Each business domain follows this internal structure:

```
domains/inventory/
├── __init__.py           # Domain exports
├── models.py             # SQLAlchemy ORM models
│   ├── Product
│   ├── Category
│   ├── Brand
│   ├── StockMovement
│   └── Warehouse
├── schemas.py            # Pydantic validation schemas
│   ├── ProductCreate
│   ├── ProductUpdate
│   ├── ProductResponse
│   └── ProductListParams
├── repository.py         # Data access abstraction
│   ├── ProductRepository
│   └── StockRepository
├── service.py            # Business logic
│   ├── ProductService
│   └── InventoryService
├── router.py             # HTTP route handlers
│   ├── POST /products
│   ├── GET /products
│   ├── GET /products/{id}
│   ├── PUT /products/{id}
│   └── DELETE /products/{id}
├── tasks.py              # Celery background jobs
│   └── generate_low_stock_alerts
└── constants.py          # Domain-specific constants
    └── DEFAULT_REORDER_DAYS
```

**Design Rules:**
- **Models** know nothing about HTTP, schemas, or services
- **Schemas** validate input/output but contain no business logic
- **Repository** handles all database queries; services don't use `Session.query()` directly
- **Service** contains business rules, orchestrates repositories, triggers tasks
- **Router** only handles HTTP concerns: parsing requests, calling services, returning responses
- **Tasks** are idempotent and retry-safe

---

## 5. Coding Standards

### 5.1 Python Standards (Backend)

#### Style & Formatting

We use **Ruff** for linting and formatting (replaces Flake8, Black, isort):

```toml
# pyproject.toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

**Key Rules:**
- Maximum line length: **100 characters**
- Use **double quotes** for strings
- Import order: stdlib → third-party → first-party → local
- Type hints are **mandatory** for all function signatures
- Docstrings: Google style

#### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| **Modules** | `snake_case` | `product_service.py` |
| **Classes** | `PascalCase` | `ProductService` |
| **Functions** | `snake_case` | `get_product_by_id()` |
| **Variables** | `snake_case` | `product_list` |
| **Constants** | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE` |
| **Private** | `_leading_underscore` | `_internal_helper()` |
| **Abstract** | `Base` prefix | `BaseRepository` |
| **Exceptions** | `Error` suffix | `ProductNotFoundError` |

#### Type Hints

```python
from typing import Optional, List
from uuid import UUID

# Correct
def get_product(
    product_id: UUID,
    tenant_id: UUID,
    include_inactive: bool = False,
) -> Optional[Product]:
    """Retrieve a single product by ID.

    Args:
        product_id: The unique product identifier.
        tenant_id: The tenant context for data isolation.
        include_inactive: Whether to include soft-deleted products.

    Returns:
        The product if found, None otherwise.

    Raises:
        ProductNotFoundError: If product does not exist and include_inactive is False.
    """
    ...

# Incorrect — missing types
def get_product(product_id, tenant_id, include_inactive=False):
    ...
```

#### Error Handling

```python
from fastapi import HTTPException
from app.core.exceptions import BusinessRuleError

# Business errors -> Custom exceptions (caught by middleware)
if product.stock_quantity < 0:
    raise BusinessRuleError(
        code="INSUFFICIENT_STOCK",
        message=f"Cannot sell {quantity} units. Only {product.stock_quantity} available.",
        details={"product_id": str(product.id), "requested": quantity},
    )

# HTTP errors -> Only in routers (never in services)
@router.get("/products/{product_id}")
async def get_product_endpoint(product_id: UUID, service: ProductService = Depends()):
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
```

### 5.2 TypeScript Standards (Frontend)

#### Style & Formatting

```json
// .prettierrc
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false
}
```

**Key Rules:**
- Use **single quotes** for strings
- Semicolons: **required**
- Trailing commas: **es5** style
- Explicit return types on exported functions
- No `any` type (use `unknown` with type guards)

#### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| **Components** | `PascalCase` | `ProductCard.tsx` |
| **Hooks** | `use` prefix + `PascalCase` | `useProductList.ts` |
| **Types/Interfaces** | `PascalCase` | `ProductCreateInput` |
| **Variables** | `camelCase` | `productList` |
| **Constants** | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE` |
| **Files** | `kebab-case` | `product-service.ts` |

#### Component Structure

```tsx
// Correct — typed props, explicit return, clean separation
import { Product } from '@/types';
import { Card } from '@/components/ui/card';

interface ProductCardProps {
  product: Product;
  onEdit: (id: string) => void;
  isLoading?: boolean;
}

export function ProductCard({ product, onEdit, isLoading = false }: ProductCardProps): JSX.Element {
  if (isLoading) {
    return <ProductCardSkeleton />;
  }

  return (
    <Card className="p-4">
      <h3 className="text-lg font-semibold">{product.name}</h3>
      <p className="text-gray-600">{product.sku}</p>
      <button onClick={() => onEdit(product.id)}>Edit</button>
    </Card>
  );
}

// Incorrect — implicit any, inline styles, no types
function ProductCard(props) {
  return <div style={{padding: 16}}>{props.product.name}</div>;
}
```

### 5.3 SQLAlchemy Standards

#### Model Definition

```python
from uuid import uuid4
from sqlalchemy import String, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, TimestampMixin

class Product(BaseModel, TimestampMixin):
    """Represents a product in the catalog."""

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_tenant_id", "tenant_id"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_sku", "tenant_id", "sku", unique=True),
    )

    # Primary key — always UUID
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Tenant isolation — every table must have this
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)

    # Business fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Foreign keys
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)

    # Relationships
    category: Mapped["Category"] = relationship(back_populates="products")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="product")

    # Soft delete
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

**Model Rules:**
- Always use `Mapped[]` and `mapped_column()` (SQLAlchemy 2.0 style)
- Every table must have `tenant_id` for multi-tenancy
- Primary keys are always `UUID` (never auto-increment integers)
- Use `Numeric` for money (never `Float`)
- Include `created_at` and `updated_at` via `TimestampMixin`
- Use soft delete (`is_active` + `deleted_at`) instead of hard delete
- Define indexes for all foreign keys and frequently queried columns
- Always include `__table_args__` for composite indexes and constraints

### 5.4 Dart Standards (Mobile)

```yaml
# analysis_options.yaml
include: package:flutter_lints/flutter.yaml

linter:
  rules:
    prefer_single_quotes: true
    always_specify_types: true
    avoid_print: true
    prefer_const_constructors: true
```

---

## 6. Git Workflow

### 6.1 Branching Strategy

We follow **GitHub Flow** with environment branches:

```
main (production)
  ^
  |   PR #123 (squash merge)
  |   +-----------------+
  +---+ feature/INV-42  |
      |  (from main)    |
      +-----------------+
            ^
            |   PR #122 (squash merge)
            |   +-----------------+
            +---+ feature/POS-15  |
                |  (from main)    |
                +-----------------+
```

**Branch Types:**

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New functionality | `feature/INV-42-low-stock-prediction` |
| `bugfix/` | Bug fixes | `bugfix/POS-15-receipt-print-error` |
| `hotfix/` | Production critical fixes | `hotfix/SEC-01-auth-bypass` |
| `release/` | Release preparation | `release/v1.2.0` |
| `docs/` | Documentation only | `docs/api-auth-examples` |
| `refactor/` | Code restructuring | `refactor/inventory-repository` |

### 6.2 Commit Message Convention

We use **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
| Type | Use When |
|------|----------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Code style (formatting, no logic change) |
| `refactor` | Code restructuring |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `chore` | Build, CI, dependencies |
| `security` | Security-related changes |

**Examples:**
```
feat(inventory): add AI low stock prediction endpoint

Implement Prophet-based forecasting for inventory levels.
- Adds /api/v1/ai/inventory/predict endpoint
- Includes 7-day and 30-day horizon predictions
- Returns confidence intervals

Closes #INV-42
```

```
fix(pos): resolve cash drawer not opening on card payment

The cash drawer trigger was incorrectly tied to payment method
check instead of drawer configuration flag.

Fixes #POS-15
```

### 6.3 Pull Request Process

1. **Before Creating PR:**
   ```bash
   git checkout main
   git pull origin main
   git checkout feature/XYZ-123
   git rebase main
   # Resolve conflicts if any
   ```

2. **Create PR:**
   - Title follows commit convention: `feat(inventory): add low stock prediction`
   - Fill PR template:
     - Description of changes
     - Link to related issue: `Closes #XYZ-123`
     - Screenshots (for UI changes)
     - Testing instructions
     - Checklist:
       - [ ] Code follows style guide
       - [ ] Tests added/updated
       - [ ] Documentation updated
       - [ ] No breaking changes (or documented)

3. **Code Review Requirements:**
   - Minimum **2 approvals** for backend changes
   - Minimum **1 approval** for frontend changes
   - **All CI checks must pass**
   - No unresolved conversations

4. **Merge:**
   - Use **Squash and Merge** for feature branches
   - Use **Merge Commit** for release branches
   - Delete branch after merge

### 6.4 Release Process

```bash
# 1. Create release branch
git checkout -b release/v1.2.0

# 2. Update version
# backend/pyproject.toml -> version = "1.2.0"
# frontend/package.json -> "version": "1.2.0"

# 3. Update CHANGELOG.md

# 4. Create PR to main
# ... review and merge ...

# 5. Tag release
git checkout main
git pull origin main
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0

# 6. GitHub Actions triggers deployment
```

---

## 7. Architecture Overview

### 7.1 High-Level Architecture

```
+---------------------------------------------------------------------+
|                         CLIENT LAYER                                 |
|  +--------------+  +--------------+  +--------------------------+  |
|  |   React Web  |  |  Mobile App  |  |  Third-Party Integrations|  |
|  |   (Next.js)  |  |(Flutter/RN)  |  |  (API Consumers)         |  |
|  +------+-------+  +------+-------+  +------------+-------------+  |
+--------+---------+----------+--------+-------------+---------------+
          |                 |                       |
          +-----------------+-----------------------+
                            | HTTPS / REST / JSON
+---------------------------+-----------------------------------------+
|                      API GATEWAY / INGRESS                           |
|         (Nginx / Traefik — SSL termination, rate limiting)           |
+---------------------------+-----------------------------------------+
                            |
+---------------------------+-----------------------------------------+
|                    APPLICATION LAYER (FastAPI)                       |
|  +---------------------------------------------------------------+  |
|  |  API Router -> Service -> Repository -> SQLAlchemy -> PostgreSQL |  |
|  |  Auth Middleware -> JWT Validation -> Tenant Resolution -> RBAC   |  |
|  +---------------------------------------------------------------+  |
|  +---------------------------------------------------------------+  |
|  |  Celery Workers (Background Jobs)                             |  |
|  |  - Email sending                                              |  |
|  |  - Report generation                                          |  |
|  |  - AI model inference                                         |  |
|  |  - Scheduled tasks (backup, notifications)                    |  |
|  +---------------------------------------------------------------+  |
+---------------------------+-----------------------------------------+
                            |
        +-------------------+-------------------+
        |                   |                   |
+-------+-------+  +--------+--------+  +------+------+
|    Redis     |  |    RabbitMQ     |  |    MinIO    |
|   (Cache)    |  |   (Task Queue)  |  |  (Storage)  |
+--------------+  +-----------------+  +-------------+
```

### 7.2 Multi-Tenancy Architecture

**Strategy: Database-per-Tenant (Schema Isolation)**

```
PostgreSQL Server
+-- Database: ribdigi_platform
|   +-- Table: tenants
|   +-- Table: subscriptions
|   +-- Table: global_audit_logs
|
+-- Database: tenant_abc_pharma
|   +-- Schema: public
|   |   +-- Table: products
|   |   +-- Table: customers
|   |   +-- Table: sales_invoices
|   |   +-- ... (all business tables)
|
+-- Database: tenant_xyz_retail
|   +-- Schema: public
|   |   +-- Table: products
|   |   +-- Table: customers
|   |   +-- ...
```

**Tenant Resolution Flow:**
1. Request arrives at `https://abcpharma.ribdigi.com`
2. Nginx extracts subdomain -> `abcpharma`
3. FastAPI middleware looks up `abcpharma` in `tenants` table
4. Retrieves `tenant_id` and database connection string
5. Creates SQLAlchemy session bound to tenant database
6. All subsequent queries use this isolated session
7. JWT token also contains `tenant_id` for defense-in-depth validation

### 7.3 Domain Boundaries

```
+-------------------------------------------------------------+
|                      CORE DOMAINS                            |
+-------------+-------------+-------------+-----------------+
|  Inventory  |    Sales    | Purchasing  |   Accounting    |
|  (Products, |  (Customers,|  (Suppliers,|  (COA, Journal, |
|   Stock,    |   Invoices, |   PO, GRN,  |   AR, AP,       |
|   Warehouse)|   POS)      |   Invoices) |   Reports)      |
+-------------+-------------+-------------+-----------------+
|    Users    |   Expenses  |  Multi-Store|  AI Assistant   |
|  (Auth,     |  (Categories|  (Branches, |  (Chat,         |
|   Roles,    |   Entries,  |   Stores,   |   Predictions,  |
|   Perms)    |   Approval) |   Transfers)|   Insights)     |
+-------------+-------------+-------------+-----------------+

Cross-Cutting Concerns:
+-- Security (Auth, RBAC, Audit)
+-- Notifications (Email, SMS, In-App)
+-- Storage (S3/MinIO file handling)
+-- Caching (Redis query cache)
+-- Logging (Structured JSON logs)
```

---

## 8. Backend Development

### 8.1 FastAPI Application Structure

**Entry Point (`app/main.py`):**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.middleware import TenantMiddleware, LoggingMiddleware
from app.api.v1.router import api_router
from app.workers.celery_app import celery_app

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db_pool()
    await verify_storage_connection()
    yield
    # Shutdown
    await close_db_pool()

app = FastAPI(
    title="RIBDIGI ERP API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Middleware (order matters!)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(api_router, prefix="/api/v1")
```

### 8.2 Dependency Injection Pattern

```python
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_current_user, get_tenant_context
from app.domains.inventory.service import ProductService
from app.domains.inventory.repository import ProductRepository

# Correct — inject dependencies, no global state
@router.get("/products")
async def list_products(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    tenant: TenantContext = Depends(get_tenant_context),
    current_user: User = Depends(get_current_user),
    service: ProductService = Depends(),
):
    """List products for the current tenant."""
    return await service.list_products(
        db=db,
        tenant_id=tenant.id,
        user=current_user,
    )

# Service with repository injection
class ProductService:
    def __init__(self, repo: ProductRepository = Depends()):
        self.repo = repo

    async def list_products(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        user: User,
    ) -> PaginatedResponse[Product]:
        ...
```

### 8.3 Service Layer Pattern

```python
from uuid import UUID
from typing import Optional
from app.core.exceptions import BusinessRuleError
from app.domains.inventory.schemas import ProductCreate, ProductUpdate, ProductResponse

class ProductService:
    """Business logic for product management."""

    def __init__(self, repo: ProductRepository):
        self.repo = repo

    async def create_product(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data: ProductCreate,
        created_by: UUID,
    ) -> ProductResponse:
        """Create a new product with business rule validation."""

        # Business rule: SKU must be unique per tenant
        existing = await self.repo.get_by_sku(db, tenant_id, data.sku)
        if existing:
            raise BusinessRuleError(
                code="DUPLICATE_SKU",
                message=f"Product with SKU '{data.sku}' already exists.",
            )

        # Business rule: Selling price must be >= cost price
        if data.selling_price < data.cost_price:
            raise BusinessRuleError(
                code="INVALID_PRICING",
                message="Selling price cannot be less than cost price.",
            )

        # Create entity
        product = Product(
            tenant_id=tenant_id,
            created_by=created_by,
            **data.model_dump(),
        )

        await self.repo.create(db, product)
        await db.commit()

        # Background task: Generate barcode if missing
        if not product.barcode:
            generate_barcode.delay(product.id)

        return ProductResponse.model_validate(product)
```

### 8.4 Repository Pattern

```python
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class ProductRepository:
    """Data access layer for products."""

    async def get_by_id(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        product_id: UUID,
    ) -> Optional[Product]:
        stmt = (
            select(Product)
            .where(
                and_(
                    Product.id == product_id,
                    Product.tenant_id == tenant_id,
                    Product.is_active == True,
                )
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sku(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        sku: str,
    ) -> Optional[Product]:
        stmt = (
            select(Product)
            .where(
                and_(
                    Product.tenant_id == tenant_id,
                    Product.sku == sku,
                    Product.is_active == True,
                )
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_products(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        filters: ProductListFilter,
        pagination: PaginationParams,
    ) -> tuple[List[Product], int]:
        """Return (products, total_count)."""
        where_clauses = [
            Product.tenant_id == tenant_id,
            Product.is_active == True,
        ]

        if filters.category_id:
            where_clauses.append(Product.category_id == filters.category_id)
        if filters.search:
            where_clauses.append(
                Product.name.ilike(f"%{filters.search}%")
            )

        # Count query
        count_stmt = select(func.count()).select_from(Product).where(and_(*where_clauses))
        total = await db.scalar(count_stmt)

        # Data query
        stmt = (
            select(Product)
            .where(and_(*where_clauses))
            .order_by(Product.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all(), total
```

---

## 9. Frontend Development

### 9.1 Next.js App Router Structure

```
frontend/src/app/
+-- (auth)/                    # Route group — no sidebar layout
|   +-- login/
|   |   +-- page.tsx
|   +-- forgot-password/
|   +-- reset-password/
|
+-- (dashboard)/               # Route group — with sidebar layout
|   +-- layout.tsx             # Dashboard shell with sidebar + topbar
|   +-- page.tsx               # Dashboard home (redirects to /dashboard)
|   +-- dashboard/
|   |   +-- page.tsx           # Executive dashboard
|   +-- inventory/
|   |   +-- products/
|   |   |   +-- page.tsx       # Product list
|   |   |   +-- [id]/
|   |   |       +-- page.tsx   # Product detail/edit
|   |   +-- stock-in/
|   |   +-- stock-out/
|   |   +-- warehouses/
|   +-- sales/
|   |   +-- customers/
|   |   +-- invoices/
|   |   +-- quotations/
|   +-- pos/
|   |   +-- page.tsx           # POS interface (full screen)
|   +-- settings/
|       +-- page.tsx
|
+-- api/                       # Next.js API routes (if needed)
+-- layout.tsx                 # Root layout (providers, fonts)
```

### 9.2 API Client Setup

```typescript
// src/lib/api-client.ts
import axios, { AxiosError, AxiosInstance } from 'axios';
import { useAuthStore } from '@/stores/authStore';

const apiClient: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach JWT token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest) {
      // Attempt token refresh
      const newToken = await useAuthStore.getState().refreshToken();
      if (newToken) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }

      // Refresh failed — redirect to login
      window.location.href = '/login';
    }

    return Promise.reject(error);
  }
);

export default apiClient;
```

### 9.3 Data Fetching Pattern

```typescript
// src/hooks/useProducts.ts
import useSWR from 'swr';
import apiClient from '@/lib/api-client';
import { Product, PaginatedResponse } from '@/types';

interface UseProductsOptions {
  page?: number;
  limit?: number;
  search?: string;
  categoryId?: string;
}

export function useProducts(options: UseProductsOptions = {}) {
  const { page = 1, limit = 20, search, categoryId } = options;

  const queryParams = new URLSearchParams();
  queryParams.set('page', String(page));
  queryParams.set('limit', String(limit));
  if (search) queryParams.set('search', search);
  if (categoryId) queryParams.set('category_id', categoryId);

  const { data, error, isLoading, mutate } = useSWR<PaginatedResponse<Product>>(
    `/api/v1/products?${queryParams.toString()}`,
    (url: string) => apiClient.get(url).then((res) => res.data),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    }
  );

  return {
    products: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    mutate,
  };
}
```

### 9.4 Form Handling

```tsx
// src/components/forms/ProductForm.tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const productSchema = z.object({
  name: z.string().min(1, 'Product name is required').max(255),
  sku: z.string().min(1, 'SKU is required').max(100),
  costPrice: z.number().positive('Cost price must be positive'),
  sellingPrice: z.number().positive('Selling price must be positive'),
  categoryId: z.string().uuid('Category is required'),
});

type ProductFormData = z.infer<typeof productSchema>;

interface ProductFormProps {
  initialData?: Partial<ProductFormData>;
  onSubmit: (data: ProductFormData) => Promise<void>;
}

export function ProductForm({ initialData, onSubmit }: ProductFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ProductFormData>({
    resolver: zodResolver(productSchema),
    defaultValues: initialData,
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <label htmlFor="name">Product Name</label>
        <input id="name" {...register('name')} className="input" />
        {errors.name && <span className="error">{errors.name.message}</span>}
      </div>

      <div>
        <label htmlFor="sku">SKU</label>
        <input id="sku" {...register('sku')} className="input" />
        {errors.sku && <span className="error">{errors.sku.message}</span>}
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Saving...' : 'Save Product'}
      </button>
    </form>
  );
}
```

---

## 10. AI/ML Pipeline Development

### 10.1 AI Service Architecture

The AI capabilities run as a separate FastAPI sub-application within the backend:

```
backend/ai/
+-- api/
|   +-- main.py              # AI service entry point
|   +-- router.py            # /api/v1/ai/* routes
|   +-- deps.py              # AI service dependencies
+-- models/                  # Serialized models (pickle/joblib)
|   +-- inventory_forecaster.pkl
|   +-- sales_prophet.pkl
|   +-- expense_anomaly.pkl
+-- pipelines/
|   +-- inventory_pipeline.py
|   +-- sales_pipeline.py
|   +-- expense_pipeline.py
+-- notebooks/
    +-- exploration/         # Jupyter notebooks (gitignored in prod)
```

### 10.2 Model Training Pipeline

```python
# backend/ai/pipelines/inventory_pipeline.py
import pandas as pd
from prophet import Prophet
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.repository import StockRepository

class InventoryForecastingPipeline:
    """Train and inference pipeline for inventory demand forecasting."""

    async def fetch_training_data(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        product_id: UUID,
        days_history: int = 365,
    ) -> pd.DataFrame:
        """Fetch historical stock movements for training."""
        movements = await StockRepository().get_movement_history(
            db, tenant_id, product_id, days=days_history
        )

        df = pd.DataFrame(movements)
        df['ds'] = pd.to_datetime(df['date'])
        df['y'] = df['quantity_sold']
        return df[['ds', 'y']]

    def train_model(self, df: pd.DataFrame) -> Prophet:
        """Train Prophet model on historical data."""
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.85,
        )
        model.fit(df)
        return model

    def predict(self, model: Prophet, days: int = 14) -> pd.DataFrame:
        """Generate forecast for specified days."""
        future = model.make_future_dataframe(periods=days)
        forecast = model.predict(future)
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(days)

    async def generate_alert(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        product_id: UUID,
    ) -> dict:
        """Generate low stock prediction alert."""
        df = await self.fetch_training_data(db, tenant_id, product_id)

        if len(df) < 30:
            return {"status": "insufficient_data", "message": "Need 30+ days of history"}

        model = self.train_model(df)
        forecast = self.predict(model, days=14)

        # Get current stock
        current_stock = await StockRepository().get_current_stock(db, tenant_id, product_id)

        # Find predicted stockout date
        stockout_date = None
        for _, row in forecast.iterrows():
            if row['yhat'] > current_stock:
                stockout_date = row['ds']
                break

        return {
            "product_id": str(product_id),
            "current_stock": current_stock,
            "predicted_stockout_date": stockout_date.isoformat() if stockout_date else None,
            "confidence": 0.85,
            "recommended_order_quantity": int(forecast['yhat'].sum() * 1.2),
        }
```

### 10.3 Background AI Tasks

```python
# backend/app/domains/inventory/tasks.py
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from backend.ai.pipelines.inventory_pipeline import InventoryForecastingPipeline

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_low_stock_predictions(self, tenant_id: str):
    """Daily background task to generate low stock predictions."""
    try:
        pipeline = InventoryForecastingPipeline()

        # Get all products near reorder level
        products = get_low_stock_products(tenant_id)

        for product in products:
            prediction = pipeline.generate_alert(
                db=get_db_session(),
                tenant_id=UUID(tenant_id),
                product_id=product.id,
            )

            if prediction.get("predicted_stockout_date"):
                # Create notification
                create_notification.delay(
                    tenant_id=tenant_id,
                    type="AI_LOW_STOCK_PREDICTION",
                    title=f"Predicted stockout: {product.name}",
                    message=f"Stockout predicted by {prediction['predicted_stockout_date']}",
                    recipients=["inventory_officer", "store_manager"],
                )

    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc)
```

---

## 11. Database & Migrations

### 11.1 Migration Workflow

We use **Alembic** for database migrations:

```bash
# 1. Make model changes in domains/*/models.py

# 2. Auto-generate migration
make migration MSG="add_product_expiry_fields"
# Or:
cd backend && alembic revision --autogenerate -m "add_product_expiry_fields"

# 3. Review generated migration file in alembic/versions/
#    - Ensure tenant_id is included in new tables
#    - Verify index definitions
#    - Check for data migrations (separate if needed)

# 4. Apply migration locally
make migrate
# Or:
cd backend && alembic upgrade head

# 5. Run tests to verify
make test

# 6. Commit migration file with feature code
```

### 11.2 Writing Safe Migrations

```python
"""add_product_expiry_fields

Revision ID: 20240807_add_expiry
Revises: 20240801_init
Create Date: 2026-08-07 12:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20240807_add_expiry'
down_revision = '20240801_init'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns with defaults for existing rows
    op.add_column(
        'products',
        sa.Column('batch_number', sa.String(100), nullable=True),
    )
    op.add_column(
        'products',
        sa.Column('expiry_date', sa.Date(), nullable=True),
    )
    op.add_column(
        'products',
        sa.Column('manufacturing_date', sa.Date(), nullable=True),
    )

    # Add index for expiry queries (common in pharmacy)
    op.create_index(
        'ix_products_expiry_date',
        'products',
        ['tenant_id', 'expiry_date'],
    )


def downgrade():
    op.drop_index('ix_products_expiry_date', table_name='products')
    op.drop_column('products', 'manufacturing_date')
    op.drop_column('products', 'expiry_date')
    op.drop_column('products', 'batch_number')
```

**Migration Rules:**
- Always include `downgrade()` function
- Never drop data in upgrade without backup step
- For destructive changes, create data migration scripts separately
- Index creation should be `CONCURRENTLY` in production (use `op.execute()` with raw SQL)
- Test migrations on a copy of production data before deploying

### 11.3 Multi-Tenant Migration Strategy

Migrations run per-tenant database. The migration runner:

```python
# scripts/migrate_all_tenants.py
from app.config import settings
from app.models.base import engine_factory

async def migrate_all_tenants():
    """Apply migrations to all tenant databases."""
    tenants = await get_all_active_tenants()

    for tenant in tenants:
        engine = engine_factory(tenant.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(alembic_upgrade, "head")

        logger.info(f"Migrated tenant: {tenant.name}")
```

---

## 12. Testing Strategy

### 12.1 Testing Pyramid

```
        +---------+
        |   E2E   |  <- Playwright (frontend flows)
        |  ~5%    |
       ++---------++
       | Integration |  <- API tests with real DB
       |   ~15%    |
      ++-----------++
      |    Unit       |  <- Business logic, no DB
      |    ~80%      |
      +---------------+
```

### 12.2 Unit Tests

```python
# backend/tests/unit/inventory/test_product_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.domains.inventory.service import ProductService
from app.domains.inventory.schemas import ProductCreate
from app.core.exceptions import BusinessRuleError

@pytest.fixture
def mock_repo():
    return AsyncMock()

@pytest.fixture
def service(mock_repo):
    return ProductService(repo=mock_repo)

@pytest.mark.asyncio
async def test_create_product_with_duplicate_sku(service, mock_repo):
    """Should reject duplicate SKU within tenant."""
    # Arrange
    tenant_id = uuid4()
    existing_product = MagicMock(sku="DUPLICATE-SKU")
    mock_repo.get_by_sku.return_value = existing_product

    data = ProductCreate(
        name="Test Product",
        sku="DUPLICATE-SKU",
        cost_price=10.00,
        selling_price=15.00,
        category_id=uuid4(),
    )

    # Act & Assert
    with pytest.raises(BusinessRuleError) as exc_info:
        await service.create_product(
            db=AsyncMock(),
            tenant_id=tenant_id,
            data=data,
            created_by=uuid4(),
        )

    assert exc_info.value.code == "DUPLICATE_SKU"

@pytest.mark.asyncio
async def test_create_product_with_invalid_pricing(service, mock_repo):
    """Should reject selling price below cost price."""
    mock_repo.get_by_sku.return_value = None

    data = ProductCreate(
        name="Test Product",
        sku="VALID-SKU",
        cost_price=10.00,
        selling_price=8.00,  # Invalid!
        category_id=uuid4(),
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await service.create_product(
            db=AsyncMock(),
            tenant_id=uuid4(),
            data=data,
            created_by=uuid4(),
        )

    assert exc_info.value.code == "INVALID_PRICING"
```

### 12.3 Integration Tests

```python
# backend/tests/integration/test_products_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_product_endpoint(client: AsyncClient, auth_headers):
    """Should create product via API and persist to database."""
    payload = {
        "name": "Integration Test Product",
        "sku": "INT-TEST-001",
        "cost_price": 10.00,
        "selling_price": 15.00,
        "category_id": str(test_category_id),
    }

    response = await client.post(
        "/api/v1/products",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["sku"] == payload["sku"]
    assert "id" in data

    # Verify in database
    product = await get_product_from_db(data["id"])
    assert product is not None
    assert product.tenant_id == test_tenant_id
```

### 12.4 E2E Tests (Frontend)

```typescript
// frontend/tests/e2e/pos.spec.ts
import { test, expect } from '@playwright/test';

test.describe('POS Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="email"]', 'cashier@example.com');
    await page.fill('[name="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });

  test('complete cash sale', async ({ page }) => {
    // Navigate to POS
    await page.click('text=POS');
    await page.waitForURL('/pos');

    // Open shift
    await page.click('text=Open Shift');
    await page.fill('[name="opening_float"]', '200');
    await page.click('text=Confirm');

    // Add product to cart
    await page.fill('[placeholder="Search product..."]', 'Test Product');
    await page.click('text=Test Product');

    // Process payment
    await page.click('text=Pay');
    await page.click('text=Cash');
    await page.fill('[name="amount_received"]', '50');
    await page.click('text=Complete Sale');

    // Verify receipt
    await expect(page.locator('text=Receipt')).toBeVisible();
    await expect(page.locator('text=Change: $')).toBeVisible();
  });
});
```

### 12.5 Running Tests

```bash
# Backend tests
make test                    # Run all backend tests
make test-unit              # Unit tests only
make test-integration       # Integration tests only
make test-coverage          # With coverage report

# Frontend tests
npm run test                # Unit tests (Vitest)
npm run test:e2e           # E2E tests (Playwright)

# Mobile tests
flutter test                # Run all Dart tests
```

### 12.6 Test Data Fixtures

```python
# backend/tests/conftest.py
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models import Product, Category

@pytest_asyncio.fixture
async def test_category(db: AsyncSession, test_tenant_id):
    """Create a test category."""
    category = Category(
        tenant_id=test_tenant_id,
        name="Test Category",
        code="TEST-CAT",
    )
    db.add(category)
    await db.commit()
    return category

@pytest_asyncio.fixture
async def test_product(db: AsyncSession, test_tenant_id, test_category):
    """Create a test product."""
    product = Product(
        tenant_id=test_tenant_id,
        category_id=test_category.id,
        name="Test Product",
        sku="TEST-001",
        cost_price=10.00,
        selling_price=15.00,
        is_active=True,
    )
    db.add(product)
    await db.commit()
    return product
```

---

## 13. Docker & Local Development

### 13.1 Development Docker Compose

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ribdigi_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ribdigi_dev
      - REDIS_URL=redis://redis:6379/0
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - S3_ENDPOINT=http://minio:9000
    depends_on:
      - postgres
      - redis
      - rabbitmq
      - minio
    command: uvicorn app.main:app --host 0.0.0.0 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    command: npm run dev

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ribdigi_dev
      - REDIS_URL=redis://redis:6379/0
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - postgres
      - redis
      - rabbitmq
    command: celery -A app.workers.celery_app worker --loglevel=info

volumes:
  postgres_data:
  minio_data:
```

### 13.2 Makefile Commands

```makefile
# Makefile
.PHONY: init dev test migrate migration lint format healthcheck

init:
	pip install pre-commit
	pre-commit install
	cd frontend && npm install

dev:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Services starting..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo "RabbitMQ Management: http://localhost:15672"
	@echo "MinIO Console: http://localhost:9001"

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

test:
	cd backend && pytest -xvs

test-unit:
	cd backend && pytest -xvs -m unit

test-integration:
	cd backend && pytest -xvs -m integration

test-coverage:
	cd backend && pytest --cov=app --cov-report=html --cov-report=term

migrate:
	cd backend && alembic upgrade head

migration:
	cd backend && alembic revision --autogenerate -m "$(MSG)"

lint:
	cd backend && ruff check .
	cd backend && mypy app
	cd frontend && npm run lint

format:
	cd backend && ruff format .
	cd frontend && npm run format

healthcheck:
	@curl -s http://localhost:8000/health || echo "Backend not responding"
	@curl -s http://localhost:3000 || echo "Frontend not responding"
```

---

## 14. API Development Standards

### 14.1 RESTful Design

| Method | Action | Example |
|--------|--------|---------|
| `GET` | Read / List | `GET /api/v1/products` |
| `GET` | Read Single | `GET /api/v1/products/{id}` |
| `POST` | Create | `POST /api/v1/products` |
| `PUT` | Full Update | `PUT /api/v1/products/{id}` |
| `PATCH` | Partial Update | `PATCH /api/v1/products/{id}` |
| `DELETE` | Delete | `DELETE /api/v1/products/{id}` |

### 14.2 URL Structure

```
/api/v1/{domain}/{resource}
/api/v1/{domain}/{resource}/{id}
/api/v1/{domain}/{resource}/{id}/{subresource}
```

**Examples:**
```
GET    /api/v1/inventory/products
GET    /api/v1/inventory/products/550e8400-e29b-41d4-a716-446655440000
POST   /api/v1/sales/invoices
GET    /api/v1/sales/customers/123e4567-e89b-12d3-a456-426614174000/orders
```

### 14.3 Request/Response Format

**Success Response (200/201):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Paracetamol 500mg",
    "sku": "MED-PARA-500",
    "cost_price": 2.50,
    "selling_price": 4.00
  },
  "meta": {
    "timestamp": "2026-08-07T12:00:00Z",
    "request_id": "req_abc123"
  }
}
```

**List Response (200):**
```json
{
  "success": true,
  "data": [
    { /* item 1 */ },
    { /* item 2 */ }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 156,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  },
  "meta": {
    "timestamp": "2026-08-07T12:00:00Z",
    "request_id": "req_abc123"
  }
}
```

**Error Response (4xx/5xx):**
```json
{
  "success": false,
  "error": {
    "code": "DUPLICATE_SKU",
    "message": "Product with SKU 'MED-PARA-500' already exists.",
    "details": {
      "sku": "MED-PARA-500",
      "existing_product_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "meta": {
    "timestamp": "2026-08-07T12:00:00Z",
    "request_id": "req_abc123"
  }
}
```

### 14.4 Pagination

Use cursor-based pagination for large datasets:

```
GET /api/v1/products?cursor=eyJpZCI6IjEyMyJ9&limit=20
```

Or offset-based for simple lists:

```
GET /api/v1/products?page=2&limit=20
```

### 14.5 Filtering & Sorting

```
GET /api/v1/products?category_id=abc&search=paracetamol&sort=-created_at&is_active=true
```

| Parameter | Format | Example |
|-----------|--------|---------|
| `search` | Full-text search | `search=paracetamol` |
| `sort` | `+field` (asc) or `-field` (desc) | `sort=-created_at` |
| `filter[field]` | Exact match | `category_id=abc123` |
| `date_from` | ISO 8601 | `date_from=2026-01-01` |
| `date_to` | ISO 8601 | `date_to=2026-12-31` |

### 14.6 Rate Limiting

| Tier | Limit | Window |
|------|-------|--------|
| **Public** | 10 requests | Per minute |
| **Authenticated** | 1000 requests | Per hour |
| **Enterprise** | 10000 requests | Per hour |

Rate limit headers included in all responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1691408400
```

---

## 15. Authentication & Authorization

### 15.1 JWT Token Structure

```json
{
  "sub": "user_uuid",
  "tenant_id": "tenant_uuid",
  "role": "store_manager",
  "permissions": ["inventory:read", "sales:write"],
  "iat": 1691404800,
  "exp": 1691406600,
  "type": "access"
}
```

### 15.2 OAuth2 Flow

```
+--------+                               +---------------+
|        |--(A)- Authorization Request ->|   Resource    |
|        |                               |     Owner     |
|        |<-(B)-- Authorization Grant ---|               |
|        |                               +---------------+
|        |
|        |--(C)-- Authorization Grant -->| Authorization |
| Client |                               |     Server    |
|        |<-(D)----- Access Token -------|               |
|        |                               +---------------+
|        |
|        |--(E)----- Access Token ------>|    Resource   |
|        |                               |     Server    |
|        |<-(F)--- Protected Resource ---|               |
+--------+                               +---------------+
```

**Implementation:**
```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Validate JWT and return current user."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")

        if not user_id or not tenant_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = await get_user_by_id(user_id, tenant_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
```

### 15.3 RBAC Implementation

```python
from functools import wraps
from fastapi import Depends, HTTPException

class PermissionChecker:
    def __init__(self, required_permissions: list[str]):
        self.required_permissions = required_permissions

    def __call__(self, user: User = Depends(get_current_user)):
        for permission in self.required_permissions:
            if permission not in user.permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {permission}"
                )
        return user

# Usage in router
@router.post("/products", dependencies=[Depends(PermissionChecker(["inventory:write"]))])
async def create_product(...):
    ...
```

---

## 16. Background Jobs & Queues

### 16.1 Celery Configuration

```python
# app/workers/celery_app.py
from celery import Celery
from app.config import settings

celery_app = Celery(
    "ribdigi",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.domains.inventory.tasks",
        "app.domains.sales.tasks",
        "app.domains.purchasing.tasks",
        "app.services.email",
        "app.services.notification",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
```

### 16.2 Task Patterns

```python
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_invoice_email(self, tenant_id: str, invoice_id: str, recipient_email: str):
    """Send invoice email with exponential backoff retry."""
    try:
        invoice = get_invoice(tenant_id, invoice_id)
        pdf = generate_invoice_pdf(invoice)

        email_service.send(
            to=recipient_email,
            subject=f"Invoice #{invoice.invoice_number}",
            body=render_template("invoice_email.html", invoice=invoice),
            attachments=[("invoice.pdf", pdf)],
        )

        logger.info(f"Invoice email sent to {recipient_email}")

    except EmailServiceError as exc:
        logger.warning(f"Email failed, retrying: {exc}")
        raise self.retry(exc=exc)
    except MaxRetriesExceededError:
        logger.error(f"Max retries exceeded for invoice {invoice_id}")
        # Fallback: mark for manual sending
        mark_email_failed(tenant_id, invoice_id)
```

### 16.3 Scheduled Tasks

```python
from celery import shared_task
from celery.schedules import crontab

# Register in celery_app.py beat_schedule
celery_app.conf.beat_schedule = {
    "daily-low-stock-check": {
        "task": "app.domains.inventory.tasks.check_low_stock",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    "weekly-sales-report": {
        "task": "app.domains.sales.tasks.generate_weekly_report",
        "schedule": crontab(day_of_week=1, hour=9, minute=0),  # Monday 9 AM
    },
    "daily-backup": {
        "task": "app.services.backup.daily_backup",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

---

## 17. Caching Strategy

### 17.1 Cache Layers

| Layer | Technology | TTL | Use Case |
|-------|-----------|-----|----------|
| **Application Cache** | Redis | 5 min | Product lookups, user sessions |
| **Query Cache** | Redis | 10 min | Expensive report queries |
| **Response Cache** | Redis | 1 min | Dashboard KPIs |
| **CDN Cache** | CloudFront/Cloudflare | 1 hour | Static assets, product images |

### 17.2 Cache Implementation

```python
from functools import wraps
from app.core.cache import redis_client

async def get_cached_product(tenant_id: UUID, product_id: UUID) -> Optional[Product]:
    cache_key = f"product:{tenant_id}:{product_id}"

    # Try cache first
    cached = await redis_client.get(cache_key)
    if cached:
        return Product.parse_raw(cached)

    # Cache miss — fetch from DB
    product = await product_repo.get_by_id(tenant_id, product_id)
    if product:
        await redis_client.setex(cache_key, 300, product.json())  # 5 min TTL

    return product

async def invalidate_product_cache(tenant_id: UUID, product_id: UUID):
    """Invalidate cache on product update."""
    cache_key = f"product:{tenant_id}:{product_id}"
    await redis_client.delete(cache_key)

    # Also invalidate list caches
    await redis_client.delete(f"products:{tenant_id}:*")
```

### 17.3 Cache Invalidation Patterns

| Pattern | When to Use |
|---------|-------------|
| **Write-Through** | Update cache simultaneously with DB (for critical data) |
| **Write-Behind** | Update cache, async DB write (for high-write scenarios) |
| **Cache-Aside** | Application manages cache (most common in RIBDIGI) |
| **TTL Expiration** | Automatic eviction after time period |

---

## 18. Observability & Logging

### 18.1 Structured Logging

All logs are JSON-formatted for machine parsing:

```python
# app/core/logging.py
import structlog
import logging

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info(
    "product_created",
    product_id=str(product.id),
    tenant_id=str(tenant_id),
    sku=product.sku,
    user_id=str(created_by),
)
```

**Log Output:**
```json
{
  "event": "product_created",
  "product_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "sku": "MED-PARA-500",
  "user_id": "789e0123-e89b-12d3-a456-426614174000",
  "timestamp": "2026-08-07T12:00:00.000Z",
  "level": "info",
  "logger": "app.domains.inventory.service"
}
```

### 18.2 Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | `method`, `endpoint`, `status` | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request latency |
| `db_query_duration_seconds` | Histogram | `table`, `operation` | DB query latency |
| `cache_hit_ratio` | Gauge | `cache_name` | Cache effectiveness |
| `celery_tasks_total` | Counter | `task_name`, `status` | Task execution count |
| `active_users` | Gauge | `tenant_id` | Concurrent users |

### 18.3 Distributed Tracing

Trace ID propagation through the stack:

```python
# Middleware injects trace_id into request context
@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", generate_trace_id())
    request.state.trace_id = trace_id

    with structlog.contextvars.bind_contextvars(trace_id=trace_id):
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
```

---

## 19. Troubleshooting

### 19.1 Common Development Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | Missing dependency | Run `pip install -r requirements-dev.txt` |
| `Alembic revision conflict` | Multiple devs created migrations | Merge migration heads: `alembic merge heads` |
| `Redis connection refused` | Redis not running | Start with `docker-compose -f docker-compose.dev.yml up redis` |
| `Celery tasks not executing` | Worker not running | Start worker: `make celery-worker` |
| `Frontend 502 error` | Backend not running | Verify backend at `http://localhost:8000/health` |
| `TypeScript build errors` | Missing types | Run `npm install` and check `@types/*` packages |
| `Flutter hot reload not working` | Asset cache | Run `flutter clean` then `flutter pub get` |

### 19.2 Debugging

**Backend:**
```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use ipdb for colored output
import ipdb; ipdb.set_trace()
```

**Frontend:**
```typescript
// React DevTools + console
console.log('Debug:', data);

// React Query DevTools (included in dev)
// Access at bottom-right corner of app
```

### 19.3 Performance Profiling

```bash
# Python profiling
python -m cProfile -o profile.stats script.py

# SQL query analysis
# Enable SQLAlchemy echo in config
SQLALCHEMY_ECHO=true

# Frontend bundle analysis
npm run analyze
```

---

## 20. Appendix

### A. Quick Reference

| Command | Description |
|---------|-------------|
| `make dev` | Start all development services |
| `make test` | Run all tests |
| `make lint` | Run all linters |
| `make format` | Format all code |
| `make migrate` | Apply database migrations |
| `make migration MSG="..."` | Create new migration |
| `make healthcheck` | Verify all services healthy |

### B. Environment-Specific Configurations

| Environment | Database | Debug | Logging | Caching |
|-------------|----------|-------|---------|---------|
| **Local** | Docker PostgreSQL | True | DEBUG | Redis (local) |
| **CI** | Test PostgreSQL | False | WARNING | Mock |
| **Staging** | RDS PostgreSQL | False | INFO | ElastiCache |
| **Production** | RDS PostgreSQL (Multi-AZ) | False | WARNING | ElastiCache |

### C. Useful Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org)
- [Next.js App Router](https://nextjs.org/docs/app)
- [Celery User Guide](https://docs.celeryq.dev)
- [Prophet Documentation](https://facebook.github.io/prophet)
- [Kubernetes Basics](https://kubernetes.io/docs/tutorials)

### D. Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | August 2026 | Engineering Team | Initial MVP developer guide |

---

<p align="center">
  <strong>RIBDIGI BUSINESS ERP — Developer Guide</strong><br>
  <em>One ERP Platform. Unlimited Business.</em><br><br>
  © 2026 RIBDIGI. All rights reserved.
</p>
