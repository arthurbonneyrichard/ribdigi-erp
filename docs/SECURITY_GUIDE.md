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
| **Finance/report residual** | Stage 23 I1 extends matrix for liquid accounts/transfers, expense categories/recurring, branch + report dimension filters, mismatched header on financial reports (`test_isolation_matrix_i1.py`) |
| **MVP gate honesty** | Stage 23 G1 marks shared-schema isolation Complete for MVP; schema-per-tenant remains deferred (ADR-001); evidence `test_mvp_gate_closure_g1.py` |
| **Stage 23 fidelity** | D1 maps reports dimension + gate evidence — `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`); exit/freeze ADR-052 (`test_stage23_exit_h23x.py`) |
| **Stage 24 fidelity** | D1 maps commerce/ops/AI gate evidence — `docs/STAGE_24_FIDELITY.md` (`test_stage24_fidelity_d1.py`); exit/freeze ADR-054 (`test_stage24_exit_h24x.py`) |
| **Stage 25 fidelity** | D1 maps purchases / cross-domain / four-actual insights / AI UI evidence — `docs/STAGE_25_FIDELITY.md` (`test_stage25_fidelity_d1.py`); exit/freeze ADR-056 (`test_stage25_exit_h25x.py`); historical open ADR-055 |
| **Stage 26 open** | Production Platform & Ops Fidelity — `docs/STAGE_26_PLAN.md`, ADR-057 (`test_stage26_open.py`); Stages 1–25 remain frozen |
| **Stage 26 M1** | Monitoring scrape/alerts/log-ship — `ops/prometheus/`, `ops/logging/`, `docs/OPS_MONITORING_MVP.md` (`test_ops_monitoring_m1.py`) |
| **Stage 26 W1** | WAL/PITR strategy + S3 offsite — `docs/DR_WAL_PITR_RUNBOOK.md`, `ops/postgres/`, `ops/backup/` (`test_wal_pitr_w1.py`) |
| **Stage 26 K1** | Kubernetes/Helm deploy fidelity — `helm/ribdigi/`, `k8s/`, `docs/K8S_DEPLOY_MVP.md` (`test_k8s_deploy_k1.py`); live GHA→staging deferred |
| **Stage 26 C1** | Load capacity CI evidence — `docs/LOAD_CAPACITY_MVP.md`, `backend/loadtest/` (`test_load_capacity_c1.py`); operator 1000-VU deferred |
| **Stage 26 fidelity** | D1 maps M1–C1 ops evidence — `docs/STAGE_26_FIDELITY.md` (`test_stage26_fidelity_d1.py`); exit/freeze ADR-058 (`test_stage26_exit_h26x.py`); historical open ADR-057; secrets remain env/Secret only; main CI deploy-free (Stage 18 C1) |
| **Stage 27 open** | Commercial MVP Release Fidelity — `docs/STAGE_27_PLAN.md`, ADR-059 (`test_stage27_open.py`); Stages 1–26 remain frozen; B1 offsite / P1 PgBouncer / S1 security scan / L1 launch cert pending |
| **Stage 27 B1** | Opt-in `.ribbak` offsite upload after `create_backup` — `BACKUP_OFFSITE_UPLOAD_ENABLED` / `BACKUP_OFFSITE_S3_*` (`test_backup_offsite_b1.py`); failure → `Backup failed` (no fake success); secrets remain env-only |
| **Stage 27 P1** | PgBouncer pooling fidelity — `ops/postgres/pgbouncer.ini.example`, `docs/PGBOUNCER_MVP.md` (`test_pgbouncer_p1.py`); secrets in env/userlist only; live soak / Helm pooler Remaining |
| **Stage 27 S1** | OWASP security scan baseline evidence — `docs/SECURITY_SCAN_MVP.md`, `ops/security/zap-baseline.example.yml` (`test_security_scan_s1.py`); vendor pen test / live ZAP staging Remaining; main CI deploy-free |
| **Stage 27 L1** | Launch certification pack — `docs/LAUNCH_CERT_MVP.md`, `ops/launch/checklist-map.json` (`test_launch_cert_l1.py`); operator env / §7 sign-off remain unsigned (no fake production certificate) |
| **Stage 27 fidelity** | D1 maps B1–L1 release evidence — `docs/STAGE_27_FIDELITY.md` (`test_stage27_fidelity_d1.py`); exit/freeze ADR-060 (`test_stage27_exit_h27x.py`); historical open ADR-059; vendor pen test / live ZAP / forged §7 sign-off remain Remaining |
| **Stage 28 open** | Staging Certification Fidelity — `docs/STAGE_28_PLAN.md`, ADR-061 (`test_stage28_open.py`); Stages 1–27 remain frozen |
| **Stage 28 R1** | Operator PITR drill pack — `docs/PITR_DRILL_PACK_MVP.md`, `ops/postgres/pitr-drill-checklist.json` (`test_pitr_drill_pack_r1.py`); live base+WAL replay / managed-cloud Remaining; no CI PITR success claimed |
| **Stage 28 G1** | Staging GHA deploy pack — `docs/STAGING_GHA_MVP.md`, `ops/k8s/deploy-staging.example.yml` (`test_staging_gha_g1.py`); not in main `ci.yml`; live staging apply Remaining |
| **Stage 28 A1** | Grafana / Alertmanager pack — `docs/GRAFANA_PACK_MVP.md`, `ops/grafana/` (`test_grafana_pack_a1.py`); hosted Grafana/PagerDuty/SIEM Remaining |
| **Stage 28 C1** | Operator ~1000-VU cert pack — `docs/LOAD_CERT_PACK_MVP.md`, `ops/loadtest/` (`test_load_cert_pack_c1.py`); live 1000-VU execution Remaining; no forged certificate |
| **Stage 28 fidelity** | D1 maps R1–C1 staging-cert evidence — `docs/STAGE_28_FIDELITY.md` (`test_stage28_fidelity_d1.py`); exit/freeze ADR-062 (`test_stage28_exit_h28x.py`); historical open ADR-061; live drills / hosted SaaS / forged certs remain Remaining |
| **Stage 29 open** | Operator Hardening & Production Cutover Fidelity — `docs/STAGE_29_PLAN.md`, ADR-063 (`test_stage29_open.py`); Stages 1–28 remain frozen; closed under ADR-064 |
| **Stage 29 V1** | Vendor pen-test / ZAP staging pack — `docs/PENTEST_PACK_MVP.md`, `ops/security/` (`test_pentest_pack_v1.py`); purchased cert / live ZAP Remaining; main CI deploy-free |
| **Stage 29 B2** | PgBouncer soak / pooler pack — `docs/PGBOUNCER_SOAK_PACK_MVP.md`, `ops/postgres/` (`test_pgbouncer_soak_b2.py`); live soak / default Helm pooler Remaining |
| **Stage 29 T1** | Cert-manager / TLS ingress pack — `docs/TLS_INGRESS_PACK_MVP.md`, `ops/k8s/` (`test_tls_ingress_t1.py`); live ACME issuance / TLS cutover Remaining |
| **Stage 29 X1** | Production cutover pack — `docs/CUTOVER_PACK_MVP.md`, `ops/launch/` + `ops/k8s/deploy-production.example.yml` (`test_cutover_pack_x1.py`); live cutover / §7 sign-off Remaining; main CI deploy-free |
| **Stage 29 D1** | Operator hardening & cutover fidelity — `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`) maps V1–X1 → readiness / launch / deploy / security |
| **Stage 29 fidelity** | D1 maps V1–X1 operator-hardening evidence — `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`); exit/freeze `docs/STAGE_29_EXIT_CRITERIA.md`, ADR-064 (`test_stage29_exit_h29x.py`); historical open ADR-063; purchased cert / live soak / ACME / cutover / §7 remain Remaining |
| **Stage 30 open** | Go-Live Support Fidelity — `docs/STAGE_30_PLAN.md`, ADR-065 (`test_stage30_open.py`); Stages 1–29 remain frozen; closed under ADR-066 |
| **Stage 31 open** | Commercial MVP Closeout Fidelity — `docs/STAGE_31_PLAN.md`, ADR-067 (`test_stage31_open.py`); Stages 1–30 remain frozen; closed under ADR-068 |
| **Stage 31 G1** | MVP gate honesty matrix — `docs/MVP_GATE_MATRIX_MVP.md`, `ops/mvp/gate-matrix.json` (`test_mvp_gate_matrix_g1.py`); go-live / §7 Remaining |
| **Stage 31 R1** | Deferred ADR register — `docs/DEFERRED_ADR_REGISTER_MVP.md`, `ops/mvp/deferred-adr-register.json` (`test_deferred_adr_register_r1.py`); ADR-001–006 post-MVP scopes Remaining |
| **Stage 31 O1** | Operator Remaining register — `docs/OPERATOR_REMAINING_MVP.md`, `ops/mvp/operator-remaining-register.json` (`test_operator_remaining_o1.py`); live runs / attestation Remaining |
| **Stage 31 C1** | Commercial MVP declaration — `docs/MVP_DECLARATION_MVP.md`, `ops/mvp/mvp-declaration.json` (`test_mvp_declaration_c1.py`); packaging ≠ live go-live / §7 |
| **Stage 31 D1** | Closeout fidelity — `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`) maps G1–C1 → readiness / launch / deploy / security |
| **Stage 31 fidelity** | D1 maps G1–C1 closeout evidence — `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`); exit/freeze `docs/STAGE_31_EXIT_CRITERIA.md`, ADR-068 (`test_stage31_exit_h31x.py`); historical open ADR-067; live go-live / attestation / §7 / deferred ADR implementations remain Remaining |
| **Stage 32 open** | Commercial MVP Handoff Fidelity — `docs/STAGE_32_PLAN.md`, ADR-069 (`test_stage32_open.py`); Stages 1–31 remain frozen; closed under ADR-070 |
| **Stage 32 A1** | MVP acceptance archive — `docs/ACCEPTANCE_ARCHIVE_MVP.md`, `ops/mvp/acceptance-archive.json` (`test_acceptance_archive_a1.py`); Stage 1–31 exit/freeze index; go-live / §7 Remaining |
| **Stage 32 H1** | Operator handoff pack — `docs/OPERATOR_HANDOFF_MVP.md`, `ops/mvp/operator-handoff.json` (`test_operator_handoff_h1.py`); live handoff / §7 Remaining |
| **Stage 32 N1** | Commercial release notes — `docs/RELEASE_NOTES_MVP.md`, `ops/mvp/release-notes.json` (`test_release_notes_n1.py`); packaging ≠ production live |
| **Stage 32 B1** | Post-MVP backlog — `docs/POST_MVP_BACKLOG_MVP.md`, `ops/mvp/post-mvp-backlog.json` (`test_post_mvp_backlog_b1.py`); ADR-001–006 + Remaining indexed; deferred scopes Remaining |
| **Stage 32 D1** | Handoff fidelity — `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`) maps A1–B1 → readiness / launch / deploy / security |
| **Stage 32 fidelity** | D1 maps A1–B1 handoff evidence — `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`); exit/freeze `docs/STAGE_32_EXIT_CRITERIA.md`, ADR-070 (`test_stage32_exit_h32x.py`); historical open ADR-069; live go-live / attestation / §7 / deferred ADR implementations remain Remaining |
| **Stage 39 open** | Commercial Contract Evidence Fidelity — `docs/STAGE_39_PLAN.md`, ADR-083 (`test_stage39_open.py`); Stages 1–38 remain frozen; closed under ADR-084 |
| **Stage 39 P1** | DPA / subprocessor honesty — `docs/DPA_SUBPROCESSOR_MVP.md`, `ops/mvp/dpa-subprocessor.json` (`test_dpa_subprocessor_p1.py`); signed DPA Remaining |
| **Stage 39 A1** | MSA security addendum honesty — `docs/MSA_ADDENDUM_MVP.md`, `ops/mvp/msa-addendum.json` (`test_msa_addendum_a1.py`); signed MSA Remaining |
| **Stage 39 D1** | Contract evidence fidelity — `docs/STAGE_39_FIDELITY.md` (`test_stage39_fidelity_d1.py`) maps P1–A1 → readiness / launch / deploy / security |
| **Stage 39 fidelity** | D1 maps P1–A1 contract evidence — `docs/STAGE_39_FIDELITY.md` (`test_stage39_fidelity_d1.py`); exit/freeze `docs/STAGE_39_EXIT_CRITERIA.md`, ADR-084 (`test_stage39_exit_h39x.py`); historical open ADR-083; signed DPA/MSA / go-live / §7 remain Remaining |
| **Stage 40 open** | Commercial Availability & Supply-Chain Fidelity — `docs/STAGE_40_PLAN.md`, ADR-085 (`test_stage40_open.py`); Stages 1–39 remain frozen; closed under ADR-086 |
| **Stage 40 U1** | Status page / uptime honesty — `docs/STATUS_UPTIME_MVP.md`, `ops/mvp/status-uptime.json` (`test_status_uptime_u1.py`); live status page / 99.9% SLA Remaining |
| **Stage 40 S1** | SBOM / dependency disclosure honesty — `docs/SBOM_DISCLOSURE_MVP.md`, `ops/mvp/sbom-disclosure.json` (`test_sbom_disclosure_s1.py`); live SBOM pipeline Remaining |
| **Stage 40 D1** | Availability & supply-chain fidelity — `docs/STAGE_40_FIDELITY.md` (`test_stage40_fidelity_d1.py`) maps U1–S1 → readiness / launch / deploy / security |
| **Stage 40 fidelity** | D1 maps U1–S1 availability & supply-chain — `docs/STAGE_40_FIDELITY.md` (`test_stage40_fidelity_d1.py`); exit/freeze `docs/STAGE_40_EXIT_CRITERIA.md`, ADR-086 (`test_stage40_exit_h40x.py`); historical open ADR-085; live status page / SBOM / go-live / §7 remain Remaining |
| **Stage 41 open** | Commercial Accessibility & Change Governance Fidelity — `docs/STAGE_41_PLAN.md`, ADR-087 (`test_stage41_open.py`); Stages 1–40 remain frozen; closed under ADR-088 |
| **Stage 41 A1** | Accessibility statement honesty — `docs/ACCESSIBILITY_STATEMENT_MVP.md`, `ops/mvp/accessibility-statement.json` (`test_accessibility_statement_a1.py`); WCAG AA audit Remaining |
| **Stage 41 C1** | Change / maintenance governance honesty — `docs/CHANGE_GOVERNANCE_MVP.md`, `ops/mvp/change-governance.json` (`test_change_governance_c1.py`); public change calendar Remaining |
| **Stage 41 D1** | Accessibility & change governance fidelity — `docs/STAGE_41_FIDELITY.md` (`test_stage41_fidelity_d1.py`) maps A1–C1 → readiness / launch / deploy / security |
| **Stage 41 fidelity** | D1 maps A1–C1 accessibility & change governance — `docs/STAGE_41_FIDELITY.md` (`test_stage41_fidelity_d1.py`); exit/freeze `docs/STAGE_41_EXIT_CRITERIA.md`, ADR-088 (`test_stage41_exit_h41x.py`); historical open ADR-087; WCAG AA audit / public change calendar / go-live / §7 remain Remaining |
| **Stage 42 open** | Commercial AI Transparency Fidelity — `docs/STAGE_42_PLAN.md`, ADR-089 (`test_stage42_open.py`); Stages 1–41 remain frozen; closed under ADR-090 |
| **Stage 42 A1** | AI use disclosure honesty — `docs/AI_USE_DISCLOSURE_MVP.md`, `ops/mvp/ai-use-disclosure.json` (`test_ai_use_disclosure_a1.py`); AI certification Remaining |
| **Stage 42 P1** | AI model / provider boundary honesty — `docs/AI_PROVIDER_BOUNDARY_MVP.md`, `ops/mvp/ai-provider-boundary.json` (`test_ai_provider_boundary_p1.py`); external LLM Remaining |
| **Stage 42 D1** | AI transparency fidelity — `docs/STAGE_42_FIDELITY.md` (`test_stage42_fidelity_d1.py`) maps A1–P1 → readiness / launch / deploy / security |
| **Stage 42 fidelity** | D1 maps A1–P1 AI transparency — `docs/STAGE_42_FIDELITY.md` (`test_stage42_fidelity_d1.py`); exit/freeze `docs/STAGE_42_EXIT_CRITERIA.md`, ADR-090 (`test_stage42_exit_h42x.py`); historical open ADR-089; external LLM / AI certification / go-live / §7 remain Remaining |
| **Stage 43 open** | Commercial Legal Notice Fidelity — `docs/STAGE_43_PLAN.md`, ADR-091 (`test_stage43_open.py`); Stages 1–42 remain frozen; closed under ADR-092 |
| **Stage 43 T1** | ToS / AUP honesty — `docs/TOS_AUP_MVP.md`, `ops/mvp/tos-aup.json` (`test_tos_aup_t1.py`); signed ToS Remaining |
| **Stage 43 C1** | Cookie / privacy notice honesty — `docs/COOKIE_PRIVACY_NOTICE_MVP.md`, `ops/mvp/cookie-privacy-notice.json` (`test_cookie_privacy_notice_c1.py`); live cookie-consent Remaining |
| **Stage 43 D1** | Legal notice fidelity — `docs/STAGE_43_FIDELITY.md` (`test_stage43_fidelity_d1.py`) maps T1–C1 → readiness / launch / deploy / security |
| **Stage 43 fidelity** | D1 maps T1–C1 legal notice — `docs/STAGE_43_FIDELITY.md` (`test_stage43_fidelity_d1.py`); exit/freeze `docs/STAGE_43_EXIT_CRITERIA.md`, ADR-092 (`test_stage43_exit_h43x.py`); historical open ADR-091; signed ToS / live cookie-consent / go-live / §7 remain Remaining |
| **Stage 44 open** | Commercial Data Trust Fidelity — `docs/STAGE_44_PLAN.md`, ADR-093 (`test_stage44_open.py`); Stages 1–43 remain frozen; closed under ADR-094 |
| **Stage 44 R1** | Data residency / localization honesty — `docs/DATA_RESIDENCY_MVP.md`, `ops/mvp/data-residency.json` (`test_data_residency_r1.py`); multi-region residency Remaining |
| **Stage 44 E1** | Encryption / key-management honesty — `docs/ENCRYPTION_KMS_MVP.md`, `ops/mvp/encryption-kms.json` (`test_encryption_kms_e1.py`); HSM / live Vault Remaining |
| **Stage 44 D1** | Data trust fidelity — `docs/STAGE_44_FIDELITY.md` (`test_stage44_fidelity_d1.py`) maps R1–E1 → readiness / launch / deploy / security |
| **Stage 44 fidelity** | D1 maps R1–E1 data trust — `docs/STAGE_44_FIDELITY.md` (`test_stage44_fidelity_d1.py`); exit/freeze `docs/STAGE_44_EXIT_CRITERIA.md`, ADR-094 (`test_stage44_exit_h44x.py`); historical open ADR-093; multi-region residency / HSM / Vault / go-live / §7 remain Remaining |
| **Stage 45 open** | Commercial Continuity & Exit Fidelity — `docs/STAGE_45_PLAN.md`, ADR-095 (`test_stage45_open.py`); Stages 1–44 remain frozen; closed under ADR-096 |
| **Stage 45 O1** | RTO / RPO recovery objectives honesty — `docs/RTO_RPO_MVP.md`, `ops/mvp/rto-rpo.json` (`test_rto_rpo_o1.py`); measured RTO/RPO Remaining |
| **Stage 45 T1** | Data retention / return honesty — `docs/DATA_RETENTION_RETURN_MVP.md`, `ops/mvp/data-retention-return.json` (`test_data_retention_return_t1.py`); data-return portal Remaining |
| **Stage 45 D1** | Continuity & exit fidelity — `docs/STAGE_45_FIDELITY.md` (`test_stage45_fidelity_d1.py`) maps O1–T1 → readiness / launch / deploy / security |
| **Stage 45 fidelity** | D1 maps O1–T1 continuity & exit — `docs/STAGE_45_FIDELITY.md` (`test_stage45_fidelity_d1.py`); exit/freeze `docs/STAGE_45_EXIT_CRITERIA.md`, ADR-096 (`test_stage45_exit_h45x.py`); historical open ADR-095; measured RTO/RPO / data-return portal / go-live / §7 remain Remaining |
| **Stage 46 open** | Commercial Liability & Remedy Fidelity — `docs/STAGE_46_PLAN.md`, ADR-097 (`test_stage46_open.py`); Stages 1–45 remain frozen; closed under ADR-098 |
| **Stage 46 L1** | Limitation of liability / indemnity honesty — `docs/LIABILITY_INDEMNITY_MVP.md`, `ops/mvp/liability-indemnity.json` (`test_liability_indemnity_l1.py`); signed liability-cap Remaining |
| **Stage 46 W1** | Service credit / warranty honesty — `docs/SERVICE_CREDIT_WARRANTY_MVP.md`, `ops/mvp/service-credit-warranty.json` (`test_service_credit_warranty_w1.py`); live service credits Remaining |
| **Stage 46 D1** | Liability & remedy fidelity — `docs/STAGE_46_FIDELITY.md` (`test_stage46_fidelity_d1.py`) maps L1–W1 → readiness / launch / deploy / security |
| **Stage 46 fidelity** | D1 maps L1–W1 liability & remedy — `docs/STAGE_46_FIDELITY.md` (`test_stage46_fidelity_d1.py`); exit/freeze `docs/STAGE_46_EXIT_CRITERIA.md`, ADR-098 (`test_stage46_exit_h46x.py`); historical open ADR-097; signed liability-cap / live service credits / go-live / §7 remain Remaining |
| **Stage 47 open** | Commercial Insurance & Audit Fidelity — `docs/STAGE_47_PLAN.md`, ADR-099 (`test_stage47_open.py`); Stages 1–46 remain frozen; closed under ADR-100 |
| **Stage 47 I1** | Cyber insurance / COI honesty — `docs/CYBER_INSURANCE_MVP.md`, `ops/mvp/cyber-insurance.json` (`test_cyber_insurance_i1.py`); issued COI Remaining |
| **Stage 47 A1** | Customer audit rights honesty — `docs/CUSTOMER_AUDIT_RIGHTS_MVP.md`, `ops/mvp/customer-audit-rights.json` (`test_customer_audit_rights_a1.py`); customer audit executed Remaining |
| **Stage 47 D1** | Insurance & audit fidelity — `docs/STAGE_47_FIDELITY.md` (`test_stage47_fidelity_d1.py`) maps I1–A1 → readiness / launch / deploy / security |
| **Stage 47 fidelity** | D1 maps I1–A1 insurance & audit — `docs/STAGE_47_FIDELITY.md` (`test_stage47_fidelity_d1.py`); exit/freeze `docs/STAGE_47_EXIT_CRITERIA.md`, ADR-100 (`test_stage47_exit_h47x.py`); historical open ADR-099; issued COI / customer audit executed / go-live / §7 remain Remaining |
| **Stage 48 open** | Commercial Services Fidelity — `docs/STAGE_48_PLAN.md`, ADR-101 (`test_stage48_open.py`); Stages 1–47 remain frozen; closed under ADR-102 |
| **Stage 48 P1** | Professional services / SOW honesty — `docs/PROFESSIONAL_SERVICES_SOW_MVP.md`, `ops/mvp/professional-services-sow.json` (`test_professional_services_sow_p1.py`); signed SOW Remaining |
| **Stage 48 T1** | Customer training / certification honesty — `docs/CUSTOMER_TRAINING_CERT_MVP.md`, `ops/mvp/customer-training-cert.json` (`test_customer_training_cert_t1.py`); live training Remaining |
| **Stage 48 D1** | Services fidelity — `docs/STAGE_48_FIDELITY.md` (`test_stage48_fidelity_d1.py`) maps P1–T1 → readiness / launch / deploy / security |
| **Stage 48 fidelity** | D1 maps P1–T1 services — `docs/STAGE_48_FIDELITY.md` (`test_stage48_fidelity_d1.py`); exit/freeze `docs/STAGE_48_EXIT_CRITERIA.md`, ADR-102 (`test_stage48_exit_h48x.py`); historical open ADR-101; signed SOW / live training / go-live / §7 remain Remaining |
| **Stage 49 open** | Commercial Channel & Pricing Fidelity — `docs/STAGE_49_PLAN.md`, ADR-103 (`test_stage49_open.py`); Stages 1–48 remain frozen; closed under ADR-104 |
| **Stage 49 R1** | Partner / reseller terms honesty — `docs/PARTNER_RESELLER_MVP.md`, `ops/mvp/partner-reseller.json` (`test_partner_reseller_r1.py`); live partner program Remaining |
| **Stage 49 L1** | Pricing transparency honesty — `docs/PRICING_TRANSPARENCY_MVP.md`, `ops/mvp/pricing-transparency.json` (`test_pricing_transparency_l1.py`); public pricing portal Remaining |
| **Stage 49 D1** | Channel & pricing fidelity — `docs/STAGE_49_FIDELITY.md` (`test_stage49_fidelity_d1.py`) maps R1–L1 → readiness / launch / deploy / security |
| **Stage 49 fidelity** | D1 maps R1–L1 channel & pricing — `docs/STAGE_49_FIDELITY.md` (`test_stage49_fidelity_d1.py`); exit/freeze `docs/STAGE_49_EXIT_CRITERIA.md`, ADR-104 (`test_stage49_exit_h49x.py`); historical open ADR-103; live partner program / public pricing portal / go-live / §7 remain Remaining |
| **Stage 50 open** | Commercial Acquisition & Trial Fidelity — `docs/STAGE_50_PLAN.md`, ADR-105 (`test_stage50_open.py`); Stages 1–49 remain frozen; closed under ADR-106 |
| **Stage 50 R1** | Referral program honesty — `docs/REFERRAL_PROGRAM_MVP.md`, `ops/mvp/referral-program.json` (`test_referral_program_r1.py`); live referral credits Remaining |
| **Stage 50 F1** | Freemium trial honesty — `docs/FREEMIUM_TRIAL_MVP.md`, `ops/mvp/freemium-trial.json` (`test_freemium_trial_f1.py`); live freemium conversion Remaining |
| **Stage 50 D1** | Acquisition & trial fidelity — `docs/STAGE_50_FIDELITY.md` (`test_stage50_fidelity_d1.py`) maps R1–F1 → readiness / launch / deploy / security |
| **Stage 50 fidelity** | D1 maps R1–F1 acquisition & trial — `docs/STAGE_50_FIDELITY.md` (`test_stage50_fidelity_d1.py`); exit/freeze `docs/STAGE_50_EXIT_CRITERIA.md`, ADR-106 (`test_stage50_exit_h50x.py`); historical open ADR-105; live referral credits / freemium conversion / go-live / §7 remain Remaining |
| **Stage 51 open** | Commercial Marketplace & Add-Ons Fidelity — `docs/STAGE_51_PLAN.md`, ADR-107 (`test_stage51_open.py`); Stages 1–50 remain frozen; closed under ADR-108 |
| **Stage 51 M1** | Marketplace presence honesty — `docs/MARKETPLACE_PRESENCE_MVP.md`, `ops/mvp/marketplace-presence.json` (`test_marketplace_presence_m1.py`); live marketplace listing Remaining |
| **Stage 51 A1** | Add-on services honesty — `docs/ADDON_SERVICES_MVP.md`, `ops/mvp/addon-services.json` (`test_addon_services_a1.py`); live add-on catalog Remaining |
| **Stage 51 D1** | Marketplace & add-ons fidelity — `docs/STAGE_51_FIDELITY.md` (`test_stage51_fidelity_d1.py`) maps M1–A1 → readiness / launch / deploy / security |
| **Stage 51 fidelity** | D1 maps M1–A1 marketplace & add-ons — `docs/STAGE_51_FIDELITY.md` (`test_stage51_fidelity_d1.py`); exit/freeze `docs/STAGE_51_EXIT_CRITERIA.md`, ADR-108 (`test_stage51_exit_h51x.py`); historical open ADR-107; live marketplace listing / add-on catalog / go-live / §7 remain Remaining |
| **Stage 52 open** | Commercial Partnerships & Renewal Fidelity — `docs/STAGE_52_PLAN.md`, ADR-109 (`test_stage52_open.py`); Stages 1–51 remain frozen; closed under ADR-110 |
| **Stage 52 I1** | Industry partnerships honesty — `docs/INDUSTRY_PARTNERSHIPS_MVP.md`, `ops/mvp/industry-partnerships.json` (`test_industry_partnerships_i1.py`); live industry partnership program Remaining |
| **Stage 52 R1** | Subscription renewal / annual discount honesty — `docs/SUBSCRIPTION_RENEWAL_MVP.md`, `ops/mvp/subscription-renewal.json` (`test_subscription_renewal_r1.py`); live annual-discount enforcement Remaining |
| **Stage 52 fidelity** | D1 maps I1–R1 partnerships & renewal — `docs/STAGE_52_FIDELITY.md` (`test_stage52_fidelity_d1.py`); exit/freeze `docs/STAGE_52_EXIT_CRITERIA.md`, ADR-110 (`test_stage52_exit_h52x.py`); historical open ADR-109; live industry partnership program / annual-discount enforcement / auto-renewal / go-live / §7 remain Remaining |
| **Stage 53 open** | Commercial API & Lifecycle Fidelity — `docs/STAGE_53_PLAN.md`, ADR-111 (`test_stage53_open.py`); Stages 1–52 remain frozen; closed under ADR-112 |
| **Stage 53 A1** | API & integration commercial honesty — `docs/API_INTEGRATION_COMMERCIAL_MVP.md`, `ops/mvp/api-integration-commercial.json` (`test_api_integration_commercial_a1.py`); live API rate-limit upgrade billing Remaining |
| **Stage 53 C1** | Cancellation / refund / churn policy honesty — `docs/CANCELLATION_CHURN_MVP.md`, `ops/mvp/cancellation-churn.json` (`test_cancellation_churn_c1.py`); live cancellation portal Remaining |
| **Stage 53 fidelity** | D1 maps A1–C1 API & lifecycle — `docs/STAGE_53_FIDELITY.md` (`test_stage53_fidelity_d1.py`); exit/freeze `docs/STAGE_53_EXIT_CRITERIA.md`, ADR-112 (`test_stage53_exit_h53x.py`); historical open ADR-111; live API upgrade billing / cancellation portal / refund / churn / go-live / §7 remain Remaining |
| **Stage 54 open** | Commercial Go-To-Market Fidelity — `docs/STAGE_54_PLAN.md`, ADR-113 (`test_stage54_open.py`); Stages 1–53 remain frozen; closed under ADR-114 |
| **Stage 54 M1** | Digital marketing / case studies / testimonials honesty — `docs/DIGITAL_MARKETING_MVP.md`, `ops/mvp/digital-marketing.json` (`test_digital_marketing_m1.py`); live digital marketing campaigns Remaining |
| **Stage 54 S1** | Direct sales honesty — `docs/DIRECT_SALES_MVP.md`, `ops/mvp/direct-sales.json` (`test_direct_sales_s1.py`); live inside-sales team Remaining |
| **Stage 54 fidelity** | D1 maps M1–S1 go-to-market — `docs/STAGE_54_FIDELITY.md` (`test_stage54_fidelity_d1.py`); exit/freeze `docs/STAGE_54_EXIT_CRITERIA.md`, ADR-114 (`test_stage54_exit_h54x.py`); historical open ADR-113; live digital marketing campaigns / inside-sales / published proof / go-live / §7 remain Remaining |
| **Stage 55 open** | Commercial Licensing & Positioning Fidelity — `docs/STAGE_55_PLAN.md`, ADR-115 (`test_stage55_open.py`); Stages 1–54 remain frozen; closed under ADR-116 |
| **Stage 55 W1** | White-label licensing commercial honesty — `docs/WHITE_LABEL_LICENSING_MVP.md`, `ops/mvp/white-label-licensing.json` (`test_white_label_licensing_w1.py`); live white-label licensing Remaining |
| **Stage 55 U1** | Unit economics / competitive positioning honesty — `docs/UNIT_ECONOMICS_POSITIONING_MVP.md`, `ops/mvp/unit-economics-positioning.json` (`test_unit_economics_positioning_u1.py`); measured CAC/LTV Remaining |
| **Stage 55 fidelity** | D1 maps W1–U1 licensing & positioning — `docs/STAGE_55_FIDELITY.md` (`test_stage55_fidelity_d1.py`); exit/freeze `docs/STAGE_55_EXIT_CRITERIA.md`, ADR-116 (`test_stage55_exit_h55x.py`); historical open ADR-115; live white-label licensing / measured CAC/LTV / competitive superiority / go-live / §7 remain Remaining |
| **Stage 69 open** | MVP Commercial Go-Live Fidelity — `docs/STAGE_69_PLAN.md`, ADR-144 (`test_stage69_open.py`); Stages 1–68 remain frozen for prior scopes; V1 next historically |
| **Stage 69 V1** | Pre-flight verification honesty — `docs/PREFLIGHT_VERIFICATION_MVP.md`, `ops/mvp/preflight-verification.json` (`test_preflight_verification_v1.py`); §§1–3 verified Remaining |
| **Stage 69 A1** | Go-live attestation honesty — `docs/GOLIVE_ATTESTATION_MVP.md`, `ops/mvp/golive-attestation.json` (`test_golive_attestation_a1.py`); §7 signed Remaining |
| **Stage 69 D1** | Commercial Go-Live fidelity — `docs/STAGE_69_FIDELITY.md` (`test_stage69_fidelity_d1.py`); maps V1–A1 → readiness / launch / deploy / security; §§1–3 / §7 remain Remaining |
| **Stage 69 H69x** | Exit + freeze — `docs/STAGE_69_EXIT_CRITERIA.md`, ADR-145 (`test_stage69_exit_h69x.py`); Stages 1–69 frozen for Stage 69 scope; Stage 70 opened via ADR-146 |
| **Stage 70 open** | First Commercial Day Fidelity — `docs/STAGE_70_PLAN.md`, ADR-146 (`test_stage70_open.py`); Stages 1–69 remain frozen for prior scopes; F1 next historically |
| **Stage 70 F1** | First commercial day ops honesty — `docs/FIRST_COMMERCIAL_DAY_MVP.md`, `ops/mvp/first-commercial-day.json` (`test_first_commercial_day_f1.py`); first-day live Remaining |
| **Stage 70 G1** | Commercial go-live closeout honesty — `docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md`, `ops/mvp/commercial-golive-closeout.json` (`test_commercial_golive_closeout_g1.py`); go-live Remaining |
| **Stage 70 D1** | First Commercial Day fidelity — `docs/STAGE_70_FIDELITY.md` (`test_stage70_fidelity_d1.py`); maps F1–G1 → readiness / launch / deploy / security; first-day / go-live remain Remaining |
| **Stage 70 H70x** | Exit + freeze — `docs/STAGE_70_EXIT_CRITERIA.md`, ADR-147 (`test_stage70_exit_h70x.py`); Stages 1–70 frozen for Stage 70 scope; Stage 71 opened via ADR-148 |
| **Stage 71 open** | Commercial Steady-State Fidelity — `docs/STAGE_71_PLAN.md`, ADR-148 (`test_stage71_open.py`); Stages 1–70 remain frozen for prior scopes; S1 next historically |
| **Stage 71 S1** | Steady-state commercial ops honesty — `docs/STEADY_STATE_OPS_MVP.md`, `ops/mvp/steady-state-ops.json` (`test_steady_state_ops_s1.py`); steady-state live Remaining |
| **Stage 71 A1** | Commercial acceptance gate honesty — `docs/COMMERCIAL_ACCEPTANCE_MVP.md`, `ops/mvp/commercial-acceptance.json` (`test_commercial_acceptance_a1.py`); acceptance Remaining |
| **Stage 71 D1** | Commercial Steady-State fidelity — `docs/STAGE_71_FIDELITY.md` (`test_stage71_fidelity_d1.py`); maps S1–A1 → readiness / launch / deploy / security; steady-state / acceptance remain Remaining |
| **Stage 71 H71x** | Exit + freeze — `docs/STAGE_71_EXIT_CRITERIA.md`, ADR-149 (`test_stage71_exit_h71x.py`); Stages 1–71 frozen for Stage 71 scope; Stage 72 opened via ADR-150 |
| **Stage 72 open** | Commercial Packaging Closeout Fidelity — `docs/STAGE_72_PLAN.md`, ADR-150 (`test_stage72_open.py`); Stages 1–71 remain frozen for prior scopes; R1 next historically |
| **Stage 72 R1** | Commercial residual remaining honesty — `docs/COMMERCIAL_RESIDUAL_MVP.md`, `ops/mvp/commercial-residual.json` (`test_commercial_residual_r1.py`); residual closed Remaining |
| **Stage 72 P1** | Commercial packaging archive honesty — `docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md`, `ops/mvp/commercial-packaging-archive.json` (`test_commercial_packaging_archive_p1.py`); archive live Remaining |
| **Stage 72 D1** | Commercial Packaging Closeout fidelity — `docs/STAGE_72_FIDELITY.md` (`test_stage72_fidelity_d1.py`); maps R1–P1 → readiness / launch / deploy / security; residual / archive remain Remaining |
| **Stage 72 H72x** | Exit + freeze — `docs/STAGE_72_EXIT_CRITERIA.md`, ADR-151 (`test_stage72_exit_h72x.py`); Stages 1–72 frozen for Stage 72 scope; Stage 73 opened via ADR-152 |
| **Stage 73 open** | Commercial Assurance Fidelity — `docs/STAGE_73_PLAN.md`, ADR-152 (`test_stage73_open.py`); Stages 1–72 remain frozen for prior scopes; E1 next historically |
| **Stage 73 E1** | Commercial evidence chain honesty — `docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md`, `ops/mvp/commercial-evidence-chain.json` (`test_commercial_evidence_chain_e1.py`); evidence chain live Remaining |
| **Stage 73 A1** | Commercial assurance boundary honesty — `docs/COMMERCIAL_ASSURANCE_MVP.md`, `ops/mvp/commercial-assurance.json` (`test_commercial_assurance_a1.py`); customer assurance Remaining |
| **Stage 73 D1** | Commercial Assurance fidelity — `docs/STAGE_73_FIDELITY.md` (`test_stage73_fidelity_d1.py`); maps E1–A1 → readiness / launch / deploy / security; evidence / assurance remain Remaining |
| **Stage 73 H73x** | Exit + freeze — `docs/STAGE_73_EXIT_CRITERIA.md`, ADR-153 (`test_stage73_exit_h73x.py`); Stages 1–73 frozen for Stage 73 scope; Stage 74 opened via ADR-154 |
| **Stage 74 open** | Commercial Operator Boundary Fidelity — `docs/STAGE_74_PLAN.md`, ADR-154 (`test_stage74_open.py`); Stages 1–73 remain frozen for prior scopes; S1 next historically |
| **Stage 74 S1** | Commercial support boundary honesty — `docs/COMMERCIAL_SUPPORT_MVP.md`, `ops/mvp/commercial-support.json` (`test_commercial_support_s1.py`); support boundary live Remaining |
| **Stage 74 U1** | Commercial status boundary honesty — `docs/COMMERCIAL_STATUS_MVP.md`, `ops/mvp/commercial-status.json` (`test_commercial_status_u1.py`); status page live Remaining |
| **Stage 74 D1** | Commercial Operator Boundary fidelity — `docs/STAGE_74_FIDELITY.md` (`test_stage74_fidelity_d1.py`); maps S1–U1 → readiness / launch / deploy / security; support / status remain Remaining |
| **Stage 74 H74x** | Exit + freeze — `docs/STAGE_74_EXIT_CRITERIA.md`, ADR-155 (`test_stage74_exit_h74x.py`); Stages 1–74 frozen for Stage 74 scope; Stage 75 opened via ADR-156 |
| **Stage 75 open** | Commercial Trust Boundary Fidelity — `docs/STAGE_75_PLAN.md`, ADR-156 (`test_stage75_open.py`); Stages 1–74 remain frozen for prior scopes; C1 next historically |
| **Stage 75 C1** | Commercial security contact honesty — `docs/COMMERCIAL_SECURITY_CONTACT_MVP.md`, `ops/mvp/commercial-security-contact.json` (`test_commercial_security_contact_c1.py`); security contact live Remaining |
| **Stage 75 P1** | Commercial privacy notice honesty — `docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md`, `ops/mvp/commercial-privacy-notice.json` (`test_commercial_privacy_notice_p1.py`); privacy notice live Remaining |
| **Stage 75 D1** | Commercial Trust Boundary fidelity — `docs/STAGE_75_FIDELITY.md` (`test_stage75_fidelity_d1.py`); maps C1–P1 → readiness / launch / deploy / security; security contact / privacy remain Remaining |
| **Stage 75 H75x** | Exit + freeze — `docs/STAGE_75_EXIT_CRITERIA.md`, ADR-157 (`test_stage75_exit_h75x.py`); Stages 1–75 frozen for Stage 75 scope; Stage 76 opened via ADR-158 |
| **Stage 76 open** | Commercial Contract Boundary Fidelity — `docs/STAGE_76_PLAN.md`, ADR-158 (`test_stage76_open.py`); Stages 1–75 remain frozen for prior scopes; T1 next historically |
| **Stage 76 T1** | Commercial terms honesty — `docs/COMMERCIAL_TERMS_MVP.md`, `ops/mvp/commercial-terms.json` (`test_commercial_terms_t1.py`); signed ToS Remaining |
| **Stage 76 B1** | Commercial billing deferred honesty — `docs/COMMERCIAL_BILLING_DEFERRED_MVP.md`, `ops/mvp/commercial-billing-deferred.json` (`test_commercial_billing_deferred_b1.py`); paid billing Remaining |
| **Stage 76 D1** | Commercial Contract Boundary fidelity — `docs/STAGE_76_FIDELITY.md` (`test_stage76_fidelity_d1.py`); maps T1–B1 → readiness / launch / deploy / security; signed ToS / paid billing remain Remaining |
| **Stage 76 H76x** | Exit + freeze — `docs/STAGE_76_EXIT_CRITERIA.md`, ADR-159 (`test_stage76_exit_h76x.py`); Stages 1–76 frozen for Stage 76 scope; Stage 77 opened via ADR-160 |
| **Stage 77 open** | Commercial Legal Envelope Fidelity — `docs/STAGE_77_PLAN.md`, ADR-160 (`test_stage77_open.py`); Stages 1–76 remain frozen for prior scopes; A1 next historically |
| **Stage 77 A1** | Commercial DPA honesty — `docs/COMMERCIAL_DPA_MVP.md`, `ops/mvp/commercial-dpa.json` (`test_commercial_dpa_a1.py`); signed DPA Remaining |
| **Stage 77 L1** | Commercial liability honesty — `docs/COMMERCIAL_LIABILITY_MVP.md`, `ops/mvp/commercial-liability.json` (`test_commercial_liability_l1.py`); liability cap signed Remaining |
| **Stage 77 D1** | Commercial Legal Envelope fidelity — `docs/STAGE_77_FIDELITY.md` (`test_stage77_fidelity_d1.py`); maps A1–L1 → readiness / launch / deploy / security; signed DPA / liability remain Remaining |
| **Stage 77 H77x** | Exit + freeze — `docs/STAGE_77_EXIT_CRITERIA.md`, ADR-161 (`test_stage77_exit_h77x.py`); Stages 1–77 frozen for Stage 77 scope; Stage 78 opened via ADR-162 |
| **Stage 78 open** | Commercial Procurement Boundary Fidelity — `docs/STAGE_78_PLAN.md`, ADR-162 (`test_stage78_open.py`); Stages 1–77 remain frozen for prior scopes; P1 next historically |
| **Stage 78 P1** | Commercial pricing honesty — `docs/COMMERCIAL_PRICING_MVP.md`, `ops/mvp/commercial-pricing.json` (`test_commercial_pricing_p1.py`); public pricing portal Remaining |
| **Stage 78 S1** | Commercial professional services honesty — `docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md`, `ops/mvp/commercial-professional-services.json` (`test_commercial_professional_services_s1.py`); signed SOW Remaining |
| **Stage 78 D1** | Commercial Procurement Boundary fidelity — `docs/STAGE_78_FIDELITY.md` (`test_stage78_fidelity_d1.py`); maps P1–S1 → readiness / launch / deploy / security; pricing / SOW remain Remaining |
| **Stage 78 H78x** | Exit + freeze — `docs/STAGE_78_EXIT_CRITERIA.md`, ADR-163 (`test_stage78_exit_h78x.py`); Stages 1–78 frozen for Stage 78 scope; Stage 79 opened via ADR-164 |
| **Stage 79 open** | Commercial Data Exit Fidelity — `docs/STAGE_79_PLAN.md`, ADR-164 (`test_stage79_open.py`); Stages 1–78 remain frozen for prior scopes; R1 next historically |
| **Stage 79 R1** | Commercial data retention honesty — `docs/COMMERCIAL_DATA_RETENTION_MVP.md`, `ops/mvp/commercial-data-retention.json` (`test_commercial_data_retention_r1.py`); data return portal Remaining |
| **Stage 79 A1** | Commercial customer audit honesty — `docs/COMMERCIAL_CUSTOMER_AUDIT_MVP.md`, `ops/mvp/commercial-customer-audit.json` (`test_commercial_customer_audit_a1.py`); customer audit rights live Remaining |
| **Stage 79 D1** | Commercial Data Exit fidelity — `docs/STAGE_79_FIDELITY.md` (`test_stage79_fidelity_d1.py`); maps R1–A1 → readiness / launch / deploy / security; retention / audit remain Remaining |
| **Stage 79 H79x** | Exit + freeze — `docs/STAGE_79_EXIT_CRITERIA.md`, ADR-165 (`test_stage79_exit_h79x.py`); Stages 1–79 frozen for Stage 79 scope; Stage 80 opened via ADR-166 |
| **Stage 80 open** | Dual-Console Dashboard Fidelity — `docs/STAGE_80_PLAN.md`, ADR-166 (`test_stage80_open.py`); Stages 1–79 remain frozen for prior scopes; P1 next historically |
| **Stage 80 P1** | Platform owner dashboard charts — `/api/v1/platform/dashboard/*` (`test_platform_dashboard_charts_p1.py`); no fabricated MRR (ADR-002) |
| **Stage 80 T1** | Tenant role-scoped dashboards — `dashboard_views` (`test_tenant_role_dashboard_t1.py`); cashier omits accounting/users aggregates |
| **Stage 80 D1** | Dual-Console Dashboard fidelity — `docs/STAGE_80_FIDELITY.md` (`test_stage80_fidelity_d1.py`); maps P1–T1 → readiness / launch / deploy / security; billing remains Remaining |
| **Stage 80 H80x** | Exit + freeze — `docs/STAGE_80_EXIT_CRITERIA.md`, ADR-167 (`test_stage80_exit_h80x.py`); Stages 1–80 frozen for Stage 80 scope; Stage 81 opened via ADR-168 |
| **Stage 81 open** | Dual-Console Admin Fidelity — `docs/STAGE_81_PLAN.md`, ADR-168 (`test_stage81_open.py`); Stages 1–80 remain frozen for prior scopes; A1 next historically |
| **Stage 81 A1** | Tenant Admin RBAC console surfaces — `/users`, `/admin/roles`, `/admin/permissions` (`test_admin_console_a1.py`) |
| **Stage 81 S1** | Store-scoped manager ops + isolation — `store_scope` (`test_store_scoped_manager_s1.py`); ADR-005 membership Remaining |
| **Stage 81 D1** | Dual-Console Admin fidelity — `docs/STAGE_81_FIDELITY.md` (`test_stage81_fidelity_d1.py`); maps A1–S1 → readiness / launch / deploy / security |
| **Stage 81 H81x** | Exit + freeze — `docs/STAGE_81_EXIT_CRITERIA.md`, ADR-169 (`test_stage81_exit_h81x.py`); Stages 1–81 frozen for Stage 81 scope; Stage 82 opened via ADR-170 |
| **Stage 82 open** | Dual-Console Surface Parity — `docs/STAGE_82_PLAN.md`, ADR-170 (`test_stage82_open.py`); Stages 1–81 remain frozen for prior scopes; C1 next historically |
| **Stage 82 C1** | Tenant dashboard chart/KPI subroutes — `/api/v1/dashboard/*` slices (`test_dashboard_slices_c1.py`) |
| **Stage 82 P1** | Platform Plans console + Activity alias — `/platform/plans` (`test_platform_plans_p1.py`); no fabricated MRR |
| **Stage 82 D1** | Dual-Console Surface Parity fidelity — `docs/STAGE_82_FIDELITY.md` (`test_stage82_fidelity_d1.py`); maps C1–P1 → readiness / launch / deploy / security |
| **Stage 82 H82x** | Exit + freeze — `docs/STAGE_82_EXIT_CRITERIA.md`, ADR-171 (`test_stage82_exit_h82x.py`); Stages 1–82 frozen for Stage 82 scope; Stage 83 opened via ADR-172 |
| **Stage 83 open** | Dual-Console Ops Fidelity — `docs/STAGE_83_PLAN.md`, ADR-172 (`test_stage83_open.py`); Stages 1–82 remain frozen for prior scopes; S1 next historically |
| **Stage 83 S1** | Store-scoped chart depth — `store_ids` on charts/slices (`test_store_scoped_charts_s1.py`) |
| **Stage 83 U1** | Tenant Admin user-ops — reset password + org assignment (`test_admin_user_ops_u1.py`) |
| **Stage 83 D1** | Dual-Console Ops fidelity — `docs/STAGE_83_FIDELITY.md` (`test_stage83_fidelity_d1.py`); maps S1–U1 → readiness / launch / deploy / security |
| **Stage 83 H83x** | Exit + freeze — `docs/STAGE_83_EXIT_CRITERIA.md`, ADR-173 (`test_stage83_exit_h83x.py`); Stages 1–83 frozen for Stage 83 scope; Stage 84+ requires CONTINUE/NEXT |
| **Stage 84 open** | Dual-Console Permission & Slice Fidelity — `docs/STAGE_84_PLAN.md`, ADR-174 (`test_stage84_open.py`); Stages 1–83 remain frozen for prior scopes; A1 next historically |
| **Stage 84 A1** | Dotted permission aliases — `view`→`read`; `inventory.view` / `inventory:read` (`test_permission_aliases_a1.py`) |
| **Stage 84 S1** | Dashboard slice depth — expenses-by-category + credit + cashier shift (`test_dashboard_slice_depth_s1.py`) |
| **Stage 84 D1** | Dual-Console Permission & Slice fidelity — `docs/STAGE_84_FIDELITY.md` (`test_stage84_fidelity_d1.py`); maps A1–S1 → readiness / launch / deploy / security |
| **Stage 84 H84x** | Exit + freeze — `docs/STAGE_84_EXIT_CRITERIA.md`, ADR-175 (`test_stage84_exit_h84x.py`); Stages 1–84 frozen for Stage 84 scope; Stage 85+ requires CONTINUE/NEXT |
| **Stage 85 open** | House Roster & Tenant Access Ops — `docs/STAGE_85_PLAN.md`, ADR-176 (`test_stage85_open.py`); Stages 1–84 remain frozen for prior scopes; R1 next historically |
| **Stage 85 R1** | Platform subscriptions roster — tenant×plan metadata (`test_platform_subscriptions_r1.py`); not live billing |
| **Stage 85 E1** | Admin email password reset — `POST /users/{id}/password-reset-email` (`test_admin_email_reset_e1.py`) |
| **Stage 85 L1** | Org-chart role catalog — Manager/Tenant Admin labels + system matrix (`test_org_role_catalog_l1.py`) |
| **Stage 85 D1** | House Roster & Tenant Access Ops fidelity — `docs/STAGE_85_FIDELITY.md` (`test_stage85_fidelity_d1.py`); maps R1–L1 → readiness / launch / deploy / security |
| **Stage 85 H85x** | Exit + freeze — `docs/STAGE_85_EXIT_CRITERIA.md`, ADR-177 (`test_stage85_exit_h85x.py`); Stages 1–85 frozen for Stage 85 scope; Stage 86+ requires CONTINUE/NEXT |
| **Stage 86 open** | House Provision & Platform Access Ops — `docs/STAGE_86_PLAN.md`, ADR-178 (`test_stage86_open.py`); Stages 1–85 remain frozen for prior scopes; P1 next historically |
| **Stage 86 P1** | House tenant provision — `POST /platform/tenants` (`test_platform_tenant_provision_p1.py`) |
| **Stage 86 E1** | Platform email password reset — `POST /platform/users/{id}/password-reset-email` (`test_platform_email_reset_e1.py`) |
| **Stage 86 A1** | Platform audit Activity depth — filters + `/platform/activity` (`test_platform_audit_activity_a1.py`) |
| **Stage 86 D1** | House Provision & Platform Access Ops fidelity — `docs/STAGE_86_FIDELITY.md` (`test_stage86_fidelity_d1.py`); maps P1–A1 → readiness / launch / deploy / security |
| **Stage 86 H86x** | Exit + freeze — `docs/STAGE_86_EXIT_CRITERIA.md`, ADR-179 (`test_stage86_exit_h86x.py`); Stages 1–86 frozen for Stage 86 scope; Stage 87+ requires CONTINUE/NEXT |
| **Stage 87 open** | House Integrity & Console Boundary Ops — `docs/STAGE_87_PLAN.md`, ADR-180 (`test_stage87_open.py`); Stages 1–86 remain frozen for prior scopes; X1 next historically |
| **Stage 87 X1** | Platform audit export + chain verify — `GET /platform/audit/export` / `GET /platform/audit/verify` (`test_platform_audit_integrity_x1.py`) |
| **Stage 87 Y1** | House ops surface polish — health cards, last_activity, operator notes (`test_house_ops_surface_y1.py`) |
| **Stage 87 Z1** | Console boundary hardening — `ribdigi_principal` cookie + middleware + soft-delete honesty (`test_console_boundary_z1.py`) |
| **Stage 87 D1** | House Integrity & Console Boundary Ops fidelity — `docs/STAGE_87_FIDELITY.md` (`test_stage87_fidelity_d1.py`); maps X1–Z1 → readiness / launch / deploy / security |
| **Stage 87 H87x** | Exit + freeze — `docs/STAGE_87_EXIT_CRITERIA.md`, ADR-181 (`test_stage87_exit_h87x.py`); Stages 1–87 frozen for Stage 87 scope; Stage 88+ requires CONTINUE/NEXT |
| **Stage 88 open** | House Lifecycle & Staff Security Ops — `docs/STAGE_88_PLAN.md`, ADR-182 (`test_stage88_open.py`); Stages 1–87 remain frozen for prior scopes; L1 next historically |
| **Stage 88 L1** | Tenant lifecycle controls — `PATCH /platform/tenants/{id}/lifecycle` + suspend reason (`test_platform_tenant_lifecycle_l1.py`) |
| **Stage 88 R1** | Tenant roster export + at-risk queue — `GET /platform/tenants/export` / `GET /platform/tenants/at-risk` (`test_platform_tenant_roster_r1.py`) |
| **Stage 88 S1** | Platform staff invite + session ops — email invite + `GET/DELETE /platform/users/sessions` (`test_platform_staff_security_s1.py`) |
| **Stage 88 D1** | House Lifecycle & Staff Security Ops fidelity — `docs/STAGE_88_FIDELITY.md` (`test_stage88_fidelity_d1.py`); maps L1–S1 → readiness / launch / deploy / security |
| **Stage 88 H88x** | Exit + freeze — `docs/STAGE_88_EXIT_CRITERIA.md`, ADR-183 (`test_stage88_exit_h88x.py`); Stages 1–88 frozen for Stage 88 scope; Stage 89+ requires CONTINUE/NEXT |
| **Stage 89 open** | House Customer Assist & Roster Intelligence Ops — `docs/STAGE_89_PLAN.md`, ADR-184 (`test_stage89_open.py`); Stages 1–88 remain frozen for prior scopes; A1 next historically |
| **Stage 89 A1** | House Tenant Admin assist — `POST /platform/tenants/{id}/admin/password-reset-email` / `…/admin/resend-verification` (`test_platform_tenant_admin_assist_a1.py`); no impersonation |
| **Stage 89 F1** | Roster filters + dashboard at-risk KPIs — `plan_code`/`industry` + `at_risk_count` (`test_platform_roster_intel_f1.py`) |
| **Stage 89 C1** | Plan catalog + billing roster depth — metadata catalog (`test_platform_catalog_billing_c1.py`) |
| **Stage 89 D1** | House Customer Assist & Roster Intelligence Ops fidelity — `docs/STAGE_89_FIDELITY.md` (`test_stage89_fidelity_d1.py`); maps A1–C1 → readiness / launch / deploy / security |
| **Stage 89 H89x** | Exit + freeze — `docs/STAGE_89_EXIT_CRITERIA.md`, ADR-185 (`test_stage89_exit_h89x.py`); Stages 1–89 frozen for Stage 89 scope; Stage 90+ requires CONTINUE/NEXT |
| **Stage 90 open** | House Operator Visibility & Delivery Ops — `docs/STAGE_90_PLAN.md`, ADR-186 (`test_stage90_open.py`); Stages 1–89 remain frozen for prior scopes; E1 next historically |
| **Stage 90 E1** | House email delivery visibility — `platform.email.delivery` audit + `delivery_only` (`test_platform_email_delivery_visibility_e1.py`); no fabricated SMTP success |
| **Stage 90 O1** | Operator surfaces — Health contacts/security posture + Settings runbook links (`test_house_operator_surfaces_o1.py`) |
| **Stage 90 Q1** | Roster findability + plan context — admin email search + detail soft limits (`test_platform_roster_findability_q1.py`) |
| **Stage 90 D1** | House Operator Visibility & Delivery Ops fidelity — `docs/STAGE_90_FIDELITY.md` (`test_stage90_fidelity_d1.py`); maps E1–Q1 → readiness / launch / deploy / security |
| **Stage 90 H90x** | Exit + freeze — `docs/STAGE_90_EXIT_CRITERIA.md`, ADR-187 (`test_stage90_exit_h90x.py`); Stages 1–90 frozen for Stage 90 scope; Stage 91+ requires CONTINUE/NEXT |
| **Stage 91 open** | House Operator Investigation & Evidence Ops — `docs/STAGE_91_PLAN.md`, ADR-188 (`test_stage91_open.py`); Stages 1–90 remain frozen for prior scopes; I1 next historically |
| **Stage 91 I1** | Audit/Activity date-range investigation — `from_date`/`to_date` + Activity 7d default (`test_platform_audit_investigation_i1.py`) |
| **Stage 91 N1** | Dashboard→roster deep-links + tenant last House email delivery (`test_platform_nav_delivery_n1.py`); no impersonation |
| **Stage 91 P1** | Staff presence / health required badges / House TZ / `GET /platform/evidence` (`test_house_posture_evidence_p1.py`); packaging honesty only — not go-live Complete |
| **Stage 91 D1** | House Operator Investigation & Evidence Ops fidelity — `docs/STAGE_91_FIDELITY.md` (`test_stage91_fidelity_d1.py`); maps I1–P1 → readiness / launch / deploy / security |
| **Stage 91 H91x** | Exit + freeze — `docs/STAGE_91_EXIT_CRITERIA.md`, ADR-189 (`test_stage91_exit_h91x.py`); Stages 1–91 frozen for Stage 91 scope; Stage 92+ requires CONTINUE/NEXT |
| **Stage 92 open** | House Console Workflow & Readiness Ops — `docs/STAGE_92_PLAN.md`, ADR-190 (`test_stage92_open.py`); Stages 1–91 remain frozen for prior scopes; B1 next historically |
| **Stage 92 B1** | Investigation export + evidence download — audit `delivery_only` export + Activity window parity + evidence UI (`test_stage92_console_workflow_b1.py`); no fabricated SMTP success |
| **Stage 92 G1** | Roster triage + commercial-metadata context — notes search / list delivery / Active·Trial links / soft-limit context / billing roster enrichment (`test_stage92_roster_context_g1.py`); no MRR |
| **Stage 92 K1** | House regional formats + protected CORS allowlist on health/evidence (`test_stage92_readiness_formats_k1.py`); packaging honesty only — not go-live Complete |
| **Stage 92 D1** | House Console Workflow & Readiness Ops fidelity — `docs/STAGE_92_FIDELITY.md` (`test_stage92_fidelity_d1.py`); maps B1–K1 → readiness / launch / deploy / security |
| **Stage 92 H92x** | Exit + freeze — `docs/STAGE_92_EXIT_CRITERIA.md`, ADR-191 (`test_stage92_exit_h92x.py`); Stages 1–92 frozen for Stage 92 scope; Stage 93+ requires CONTINUE/NEXT |
| **Stage 93 open** | House Navigation & Runtime Ops — `docs/STAGE_93_PLAN.md`, ADR-192 (`test_stage93_open.py`); Stages 1–92 remain frozen for prior scopes; M1 next historically |
| **Stage 93 M1** | Roster navigation & export — industries catalog, created_this_month, URL sync, notes limit, PDF delivery, grace column (`test_stage93_roster_navigation_m1.py`) |
| **Stage 93 J1** | Staff delivery & integrity — last invite delivery + audit verified_at (`test_stage93_staff_integrity_j1.py`); no fabricated SMTP success |
| **Stage 93 V1** | Format, evidence & runtime posture — number_format, house_runtime, Celery badge, CORS alert (`test_stage93_runtime_posture_v1.py`); packaging honesty only — not go-live Complete |
| **Stage 93 D1** | House Navigation & Runtime Ops fidelity — `docs/STAGE_93_FIDELITY.md` (`test_stage93_fidelity_d1.py`); maps M1–V1 → readiness / launch / deploy / security |
| **Stage 93 H93x** | Exit + freeze — `docs/STAGE_93_EXIT_CRITERIA.md`, ADR-193 (`test_stage93_exit_h93x.py`); Stages 1–93 frozen for Stage 93 scope; Stage 94+ requires CONTINUE/NEXT |
| **Stage 94 open** | House Discovery & Runtime Assurance Ops — `docs/STAGE_94_PLAN.md`, ADR-194 (`test_stage94_open.py`); Stages 1–93 remain frozen for prior scopes; W1 next historically |
| **Stage 94 W1** | Platform staff discovery — users `q`/`role`/`is_active`, URL sync, dashboard deep-link (`test_stage94_staff_discovery_w1.py`) |
| **Stage 94 H1** | Configuration integrity & release identity — support email + IANA timezone validation, protected `runtime_identity` (`test_stage94_configuration_integrity_h1.py`); packaging honesty only — not go-live Complete |
| **Stage 94 T2** | Console state & queue awareness — shell at-risk badge, Activity/Audit empty states, plans chart link (`test_stage94_console_state_t2.py`) |
| **Stage 94 D1** | House Discovery & Runtime Assurance Ops fidelity — `docs/STAGE_94_FIDELITY.md` (`test_stage94_fidelity_d1.py`); maps W1–T2 → readiness / launch / deploy / security |
| **Stage 94 H94x** | Exit + freeze — `docs/STAGE_94_EXIT_CRITERIA.md`, ADR-195 (`test_stage94_exit_h94x.py`); Stages 1–94 frozen for Stage 94 scope; Stage 95+ requires CONTINUE/NEXT |
| **Stage 95 open** | Tenant MVP Navigation Ops — `docs/STAGE_95_PLAN.md`, ADR-196 (`test_stage95_open.py`); Stages 1–94 remain frozen for prior scopes; N1 next historically |
| **Stage 95 N1** | Tenant Shell IA regrouping — Commerce/People/Finance/Operations; Settings/Stores/User Management (`test_stage95_shell_ia_n1.py`) |
| **Stage 95 P1** | Party & stock discoverability — Customers/Suppliers/Stock deep-links + `?tab=` write-back (`test_stage95_party_stock_p1.py`) |
| **Stage 95 C1** | Chrome & settings alias — profile/logout, mobile nav collapse (`test_stage95_chrome_c1.py`); packaging honesty only — not go-live Complete |
| **Stage 95 D1** | Tenant MVP Navigation Ops fidelity — `docs/STAGE_95_FIDELITY.md` (`test_stage95_fidelity_d1.py`); maps N1–C1 → readiness / launch / deploy / security |
| **Stage 95 H95x** | Exit + freeze — `docs/STAGE_95_EXIT_CRITERIA.md`, ADR-197 (`test_stage95_exit_h95x.py`); Stages 1–95 frozen for Stage 95 scope; Stage 96+ requires CONTINUE/NEXT |
| **Stage 96 open** | Tenant MVP Outline Surface Fidelity Ops — `docs/STAGE_96_PLAN.md`, ADR-198 (`test_stage96_open.py`); Stages 1–95 remain frozen for prior scopes; B1 next historically |
| **Stage 96 B1** | Dashboard Business Overview — Profit Summary, AP Payables, notification deep-links (`test_stage96_dashboard_overview_b1.py`) |
| **Stage 96 G1** | Global topbar search — `GET /search` RBAC-gated products + customers (`test_stage96_global_search_g1.py`); no fabricated hits |
| **Stage 96 L1** | Finance / Sales / Settings leaf fidelity — Money Transfer, Income, Billers alias, Delivery status (`test_stage96_leaf_fidelity_l1.py`) |
| **Stage 96 D1** | Outline surface fidelity — `docs/STAGE_96_FIDELITY.md` (`test_stage96_fidelity_d1.py`); maps B1–L1 → readiness / launch / deploy / security |
| **Stage 96 H96x** | Exit + freeze — `docs/STAGE_96_EXIT_CRITERIA.md`, ADR-199 (`test_stage96_exit_h96x.py`); Stages 1–96 frozen for Stage 96 scope; Stage 97+ requires CONTINUE/NEXT |
| **Stage 97 open** | Tenant MVP Module Leaf Honesty Ops — `docs/STAGE_97_PLAN.md`, ADR-200 (`test_stage97_open.py`); Stages 1–96 remain frozen for prior scopes; S1 next historically |
| **Stage 97 S1** | Sales surface honesty — invoice status filters + quotation→invoice honesty (`test_stage97_sales_honesty_s1.py`) |
| **Stage 97 P1** | Purchase & Finance discoverability — Outstanding Purchases, Purchase Settings, Opening Balances / Fiscal Period (`test_stage97_purchase_finance_p1.py`) |
| **Stage 97 I1** | Inventory & Settings leaf honesty — Sub Categories, QR labels, Tax/Email/SMS/Backup aliases (`test_stage97_inventory_settings_i1.py`) |
| **Stage 97 D1** | Module leaf honesty — `docs/STAGE_97_FIDELITY.md` (`test_stage97_fidelity_d1.py`); maps S1–I1 → readiness / launch / deploy / security |
| **Stage 97 H97x** | Exit + freeze — `docs/STAGE_97_EXIT_CRITERIA.md`, ADR-201 (`test_stage97_exit_h97x.py`); Stages 1–97 frozen for Stage 97 scope; Stage 98+ requires CONTINUE/NEXT |
| **Stage 98 open** | Tenant MVP Ops Queue & Returns Honesty Ops — `docs/STAGE_98_PLAN.md`, ADR-202 (`test_stage98_open.py`); Stages 1–97 remain frozen for prior scopes; Q1 next historically |
| **Stage 98 Q1** | Expense approval queue honesty — status filters + Pending Expenses (`test_stage98_expense_queue_q1.py`) |
| **Stage 98 R1** | Returns pipeline discoverability — Sales/Purchase Returns + draft→post honesty (`test_stage98_returns_pipeline_r1.py`) |
| **Stage 98 O1** | Stock ops & bank surface — Counts / Transfers / Bank Reconciliation / Cheques / Credit kind (`test_stage98_stock_bank_o1.py`) |
| **Stage 98 D1** | Ops queue honesty — `docs/STAGE_98_FIDELITY.md` (`test_stage98_fidelity_d1.py`); maps Q1–O1 → readiness / launch / deploy / security |
| **Stage 98 H98x** | Exit + freeze — `docs/STAGE_98_EXIT_CRITERIA.md`, ADR-203 (`test_stage98_exit_h98x.py`); Stages 1–98 frozen for Stage 98 scope; Stage 99+ requires CONTINUE/NEXT |
| **Stage 99 open** | Tenant MVP Document Pipeline Honesty Ops — `docs/STAGE_99_PLAN.md`, ADR-204 (`test_stage99_open.py`); Stages 1–98 remain frozen; T1 next historically |
| **Stage 99 T1** | Quote-to-Order pipeline honesty (`test_stage99_quote_order_t1.py`) |
| **Stage 99 C1** | Purchase Request-to-GRN pipeline discoverability (`test_stage99_pr_grn_c1.py`) |
| **Stage 99 L1** | Inventory lifecycle leaf discoverability (`test_stage99_inventory_lifecycle_l1.py`) |
| **Stage 99 D1** | Document pipeline honesty — `docs/STAGE_99_FIDELITY.md` (`test_stage99_fidelity_d1.py`) |
| **Stage 99 H99x** | Exit + freeze — `docs/STAGE_99_EXIT_CRITERIA.md`, ADR-205 (`test_stage99_exit_h99x.py`); Stages 1–99 frozen; Stage 100+ requires CONTINUE/NEXT |
| **Stage 100 open** | Tenant MVP Reports & Ledger Discovery Ops — `docs/STAGE_100_PLAN.md`, ADR-206 (`test_stage100_open.py`); Stages 1–99 remain frozen; R1 next historically |
| **Stage 100 R1** | Reports financial statement discoverability (`test_stage100_reports_statements_r1.py`) |
| **Stage 100 G1** | Accounting GL leaf discoverability (`test_stage100_gl_leaves_g1.py`) |
| **Stage 100 U1** | Tenant admin discovery honesty — users `q`/`role`/`is_active` + audit URL sync (`test_stage100_tenant_admin_u1.py`) |
| **Stage 100 D1** | Reports & ledger discovery — `docs/STAGE_100_FIDELITY.md` (`test_stage100_fidelity_d1.py`) |
| **Stage 100 H100x** | Exit + freeze — `docs/STAGE_100_EXIT_CRITERIA.md`, ADR-207 (`test_stage100_exit_h100x.py`); Stages 1–100 frozen; Stage 101+ requires CONTINUE/NEXT |
| **Stage 101 open** | Tenant MVP Inventory Ops & Shift History Ops — `docs/STAGE_101_PLAN.md`, ADR-208 (`test_stage101_open.py`); Stages 1–100 remain frozen; O1 next historically |
| **Stage 101 O1** | Opening Stock & Movements Shell discoverability (`test_stage101_opening_movements_o1.py`) |
| **Stage 101 E1** | Recurring Expenses leaf & notification deep-link honesty (`test_stage101_recurring_notify_e1.py`) |
| **Stage 101 P1** | POS session history discoverability (`test_stage101_pos_sessions_p1.py`) |
| **Stage 101 D1** | Inventory ops & shift history — `docs/STAGE_101_FIDELITY.md` (`test_stage101_fidelity_d1.py`) |
| **Stage 101 H101x** | Exit + freeze — `docs/STAGE_101_EXIT_CRITERIA.md`, ADR-209 (`test_stage101_exit_h101x.py`); Stages 1–101 frozen; Stage 102+ requires CONTINUE/NEXT |
| **Stage 102 open** | Tenant MVP Residual Reports & Surface Honesty Ops — `docs/STAGE_102_PLAN.md`, ADR-210 (`test_stage102_open.py`); Stages 1–101 remain frozen; R1 next historically |
| **Stage 102 R1** | Remaining Reports tab Shell discoverability (`test_stage102_reports_residual_r1.py`) |
| **Stage 102 T1** | Tax filing / company tax / inter-store transfer honesty (`test_stage102_tax_transfer_t1.py`) |
| **Stage 102 A1** | AI section + Activity surface discoverability (`test_stage102_ai_activity_a1.py`) |
| **Stage 102 D1** | Residual reports & surface honesty — `docs/STAGE_102_FIDELITY.md` (`test_stage102_fidelity_d1.py`) |
| **Stage 102 H102x** | Exit + freeze — `docs/STAGE_102_EXIT_CRITERIA.md`, ADR-211 (`test_stage102_exit_h102x.py`); Stages 1–102 frozen; Stage 103+ requires CONTINUE/NEXT |
| **Stage 103 open** | Tenant MVP Security, Backup & Company Org Ops — `docs/STAGE_103_PLAN.md`, ADR-212 (`test_stage103_open.py`); Stages 1–102 remain frozen; S1 next historically |
| **Stage 103 S1** | Security surface discoverability (`test_stage103_security_surface_s1.py`) |
| **Stage 103 B1** | Backup schedule & restore leaf honesty (`test_stage103_backup_leaves_b1.py`) |
| **Stage 103 C1** | Company org & numbering discoverability (`test_stage103_company_org_c1.py`) |
| **Stage 103 D1** | Security, backup & company org — `docs/STAGE_103_FIDELITY.md` (`test_stage103_fidelity_d1.py`) |
| **Stage 103 H103x** | Exit + freeze — `docs/STAGE_103_EXIT_CRITERIA.md`, ADR-213 (`test_stage103_exit_h103x.py`); Stages 1–103 frozen; Stage 104+ requires CONTINUE/NEXT |
| **Stage 104 open** | Tenant MVP Ledger Filters, Commerce Leaves & Admin Ops — `docs/STAGE_104_PLAN.md`, ADR-214 (`test_stage104_open.py`); Stages 1–103 remain frozen; A1 next historically |
| **Stage 104 A1** | Ledger journal & cheque filter honesty (`test_stage104_ledger_filters_a1.py`) |
| **Stage 104 I1** | Commerce products / purchase invoices / sales status leaves (`test_stage104_commerce_leaves_i1.py`) |
| **Stage 104 R1** | Credit section & admin roles discoverability (`test_stage104_credit_roles_r1.py`) |
| **Stage 104 D1** | Ledger filters, commerce leaves & admin — `docs/STAGE_104_FIDELITY.md` (`test_stage104_fidelity_d1.py`) |
| **Stage 104 H104x** | Exit + freeze — `docs/STAGE_104_EXIT_CRITERIA.md`, ADR-215 (`test_stage104_exit_h104x.py`); Stages 1–104 frozen; Stage 105+ requires CONTINUE/NEXT |
| **Stage 105 open** | Tenant MVP Permissions Matrix, Store Policies & Platform Audit Ops — `docs/STAGE_105_PLAN.md`, ADR-216 (`test_stage105_open.py`); Stages 1–104 remain frozen; P1 next historically |
| **Stage 105 P1** | Permissions matrix honesty (`test_stage105_permissions_matrix_p1.py`) |
| **Stage 105 S1** | Store policy leaves FEFO / reorder (`test_stage105_store_policies_s1.py`) |
| **Stage 105 A1** | Platform audit filter URL sync (`test_stage105_platform_audit_a1.py`) |
| **Stage 105 D1** | Permissions, store policies & platform audit — `docs/STAGE_105_FIDELITY.md` (`test_stage105_fidelity_d1.py`) |
| **Stage 105 H105x** | Exit + freeze — `docs/STAGE_105_EXIT_CRITERIA.md`, ADR-217 (`test_stage105_exit_h105x.py`); Stages 1–105 frozen; Stage 106+ requires CONTINUE/NEXT |
| **Stage 106 open** | Tenant MVP Approval Filters, Company Profile & Notification Inbox Ops — `docs/STAGE_106_PLAN.md`, ADR-218 (`test_stage106_open.py`); Stages 1–105 remain frozen; E1 next historically |
| **Stage 106 E1** | Expense scope & purchase settings honesty (`test_stage106_expense_scope_e1.py`) |
| **Stage 106 C1** | Company profile & departments discoverability (`test_stage106_company_profile_c1.py`) |
| **Stage 106 N1** | Notification inbox leaves (`test_stage106_notification_inbox_n1.py`) |
| **Stage 106 D1** | Approval filters, company profile & notification inbox — `docs/STAGE_106_FIDELITY.md` (`test_stage106_fidelity_d1.py`) |
| **Stage 106 H106x** | Exit + freeze — `docs/STAGE_106_EXIT_CRITERIA.md`, ADR-219 (`test_stage106_exit_h106x.py`); Stages 1–106 frozen; Stage 107+ requires CONTINUE/NEXT |
| **Stage 107 open** | Tenant MVP POS Sections, Commerce Filters & Ops Leaves Ops — `docs/STAGE_107_PLAN.md`, ADR-220 (`test_stage107_open.py`); Stages 1–106 remain frozen; P1 next historically |
| **Stage 107 P1** | POS sections honesty (`test_stage107_pos_sections_p1.py`) |
| **Stage 107 S1** | Commerce filters honesty (`test_stage107_commerce_filters_s1.py`) |
| **Stage 107 O1** | Ops leaves discoverability (`test_stage107_ops_leaves_o1.py`) |
| **Stage 107 D1** | POS sections, commerce filters & ops leaves — `docs/STAGE_107_FIDELITY.md` (`test_stage107_fidelity_d1.py`) |
| **Stage 107 H107x** | Exit + freeze — `docs/STAGE_107_EXIT_CRITERIA.md`, ADR-221 (`test_stage107_exit_h107x.py`); Stages 1–107 frozen; Stage 108+ requires CONTINUE/NEXT |
| **Stage 108 open** | Tenant MVP AI Analysis Leaves, Credit Statement & Users Directory Ops — `docs/STAGE_108_PLAN.md`, ADR-222 (`test_stage108_open.py`); Stages 1–107 remain frozen; A1 next historically |
| **Stage 108 A1** | AI analysis leaves honesty (`test_stage108_ai_analysis_a1.py`) |
| **Stage 108 C1** | Credit statement surfaces discoverability (`test_stage108_credit_statement_c1.py`) |
| **Stage 108 U1** | Users directory leaves discoverability (`test_stage108_users_directory_u1.py`) |
| **Stage 108 D1** | AI analysis leaves, credit statement & users directory — `docs/STAGE_108_FIDELITY.md` (`test_stage108_fidelity_d1.py`) |
| **Stage 108 H108x** | Exit + freeze — `docs/STAGE_108_EXIT_CRITERIA.md`, ADR-223 (`test_stage108_exit_h108x.py`); Stages 1–108 frozen; Stage 109+ requires CONTINUE/NEXT |
| **Stage 109 open** | Tenant MVP Report Filters, Document Status Leaves & Platform Status Ops — `docs/STAGE_109_PLAN.md`, ADR-224 (`test_stage109_open.py`); Stages 1–108 remain frozen; R1 next historically |
| **Stage 109 R1** | Report / tax / movements period & dimension URL sync (`test_stage109_report_filters_r1.py`) |
| **Stage 109 S1** | Sales document status Shell leaves (`test_stage109_sales_status_s1.py`) |
| **Stage 109 O1** | Platform status leaves + bank-recon hash (`test_stage109_ops_status_o1.py`) |
| **Stage 109 D1** | Report filters, document status leaves & platform status — `docs/STAGE_109_FIDELITY.md` (`test_stage109_fidelity_d1.py`) |
| **Stage 109 H109x** | Exit + freeze — `docs/STAGE_109_EXIT_CRITERIA.md`, ADR-225 (`test_stage109_exit_h109x.py`); Stages 1–109 frozen; Stage 110+ requires CONTINUE/NEXT |
| **Stage 110 open** | Tenant MVP Purchasing Status Leaves, Expense Decision Queue & Admin Audit Ops — `docs/STAGE_110_PLAN.md`, ADR-226 (`test_stage110_open.py`); Stages 1–109 remain frozen; P1 next historically |
| **Stage 110 P1** | Purchasing document status Shell leaves (`test_stage110_purchasing_status_p1.py`) |
| **Stage 110 E1** | Expense decision queue Shell leaves (`test_stage110_expense_queue_e1.py`) |
| **Stage 110 A1** | Admin Create Role hash & tenant Audit module leaves (`test_stage110_admin_audit_a1.py`) |
| **Stage 110 D1** | Purchasing status leaves, expense decision queue & admin audit — `docs/STAGE_110_FIDELITY.md` (`test_stage110_fidelity_d1.py`) |
| **Stage 110 H110x** | Exit + freeze — `docs/STAGE_110_EXIT_CRITERIA.md`, ADR-227 (`test_stage110_exit_h110x.py`); Stages 1–110 frozen; Stage 111+ requires CONTINUE/NEXT |
| **Stage 111 open** | Tenant MVP Inventory Movement Type Leaves, Posted Sales Returns & Cheque Hash Ops — `docs/STAGE_111_PLAN.md`, ADR-228 (`test_stage111_open.py`); Stages 1–110 remain frozen; I1 next historically |
| **Stage 111 I1** | Inventory movement_type Shell leaves (`test_stage111_inventory_movement_types_i1.py`) |
| **Stage 111 S1** | Posted Sales Returns Shell leaf (`test_stage111_posted_sales_returns_s1.py`) |
| **Stage 111 C1** | Accounting `#cheques` hash + deposited/cleared leaves (`test_stage111_cheque_hash_c1.py`) |
| **Stage 111 D1** | Inventory movement types, posted sales returns & cheque hash — `docs/STAGE_111_FIDELITY.md` (`test_stage111_fidelity_d1.py`) |
| **Stage 111 H111x** | Exit + freeze — `docs/STAGE_111_EXIT_CRITERIA.md`, ADR-229 (`test_stage111_exit_h111x.py`); Stages 1–111 frozen; Stage 112+ requires CONTINUE/NEXT |
| **Stage 112 open** | Tenant MVP Report Schedule Leaves, Stores Cash Drawer & Platform Plan Ops — `docs/STAGE_112_PLAN.md`, ADR-230 (`test_stage112_open.py`); Stages 1–111 remain frozen; R1 next historically |
| **Stage 112 R1** | Report schedule frequency/enabled Shell leaves (`test_stage112_report_schedules_r1.py`) |
| **Stage 112 S1** | Stores Cash Drawer hash leaf (`test_stage112_stores_cash_drawer_s1.py`) |
| **Stage 112 P1** | Platform plan_code leaves + at-risk hash (`test_stage112_platform_plan_p1.py`) |
| **Stage 112 D1** | Report schedule leaves, stores cash drawer & platform plan — `docs/STAGE_112_FIDELITY.md` (`test_stage112_fidelity_d1.py`) |
| **Stage 112 H112x** | Exit + freeze — `docs/STAGE_112_EXIT_CRITERIA.md`, ADR-231 (`test_stage112_exit_h112x.py`); Stages 1–112 frozen; Stage 113+ requires CONTINUE/NEXT |

