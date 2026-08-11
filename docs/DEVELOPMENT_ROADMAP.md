# Development Roadmap

## RIBDIGI BUSINESS ERP — MVP Development Roadmap

**Version:** 1.0.0  
**Classification:** Internal — Product & Engineering  
**Last Updated:** August 2026  
**Applies To:** RIBDIGI ERP MVP (Version 1.0)  
**Total Phases:** 5  
**Estimated Duration:** 24–28 Weeks

---

## Table of Contents

1. [Roadmap Overview](#1-roadmap-overview)
2. [Phase 1: Foundation & Platform Core](#2-phase-1-foundation--platform-core)
3. [Phase 2: Inventory & Supply Chain](#3-phase-2-inventory--supply-chain)
4. [Phase 3: Sales, POS & Financials](#4-phase-3-sales-pos--financials)
5. [Phase 4: Intelligence, Multi-Store & Scale](#5-phase-4-intelligence-multi-store--scale)
6. [Phase 5: Polish, Security & Launch](#6-phase-5-polish-security--launch)
7. [Appendix: Cross-Cutting Concerns](#7-appendix-cross-cutting-concerns)

---

## 1. Roadmap Overview

### 1.1 Development Philosophy

The MVP is delivered through **5 incremental phases**, each building upon the previous. Each phase produces a deployable milestone, enabling early validation, stakeholder feedback, and risk mitigation.

**Delivery Model:**
- Agile sprints (2-week cycles)
- Each phase = 4–6 sprints
- Continuous integration and deployment to staging
- Weekly demo to stakeholders
- Phase-gate review before proceeding

### 1.2 Phase Summary

| Phase | Name | Duration | Sprints | Key Deliverable |
|-------|------|----------|---------|-----------------|
| **1** | Foundation & Platform Core | 6 weeks | 3 | Working tenant registration, auth, user management, dashboard |
| **2** | Inventory & Supply Chain | 6 weeks | 3 | Full inventory + purchasing system with stock tracking |
| **3** | Sales, POS & Financials | 6 weeks | 3 | Sales pipeline, POS, accounting, tax, credit management |
| **4** | Intelligence, Multi-Store & Scale | 6 weeks | 3 | AI assistant, multi-store, reports, notifications |
| **5** | Polish, Security & Launch | 4–6 weeks | 2–3 | Security hardening, performance optimization, production launch |

### 1.3 Dependency Graph

```
Phase 1 (Foundation)
    │
    ├──▶ Phase 2 (Inventory)
    │       │
    │       ├──▶ Phase 3 (Sales + POS + Accounting)
    │       │       │
    │       │       ├──▶ Phase 4 (AI + Multi-Store + Reports)
    │       │       │       │
    │       │       │       └──▶ Phase 5 (Polish + Launch)
    │       │       │
    │       └──▶ (Purchasing depends on Inventory + Suppliers)
    │
    └──▶ (All phases depend on Foundation: Auth, Tenant, Users)
```

---

## 2. Phase 1: Foundation & Platform Core

**Duration:** 6 Weeks (3 Sprints)  
**Sprint Length:** 2 Weeks  
**Team Size:** 4 Engineers (2 Backend, 1 Frontend, 1 Full-Stack/DevOps)

### 2.1 Objective

Establish the technical foundation of the platform: multi-tenant architecture, authentication, user management, company setup, and the executive dashboard. This phase delivers the "shell" that all subsequent features inhabit.

**Stage 1 exit (2026-08-09):** Foundation workstreams A–H are recorded as met in `docs/STAGE_1_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_008_STAGE1_FREEZE.md` (no new Stage 1 feature scope).

**Stage 2 open (2026-08-09):** Inventory & Supply Chain hardening track approved — `docs/ADR_009_STAGE2_OPEN.md` + `docs/STAGE_2_PLAN.md`.

**Stage 2 exit (2026-08-09):** I1–I6 met — `docs/STAGE_2_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_010_STAGE2_FREEZE.md` (no new Stage 2 feature scope; amended when Stage 3 opened).

**Stage 3 open (2026-08-09):** Sales, POS & Financials hardening track approved — `docs/ADR_011_STAGE3_OPEN.md` + `docs/STAGE_3_PLAN.md`.

**Stage 3 exit (2026-08-09):** A1–A3, P1, C1 met — `docs/STAGE_3_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_012_STAGE3_FREEZE.md` (amended when Stage 4 opened).

**Stage 4 open (2026-08-09):** Intelligence, Multi-Store & Scale hardening track approved — `docs/ADR_013_STAGE4_OPEN.md` + `docs/STAGE_4_PLAN.md`.

**Stage 4 exit (2026-08-09):** T1, M1, N1, R1 met — `docs/STAGE_4_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_014_STAGE4_FREEZE.md` (amended when Stage 5 opened).

**Stage 5 open (2026-08-09):** Polish, Security & Launch hardening track approved — `docs/ADR_015_STAGE5_OPEN.md` + `docs/STAGE_5_PLAN.md`.

**Stage 5 exit (2026-08-09):** S1, O1, A1, B1, H5, L1 met — `docs/STAGE_5_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_016_STAGE5_FREEZE.md` (amended when Stage 6 opened).

**Stage 6 open (2026-08-09):** Integrations, Onboarding & Performance track approved — `docs/ADR_017_STAGE6_OPEN.md` + `docs/STAGE_6_PLAN.md`.

**Stage 6 exit (2026-08-09):** K1, W1, N2, P2 met — `docs/STAGE_6_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_018_STAGE6_FREEZE.md` (amended when Stage 7 opened).

**Stage 7 open (2026-08-09):** Launch Reliability Closeout track approved — `docs/ADR_019_STAGE7_OPEN.md` + `docs/STAGE_7_PLAN.md`.

**Stage 7 exit (2026-08-09):** W2, C2, K2, L7x met — `docs/STAGE_7_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_020_STAGE7_FREEZE.md`. Launch checklist: `docs/LAUNCH_CHECKLIST.md`.

**Stage 8 open (2026-08-09):** Credit Fidelity & AP Cash Closeout track approved — `docs/ADR_021_STAGE8_OPEN.md` + `docs/STAGE_8_PLAN.md`.

**Stage 8 exit (2026-08-09):** S1, S2, A1, P1, H8x met — `docs/STAGE_8_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_022_STAGE8_FREEZE.md`.

**Stage 9 open (2026-08-09):** Report Fidelity & Document Attachments Closeout track approved — `docs/ADR_023_STAGE9_OPEN.md` + `docs/STAGE_9_PLAN.md`.

**Stage 9 exit (2026-08-09):** J1, R1, R2, D1, H9x met — `docs/STAGE_9_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_024_STAGE9_FREEZE.md`. Fidelity: `docs/STAGE_9_FIDELITY.md`.

**Stage 10 open (2026-08-09):** Tax Fidelity & Document Workflow Closeout track approved — `docs/ADR_025_STAGE10_OPEN.md` + `docs/STAGE_10_PLAN.md`.

**Stage 10 exit (2026-08-09):** T1, T2, A1, B1, H10x met — `docs/STAGE_10_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_026_STAGE10_FREEZE.md`.

**Stage 11 open (2026-08-10):** Purchase-to-Pay Chain Fidelity track approved — `docs/ADR_027_STAGE11_OPEN.md` + `docs/STAGE_11_PLAN.md` (PO → GRN → inventory → supplier balance → accounting → audit).

**Stage 11 exit (2026-08-10):** C1, C2, A1, D1, H11x met — `docs/STAGE_11_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_028_STAGE11_FREEZE.md`. Fidelity: `docs/STAGE_11_FIDELITY.md`.

**Stage 12 open (2026-08-10):** Order-to-Cash & POS Chain Fidelity track approved — `docs/ADR_029_STAGE12_OPEN.md` + `docs/STAGE_12_PLAN.md` (Customers → Sales → Invoices → Payments → POS).

**Stage 12 exit (2026-08-10):** C1, C2, A1, D1, H12x met — `docs/STAGE_12_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_030_STAGE12_FREEZE.md`. Fidelity: `docs/STAGE_12_FIDELITY.md`.

**Stage 13 open (2026-08-10):** POS Sale Execution Chain Hardening track approved — `docs/ADR_031_STAGE13_OPEN.md` + `docs/STAGE_13_PLAN.md` (POS → Sale → Payment → Inventory → Receipt → Accounting → Audit).

**Stage 13 exit (2026-08-10):** H1, H2, D1, H13x met — `docs/STAGE_13_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_032_STAGE13_FREEZE.md`. Fidelity: `docs/STAGE_13_FIDELITY.md`.

**Stage 14 open (2026-08-10):** Finance Closeout Chain Fidelity track approved — `docs/ADR_033_STAGE14_OPEN.md` + `docs/STAGE_14_PLAN.md` (Expenses → Accounting → Credit → Tax).

**Stage 14 D1 (2026-08-10):** Spec / BR / readiness fidelity sync — `docs/STAGE_14_FIDELITY.md`.

**Stage 14 exit (2026-08-10):** E1, E2, A1, A2, T1, R1, A3, D1, H14x met — `docs/STAGE_14_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_034_STAGE14_FREEZE.md`. Fidelity: `docs/STAGE_14_FIDELITY.md`.

**Stage 15 open (2026-08-10):** Sales Inventory–Ledger Chain Fidelity track approved — `docs/ADR_035_STAGE15_OPEN.md` + `docs/STAGE_15_PLAN.md` (Sales → Inventory → Customer balance → Tax → Accounting → Audit).

**Stage 15 D1 (2026-08-10):** Spec / BR / readiness fidelity sync — `docs/STAGE_15_FIDELITY.md`.

**Stage 15 exit (2026-08-10):** C1, I1, H1, R1, T1, A1, D1, H15x met — `docs/STAGE_15_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_036_STAGE15_FREEZE.md`. Fidelity: `docs/STAGE_15_FIDELITY.md`.

**Stage 16 open (2026-08-10):** Multi-Store / Reports / Notifications Fidelity track approved — `docs/ADR_037_STAGE16_OPEN.md` + `docs/STAGE_16_PLAN.md` (Warehouses → Stock per location → Transfers → Transfer receiving → Central management; Reports suite; Notification alerts).

**Stage 16 D1 (2026-08-10):** Spec / BR-13–15 / readiness fidelity sync — `docs/STAGE_16_FIDELITY.md`.

**Stage 16 exit (2026-08-10):** M1, N1, R1, R2, M2, N2, D1, H16x met — `docs/STAGE_16_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_038_STAGE16_FREEZE.md`. Fidelity: `docs/STAGE_16_FIDELITY.md`.

**Stage 17 open (2026-08-10):** Inventory Catalog & Stock Ops Fidelity track approved — `docs/ADR_039_STAGE17_OPEN.md` + `docs/STAGE_17_PLAN.md` (Catalog → Stock Ops → Warehouse → Low Stock).

**Stage 17 D1 (2026-08-10):** Spec / BR-5.1–5.5 / readiness fidelity sync — `docs/STAGE_17_FIDELITY.md`.

**Stage 17 exit (2026-08-10):** C1, S1, S2, W1, L1, A1, D1, H17x met — `docs/STAGE_17_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_040_STAGE17_FREEZE.md`. Fidelity: `docs/STAGE_17_FIDELITY.md`.

**Stage 18 open (2026-08-10):** Launch Integrity & Ops Fidelity track approved — `docs/ADR_041_STAGE18_OPEN.md` + `docs/STAGE_18_PLAN.md` (Security → Backup/Restore → Data integrity → Logging/Monitoring → Test & deploy hygiene).

**Stage 18 D1 (2026-08-10):** Spec / BR-16–17 / readiness / launch fidelity sync — `docs/STAGE_18_FIDELITY.md`.

**Stage 18 exit (2026-08-10):** S1, A1, B1, I1, L1, T1, C1, D1, H18x met — `docs/STAGE_18_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_042_STAGE18_FREEZE.md`. Fidelity: `docs/STAGE_18_FIDELITY.md`.

**Stage 19 open (2026-08-10):** API, Settings & Operator Reliability Fidelity track approved — `docs/ADR_043_STAGE19_OPEN.md` + `docs/STAGE_19_PLAN.md` (API surface → Company & security settings → Operator reliability).

**Stage 19 D1 (2026-08-10):** Spec / BR-18–20 / readiness / launch fidelity sync — `docs/STAGE_19_FIDELITY.md`.

**Stage 19 exit (2026-08-10):** K1, P1, S1, A1, U1, C1, R1, D1, H19x met — `docs/STAGE_19_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_044_STAGE19_FREEZE.md`. Fidelity: `docs/STAGE_19_FIDELITY.md`.

**Stage 20 open (2026-08-10):** AI Business Assistant Fidelity track approved — `docs/ADR_045_STAGE20_OPEN.md` + `docs/STAGE_20_PLAN.md` (AI assistant surface → Inventory & sales intelligence → Customer & security AI).

**Stage 20 D1 (2026-08-10):** Spec / BR-21 / readiness / Phase 4 / USER_MANUAL / API fidelity sync — `docs/STAGE_20_FIDELITY.md` (`test_stage20_fidelity_d1.py`).

**Stage 20 exit (2026-08-10):** C1, I1, V1, L1, S1, R1, U1, D1, H20x met — `docs/STAGE_20_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_046_STAGE20_FREEZE.md`. Fidelity: `docs/STAGE_20_FIDELITY.md`.

**Stage 21 open (2026-08-10):** Tenant Lifecycle, Org & Dashboard Fidelity track approved — `docs/ADR_047_STAGE21_OPEN.md` + `docs/STAGE_21_PLAN.md` (tenant lifecycle → org/admin → identity shell → executive dashboard).

**Stage 21 D1 (2026-08-10):** Spec / BR-1–4 / readiness / USER_MANUAL / API / launch §§1–2 fidelity sync — `docs/STAGE_21_FIDELITY.md` (`test_stage21_fidelity_d1.py`).

**Stage 21 exit (2026-08-10):** T1, I1, O1, C1, U1, V1, N1, D1, H21x met — `docs/STAGE_21_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_048_STAGE21_FREEZE.md`. Fidelity: `docs/STAGE_21_FIDELITY.md`.

**Stage 22 open (2026-08-10):** Expenses, Ledger, Credit & Tax Surface Fidelity track approved — `docs/ADR_049_STAGE22_OPEN.md` + `docs/STAGE_22_PLAN.md` (expenses → ledger → credit/tax).

**Stage 22 D1 (2026-08-10):** Spec / BR-9–12 / readiness / USER_MANUAL / API / launch fidelity sync — `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

**Stage 22 exit (2026-08-10):** E1, A1, C1, B1, P1, R1, T1, D1, H22x met — `docs/STAGE_22_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_050_STAGE22_FREEZE.md`. Fidelity: `docs/STAGE_22_FIDELITY.md`.

**Stage 23 open (2026-08-10):** Reports Dimension & Commercial MVP Gate Fidelity track approved — `docs/ADR_051_STAGE23_OPEN.md` + `docs/STAGE_23_PLAN.md` (reports filters → gate closure).

**Stage 23 F1 (2026-08-10):** Balance sheet + financial `store_id`/`branch_id` filters — `test_financial_report_filters_f1.py` (BR-14.5).

**Stage 23 C1 (2026-08-10):** Financial comparative P&L / cash-flow / balance sheet — `test_financial_comparative_c1.py` (BR-14.5).

**Stage 23 I1 (2026-08-10):** Isolation matrix residual — liquid accounts/transfers, expense categories/recurring, report dimensions, mismatched header (`test_isolation_matrix_i1.py`).

**Stage 23 G1 (2026-08-10):** Commercial MVP gate closure — readiness honesty flips for isolation, lifecycle, expenses, accounting, tax, reports (`test_mvp_gate_closure_g1.py`); Remaining deferred-only (ADR-001/002, Open Banking, e-file, FIFO/LIFO/WA).

**Stage 23 B1 (2026-08-10):** Logical DR drill automation evidence — create → dry-run → guarded restore → verify + foreign-tenant 404; artifact `/opt/cursor/artifacts/dr/stage23_b1_logical_drill.json` (`test_logical_dr_drill_b1.py`); WAL/PITR deferred.

**Stage 23 D1 (2026-08-10):** Spec / BR-14 / readiness / USER_MANUAL / API fidelity sync — `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`); open ADR `docs/ADR_051_STAGE23_OPEN.md`; plan `docs/STAGE_23_PLAN.md`.

**Stage 23 exit (2026-08-10):** F1, C1, I1, G1, B1, D1, H23x met — `docs/STAGE_23_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_052_STAGE23_FREEZE.md`. Fidelity: `docs/STAGE_23_FIDELITY.md`.

**Stage 24 open (2026-08-10):** Commerce & Ops Gate Fidelity track approved — `docs/ADR_053_STAGE24_OPEN.md` + `docs/STAGE_24_PLAN.md` (numbering → commerce/ops/AI gate honesty).

**Stage 24 N1 (2026-08-10):** Shared document numbering series fidelity — configure/preview all `DOC_KEYS`; live QT/SO/INV/SR/CN/PO/GRN allocation (`test_document_numbering_n1.py`).

**Stage 24 G1 (2026-08-10):** Commerce gates closure — Inventory, Purchasing, Sales, POS, Multi-store Complete (MVP) (`test_commerce_gate_closure_g1.py`); Remaining deferred-only (Kanban, USB/serial, multi-bin, ADR-005).

**Stage 24 O1 (2026-08-10):** Ops Redis/Celery + AI MVP gate honesty — Redis/Celery intended workloads + AI provider/tenant-safe/functions Complete (MVP) (`test_ops_ai_gate_closure_o1.py`); Remaining PgBouncer/LLM/Prophet; monitoring/WAL/K8s/load stay open.

**Stage 24 D1 (2026-08-10):** Spec / BR-20.4 / readiness / USER_MANUAL / API fidelity sync — `docs/STAGE_24_FIDELITY.md` (`test_stage24_fidelity_d1.py`); open ADR `docs/ADR_053_STAGE24_OPEN.md`; plan `docs/STAGE_24_PLAN.md`.

**Stage 24 exit (2026-08-11):** N1, G1, O1, D1, H24x met — `docs/STAGE_24_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_054_STAGE24_FREEZE.md`. Fidelity: `docs/STAGE_24_FIDELITY.md`.

**Stage 25 open (2026-08-11):** Actuals → AI Analysis → Business Insights track approved — `docs/ADR_055_STAGE25_OPEN.md` + `docs/STAGE_25_PLAN.md` (Inv/Sales/Purch/Exp actuals → basic AI → insights).

**Stage 25 P1 (2026-08-11):** Purchases actuals → AI analysis — `GET /ai/purchases/analysis` spend trend, supplier concentration, PO fill/open backlog, overdue PI suggestions (`test_ai_purchases_analysis_p1.py`; BR-21.11).

**Stage 25 X1 (2026-08-11):** Cross-domain AI analysis — `GET /ai/cross-domain/analysis` orchestrates Inv/Sales/Purch/Exp analyzers + `cross_signals` (`test_ai_cross_domain_x1.py`; BR-21.12).

**Stage 25 B1 (2026-08-11):** Business Insights surface cites all four actuals — `GET /ai/insights` `domains`/`actuals_covered` + purchase spend/overdue/draft PO cards; dashboard/`/ai` UI (`test_ai_business_insights_b1.py`; BR-21.2).

**Stage 25 U1 (2026-08-11):** AI UI fidelity — `/ai` purchases analysis, cross-domain analysis, and document analyze panels (`test_ai_ui_fidelity_u1.py`; `frontend/app/ai/page.tsx`).

**Stage 25 D1 (2026-08-11):** Spec / BR-21.2 / 21.11 / 21.12 / readiness / USER_MANUAL / API fidelity sync — `docs/STAGE_25_FIDELITY.md` (`test_stage25_fidelity_d1.py`); open ADR `docs/ADR_055_STAGE25_OPEN.md`; plan `docs/STAGE_25_PLAN.md`.

**Stage 25 exit (2026-08-11):** P1, X1, B1, U1, D1, H25x met — `docs/STAGE_25_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_056_STAGE25_FREEZE.md`. Fidelity: `docs/STAGE_25_FIDELITY.md`.

**Stage 26 open (2026-08-11):** Production Platform & Ops Fidelity track approved — `docs/ADR_057_STAGE26_OPEN.md` + `docs/STAGE_26_PLAN.md` (Monitoring → WAL/PITR → K8s → Load capacity → fidelity).

**Stage 26 M1 (2026-08-11):** Monitoring & alerting fidelity — Prometheus scrape `ops/prometheus/prometheus.yml`, alerts `ops/prometheus/alerts/ribdigi.yml`, Fluent Bit example `ops/logging/fluent-bit-ribdigi.conf.example`, `docs/OPS_MONITORING_MVP.md` (`test_ops_monitoring_m1.py`); readiness monitoring Complete (MVP).

**Stage 26 W1 (2026-08-11):** WAL / PITR strategy + S3 offsite — `docs/DR_WAL_PITR_RUNBOOK.md`, `ops/postgres/` WAL archive configs, `ops/backup/sync-ribbak-offsite.sh.example`, evidence `stage26_w1_wal_pitr_strategy.json` (`test_wal_pitr_w1.py`); readiness WAL Complete (MVP); operator PITR drill Remaining.

**Stage 26 K1 (2026-08-11):** Kubernetes / Helm deploy fidelity — `helm/ribdigi/`, hardened `k8s/` with `/api/v1/health/ready` probes, `ops/k8s/` install/smoke, `docs/K8S_DEPLOY_MVP.md`, evidence `stage26_k1_deploy_fidelity.json` (`test_k8s_deploy_k1.py`); readiness Kubernetes Complete (MVP); live GHA→staging Remaining.

**Stage 26 C1 (2026-08-11):** Load capacity evidence — CI smoke + CI capacity profiles via `backend/loadtest/` (`--ci-capacity`), `docs/LOAD_CAPACITY_MVP.md`, evidence `stage26_c1_capacity_evidence.json` (`test_load_capacity_c1.py`); readiness load Complete (MVP); operator ~1000-VU Remaining.

**Stage 26 D1 (2026-08-11):** Spec / BR-16 / NFR §5.6 / readiness / deploy / launch / security fidelity sync — `docs/STAGE_26_FIDELITY.md` (`test_stage26_fidelity_d1.py`); open ADR `docs/ADR_057_STAGE26_OPEN.md`; plan `docs/STAGE_26_PLAN.md`.

**Stage 26 exit (2026-08-11):** M1, W1, K1, C1, D1, H26x met — `docs/STAGE_26_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_058_STAGE26_FREEZE.md`. Fidelity: `docs/STAGE_26_FIDELITY.md`.

**Stage 27 open (2026-08-11):** Commercial MVP Release Fidelity track approved — `docs/ADR_059_STAGE27_OPEN.md` + `docs/STAGE_27_PLAN.md` (Auto `.ribbak` offsite → PgBouncer → Security scan → Launch cert → fidelity).

**Stage 27 B1 (2026-08-11):** Automatic `.ribbak` offsite upload after `create_backup` — `BACKUP_OFFSITE_UPLOAD_ENABLED` / `BACKUP_OFFSITE_S3_BUCKET` / `BACKUP_OFFSITE_S3_PREFIX`; failure → `Backup failed` (no fake success); evidence `stage27_b1_offsite_upload.json` (`test_backup_offsite_b1.py`); operator `ops/backup/sync-ribbak-offsite.sh.example` retained.

**Stage 27 P1 (2026-08-11):** PgBouncer connection pooling fidelity — `ops/postgres/pgbouncer.ini.example`, `docker-compose.pgbouncer.example.yml`, `docs/PGBOUNCER_MVP.md`, evidence `stage27_p1_pgbouncer.json` (`test_pgbouncer_p1.py`); asyncpg statement cache disabled when URL targets PgBouncer; live soak / Helm pooler Remaining.

**Stage 27 S1 (2026-08-11):** Security scan / OWASP baseline evidence — `docs/SECURITY_SCAN_MVP.md`, `ops/security/zap-baseline.example.yml` (not in main CI), evidence `stage27_s1_security_scan.json` (`test_security_scan_s1.py`); vendor pen test / live ZAP staging Remaining.

**Stage 27 L1 (2026-08-11):** Launch certification pack — `docs/LAUNCH_CERT_MVP.md`, `ops/launch/checklist-map.json`, evidence `stage27_l1_launch_cert.json` (`test_launch_cert_l1.py`); operator §§1–3 / §7 remain unsigned (no fake production sign-off).

**Stage 27 D1 (2026-08-11):** Spec / BR-16 / readiness / deploy / launch / security fidelity sync — `docs/STAGE_27_FIDELITY.md` (`test_stage27_fidelity_d1.py`); open ADR `docs/ADR_059_STAGE27_OPEN.md`; plan `docs/STAGE_27_PLAN.md`.

**Stage 27 exit (2026-08-11):** B1, P1, S1, L1, D1, H27x met — `docs/STAGE_27_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_060_STAGE27_FREEZE.md`. Fidelity: `docs/STAGE_27_FIDELITY.md`.

**Stage 28 open (2026-08-11):** Staging Certification Fidelity track approved — `docs/ADR_061_STAGE28_OPEN.md` + `docs/STAGE_28_PLAN.md` (Operator PITR drill → Staging GHA → Grafana/Alertmanager → 1000-VU cert → fidelity).

**Stage 28 R1 (2026-08-11):** Operator PITR drill pack — `docs/PITR_DRILL_PACK_MVP.md`, `ops/postgres/pitr-drill-checklist.json`, evidence `stage28_r1_pitr_drill_pack.json` (`test_pitr_drill_pack_r1.py`); extends `docs/DR_WAL_PITR_RUNBOOK.md`; live staging drill execution Remaining (no fake CI PITR success).

**Stage 28 G1 (2026-08-11):** Staging GHA deploy workflow pack — `docs/STAGING_GHA_MVP.md`, `ops/k8s/deploy-staging.example.yml` (not main `ci.yml`), evidence `stage28_g1_staging_gha.json` (`test_staging_gha_g1.py`); live staging apply Remaining.

**Stage 28 A1 (2026-08-11):** Grafana / Alertmanager operator pack — `docs/GRAFANA_PACK_MVP.md`, `ops/grafana/dashboard-ribdigi-mvp.json.example`, `ops/grafana/alertmanager.yml.example`, evidence `stage28_a1_grafana_pack.json` (`test_grafana_pack_a1.py`); hosted SaaS Remaining.

**Stage 28 C1 (2026-08-11):** Operator ~1000-VU cert pack — `docs/LOAD_CERT_PACK_MVP.md`, `ops/loadtest/1000vu-cert-checklist.json`, `ops/loadtest/operator_1000vu_run.example.json`, evidence `stage28_c1_load_cert_pack.json` (`test_load_cert_pack_c1.py`); live 1000-VU execution Remaining (no forged certificate).

**Stage 28 D1 (2026-08-11):** Spec / BR-16 / readiness / deploy / launch / security fidelity sync — `docs/STAGE_28_FIDELITY.md` (`test_stage28_fidelity_d1.py`); open ADR `docs/ADR_061_STAGE28_OPEN.md`; plan `docs/STAGE_28_PLAN.md`.

**Stage 28 exit (2026-08-11):** R1, G1, A1, C1, D1, H28x met — `docs/STAGE_28_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_062_STAGE28_FREEZE.md`. Fidelity: `docs/STAGE_28_FIDELITY.md`.

**Stage 29 open (2026-08-11):** Operator Hardening & Production Cutover Fidelity track approved — `docs/ADR_063_STAGE29_OPEN.md` + `docs/STAGE_29_PLAN.md` (Vendor pen-test/ZAP → PgBouncer soak → Cert-manager/TLS → Production cutover → fidelity).

**Stage 29 V1 (2026-08-11):** Vendor pen-test / ZAP staging pack — `docs/PENTEST_PACK_MVP.md`, `ops/security/pentest-engagement-checklist.json`, `ops/security/vendor-engagement.example.json`, evidence `stage29_v1_pentest_pack.json` (`test_pentest_pack_v1.py`); purchased cert / live ZAP Remaining.

**Stage 29 B2 (2026-08-11):** PgBouncer soak / pooler pack — `docs/PGBOUNCER_SOAK_PACK_MVP.md`, `ops/postgres/pgbouncer-soak-checklist.json`, `ops/postgres/pgbouncer-deployment.example.yaml`, evidence `stage29_b2_pgbouncer_soak.json` (`test_pgbouncer_soak_b2.py`); live soak / default Helm pooler Remaining.

**Stage 29 T1 (2026-08-11):** Cert-manager / TLS ingress pack — `docs/TLS_INGRESS_PACK_MVP.md`, `ops/k8s/cluster-issuer.example.yaml`, `ops/k8s/ingress-tls.example.yaml`, evidence `stage29_t1_tls_ingress.json` (`test_tls_ingress_t1.py`); live ACME issuance / TLS cutover Remaining.

**Stage 29 X1 (2026-08-11):** Production cutover pack — `docs/CUTOVER_PACK_MVP.md`, `ops/launch/cutover-checklist.json`, `ops/k8s/deploy-production.example.yml`, evidence `stage29_x1_cutover_pack.json` (`test_cutover_pack_x1.py`); live cutover / §7 sign-off Remaining.

**Stage 29 D1 (2026-08-11):** Operator hardening & cutover fidelity sync — `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`) maps V1–X1 → BR-16 / readiness / deploy / launch / security; H29x next.

**Stage 29 exit (2026-08-11):** V1, B2, T1, X1, D1, H29x met — `docs/STAGE_29_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_064_STAGE29_FREEZE.md`. Fidelity: `docs/STAGE_29_FIDELITY.md`.

**Stage 30 open (2026-08-11):** Go-Live Support Fidelity track approved — `docs/ADR_065_STAGE30_OPEN.md` + `docs/STAGE_30_PLAN.md` (Evidence ledger → Incident/on-call → Support/Admin runbooks → Attestation → fidelity).

**Stage 30 L1 (2026-08-11):** Operator evidence ledger — `docs/EVIDENCE_LEDGER_MVP.md`, `ops/evidence/ledger.json`, evidence `stage30_l1_evidence_ledger.json` (`test_evidence_ledger_l1.py`); live runs / attestation Remaining.

**Stage 30 I1 (2026-08-11):** Incident response / on-call pack — `docs/INCIDENT_PACK_MVP.md`, `ops/incident/incident-checklist.json`, `ops/incident/oncall-runbook.md.example`, evidence `stage30_i1_incident_pack.json` (`test_incident_pack_i1.py`); hosted PagerDuty / live rota Remaining.

**Stage 30 S1 (2026-08-11):** Support & Admin runbook fidelity — `docs/SUPPORT_RUNBOOK_MVP.md`, `ops/support/admin-ops-map.json`, ADMIN_MANUAL §§7/11/12 sync, evidence `stage30_s1_support_runbook.json` (`test_support_runbook_s1.py`); live ops SLA Remaining.

**Stage 30 A1 (2026-08-11):** Go-live attestation matrix — `docs/ATTESTATION_PACK_MVP.md`, `ops/launch/attestation-matrix.json`, evidence `stage30_a1_attestation_pack.json` (`test_attestation_pack_a1.py`); §§1–3 / §7 / attestation Remaining.

**Stage 30 D1 (2026-08-11):** Go-live support fidelity sync — `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`) maps L1–A1 → BR-16 / readiness / deploy / launch / security / admin; H30x next.

**Stage 30 exit (2026-08-11):** L1, I1, S1, A1, D1, H30x met — `docs/STAGE_30_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_066_STAGE30_FREEZE.md`. Fidelity: `docs/STAGE_30_FIDELITY.md`.

**Stage 31 open (2026-08-11):** Commercial MVP Closeout Fidelity track approved — `docs/ADR_067_STAGE31_OPEN.md` + `docs/STAGE_31_PLAN.md` (Gate honesty → Deferred ADR register → Operator Remaining → MVP declaration → fidelity).

**Stage 31 G1 (2026-08-11):** MVP gate honesty matrix — `docs/MVP_GATE_MATRIX_MVP.md`, `ops/mvp/gate-matrix.json`, evidence `stage31_g1_mvp_gate_matrix.json` (`test_mvp_gate_matrix_g1.py`); go-live / §7 Remaining.

**Stage 31 R1 (2026-08-11):** Deferred ADR register — `docs/DEFERRED_ADR_REGISTER_MVP.md`, `ops/mvp/deferred-adr-register.json`, evidence `stage31_r1_deferred_adr_register.json` (`test_deferred_adr_register_r1.py`); ADR-001–006 post-MVP scopes Remaining.

**Stage 31 O1 (2026-08-11):** Operator Remaining register — `docs/OPERATOR_REMAINING_MVP.md`, `ops/mvp/operator-remaining-register.json`, evidence `stage31_o1_operator_remaining.json` (`test_operator_remaining_o1.py`); live runs / attestation / §7 Remaining.

**Stage 31 C1 (2026-08-11):** Commercial MVP declaration — `docs/MVP_DECLARATION_MVP.md`, `ops/mvp/mvp-declaration.json`, evidence `stage31_c1_mvp_declaration.json` (`test_mvp_declaration_c1.py`); packaging Complete ≠ live go-live / §7.

**Stage 31 D1 (2026-08-11):** Commercial MVP closeout fidelity sync — `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`) maps G1–C1 → BR-16 / readiness / deploy / launch / security; H31x next.

**Stage 31 exit (2026-08-11):** G1, R1, O1, C1, D1, H31x met — `docs/STAGE_31_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_068_STAGE31_FREEZE.md`. Fidelity: `docs/STAGE_31_FIDELITY.md`.

**Stage 32 open (2026-08-11):** Commercial MVP Handoff Fidelity track approved — `docs/ADR_069_STAGE32_OPEN.md` + `docs/STAGE_32_PLAN.md` (Acceptance archive → Operator handoff → Release notes → Post-MVP backlog → fidelity).

**Stage 32 A1 (2026-08-11):** MVP acceptance archive — `docs/ACCEPTANCE_ARCHIVE_MVP.md`, `ops/mvp/acceptance-archive.json`, evidence `stage32_a1_acceptance_archive.json` (`test_acceptance_archive_a1.py`); Stage 1–31 exit/freeze index; go-live / §7 Remaining.

**Stage 32 H1 (2026-08-11):** Operator handoff pack — `docs/OPERATOR_HANDOFF_MVP.md`, `ops/mvp/operator-handoff.json`, evidence `stage32_h1_operator_handoff.json` (`test_operator_handoff_h1.py`); ops take-over checklist; live handoff / §7 Remaining.

**Stage 32 N1 (2026-08-11):** Commercial release notes — `docs/RELEASE_NOTES_MVP.md`, `ops/mvp/release-notes.json`, evidence `stage32_n1_release_notes.json` (`test_release_notes_n1.py`); packaging Complete ≠ production live.

**Stage 32 B1 (2026-08-11):** Post-MVP backlog — `docs/POST_MVP_BACKLOG_MVP.md`, `ops/mvp/post-mvp-backlog.json`, evidence `stage32_b1_post_mvp_backlog.json` (`test_post_mvp_backlog_b1.py`); ADR-001–006 + operator Remaining indexed; deferred scopes Remaining.

**Stage 32 D1 (2026-08-11):** Commercial MVP handoff fidelity sync — `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`) maps A1–B1 → BR-16 / readiness / deploy / launch / security; H32x next.

**Stage 32 exit (2026-08-11):** A1, H1, N1, B1, D1, H32x met — `docs/STAGE_32_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_070_STAGE32_FREEZE.md`. Fidelity: `docs/STAGE_32_FIDELITY.md`.

**Stage 33 open (2026-08-11):** Commercial MVP Continuity Fidelity track approved — `docs/ADR_071_STAGE33_OPEN.md` + `docs/STAGE_33_PLAN.md` (Residual risk → Compliance readiness → First-tenant onboarding → Knowledge transfer → fidelity).

**Stage 33 K1 (2026-08-11):** Residual risk register — `docs/RESIDUAL_RISK_MVP.md`, `ops/mvp/residual-risk-register.json`, evidence `stage33_k1_residual_risk.json` (`test_residual_risk_k1.py`); risks remain open/accepted; go-live Remaining.

**Stage 33 C1 (2026-08-11):** Compliance readiness — `docs/COMPLIANCE_READINESS_MVP.md`, `ops/mvp/compliance-readiness-register.json`, evidence `stage33_c1_compliance_readiness.json` (`test_compliance_readiness_c1.py`); SOC 2 / ISO certification Remaining.

**Stage 33 F1 (2026-08-11):** First-tenant onboarding — `docs/FIRST_TENANT_ONBOARDING_MVP.md`, `ops/mvp/first-tenant-onboarding.json`, evidence `stage33_f1_first_tenant_onboarding.json` (`test_first_tenant_onboarding_f1.py`); live onboarding success Remaining.

**Stage 33 T1 (2026-08-11):** Knowledge transfer — `docs/KNOWLEDGE_TRANSFER_MVP.md`, `ops/mvp/knowledge-transfer.json`, evidence `stage33_t1_knowledge_transfer.json` (`test_knowledge_transfer_t1.py`); live training Remaining.

**Stage 33 D1 (2026-08-11):** Commercial MVP continuity fidelity sync — `docs/STAGE_33_FIDELITY.md` (`test_stage33_fidelity_d1.py`) maps K1–T1 → BR-16 / readiness / deploy / launch / security; H33x next.

**Stage 33 exit (2026-08-11):** K1, C1, F1, T1, D1, H33x met — `docs/STAGE_33_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_072_STAGE33_FREEZE.md`. Fidelity: `docs/STAGE_33_FIDELITY.md`.

**Stage 34 open (2026-08-11):** Commercial Customer Assurance Fidelity track approved — `docs/ADR_073_STAGE34_OPEN.md` + `docs/STAGE_34_PLAN.md` (Assurance evidence → Compliance questionnaire → Support SLA boundary → Billing-deferred honesty → fidelity).

**Stage 34 A1 (2026-08-11):** Assurance evidence — `docs/ASSURANCE_EVIDENCE_MVP.md`, `ops/mvp/assurance-evidence.json`, evidence `stage34_a1_assurance_evidence.json` (`test_assurance_evidence_a1.py`); live attestation / §7 Remaining.

**Stage 34 C1 (2026-08-11):** Compliance questionnaire — `docs/COMPLIANCE_QUESTIONNAIRE_MVP.md`, `ops/mvp/compliance-questionnaire.json`, evidence `stage34_c1_compliance_questionnaire.json` (`test_compliance_questionnaire_c1.py`); SOC 2 / ISO certification Remaining.

**Stage 34 D1 (2026-08-11):** Commercial customer assurance fidelity sync — `docs/STAGE_34_FIDELITY.md` (`test_stage34_fidelity_d1.py`) maps A1–C1 → BR-16 / readiness / deploy / launch / security; S1/B1 deferred.

**Stage 34 exit (2026-08-11):** A1, C1, D1, H34x met; S1/B1 deferred — `docs/STAGE_34_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_074_STAGE34_FREEZE.md`. Fidelity: `docs/STAGE_34_FIDELITY.md`.

**Stage 35 open (2026-08-11):** Commercial End-to-End Operational Smoke Fidelity track approved — `docs/ADR_075_STAGE35_OPEN.md` + `docs/STAGE_35_PLAN.md` (Org bootstrap → Users/RBAC → Purchase-to-stock → Sale-to-payment → Verify financials → Backup/restore → fidelity).

**Stage 35 T1 (2026-08-11):** Org bootstrap — `docs/E2E_ORG_BOOTSTRAP_MVP.md`, `ops/mvp/e2e-org-bootstrap.json`, evidence `stage35_t1_e2e_org_bootstrap.json` (`test_e2e_org_bootstrap_t1.py`); tenant → company → branch → store → warehouse; live bootstrap / demo tenants Remaining.

**Stage 35 U1 (2026-08-11):** Users + RBAC — `docs/E2E_USERS_RBAC_MVP.md`, `ops/mvp/e2e-users-rbac.json`, evidence `stage35_u1_e2e_users_rbac.json` (`test_e2e_users_rbac_u1.py`); roles + RBAC smoke packaging; live provisioning / ADR-005 store membership Remaining.

**Stage 35 P1 (2026-08-11):** Purchase-to-stock — `docs/E2E_PURCHASE_STOCK_MVP.md`, `ops/mvp/e2e-purchase-stock.json`, evidence `stage35_p1_e2e_purchase_stock.json` (`test_e2e_purchase_stock_p1.py`); supplier → products → PO → GRN → verify stock; live purchasing / PO Kanban Remaining.

**Stage 35 S1 (2026-08-11):** Sale-to-payment — `docs/E2E_SALE_PAYMENT_MVP.md`, `ops/mvp/e2e-sale-payment.json`, evidence `stage35_s1_e2e_sale_payment.json` (`test_e2e_sale_payment_s1.py`); customer → POS → payment → stock reduction; live POS / USB-serial Remaining.

**Stage 35 V1 (2026-08-11):** Verify financials — `docs/E2E_VERIFY_FINANCIALS_MVP.md`, `ops/mvp/e2e-verify-financials.json`, evidence `stage35_v1_e2e_verify_financials.json` (`test_e2e_verify_financials_v1.py`); tax → accounting → credit → reports → audit; live verification / tax e-file Remaining.

**Stage 35 R1 (2026-08-11):** Backup + restore — `docs/E2E_BACKUP_RESTORE_MVP.md`, `ops/mvp/e2e-backup-restore.json`, evidence `stage35_r1_e2e_backup_restore.json` (`test_e2e_backup_restore_r1.py`); logical backup → dry-run → apply → verify; live restore / PITR drill Remaining.

**Stage 35 D1 (2026-08-11):** E2E operational smoke fidelity — `docs/STAGE_35_FIDELITY.md` (`test_stage35_fidelity_d1.py`); maps T1–R1 → readiness / launch / deploy / security; live E2E smoke Remaining.

**Stage 35 exit (2026-08-11):** T1, U1, P1, S1, V1, R1, D1, H35x met — `docs/STAGE_35_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_076_STAGE35_FREEZE.md`. Fidelity: `docs/STAGE_35_FIDELITY.md`.

**Stage 36 open (2026-08-11):** Commercial Assurance Completion Fidelity track approved — `docs/ADR_077_STAGE36_OPEN.md` + `docs/STAGE_36_PLAN.md` (Support SLA boundary → Billing-deferred honesty → fidelity).

**Stage 36 S1 (2026-08-11):** Support SLA boundary — `docs/SUPPORT_SLA_BOUNDARY_MVP.md`, `ops/mvp/support-sla-boundary.json`, evidence `stage36_s1_support_sla_boundary.json` (`test_support_sla_boundary_s1.py`); live SLA / PagerDuty Remaining.

**Stage 36 B1 (2026-08-11):** Billing-deferred honesty — `docs/BILLING_DEFERRED_HONESTY_MVP.md`, `ops/mvp/billing-deferred-honesty.json`, evidence `stage36_b1_billing_deferred_honesty.json` (`test_billing_deferred_honesty_b1.py`); ADR-002 / plan_code metadata; paid billing Remaining.

**Stage 36 D1 (2026-08-11):** Commercial assurance completion fidelity — `docs/STAGE_36_FIDELITY.md` (`test_stage36_fidelity_d1.py`); maps S1–B1 → readiness / launch / deploy / security; live SLA / paid billing Remaining.

**Stage 36 exit (2026-08-11):** S1, B1, D1, H36x met — `docs/STAGE_36_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_078_STAGE36_FREEZE.md`. Fidelity: `docs/STAGE_36_FIDELITY.md`.

**Stage 37 open (2026-08-11):** Commercial Data Protection Fidelity track approved — `docs/ADR_079_STAGE37_OPEN.md` + `docs/STAGE_37_PLAN.md` (Data subject access/portability → Erasure/soft-delete honesty → fidelity).

**Stage 37 P1 (2026-08-11):** Data subject access / portability — `docs/DATA_PORTABILITY_MVP.md`, `ops/mvp/data-portability.json`, evidence `stage37_p1_data_portability.json` (`test_data_portability_p1.py`); GDPR / DSAR Remaining.

**Stage 37 E1 (2026-08-11):** Erasure / soft-delete honesty — `docs/ERASURE_HONESTY_MVP.md`, `ops/mvp/erasure-honesty.json`, evidence `stage37_e1_erasure_honesty.json` (`test_erasure_honesty_e1.py`); ADR-003; hard-delete Remaining.

**Stage 37 D1 (2026-08-11):** Commercial data protection fidelity — `docs/STAGE_37_FIDELITY.md` (`test_stage37_fidelity_d1.py`); maps P1–E1 → readiness / launch / deploy / security; GDPR / hard-delete Remaining.

**Stage 37 exit (2026-08-11):** P1, E1, D1, H37x met — `docs/STAGE_37_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_080_STAGE37_FREEZE.md`. Fidelity: `docs/STAGE_37_FIDELITY.md`.

**Stage 38 open (2026-08-11):** Commercial Security Disclosure Fidelity track approved — `docs/ADR_081_STAGE38_OPEN.md` + `docs/STAGE_38_PLAN.md` (Vulnerability disclosure → Breach notification / security contact → fidelity).

**Stage 38 V1 (2026-08-11):** Vulnerability disclosure — `docs/VULN_DISCLOSURE_MVP.md`, `ops/mvp/vuln-disclosure.json`, evidence `stage38_v1_vuln_disclosure.json` (`test_vuln_disclosure_v1.py`); live disclosure / bug-bounty Remaining.

**Stage 38 B1 (2026-08-11):** Breach notification / security contact — `docs/BREACH_NOTIFICATION_MVP.md`, `ops/mvp/breach-notification.json`, evidence `stage38_b1_breach_notification.json` (`test_breach_notification_b1.py`); live breach drill Remaining.

**Stage 38 D1 (2026-08-11):** Commercial security disclosure fidelity — `docs/STAGE_38_FIDELITY.md` (`test_stage38_fidelity_d1.py`); maps V1–B1 → readiness / launch / deploy / security; live disclosure / breach drill Remaining.

**Stage 38 exit (2026-08-11):** V1, B1, D1, H38x met — `docs/STAGE_38_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_082_STAGE38_FREEZE.md`. Fidelity: `docs/STAGE_38_FIDELITY.md`.

**Stage 39 open (2026-08-11):** Commercial Contract Evidence Fidelity track approved — `docs/ADR_083_STAGE39_OPEN.md` + `docs/STAGE_39_PLAN.md` (DPA/subprocessor → MSA security addendum → fidelity).

**Stage 39 P1 (2026-08-11):** DPA / subprocessor honesty — `docs/DPA_SUBPROCESSOR_MVP.md`, `ops/mvp/dpa-subprocessor.json`, evidence `stage39_p1_dpa_subprocessor.json` (`test_dpa_subprocessor_p1.py`); signed DPA Remaining.

**Stage 39 A1 (2026-08-11):** MSA security addendum honesty — `docs/MSA_ADDENDUM_MVP.md`, `ops/mvp/msa-addendum.json`, evidence `stage39_a1_msa_addendum.json` (`test_msa_addendum_a1.py`); signed MSA Remaining.

**Stage 39 D1 (2026-08-11):** Commercial contract evidence fidelity — `docs/STAGE_39_FIDELITY.md` (`test_stage39_fidelity_d1.py`); maps P1–A1 → readiness / launch / deploy / security; signed DPA/MSA Remaining.

**Stage 39 exit (2026-08-11):** P1, A1, D1, H39x met — `docs/STAGE_39_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_084_STAGE39_FREEZE.md`. Fidelity: `docs/STAGE_39_FIDELITY.md`.

**Stage 40 open (2026-08-11):** Commercial Availability & Supply-Chain Fidelity track approved — `docs/ADR_085_STAGE40_OPEN.md` + `docs/STAGE_40_PLAN.md` (status/uptime → SBOM/dependency disclosure → fidelity).

**Stage 40 U1 (2026-08-11):** Status page / uptime honesty — `docs/STATUS_UPTIME_MVP.md`, `ops/mvp/status-uptime.json`, evidence `stage40_u1_status_uptime.json` (`test_status_uptime_u1.py`); live status page / 99.9% SLA Remaining.

**Stage 40 S1 (2026-08-11):** SBOM / dependency disclosure honesty — `docs/SBOM_DISCLOSURE_MVP.md`, `ops/mvp/sbom-disclosure.json`, evidence `stage40_s1_sbom_disclosure.json` (`test_sbom_disclosure_s1.py`); live SBOM pipeline Remaining.

**Stage 40 D1 (2026-08-11):** Commercial availability & supply-chain fidelity — `docs/STAGE_40_FIDELITY.md` (`test_stage40_fidelity_d1.py`); maps U1–S1 → readiness / launch / deploy / security; live status page / SBOM pipeline Remaining.

**Stage 40 exit (2026-08-11):** U1, S1, D1, H40x met — `docs/STAGE_40_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_086_STAGE40_FREEZE.md`. Fidelity: `docs/STAGE_40_FIDELITY.md`.

**Stage 41 open (2026-08-11):** Commercial Accessibility & Change Governance Fidelity track approved — `docs/ADR_087_STAGE41_OPEN.md` + `docs/STAGE_41_PLAN.md` (accessibility statement → change/maintenance governance → fidelity).

**Stage 41 A1 (2026-08-11):** Accessibility statement honesty — `docs/ACCESSIBILITY_STATEMENT_MVP.md`, `ops/mvp/accessibility-statement.json`, evidence `stage41_a1_accessibility_statement.json` (`test_accessibility_statement_a1.py`); WCAG AA audit Remaining.

**Stage 41 C1 (2026-08-11):** Change / maintenance governance honesty — `docs/CHANGE_GOVERNANCE_MVP.md`, `ops/mvp/change-governance.json`, evidence `stage41_c1_change_governance.json` (`test_change_governance_c1.py`); public change calendar Remaining.

**Stage 41 D1 (2026-08-11):** Commercial accessibility & change governance fidelity — `docs/STAGE_41_FIDELITY.md` (`test_stage41_fidelity_d1.py`); maps A1–C1 → readiness / launch / deploy / security; WCAG AA audit / public change calendar Remaining.

**Stage 41 exit (2026-08-11):** A1, C1, D1, H41x met — `docs/STAGE_41_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_088_STAGE41_FREEZE.md`. Fidelity: `docs/STAGE_41_FIDELITY.md`.

**Stage 42 open (2026-08-11):** Commercial AI Transparency Fidelity track approved — `docs/ADR_089_STAGE42_OPEN.md` + `docs/STAGE_42_PLAN.md` (AI use disclosure → AI model/provider boundary → fidelity).

**Stage 42 A1 (2026-08-11):** AI use disclosure honesty — `docs/AI_USE_DISCLOSURE_MVP.md`, `ops/mvp/ai-use-disclosure.json`, evidence `stage42_a1_ai_use_disclosure.json` (`test_ai_use_disclosure_a1.py`); AI certification Remaining.

**Stage 42 P1 (2026-08-11):** AI model / provider boundary honesty — `docs/AI_PROVIDER_BOUNDARY_MVP.md`, `ops/mvp/ai-provider-boundary.json`, evidence `stage42_p1_ai_provider_boundary.json` (`test_ai_provider_boundary_p1.py`); external LLM Remaining.

**Stage 42 D1 (2026-08-11):** Commercial AI transparency fidelity — `docs/STAGE_42_FIDELITY.md` (`test_stage42_fidelity_d1.py`); maps A1–P1 → readiness / launch / deploy / security; external LLM / AI certification Remaining.

**Stage 42 exit (2026-08-11):** A1, P1, D1, H42x met — `docs/STAGE_42_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_090_STAGE42_FREEZE.md`. Fidelity: `docs/STAGE_42_FIDELITY.md`.

**Stage 43 open (2026-08-11):** Commercial Legal Notice Fidelity track approved — `docs/ADR_091_STAGE43_OPEN.md` + `docs/STAGE_43_PLAN.md` (ToS/AUP → cookie/privacy notice → fidelity).

**Stage 43 T1 (2026-08-11):** ToS / AUP honesty — `docs/TOS_AUP_MVP.md`, `ops/mvp/tos-aup.json`, evidence `stage43_t1_tos_aup.json` (`test_tos_aup_t1.py`); signed ToS Remaining.

**Stage 43 C1 (2026-08-11):** Cookie / privacy notice honesty — `docs/COOKIE_PRIVACY_NOTICE_MVP.md`, `ops/mvp/cookie-privacy-notice.json`, evidence `stage43_c1_cookie_privacy_notice.json` (`test_cookie_privacy_notice_c1.py`); live cookie-consent Remaining.

**Stage 43 D1 (2026-08-11):** Commercial legal notice fidelity — `docs/STAGE_43_FIDELITY.md` (`test_stage43_fidelity_d1.py`); maps T1–C1 → readiness / launch / deploy / security; signed ToS / live cookie-consent Remaining.

**Stage 43 exit (2026-08-11):** T1, C1, D1, H43x met — `docs/STAGE_43_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_092_STAGE43_FREEZE.md`. Fidelity: `docs/STAGE_43_FIDELITY.md`.

**Stage 44 open (2026-08-11):** Commercial Data Trust Fidelity track approved — `docs/ADR_093_STAGE44_OPEN.md` + `docs/STAGE_44_PLAN.md` (data residency → encryption/KMS → fidelity).

**Stage 44 R1 (2026-08-11):** Data residency / localization honesty — `docs/DATA_RESIDENCY_MVP.md`, `ops/mvp/data-residency.json`, evidence `stage44_r1_data_residency.json` (`test_data_residency_r1.py`); multi-region residency Remaining.

**Stage 44 E1 (2026-08-11):** Encryption / key-management honesty — `docs/ENCRYPTION_KMS_MVP.md`, `ops/mvp/encryption-kms.json`, evidence `stage44_e1_encryption_kms.json` (`test_encryption_kms_e1.py`); HSM / live Vault Remaining.

**Stage 44 D1 (2026-08-11):** Commercial data trust fidelity — `docs/STAGE_44_FIDELITY.md` (`test_stage44_fidelity_d1.py`); maps R1–E1 → readiness / launch / deploy / security; multi-region residency / HSM / Vault Remaining.

**Stage 44 exit (2026-08-11):** R1, E1, D1, H44x met — `docs/STAGE_44_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_094_STAGE44_FREEZE.md`. Fidelity: `docs/STAGE_44_FIDELITY.md`.

**Stage 45 open (2026-08-11):** Commercial Continuity & Exit Fidelity track approved — `docs/ADR_095_STAGE45_OPEN.md` + `docs/STAGE_45_PLAN.md` (RTO/RPO → retention/return → fidelity).

**Stage 45 O1 (2026-08-11):** RTO / RPO recovery objectives honesty — `docs/RTO_RPO_MVP.md`, `ops/mvp/rto-rpo.json`, evidence `stage45_o1_rto_rpo.json` (`test_rto_rpo_o1.py`); measured RTO/RPO Remaining.

**Stage 45 T1 (2026-08-11):** Data retention / return honesty — `docs/DATA_RETENTION_RETURN_MVP.md`, `ops/mvp/data-retention-return.json`, evidence `stage45_t1_data_retention_return.json` (`test_data_retention_return_t1.py`); data-return portal Remaining.

**Stage 45 D1 (2026-08-11):** Commercial continuity & exit fidelity — `docs/STAGE_45_FIDELITY.md` (`test_stage45_fidelity_d1.py`); maps O1–T1 → readiness / launch / deploy / security; measured RTO/RPO / data-return portal Remaining.

**Stage 45 exit (2026-08-11):** O1, T1, D1, H45x met — `docs/STAGE_45_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_096_STAGE45_FREEZE.md`. Fidelity: `docs/STAGE_45_FIDELITY.md`.

**Stage 46 open (2026-08-11):** Commercial Liability & Remedy Fidelity track approved — `docs/ADR_097_STAGE46_OPEN.md` + `docs/STAGE_46_PLAN.md` (liability/indemnity → service credit/warranty → fidelity).

**Stage 46 L1 (2026-08-11):** Limitation of liability / indemnity honesty — `docs/LIABILITY_INDEMNITY_MVP.md`, `ops/mvp/liability-indemnity.json`, evidence `stage46_l1_liability_indemnity.json` (`test_liability_indemnity_l1.py`); signed liability-cap Remaining.

**Stage 46 W1 (2026-08-11):** Service credit / warranty honesty — `docs/SERVICE_CREDIT_WARRANTY_MVP.md`, `ops/mvp/service-credit-warranty.json`, evidence `stage46_w1_service_credit_warranty.json` (`test_service_credit_warranty_w1.py`); live service credits Remaining.

**Stage 46 D1 (2026-08-11):** Commercial liability & remedy fidelity — `docs/STAGE_46_FIDELITY.md` (`test_stage46_fidelity_d1.py`); maps L1–W1 → readiness / launch / deploy / security; signed liability-cap / live service credits Remaining.

**Stage 46 exit (2026-08-11):** L1, W1, D1, H46x met — `docs/STAGE_46_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_098_STAGE46_FREEZE.md`. Fidelity: `docs/STAGE_46_FIDELITY.md`.

**Stage 47 open (2026-08-11):** Commercial Insurance & Audit Fidelity track approved — `docs/ADR_099_STAGE47_OPEN.md` + `docs/STAGE_47_PLAN.md` (cyber insurance/COI → customer audit rights → fidelity).

**Stage 47 I1 (2026-08-11):** Cyber insurance / COI honesty — `docs/CYBER_INSURANCE_MVP.md`, `ops/mvp/cyber-insurance.json`, evidence `stage47_i1_cyber_insurance.json` (`test_cyber_insurance_i1.py`); issued COI Remaining.

**Stage 47 A1 (2026-08-11):** Customer audit rights honesty — `docs/CUSTOMER_AUDIT_RIGHTS_MVP.md`, `ops/mvp/customer-audit-rights.json`, evidence `stage47_a1_customer_audit_rights.json` (`test_customer_audit_rights_a1.py`); customer audit executed Remaining.

**Stage 47 D1 (2026-08-11):** Commercial insurance & audit fidelity — `docs/STAGE_47_FIDELITY.md` (`test_stage47_fidelity_d1.py`); maps I1–A1 → readiness / launch / deploy / security; issued COI / customer audit executed Remaining.

**Stage 47 exit (2026-08-11):** I1, A1, D1, H47x met — `docs/STAGE_47_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_100_STAGE47_FREEZE.md`. Fidelity: `docs/STAGE_47_FIDELITY.md`.

**Stage 48 open (2026-08-11):** Commercial Services Fidelity track approved — `docs/ADR_101_STAGE48_OPEN.md` + `docs/STAGE_48_PLAN.md` (professional services/SOW → customer training/cert → fidelity).

**Stage 48 P1 (2026-08-11):** Professional services / SOW honesty — `docs/PROFESSIONAL_SERVICES_SOW_MVP.md`, `ops/mvp/professional-services-sow.json`, evidence `stage48_p1_professional_services_sow.json` (`test_professional_services_sow_p1.py`); signed SOW Remaining.

**Stage 48 T1 (2026-08-11):** Customer training / certification honesty — `docs/CUSTOMER_TRAINING_CERT_MVP.md`, `ops/mvp/customer-training-cert.json`, evidence `stage48_t1_customer_training_cert.json` (`test_customer_training_cert_t1.py`); live training Remaining.

**Stage 48 D1 (2026-08-11):** Commercial services fidelity — `docs/STAGE_48_FIDELITY.md` (`test_stage48_fidelity_d1.py`); maps P1–T1 → readiness / launch / deploy / security; signed SOW / live training Remaining.

**Stage 48 exit (2026-08-11):** P1, T1, D1, H48x met — `docs/STAGE_48_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_102_STAGE48_FREEZE.md`. Fidelity: `docs/STAGE_48_FIDELITY.md`.

**Stage 49 open (2026-08-11):** Commercial Channel & Pricing Fidelity track approved — `docs/ADR_103_STAGE49_OPEN.md` + `docs/STAGE_49_PLAN.md` (partner/reseller → pricing transparency → fidelity).

**Stage 49 R1 (2026-08-11):** Partner / reseller terms honesty — `docs/PARTNER_RESELLER_MVP.md`, `ops/mvp/partner-reseller.json`, evidence `stage49_r1_partner_reseller.json` (`test_partner_reseller_r1.py`); live partner program Remaining.

**Stage 49 L1 (2026-08-11):** Pricing transparency honesty — `docs/PRICING_TRANSPARENCY_MVP.md`, `ops/mvp/pricing-transparency.json`, evidence `stage49_l1_pricing_transparency.json` (`test_pricing_transparency_l1.py`); public pricing portal Remaining.

**Stage 49 D1 (2026-08-11):** Channel & pricing fidelity sync — `docs/STAGE_49_FIDELITY.md` (`test_stage49_fidelity_d1.py`); maps R1–L1 → readiness / launch / deploy / security.

**Stage 49 exit (2026-08-11):** R1, L1, D1, H49x met — `docs/STAGE_49_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_104_STAGE49_FREEZE.md`. Fidelity: `docs/STAGE_49_FIDELITY.md`.

**Stage 50 open (2026-08-11):** Commercial Acquisition & Trial Fidelity track approved — `docs/ADR_105_STAGE50_OPEN.md` + `docs/STAGE_50_PLAN.md` (referral → freemium trial → fidelity).

**Stage 50 R1 (2026-08-11):** Referral program honesty — `docs/REFERRAL_PROGRAM_MVP.md`, `ops/mvp/referral-program.json`, evidence `stage50_r1_referral_program.json` (`test_referral_program_r1.py`); live referral credits Remaining.

**Stage 50 F1 (2026-08-11):** Freemium trial honesty — `docs/FREEMIUM_TRIAL_MVP.md`, `ops/mvp/freemium-trial.json`, evidence `stage50_f1_freemium_trial.json` (`test_freemium_trial_f1.py`); live freemium conversion Remaining.

**Stage 50 D1 (2026-08-11):** Acquisition & trial fidelity sync — `docs/STAGE_50_FIDELITY.md` (`test_stage50_fidelity_d1.py`); maps R1–F1 → readiness / launch / deploy / security.

**Stage 50 exit (2026-08-11):** R1, F1, D1, H50x met — `docs/STAGE_50_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_106_STAGE50_FREEZE.md`. Fidelity: `docs/STAGE_50_FIDELITY.md`.

**Stage 51 open (2026-08-11):** Commercial Marketplace & Add-Ons Fidelity track approved — `docs/ADR_107_STAGE51_OPEN.md` + `docs/STAGE_51_PLAN.md` (marketplace → add-ons → fidelity).

**Stage 51 M1 (2026-08-11):** Marketplace presence honesty — `docs/MARKETPLACE_PRESENCE_MVP.md`, `ops/mvp/marketplace-presence.json`, evidence `stage51_m1_marketplace_presence.json` (`test_marketplace_presence_m1.py`); live marketplace listing Remaining.

**Stage 51 A1 (2026-08-11):** Add-on services honesty — `docs/ADDON_SERVICES_MVP.md`, `ops/mvp/addon-services.json`, evidence `stage51_a1_addon_services.json` (`test_addon_services_a1.py`); live add-on catalog Remaining.

**Stage 51 D1 (2026-08-11):** Marketplace & add-ons fidelity sync — `docs/STAGE_51_FIDELITY.md` (`test_stage51_fidelity_d1.py`); maps M1–A1 → readiness / launch / deploy / security.

**Stage 51 exit (2026-08-11):** M1, A1, D1, H51x met — `docs/STAGE_51_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_108_STAGE51_FREEZE.md`. Fidelity: `docs/STAGE_51_FIDELITY.md`.

**Stage 52 open (2026-08-11):** Commercial Partnerships & Renewal Fidelity track approved — `docs/ADR_109_STAGE52_OPEN.md` + `docs/STAGE_52_PLAN.md` (industry partnerships → renewal/discount → fidelity).

**Stage 52 I1 (2026-08-11):** Industry partnerships honesty — `docs/INDUSTRY_PARTNERSHIPS_MVP.md`, `ops/mvp/industry-partnerships.json`, evidence `stage52_i1_industry_partnerships.json` (`test_industry_partnerships_i1.py`); live industry partnership program Remaining.

**Stage 52 R1 (2026-08-11):** Subscription renewal / annual discount honesty — `docs/SUBSCRIPTION_RENEWAL_MVP.md`, `ops/mvp/subscription-renewal.json`, evidence `stage52_r1_subscription_renewal.json` (`test_subscription_renewal_r1.py`); live annual-discount enforcement Remaining.

**Stage 52 D1 (2026-08-11):** Partnerships & renewal fidelity sync — `docs/STAGE_52_FIDELITY.md` (`test_stage52_fidelity_d1.py`); maps I1–R1 → readiness / launch / deploy / security.




### 2.2 Features

| # | Feature | Module | Priority |
|---|---------|--------|----------|
| 1.1 | Company (Tenant) Registration | Multi-Tenant Management | P0 |
| 1.2 | Company Profile, Logo, Settings | Multi-Tenant Management | P0 |
| 1.3 | Industry Selection, Currency, Time Zone, Fiscal Year | Multi-Tenant Management | P0 |
| 1.4 | Tenant Status & Subscription Plan | Multi-Tenant Management | P0 |
| 1.5 | Data Isolation & Tenant Database Initialization | Multi-Tenant Management | P0 |
| 1.6 | Company Information, Branch, Store, Warehouse, Department Setup | System Administration | P0 |
| 1.7 | Currency Setup, Language, Tax Configuration | System Administration | P0 |
| 1.8 | User Accounts (Create, Edit, Delete, Activate/Deactivate) | User Management | P0 |
| 1.9 | Roles (Super Admin, Company Admin, Store Manager, etc.) | User Management | P0 |
| 1.10 | Module, Menu & Record Permissions | User Management | P0 |
| 1.11 | Executive Dashboard (Total Sales, Purchases, Expenses, Customers, Suppliers, Products, Low Stock, Recent Sales, Top Products, Daily/Monthly Revenue) | Dashboard | P0 |
| 1.12 | Notifications (Dashboard, Email, SMS framework) | Notifications | P1 |
| 1.13 | Login, Logout, Password Reset, Email Verification | Authentication & Security | P0 |
| 1.14 | JWT + OAuth2 Authentication | Authentication & Security | P0 |
| 1.15 | Session Management | Authentication & Security | P0 |
| 1.16 | Company Information, Currency, Date/Number Format, Email Settings, Invoice Numbering, Receipt Templates | System Settings | P1 |

### 2.3 Database Changes

- Create `public.tenants` table (global registry)
- Create tenant schema provisioning system
- Create per-tenant tables: `users`, `roles`, `permissions`, `branches`, `stores`, `warehouses`, `departments`, `notification_preferences`
- Create `public.subscription_plans` reference table
- Set up Alembic multi-tenant migration infrastructure

### 2.4 APIs Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login` | POST | User authentication |
| `/auth/refresh` | POST | Token refresh |
| `/auth/logout` | POST | Session termination |
| `/auth/password-reset-request` | POST | Initiate password reset |
| `/auth/password-reset` | POST | Complete password reset |
| `/tenants` | POST | Register new tenant |
| `/tenants/{id}` | GET/PATCH | Manage tenant profile |
| `/tenants/{id}/setup` | POST | Initial company setup |
| `/users` | CRUD | User management |
| `/roles` | GET | List roles |
| `/roles/{id}/permissions` | PUT | Update permissions |
| `/dashboard` | GET | Executive dashboard metrics |
| `/system-settings` | GET/PATCH | System configuration |

### 2.5 UI Requirements

- **Tenant Registration Flow:** Multi-step wizard (Company Info → Industry → Admin Account → Confirmation)
- **Login Screen:** Branded per tenant, email/password, "Remember me", "Forgot password"
- **Dashboard:** KPI cards, sparkline charts, recent activity feed, low-stock alerts widget
- **User Management:** Data table with search/filter, role assignment modal, permission matrix grid
- **Settings:** Tabbed interface (Company, Currency, Tax, Email, Templates)
- **Responsive:** Sidebar navigation collapses on mobile; dashboard cards stack vertically

### 2.6 Testing Requirements

| Test Type | Coverage Target | Key Scenarios |
|-----------|-----------------|---------------|
| **Unit Tests** | > 80% | Auth service, tenant service, permission resolver |
| **Integration Tests** | All new endpoints | Login flow, tenant provisioning, permission enforcement |
| **E2E Tests** | Critical paths | Registration → Login → Dashboard → Logout |
| **Security Tests** | All auth endpoints | Brute force protection, JWT expiry, session hijacking prevention |
| **Load Tests** | 100 concurrent logins | PgBouncer connection pooling under load |

### 2.7 Deliverables

- [ ] Deployable backend with multi-tenant middleware
- [ ] Frontend with authentication guards and role-based menu rendering
- [ ] Working tenant registration and onboarding wizard
- [ ] Executive dashboard with real-time KPIs (mock data acceptable)
- [ ] User management with all 7 roles and 3 permission layers
- [ ] CI/CD pipeline operational (GitHub Actions → Staging K8s)
- [ ] Database migration system (Alembic) tested across multiple tenant schemas
- [ ] API documentation (OpenAPI/Swagger) auto-generated

### 2.8 AI/Cursor Implementation Prompt

```
Implement Phase 1 of RIBDIGI ERP MVP:

BACKEND (FastAPI + SQLAlchemy 2.0 + PostgreSQL):
1. Create multi-tenant middleware that reads X-Tenant-ID header, validates against JWT claim, and sets PostgreSQL search_path dynamically.
2. Implement auth module with JWT access/refresh tokens (15 min / 7 days), bcrypt password hashing, and Redis session storage.
3. Build tenant registration endpoint that: validates domain, creates public.tenants record, provisions tenant schema, runs Alembic migrations, seeds default roles and admin user.
4. Create RBAC system: 7 roles with module/menu/record permission layers. Permission middleware must check every protected route.
5. Build dashboard aggregation service that queries tenant schema for summary metrics (sales total, purchase total, expense total, active products, low stock count, recent transactions).

FRONTEND (Next.js 14 + React):
1. Build login page with form validation (Zod), error handling, and loading states.
2. Create registration wizard: 4 steps with progress indicator, validation at each step.
3. Implement sidebar navigation that renders menus based on user's menu_permissions from API.
4. Build executive dashboard: KPI cards with icons, line chart for revenue trend, bar chart for top products, data table for recent sales.
5. Create user management page: table with pagination, role dropdown, activate/deactivate toggle, permission matrix modal.

DATABASE:
1. Define all Phase 1 tables in SQLAlchemy models with TenantMixin and TimestampMixin.
2. Create Alembic env.py that iterates all tenant schemas and applies migrations.
3. Add indexes on tenant_id, email, status for performance.

DEVOPS:
1. Docker Compose setup for local development (backend, frontend, postgres, redis).
2. GitHub Actions workflow: lint → test → build → deploy to staging.
3. Kubernetes manifests for backend, frontend, postgres, redis deployments.

Acceptance Criteria:
- A new tenant can register, receive confirmation email, log in, and see dashboard.
- Admin can create users, assign roles, and permissions are enforced (403 for unauthorized access).
- Dashboard loads in < 2 seconds with < 50 database queries.
- All tests pass (unit + integration + e2e).
```

---

## 3. Phase 2: Inventory & Supply Chain

**Duration:** 6 Weeks (3 Sprints)  
**Sprint Length:** 2 Weeks  
**Team Size:** 5 Engineers (2 Backend, 2 Frontend, 1 QA)

### 3.1 Objective

Build the complete inventory management and purchasing system. This includes product catalog management, stock tracking, warehouse operations, supplier management, and the full purchase order lifecycle. This is the operational heart of the ERP.

**Stage 2 delivery plan (frozen):** `docs/STAGE_2_PLAN.md` — exit `docs/STAGE_2_EXIT_CRITERIA.md` / ADR-010.

### 3.2 Features

| # | Feature | Module | Priority |
|---|---------|--------|----------|
| 2.1 | Product Categories, Brands, Units | Inventory | P0 |
| 2.2 | Product Master (Name, SKU, Barcode, Variants, Images) | Inventory | P0 |
| 2.3 | Stock In / Stock Out / Stock Adjustment | Inventory | P0 |
| 2.4 | Stock Transfer (Inter-warehouse) | Inventory | P0 |
| 2.5 | Opening Stock Entry | Inventory | P0 |
| 2.6 | Stock Count (Physical Inventory) | Inventory | P0 |
| 2.7 | Stock Movement History | Inventory | P0 |
| 2.8 | Multiple Warehouses & Warehouse Stock | Inventory | P0 |
| 2.9 | Low Stock Alerts (Minimum Stock, Reorder Level) | Inventory | P0 |
| 2.10 | Supplier Profile & Contact Details | Purchasing | P0 |
| 2.11 | Supplier Balance Tracking | Purchasing | P0 |
| 2.12 | Purchase Request | Purchasing | P0 |
| 2.13 | Purchase Order (PO) | Purchasing | P0 |
| 2.14 | Goods Received Note (GRN) | Purchasing | P0 |
| 2.15 | Purchase Invoice | Purchasing | P0 |
| 2.16 | Purchase Return | Purchasing | P1 |
| 2.17 | Barcode generation & scanning support | Inventory | P1 |

### 3.3 Database Changes

- Create tables: `categories`, `brands`, `units`, `products`, `product_variants`, `product_images`, `warehouses`, `stock_levels`, `stock_movements`, `stock_transfers`, `stock_counts`, `stock_count_items`
- Create tables: `suppliers`, `purchase_requests`, `purchase_request_items`, `purchase_orders`, `purchase_order_items`, `grns`, `grn_items`, `purchase_invoices`, `purchase_returns`
- Add triggers/functions for automatic stock level updates on movement
- Add indexes on SKU, barcode, product_id + warehouse_id combinations

### 3.4 APIs Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/inventory/categories` | CRUD | Product categories |
| `/inventory/brands` | CRUD | Brands |
| `/inventory/units` | CRUD | Units |
| `/products` | CRUD | Product management |
| `/products/{id}/variants` | CRUD | Variant management |
| `/products/{id}/stock-levels` | PATCH | Set min/reorder levels |
| `/inventory/stock-in` | POST | Receive stock |
| `/inventory/stock-out` | POST | Issue stock |
| `/inventory/stock-adjustments` | POST | Adjust stock |
| `/inventory/stock-transfers` | CRUD | Transfer stock |
| `/inventory/stock-counts` | CRUD | Physical counts |
| `/inventory/low-stock` | GET | Low stock alerts |
| `/inventory/movements` | GET | Movement history |
| `/suppliers` | CRUD | Supplier management |
| `/purchases/requests` | CRUD | Purchase requests |
| `/purchases/orders` | CRUD | Purchase orders |
| `/purchases/grn` | CRUD | GRN processing |
| `/purchases/invoices` | CRUD | Purchase invoices |
| `/purchases/returns` | CRUD | Purchase returns |

### 3.5 UI Requirements

- **Product Catalog:** Grid/list view with image thumbnails, quick search, filter by category/brand/status. Bulk import via CSV.
- **Product Detail:** Tabbed view (General, Variants, Stock Levels, Images, History). Variant table with inline editing.
- **Stock Operations:** Form with barcode scanner input, product search dropdown, quantity input, warehouse selection, reason notes.
- **Stock Transfer:** Source/destination warehouse selector, product list with quantities, status tracker (Pending → In Transit → Received).
- **Stock Count:** Scan or select products, expected vs actual quantity input, variance calculation, completion workflow.
- **Supplier Management:** Contact card layout, balance display, transaction history tab.
- **Purchase Order Workflow:** Status-driven UI (Draft → Sent → Partially Received → Received). PO → GRN → Invoice linking.
- **Low Stock Dashboard:** Alert banner on dashboard, dedicated page with reorder suggestions, one-click "Create PO" from alert.

### 3.6 Testing Requirements

| Test Type | Coverage Target | Key Scenarios |
|-----------|-----------------|---------------|
| **Unit Tests** | > 80% | Stock calculation logic, PO total computation, GRN reconciliation |
| **Integration Tests** | All inventory & purchasing endpoints | Stock in → level increase, PO → GRN → stock update, transfer between warehouses |
| **E2E Tests** | Full purchasing workflow | Create supplier → Create PO → Receive GRN → Verify stock levels → Create invoice → Check supplier balance |
| **Concurrency Tests** | Simultaneous stock operations | Two users adjusting same product stock simultaneously — no negative stock |
| **Data Integrity Tests** | All stock movements | Ensure stock_levels.quantity always equals SUM(stock_movements.quantity) |

### 3.7 Deliverables

- [ ] Complete product catalog with variants, images, barcodes
- [ ] Real-time stock tracking across multiple warehouses
- [ ] Full purchasing workflow: Request → PO → GRN → Invoice → Return
- [ ] Low stock alert system with configurable thresholds
- [ ] Stock movement audit trail (who, what, when, why)
- [ ] Physical stock count module with variance reporting
- [ ] Supplier balance tracking with aging report
- [ ] CSV bulk import for products and stock

### 3.8 AI/Cursor Implementation Prompt

```
Implement Phase 2 of RIBDIGI ERP MVP — Inventory & Supply Chain:

BACKEND (FastAPI + SQLAlchemy 2.0):
1. Build complete inventory module: categories (hierarchical), brands, units, products with variants, images (S3 upload), SKUs, barcodes.
2. Implement stock engine: stock_levels table is the source of truth. Every stock_in, stock_out, adjustment, transfer must create a stock_movements record AND update stock_levels atomically (use database transaction).
3. Stock transfer workflow: create transfer (pending) → deduct from source warehouse → mark in_transit → receive at destination → add to destination warehouse. Rejection/cancellation must reverse deductions.
4. Stock count: create count → record expected vs actual → on completion, auto-generate stock_adjustment for variances.
5. Low stock alerts: background Celery task runs every hour. Checks stock_levels where quantity <= minimum_stock. Creates notification records.
6. Purchasing module: suppliers with opening_balance and current_balance. Purchase request → approval → convert to PO. PO status flow: draft → sent → partially_received → received → cancelled. GRN links to PO and updates received_qty on PO items. Purchase invoice links to PO/GRN and updates supplier balance.
7. All monetary calculations use Decimal(15,4). No floating-point arithmetic.

FRONTEND (Next.js):
1. Product catalog page: grid view with images, filters (category, brand, status), search, pagination. "Add Product" modal with variant builder (dynamic rows).
2. Product detail: tabs for Info, Variants (table with price/cost/SKU), Stock (warehouse grid with quantities), Images (gallery with primary selector), History (timeline of movements).
3. Stock operations page: tabbed interface for Stock In / Stock Out / Adjustment. Barcode input field with camera support. Auto-populate product on scan.
4. Stock transfer page: wizard — select source warehouse → select destination → add products → confirm → track status.
5. Purchasing page: tabbed (Requests, Orders, GRN, Invoices, Returns). Kanban-style status board for POs. GRN form with PO auto-population.
6. Low stock alerts: red badge on inventory menu item. Alert page with "Create PO" action button per item.

DATABASE:
1. Add all Phase 2 tables. Use foreign keys with appropriate ON DELETE actions (CASCADE for variants/images, RESTRICT for stock movements).
2. Add composite indexes: (product_id, variant_id, warehouse_id) on stock_levels. (product_id, created_at) on stock_movements.
3. Create database function update_stock_level() triggered on stock_movement insert.

Acceptance Criteria:
- User can create a product with 3 variants, each with different SKUs and barcodes.
- Stock In of 100 units increases warehouse stock. Stock Out of 5 decreases it. Movement history shows both.
- Transfer of 20 units from Warehouse A to B: A decreases by 20, B increases by 20.
- PO for 50 units → GRN for 48 accepted + 2 rejected → PO status = partially_received → stock increases by 48.
- Low stock alert fires when product drops below minimum_stock threshold.
- All stock operations complete in < 500ms API response time.
```

---

## 4. Phase 3: Sales, POS & Financials

**Duration:** 6 Weeks (3 Sprints)  
**Sprint Length:** 2 Weeks  
**Team Size:** 5 Engineers (2 Backend, 2 Frontend, 1 QA)

### 4.1 Objective

Build the revenue-generating side of the platform: customer management, sales pipeline (quotation → order → invoice), Point of Sale (POS), expense tracking, basic accounting, tax management, and credit control. This phase makes the ERP commercially usable.

**Stage 3 delivery plan (frozen):** `docs/STAGE_3_PLAN.md` — exit `docs/STAGE_3_EXIT_CRITERIA.md` / ADR-012.

### 4.2 Features

| # | Feature | Module | Priority |
|---|---------|--------|----------|
| 3.1 | Customer Profile & Customer Groups | Sales | P0 |
| 3.2 | Customer Balance Tracking | Sales | P0 |
| 3.3 | Quotation → Sales Order → Invoice | Sales | P0 |
| 3.4 | Sales Return | Sales | P0 |
| 3.5 | POS with Barcode Scanner & Product Search | POS | P0 |
| 3.6 | POS Discounts & Multiple Payment Methods | POS | P0 |
| 3.7 | Receipt Printing & Cash Drawer | POS | P0 |
| 3.8 | POS Shift Opening & Closing | POS | P0 |
| 3.9 | Expense Categories & Expense Entry | Expense | P0 |
| 3.10 | Expense Approval & Attachments | Expense | P0 |
| 3.11 | Recurring Expenses | Expense | P1 |
| 3.12 | Chart of Accounts | Accounting | P0 |
| 3.13 | Journal Entries (Double Entry) | Accounting | P0 |
| 3.14 | Cash Accounts & Bank Accounts | Accounting | P0 |
| 3.15 | Accounts Receivable & Payable | Accounting | P0 |
| 3.16 | Profit & Loss, Cash Flow, Trial Balance | Accounting | P0 |
| 3.17 | Customer Credit Limit & Credit Sales | Credit | P0 |
| 3.18 | Outstanding Balance & Payment Collection | Credit | P0 |
| 3.19 | Supplier Outstanding Bills & Payment Schedule | Credit | P0 |
| 3.20 | VAT/Tax Rates & Automatic Tax Calculation | Tax | P0 |
| 3.21 | Tax Reports | Tax | P1 |

### 4.3 Database Changes

- Create tables: `customers`, `customer_groups`, `quotations`, `quotation_items`, `sales_orders`, `sales_order_items`, `invoices`, `invoice_items`, `sales_returns`, `sales_return_items`
- Create tables: `pos_sessions`, `pos_sales`, `pos_sale_items`, `pos_payments`
- Create tables: `expense_categories`, `expenses`, `recurring_expenses`
- Create tables: `accounts`, `journal_entries`, `journal_entry_lines`
- Create tables: `customer_payments`, `payment_allocations`, `supplier_payments`
- Create table: `tax_rates`
- Add generated column `is_balanced` on journal_entries
- Add indexes on customer_id, invoice_date, due_date, status

### 4.4 APIs Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/customers` | CRUD | Customer management |
| `/customers/groups` | CRUD | Customer groups |
| `/customers/{id}/credit` | GET | Credit info |
| `/customers/{id}/payments` | POST | Record payment |
| `/sales/quotations` | CRUD | Quotations |
| `/sales/quotations/{id}/convert-to-order` | POST | Convert quote |
| `/sales/orders` | CRUD | Sales orders |
| `/sales/orders/{id}/convert-to-invoice` | POST | Convert order |
| `/sales/invoices` | CRUD | Invoices |
| `/sales/invoices/{id}/payments` | POST | Pay invoice |
| `/sales/returns` | CRUD | Sales returns |
| `/pos/sessions/open` | POST | Open shift |
| `/pos/sessions/{id}/close` | POST | Close shift |
| `/pos/sales` | POST | Create sale |
| `/pos/products/search` | GET | Product search |
| `/pos/sales/{id}/receipt` | GET | Print receipt |
| `/expenses/categories` | CRUD | Expense categories |
| `/expenses` | CRUD | Expenses |
| `/expenses/{id}/approve` | POST | Approve expense |
| `/expenses/recurring` | CRUD | Recurring expenses |
| `/accounting/accounts` | CRUD | Chart of accounts |
| `/accounting/journal-entries` | CRUD | Journal entries |
| `/accounting/accounts/{id}/transactions` | GET | Account transactions |
| `/reports/profit-loss` | GET | P&L report |
| `/reports/cash-flow` | GET | Cash flow |
| `/reports/trial-balance` | GET | Trial balance |
| `/taxes/rates` | CRUD | Tax rates |
| `/reports/tax` | GET | Tax reports |

### 4.5 UI Requirements

- **Customer Management:** List with balance column (color-coded: green = credit available, red = overdue). Detail page with transaction history, credit limit bar.
- **Sales Pipeline:** Kanban board (Quotation → Order → Invoice). Drag-and-drop status changes. One-click convert actions.
- **Invoice Builder:** Line item table with product search, auto-tax calculation, discount row, total summary. "Print" and "Email" buttons.
- **POS Screen:** Full-screen touch-optimized interface. Product grid with images, cart sidebar, numeric keypad, discount popup, payment method split (cash + card), receipt preview.
- **Shift Management:** Modal for opening count (denominations), closing count with variance calculation, cash drawer status.
- **Expense Entry:** Quick-add form (category, amount, date, attachment upload). Approval queue for managers.
- **Accounting:** Tree-view chart of accounts. Journal entry form with dynamic debit/credit rows (must balance). Financial report pages with date range picker.
- **Credit Dashboard:** Outstanding invoices table with aging buckets (0-30, 31-60, 61-90, 90+ days). Payment collection modal with allocation to multiple invoices.

### 4.6 Testing Requirements

| Test Type | Coverage Target | Key Scenarios |
|-----------|-----------------|---------------|
| **Unit Tests** | > 80% | Invoice total calculation, journal entry balancing, tax computation, credit limit enforcement |
| **Integration Tests** | All sales/accounting endpoints | Quote → Order → Invoice → Payment → Journal entry auto-creation |
| **E2E Tests** | POS full flow | Open shift → Scan 3 products → Apply discount → Split payment → Close shift → Verify cash difference |
| **Financial Integrity Tests** | All accounting transactions | Total debits always equal total credits. Account balances derived from journal lines. |
| **Credit Limit Tests** | Sales endpoints | Attempt invoice exceeding credit limit → 403 error. Payment reducing balance → new sales allowed. |

### 4.7 Deliverables

- [ ] Complete sales pipeline: Quotation → Order → Invoice → Payment → Return
- [x] Fully functional POS with barcode support, discounts, split payments, receipts (Stage 12 C2 / Stage 13 H1–H2; USB/serial drivers deferred)
- [x] Shift management with cash reconciliation (Stage 12 C2 / A1)
- [ ] Expense tracking with approval workflow and receipt attachments
- [ ] Double-entry accounting with Chart of Accounts, Journal Entries, AR/AP
- [ ] Financial reports: P&L, Cash Flow, Trial Balance
- [ ] Tax engine with automatic calculation on invoices and POs
- [ ] Customer & supplier credit management with aging reports
- [ ] Recurring expense automation (Celery beat)

### 4.8 AI/Cursor Implementation Prompt

```
Implement Phase 3 of RIBDIGI ERP MVP — Sales, POS & Financials:

BACKEND (FastAPI):
1. Sales pipeline: quotation (draft/sent/accepted/expired/converted) → sales_order (draft/confirmed/processing/shipped/delivered/cancelled) → invoice (unpaid/partial/paid/overdue/cancelled). Each conversion copies line items and links parent record.
2. Invoice auto-generates journal entry: Debit AR, Credit Sales Income, Credit Tax Payable. On payment: Debit Cash/Bank, Credit AR.
3. POS module: pos_sessions (shift) with opening_cash. pos_sales linked to session. Multiple pos_payments per sale (cash + card). On sale completion, auto-deduct stock and create invoice (optional). Receipt generated as PDF and stored in S3.
4. Shift close: calculate closing_cash vs actual_cash → cash_difference. Lock session from new sales after close.
5. Expense module: expense entry with attachment upload to S3. Approval workflow: pending → approved → paid. Recurring expenses: Celery beat task creates expense records on schedule (daily/weekly/monthly/quarterly/yearly).
6. Accounting: chart of accounts with 5 types (asset, liability, equity, income, expense). Hierarchical with parent_id. Journal entries must balance (total_debit = total_credit). Auto-post journal entries from invoices, payments, expenses.
7. Tax: tax_rates table with type (vat/gst/sales_tax/custom). Auto-calculate tax on invoice/PO line items based on tax_rate. Tax report aggregates by period.
8. Credit: customer credit_limit enforcement at invoice creation. Outstanding balance = SUM(invoice.total) - SUM(payment.amount). Payment allocation distributes payment across oldest invoices first (FIFO).

FRONTEND (Next.js):
1. Sales pipeline kanban: 5 columns for quotations, drag cards between statuses. Convert button triggers API and moves card to next column.
2. Invoice builder: autocomplete product search, dynamic line rows, live tax/discount/total calculation. Print button opens PDF in new tab.
3. POS screen: fullscreen layout. Left = product grid with search. Right = cart with quantity +/-, discount, total. Bottom = payment buttons (Cash, Card, Mobile). Receipt modal after payment.
4. Shift modal: opening count (enter bill denominations). Closing count with calculator-style input. Variance display (red if negative, green if positive).
5. Accounting: tree table for chart of accounts (expand/collapse). Journal entry form with add-row button, real-time balance check (red if unbalanced). Report pages with date picker and export to PDF.
6. Credit dashboard: aging table with color-coded rows. Payment modal: enter amount, auto-allocate to invoices, manual override allowed.

DATABASE:
1. Add all Phase 3 tables. Ensure journal_entry_lines has CHECK (debit > 0 OR credit > 0).
2. Add generated column is_balanced on journal_entries.
3. Indexes: (customer_id, status) on invoices, (account_id, created_at) on journal_entry_lines.

Acceptance Criteria:
- Create quotation with 3 items → convert to order → convert to invoice → record payment → customer balance = 0.
- POS sale of 2 products with 10% discount and split payment (cash 50%, card 50%) generates correct receipt.
- Shift opens with $200, sales total $500, closing count $695 → cash_difference = -$5.
- Journal entry with $100 debit and $99 credit is rejected (unbalanced).
- Customer with $500 credit limit cannot have invoice totaling $501.
- Tax of 10% on $100 item = $10 tax, $110 total.
```

---

## 5. Phase 4: Intelligence, Multi-Store & Scale

**Duration:** 6 Weeks (3 Sprints)  
**Sprint Length:** 2 Weeks  
**Team Size:** 5 Engineers (2 Backend, 1 Frontend, 1 AI/ML, 1 QA)

### 5.1 Objective

Add advanced capabilities that differentiate RIBDIGI from basic ERPs: AI-driven business insights, multi-store management for retail chains, comprehensive reporting, and proactive notifications. This phase transforms the ERP from a record-keeping tool into an intelligent business advisor.

**Stage 4 delivery plan (frozen):** `docs/STAGE_4_PLAN.md` — exit `docs/STAGE_4_EXIT_CRITERIA.md` / ADR-014.

### 5.2 Features

| # | Feature | Module | Priority |
|---|---------|--------|----------|
| 4.1 | Store Creation & Store Manager Assignment | Multi-Store | P0 |
| 4.2 | Store Inventory & Store Sales | Multi-Store | P0 |
| 4.3 | Inter-Store Transfers | Multi-Store | P0 |
| 4.4 | Sales Reports (Daily, Monthly, Product) | Reports | P0 |
| 4.5 | Inventory Reports (Stock Balance, Low Stock, Movement) | Reports | P0 |
| 4.6 | Purchase Reports (Summary, Supplier) | Reports | P0 |
| 4.7 | Expense Reports (Summary) | Reports | P0 |
| 4.8 | Financial Reports (P&L, Cash Flow) | Reports | P0 |
| 4.9 | Low Stock Notifications | Notifications | P0 |
| 4.10 | New Order / Purchase Received / Payment Due Notifications | Notifications | P0 |
| 4.11 | Credit Limit Reached Notifications | Notifications | P0 |
| 4.12 | Dashboard, Email, SMS Delivery | Notifications | P1 |
| 4.13 | AI ERP Chat Assistant | AI | P1 |
| 4.14 | AI Dashboard Insights | AI | P1 |
| 4.15 | Smart Inventory Intelligence | AI | P1 |
| 4.16 | AI Low Stock Prediction | AI | P1 |
| 4.17 | AI Sales Analysis | AI | P1 |
| 4.18 | AI Expense Analysis | AI | P1 |
| 4.19 | AI Report Generator | AI | P1 |
| 4.20 | AI Document Assistant (OCR) | AI | P2 |
| 4.21 | AI Customer Assistant | AI | P2 |
| 4.22 | AI Security Monitor | AI | P2 |

### 5.3 Database Changes

- Create tables: `stores`, `store_inventory`, `store_transfers`, `store_transfer_items`
- Create tables: `notifications`, `notification_preferences`
- Create AI feature tables: `ai_queries`, `ai_insights`, `ai_documents` (for tracking AI interactions)
- Add materialized views for report aggregation (daily_sales, monthly_sales, stock_balance_summary)
- Add indexes on store_id, notification_type, created_at for performance

### 5.4 APIs Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/stores` | CRUD | Store management |
| `/stores/{id}/inventory` | GET | Store inventory |
| `/stores/{id}/sales` | GET | Store sales |
| `/stores/transfers` | CRUD | Inter-store transfers |
| `/reports/sales/daily` | GET | Daily sales report |
| `/reports/sales/monthly` | GET | Monthly sales report |
| `/reports/sales/products` | GET | Product sales report |
| `/reports/inventory/balance` | GET | Stock balance report |
| `/reports/inventory/valuation` | GET | Stock valuation (Stage 9 R2 — standard cost) |
| `/reports/inventory/movements` | GET | Stock movement report |
| `/reports/purchases/summary` | GET | Purchase summary |
| `/reports/purchases/suppliers` | GET | Supplier purchase report |
| `/reports/purchases/pending-orders` | GET | Pending POs (Stage 9 R1) |
| `/reports/purchases/returns` | GET | Purchase return summary (Stage 9 R1) |
| `/reports/expenses/summary` | GET | Expense summary |
| `/notifications` | GET | List notifications |
| `/notifications/{id}/read` | PATCH | Mark read |
| `/notifications/settings` | GET/PATCH | Notification preferences |
| `/ai/chat` | POST | AI chat assistant (Stage 20 C1) |
| `/ai/chat/history` | GET | Chat history |
| `/ai/insights` | GET | Dashboard insights (Stage 20 I1) |
| `/ai/inventory/predictions` | GET | Inventory predictions |
| `/ai/inventory/demand-forecast` | GET | Demand 7/30/90 + reorder (Stage 20 V1) |
| `/ai/inventory/dead-stock` | GET | Dead stock (Stage 20 V1) |
| `/ai/inventory/low-stock-prediction` | GET | Low stock prediction (Stage 20 L1) |
| `/ai/sales/analysis` | GET | Sales analysis (Stage 20 S1) |
| `/ai/expenses/analysis` | GET | Expense analysis (BR-21.6 / Stage 10) |
| `/ai/reports/generate` | POST | AI report generation (+ `?export=true`) (Stage 20 R1) |
| `/ai/reports/templates` | GET/POST | Saved NL report templates (Stage 20 R1) |
| `/ai/documents/analyze` | POST | Document OCR analysis (BR-21.8 / Stage 10) |
| `/ai/customer/assist` | POST | Customer AI assistant (Stage 20 U1) |
| `/ai/customers/insights` | GET | Churn / best / promos (Stage 20 U1) |
| `/ai/security/alerts` | GET | AI security alerts (Stage 20 U1) |

Stage 20 D1 fidelity: `docs/STAGE_20_FIDELITY.md`.

### 5.5 UI Requirements

- **Multi-Store Dashboard:** Store selector dropdown (global context switch). Per-store inventory and sales views. Transfer request form with source/destination store pickers.
- **Reports Center:** Sidebar with report categories. Date range picker with presets (Today, This Week, This Month, Last Month, Custom). Tables with sortable columns, export to PDF/Excel. Charts (line for trends, pie for breakdowns).
- **Notification Center:** Bell icon with unread badge. Dropdown panel with notification list, mark-all-read. Settings page with per-type channel toggles (Dashboard/Email/SMS).
- **AI Chat Assistant:** Floating chat widget (bottom-right) or dedicated page. Natural language input, suggested prompts, response with data cards and "View Details" links. Conversation history.
- **AI Insights Cards:** Dashboard widgets with AI-generated summaries ("Sales are up 15% vs last month", "Top 3 products at risk of stockout"). Sparkline charts with trend arrows.
- **AI Report Generator:** Form with natural language query ("Show me monthly sales for Store A in Q2"), format selector (PDF/Excel), generate button with loading state.
- **Document Assistant:** Upload zone (drag & drop) for invoices/receipts. OCR results with editable extracted fields. Save to expense/invoice workflow.

### 5.6 Testing Requirements

| Test Type | Coverage Target | Key Scenarios |
|-----------|-----------------|---------------|
| **Unit Tests** | > 70% | AI prediction models, report aggregation queries, notification dispatch |
| **Integration Tests** | All report & AI endpoints | Report generation with date filters, AI chat with context, document upload → OCR → data extraction |
| **E2E Tests** | Multi-store flow | Create Store A and B → Transfer stock from A to B → Verify both store inventories |
| **AI Accuracy Tests** | Model predictions | Low stock prediction accuracy > 75% on historical data. Sales forecast MAPE < 20%. |
| **Performance Tests** | Report generation | Monthly sales report for 10K invoices completes in < 3 seconds. |
| **Notification Tests** | All trigger events | Low stock event → notification created within 5 seconds. Email dispatched via Celery. |

### 5.7 Deliverables

- [ ] Multi-store management with inter-store transfers
- [ ] Comprehensive report suite (Sales, Inventory, Purchase, Expense, Financial)
- [ ] Real-time notification system (Dashboard, Email, SMS)
- [ ] AI Chat Assistant integrated with all modules
- [ ] AI Dashboard Insights with natural language summaries
- [ ] AI Inventory Predictions (demand forecasting, stockout prediction)
- [ ] AI Sales & Expense Analysis (trend detection, anomaly detection)
- [ ] AI Report Generator (natural language to structured report)
- [ ] AI Document Assistant (OCR for invoices and receipts)
- [ ] AI Security Monitor (anomaly detection on login/access patterns)
- [ ] Materialized views for fast report loading
- [ ] Global store context switcher in UI header

### 5.8 AI/Cursor Implementation Prompt

```
Implement Phase 4 of RIBDIGI ERP MVP — Intelligence, Multi-Store & Scale:

BACKEND (FastAPI + AI Stack):
1. Multi-store: stores table linked to warehouses and managers. store_inventory mirrors stock_levels but per store. Inter-store transfer workflow similar to warehouse transfers but with store-specific UI.
2. Reports: Build aggregation service using SQLAlchemy core (not ORM) for performance. Materialized views refreshed every hour via Celery beat. Reports: daily_sales (group by date), monthly_sales (group by month), product_sales (group by product), stock_balance (current snapshot), purchase_summary (group by supplier/month), expense_summary (group by category/month).
3. Notifications: Event-driven architecture. On stock.low event → create notification record. Notification dispatcher Celery task checks preferences and sends via dashboard (real-time via WebSocket), email (SMTP), or SMS (Twilio).
4. AI Chat Assistant: FastAPI endpoint /ai/chat. Uses RAG pattern: user query → embedding → retrieve relevant tenant data (top products, recent sales, stock levels) → construct prompt with context → LLM response. Context strictly scoped to tenant data user has permission to access.
5. AI Insights: Nightly Celery job runs Pandas analysis on tenant data. Generates insight records: "Top selling product", "Stockout risk items", "Expense trend up/down". Stored in cache (Redis) for fast dashboard loading.
6. AI Predictions: Use Prophet for time-series forecasting. Input: daily sales history per product. Output: 30-day demand forecast. Use Scikit-learn IsolationForest for anomaly detection in expenses and sales.
7. AI Report Generator: Natural language query parsed to identify intent (sales_report, inventory_report), filters (date_range, store_id), and format (pdf, excel). Execute SQL query → format with Jinja2 template → generate PDF (WeasyPrint) or Excel (OpenPyXL).
8. AI Document Assistant: Upload file → OCR (Tesseract/EasyOCR) → extract text → NLP parsing (regex + heuristics) → structured data (vendor, amount, date, items) → pre-fill expense/invoice form.
9. AI Security Monitor: Analyze audit_logs for anomaly patterns (login from new IP, unusual hour, rapid failed attempts). Risk score per event. Alert if score > threshold.

FRONTEND (Next.js):
1. Store switcher: dropdown in header navbar. Switching updates global context and refreshes all data.
2. Reports page: sidebar navigation, date range picker, data table with sorting, chart visualization (Recharts), export buttons.
3. AI Chat: floating widget with message history, suggested questions, typing indicator. Responses render data tables and action buttons inline.
4. AI Insights: dashboard cards with auto-refresh every 6 hours. Trend arrows (up/down/neutral) with percentage change.
5. Document upload: drag-and-drop zone with preview. OCR results displayed in editable form fields. "Save as Expense" or "Save as Invoice" buttons.

DATABASE:
1. Add store-related tables. Add notification tables. Add ai_queries log table for auditing AI interactions.
2. Create materialized views for reports with concurrent refresh support.
3. Indexes: (store_id, product_id) on store_inventory, (user_id, is_read) on notifications.

Acceptance Criteria:
- Store A can transfer 50 units of Product X to Store B. Both store inventories update correctly.
- Monthly sales report for last 3 months renders in < 3 seconds with chart.
- AI chat answers "What are my top 3 products?" by querying actual sales data and returning formatted list.
- AI predicts stockout for Product Y in 12 days based on current velocity.
- Document upload of receipt.jpg extracts total amount, vendor name, and date with > 80% accuracy.
- Notification received within 5 seconds of low stock event trigger.
```

---

## 6. Phase 5: Polish, Security & Launch

**Duration:** 4–6 Weeks (2–3 Sprints)  
**Sprint Length:** 2 Weeks  
**Team Size:** 6 Engineers (2 Backend, 2 Frontend, 1 DevOps, 1 QA/Security)

### 6.1 Objective

Harden the platform for production readiness: implement backup/recovery, audit logs, API expansion, advanced security features, performance optimization, and final QA. This phase ensures the MVP is secure, reliable, and scalable enough for real tenant onboarding.

**Stage 5 delivery plan (closed):** `docs/STAGE_5_PLAN.md` — exit met; freeze ADR-016.

**Stage 6 delivery plan (closed):** `docs/STAGE_6_PLAN.md` — exit met; freeze ADR-018.

**Active delivery plan:** Stage 39 exit met (`docs/STAGE_39_EXIT_CRITERIA.md`, ADR-084). Stages 1–39 remain frozen for their scopes; Stage 40+ requires explicit open ADR after CONTINUE/NEXT.

### 6.2 Features

| # | Feature | Module | Priority |
|---|---------|--------|----------|
| 5.1 | Manual Backup & Scheduled Backup | Backup & Recovery | P0 |
| 5.2 | Database Restore | Backup & Recovery | P0 |
| 5.3 | Audit Logs (Login, Logout, Product Changes, Sales, Purchases, User Activity) | Audit Logs | P0 |
| 5.4 | Authentication API | API | P0 |
| 5.5 | Products API | API | P0 |
| 5.6 | Customers API | API | P0 |
| 5.7 | Sales API | API | P0 |
| 5.8 | Purchases API | API | P0 |
| 5.9 | Two-Factor Authentication (Optional) | Authentication & Security | P1 |
| 5.10 | Email Verification | Authentication & Security | P0 |
| 5.11 | Password Reset | Authentication & Security | P0 |
| 5.12 | Session Management | Authentication & Security | P0 |
| 5.13 | Performance Optimization (Caching, Query Tuning) | System | P0 |
| 5.14 | Load Testing & Scaling Validation | System | P0 |
| 5.15 | Security Audit & Penetration Testing | Security | P0 |
| 5.16 | Documentation Completion (API Docs, User Manual, Admin Manual) | Documentation | P1 |
| 5.17 | Onboarding Flow Optimization | System | P1 |
| 5.18 | Production Deployment & Monitoring | DevOps | P0 |

### 6.3 Database Changes

- Create `audit_logs` table (if not created in Phase 1)
- Add audit trigger functions for tracking changes on critical tables (products, sales, purchases, users)
- Optimize indexes based on query performance analysis (EXPLAIN ANALYZE)
- Add connection pooling configuration (PgBouncer)
- Set up WAL archiving for point-in-time recovery
- Create backup metadata tables

### 6.4 APIs Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/2fa/enable` | POST | Enable 2FA |
| `/auth/2fa/verify` | POST | Verify 2FA code |
| `/auth/sessions` | GET | List active sessions |
| `/auth/sessions/{id}` | DELETE | Revoke session |
| `/api/v1/products` | GET | Public products API (paginated) |
| `/api/v1/customers` | GET | Public customers API |
| `/api/v1/sales` | GET | Public sales API |
| `/api/v1/purchases` | GET | Public purchases API |
| `/webhooks` | CRUD | Webhook management |
| `/backup/manual` | POST | Trigger manual backup |
| `/backup/restore` | POST | Restore from backup |
| `/audit-logs` | GET | Query audit logs |

### 6.5 UI Requirements

- **Backup Management:** Admin page showing backup history (date, size, status). "Backup Now" button, "Restore" button with confirmation modal (destructive action warning). Scheduled backup configuration (frequency, retention).
- **Audit Log Viewer:** Filterable table (date range, user, event type, resource type). Diff view showing old vs new values for update events. Export to CSV.
- **Security Settings:** 2FA setup wizard (QR code display, verification code input). Active sessions list with "Revoke" buttons per device. Password policy configuration.
- **API Keys:** Generate/revoke API keys for third-party integrations. Usage statistics (requests, last used) — **COMPLETE (Stage 7 K2).**
- **Performance Dashboard:** Admin-only page showing query slow log, cache hit rates, average response times, error rates.
- **Onboarding Checklist:** New tenant sees progress checklist (Setup company → Add products → Create supplier → Make first sale) with skip/complete actions. **COMPLETE (Stage 6 N2):** `GET /onboarding/checklist` + Shell banner; dismissible at ≥80%.

### 6.6 Testing Requirements

| Test Type | Coverage Target | Key Scenarios |
|-----------|-----------------|---------------|
| **Unit Tests** | > 85% | All new code in Phase 5 |
| **Integration Tests** | All endpoints | Backup/restore, audit log creation, API key auth, webhook delivery |
| **E2E Tests** | Full user journeys | Registration → Onboarding → First sale → Report → Backup → Logout |
| **Security Tests** | Full OWASP Top 10 | SQL injection, XSS, CSRF, broken auth, sensitive data exposure, security misconfiguration |
| **Load Tests** | 1000 concurrent users | Login, dashboard, product search, invoice creation under load |
| **Penetration Test** | External vendor | Third-party security assessment |
| **Disaster Recovery Drill** | Full system | Backup → simulate data loss → restore → verify integrity |

### 6.7 Deliverables

- [ ] Automated backup system (daily full + continuous WAL)
- [ ] Point-in-time database restore capability
- [ ] Immutable audit log for all sensitive operations
- [ ] Complete REST API for external integrations (Products, Customers, Sales, Purchases)
- [ ] Webhook system with signature verification
- [ ] Two-factor authentication (TOTP)
- [ ] Email verification and password reset flows
- [ ] Session management with revoke capability
- [ ] Performance optimized: p95 API response < 200ms, dashboard load < 2s
- [ ] Load tested: 1000 concurrent users, 100 transactions/second
- [ ] Security hardened: TLS 1.3, WAF rules, rate limiting, input validation, RBAC enforced
- [ ] Production Kubernetes deployment with monitoring (Prometheus/Grafana)
- [ ] Complete documentation set: API docs, User Manual, Admin Manual, Security Guide
- [x] Launch checklist documented (Stage 7 L7x — `docs/LAUNCH_CHECKLIST.md`); operator environment sign-off remains ops

### 6.8 AI/Cursor Implementation Prompt

```
Implement Phase 5 of RIBDIGI ERP MVP — Polish, Security & Launch:

BACKEND (FastAPI + DevOps):
1. Backup system: pg_basebackup for full backups daily at 2 AM. WAL archiving continuous to S3. Backup metadata stored in PostgreSQL. Restore endpoint validates backup integrity (checksum) before restoring. Tenant-level restore isolates to single schema.
2. Audit logs: Middleware intercepts all POST/PUT/PATCH/DELETE requests. Captures: user_id, session_id, IP, user_agent, event_type, resource_type, resource_id, action, old_values (JSONB), new_values (JSONB). Stored in append-only audit_logs table. 7-year retention for financial events.
3. API expansion: Public API endpoints under /api/v1/ with API key authentication (separate from JWT). Rate limiting per API key. Webhook system: tenants register URLs, events trigger POST with HMAC-SHA256 signature. Retry logic with exponential backoff.
4. 2FA: TOTP-based using pyotp. QR code generation for setup. Backup codes (10 single-use). Enforced per role (optional for cashier, mandatory for admin).
5. Email verification: SendGrid/AWS SES integration. Verification token expires in 24 hours. Unverified users blocked from protected routes.
6. Performance: Redis caching for dashboard metrics (5 min TTL), product catalog (10 min TTL), user permissions (1 hour TTL). SQL query optimization: add missing indexes, refactor N+1 queries using joinedload. Database connection pooling via PgBouncer. **PARTIAL (Stage 6 P2 + Stage 7 C2):** dashboard + catalog + permissions Redis/app cache with invalidation; PgBouncer remains deferred.
7. Security: Input sanitization on all endpoints. CORS restricted to known origins. Security headers (HSTS, CSP, X-Frame-Options). Rate limiting per tenant tier. Container security: non-root user, read-only root filesystem, dropped capabilities.

FRONTEND (Next.js):
1. Backup page: admin-only. Table of backups with download/restore buttons. Schedule config form (cron expression picker). Restore confirmation with "Type RESTORE to confirm" safety.
2. Audit log viewer: filter sidebar (date range, user dropdown, event type checkboxes). Table with expandable rows showing old/new value diff (green for added, red for removed).
3. Security settings: 2FA setup modal with QR code and 6-digit input. Active sessions table showing device, IP, location, last active, revoke button.
4. API Keys: generate button, copy-to-clipboard, revoke button. Usage chart (requests per day). **COMPLETE (Stage 7 K2).**
5. Onboarding checklist: persistent banner for new tenants. 5 steps with progress bar. Each step links to relevant page. Dismissible after 80% complete.

DEVOPS:
1. Production Kubernetes deployment: Helm charts with values-production.yaml. Ingress with TLS 1.3. Cert-manager for Let's Encrypt. HPA for backend (5-20 pods), frontend (3-10 pods), Celery (3-15 pods).
2. Monitoring: Prometheus + Grafana. Dashboards: API latency, error rate, database connections, Redis memory, queue depth. Alerts: PagerDuty integration for error rate > 5%, disk > 80%, DB connections > 80%.
3. Logging: Structured JSON logs (structlog). Fluent Bit → Elasticsearch → Kibana. Centralized log aggregation with tenant_id tagging.
4. CI/CD: GitHub Actions → build → test → security scan (Trivy) → deploy to staging → manual approval → deploy to production.

Acceptance Criteria:
- Backup completes in < 10 minutes for 5GB database. Restore completes in < 30 minutes.
- Audit log captures every product update with exact old/new values diff.
- API key authentication works with external curl request. Rate limit headers returned (X-RateLimit-Limit, X-RateLimit-Remaining).
- 2FA setup succeeds and subsequent login requires 6-digit code.
- Dashboard loads in < 2 seconds with < 20 database queries (cached).
- Load test: 1000 concurrent users, 95th percentile response time < 500ms, 0% error rate.
- Security scan: zero critical vulnerabilities in dependencies (Trivy).
- All 5 phases of features functional end-to-end in production environment.
```

---

## 7. Appendix: Cross-Cutting Concerns

### 7.1 Technology Stack Consistency

All phases use the same technical stack:
- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, Celery + RabbitMQ
- **Frontend:** React / Next.js 14
- **Mobile:** Flutter / React Native (post-MVP)
- **AI:** Pandas, Scikit-learn, Prophet
- **Storage:** S3-Compatible Storage
- **Auth:** JWT + OAuth2
- **Container:** Docker
- **Deployment:** Kubernetes
- **CI/CD:** GitHub Actions

### 7.2 Definition of Done (Per Feature)

Every feature in every phase must meet:
- [ ] Code written and peer-reviewed
- [ ] Unit tests written and passing (> 80% coverage)
- [ ] Integration tests passing
- [ ] API documentation updated (OpenAPI/Swagger)
- [ ] UI implemented with responsive design
- [ ] Accessibility checked (WCAG 2.1 AA)
- [ ] Security review completed (no secrets in code, input validation, RBAC)
- [ ] Database migration created and tested
- [ ] Deployed to staging and manually tested
- [ ] Product owner acceptance

### 7.3 Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Multi-tenant schema migration complexity** | Automated Alembic env.py tested early in Phase 1. Migration dry-runs on staging clones. |
| **AI model accuracy below expectations** | Fallback to rule-based logic. Continuous model retraining pipeline. Human-in-the-loop validation. |
| **POS hardware integration delays** | Abstract hardware layer. Mock implementations for development. Bluetooth/USB HID as fallback. |
| **Performance degradation at scale** | Load testing in Phase 5. Read replicas for reports. Connection pooling. Caching strategy. |
| **Security vulnerabilities** | Security-focused Phase 5. Third-party penetration test. OWASP ZAP scanning in CI/CD. |
| **Team bandwidth constraints** | Parallel track development (Backend + Frontend). Feature flags for incomplete work. Scope cut criteria defined. |

### 7.4 Post-MVP Roadmap (Preview)

| Quarter | Focus Area | Key Features |
|---------|------------|--------------|
| **Q1 2027** | Mobile & API | Flutter mobile app, expanded API v2, OAuth2 provider, webhook marketplace |
| **Q2 2027** | Advanced Accounting | Bank reconciliation, multi-currency, fixed assets, payroll integration |
| **Q3 2027** | Supply Chain | Multi-warehouse with locations, batch/lot tracking, expiry management, demand planning |
| **Q4 2027** | Enterprise Scale | Custom fields, workflow builder, advanced analytics (Power BI/Tableau), SSO/SAML |
| **Q1 2028** | Ecosystem | App marketplace, third-party integrations (Shopify, WooCommerce, Amazon), white-labeling |

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Technical Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, Celery + RabbitMQ, React/Next.js, Docker, Kubernetes, GitHub Actions  
**Owner:** Product & Engineering Leadership  
**Review Cycle:** Bi-weekly (per sprint) or upon scope changes

**Stage 52 exit (2026-08-11):** I1, R1, D1, H52x met — `docs/STAGE_52_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_110_STAGE52_FREEZE.md`. Fidelity: `docs/STAGE_52_FIDELITY.md`.

**Stage 53 open (2026-08-11):** Commercial API & Lifecycle Fidelity track approved — `docs/ADR_111_STAGE53_OPEN.md` + `docs/STAGE_53_PLAN.md` (API/integration commercial → cancellation/churn → fidelity).

**Stage 53 A1 (2026-08-11):** API & integration commercial honesty — `docs/API_INTEGRATION_COMMERCIAL_MVP.md`, `ops/mvp/api-integration-commercial.json`, evidence `stage53_a1_api_integration_commercial.json` (`test_api_integration_commercial_a1.py`); live API rate-limit upgrade billing Remaining.

**Stage 53 C1 (2026-08-11):** Cancellation / refund / churn policy honesty — `docs/CANCELLATION_CHURN_MVP.md`, `ops/mvp/cancellation-churn.json`, evidence `stage53_c1_cancellation_churn.json` (`test_cancellation_churn_c1.py`); live cancellation portal Remaining.

**Stage 53 D1 (2026-08-11):** API & lifecycle fidelity sync — `docs/STAGE_53_FIDELITY.md` (`test_stage53_fidelity_d1.py`); maps A1–C1 → readiness / launch / deploy / security.

**Stage 53 exit (2026-08-11):** A1, C1, D1, H53x met — `docs/STAGE_53_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_112_STAGE53_FREEZE.md`. Fidelity: `docs/STAGE_53_FIDELITY.md`.

**Stage 54 open (2026-08-11):** Commercial Go-To-Market Fidelity track approved — `docs/ADR_113_STAGE54_OPEN.md` + `docs/STAGE_54_PLAN.md` (digital marketing/testimonials → direct sales → fidelity).

**Stage 54 M1 (2026-08-11):** Digital marketing / case studies / testimonials honesty — `docs/DIGITAL_MARKETING_MVP.md`, `ops/mvp/digital-marketing.json`, evidence `stage54_m1_digital_marketing.json` (`test_digital_marketing_m1.py`); live digital marketing campaigns Remaining.

**Stage 54 S1 (2026-08-11):** Direct sales honesty — `docs/DIRECT_SALES_MVP.md`, `ops/mvp/direct-sales.json`, evidence `stage54_s1_direct_sales.json` (`test_direct_sales_s1.py`); live inside-sales team Remaining.

**Stage 54 D1 (2026-08-11):** Go-to-market fidelity sync — `docs/STAGE_54_FIDELITY.md` (`test_stage54_fidelity_d1.py`); maps M1–S1 → readiness / launch / deploy / security.

**Stage 54 exit (2026-08-11):** M1, S1, D1, H54x met — `docs/STAGE_54_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_114_STAGE54_FREEZE.md`. Fidelity: `docs/STAGE_54_FIDELITY.md`.

**Stage 55 open (2026-08-11):** Commercial Licensing & Positioning Fidelity track approved — `docs/ADR_115_STAGE55_OPEN.md` + `docs/STAGE_55_PLAN.md` (white-label licensing → unit economics/competitive positioning → fidelity).

**Stage 55 W1 (2026-08-11):** White-label licensing commercial honesty — `docs/WHITE_LABEL_LICENSING_MVP.md`, `ops/mvp/white-label-licensing.json`, evidence `stage55_w1_white_label_licensing.json` (`test_white_label_licensing_w1.py`); live white-label licensing Remaining.

**Stage 55 U1 (2026-08-11):** Unit economics / competitive positioning honesty — `docs/UNIT_ECONOMICS_POSITIONING_MVP.md`, `ops/mvp/unit-economics-positioning.json`, evidence `stage55_u1_unit_economics_positioning.json` (`test_unit_economics_positioning_u1.py`); measured CAC/LTV Remaining.

**Stage 55 D1 (2026-08-11):** Licensing & positioning fidelity sync — `docs/STAGE_55_FIDELITY.md` (`test_stage55_fidelity_d1.py`); maps W1–U1 → readiness / launch / deploy / security.

**Stage 55 exit (2026-08-11):** W1, U1, D1, H55x met — `docs/STAGE_55_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_116_STAGE55_FREEZE.md`. Fidelity: `docs/STAGE_55_FIDELITY.md`.

**Stage 56 open (2026-08-11):** Commercial Onboarding & Expansion Fidelity track approved — `docs/ADR_117_STAGE56_OPEN.md` + `docs/STAGE_56_PLAN.md` (implementation/onboarding → geographic expansion → fidelity).

**Stage 56 O1 (2026-08-11):** Implementation & onboarding commercial honesty — `docs/IMPLEMENTATION_ONBOARDING_MVP.md`, `ops/mvp/implementation-onboarding.json`, evidence `stage56_o1_implementation_onboarding.json` (`test_implementation_onboarding_o1.py`); live data-migration fee billing Remaining.

**Stage 56 G1 (2026-08-11):** Geographic expansion honesty — `docs/GEOGRAPHIC_EXPANSION_MVP.md`, `ops/mvp/geographic-expansion.json`, evidence `stage56_g1_geographic_expansion.json` (`test_geographic_expansion_g1.py`); multi-market expansion Remaining.

**Stage 56 D1 (2026-08-11):** Onboarding & expansion fidelity sync — `docs/STAGE_56_FIDELITY.md` (`test_stage56_fidelity_d1.py`); maps O1–G1 → readiness / launch / deploy / security.

**Stage 56 exit (2026-08-11):** O1, G1, D1, H56x met — `docs/STAGE_56_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_118_STAGE56_FREEZE.md`. Fidelity: `docs/STAGE_56_FIDELITY.md`.

**Stage 57 open (2026-08-11):** Commercial Mobile & Metrics Fidelity track approved — `docs/ADR_119_STAGE57_OPEN.md` + `docs/STAGE_57_PLAN.md` (mobile app GTM → success metrics → fidelity).

**Stage 57 A1 (2026-08-11):** Mobile app GTM honesty — `docs/MOBILE_APP_GTM_MVP.md`, `ops/mvp/mobile-app-gtm.json`, evidence `stage57_a1_mobile_app_gtm.json` (`test_mobile_app_gtm_a1.py`); live Flutter / store publish Remaining.

**Stage 57 K1 (2026-08-11):** Success metrics honesty — `docs/SUCCESS_METRICS_MVP.md`, `ops/mvp/success-metrics.json`, evidence `stage57_k1_success_metrics.json` (`test_success_metrics_k1.py`); measured MAU / NPS / uptime Remaining.

**Stage 57 D1 (2026-08-11):** Mobile & metrics fidelity sync — `docs/STAGE_57_FIDELITY.md` (`test_stage57_fidelity_d1.py`); maps A1–K1 → readiness / launch / deploy / security.

**Stage 57 exit (2026-08-11):** A1, K1, D1, H57x met — `docs/STAGE_57_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_120_STAGE57_FREEZE.md`. Fidelity: `docs/STAGE_57_FIDELITY.md`.

**Stage 58 open (2026-08-11):** Commercial Business & AI Metrics Fidelity track approved — `docs/ADR_121_STAGE58_OPEN.md` + `docs/STAGE_58_PLAN.md` (business metrics → AI metrics → fidelity).

**Stage 58 B1 (2026-08-11):** Business metrics honesty — `docs/BUSINESS_METRICS_MVP.md`, `ops/mvp/business-metrics.json`, evidence `stage58_b1_business_metrics.json` (`test_business_metrics_b1.py`); measured MRR / NRR Remaining.

**Stage 58 I1 (2026-08-11):** AI metrics honesty — `docs/AI_METRICS_MVP.md`, `ops/mvp/ai-metrics.json`, evidence `stage58_i1_ai_metrics.json` (`test_ai_metrics_i1.py`); measured AI adoption / accuracy Remaining.

**Stage 58 D1 (2026-08-11):** Business & AI metrics fidelity sync — `docs/STAGE_58_FIDELITY.md` (`test_stage58_fidelity_d1.py`); maps B1–I1 → readiness / launch / deploy / security.

**Stage 58 exit (2026-08-11):** B1, I1, D1, H58x met — `docs/STAGE_58_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_122_STAGE58_FREEZE.md`. Fidelity: `docs/STAGE_58_FIDELITY.md`.

**Stage 59 open (2026-08-11):** Commercial Channel Extensions Fidelity track approved — `docs/ADR_123_STAGE59_OPEN.md` + `docs/STAGE_59_PLAN.md` (e-commerce integration → CRM commercial → fidelity).

**Stage 59 E1 (2026-08-11):** E-commerce integration honesty — `docs/ECOMMERCE_INTEGRATION_MVP.md`, `ops/mvp/ecommerce-integration.json`, evidence `stage59_e1_ecommerce_integration.json` (`test_ecommerce_integration_e1.py`); live Shopify / WooCommerce Remaining.

**Stage 59 C1 (2026-08-11):** CRM commercial honesty — `docs/CRM_COMMERCIAL_MVP.md`, `ops/mvp/crm-commercial.json`, evidence `stage59_c1_crm_commercial.json` (`test_crm_commercial_c1.py`); live CRM module / segmentation Remaining.

**Stage 59 D1 (2026-08-11):** Channel extensions fidelity sync — `docs/STAGE_59_FIDELITY.md` (`test_stage59_fidelity_d1.py`); maps E1–C1 → readiness / launch / deploy / security.

**Stage 59 exit (2026-08-11):** E1, C1, D1, H59x met — `docs/STAGE_59_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_124_STAGE59_FREEZE.md`. Fidelity: `docs/STAGE_59_FIDELITY.md`.

**Stage 60 open (2026-08-11):** Commercial Manufacturing & Tax Fidelity track approved — `docs/ADR_125_STAGE60_OPEN.md` + `docs/STAGE_60_PLAN.md` (advanced manufacturing → multi-country tax → fidelity).

**Stage 60 M1 (2026-08-11):** Advanced manufacturing honesty — `docs/ADVANCED_MANUFACTURING_MVP.md`, `ops/mvp/advanced-manufacturing.json`, evidence `stage60_m1_advanced_manufacturing.json` (`test_advanced_manufacturing_m1.py`); live MRP / production scheduling Remaining.

**Stage 60 T1 (2026-08-11):** Multi-country tax honesty — `docs/MULTI_COUNTRY_TAX_MVP.md`, `ops/mvp/multi-country-tax.json`, evidence `stage60_t1_multi_country_tax.json` (`test_multi_country_tax_t1.py`); live multi-country tax e-file Remaining.

**Stage 60 D1 (2026-08-11):** Manufacturing & tax fidelity sync — `docs/STAGE_60_FIDELITY.md` (`test_stage60_fidelity_d1.py`); maps M1–T1 → readiness / launch / deploy / security.

**Stage 60 exit (2026-08-11):** M1, T1, D1, H60x met — `docs/STAGE_60_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_126_STAGE60_FREEZE.md`. Fidelity: `docs/STAGE_60_FIDELITY.md`.

**Stage 61 open (2026-08-11):** Commercial Fintech & Supply-Chain Fidelity track approved — `docs/ADR_127_STAGE61_OPEN.md` + `docs/STAGE_61_PLAN.md` (embedded fintech → supply chain integration → fidelity).

**Stage 61 F1 (2026-08-11):** Embedded fintech honesty — `docs/EMBEDDED_FINTECH_MVP.md`, `ops/mvp/embedded-fintech.json`, evidence `stage61_f1_embedded_fintech.json` (`test_embedded_fintech_f1.py`); live lending / invoice financing Remaining.

**Stage 61 S1 (2026-08-11):** Supply chain integration honesty — `docs/SUPPLY_CHAIN_INTEGRATION_MVP.md`, `ops/mvp/supply-chain-integration.json`, evidence `stage61_s1_supply_chain_integration.json` (`test_supply_chain_integration_s1.py`); live supplier supply-chain Remaining.

**Stage 61 D1 (2026-08-11):** Fintech & supply-chain fidelity sync — `docs/STAGE_61_FIDELITY.md` (`test_stage61_fidelity_d1.py`); maps F1–S1 → readiness / launch / deploy / security.

**Stage 61 exit (2026-08-11):** F1, S1, D1, H61x met — `docs/STAGE_61_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_128_STAGE61_FREEZE.md`. Fidelity: `docs/STAGE_61_FIDELITY.md`.

**Stage 62 open (2026-08-11):** Commercial IoT & AI Marketplace Fidelity track approved — `docs/ADR_129_STAGE62_OPEN.md` + `docs/STAGE_62_PLAN.md` (IoT integration → AI model marketplace → fidelity).

**Stage 62 I1 (2026-08-11):** IoT integration honesty — `docs/IOT_INTEGRATION_MVP.md`, `ops/mvp/iot-integration.json`, evidence `stage62_i1_iot_integration.json` (`test_iot_integration_i1.py`); live smart shelves / temperature sensors Remaining.

**Stage 62 A1 (2026-08-11):** AI model marketplace honesty — `docs/AI_MODEL_MARKETPLACE_MVP.md`, `ops/mvp/ai-model-marketplace.json`, evidence `stage62_a1_ai_model_marketplace.json` (`test_ai_model_marketplace_a1.py`); live industry-prediction marketplace Remaining.

**Stage 62 D1 (2026-08-11):** IoT & AI marketplace fidelity sync — `docs/STAGE_62_FIDELITY.md` (`test_stage62_fidelity_d1.py`); maps I1–A1 → readiness / launch / deploy / security.

**Stage 62 exit (2026-08-11):** I1, A1, D1, H62x met — `docs/STAGE_62_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_130_STAGE62_FREEZE.md`. Fidelity: `docs/STAGE_62_FIDELITY.md`.

**Stage 63 open (2026-08-11):** Commercial Capital & Scale Fidelity track approved — `docs/ADR_131_STAGE63_OPEN.md` + `docs/STAGE_63_PLAN.md` (IPO readiness → global scale → fidelity).

**Stage 63 P1 (2026-08-11):** IPO readiness honesty — `docs/IPO_READINESS_MVP.md`, `ops/mvp/ipo-readiness.json`, evidence `stage63_p1_ipo_readiness.json` (`test_ipo_readiness_p1.py`); live IPO / Series B–C funding Remaining.

**Stage 63 G1 (2026-08-11):** Global scale honesty — `docs/GLOBAL_SCALE_MVP.md`, `ops/mvp/global-scale.json`, evidence `stage63_g1_global_scale.json` (`test_global_scale_g1.py`); measured 50k customers / 20+ countries Remaining.

**Stage 63 D1 (2026-08-11):** Capital & scale fidelity sync — `docs/STAGE_63_FIDELITY.md` (`test_stage63_fidelity_d1.py`); maps P1–G1 → readiness / launch / deploy / security.

**Stage 63 exit (2026-08-11):** P1, G1, D1, H63x met — `docs/STAGE_63_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_132_STAGE63_FREEZE.md`. Fidelity: `docs/STAGE_63_FIDELITY.md`.

**Stage 64 open (2026-08-11):** Commercial Analytics & Franchise Fidelity track approved — `docs/ADR_133_STAGE64_OPEN.md` + `docs/STAGE_64_PLAN.md` (Advanced BI → franchise & chain → fidelity).

**Stage 64 B1 (2026-08-11):** Advanced BI honesty — `docs/ADVANCED_BI_MVP.md`, `ops/mvp/advanced-bi.json`, evidence `stage64_b1_advanced_bi.json` (`test_advanced_bi_b1.py`); live Advanced BI / custom analytics Remaining.

**Stage 64 F1 (2026-08-11):** Franchise & chain enterprise honesty — `docs/FRANCHISE_CHAIN_MVP.md`, `ops/mvp/franchise-chain.json`, evidence `stage64_f1_franchise_chain.json` (`test_franchise_chain_f1.py`); live franchise / chain deals Remaining.

**Stage 64 D1 (2026-08-11):** Analytics & franchise fidelity sync — `docs/STAGE_64_FIDELITY.md` (`test_stage64_fidelity_d1.py`); maps B1–F1 → readiness / launch / deploy / security.

**Stage 64 exit (2026-08-11):** B1, F1, D1, H64x met — `docs/STAGE_64_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_134_STAGE64_FREEZE.md`. Fidelity: `docs/STAGE_64_FIDELITY.md`. Stage 65 next (not yet opened).

**Stage 65 open (2026-08-11):** MVP Release Candidate Fidelity track approved — `docs/ADR_135_STAGE65_OPEN.md` + `docs/STAGE_65_PLAN.md` (Development → Internal QA → Staging → Controlled Business Pilot → … → MVP Release Candidate; R1 next).

**Stage 65 R1 (2026-08-11):** Release pipeline honesty — `docs/RELEASE_PIPELINE_MVP.md`, `ops/mvp/release-pipeline.json`, evidence `stage65_r1_release_pipeline.json` (`test_release_pipeline_r1.py`); signed MVP RC / live staging promotion Remaining.

**Stage 65 P1 (2026-08-11):** Controlled business pilot honesty — `docs/BUSINESS_PILOT_MVP.md`, `ops/mvp/business-pilot.json`, evidence `stage65_p1_business_pilot.json` (`test_business_pilot_p1.py`); live controlled business pilot Remaining.

**Stage 65 D1 (2026-08-11):** MVP release-candidate fidelity sync — `docs/STAGE_65_FIDELITY.md` (`test_stage65_fidelity_d1.py`); maps R1–P1 → readiness / launch / deploy / security.

**Stage 65 exit (2026-08-11):** R1, P1, D1, H65x met — `docs/STAGE_65_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_136_STAGE65_FREEZE.md`. Fidelity: `docs/STAGE_65_FIDELITY.md`. Stage 66 opened via ADR-138.

**Stage 66 open (2026-08-11):** MVP Production Launch Fidelity track approved — `docs/ADR_138_STAGE66_OPEN.md` + `docs/STAGE_66_PLAN.md` (MVP Release Candidate → Production Cutover → First Paying Tenant → Go-Live Attestation → MVP Production Launch; L1 next).

**Stage 66 L1 (2026-08-11):** Production launch honesty — `docs/PRODUCTION_LAUNCH_MVP.md`, `ops/mvp/production-launch.json`, evidence `stage66_l1_production_launch.json` (`test_production_launch_l1.py`); live cutover / §7 signed / go-live Remaining.

**Stage 66 T1 (2026-08-11):** First tenant go-live honesty — `docs/FIRST_TENANT_GOLIVE_MVP.md`, `ops/mvp/first-tenant-golive.json`, evidence `stage66_t1_first_tenant_golive.json` (`test_first_tenant_golive_t1.py`); first paying tenant / live onboarding Remaining.

**Stage 66 D1 (2026-08-11):** MVP production-launch fidelity sync — `docs/STAGE_66_FIDELITY.md` (`test_stage66_fidelity_d1.py`); maps L1–T1 → readiness / launch / deploy / security.

**Stage 66 exit (2026-08-11):** L1, T1, D1, H66x met — `docs/STAGE_66_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_139_STAGE66_FREEZE.md`. Fidelity: `docs/STAGE_66_FIDELITY.md`. Stage 67 opened via ADR-140.

**Stage 67 open (2026-08-11):** MVP Post-Launch Continuity Fidelity track approved — `docs/ADR_140_STAGE67_OPEN.md` + `docs/STAGE_67_PLAN.md` (MVP Production Launch → Production Hypercare → Operator Steady-State Handoff → Customer Success Stabilization → Post-Launch Continuity; H1 next).

**Stage 67 H1 (2026-08-11):** Production hypercare honesty — `docs/PRODUCTION_HYPERCARE_MVP.md`, `ops/mvp/production-hypercare.json`, evidence `stage67_h1_production_hypercare.json` (`test_production_hypercare_h1.py`); live hypercare / incident drill Remaining.

**Stage 67 C1 (2026-08-11):** Post-launch continuity honesty — `docs/POST_LAUNCH_CONTINUITY_MVP.md`, `ops/mvp/post-launch-continuity.json`, evidence `stage67_c1_post_launch_continuity.json` (`test_post_launch_continuity_c1.py`); live continuity / steady-state handoff Remaining.

**Stage 67 D1 (2026-08-11):** MVP post-launch continuity fidelity sync — `docs/STAGE_67_FIDELITY.md` (`test_stage67_fidelity_d1.py`); maps H1–C1 → readiness / launch / deploy / security.

**Stage 67 exit (2026-08-11):** H1, C1, D1, H67x met — `docs/STAGE_67_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_141_STAGE67_FREEZE.md`. Fidelity: `docs/STAGE_67_FIDELITY.md`. Stage 68 opened via ADR-142.

**Stage 68 open (2026-08-11):** Platform ↔ Tenant Console Fidelity track approved — `docs/ADR_142_STAGE68_OPEN.md` + `docs/STAGE_68_PLAN.md` (RIBDIGI HOUSE Platform Owner ↔ TENANT COMPANY Dashboard; H1 next).

**Stage 68 H1 (2026-08-11):** Ribdigi House console honesty — `docs/RIBDIGI_HOUSE_CONSOLE_MVP.md`, `ops/mvp/ribdigi-house-console.json`, evidence `stage68_h1_ribdigi_house_console.json` (`test_ribdigi_house_console_h1.py`); paid billing / live subscriptions Remaining.

**Stage 68 T1 (2026-08-11):** Tenant Company console honesty — `docs/TENANT_COMPANY_CONSOLE_MVP.md`, `ops/mvp/tenant-company-console.json`, evidence `stage68_t1_tenant_company_console.json` (`test_tenant_company_console_t1.py`); module re-Complete / demo tenant Remaining.

**Stage 68 D1 (2026-08-11):** Platform ↔ Tenant console fidelity sync — `docs/STAGE_68_FIDELITY.md` (`test_stage68_fidelity_d1.py`); maps H1–T1 → readiness / launch / deploy / security.

**Stage 68 exit (2026-08-11):** H1, T1, D1, H68x met — `docs/STAGE_68_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_143_STAGE68_FREEZE.md`. Fidelity: `docs/STAGE_68_FIDELITY.md`. Stage 69 opened via ADR-144.

**Stage 69 open (2026-08-11):** MVP Commercial Go-Live Fidelity track approved — `docs/ADR_144_STAGE69_OPEN.md` + `docs/STAGE_69_PLAN.md` (Platform ↔ Tenant Consoles Ready → Pre-Flight §§1–3 → Go-Live Attestation §7 → First Commercial Day Ops → MVP Commercial Go-Live; V1 next).

**Stage 69 V1 (2026-08-11):** Pre-flight verification honesty — `docs/PREFLIGHT_VERIFICATION_MVP.md`, `ops/mvp/preflight-verification.json`, evidence `stage69_v1_preflight_verification.json` (`test_preflight_verification_v1.py`); §§1–3 verified Remaining.

**Stage 69 A1 (2026-08-11):** Go-live attestation honesty — `docs/GOLIVE_ATTESTATION_MVP.md`, `ops/mvp/golive-attestation.json`, evidence `stage69_a1_golive_attestation.json` (`test_golive_attestation_a1.py`); §7 signed Remaining.

**Stage 69 D1 (2026-08-11):** MVP Commercial Go-Live fidelity sync — `docs/STAGE_69_FIDELITY.md` (`test_stage69_fidelity_d1.py`); maps V1–A1 → readiness / launch / deploy / security.

**Stage 69 exit (2026-08-11):** V1, A1, D1, H69x met — `docs/STAGE_69_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_145_STAGE69_FREEZE.md`. Fidelity: `docs/STAGE_69_FIDELITY.md`. Stage 70 opened via ADR-146.

**Stage 70 open (2026-08-11):** First Commercial Day Fidelity track approved — `docs/ADR_146_STAGE70_OPEN.md` + `docs/STAGE_70_PLAN.md` (First Commercial Day Ops → MVP Commercial Go-Live Closeout → First Commercial Day Fidelity; F1 next).

**Stage 70 F1 (2026-08-11):** First commercial day ops honesty — `docs/FIRST_COMMERCIAL_DAY_MVP.md`, `ops/mvp/first-commercial-day.json`, evidence `stage70_f1_first_commercial_day.json` (`test_first_commercial_day_f1.py`); first-day live Remaining.

**Stage 70 G1 (2026-08-11):** Commercial go-live closeout honesty — `docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md`, `ops/mvp/commercial-golive-closeout.json`, evidence `stage70_g1_commercial_golive_closeout.json` (`test_commercial_golive_closeout_g1.py`); go-live Remaining.

**Stage 70 D1 (2026-08-11):** First Commercial Day fidelity sync — `docs/STAGE_70_FIDELITY.md` (`test_stage70_fidelity_d1.py`); maps F1–G1 → readiness / launch / deploy / security.

**Stage 70 exit (2026-08-11):** F1, G1, D1, H70x met — `docs/STAGE_70_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_147_STAGE70_FREEZE.md`. Fidelity: `docs/STAGE_70_FIDELITY.md`. Stage 71 opened via ADR-148.

**Stage 71 open (2026-08-11):** Commercial Steady-State Fidelity track approved — `docs/ADR_148_STAGE71_OPEN.md` + `docs/STAGE_71_PLAN.md` (Steady-State Commercial Ops → Commercial Acceptance Gate → Commercial Steady-State Fidelity; S1 next).

**Stage 71 S1 (2026-08-11):** Steady-state commercial ops honesty — `docs/STEADY_STATE_OPS_MVP.md`, `ops/mvp/steady-state-ops.json`, evidence `stage71_s1_steady_state_ops.json` (`test_steady_state_ops_s1.py`); steady-state live Remaining.

**Stage 71 A1 (2026-08-11):** Commercial acceptance gate honesty — `docs/COMMERCIAL_ACCEPTANCE_MVP.md`, `ops/mvp/commercial-acceptance.json`, evidence `stage71_a1_commercial_acceptance.json` (`test_commercial_acceptance_a1.py`); acceptance Remaining.

**Stage 71 D1 (2026-08-11):** Commercial Steady-State fidelity sync — `docs/STAGE_71_FIDELITY.md` (`test_stage71_fidelity_d1.py`); maps S1–A1 → readiness / launch / deploy / security.

**Stage 71 exit (2026-08-11):** S1, A1, D1, H71x met — `docs/STAGE_71_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_149_STAGE71_FREEZE.md`. Fidelity: `docs/STAGE_71_FIDELITY.md`. Stage 72 opened via ADR-150.

**Stage 72 open (2026-08-11):** Commercial Packaging Closeout Fidelity track approved — `docs/ADR_150_STAGE72_OPEN.md` + `docs/STAGE_72_PLAN.md` (Commercial Residual Remaining Register → MVP Commercial Packaging Archive → Commercial Packaging Closeout Fidelity; R1 next).

**Stage 72 R1 (2026-08-11):** Commercial residual remaining honesty — `docs/COMMERCIAL_RESIDUAL_MVP.md`, `ops/mvp/commercial-residual.json`, evidence `stage72_r1_commercial_residual.json` (`test_commercial_residual_r1.py`); residual closed Remaining.

**Stage 72 P1 (2026-08-11):** Commercial packaging archive honesty — `docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md`, `ops/mvp/commercial-packaging-archive.json`, evidence `stage72_p1_commercial_packaging_archive.json` (`test_commercial_packaging_archive_p1.py`); archive live Remaining.

**Stage 72 D1 (2026-08-11):** Commercial Packaging Closeout fidelity sync — `docs/STAGE_72_FIDELITY.md` (`test_stage72_fidelity_d1.py`); maps R1–P1 → readiness / launch / deploy / security.

**Stage 72 exit (2026-08-11):** R1, P1, D1, H72x met — `docs/STAGE_72_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_151_STAGE72_FREEZE.md`. Fidelity: `docs/STAGE_72_FIDELITY.md`. Stage 73 opened via ADR-152.

**Stage 73 open (2026-08-11):** Commercial Assurance Fidelity track approved — `docs/ADR_152_STAGE73_OPEN.md` + `docs/STAGE_73_PLAN.md` (Commercial Evidence Chain → Commercial Assurance Boundary → Commercial Assurance Fidelity; E1 next).

**Stage 73 E1 (2026-08-11):** Commercial evidence chain honesty — `docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md`, `ops/mvp/commercial-evidence-chain.json`, evidence `stage73_e1_commercial_evidence_chain.json` (`test_commercial_evidence_chain_e1.py`); evidence chain live Remaining.

**Stage 73 A1 (2026-08-11):** Commercial assurance boundary honesty — `docs/COMMERCIAL_ASSURANCE_MVP.md`, `ops/mvp/commercial-assurance.json`, evidence `stage73_a1_commercial_assurance.json` (`test_commercial_assurance_a1.py`); customer assurance Remaining.

**Stage 73 D1 (2026-08-11):** Commercial Assurance fidelity sync — `docs/STAGE_73_FIDELITY.md` (`test_stage73_fidelity_d1.py`); maps E1–A1 → readiness / launch / deploy / security.

**Stage 73 exit (2026-08-11):** E1, A1, D1, H73x met — `docs/STAGE_73_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_153_STAGE73_FREEZE.md`. Fidelity: `docs/STAGE_73_FIDELITY.md`. Stage 74 opened via ADR-154.

**Stage 74 open (2026-08-11):** Commercial Operator Boundary Fidelity track approved — `docs/ADR_154_STAGE74_OPEN.md` + `docs/STAGE_74_PLAN.md` (Commercial Support Boundary → Commercial Status Boundary → Commercial Operator Boundary Fidelity; S1 next).

**Stage 74 S1 (2026-08-11):** Commercial support boundary honesty — `docs/COMMERCIAL_SUPPORT_MVP.md`, `ops/mvp/commercial-support.json`, evidence `stage74_s1_commercial_support.json` (`test_commercial_support_s1.py`); support boundary live Remaining.

**Stage 74 U1 (2026-08-11):** Commercial status boundary honesty — `docs/COMMERCIAL_STATUS_MVP.md`, `ops/mvp/commercial-status.json`, evidence `stage74_u1_commercial_status.json` (`test_commercial_status_u1.py`); status page live Remaining.

**Stage 74 D1 (2026-08-11):** Commercial Operator Boundary fidelity sync — `docs/STAGE_74_FIDELITY.md` (`test_stage74_fidelity_d1.py`); maps S1–U1 → readiness / launch / deploy / security.

**Stage 74 exit (2026-08-11):** S1, U1, D1, H74x met — `docs/STAGE_74_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_155_STAGE74_FREEZE.md`. Fidelity: `docs/STAGE_74_FIDELITY.md`.

**Stage 75 open (2026-08-11):** Commercial Trust Boundary Fidelity track approved — `docs/ADR_156_STAGE75_OPEN.md` + `docs/STAGE_75_PLAN.md` (Commercial Security Contact Boundary → Commercial Privacy Notice Boundary → Commercial Trust Boundary Fidelity; C1 next).

**Stage 75 C1 (2026-08-11):** Commercial security contact honesty — `docs/COMMERCIAL_SECURITY_CONTACT_MVP.md`, `ops/mvp/commercial-security-contact.json`, evidence `stage75_c1_commercial_security_contact.json` (`test_commercial_security_contact_c1.py`); security contact live Remaining.

**Stage 75 P1 (2026-08-11):** Commercial privacy notice honesty — `docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md`, `ops/mvp/commercial-privacy-notice.json`, evidence `stage75_p1_commercial_privacy_notice.json` (`test_commercial_privacy_notice_p1.py`); privacy notice live Remaining.

**Stage 75 D1 (2026-08-11):** Commercial Trust Boundary fidelity sync — `docs/STAGE_75_FIDELITY.md` (`test_stage75_fidelity_d1.py`); maps C1–P1 → readiness / launch / deploy / security.

**Stage 75 exit (2026-08-11):** C1, P1, D1, H75x met — `docs/STAGE_75_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_157_STAGE75_FREEZE.md`. Fidelity: `docs/STAGE_75_FIDELITY.md`.

**Stage 76 open (2026-08-11):** Commercial Contract Boundary Fidelity track approved — `docs/ADR_158_STAGE76_OPEN.md` + `docs/STAGE_76_PLAN.md` (Commercial Terms Boundary → Commercial Billing Deferred Boundary → Commercial Contract Boundary Fidelity; T1 next).

**Stage 76 T1 (2026-08-11):** Commercial terms honesty — `docs/COMMERCIAL_TERMS_MVP.md`, `ops/mvp/commercial-terms.json`, evidence `stage76_t1_commercial_terms.json` (`test_commercial_terms_t1.py`); signed ToS Remaining.

**Stage 76 B1 (2026-08-11):** Commercial billing deferred honesty — `docs/COMMERCIAL_BILLING_DEFERRED_MVP.md`, `ops/mvp/commercial-billing-deferred.json`, evidence `stage76_b1_commercial_billing_deferred.json` (`test_commercial_billing_deferred_b1.py`); paid billing Remaining.

**Stage 76 D1 (2026-08-11):** Commercial Contract Boundary fidelity sync — `docs/STAGE_76_FIDELITY.md` (`test_stage76_fidelity_d1.py`); maps T1–B1 → readiness / launch / deploy / security.

**Stage 76 exit (2026-08-11):** T1, B1, D1, H76x met — `docs/STAGE_76_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_159_STAGE76_FREEZE.md`. Fidelity: `docs/STAGE_76_FIDELITY.md`.

**Stage 77 open (2026-08-11):** Commercial Legal Envelope Fidelity track approved — `docs/ADR_160_STAGE77_OPEN.md` + `docs/STAGE_77_PLAN.md` (Commercial DPA Boundary → Commercial Liability Boundary → Commercial Legal Envelope Fidelity; A1 next).

**Stage 77 A1 (2026-08-11):** Commercial DPA honesty — `docs/COMMERCIAL_DPA_MVP.md`, `ops/mvp/commercial-dpa.json`, evidence `stage77_a1_commercial_dpa.json` (`test_commercial_dpa_a1.py`); signed DPA Remaining.

**Stage 77 L1 (2026-08-11):** Commercial liability honesty — `docs/COMMERCIAL_LIABILITY_MVP.md`, `ops/mvp/commercial-liability.json`, evidence `stage77_l1_commercial_liability.json` (`test_commercial_liability_l1.py`); liability cap signed Remaining.

**Stage 77 D1 (2026-08-11):** Commercial Legal Envelope fidelity sync — `docs/STAGE_77_FIDELITY.md` (`test_stage77_fidelity_d1.py`); maps A1–L1 → readiness / launch / deploy / security.

**Stage 77 exit (2026-08-11):** A1, L1, D1, H77x met — `docs/STAGE_77_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_161_STAGE77_FREEZE.md`. Fidelity: `docs/STAGE_77_FIDELITY.md`.

**Stage 78 open (2026-08-11):** Commercial Procurement Boundary Fidelity track approved — `docs/ADR_162_STAGE78_OPEN.md` + `docs/STAGE_78_PLAN.md` (Commercial Pricing Boundary → Commercial Professional Services Boundary → Commercial Procurement Boundary Fidelity; P1 next).

**Stage 78 P1 (2026-08-11):** Commercial pricing honesty — `docs/COMMERCIAL_PRICING_MVP.md`, `ops/mvp/commercial-pricing.json`, evidence `stage78_p1_commercial_pricing.json` (`test_commercial_pricing_p1.py`); public pricing portal Remaining.

**Stage 78 S1 (2026-08-11):** Commercial professional services honesty — `docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md`, `ops/mvp/commercial-professional-services.json`, evidence `stage78_s1_commercial_professional_services.json` (`test_commercial_professional_services_s1.py`); signed SOW Remaining.

**Stage 78 D1 (2026-08-11):** Commercial Procurement Boundary fidelity sync — `docs/STAGE_78_FIDELITY.md` (`test_stage78_fidelity_d1.py`); maps P1–S1 → readiness / launch / deploy / security.

**Stage 78 exit (2026-08-11):** P1, S1, D1, H78x met — `docs/STAGE_78_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_163_STAGE78_FREEZE.md`. Fidelity: `docs/STAGE_78_FIDELITY.md`.

**Stage 79 open (2026-08-11):** Commercial Data Exit Fidelity track approved — `docs/ADR_164_STAGE79_OPEN.md` + `docs/STAGE_79_PLAN.md` (Commercial Data Retention/Return Boundary → Commercial Customer Audit Boundary → Commercial Data Exit Fidelity; R1 next).

**Stage 79 R1 (2026-08-11):** Commercial data retention honesty — `docs/COMMERCIAL_DATA_RETENTION_MVP.md`, `ops/mvp/commercial-data-retention.json`, evidence `stage79_r1_commercial_data_retention.json` (`test_commercial_data_retention_r1.py`); data return portal Remaining.

**Stage 79 A1 (2026-08-11):** Commercial customer audit honesty — `docs/COMMERCIAL_CUSTOMER_AUDIT_MVP.md`, `ops/mvp/commercial-customer-audit.json`, evidence `stage79_a1_commercial_customer_audit.json` (`test_commercial_customer_audit_a1.py`); customer audit rights live Remaining.

**Stage 79 D1 (2026-08-11):** Commercial Data Exit fidelity sync — `docs/STAGE_79_FIDELITY.md` (`test_stage79_fidelity_d1.py`); maps R1–A1 → readiness / launch / deploy / security.

**Stage 79 exit (2026-08-11):** R1, A1, D1, H79x met — `docs/STAGE_79_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_165_STAGE79_FREEZE.md`. Fidelity: `docs/STAGE_79_FIDELITY.md`.

**Stage 80 open (2026-08-11):** Dual-Console Dashboard Fidelity track approved — `docs/ADR_166_STAGE80_OPEN.md` + `docs/STAGE_80_PLAN.md` (Platform Owner Dashboard Charts → Tenant Role-Scoped Dashboards → Dual-Console Dashboard Fidelity; P1 next).

**Stage 80 P1 (2026-08-11):** Platform owner dashboard charts — `/api/v1/platform/dashboard/*` (`test_platform_dashboard_charts_p1.py`); `mrr_fabricated_claimed: false` (ADR-002).

**Stage 80 T1 (2026-08-11):** Tenant role-scoped dashboards — `dashboard_views` (`test_tenant_role_dashboard_t1.py`).

**Stage 80 D1 (2026-08-11):** Dual-Console Dashboard fidelity sync — `docs/STAGE_80_FIDELITY.md` (`test_stage80_fidelity_d1.py`); maps P1–T1 → readiness / launch / deploy / security.

**Stage 80 exit (2026-08-11):** P1, T1, D1, H80x met — `docs/STAGE_80_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_167_STAGE80_FREEZE.md`. Fidelity: `docs/STAGE_80_FIDELITY.md`.

**Stage 81 open (2026-08-11):** Dual-Console Admin Fidelity track approved — `docs/ADR_168_STAGE81_OPEN.md` + `docs/STAGE_81_PLAN.md` (Tenant Admin RBAC Console Surfaces → Store-Scoped Manager Ops → Dual-Console Admin Fidelity; A1 next).

**Stage 81 A1 (2026-08-11):** Tenant Admin RBAC console surfaces — `/users`, `/admin/roles`, `/admin/permissions` (`test_admin_console_a1.py`).

**Stage 81 S1 (2026-08-11):** Store-scoped manager ops — `store_scope` / `stores.manager_id` (`test_store_scoped_manager_s1.py`); ADR-005 membership Remaining.

**Stage 81 D1 (2026-08-11):** Dual-Console Admin fidelity sync — `docs/STAGE_81_FIDELITY.md` (`test_stage81_fidelity_d1.py`); maps A1–S1 → readiness / launch / deploy / security.

**Stage 81 exit (2026-08-11):** A1, S1, D1, H81x met — `docs/STAGE_81_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_169_STAGE81_FREEZE.md`. Fidelity: `docs/STAGE_81_FIDELITY.md`.

**Stage 82 open (2026-08-11):** Dual-Console Surface Parity track approved — `docs/ADR_170_STAGE82_OPEN.md` + `docs/STAGE_82_PLAN.md` (Tenant Dashboard Chart Subroutes → Platform Plans Console → Dual-Console Surface Parity; C1 next).

**Stage 82 C1 (2026-08-11):** Tenant dashboard chart/KPI subroutes — `/api/v1/dashboard/*` slices (`test_dashboard_slices_c1.py`).

**Stage 82 P1 (2026-08-11):** Platform Plans console + Activity alias — `/platform/plans` (`test_platform_plans_p1.py`); ADR-002 billing Remaining.

**Stage 82 D1 (2026-08-11):** Dual-Console Surface Parity fidelity sync — `docs/STAGE_82_FIDELITY.md` (`test_stage82_fidelity_d1.py`); maps C1–P1 → readiness / launch / deploy / security.

**Stage 82 exit (2026-08-11):** C1, P1, D1, H82x met — `docs/STAGE_82_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_171_STAGE82_FREEZE.md`. Fidelity: `docs/STAGE_82_FIDELITY.md`.

**Stage 83 open (2026-08-11):** Dual-Console Ops Fidelity track approved — `docs/ADR_172_STAGE83_OPEN.md` + `docs/STAGE_83_PLAN.md` (Store-Scoped Chart Depth → Tenant Admin User Ops → Dual-Console Ops Fidelity; S1 next).

**Stage 83 S1 (2026-08-11):** Store-scoped chart depth — `store_ids` on charts/slices (`test_store_scoped_charts_s1.py`).

**Stage 83 U1 (2026-08-11):** Tenant Admin user-ops — reset password + org assignment (`test_admin_user_ops_u1.py`).

**Stage 83 D1 (2026-08-11):** Dual-Console Ops fidelity sync — `docs/STAGE_83_FIDELITY.md` (`test_stage83_fidelity_d1.py`); maps S1–U1 → readiness / launch / deploy / security.

**Stage 83 exit (2026-08-11):** S1, U1, D1, H83x met — `docs/STAGE_83_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_173_STAGE83_FREEZE.md`. Fidelity: `docs/STAGE_83_FIDELITY.md`.

**Stage 84 open (2026-08-11):** Dual-Console Permission & Slice Fidelity track approved — `docs/ADR_174_STAGE84_OPEN.md` + `docs/STAGE_84_PLAN.md` (Dotted Permission Aliases → Tenant Dashboard Slice Depth → Dual-Console Permission & Slice Fidelity; A1 next).

**Stage 84 A1 (2026-08-11):** Dotted permission aliases — `view`→`read`; `module.action` / `module:action` (`test_permission_aliases_a1.py`).

**Stage 84 S1 (2026-08-11):** Dashboard slice depth — expenses-by-category + credit outstanding + cashier open-shift UI (`test_dashboard_slice_depth_s1.py`).

**Stage 84 D1 (2026-08-11):** Dual-Console Permission & Slice fidelity sync — `docs/STAGE_84_FIDELITY.md` (`test_stage84_fidelity_d1.py`); maps A1–S1 → readiness / launch / deploy / security.

**Stage 84 exit (2026-08-11):** A1, S1, D1, H84x met — `docs/STAGE_84_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_175_STAGE84_FREEZE.md`. Fidelity: `docs/STAGE_84_FIDELITY.md`.

**Stage 85 open (2026-08-11):** House Roster & Tenant Access Ops track approved — `docs/ADR_176_STAGE85_OPEN.md` + `docs/STAGE_85_PLAN.md` (Platform Subscriptions Roster → Admin Email Password Reset → Org-Chart Role Catalog → House Roster & Tenant Access Ops; R1 next).

**Stage 85 R1 (2026-08-11):** Platform subscriptions roster — tenant×plan metadata (`test_platform_subscriptions_r1.py`); `subscriptions_live_claimed: false`.

**Stage 85 E1 (2026-08-11):** Admin email password reset — `POST /users/{id}/password-reset-email` (`test_admin_email_reset_e1.py`).

**Stage 85 L1 (2026-08-11):** Org-chart role catalog — Manager/Tenant Admin labels + system matrix (`test_org_role_catalog_l1.py`).

**Stage 85 D1 (2026-08-11):** House Roster & Tenant Access Ops fidelity sync — `docs/STAGE_85_FIDELITY.md` (`test_stage85_fidelity_d1.py`); maps R1–L1 → readiness / launch / deploy / security.

**Stage 85 exit (2026-08-11):** R1, E1, L1, D1, H85x met — `docs/STAGE_85_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_177_STAGE85_FREEZE.md`. Fidelity: `docs/STAGE_85_FIDELITY.md`.

**Stage 86 open (2026-08-11):** House Provision & Platform Access Ops track approved — `docs/ADR_178_STAGE86_OPEN.md` + `docs/STAGE_86_PLAN.md` (House Tenant Provision → Platform Email Password Reset → Platform Audit Activity Depth → House Provision & Platform Access Ops; P1 next).

**Stage 86 P1 (2026-08-11):** House tenant provision — `POST /platform/tenants` (`test_platform_tenant_provision_p1.py`).

**Stage 86 E1 (2026-08-11):** Platform email password reset — `POST /platform/users/{id}/password-reset-email` (`test_platform_email_reset_e1.py`).

**Stage 86 A1 (2026-08-11):** Platform audit Activity depth — filters + `/platform/activity` (`test_platform_audit_activity_a1.py`).

**Stage 86 D1 (2026-08-11):** House Provision & Platform Access Ops fidelity sync — `docs/STAGE_86_FIDELITY.md` (`test_stage86_fidelity_d1.py`); maps P1–A1 → readiness / launch / deploy / security.

**Stage 86 exit (2026-08-11):** P1, E1, A1, D1, H86x met — `docs/STAGE_86_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_179_STAGE86_FREEZE.md`. Fidelity: `docs/STAGE_86_FIDELITY.md`.

**Stage 87 open (2026-08-11):** House Integrity & Console Boundary Ops track approved — `docs/ADR_180_STAGE87_OPEN.md` + `docs/STAGE_87_PLAN.md` (Platform Audit Export & Chain Verify → House Ops Surface Polish → Console Boundary Hardening → House Integrity & Console Boundary Ops; X1 next).

**Stage 87 X1 (2026-08-11):** Platform audit export + chain verify — `GET /platform/audit/export` / `GET /platform/audit/verify` (`test_platform_audit_integrity_x1.py`).

**Stage 87 Y1 (2026-08-11):** House ops surface polish — health cards, last_activity UI, operator notes, settings honesty (`test_house_ops_surface_y1.py`).

**Stage 87 Z1 (2026-08-11):** Console boundary hardening — principal cookie + middleware + soft-delete honesty (`test_console_boundary_z1.py`).

**Stage 87 D1 (2026-08-11):** House Integrity & Console Boundary Ops fidelity sync — `docs/STAGE_87_FIDELITY.md` (`test_stage87_fidelity_d1.py`); maps X1–Z1 → readiness / launch / deploy / security.

**Stage 87 exit (2026-08-11):** X1, Y1, Z1, D1, H87x met — `docs/STAGE_87_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_181_STAGE87_FREEZE.md`. Fidelity: `docs/STAGE_87_FIDELITY.md`.

**Stage 88 open (2026-08-11):** House Lifecycle & Staff Security Ops track approved — `docs/ADR_182_STAGE88_OPEN.md` + `docs/STAGE_88_PLAN.md` (Tenant Lifecycle Controls → Tenant Roster Export & At-Risk Queue → Platform Staff Invite & Session Ops → House Lifecycle & Staff Security Ops; L1 next).

**Stage 88 L1 (2026-08-11):** Tenant lifecycle controls — `PATCH /platform/tenants/{id}/lifecycle` + suspend reason (`test_platform_tenant_lifecycle_l1.py`).

**Stage 88 R1 (2026-08-11):** Tenant roster export + at-risk queue — `GET /platform/tenants/export` / `GET /platform/tenants/at-risk` (`test_platform_tenant_roster_r1.py`).

**Stage 88 S1 (2026-08-11):** Platform staff invite + session ops — email invite + `GET/DELETE /platform/users/sessions` (`test_platform_staff_security_s1.py`).

**Stage 88 D1 (2026-08-11):** House Lifecycle & Staff Security Ops fidelity sync — `docs/STAGE_88_FIDELITY.md` (`test_stage88_fidelity_d1.py`); maps L1–S1 → readiness / launch / deploy / security.

**Stage 88 exit (2026-08-11):** L1, R1, S1, D1, H88x met — `docs/STAGE_88_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_183_STAGE88_FREEZE.md`. Fidelity: `docs/STAGE_88_FIDELITY.md`.

**Stage 89 open (2026-08-11):** House Customer Assist & Roster Intelligence Ops track approved — `docs/ADR_184_STAGE89_OPEN.md` + `docs/STAGE_89_PLAN.md` (House Tenant Admin Assist → Tenant Roster Filters & Dashboard At-Risk KPIs → Plan Catalog & Billing Roster Depth → House Customer Assist & Roster Intelligence Ops; A1 next).

**Stage 89 A1 (2026-08-11):** House Tenant Admin assist — `POST /platform/tenants/{id}/admin/password-reset-email` / `…/admin/resend-verification` (`test_platform_tenant_admin_assist_a1.py`).

**Stage 89 F1 (2026-08-11):** Roster filters + dashboard at-risk KPIs — `plan_code`/`industry` filters + `at_risk_count` (`test_platform_roster_intel_f1.py`).

**Stage 89 C1 (2026-08-11):** Plan catalog + billing roster depth — metadata catalog + trial_ends deep-links (`test_platform_catalog_billing_c1.py`).

**Stage 89 D1 (2026-08-11):** House Customer Assist & Roster Intelligence Ops fidelity sync — `docs/STAGE_89_FIDELITY.md` (`test_stage89_fidelity_d1.py`); maps A1–C1 → readiness / launch / deploy / security.

**Stage 89 exit (2026-08-11):** A1, F1, C1, D1, H89x met — `docs/STAGE_89_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_185_STAGE89_FREEZE.md`. Fidelity: `docs/STAGE_89_FIDELITY.md`.

**Stage 90 open (2026-08-11):** House Operator Visibility & Delivery Ops track approved — `docs/ADR_186_STAGE90_OPEN.md` + `docs/STAGE_90_PLAN.md` (House Email Delivery Visibility → Operator Contact / Security / Runbook Surfaces → Roster Findability & Plan Context → House Operator Visibility & Delivery Ops; E1 next).

**Stage 90 E1 (2026-08-11):** House email delivery visibility — `platform.email.delivery` + `delivery_only` (`test_platform_email_delivery_visibility_e1.py`).

**Stage 90 O1 (2026-08-11):** Operator surfaces — Health contacts/security + Settings runbook links (`test_house_operator_surfaces_o1.py`).

**Stage 90 Q1 (2026-08-11):** Roster findability + plan context — admin email search + detail soft limits (`test_platform_roster_findability_q1.py`).

**Stage 90 D1 (2026-08-11):** House Operator Visibility & Delivery Ops fidelity sync — `docs/STAGE_90_FIDELITY.md` (`test_stage90_fidelity_d1.py`); maps E1–Q1 → readiness / launch / deploy / security.

**Stage 90 exit (2026-08-11):** E1, O1, Q1, D1, H90x met — `docs/STAGE_90_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_187_STAGE90_FREEZE.md`. Fidelity: `docs/STAGE_90_FIDELITY.md`.

**Stage 91 open (2026-08-11):** House Operator Investigation & Evidence Ops track approved — `docs/ADR_188_STAGE91_OPEN.md` + `docs/STAGE_91_PLAN.md` (Audit/Activity Date-Range Investigation → Dashboard→Roster Deep-Links & Tenant Delivery Context → Staff Presence / Health Required Badges / House TZ + Operator Evidence Export → House Operator Investigation & Evidence Ops; I1 next).

**Stage 91 I1 (2026-08-11):** Audit/Activity date-range investigation — `from_date`/`to_date` + Activity 7d default (`test_platform_audit_investigation_i1.py`).

**Stage 91 N1 (2026-08-11):** Dashboard→roster deep-links + tenant last House email delivery (`test_platform_nav_delivery_n1.py`).

**Stage 91 P1 (2026-08-11):** Staff presence, health required badges, House TZ, `GET /platform/evidence` (`test_house_posture_evidence_p1.py`).

**Stage 91 D1 (2026-08-11):** House Operator Investigation & Evidence Ops fidelity sync — `docs/STAGE_91_FIDELITY.md` (`test_stage91_fidelity_d1.py`); maps I1–P1 → readiness / launch / deploy / security.

**Stage 91 exit (2026-08-11):** I1, N1, P1, D1, H91x met — `docs/STAGE_91_EXIT_CRITERIA.md`. Scope freeze: `docs/ADR_189_STAGE91_FREEZE.md`. Fidelity: `docs/STAGE_91_FIDELITY.md`.
