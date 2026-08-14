# PgBouncer Soak Pack Remaining-Gate Index MVP — Stage 317 I1

**Status:** Complete (MVP packaging) — Stage 317 I1  
**Evidence:** `backend/tests/test_stage317_index_i1.py`  
**Register:** `ops/mvp/pgbouncer-soak-pack-remaining-gate.json`  
**Related:** [PGBOUNCER_SOAK_PACK_RG_BLOCKERS_MVP.md](PGBOUNCER_SOAK_PACK_RG_BLOCKERS_MVP.md) · [PGBOUNCER_SOAK_PACK_RG_POINTERS_MVP.md](PGBOUNCER_SOAK_PACK_RG_POINTERS_MVP.md) · [PGBOUNCER_SOAK_PACK_MVP.md](PGBOUNCER_SOAK_PACK_MVP.md) · [PGBOUNCER_SOAK_REMAINING_GATE_MVP.md](PGBOUNCER_SOAK_REMAINING_GATE_MVP.md) · [PENTEST_PACK_REMAINING_GATE_MVP.md](PENTEST_PACK_REMAINING_GATE_MVP.md) · [SECURITY_SCAN_PACK_REMAINING_GATE_MVP.md](SECURITY_SCAN_PACK_REMAINING_GATE_MVP.md) · [STAGE_317_PLAN.md](STAGE_317_PLAN.md)

Single index of Stage 29 B2 PgBouncer soak-pack remaining gates. Packaging only — **live soak executed Complete and Helm pooler default Complete remain MISSING.** Prefixed `PGBOUNCER_SOAK_PACK_*` remaining-gate docs (`_REMAINING_GATE` / `_RG_*`) — distinct from Stage 29 B2 `PGBOUNCER_SOAK_PACK_MVP.md`, Stage 208 `PGBOUNCER_SOAK_REMAINING_GATE_*`, Stage 316 `PENTEST_PACK_*`, and Stage 315 `SECURITY_SCAN_PACK_*`.

## Classification

| Flag | Value |
|------|-------|
| `packaging_complete` | true |
| `live_soak_executed` | **false** |
| `helm_pooler_default_claimed` | **false** |
| `managed_cloud_pooler_claimed` | **false** |
| `live_tls_ingress_claimed` | **false** |
| `go_live_claimed` | **false** |

## Index order

1. Read **B1** blocker matrix (`live_soak_executed` / `helm_pooler_default_claimed`, Stage 29 B2 / Stage 208 non-claim).
2. Follow **P1** pointers into Stage 29 B2 / Stage 316 / Stage 315 / Stage 208 adjacency.
3. Reaffirm live soak / Helm pooler default stay MISSING until real Completes ship.
4. Do not treat Stage 29 B2 packaging, Stage 208 remaining-gate, or Stage 316 packs as live soak Complete.
5. Leave live soak / Helm pooler default / managed cloud pooler / live TLS ingress / go-live as Remaining.

## Explicitly not claimed

- Live soak executed Complete
- Helm pooler default Complete
- Managed cloud pooler Complete
- Live TLS ingress Complete
- Go-live Complete