| **Stage 68 open** | Platform ↔ Tenant Console Fidelity — `docs/STAGE_68_PLAN.md`, ADR-142 (`test_stage68_open.py`); historical open; closed via H68x / ADR-143 |
| **Stage 68 H1** | Ribdigi House console honesty — `docs/RIBDIGI_HOUSE_CONSOLE_MVP.md`, `ops/mvp/ribdigi-house-console.json` (`test_ribdigi_house_console_h1.py`); paid billing / live subscriptions Remaining |
| **Stage 68 T1** | Tenant Company console honesty — `docs/TENANT_COMPANY_CONSOLE_MVP.md`, `ops/mvp/tenant-company-console.json` (`test_tenant_company_console_t1.py`); module re-Complete / demo tenant Remaining |
| **Stage 68 D1** | Platform ↔ Tenant console fidelity — `docs/STAGE_68_FIDELITY.md` (`test_stage68_fidelity_d1.py`); maps H1–T1 → readiness / launch / deploy / security; paid billing / module re-Complete Remaining |
| **Stage 68 H68x** | Exit + freeze — `docs/STAGE_68_EXIT_CRITERIA.md`, ADR-143 (`test_stage68_exit_h68x.py`); Stages 1–68 frozen for Stage 68 scope; Stage 69 opened via ADR-144 |
| **Stage 68 fidelity** | D1 maps H1–T1 House & Tenant Company consoles — `docs/STAGE_68_FIDELITY.md` (`test_stage68_fidelity_d1.py`); historical open ADR-142; paid billing / module re-Complete Remaining |
| **Stage 67 open** | MVP Post-Launch Continuity Fidelity — `docs/STAGE_67_PLAN.md`, ADR-140 (`test_stage67_open.py`); historical open; closed via H67x / ADR-141 |
| **Stage 67 H1** | Production hypercare honesty — `docs/PRODUCTION_HYPERCARE_MVP.md`, `ops/mvp/production-hypercare.json` (`test_production_hypercare_h1.py`); live hypercare / incident drill Remaining |
| **Stage 67 C1** | Post-launch continuity honesty — `docs/POST_LAUNCH_CONTINUITY_MVP.md`, `ops/mvp/post-launch-continuity.json` (`test_post_launch_continuity_c1.py`); live continuity / steady-state handoff Remaining |
| **Stage 67 D1** | MVP post-launch continuity fidelity — `docs/STAGE_67_FIDELITY.md` (`test_stage67_fidelity_d1.py`); maps H1–C1 → readiness / launch / deploy / security |
| **Stage 67 H67x** | Exit + freeze — `docs/STAGE_67_EXIT_CRITERIA.md`, ADR-141 (`test_stage67_exit_h67x.py`); Stages 1–67 frozen for Stage 67 scope; Stage 68 opened via ADR-142 |
| **Stage 66 open** | MVP Production Launch Fidelity — `docs/STAGE_66_PLAN.md`, ADR-138 (`test_stage66_open.py`); historical open; closed via H66x / ADR-139 |
| **Stage 66 L1** | Production launch honesty — `docs/PRODUCTION_LAUNCH_MVP.md`, `ops/mvp/production-launch.json` (`test_production_launch_l1.py`); live cutover / §7 signed / go-live Remaining |
| **Stage 66 T1** | First tenant go-live honesty — `docs/FIRST_TENANT_GOLIVE_MVP.md`, `ops/mvp/first-tenant-golive.json` (`test_first_tenant_golive_t1.py`); first paying tenant / live onboarding Remaining |
| **Stage 66 D1** | MVP production-launch fidelity — `docs/STAGE_66_FIDELITY.md` (`test_stage66_fidelity_d1.py`); maps L1–T1 → readiness / launch / deploy / security; live cutover / first paying tenant / §7 Remaining |
| **Stage 66 H66x** | Exit + freeze — `docs/STAGE_66_EXIT_CRITERIA.md`, ADR-139 (`test_stage66_exit_h66x.py`); Stages 1–66 frozen for Stage 66 scope; Stage 67 opened via ADR-140 |
| **Stage 66 fidelity** | D1 maps L1–T1 production launch & first-tenant go-live — `docs/STAGE_66_FIDELITY.md` (`test_stage66_fidelity_d1.py`); historical open ADR-138; live cutover / first paying tenant / §7 Remaining |
| **Stage 65 open** | MVP Release Candidate Fidelity — `docs/STAGE_65_PLAN.md`, ADR-135 (`test_stage65_open.py`); historical open; closed via H65x / ADR-136 |
| **Stage 65 R1** | Release pipeline honesty — `docs/RELEASE_PIPELINE_MVP.md`, `ops/mvp/release-pipeline.json` (`test_release_pipeline_r1.py`); signed MVP RC / live staging promotion Remaining |
| **Stage 65 P1** | Controlled business pilot honesty — `docs/BUSINESS_PILOT_MVP.md`, `ops/mvp/business-pilot.json` (`test_business_pilot_p1.py`); live controlled business pilot Remaining |
| **Stage 65 D1** | MVP release-candidate fidelity — `docs/STAGE_65_FIDELITY.md` (`test_stage65_fidelity_d1.py`); maps R1–P1 → readiness / launch / deploy / security; signed MVP RC / live pilot Remaining |
| **Stage 65 H65x** | Exit + freeze — `docs/STAGE_65_EXIT_CRITERIA.md`, ADR-136 (`test_stage65_exit_h65x.py`); Stages 1–65 frozen for Stage 65 scope; Stage 66 opened via ADR-138 |
| **Stage 65 fidelity** | D1 maps R1–P1 release pipeline & pilot — `docs/STAGE_65_FIDELITY.md` (`test_stage65_fidelity_d1.py`); historical open ADR-135; signed MVP RC / live pilot Remaining |
| **Stage 64 open** | Commercial Analytics & Franchise Fidelity — `docs/STAGE_64_PLAN.md`, ADR-133 (`test_stage64_open.py`); closed under ADR-134; Stages 1–64 frozen for Stage 64 scope |
| **Stage 64 B1** | Advanced BI honesty — `docs/ADVANCED_BI_MVP.md`, `ops/mvp/advanced-bi.json` (`test_advanced_bi_b1.py`); live Advanced BI / custom analytics Remaining |
| **Stage 64 F1** | Franchise & chain enterprise honesty — `docs/FRANCHISE_CHAIN_MVP.md`, `ops/mvp/franchise-chain.json` (`test_franchise_chain_f1.py`); live franchise / chain deals Remaining |
| **Stage 64 D1** | Analytics & franchise fidelity — `docs/STAGE_64_FIDELITY.md` (`test_stage64_fidelity_d1.py`); maps B1–F1 → readiness / launch / deploy / security; live Advanced BI / franchise deals Remaining |
| **Stage 64 H64x** | Exit + freeze — `docs/STAGE_64_EXIT_CRITERIA.md`, ADR-134 (`test_stage64_exit_h64x.py`); Stage 65 opened via ADR-135; Stages 1–64 frozen for Stage 64 scope |
| **Stage 64 fidelity** | D1 maps B1–F1 analytics & franchise — `docs/STAGE_64_FIDELITY.md` (`test_stage64_fidelity_d1.py`); exit/freeze `docs/STAGE_64_EXIT_CRITERIA.md`, ADR-134 (`test_stage64_exit_h64x.py`); historical open ADR-133; live Advanced BI / franchise deals Remaining |
| **Stage 63 open** | Commercial Capital & Scale Fidelity — `docs/STAGE_63_PLAN.md`, ADR-131 (`test_stage63_open.py`); Stages 1–62 remain frozen; closed under ADR-132 |
| **Stage 63 P1** | IPO readiness honesty — `docs/IPO_READINESS_MVP.md`, `ops/mvp/ipo-readiness.json` (`test_ipo_readiness_p1.py`); live IPO / Series B–C funding Remaining |
| **Stage 63 G1** | Global scale honesty — `docs/GLOBAL_SCALE_MVP.md`, `ops/mvp/global-scale.json` (`test_global_scale_g1.py`); measured 50k customers / 20+ countries Remaining |
| **Stage 63 D1** | Capital & scale fidelity — `docs/STAGE_63_FIDELITY.md` (`test_stage63_fidelity_d1.py`); maps P1–G1 → readiness / launch / deploy / security; live IPO / measured global scale Remaining |
| **Stage 63 fidelity** | D1 maps P1–G1 capital & scale — `docs/STAGE_63_FIDELITY.md` (`test_stage63_fidelity_d1.py`); exit/freeze `docs/STAGE_63_EXIT_CRITERIA.md`, ADR-132 (`test_stage63_exit_h63x.py`); historical open ADR-131; live IPO / measured global scale Remaining |
| **Stage 62 open** | Commercial IoT & AI Marketplace Fidelity — `docs/STAGE_62_PLAN.md`, ADR-129 (`test_stage62_open.py`); Stages 1–61 remain frozen; closed under ADR-130 |
| **Stage 62 I1** | IoT integration honesty — `docs/IOT_INTEGRATION_MVP.md`, `ops/mvp/iot-integration.json` (`test_iot_integration_i1.py`); live smart shelves / temperature sensors Remaining |
| **Stage 62 A1** | AI model marketplace honesty — `docs/AI_MODEL_MARKETPLACE_MVP.md`, `ops/mvp/ai-model-marketplace.json` (`test_ai_model_marketplace_a1.py`); live industry-prediction marketplace Remaining |
| **Stage 62 D1** | IoT & AI marketplace fidelity — `docs/STAGE_62_FIDELITY.md` (`test_stage62_fidelity_d1.py`); maps I1–A1 → readiness / launch / deploy / security; live IoT / AI model marketplace Remaining |
| **Stage 62 fidelity** | D1 maps I1–A1 IoT & AI marketplace — `docs/STAGE_62_FIDELITY.md` (`test_stage62_fidelity_d1.py`); exit/freeze `docs/STAGE_62_EXIT_CRITERIA.md`, ADR-130 (`test_stage62_exit_h62x.py`); historical open ADR-129; live IoT / AI model marketplace Remaining |
| **Stage 61 open** | Commercial Fintech & Supply-Chain Fidelity — `docs/STAGE_61_PLAN.md`, ADR-127 (`test_stage61_open.py`); Stages 1–60 remain frozen; closed under ADR-128 |
| **Stage 61 F1** | Embedded fintech honesty — `docs/EMBEDDED_FINTECH_MVP.md`, `ops/mvp/embedded-fintech.json` (`test_embedded_fintech_f1.py`); live lending / invoice financing Remaining |
| **Stage 61 S1** | Supply chain integration honesty — `docs/SUPPLY_CHAIN_INTEGRATION_MVP.md`, `ops/mvp/supply-chain-integration.json` (`test_supply_chain_integration_s1.py`); live supplier supply-chain Remaining |
| **Stage 61 D1** | Fintech & supply-chain fidelity — `docs/STAGE_61_FIDELITY.md` (`test_stage61_fidelity_d1.py`); maps F1–S1 → readiness / launch / deploy / security; live lending / supplier supply-chain Remaining |
| **Stage 61 fidelity** | D1 maps F1–S1 fintech & supply-chain — `docs/STAGE_61_FIDELITY.md` (`test_stage61_fidelity_d1.py`); exit/freeze `docs/STAGE_61_EXIT_CRITERIA.md`, ADR-128 (`test_stage61_exit_h61x.py`); historical open ADR-127; live lending / supplier supply-chain Remaining |
| **Stage 60 open** | Commercial Manufacturing & Tax Fidelity — `docs/STAGE_60_PLAN.md`, ADR-125 (`test_stage60_open.py`); Stages 1–59 remain frozen; closed under ADR-126 |
| **Stage 60 M1** | Advanced manufacturing honesty — `docs/ADVANCED_MANUFACTURING_MVP.md`, `ops/mvp/advanced-manufacturing.json` (`test_advanced_manufacturing_m1.py`); live MRP / production scheduling Remaining |
| **Stage 60 T1** | Multi-country tax honesty — `docs/MULTI_COUNTRY_TAX_MVP.md`, `ops/mvp/multi-country-tax.json` (`test_multi_country_tax_t1.py`); live multi-country tax e-file Remaining |
| **Stage 60 D1** | Manufacturing & tax fidelity — `docs/STAGE_60_FIDELITY.md` (`test_stage60_fidelity_d1.py`); maps M1–T1 → readiness / launch / deploy / security; live MRP / tax e-file Remaining |
| **Stage 60 fidelity** | D1 maps M1–T1 manufacturing & tax — `docs/STAGE_60_FIDELITY.md` (`test_stage60_fidelity_d1.py`); exit/freeze `docs/STAGE_60_EXIT_CRITERIA.md`, ADR-126 (`test_stage60_exit_h60x.py`); historical open ADR-125; live MRP / tax e-file Remaining |
| **Stage 59 open** | Commercial Channel Extensions Fidelity — `docs/STAGE_59_PLAN.md`, ADR-123 (`test_stage59_open.py`); Stages 1–58 remain frozen; closed under ADR-124 |
| **Stage 59 E1** | E-commerce integration honesty — `docs/ECOMMERCE_INTEGRATION_MVP.md`, `ops/mvp/ecommerce-integration.json` (`test_ecommerce_integration_e1.py`); live Shopify / WooCommerce Remaining |
| **Stage 59 C1** | CRM commercial honesty — `docs/CRM_COMMERCIAL_MVP.md`, `ops/mvp/crm-commercial.json` (`test_crm_commercial_c1.py`); live CRM module / segmentation Remaining |
| **Stage 59 D1** | Channel extensions fidelity — `docs/STAGE_59_FIDELITY.md` (`test_stage59_fidelity_d1.py`); maps E1–C1 → readiness / launch / deploy / security; live Shopify / CRM Remaining |
| **Stage 59 fidelity** | D1 maps E1–C1 channel extensions — `docs/STAGE_59_FIDELITY.md` (`test_stage59_fidelity_d1.py`); exit/freeze `docs/STAGE_59_EXIT_CRITERIA.md`, ADR-124 (`test_stage59_exit_h59x.py`); historical open ADR-123; live Shopify / CRM Remaining |
| **Stage 58 open** | Commercial Business & AI Metrics Fidelity — `docs/STAGE_58_PLAN.md`, ADR-121 (`test_stage58_open.py`); Stages 1–57 remain frozen; closed under ADR-122 |
| **Stage 58 B1** | Business metrics honesty — `docs/BUSINESS_METRICS_MVP.md`, `ops/mvp/business-metrics.json` (`test_business_metrics_b1.py`); measured MRR / NRR Remaining |
| **Stage 58 I1** | AI metrics honesty — `docs/AI_METRICS_MVP.md`, `ops/mvp/ai-metrics.json` (`test_ai_metrics_i1.py`); measured AI adoption / accuracy Remaining |
| **Stage 58 fidelity** | D1 maps B1–I1 business & AI metrics — `docs/STAGE_58_FIDELITY.md` (`test_stage58_fidelity_d1.py`); exit/freeze `docs/STAGE_58_EXIT_CRITERIA.md`, ADR-122 (`test_stage58_exit_h58x.py`); historical open ADR-121; measured MRR / NRR / AI adoption / accuracy / go-live / §7 remain Remaining |
| **Stage 57 open** | Commercial Mobile & Metrics Fidelity — `docs/STAGE_57_PLAN.md`, ADR-119 (`test_stage57_open.py`); Stages 1–56 remain frozen; closed under ADR-120 |
| **Stage 57 A1** | Mobile app GTM honesty — `docs/MOBILE_APP_GTM_MVP.md`, `ops/mvp/mobile-app-gtm.json` (`test_mobile_app_gtm_a1.py`); live Flutter / store publish Remaining |
| **Stage 57 K1** | Success metrics honesty — `docs/SUCCESS_METRICS_MVP.md`, `ops/mvp/success-metrics.json` (`test_success_metrics_k1.py`); measured MAU / NPS / uptime Remaining |
| **Stage 57 fidelity** | D1 maps A1–K1 mobile & metrics — `docs/STAGE_57_FIDELITY.md` (`test_stage57_fidelity_d1.py`); exit/freeze `docs/STAGE_57_EXIT_CRITERIA.md`, ADR-120 (`test_stage57_exit_h57x.py`); historical open ADR-119; live Flutter / store publish / measured MAU / NPS / uptime / go-live / §7 remain Remaining |
| **Stage 56 open** | Commercial Onboarding & Expansion Fidelity — `docs/STAGE_56_PLAN.md`, ADR-117 (`test_stage56_open.py`); Stages 1–55 remain frozen; closed under ADR-118 |
| **Stage 56 O1** | Implementation & onboarding commercial honesty — `docs/IMPLEMENTATION_ONBOARDING_MVP.md`, `ops/mvp/implementation-onboarding.json` (`test_implementation_onboarding_o1.py`); live data-migration fee billing Remaining |
| **Stage 56 G1** | Geographic expansion honesty — `docs/GEOGRAPHIC_EXPANSION_MVP.md`, `ops/mvp/geographic-expansion.json` (`test_geographic_expansion_g1.py`); multi-market expansion Remaining |
| **Stage 56 fidelity** | D1 maps O1–G1 onboarding & expansion — `docs/STAGE_56_FIDELITY.md` (`test_stage56_fidelity_d1.py`); exit/freeze `docs/STAGE_56_EXIT_CRITERIA.md`, ADR-118 (`test_stage56_exit_h56x.py`); historical open ADR-117; live data-migration fee billing / multi-market expansion / international localization / go-live / §7 remain Remaining |
| **Stage 38 open** | Commercial Security Disclosure Fidelity — `docs/STAGE_38_PLAN.md`, ADR-081 (`test_stage38_open.py`); Stages 1–37 remain frozen; closed under ADR-082 |
| **Stage 38 V1** | Vulnerability disclosure — `docs/VULN_DISCLOSURE_MVP.md`, `ops/mvp/vuln-disclosure.json` (`test_vuln_disclosure_v1.py`); live disclosure / bug-bounty Remaining |
| **Stage 38 B1** | Breach notification / security contact — `docs/BREACH_NOTIFICATION_MVP.md`, `ops/mvp/breach-notification.json` (`test_breach_notification_b1.py`); live breach drill Remaining |
| **Stage 38 D1** | Security disclosure fidelity — `docs/STAGE_38_FIDELITY.md` (`test_stage38_fidelity_d1.py`) maps V1–B1 → readiness / launch / deploy / security |
| **Stage 38 fidelity** | D1 maps V1–B1 security disclosure — `docs/STAGE_38_FIDELITY.md` (`test_stage38_fidelity_d1.py`); exit/freeze `docs/STAGE_38_EXIT_CRITERIA.md`, ADR-082 (`test_stage38_exit_h38x.py`); historical open ADR-081; live disclosure / breach drill / go-live / §7 remain Remaining |
| **Stage 37 open** | Commercial Data Protection Fidelity — `docs/STAGE_37_PLAN.md`, ADR-079 (`test_stage37_open.py`); Stages 1–36 remain frozen; closed under ADR-080 |
| **Stage 37 P1** | Data subject access / portability — `docs/DATA_PORTABILITY_MVP.md`, `ops/mvp/data-portability.json` (`test_data_portability_p1.py`); GDPR / DSAR Remaining |
| **Stage 37 E1** | Erasure / soft-delete honesty — `docs/ERASURE_HONESTY_MVP.md`, `ops/mvp/erasure-honesty.json` (`test_erasure_honesty_e1.py`); hard-delete Remaining; ADR-003 |
| **Stage 37 D1** | Data protection fidelity — `docs/STAGE_37_FIDELITY.md` (`test_stage37_fidelity_d1.py`) maps P1–E1 → readiness / launch / deploy / security |
| **Stage 37 fidelity** | D1 maps P1–E1 data protection — `docs/STAGE_37_FIDELITY.md` (`test_stage37_fidelity_d1.py`); exit/freeze `docs/STAGE_37_EXIT_CRITERIA.md`, ADR-080 (`test_stage37_exit_h37x.py`); historical open ADR-079; GDPR / hard-delete / go-live / §7 remain Remaining |
| **Stage 36 open** | Commercial Assurance Completion Fidelity — `docs/STAGE_36_PLAN.md`, ADR-077 (`test_stage36_open.py`); Stages 1–35 remain frozen; closed under ADR-078 |
| **Stage 36 S1** | Support SLA boundary — `docs/SUPPORT_SLA_BOUNDARY_MVP.md`, `ops/mvp/support-sla-boundary.json` (`test_support_sla_boundary_s1.py`); live SLA Remaining; PagerDuty deferred |
| **Stage 36 B1** | Billing-deferred honesty — `docs/BILLING_DEFERRED_HONESTY_MVP.md`, `ops/mvp/billing-deferred-honesty.json` (`test_billing_deferred_honesty_b1.py`); paid billing Remaining; ADR-002 |
| **Stage 36 D1** | Assurance completion fidelity — `docs/STAGE_36_FIDELITY.md` (`test_stage36_fidelity_d1.py`) maps S1–B1 → readiness / launch / deploy / security |
| **Stage 36 fidelity** | D1 maps S1–B1 assurance completion — `docs/STAGE_36_FIDELITY.md` (`test_stage36_fidelity_d1.py`); exit/freeze `docs/STAGE_36_EXIT_CRITERIA.md`, ADR-078 (`test_stage36_exit_h36x.py`); historical open ADR-077; live SLA / paid billing / go-live / §7 remain Remaining |
| **Stage 35 open** | Commercial End-to-End Operational Smoke Fidelity — `docs/STAGE_35_PLAN.md`, ADR-075 (`test_stage35_open.py`); Stages 1–34 remain frozen; closed under ADR-076 |
| **Stage 35 T1** | Org bootstrap — `docs/E2E_ORG_BOOTSTRAP_MVP.md`, `ops/mvp/e2e-org-bootstrap.json` (`test_e2e_org_bootstrap_t1.py`); live bootstrap / demo tenants Remaining |
| **Stage 35 U1** | Users + RBAC — `docs/E2E_USERS_RBAC_MVP.md`, `ops/mvp/e2e-users-rbac.json` (`test_e2e_users_rbac_u1.py`); live provisioning Remaining; ADR-005 store membership deferred |
| **Stage 35 P1** | Purchase-to-stock — `docs/E2E_PURCHASE_STOCK_MVP.md`, `ops/mvp/e2e-purchase-stock.json` (`test_e2e_purchase_stock_p1.py`); live purchasing Remaining; PO Kanban deferred |
| **Stage 35 S1** | Sale-to-payment — `docs/E2E_SALE_PAYMENT_MVP.md`, `ops/mvp/e2e-sale-payment.json` (`test_e2e_sale_payment_s1.py`); live POS Remaining; USB/serial deferred |
| **Stage 35 V1** | Verify financials — `docs/E2E_VERIFY_FINANCIALS_MVP.md`, `ops/mvp/e2e-verify-financials.json` (`test_e2e_verify_financials_v1.py`); live verification Remaining; tax e-file deferred |
| **Stage 35 R1** | Backup + restore — `docs/E2E_BACKUP_RESTORE_MVP.md`, `ops/mvp/e2e-backup-restore.json` (`test_e2e_backup_restore_r1.py`); live restore Remaining; PITR drill deferred |
| **Stage 35 D1** | E2E smoke fidelity — `docs/STAGE_35_FIDELITY.md` (`test_stage35_fidelity_d1.py`) maps T1–R1 → readiness / launch / deploy / security |
| **Stage 35 fidelity** | D1 maps T1–R1 E2E smoke packs — `docs/STAGE_35_FIDELITY.md` (`test_stage35_fidelity_d1.py`); exit/freeze `docs/STAGE_35_EXIT_CRITERIA.md`, ADR-076 (`test_stage35_exit_h35x.py`); historical open ADR-075; live E2E smoke / go-live / §7 remain Remaining |
| **Stage 34 open** | Commercial Customer Assurance Fidelity — `docs/STAGE_34_PLAN.md`, ADR-073 (`test_stage34_open.py`); Stages 1–33 remain frozen; closed under ADR-074; S1/B1 deferred |
| **Stage 34 A1** | Assurance evidence — `docs/ASSURANCE_EVIDENCE_MVP.md`, `ops/mvp/assurance-evidence.json` (`test_assurance_evidence_a1.py`); live attestation / §7 Remaining |
| **Stage 34 C1** | Compliance questionnaire — `docs/COMPLIANCE_QUESTIONNAIRE_MVP.md`, `ops/mvp/compliance-questionnaire.json` (`test_compliance_questionnaire_c1.py`); SOC 2 / ISO certification Remaining |
| **Stage 34 D1** | Assurance fidelity — `docs/STAGE_34_FIDELITY.md` (`test_stage34_fidelity_d1.py`) maps A1–C1 → readiness / launch / deploy / security |
| **Stage 34 fidelity** | D1 maps A1–C1 assurance evidence — `docs/STAGE_34_FIDELITY.md` (`test_stage34_fidelity_d1.py`); exit/freeze `docs/STAGE_34_EXIT_CRITERIA.md`, ADR-074 (`test_stage34_exit_h34x.py`); historical open ADR-073; S1/B1 deferred; live attestation / §7 / SOC 2 / ISO remain Remaining |
| **Stage 33 open** | Commercial MVP Continuity Fidelity — `docs/STAGE_33_PLAN.md`, ADR-071 (`test_stage33_open.py`); Stages 1–32 remain frozen; closed under ADR-072 |
| **Stage 33 K1** | Residual risk register — `docs/RESIDUAL_RISK_MVP.md`, `ops/mvp/residual-risk-register.json` (`test_residual_risk_k1.py`); risks closed / go-live Remaining |
| **Stage 33 C1** | Compliance readiness — `docs/COMPLIANCE_READINESS_MVP.md`, `ops/mvp/compliance-readiness-register.json` (`test_compliance_readiness_c1.py`); SOC 2 / ISO certification Remaining |
| **Stage 33 F1** | First-tenant onboarding — `docs/FIRST_TENANT_ONBOARDING_MVP.md`, `ops/mvp/first-tenant-onboarding.json` (`test_first_tenant_onboarding_f1.py`); live onboarding success Remaining |
| **Stage 33 T1** | Knowledge transfer — `docs/KNOWLEDGE_TRANSFER_MVP.md`, `ops/mvp/knowledge-transfer.json` (`test_knowledge_transfer_t1.py`); live training Remaining |
| **Stage 33 D1** | Continuity fidelity — `docs/STAGE_33_FIDELITY.md` (`test_stage33_fidelity_d1.py`) maps K1–T1 → readiness / launch / deploy / security |
| **Stage 33 fidelity** | D1 maps K1–T1 continuity evidence — `docs/STAGE_33_FIDELITY.md` (`test_stage33_fidelity_d1.py`); exit/freeze `docs/STAGE_33_EXIT_CRITERIA.md`, ADR-072 (`test_stage33_exit_h33x.py`); historical open ADR-071; live go-live / attestation / §7 / SOC 2 / ISO / live onboarding / training / deferred ADR implementations remain Remaining |
| **Stage 30 L1** | Operator evidence ledger — `docs/EVIDENCE_LEDGER_MVP.md`, `ops/evidence/ledger.json` (`test_evidence_ledger_l1.py`); live runs / attestation Remaining |
| **Stage 30 I1** | Incident response / on-call pack — `docs/INCIDENT_PACK_MVP.md`, `ops/incident/` (`test_incident_pack_i1.py`); hosted PagerDuty / live rota Remaining |
| **Stage 30 S1** | Support & Admin runbook fidelity — `docs/SUPPORT_RUNBOOK_MVP.md`, `ops/support/` + ADMIN_MANUAL §§7/11/12 (`test_support_runbook_s1.py`); live ops SLA Remaining |
| **Stage 30 A1** | Go-live attestation matrix — `docs/ATTESTATION_PACK_MVP.md`, `ops/launch/attestation-matrix.json` (`test_attestation_pack_a1.py`); §§1–3 / §7 / attestation Remaining |
| **Stage 30 D1** | Go-live support fidelity — `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`) maps L1–A1 → readiness / launch / deploy / security / admin |
| **Stage 30 fidelity** | D1 maps L1–A1 go-live support evidence — `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`); exit/freeze `docs/STAGE_30_EXIT_CRITERIA.md`, ADR-066 (`test_stage30_exit_h30x.py`); historical open ADR-065; live attestation / §7 / hosted PagerDuty remain Remaining |

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
- Stage 19 D1 fidelity sync: BR-18–20 + readiness + launch §§1–5 — `docs/STAGE_19_FIDELITY.md` (`test_stage19_fidelity_d1.py`); auth/session U1 `test_auth_session_br19_u1.py`; Auth API K1 `test_auth_api_fidelity_k1.py`; exit met H19x / ADR-044 (`test_stage19_exit_h19x.py`)

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
- **Monitoring hooks:** `GET /api/v1/health` / `health/ready` and Prometheus-text `GET /api/v1/metrics` (Stage 5 H5). Stage 26 M1: versioned scrape/alerts (`ops/prometheus/`) + Fluent Bit log-ship example (`ops/logging/fluent-bit-ribdigi.conf.example`); evidence `test_ops_monitoring_m1.py`. Hosted Grafana/PagerDuty/SIEM deferred.
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
- Stage 26 W1 MVP strategy: WAL archiving → S3-compatible store + `.ribbak` offsite sync — `docs/DR_WAL_PITR_RUNBOOK.md`, `ops/postgres/`, `ops/backup/` (`test_wal_pitr_w1.py`)
- Operator staging PITR drill (base + WAL replay) remains Remaining; strategy RTO < 4 hours / RPO < 15 minutes when archive health is proven
- Logical tenant restore remains `.ribbak` (`docs/DR_LOGICAL_BACKUP_RUNBOOK.md`)

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

