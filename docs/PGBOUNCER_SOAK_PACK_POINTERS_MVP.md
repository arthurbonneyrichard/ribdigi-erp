# PgBouncer Soak Pack Pointers MVP — Stage 208 P1

**Status:** Complete (MVP packaging) — Stage 208 P1  
**Evidence:** `backend/tests/test_stage208_pointers_p1.py`  
**Register:** `ops/mvp/pgbouncer-soak-pack-pointers.json`  
**Related:** [PGBOUNCER_SOAK_REMAINING_GATE_MVP.md](PGBOUNCER_SOAK_REMAINING_GATE_MVP.md) · [PGBOUNCER_SOAK_PACK_MVP.md](PGBOUNCER_SOAK_PACK_MVP.md) · [TLS_INGRESS_REMAINING_GATE_MVP.md](TLS_INGRESS_REMAINING_GATE_MVP.md) · [STAGE_208_PLAN.md](STAGE_208_PLAN.md)

Pointers into Stage 29 B2 PgBouncer soak pack, checklist/evidence schema, and Stage 207 TLS ingress remaining-gate adjacency. Every pointer keeps live soak non-claimed.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `live_soak_executed` | **false** |
| `helm_pooler_default_claimed` | **false** |
| `go_live_claimed` | **false** |
| `live_tls_ingress_claimed` | **false** |

## Pack pointers

| Gate theme | Primary docs |
|------------|--------------|
| Stage 29 B2 soak pack | `PGBOUNCER_SOAK_PACK_MVP.md` / `ops/postgres/pgbouncer-soak-checklist.json` |
| Soak evidence schema | `ops/postgres/soak-evidence.example.json` |
| Optional Deployment snippet | `ops/postgres/pgbouncer-deployment.example.yaml` |
| Stage 207 TLS ingress remaining-gate | `TLS_INGRESS_REMAINING_GATE_MVP.md` (orthogonal) |
| Production readiness | `PRODUCTION_READINESS.md` |

## Explicit non-claim

1. Stage 29 B2 packaging Completes are **not** live PgBouncer soak Complete.
2. Checklist / evidence schema are **not** live soak certificates.
3. Do not claim default Helm pooler from this index.
4. Do not claim live soak Complete from this pointer index.
5. Distinct from Stage 207 TLS ingress remaining-gate.

## Explicitly not claimed

- Live PgBouncer soak Completes
- Go-live Completes
