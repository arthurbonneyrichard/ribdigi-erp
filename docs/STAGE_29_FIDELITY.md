# Stage 29 Fidelity Notes — Operator Hardening & Production Cutover Fidelity

**Status:** Open with Stage 29 D1; H29x next (ADR-063)  
**Surface:** Vendor pen-test/ZAP → PgBouncer soak → Cert-manager/TLS → Production cutover → Fidelity closeout  
**Open ADR:** [ADR-063](ADR_063_STAGE29_OPEN.md)  
**Plan:** [STAGE_29_PLAN.md](STAGE_29_PLAN.md)

Stage 29 proves the owner product outline after Stage 28 freeze — Vendor Pen-Test / ZAP Staging Pack + PgBouncer Soak / Helm Pooler Pack + Cert-manager / TLS Ingress Pack + Production Cutover Pack → Operator Hardening & Production Cutover Fidelity — by extending proven Stage 26/27/28 assets. It is **not** paid billing (ADR-002), schema-per-tenant (ADR-001), i18n packs (ADR-006), user↔store membership (ADR-005), hard-delete archival (ADR-003), Open Banking, tax e-file portals, claiming hosted Grafana/PagerDuty/SIEM as SaaS Complete, live production cutover via main `ci.yml`, purchased vendor pen-test certificates, green live soak / ACME issuance, forged production §7 sign-off, re-packaging Stage 28 R1/G1/A1/C1 packs as new Complete, external LLM/Prophet, or reopening Stages 1–28.

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| Vendor pen-test / ZAP staging | OWASP baseline + ZAP template (Stage 27 S1); purchase Remaining | Stage 29 V1 engagement pack Complete (MVP) — packaging; purchased cert / live ZAP Remaining |
| PgBouncer soak / Helm pooler | Packaging only (Stage 27 P1); soak Remaining | Stage 29 B2 soak / optional pooler pack Complete (MVP) — packaging; live soak / default Helm Remaining |
| Cert-manager / TLS ingress | Helm Ingress paths (Stage 26 K1); ACME Remaining | Stage 29 T1 ClusterIssuer + Ingress TLS pack Complete (MVP) — packaging; live issuance Remaining |
| Production cutover / §7 | Launch cert map (Stage 27 L1) + staging GHA (Stage 28 G1); cutover Remaining | Stage 29 X1 cutover / rollback / secrets harness Complete (MVP) — not forged §7 |
| Spec / readiness / deploy / launch / security | Workstream docs synced piecemeal | This note + `test_stage29_fidelity_d1.py` |

## Workstream → evidence → BR / gate → remaining

| WS | Evidence | BR / gate mapping | Remaining |
|----|----------|-------------------|-----------|
| **V1** | `test_pentest_pack_v1.py` — `PENTEST_PACK_MVP.md`, `pentest-engagement-checklist.json` | OWASP/security gate | Purchased cert; live ZAP staging |
| **B2** | `test_pgbouncer_soak_b2.py` — `PGBOUNCER_SOAK_PACK_MVP.md`, soak checklist | NFR pool / load adjacency | Live soak; default Helm pooler |
| **T1** | `test_tls_ingress_t1.py` — `TLS_INGRESS_PACK_MVP.md`, issuer/Ingress examples | K8s deploy gate | Live ACME / TLS cutover |
| **X1** | `test_cutover_pack_x1.py` — `CUTOVER_PACK_MVP.md`, cutover checklist + prod GHA | Launch §§1–3 / §7; K8s / Stage 18 C1 | Live cutover; §7 Name/Date |
| **D1** | This note + `test_stage29_fidelity_d1.py` | BR-16 + readiness + deploy / launch / security | — |
| **H29x** | `STAGE_29_EXIT_CRITERIA.md`; ADR-064; `test_stage29_exit_h29x.py` | Stage 29 exit + freeze | Next track needs open ADR |

## Evidence tests

- `backend/tests/test_pentest_pack_v1.py`
- `backend/tests/test_pgbouncer_soak_b2.py`
- `backend/tests/test_tls_ingress_t1.py`
- `backend/tests/test_cutover_pack_x1.py`
- `backend/tests/test_stage29_open.py`
- `backend/tests/test_stage29_fidelity_d1.py`

## Spec sync targets

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md` — BR-16 fidelity (+ Stage 29 V1–X1 / D1 cite)
- `docs/API_DOCUMENTATION.md` — Stage 29 V1–X1 / D1 cite
- `PRODUCTION_READINESS.md` — OWASP / PgBouncer / K8s / launch Completes + Stage 29 D1 cite
- `docs/DEVELOPMENT_ROADMAP.md` — Stage 29 D1
- `docs/LAUNCH_CHECKLIST.md` — V1–X1 / D1 evidence
- `docs/DEPLOYMENT_GUIDE.md` — Stage 29 B2 / T1 / X1 / D1
- `docs/SECURITY_GUIDE.md` — Stage 29 V1–X1 / D1 cite
- `docs/PENTEST_PACK_MVP.md` · `docs/PGBOUNCER_SOAK_PACK_MVP.md` · `docs/TLS_INGRESS_PACK_MVP.md` · `docs/CUTOVER_PACK_MVP.md`
- `docs/STAGE_29_PLAN.md` — D1 complete; H29x next
- `docs/ADR_063_STAGE29_OPEN.md`

## Deferred (not Stage 29 blockers)

- Purchased vendor penetration test certificate; live ZAP-in-CI against authenticated staging
- Live PgBouncer soak numbers; in-cluster Helm PgBouncer as default data plane
- Live Let’s Encrypt issuance / production TLS cutover execution
- Live production cutover; forged / pre-filled production §7 sign-off
- Live GHA → staging cluster apply; hosted Grafana/PagerDuty/SIEM as SaaS Complete
- Live operator PITR / ~1000-VU execution (Stage 28 packs remain packaging-only)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–28 frozen feature scopes
- Main `ci.yml` deploy jobs (Stage 18 C1 remains deploy-free)