**MVP fidelity (Stage 33 C1):** Compliance readiness packaging maps control themes to existing packs — `docs/COMPLIANCE_READINESS_MVP.md`, `ops/mvp/compliance-readiness-register.json` (`test_compliance_readiness_c1.py`). Packaging keeps `soc2_complete_claimed: false`, `iso27001_complete_claimed: false`, `certification_complete_claimed: false` — not SOC 2 / ISO certification Complete.

**MVP fidelity (Stage 34 C1):** Compliance questionnaire boundary packaging maps customer questionnaire themes to Stage 33 C1 controls — `docs/COMPLIANCE_QUESTIONNAIRE_MVP.md`, `ops/mvp/compliance-questionnaire.json` (`test_compliance_questionnaire_c1.py`). Packaging keeps `soc2_complete_claimed: false`, `iso27001_complete_claimed: false`, `certification_complete_claimed: false`, `questionnaire_answers_certified: false` — not SOC 2 / ISO certification Complete.

---

## 15. Incident Response Plan

**MVP fidelity (Stage 30 I1):** Operator incident / on-call packaging — `docs/INCIDENT_PACK_MVP.md`, `ops/incident/incident-checklist.json`, `ops/incident/oncall-runbook.md.example` (`test_incident_pack_i1.py`). Extends Stage 26 M1 alerts + Stage 28 A1 Alertmanager. Packaging keeps `pagerduty_hosted_claimed: false`, `oncall_rota_live: false`, `incident_drill_executed: false` — not hosted PagerDuty SaaS Complete.

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
- [ ] Incident response runbook accessible to on-call team — Stage 30 I1 packs `ops/incident/oncall-runbook.md.example` (`docs/INCIDENT_PACK_MVP.md`, `test_incident_pack_i1.py`); live rota / hosted PagerDuty Remaining

