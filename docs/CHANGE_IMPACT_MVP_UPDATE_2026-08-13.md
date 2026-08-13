# Change-Impact Audit — Updated Commercial MVP Prompt (2026-08-13)

**Status:** Accepted baseline for Stage 162+  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP v1.0  
**Tip at audit:** Stage 161 freeze ADR-329 (`989739c`)  
**Rule:** Do not restart the project. Preserve working engines. Extend / refactor only where required.

## Executive summary

Most core tenant ERP engines (inventory, stock, sales, POS online, purchasing, accounting, reports, backup, platform console) are **COMPLETE** for MVP honesty. The updated prompt’s largest **new** gap is **Offline-first / PWA / Sync** (greenfield). The largest **refactor** is **tenant navigation IA** (Stage 95 Commerce/Operations flat sections → approved expandable parents). Deferred ADRs (002/003/005) and honesty flags remain **false** — do not claim Complete.

---

## What is preserved (do not rebuild)

| Area | Status | Notes |
|------|--------|-------|
| Platform vs Tenant separation | COMPLETE | `/platform/*` + `PlatformShell`; tenant `Shell` |
| Auth / RBAC module+action | COMPLETE | Soft-delete users (ADR-003) |
| Role-aware dashboards | COMPLETE | Cashier / store_manager / executive filters |
| Inventory / Stock engines | COMPLETE | Tabs + APIs; transfers/counts/movements |
| Sales / Purchasing / Credit | COMPLETE | Real AR/AP + journals |
| Online POS | COMPLETE | Sessions, tenders, receipts, barcode/QR |
| Accounting reports + path CSVs | COMPLETE | Stages 159–161 path exports |
| Backup `.ribbak` | COMPLETE | No fake success |
| Docker / Redis / RabbitMQ / Celery | COMPLETE | Main `ci.yml` deploy-free |
| Stages 1–161 freezes | IN FORCE | Bugfix/doc only unless superseding ADR |

---

## Impact matrix (updated prompt → current state)

| Updated requirement | Current | Verdict | Files / surface | DB | API | Frontend | Security | Recommended action |
|---------------------|---------|---------|-----------------|----|-----|----------|----------|--------------------|
| Platform Owner dashboard KPIs | Real tenant/lifecycle KPIs; MRR null | COMPLETE (honest) | `platform/dashboard`, `platform_api.py` | — | — | — | Tenant isolation OK | Keep; never fabricate MRR |
| Platform tenant mgmt | List/activate/suspend | COMPLETE | `platform/tenants` | — | — | — | OK | Keep |
| Tenant RBAC + custom roles | Module/action model | COMPLETE | `rbac.py`, `/roles` | — | — | admin pages | OK | Keep; do not rename to `products.view` without migration plan |
| User suspend/archive | `is_active` only | PARTIAL | `users`, ADR-003 | Maybe later | Extend | Users UI | Soft-delete only | Defer archive/hard-delete (ADR-003) |
| User↔store/warehouse assign | Branch/dept + manager_id | MISSING | ADR-005 | Yes if opened | Yes | Users/Stores | Critical tenancy | Defer per ADR-005 or open dedicated stage |
| Tenant nav parents (§37) | Stage 95 Commerce/Ops flat | REQUIRES REFACTOR | `Shell.tsx` | No | No | Shell only | Menu gating unchanged | **Stage 162 N1** |
| Role-aware dashboards | Implemented | COMPLETE | `dashboard_views.py` | — | — | dashboard | Backend enforced | Keep |
| Inventory / Stock / Sales / Purchase | Engines + UI | COMPLETE | module pages | — | — | — | OK | Keep; nav regroup only |
| POS Hold/Resume | Stage 165 H1 Partial / Stage 166 S1 soft reserve | PARTIAL | `pos_held_carts` + `reserved_qty` | Yes | — | POS | Soft reserve optional; not Offline Complete | Offline Complete later |
| Billers CRUD | Alias to salesperson report | PARTIAL | Shell link | Yes if CRUD | Yes | People | — | Defer (honesty) |
| Parallel Income module | P&L alias | PARTIAL | Accounting | — | — | — | — | Defer |
| Finance reports path CSVs | Stages 160–161 | COMPLETE | `finance_ops_export.py` | — | — | Reports/Accounting | RBAC | Keep |
| Offline / PWA / Sync | Stage 163–165 | PARTIAL | PWA+queue+IDB+Hold | Yes | Yes | PWA+POS | Device/tenant checks | Client queue+Partial Hold; Offline Complete **166+** |
| Device registration | Stage 163 V1 | COMPLETE (MVP) | `offline_devices` | Yes | — | Settings | Soft revoke | Keep |
| Sync APIs `/sync/*` | Stage 164 Q1–C1 | COMPLETE (MVP) | `sync_engine.py` | Yes | — | — | Idempotency | Keep; conflict resolve UX later |
| Connectivity status UI | Stage 163 C1 | COMPLETE (MVP) | Shell | No | No | Chrome | — | Keep |
| Idempotency offline txs | Stage 164 I1 | COMPLETE (MVP) | `client_request_id` | Yes | — | POS/sync | Unique per tenant | Keep |
| Idempotency offline txs | None | MISSING | POS schemas | Unique constraints | Yes | Queue | Critical | With sync push |
| Backup / VPS | Complete packaging | COMPLETE | backup, helm/compose | — | — | — | Secrets | Keep |
| Paid billing | Deferred ADR-002 | MISSING (honest) | platform billing | — | — | — | — | Keep deferred; flags false |

