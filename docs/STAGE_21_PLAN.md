# Stage 21 Plan — Tenant Lifecycle, Org & Dashboard Fidelity

**Status:** Open  
**Base:** Tenant lifecycle → Org & administration → Identity shell → Executive dashboard → Fidelity closeout  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-047](ADR_047_STAGE21_OPEN.md)

Stage 21 closes commercial-MVP foundation fidelity after Stage 20 freeze. Tenant registration/lifecycle, org units, users/roles, executive dashboard, and notifications engines already exist (Stage 1 / 18 / 19). This track proves BR-1–4 with live evidence and docs sync — **not** paid billing, schema-per-tenant, i18n packs, K8s/WAL/PITR, Grafana, certified 1000-VU, or reopening Stages 1–20.

## Product outline (owner)

```
Tenant lifecycle
 ├── Registration · profile · trial/grace (BR-1.1–1.3)
 └── Isolation · seed provisioning (BR-1.4–1.5)

Org & administration
 ├── Branches · stores · warehouses · departments (BR-2.2–2.5)
 └── Company · currency · tax config (BR-2.1, 2.6, 2.8)

Identity shell
 └── Users · roles · permissions sync (BR-3)

Executive dashboard
 ├── KPIs · inventory alerts · sales viz (BR-4.1–4.3)
 └── Notifications panel (BR-4.4)

Fidelity closeout
 ├── Docs / BR-1–4 / readiness / launch §§1–2 sync
 └── Exit + freeze
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven tenant / org / users / dashboard / notification engines — do not rewrite stacks or invent fake success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–20 feature scopes. BR-2.7 multi-language packs remain ADR-006 deferred; English + i18n scaffold only. ADR-001 shared-schema + `tenant_id` remains MVP isolation.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **T1** | Tenant registration & lifecycle (BR-1.1–1.3) | P0 | COMPLETE |
| **I1** | Isolation & tenant init seeds (BR-1.4–1.5) | P0 | COMPLETE |
| **O1** | Org units fidelity (BR-2.2–2.5) | P0 | COMPLETE |
| **C1** | Company / currency / tax setup (BR-2.1, 2.6, 2.8) | P1 | COMPLETE |
| **U1** | Users & roles fidelity (BR-3) | P1 | COMPLETE |
| **V1** | Dashboard KPIs & visualizations (BR-4.1–4.3) | P1 | PENDING |
| **N1** | Dashboard notifications panel (BR-4.4) | P1 | PENDING |
| **D1** | Spec / BR-1–4 / readiness / launch §§1–2 fidelity sync | P2 | PENDING |
| **H21x** | Stage 21 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- External LLM / Prophet / IsolationForest vendor model upgrades
- PO OCR auto-apply (expense/PI OCR remains Stage 10)
- Kubernetes / Helm production chart; GHA → staging K8s deploy
- Full Prometheus / Grafana / PagerDuty stack; centralized SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU capacity certificate; vendor penetration test / ZAP-in-CI Top 10
- Multi-bin; FIFO/LIFO/WA
- WebSocket realtime notifications; Open Banking; tax e-file portals
- Richer WYSIWYG template designer
- Reopening Stages 1–20 frozen feature scopes

## T1 acceptance criteria

- [x] Tenant register (company/email/password/industry), email uniqueness, trial default, verification path proven.
- [x] Company profile + subscription statuses (Trial/Active/Suspended) + grace/read-only where already implemented proven.
- [x] Automated proof: `backend/tests/test_tenant_lifecycle_t1.py`.
- [x] BR-1.1–1.3 synced with evidence.

## I1 acceptance criteria

- [x] Cross-tenant isolation + API tenant context validation proven (shared-schema `tenant_id`; not separate DBs).
- [x] Registration/init seeds COA / tax / UoM / expense categories proven.
- [x] Tenant-scoped backup path regression where applicable.
- [x] Automated proof: `backend/tests/test_tenant_isolation_seeds_i1.py`.
- [x] BR-1.4–1.5 synced with evidence (ADR-001 honesty on isolation model).

## O1 acceptance criteria

- [x] Branches / stores / warehouses / departments CRUD + deactivate-without-loss + manager/hours/type attrs proven.
- [x] Automated proof: `backend/tests/test_org_units_o1.py`.
- [x] BR-2.2–2.5 synced with evidence.

## C1 acceptance criteria

- [x] Company legal/tax/multi-address/contact + currency/FX + tax rates/default/category applicability proven.
- [x] Automated proof: `backend/tests/test_company_currency_tax_c1.py`.
- [x] BR-2.1 / 2.6 / 2.8 synced with evidence (BR-2.7 deferred packs remain ADR-006).

## U1 acceptance criteria

- [x] User CRUD/import/activate + predefined/custom roles + permission inheritance/override (where implemented) proven.
- [x] Automated proof: `backend/tests/test_users_roles_u1.py`.
- [x] BR-3 synced with evidence (ADR-003/005 deferred items remain deferred).

## V1 acceptance criteria

- [ ] KPI cards, MoM/period compare, low/OOS/expiring alerts, recent sales / top products / revenue charts proven.
- [ ] Automated proof: `backend/tests/test_dashboard_kpis_v1.py`.
- [ ] BR-4.1–4.3 synced with evidence.

## N1 acceptance criteria

- [ ] Unread count, categorized groups, mark read/unread, 90-day history panel proven.
- [ ] Automated proof: `backend/tests/test_dashboard_notifications_n1.py`.
- [ ] BR-4.4 synced with evidence.

## D1 acceptance criteria

- [ ] BR-1–4, tenancy readiness, USER_MANUAL / API / launch §§1–2 aligned — `docs/STAGE_21_FIDELITY.md`.
- [ ] Guard test: `backend/tests/test_stage21_fidelity_d1.py`.

## H21x acceptance criteria

See workstream table; filled when exit workstream starts.

## Sign-off

T1–U1 complete. Pending V1 → H21x. Stages 1–20 remain frozen for their scopes.
