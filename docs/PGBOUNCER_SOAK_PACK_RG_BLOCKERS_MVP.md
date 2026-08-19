# PgBouncer Soak Pack RG Blockers MVP — Stage 317 B1

**Status:** Complete (MVP packaging) — Stage 317 B1  
**Evidence:** `backend/tests/test_stage317_blockers_b1.py`  
**Register:** `ops/mvp/pgbouncer-soak-pack-rg-blockers.json`  
**Related:** [PGBOUNCER_SOAK_PACK_REMAINING_GATE_MVP.md](PGBOUNCER_SOAK_PACK_REMAINING_GATE_MVP.md) · [PGBOUNCER_SOAK_PACK_MVP.md](PGBOUNCER_SOAK_PACK_MVP.md)

## Blockers

| ID | Surface | Status |
|----|---------|--------|
| live_soak_executed | Live soak executed Complete | REMAINING |
| helm_pooler_default_claimed | Helm pooler default Complete | REMAINING |
| managed_cloud_pooler_claimed | Managed cloud pooler Complete | REMAINING |
| live_tls_ingress_claimed | Live TLS ingress Complete | REMAINING |
| go_live_complete | Go-live | REMAINING |
| stage29_as_live_soak | Stage 29 B2 packaging as live soak Complete | NON_CLAIM |
| stage208_as_live_soak | Stage 208 PgBouncer soak remaining-gate as live soak Complete | NON_CLAIM |

Honesty: `live_soak_executed` / `helm_pooler_default_claimed` / `managed_cloud_pooler_claimed` / `live_tls_ingress_claimed` / `go_live_claimed` remain **false**.
