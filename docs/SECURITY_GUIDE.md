# Security Guide

## RIBDIGI BUSINESS ERP — MVP Security Documentation

**Version:** 1.0.0  
**Classification:** Internal — Engineering & DevOps  
**Last Updated:** August 2026  
**Applies To:** RIBDIGI ERP MVP (Version 1.0)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Security Architecture](#2-security-architecture)
3. [Threat Model](#3-threat-model)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [Role-Based Access Control (RBAC)](#5-role-based-access-control-rbac)
6. [Data Protection & Encryption](#6-data-protection--encryption)
7. [Multi-Tenancy & Data Isolation](#7-multi-tenancy--data-isolation)
8. [API Security](#8-api-security)
9. [Session Management](#9-session-management)
10. [Audit & Logging](#10-audit--logging)
11. [Backup & Recovery Security](#11-backup--recovery-security)
12. [Infrastructure & Container Security](#12-infrastructure--container-security)
13. [AI Security](#13-ai-security)
14. [Compliance & Standards](#14-compliance--standards)
15. [Incident Response Plan](#15-incident-response-plan)
16. [Security Checklist](#16-security-checklist)

---

## 1. Overview

RIBDIGI BUSINESS ERP is a multi-tenant SaaS platform serving Retail, Mart, Pharmacy, Restaurant, Bakery, Wholesale, and Manufacturing industries. This guide defines the security principles, controls, and operational practices required to protect tenant data, ensure regulatory compliance, and maintain platform integrity.

**Security Principles:**
- **Defense in Depth:** Multiple layers of security controls
- **Least Privilege:** Users and services receive minimum necessary access
- **Zero Trust:** Verify every request, regardless of origin
- **Data Sovereignty:** Tenant data is isolated and never commingled
- **Transparency:** All security-relevant events are logged and auditable

**Scope:** This document covers the MVP release (Version 1.0) including all 21 functional modules, the FastAPI backend, React/Next.js frontend, PostgreSQL database, Redis cache, and Kubernetes deployment.

---

## 2. Security Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  React/Next.js  │  Flutter/React Native  │  Third-Party    │
└──────────────────────┬──────────────────────────────────────┘
                       │  HTTPS / TLS 1.3
┌──────────────────────▼──────────────────────────────────────┐
│                     API Gateway (K8s Ingress)                │
│  • WAF Rules  • Rate Limiting  • DDoS Protection  • TLS    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Application Layer (FastAPI)                │
│  • JWT/OAuth2 Auth  • RBAC  • Input Validation  • CORS     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    Service Layer                             │
│  • Tenant Isolation  • Business Logic  • AI Services         │
└──────┬───────────────┬───────────────┬──────────────────────┘
       │               │               │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│  PostgreSQL │ │    Redis    │ │  S3 Storage │
│  (Tenant    │ │  (Session & │ │  (Documents │
│   Isolated) │ │   Cache)    │ │   & Images) │
└─────────────┘ └─────────────┘ └─────────────┘
```

### 2.2 Security Boundaries

| Boundary | Control Mechanism |
|----------|-------------------|
| External → API | TLS 1.3, API Gateway, WAF |
| API → Services | JWT Validation, RBAC, Tenant Header Verification |
| Services → Database | SQLAlchemy ORM, Row-Level Security, Parameterized Queries |
| Services → Cache | Redis AUTH, TLS, Namespaced Keys |
| Services → Storage | Signed URLs, IAM Policies, Encryption at Rest |
| Tenant → Tenant | Database-level isolation, Schema separation, Foreign Key Constraints |

---

## 3. Threat Model

### 3.1 STRIDE Analysis

| Threat | Category | Mitigation |
|--------|----------|------------|
| **Spoofing** | Identity | JWT + OAuth2, MFA, Email Verification |
| **Tampering** | Data Integrity | HTTPS, Request Signing, Database Constraints |
| **Repudiation** | Non-repudiation | Audit Logs, Immutable Logs, Digital Signatures on Invoices |
| **Information Disclosure** | Confidentiality | Encryption at Rest & in Transit, RBAC, Tenant Isolation |
| **Denial of Service** | Availability | Rate Limiting, DDoS Protection, Resource Quotas, Auto-scaling |
| **Elevation of Privilege** | Authorization | RBAC, Principle of Least Privilege, Permission Middleware |

### 3.2 Key Threat Scenarios

**T1: Cross-Tenant Data Leakage**
- *Risk:* Tenant A accesses Tenant B's data via manipulated `X-Tenant-ID` header
- *Mitigation:* JWT contains `tenant_id` claim; middleware validates header against token; database queries filtered by `tenant_id`

**T2: Privilege Escalation**
- *Risk:* Cashier user grants themselves Company Admin rights
- *Mitigation:* Role changes restricted to Super Admin; permission middleware checks on every request; immutable audit trail

**T3: SQL Injection via Product Search**
- *Risk:* Attacker injects SQL through barcode scanner or search field
- *Mitigation:* SQLAlchemy ORM with parameterized queries; input validation; strict type coercion

**T4: Session Hijacking**
- *Risk:* Attacker steals JWT token and impersonates user
- *Mitigation:* Short-lived access tokens (15 min); refresh token rotation; secure httpOnly cookies; IP binding (optional)

**T5: AI Prompt Injection**
- *Risk:* Malicious input manipulates AI assistant to expose sensitive data
- *Mitigation:* Input sanitization; context isolation; output filtering; rate limiting on AI endpoints

**T6: Insider Threat — Data Exfiltration**
- *Risk:* Employee with valid credentials bulk-exports customer data
- *Mitigation:* Rate limiting on export endpoints; audit logging; anomaly detection; data loss prevention (DLP) policies

---

## 4. Authentication & Authorization

### 4.1 Authentication Flow

RIBDIGI ERP uses **JWT (JSON Web Tokens)** with **OAuth2** Resource Owner Password Credentials flow for the MVP.

**Login Sequence:**
```
1. Client → POST /auth/login {email, password, tenant_id}
2. Server validates credentials against bcrypt-hashed password
3. Server generates access_token (15 min expiry) + refresh_token (7 days)
4. Server stores refresh_token hash in Redis with TTL
5. Client receives tokens and stores access_token in memory
6. Client includes access_token in Authorization: Bearer header for all subsequent requests
```

### 4.2 Password Policy

Live engine (`validate_password_strength` / login lockout) — Stage 19 U1 evidence: `test_auth_session_br19_u1.py`.

| Requirement | Rule |
|-------------|------|
| Minimum Length | 8 characters |
| Complexity | Uppercase, lowercase, digit, special character |
| History | Not enforced in commercial MVP (deferred) |
| Expiry | Not enforced in commercial MVP (deferred) |
| Lockout | 5 failed attempts → 30-minute lockout |
| Storage | bcrypt (`$2b$` / `$2a$`) |

### 4.2 Password Policy (aspirational / post-MVP)

Earlier draft targets (min 12, 15-minute lockout, history/expiry) remain product backlog — not current runtime.

### 4.3 Two-Factor Authentication (Optional)

- **TOTP-based** using authenticator apps (Google Authenticator, Authy)
- **Enforcement:** Can be mandated per role (e.g., Super Admin, Company Admin)
- **Backup Codes:** 10 single-use recovery codes generated on 2FA setup
- **Implementation:** `pyotp` library; secret encrypted with tenant master key

### 4.4 Email Verification

- Mandatory for new user registration
- Verification link expires in 24 hours
- JWT token embedded in verification URL with single-use signature
- Unverified accounts cannot access protected resources

### 4.5 Password Reset

- Secure token sent via email (cryptographically random, 32 bytes)
- Token expires in 1 hour
- Token is single-use; consumed on first access
- Reset event logged in audit trail

---

## 5. Role-Based Access Control (RBAC)

### 5.1 Role Hierarchy

```
super_admin
    └── company_admin
            ├── store_manager
            │       ├── sales_officer
            │       └── cashier
            ├── inventory_officer
            └── accountant
```

### 5.2 Permission Layers

RBAC operates across three dimensions:

**1. Module Permissions**
Controls access to major functional areas:
- `inventory`, `sales`, `pos`, `purchases`, `accounting`, `reports`, `admin`

**2. Menu Permissions**
Controls visibility of navigation items:
- `products`, `stock_in`, `stock_out`, `invoices`, `expenses`, `settings`

**3. Record Permissions**
Controls CRUD operations on specific entities:
- `read`, `write`, `delete`, `approve`, `export`

### 5.3 Permission Matrix (MVP)

| Module | Super Admin | Company Admin | Store Manager | Sales Officer | Inventory Officer | Accountant | Cashier |
|--------|:-----------:|:-------------:|:-------------:|:-------------:|:-----------------:|:----------:|:-------:|
| Tenant Management | Full | — | — | — | — | — | — |
| User Management | Full | Full | Read | — | — | — | — |
| Dashboard | Full | Full | Full | Full | Full | Full | Full |
| Products | Full | Full | Read | Read | Full | Read | Read |
| Stock Operations | Full | Full | Read | — | Full | — | — |
| Sales/Invoices | Full | Full | Full | Full | — | Read | Read |
| POS | Full | Full | Full | Full | — | — | Full |
| Purchases | Full | Full | Read | — | Full | Read | — |
| Expenses | Full | Full | Read | — | — | Full | — |
| Accounting | Full | Full | — | — | — | Full | — |
| Reports | Full | Full | Full | Limited | Limited | Full | — |
| System Settings | Full | Full | — | — | — | — | — |

### 5.4 Implementation

- Permissions are stored in PostgreSQL and cached in Redis
- FastAPI dependency `require_permissions()` validates on every protected route
- Permission checks occur at both API gateway and service layer
- Dynamic permission updates invalidate Redis cache immediately

---

## 6. Data Protection & Encryption

### 6.1 Encryption in Transit

- **Protocol:** TLS 1.3 (minimum TLS 1.2)
- **Certificate:** Let's Encrypt or commercial wildcard certificate
- **HSTS:** Enabled with max-age 31536000 seconds
- **Cipher Suites:** ECDHE with AES-256-GCM, ChaCha20-Poly1305
- **Internal Service Communication:** mTLS via Istio/Linkerd (Kubernetes)

### 6.2 Encryption at Rest

| Data Store | Encryption Method | Key Management |
|------------|-------------------|----------------|
| PostgreSQL | AES-256 (cloud provider managed or pgcrypto) | AWS KMS / HashiCorp Vault |
| Redis | TLS + AUTH | Redis ACL + Kubernetes Secrets |
| S3 Storage | AES-256-SSE | S3 Bucket Keys / KMS |
| Application Logs | AES-256-GCM | Centralized logging with encrypted storage |
| Backups | AES-256 | Backup encryption keys stored in Vault |

### 6.3 Sensitive Data Handling

**PII (Personally Identifiable Information):**
- Customer names, emails, phone numbers, addresses
- Stored encrypted at application level for high-sensitivity tenants (optional)
- Access logged in audit trail

**Financial Data:**
- Bank account numbers, tax IDs
- Encrypted at rest; decrypted only in memory during processing
- Never logged to application logs

**Passwords:**
- bcrypt-hashed (cost factor 12)
- Plaintext passwords never persisted; immediately hashed on receipt

**API Keys & Secrets:**
- Stored in HashiCorp Vault or Kubernetes Secrets
- Rotated every 90 days
- Never committed to version control

### 6.4 Data Masking

- **Logs:** Credit card numbers, tax IDs, and passwords are automatically masked
- **UI:** Partial masking of sensitive fields for non-admin users (e.g., `****-****-1234`)
- **Exports:** PII fields optionally excluded based on user role

---

## 7. Multi-Tenancy & Data Isolation

### 7.1 Tenant Isolation Strategy

RIBDIGI ERP MVP uses **shared-schema + `tenant_id`** isolation (ADR-001). Schema-per-tenant remains a deferred post-MVP option.

- All tenant business tables carry `tenant_id` with query filters on every protected path
- Tenant context from JWT (and validated `X-Tenant-ID` when present); header mismatch → `403`
- Foreign resource IDs from another tenant → `404` (no existence leak)

### 7.2 Isolation Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| **Data Separation** | Shared schema with mandatory `tenant_id` on tenant-owned rows |
| **Query Enforcement** | Service/API layer scopes selects/updates by `claims["tenant_id"]` |
| **Cross-Tenant Prevention** | Foreign-id and mismatched-header proofs in isolation matrix |
| **Launch smoke coverage** | Stage 18 S1 extends matrix for API keys, webhooks, OCR-apply, stock counts, warehouse transfers, quotations/orders, product warehouse-stock (`test_isolation_matrix_s1.py`; base `test_tenant_isolation_matrix.py`) |

### 7.3 Tenant Lifecycle Security

**Onboarding:**
1. Tenant registration triggers schema creation
2. Default roles and permissions seeded
3. Admin user created with forced password change on first login
4. API key generated and encrypted in Vault

**Suspension:**
1. Tenant status set to `suspended`
2. All active sessions invalidated in Redis
3. API requests blocked at middleware layer
4. Data retained per retention policy (typically 30 days before archival)

**Deletion:**
1. Soft delete: tenant marked `deleted` with 30-day grace period
2. Hard delete: schema dropped after grace period; backups purged per policy
3. Audit log retained for compliance (typically 7 years)

---

## 8. API Security

### 8.1 Authentication API

**Endpoints:**
- `POST /auth/login` — JWT access + refresh (Stage 19 K1); rate limited via auth bucket
- `POST /auth/refresh` — Rotates session; old refresh revoked (Stage 19 K1); auth rate-limit class
- `POST /auth/password-reset-request` — Rate limited via auth bucket
- `POST /auth/password-reset` — Token single-use, 1-hour expiry
- `POST /auth/2fa/verify` — Rate limited via auth bucket

Evidence: `test_auth_api_fidelity_k1.py` (BR-18.1).

### 8.2 API Security Controls

| Control | Implementation |
|---------|----------------|
| **Input Validation** | Pydantic models with strict type checking; regex patterns for IDs |
| **Output Serialization** | SQLAlchemy models → Pydantic schemas; no raw dict exposure |
| **SQL Injection Prevention** | SQLAlchemy ORM exclusively; raw SQL prohibited in application code |
| **XSS Prevention** | Output encoding in React frontend; Content-Type enforcement |
| **CSRF Protection** | SameSite=Strict cookies; CSRF tokens for state-changing operations |
| **CORS Policy** | Whitelist of allowed origins per tenant; preflight handling |
| **Content Security Policy** | Strict CSP headers preventing inline scripts |

### 8.3 Rate Limiting

MVP (Stage 5 S1 / Stage 19 K1): Redis or in-memory sliding window keyed by `{client_ip}:{auth|api}:{X-Tenant-ID|anon}`. Caps from `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_AUTH_PER_MINUTE` (auth paths include login + refresh). Plan-tier tables deferred post-MVP.

**Rate Limit Headers:**
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Backend: memory|redis
```

Evidence: `test_production_security_s1.py`, `test_auth_api_fidelity_k1.py` (tenant bucket isolation).

### 8.4 API Versioning

- URL versioning: `/v1/`, `/v2/`
- Deprecated versions receive 6-month sunset notice
- Security patches backported to supported versions

---

## 9. Session Management

### 9.1 JWT Configuration

**Access Token:**
- Algorithm: RS256 (asymmetric) or HS256 (symmetric for MVP)
- Expiry: 15 minutes
- Claims: `sub` (user_id), `tenant_id`, `role`, `iat`, `exp`, `jti`

**Refresh Token:**
- Expiry: 7 days
- Stored as SHA-256 hash in Redis with user_id mapping
- Rotation on every use; old refresh token invalidated
- Family detection: reused refresh tokens trigger session revocation

### 9.2 Session Lifecycle

**Creation:**
- Issued on successful login or token refresh
- Session record created in Redis with TTL matching token expiry

**Validation:**
- Every request validates JWT signature and expiry
- Redis checked for session revocation (logout, password change, role change)
- IP address and User-Agent optionally validated

**Termination:**
- `POST /auth/logout` — Invalidates current session
- `DELETE /auth/sessions/{session_id}` — Admin can terminate specific sessions
- Password change — All sessions except current revoked
- Account suspension — All sessions immediately revoked

### 9.3 Concurrent Session Limits

| Role | Max Concurrent Sessions |
|------|------------------------|
| Super Admin | 3 |
| Company Admin | 5 |
| Store Manager | 5 |
| Other Roles | 10 |

---

## 10. Audit & Logging

### 10.1 Audit Log Requirements

All security-relevant events are captured in an immutable audit log:

**Tracked Events:**
- Login / Logout (success and failure)
- Password changes
- Role/permission modifications
- Product changes (create, update, delete)
- Sales transactions (create, void, refund)
- Purchase orders (create, approve, receive)
- User activity (CRUD operations on sensitive resources)
- Tenant status changes
- Backup and restore operations
- AI assistant queries (anonymized where possible)
- Expense workflow domain audit (Stage 14 A3): `expense_submitted`, `expense_auto_approved`, `expense_level_approved`, `expense_approved`, `expense_rejected` (`module=expenses`; reject includes reason)
- Sales path domain audit (Stage 15 A1): enriched `invoice_posted` (stock/tax/AR) and `sales_return_posted` (`module=sales`); linked `journal_posted` for `source_type=sales_invoice|sales_return`
- Inventory path domain audit (Stage 17 A1): `product_create`, `product_update` / soft-delete `product_deactivate` with before/after field diffs (`module=inventory`); stock mutations via `stock_{movement_type}` (`before`/`after` qty, warehouse, reason)
- Security hardening fidelity (Stage 18 A1): `login` / `login_failed` / `logout` / `idle_logout`; `user_created` / `user_updated` / `user_deactivated`; purchases `po_created` / `grn_posted`; `journal_posted`; BR-17.2 filter/export/verify/retention (`test_security_hardening_a1.py`)
- Stage 18 D1 fidelity sync: BR-16/17 + readiness + launch checklist — `docs/STAGE_18_FIDELITY.md` (`test_stage18_fidelity_d1.py`); exit met H18x / ADR-042 (`test_stage18_exit_h18x.py`)

### 10.2 Audit Log Schema

```json
{
  "event_id": "aud_8f3a9b2c1d4e",
  "timestamp": "2026-08-07T13:51:00Z",
  "tenant_id": "tenant_abc123",
  "user_id": "usr_001",
  "session_id": "sess_001",
  "ip_address": "203.0.113.42",
  "user_agent": "Mozilla/5.0 ...",
  "event_type": "product.updated",
  "resource_type": "product",
  "resource_id": "prod_001",
  "action": "update",
  "old_values": { "price": 10.99 },
  "new_values": { "price": 12.99 },
  "outcome": "success",
  "reason": "Standard price adjustment"
}
```

### 10.3 Log Security

- **Immutability:** Audit logs written to append-only storage (WORM)
- **Retention:** 7 years for financial transactions; 2 years for access logs
- **Encryption:** Encrypted at rest with tenant-specific keys
- **Access:** Read-only access restricted to Super Admin and compliance officers
- **Integrity:** Cryptographic hashing of log chains to detect tampering

### 10.4 Application Logging

- **MVP (Stage 18 L1):** Structured JSON request/error logs via `RequestLoggingMiddleware` (`ribdigi.request` logger). Fields: `request_id`, `tenant_id`, `user_id`, `status`, `latency_ms`, safe `error_code`. Correlation header `X-Request-ID`. See `docs/OPS_MONITORING_MVP.md`.
- **Levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL (`LOG_LEVEL`)
- **Sensitive Data:** Request bodies and secrets are not written to access logs; only safe error codes
- **Monitoring hooks:** `GET /api/v1/health` / `health/ready` and Prometheus-text `GET /api/v1/metrics` (Stage 5 H5). Full Grafana/PagerDuty deferred.
- **Audit trail:** Financial/security events remain on the hash-chained audit log (BR-17), not access logs.

---

## 11. Backup & Recovery Security

### 11.1 Backup Strategy

| Type | Frequency | Retention | Encryption |
|------|-----------|-----------|------------|
| Database Full | Daily | 30 days | AES-256 |
| Database Incremental | Every 6 hours | 7 days | AES-256 |
| File Storage (S3) | Continuous versioning | 90 days | SSE-S3 |
| Configuration | On change | 30 versions | AES-256 |

### 11.2 Backup Security Controls

- **Encryption:** All backups encrypted before leaving the application server
- **Key Management:** Backup encryption keys stored separately from data in HashiCorp Vault
- **Access Control:** Backup operations restricted to infrastructure service accounts
- **Integrity Verification:** SHA-256 checksums verified on every backup and restore
- **Offsite Storage:** Backups replicated to geographically separate region
- **Testing:** Monthly restore drills conducted in isolated environment

### 11.3 Recovery Procedures

**Point-in-Time Recovery (PITR):**
- PostgreSQL WAL archiving enables recovery to any point within retention window
- Recovery tested quarterly; RTO < 4 hours, RPO < 15 minutes

**Tenant-Level Restore:**
- Individual tenant schemas can be restored without affecting other tenants
- Requires Super Admin approval and multi-person authorization

---

## 12. Infrastructure & Container Security

### 12.1 Kubernetes Security

| Control | Implementation |
|---------|----------------|
| **Network Policies** | Default deny; explicit allow rules between namespaces |
| **Pod Security Standards** | Restricted profile enforced |
| **RBAC** | Service accounts with minimal permissions |
| **Secrets Management** | Kubernetes Secrets or External Secrets Operator + Vault |
| **Image Scanning** | Trivy/Clair scan on every build; critical CVEs block deployment |
| **Runtime Security** | Falco for anomaly detection; read-only root filesystems |

### 12.2 Docker Security

- **Base Images:** Distroless or Alpine Linux; minimal attack surface
- **Non-Root User:** All containers run as non-root (UID 1000+)
- **No Privileged Mode:** Privileged containers prohibited
- **Resource Limits:** CPU and memory limits prevent DoS
- **Image Signing:** Cosign for container image verification

### 12.3 Network Security

- **VPC Isolation:** Production, staging, and development in separate VPCs
- **Firewall Rules:** Least-privilege ingress/egress rules
- **DDoS Protection:** Cloud provider DDoS mitigation (AWS Shield, Cloudflare)
- **VPN/Bastion:** Administrative access via bastion hosts only

### 12.4 Dependency Security

- **SBOM:** Software Bill of Materials generated for every release
- **Vulnerability Scanning:** Snyk or Dependabot on all dependencies
- **License Compliance:** FOSSA or similar for open-source license tracking
- **Update Policy:** Critical security patches applied within 48 hours

---

## 13. AI Security

### 13.1 AI Business Assistant Security

The MVP includes AI capabilities across 10 modules. Security controls include:

**Input Sanitization:**
- All free-text user inputs to AI endpoints sanitized for prompt injection attacks (`app.ai_guard`)
- Maximum input length enforced (chat 2000 chars; other NL prompts 4000 chars)
- Blocked keywords and patterns for sensitive data exfiltration / jailbreak attempts
- AI usage audited (`module=ai`) with secret/email redaction in stored prompt previews; rejections audited as `ai_prompt_rejected`

**Context Isolation:**
- AI assistant receives only data the user has permission to access
- Tenant context strictly enforced; AI cannot access cross-tenant data
- Session context scoped to current conversation only

**Output Filtering:**
- AI responses scanned for PII leakage
- Financial figures validated against actual database records before display
- Disallowed content patterns blocked

**AI Security Monitor (Basic):**
- Monitors AI query patterns for anomalies
- Flags unusual data access volumes or suspicious prompt patterns
- Alerts security team on potential abuse

### 13.2 Model Security

- **Local/Private Models:** Where possible, models run within tenant infrastructure boundaries
- **API Keys:** External AI provider keys stored in Vault; rotated monthly
- **Data Retention:** No tenant data retained by external AI providers
- **Anonymization:** PII stripped from training or fine-tuning data

---

## 14. Compliance & Standards

### 14.1 Applicable Regulations

| Regulation | Applicability | MVP Status |
|------------|---------------|------------|
| **GDPR** | EU customers | Data isolation, right to deletion, audit logs |
| **PCI-DSS** | Card payment processing | Tokenized payments; no card data stored |
| **SOX** | Public company customers | Audit trails, financial controls |
| **Local Tax Laws** | All jurisdictions | Tax reports, immutable invoice records |
| **Industry-Specific** | Pharmacy, Food | Data integrity, batch tracking, expiry management |

### 14.2 Compliance Controls

- **Data Retention:** Configurable per tenant; automatic purging after retention period
- **Right to Erasure:** Tenant data deleted within 30 days of request
- **Data Portability:** Export functionality provides machine-readable data dumps
- **Consent Management:** Explicit consent for marketing communications and AI processing

### 14.3 Security Certifications Roadmap

| Certification | Target Date | Phase |
|---------------|-------------|-------|
| SOC 2 Type I | Q2 2027 | Post-MVP |
| ISO 27001 | Q4 2027 | Post-MVP |
| PCI-DSS Level 1 | Q2 2028 | Scale Phase |

---

## 15. Incident Response Plan

### 15.1 Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **Critical (P1)** | Active breach or system compromise | 15 minutes | Ransomware, data exfiltration in progress |
| **High (P2)** | Potential breach or major vulnerability | 1 hour | Zero-day exploit, credential leak |
| **Medium (P3)** | Security weakness or policy violation | 24 hours | Misconfigured S3 bucket, expired certificate |
| **Low (P4)** | Minor issue or hardening opportunity | 7 days | Missing security header, outdated dependency |

### 15.2 Response Playbook

**Detection → Containment → Eradication → Recovery → Post-Incident**

1. **Detection:** AI Security Monitor, audit logs, automated alerts, user reports
2. **Containment:** Isolate affected tenant(s); revoke compromised sessions; block malicious IPs
3. **Eradication:** Patch vulnerability; rotate exposed credentials; remove attacker access
4. **Recovery:** Restore from clean backups; verify integrity; resume operations
5. **Post-Incident:** Root cause analysis; update threat model; communicate to affected tenants

### 15.3 Communication Plan

- **Internal:** Slack #security-incidents, PagerDuty escalation
- **External:** Email to affected tenant admins within 24 hours for P1/P2
- **Regulatory:** GDPR breach notification within 72 hours if applicable

---

## 16. Security Checklist

### 16.1 Pre-Deployment Checklist

- [ ] All secrets stored in Vault/K8s Secrets (not in code)
- [ ] TLS 1.3 configured on all endpoints
- [x] Rate limiting enabled and tested (`RATE_LIMIT_ENABLED=true`; prefer `RATE_LIMIT_REQUIRE_REDIS=true` in multi-instance production)
- [x] CORS policy restricted to known origins (`CORS_ORIGINS` whitelist; never `*`)
- [ ] SQLAlchemy ORM used exclusively (no raw SQL)
- [ ] Input validation on all API endpoints
- [ ] RBAC middleware applied to all protected routes
- [ ] Audit logging enabled for all sensitive operations
- [ ] Database backups encrypted and tested
- [ ] Container images scanned (no critical CVEs)
- [ ] Network policies applied in Kubernetes
- [ ] DDoS protection enabled
- [x] Security headers configured (HSTS in production, CSP `default-src 'none'`, X-Frame-Options DENY, COOP)
- [x] OpenAPI `/docs` / `/redoc` / `/openapi.json` disabled when `APP_ENV=production`
- [ ] Password policy enforced
- [ ] Session timeout and rotation configured
- [x] AI input sanitization + AI audit logging active (Stage 5 A1; external-LLM output filtering post-MVP)
- [ ] Incident response runbook accessible to on-call team

**Stage 5 S1 verify:** `GET /api/v1/health` returns `security.rate_limit_enabled`, `openapi_enabled=false` in production, and response includes CSP + rate-limit headers.

**Stage 5 O1 verify:** run `pytest tests/test_owasp_smoke.py tests/test_owasp_suite_o1.py` — covers OWASP A01/A02/A03/A05/A07 automated controls. Vendor ZAP / pen test is out of MVP scope.

### 16.2 Ongoing Security Operations

- [ ] Daily review of security alerts and failed login attempts
- [ ] Weekly vulnerability scan of dependencies
- [ ] Monthly penetration test of authentication flows
- [x] Quarterly logical backup restore drill procedure documented + automated proof (Stage 5 B1; infra WAL/PITR drill post-MVP)
- [ ] Quarterly access review (user roles and permissions)
- [ ] Annual third-party security audit
- [ ] Continuous monitoring of audit logs for anomalies

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Technical Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, JWT + OAuth2, Docker, Kubernetes  
**Owner:** Security Engineering Team  
**Review Cycle:** Quarterly or upon significant architectural change