**Stage 5 S1 verify:** `GET /api/v1/health` returns `security.rate_limit_enabled`, `openapi_enabled=false` in production, and response includes CSP + rate-limit headers.

**Stage 5 O1 / Stage 27 S1 verify:** run `pytest tests/test_owasp_smoke.py tests/test_owasp_suite_o1.py tests/test_owasp_suite_t1.py tests/test_security_scan_s1.py` — covers OWASP A01/A02/A03/A05/A07 automated controls + durable baseline evidence (`docs/SECURITY_SCAN_MVP.md`). Vendor ZAP / external pen test remain Remaining.

### 16.2 Ongoing Security Operations

- [ ] Daily review of security alerts and failed login attempts
- [ ] Weekly vulnerability scan of dependencies
- [ ] Monthly penetration test of authentication flows
- [x] Quarterly logical backup restore drill procedure documented + automated proof (Stage 5 B1 + Stage 23 B1 commercial MVP gate `test_logical_dr_drill_b1.py` / `stage23_b1_logical_drill.json`; infra WAL/PITR drill post-MVP)
- [ ] Quarterly access review (user roles and permissions)
- [ ] Annual third-party security audit
- [ ] Continuous monitoring of audit logs for anomalies

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Technical Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, JWT + OAuth2, Docker, Kubernetes  
**Owner:** Security Engineering Team  
**Review Cycle:** Quarterly or upon significant architectural change