---

## New requirements that affect completed work

1. **Navigation IA (§37)** — supersedes Stage 95 section labels; must not duplicate pages; preserve deep-links and RBAC menu gating. Stage 95 shell tests need amendment under Stage 162.
2. **Offline/PWA (§13–30)** — does **not** replace online POS; extends it. Do not weaken online transactional integrity.
3. **Permission naming (`products.view`)** — current model is `inventory`+`read`; mapping/aliases only if required — do not break existing grants.
4. **User store assignment (§7)** — conflicts with ADR-005 deferral; open only via explicit ADR amendment.
5. **Hold/Resume** — previously deferred; may land with offline cart queue.

---

## Safest incremental plan (mapped to UPDATE stages)

| Priority | Update stage | Incremental Stage | Focus |
|----------|--------------|-------------------|-------|
| P0 now | UI §37 + Update 1 polish | **162** | Approved expandable navigation hierarchy |
| P0 next | Update 8 start | **163** | Offline honesty ADR + PWA shell + connectivity chrome + device model skeleton |
| P0 | Update 8 | **164+** | Sync queue client + `/sync/*` + idempotent POS push |
| P1 | Update 7 residual | later | POS Hold/Resume (online + offline) |
| P1 | Update 4 residual | later | Billers CRUD (if product still requires) |
| Deferred | ADR-002/003/005 | post-MVP or dedicated ADR open | Billing / hard-delete / membership |

---

## Honesty flags (must remain false)

`mrr_fabricated_claimed`, `billing_complete_claimed`, `subscriptions_live_claimed`, `user_store_membership_claimed`, `hard_delete_claimed`, `sections_1_3_verified`, `section_7_signed`, `go_live_claimed`, `attestation_claimed`.

Do **not** claim Offline Complete until sync + idempotency + conflict tests pass end-to-end.

---

## Stage 162 decision (opened from this audit)

**Tenant MVP Approved Navigation Hierarchy Fidelity** — expand/collapse parents matching §37; no new duplicate modules; all existing hrefs preserved; Offline remains MISSING until Stage 163+.

## Stage 163 decision (opened after Stage 162 freeze)

**Tenant MVP Offline Foundation Fidelity** — PWA shell + connectivity chrome + device registration + `/sync/status` honesty. Sync push/pull/conflicts and offline sales remain Stage 164+. Do not claim Offline Complete.

## Stage 164 decision (opened after Stage 163 freeze)

**Tenant MVP Sync Queue + Idempotent Offline POS Fidelity** — real queue tables, push/pull/ack/conflicts, `client_request_id` idempotency. Hold/Resume and Offline Complete remain Stage 165+.

## Stage 165 decision (opened after Stage 164 freeze)

**Tenant MVP Offline Client Queue + Hold/Resume + Conflict Resolve Fidelity** — IndexedDB queue, Partial Hold/Resume (no stock reserve), conflict resolve without silent re-apply. Offline Complete remains Stage 166+.

## Stage 166 decision (opened after Stage 165 freeze)

**Offline Complete Hardening Fidelity** — stock-safe offline catalog cache (C1), accept_client safe re-apply (A1), Hold soft `product.reserved_qty` reserve (S1). Offline Complete remains deferred (Stage 167+).

## Stage 167 decision (opened after Stage 166 freeze)

