# Stage 29 Exit Criteria

**Status:** Met for Operator Hardening & Production Cutover Fidelity workstreams V1, B2, T1, X1, D1, H29x (2026-08-11)  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Freeze:** [ADR-064](ADR_064_STAGE29_FREEZE.md)  
**Plan:** [STAGE_29_PLAN.md](STAGE_29_PLAN.md)  
**Fidelity:** [STAGE_29_FIDELITY.md](STAGE_29_FIDELITY.md)  
**Open ADR (historical):** [ADR-063](ADR_063_STAGE29_OPEN.md)

Stage 29 exit closes the vendor pen-test/ZAP pack → PgBouncer soak → cert-manager/TLS → production cutover → fidelity closeout track after Stage 28 freeze. It is **not** a claim that purchased vendor pen-test certificates, live ZAP-against-staging, live PgBouncer soak / default Helm pooler, live Let’s Encrypt issuance, live production cutover via main `ci.yml`, forged production §7 sign-off, hosted Grafana/PagerDuty/SIEM as SaaS Complete, live PITR/1000-VU/GHA apply execution, paid billing, schema-per-tenant, i18n packs, hard-delete archival, user↔store membership, Open Banking, tax e-file portals, external LLM/Prophet, or reopening Stages 1–28 are Complete.

## Workstream checklist

| ID | Workstream | Verdict | Evidence |
|----|------------|---------|----------|
| V1 | Vendor pen-test / ZAP staging packaging | COMPLETE | `test_pentest_pack_v1.py` |
| B2 | PgBouncer soak / Helm pooler packaging | COMPLETE | `test_pgbouncer_soak_b2.py` |
| T1 | Cert-manager / TLS ingress packaging | COMPLETE | `test_tls_ingress_t1.py` |
| X1 | Production cutover pack (LAUNCH §§1–3 / §7) | COMPLETE | `test_cutover_pack_x1.py` |
| D1 | Spec / readiness / deploy / launch / security fidelity | COMPLETE | `STAGE_29_FIDELITY.md`; `test_stage29_fidelity_d1.py` |
| H29x | Exit criteria + freeze ADR | COMPLETE | This document + ADR-064; `test_stage29_exit_h29x.py` |

Readiness honesty for pen-test engagement, PgBouncer soak/pooler, TLS ingress examples, and cutover harness remains **Complete (MVP)** with Remaining documented in `PRODUCTION_READINESS.md` and `docs/STAGE_29_FIDELITY.md`. Main `ci.yml` stays deploy-free (**Stage 18 C1**). Purchased vendor certs / live soak / ACME / cutover / §7 remain Remaining until operators record real runs outside CI.

## Explicitly deferred (not Stage 29 blockers)

- Purchased vendor penetration test certificate; live ZAP-in-CI against authenticated staging
- Live PgBouncer soak numbers; in-cluster Helm PgBouncer as default data plane
- Live Let’s Encrypt issuance / production TLS cutover execution
- Live production cutover; forged / pre-filled production §7 sign-off
- Live GHA → staging cluster apply; hosted Grafana/PagerDuty/SIEM as SaaS Complete
- Live operator PITR / ~1000-VU execution (Stage 28 packs remain packaging-only)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish
- Vendor-specific USB/serial POS drivers
- Richer WYSIWYG template designer; restore-to-new-tenant
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–28 frozen feature scopes
- Items already deferred under Stage 1–28 ADRs
- Main `ci.yml` deploy jobs (Stage 18 C1 remains deploy-free)

## Sign-off rule

Stage 29 operator hardening & cutover exit is **met** when the table above has no CRITICAL/MISSING rows for V1–D1, H29x and ADR-064 is accepted. Broader commercial MVP readiness remains in `PRODUCTION_READINESS.md` (Remaining rows above stay post-MVP operator work outside this track). Stage 30+ requires an explicit open ADR after CONTINUE/NEXT.
