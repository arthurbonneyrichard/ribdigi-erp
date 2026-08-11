# Stage 27 Plan — Commercial MVP Release Fidelity

**Status:** Open — B1 next (ADR-059)  
**Base:** Auto `.ribbak` Offsite + PgBouncer + Security Scan Evidence + Launch Certification → Release Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-059](ADR_059_STAGE27_OPEN.md)

Stage 27 closes the owner product outline after Stage 26 freeze: **Auto `.ribbak` Offsite Upload + PgBouncer Pooling Fidelity + Security Scan Evidence + Launch Certification Pack → Commercial MVP Release Fidelity**. Stage 26 delivered Complete (MVP) ops platform gates (monitoring, WAL/PITR strategy, Kubernetes/Helm, CI load capacity) with honest Remaining. This track extends proven Stage 5/18/23/26 assets (`create_backup`, `ops/backup/sync-ribbak-offsite.sh.example`, `docker-compose.prod.yml`, OWASP smoke suite, `docs/LAUNCH_CHECKLIST.md`) to close those Remaining items that can be evidenced without inventing hosted Grafana, vendor pen-test certificates, or live cluster apply success — **not** paid billing, schema-per-tenant, i18n packs, ADR-003/005, Open Banking, tax e-file, external LLM/Prophet, or reopening Stages 1–26.

## Product outline (owner)

```
Auto .ribbak Offsite Upload
        +
PgBouncer Pooling Fidelity
        +
Security Scan Evidence
        +
Launch Certification Pack
        ↓
Commercial MVP Release Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 5/18/23/26 ops patterns (logical backup, offsite sync script, Compose/prod env, OWASP suite, launch checklist) — do not invent fake Grafana/PagerDuty, vendor pen-test pass, or live GHA→staging success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–26 feature scopes. Deferred ADRs (001–006), hosted Grafana/SIEM, certified ~1000-VU soak, and live production cutover stay deferred unless explicitly in this plan.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **B1** | Automatic `.ribbak` offsite upload fidelity | P0 | COMPLETE |
| **P1** | PgBouncer connection pooling fidelity | P0 | COMPLETE |
| **S1** | Security scan / ZAP-in-CI baseline evidence | P0 | PENDING |
| **L1** | Launch certification pack (operator sign-off evidence) | P1 | PENDING |
| **D1** | Spec / readiness / launch / security / deploy fidelity sync | P2 | PENDING |
| **H27x** | Stage 27 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Hosted Grafana / Alertmanager → PagerDuty / SIEM as a managed service claim
- Live GHA → production cluster cutover (staging workflow evidence only if proven)
- Operator staging ~1000-VU / p95 < 500 ms certificate (extends Stage 26 C1 Remaining)
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish; vendor USB/serial POS drivers
- Richer WYSIWYG template designer; restore-to-new-tenant
- External LLM / Prophet / IsolationForest; PO OCR auto-apply
- Reopening Stages 1–26 frozen feature scopes

## B1 acceptance criteria

- [x] Automatic (or hook-driven) `.ribbak` offsite upload fidelity after `create_backup` — extend Stage 26 `ops/backup/` / backup service (not fake S3 success without evidence).
- [x] Failure path does not claim backup success when offsite upload fails (honest Remaining if opt-in only).
- [x] Automated proof: `backend/tests/test_backup_offsite_b1.py`.
- [x] PRODUCTION_READINESS / BR-16 honesty updated with evidence.
- [x] Plan / launch / roadmap cite Stage 27 B1.

## P1 acceptance criteria

- [x] PgBouncer pooling fidelity — versioned operator config + Compose/prod wiring docs (extend Stage 18 C1 — not invent in-cluster pooler claim).
- [x] App DATABASE_URL / pool guidance documented; no silent production misconfig.
- [x] Automated proof: `backend/tests/test_pgbouncer_p1.py`.
- [x] PRODUCTION_READINESS Redis/Celery Remaining honesty updated (PgBouncer Complete MVP or Partial with evidence).
- [x] Plan / launch / roadmap cite Stage 27 P1.

## S1 acceptance criteria

- [ ] Security scan baseline evidence in CI (extend OWASP smoke / optional ZAP baseline artifact — not fake vendor pen-test Complete).
- [ ] Durable artifact path under `/opt/cursor/artifacts/security/` (or equivalent).
- [ ] Automated proof: `backend/tests/test_security_scan_s1.py`.
- [ ] SECURITY_GUIDE / PRODUCTION_READINESS honesty updated (vendor pen test remains Remaining if not purchased).
- [ ] Plan / launch / roadmap cite Stage 27 S1.

## L1 acceptance criteria

- [ ] Launch certification pack — operator LAUNCH_CHECKLIST evidence packaging / automation hooks (extend `docs/LAUNCH_CHECKLIST.md` — not fake production sign-off).
- [ ] Durable artifact or checklist mapping for env / smoke / ops rows that can be proven in CI vs operator-only.
- [ ] Automated proof: `backend/tests/test_launch_cert_l1.py`.
- [ ] Plan / launch / roadmap cite Stage 27 L1.

## D1 acceptance criteria

- [ ] `docs/STAGE_27_FIDELITY.md` maps B1–L1 evidence → readiness / launch / security / deploy docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 27 D1.
- [ ] Automated proof: `backend/tests/test_stage27_fidelity_d1.py`.

## H27x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for B1–D1 / H27x — `docs/STAGE_27_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_060_STAGE27_FREEZE.md` (number reserved at close).
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage27_exit_h27x.py`.
- [ ] Stages 1–26 freezes remain; Stage 28+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 27 open under ADR-059. B1 / P1 complete; S1 next. Stages 1–26 remain frozen for their scopes.