**Offline Complete E2E Hardening Fidelity** — catalog TTL/refresh (T1), conflict re-apply UX polish (U1), Hold soft-reserve expiry/cleanup (E1). Offline Complete remains deferred (Stage 168+).

## Stage 168 decision (opened after Stage 167 freeze)

**Offline Complete Attestation Fidelity** — SW static-cache contract (W1), offline sale/flush API attestation (F1), device revoke mid-queue honesty (R1). Offline Complete product claim remains deferred (Stage 169+).

## Stage 169 decision (opened after Stage 168 freeze)

**Tenant MVP Production Ops Hardening Fidelity** — backup restore drill honesty (B1), migration gate checklist (M1), offline/sync runbook (R1). Live DR / production migrate / Offline Complete / go-live remain deferred (Stage 170+).

## Stage 170 decision (opened after Stage 169 freeze)

**Tenant MVP Support Readiness Fidelity** — support readiness runbook (S1), incident severity matrix (V1), offline/sync escalation paths (E1). Live support SLA / PagerDuty / Offline Complete / go-live remain deferred (Stage 171+).

## Stage 171 decision (opened after Stage 170 freeze)

**Tenant MVP Knowledge Base Fidelity** — knowledge base hub (K1), FAQ offline/POS/Hold (F1), troubleshooting index with backup drill links (T1). Hosted FAQ SaaS / live training / Offline Complete / go-live remain deferred (Stage 172+).

## Stage 172 decision (opened after Stage 171 freeze)

**Tenant MVP Cashier Quickstart Fidelity** — quickstart hub (Q1), bind + catalog refresh (B1), Hold/flush/accept-client day-one ops (O1). Offline Complete / live training / go-live remain deferred (Stage 173+).

## Stage 173 decision (opened after Stage 172 freeze)

**Tenant MVP Store-Open Checklist Fidelity** — store-open hub (S1), store select + low-stock glance (L1), Hold expiry + device health + conflict queue (H1). Offline Complete / live training / go-live remain deferred (Stage 174+).

## Stage 174 decision (opened after Stage 173 freeze)

**Tenant MVP Store-Close Checklist Fidelity** — store-close hub (C1), Hold clear/expiry + sync queue drain (E1), conflict triage + catalog age + backup drill pointer (T1). Offline Complete / live DR / go-live remain deferred (Stage 175+).

## Stage 175 decision (opened after Stage 174 freeze)

**Tenant MVP Shift-Handover Checklist Fidelity** — handover hub (H1), shift snapshot Holds/sync/conflicts (S1), device bind + open/close pack pointers (P1). Offline Complete / live training / go-live remain deferred (Stage 176+).

## Stage 176 decision (opened after Stage 175 freeze)

**Tenant MVP Weekly POS Ops Review Fidelity** — weekly review hub (W1), open/close/handover adherence (A1), conflict backlog age + catalog TTL cadence + support escalation pointers (R1). Offline Complete / live SLA / go-live remain deferred (Stage 177+).

## Stage 177 decision (opened after Stage 176 freeze)

**Tenant MVP Monthly POS Ops Fidelity** — monthly rollup hub (M1), weekly outcomes + Hold trends (T1), device revoke/rebind + backup drill schedule + residual risk honesty pointers (P1). Offline Complete / live DR / go-live remain deferred (Stage 178+).

## Stage 178 decision (opened after Stage 177 freeze)

**Tenant MVP Quarterly POS Ops Fidelity** — quarterly hub (Q1), monthly outcomes rollup (R1), Offline Complete remaining + migration gate + support residual + go-live non-claim (G1). Offline Complete / live migration / go-live remain deferred (Stage 179+).

## Stage 179 decision (opened after Stage 178 freeze)

**Tenant MVP Offline Complete Remaining-Gate Index Fidelity** — remaining-gate index hub (I1), blocker matrix (B1), Stages 166–169 pack pointers with explicit non-claim (P1). Offline Complete / go-live remain deferred (Stage 180+).
## Stage 180 decision (opened after Stage 179 freeze)

**Tenant MVP Go-Live Remaining-Gate Index Fidelity** — go-live remaining-gate hub (G1), blocker matrix (B1), LAUNCH / Offline Complete / ADR-002 pointers with explicit non-claim (P1). Go-live / Offline Complete / billing Completes remain deferred (Stage 181+).
## Stage 181 decision (opened after Stage 180 freeze)

