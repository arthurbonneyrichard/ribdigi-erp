# PgBouncer MVP — Connection Pooling Fidelity

**Status:** Complete (MVP) — Stage 27 P1  
**Evidence:** `backend/tests/test_pgbouncer_p1.py` · `/opt/cursor/artifacts/db/stage27_p1_pgbouncer.json`  
**Configs:** `ops/postgres/pgbouncer.ini.example`, `userlist.txt.example`, `docker-compose.pgbouncer.example.yml`

This is the **MVP PgBouncer packaging surface**: versioned operator config + Compose overlay + `DATABASE_URL` guidance for FastAPI/SQLAlchemy async. It is **not** a claim that PgBouncer runs in default `docker-compose`, main CI, or an in-cluster Helm chart.

## Why

Many uvicorn workers + Celery processes open direct Postgres connections. PgBouncer multiplexes client connections onto a smaller server pool.

## Operator install (staging)

1. Copy `ops/postgres/pgbouncer.ini.example` and fill `userlist.txt` from the Postgres role password hash.
2. Start optional overlay:  
   `docker compose -f docker-compose.yml -f ops/postgres/docker-compose.pgbouncer.example.yml up -d pgbouncer`
3. Point app env at the pooler (Stage 18 C1 prod path remains valid without PgBouncer):

```bash
DATABASE_URL=postgresql+asyncpg://ribdigi:SECRET@pgbouncer:6432/ribdigi_erp
# Optional explicit flag (also auto-detected for host pgbouncer / port 6432):
PGBOUNCER_TRANSACTION_MODE=true
```

4. Keep Alembic / `psql` admin sessions on `postgres:5432` when preferred.
5. Keep SQLAlchemy app-side pool modest (`DB_POOL_SIZE` / `DB_MAX_OVERFLOW`; defaults stay conservative).

## Transaction vs session pooling

| Mode | When to use |
|------|-------------|
| **transaction** (example default) | Best multiplexing. Requires asyncpg `statement_cache_size=0` (app applies automatically when URL targets PgBouncer / `:6432` or `PGBOUNCER_TRANSACTION_MODE=true`). Avoid session-scoped features across checkouts (`LISTEN`, temp tables spanning transactions). |
| **session** | Safer if you cannot disable the statement cache; weaker multiplexing. Set `pool_mode = session` in `pgbouncer.ini`. |

## Explicitly Remaining

- Live load proof that p95 improves under ~1000 VU with PgBouncer sized infra (**execution**)
- In-cluster / Helm PgBouncer as **default** K8s data plane
- Managed-cloud pooler product substitution (RDS Proxy, etc.) as Complete

## Soak / pooler pack (Stage 29 B2)

Authoritative pack: [PGBOUNCER_SOAK_PACK_MVP.md](PGBOUNCER_SOAK_PACK_MVP.md) · `ops/postgres/pgbouncer-soak-checklist.json` · `ops/postgres/soak-evidence.example.json` · optional `ops/postgres/pgbouncer-deployment.example.yaml` (not default Helm).

Packaging evidence keeps `live_soak_executed: false`, `helm_pooler_default_claimed: false`.

## Sign-off

Stage 27 P1 is met when versioned configs + this doc exist, `test_pgbouncer_p1.py` passes, and `PRODUCTION_READINESS.md` records PgBouncer Complete (MVP) with honest Remaining limited to live soak / in-cluster defaults. Stage 29 B2 is met when the soak pack + `test_pgbouncer_soak_b2.py` pass without inventing live soak success.
