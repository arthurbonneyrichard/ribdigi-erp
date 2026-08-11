# Stage 24 Plan — Commerce & Ops Gate Fidelity

**Status:** Open  
**Base:** Commerce surface gate closure → Ops/AI gate honesty → Fidelity closeout  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-053](ADR_053_STAGE24_OPEN.md)

Stage 24 closes remaining commercial-MVP **readiness honesty** for Inventory, Purchasing, Sales, POS, Multi-store, Redis/Celery intended workloads, and AI functions after Stage 23 freeze. Engines and fidelity proofs already exist (Stages 11–20). This track flips gates to Complete (MVP) where Remaining is deferred-only, proves shared document-numbering series coverage, and syncs docs — **not** paid billing, schema-per-tenant, i18n packs, ADR-005 multi-bin staff membership, Open Banking, tax e-file, K8s/WAL/PITR, Grafana, certified 1000-VU, vendor USB/serial drivers, PO Kanban polish, external LLM/Prophet, or reopening Stages 1–23.

## Product outline (owner)

```
Commerce surface gate closure
 ├── Shared document numbering series evidence (order / return / CN / PO / GRN)
 ├── Inventory · Purchasing Complete (MVP) — Remaining Kanban polish
 ├── Sales · POS Complete (MVP) — Remaining vendor USB/serial drivers
 └── Multi-store Complete (MVP) — Remaining multi-bin + ADR-005

Ops / AI gate honesty
 ├── Redis / Celery / RabbitMQ intended workloads Complete (MVP)
 └── AI functions Complete (MVP) — Remaining LLM / Prophet / PO OCR apply

Fidelity closeout
 ├── Docs / readiness / USER_MANUAL / launch sync
 └── Exit + freeze
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven numbering / readiness / AI engines — do not rewrite stacks or invent fake success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–23 feature scopes. Deferred ADRs (001–006) and ops platforms (K8s/WAL/Grafana/1000-VU) stay deferred.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **N1** | Shared document numbering series fidelity | P0 | COMPLETE |
| **G1** | Commerce gates closure (Inv / Purch / Sales / POS / Multi-store) | P0 | COMPLETE |
| **O1** | Ops Redis/Celery + AI MVP gate honesty | P1 | PENDING |
| **D1** | Spec / readiness / USER_MANUAL / API fidelity sync | P2 | PENDING |
| **H24x** | Stage 24 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Kubernetes / Helm; Grafana / PagerDuty / SIEM
- pg_dump / WAL / S3 offsite PITR; PgBouncer
- Certified ~1000-VU; vendor penetration test / ZAP-in-CI Top 10
- Multi-bin locations; FIFO/LIFO/WA
- PO Kanban optional polish; percentage discount UI polish
- Vendor-specific USB/serial POS drivers beyond TCP ESC/POS / browser bridge
- External LLM provider; Prophet/ML upgrades; PO OCR auto-apply
- Richer WYSIWYG template designer; restore-to-new-tenant
- Reopening Stages 1–23 frozen feature scopes

## N1 acceptance criteria

- [x] `document_numbering` configure + preview covers all `DOC_KEYS` (invoice / PI / PO / GRN / quote / order / return / credit note / purchase return / debit note).
- [x] Live allocation honors configured prefixes for quotation, sales order, sales invoice, sales return, credit note, PO, GRN.
- [x] Unknown document type rejected by numbering merge (`400`).
- [x] Automated proof: `backend/tests/test_document_numbering_n1.py`.
- [x] BR-20.4 / launch / roadmap / readiness Sales Remaining cite Stage 24 N1.

## G1 acceptance criteria

- [x] Inventory gate Complete (MVP); Remaining multi-bin + PO Kanban polish only.
- [x] Purchasing gate Complete (MVP); Remaining PO Kanban polish only.
- [x] Sales gate Complete (MVP); Remaining percentage discount UI polish only.
- [x] POS gate Complete (MVP); Remaining vendor USB/serial drivers only.
- [x] Multi-store gate Complete (MVP); Remaining multi-bin + ADR-005 only.
- [x] No fake-complete of Redis/Celery, AI provider, WAL, K8s, monitoring, or load gates (O1 / post-MVP).
- [x] Automated proof: `backend/tests/test_commerce_gate_closure_g1.py`.
- [x] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / plan synced (Stage 24 G1).

## O1–H24x acceptance criteria

Filled when each workstream starts.

## Sign-off

Plan authored; ADR-053 open. N1–G1 complete; O1 next. Stages 1–23 remain frozen for their scopes.