**Tenant MVP Billing Remaining-Gate Index Fidelity** — billing remaining-gate hub (I1), blocker matrix (B1), ADR-002 / deferred honesty / commercial billing pointers with explicit non-claim (P1). Billing / payment provider / checkout Completes remain deferred (Stage 182+).
## Stage 182 decision (opened after Stage 181 freeze)

**Tenant MVP User↔Store Membership Remaining-Gate Index Fidelity** — membership remaining-gate hub (I1), blocker matrix (B1), ADR-005 / E2E users-RBAC / deferred ADR pointers with explicit non-claim (P1). Membership / `users.store_id` Completes remain deferred (Stage 183+).
## Stage 183 decision (opened after Stage 182 freeze)

**Tenant MVP Hard-Delete Remaining-Gate Index Fidelity** — hard-delete remaining-gate hub (I1), blocker matrix (B1), ADR-003 / erasure honesty / deferred ADR pointers with explicit non-claim (P1). Hard-delete / archival Completes remain deferred (Stage 184+).
## Stage 184 decision (opened after Stage 183 freeze)

**Tenant MVP Language/i18n Remaining-Gate Index Fidelity** — i18n remaining-gate hub (I1), blocker matrix (B1), ADR-006 / deferred ADR / scaffold pointers with explicit non-claim (P1). Multi-language / non-English packs Completes remain deferred (Stage 185+).
## Stage 185 decision (opened after Stage 184 freeze)

**Tenant MVP Schema-Per-Tenant Remaining-Gate Index Fidelity** — schema-per-tenant remaining-gate hub (I1), blocker matrix (B1), ADR-001 / deferred ADR / readiness pointers with explicit non-claim (P1). Schema-per-tenant / database-per-tenant Completes remain deferred (Stage 186+).
## Stage 186 decision (opened after Stage 185 freeze)

**Tenant MVP Audit-Retention Remaining-Gate Index Fidelity** — audit-retention remaining-gate hub (I1), blocker matrix (B1), ADR-007 / retention pointers with explicit non-claim (P1). Hot audit purge / physical delete Completes remain deferred (Stage 187+).
## Stage 187 decision (opened after Stage 186 freeze)

**Tenant MVP Attestation Remaining-Gate Index Fidelity** — attestation remaining-gate hub (I1), blocker matrix (B1), Stage 69 / LAUNCH pointers with explicit non-claim (P1). Attestation / §7 signed / go-live Completes remain deferred (Stage 188+).
## Stage 188 decision (opened after Stage 187 freeze)

**Tenant MVP Support-SLA Remaining-Gate Index Fidelity** — support-SLA remaining-gate hub (I1), blocker matrix (B1), Stage 36 / support readiness pointers with explicit non-claim (P1). Live support SLA / PagerDuty Completes remain deferred (Stage 189+).
## Stage 189 decision (opened after Stage 188 freeze)

**Tenant MVP Live-Training Remaining-Gate Index Fidelity** — live-training remaining-gate hub (I1), blocker matrix (B1), Stage 33 / Stage 48 / materials pointers with explicit non-claim (P1). Live training / attendance certification Completes remain deferred (Stage 190+).
## Stage 190 decision (opened after Stage 189 freeze)

**Tenant MVP Offline Materials Remaining-Gate Index Fidelity** — offline materials remaining-gate hub (I1), blocker matrix (B1), Stage 171–175 / Stage 179 pointers with explicit non-claim (P1). Offline Complete remains deferred (Stage 191+); distinct from Stage 179 Offline Complete remaining-gate.
## Stage 191 decision (opened after Stage 190 freeze)

**Tenant MVP Hosted FAQ SaaS Remaining-Gate Index Fidelity** — hosted FAQ SaaS remaining-gate hub (I1), blocker matrix (B1), Stage 171 KB/FAQ / Stage 190 pointers with explicit non-claim (P1). Hosted FAQ SaaS Completes remain deferred (Stage 192+).
## Stage 192 decision (opened after Stage 191 freeze)

**Tenant MVP Live DR Remaining-Gate Index Fidelity** — live DR remaining-gate hub (I1), blocker matrix (B1), Stage 169 / Stage 35 / Stage 191 pointers with explicit non-claim (P1). Live DR / live PITR Completes remain deferred (Stage 193+).
## Stage 193 decision (opened after Stage 192 freeze)

**Tenant MVP Live Migration Remaining-Gate Index Fidelity** — live migration remaining-gate hub (I1), blocker matrix (B1), Stage 169 / Stage 178 / Stage 192 pointers with explicit non-claim (P1). Live / production migrate Completes remain deferred (Stage 194+).
