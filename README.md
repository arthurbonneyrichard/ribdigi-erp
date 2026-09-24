# RIBDIGI BUSINESS ERP

**One ERP Platform. Unlimited Business.**

This repository is the RIBDIGI BUSINESS ERP product codebase. The target product is a commercial, multi-tenant SaaS ERP for Retail, Mart, Pharmacy, Restaurant, Bakery, Wholesale, and Manufacturing.

## Product principle: no demo behavior

Production startup must never auto-create a demo tenant, default user, fake transaction, sample company, or known password. The login page contains no pre-filled credentials. Optional local seed data is disabled by default, blocked in production, and must be explicitly enabled with `ALLOW_DEVELOPMENT_SEED=true`.

Endpoints must not report unfinished operations as successful. Features that require production services (for example backup/restore or an AI provider) return an unavailable error until the real service is configured.

## Current implementation status

The repository contains a working application foundation and several implemented ERP flows, but **market readiness must be determined by verified acceptance criteria, not by labels**. The authoritative requirements are under `docs/`. The production launch gate is `PRODUCTION_READINESS.md`.

The original specification requires, among other items, complete tenant isolation, granular RBAC, complete POS/inventory/accounting workflows, backup and restore, 2FA, session management, email verification/password reset, audit coverage, API/webhooks, security hardening, monitoring, load testing, and launch sign-off. Features must not be called complete until their implementation and tests exist.

## Local development

```bash
cp .env.example .env
docker compose up --build
```

- Web UI: http://localhost:3000
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

No default application login is created automatically. Create a tenant through the tenant registration API/UI.

## Optional local seed data

Local seed data is strictly for developer testing and is disabled by default. To use it in a disposable local environment only:

```env
APP_ENV=development
ALLOW_DEVELOPMENT_SEED=true
```

Then run:

```bash
docker compose exec backend python scripts/seed.py
```

Never enable this flag in staging or production.

## Production deployment

### Option A — Dokploy (recommended for first VPS)

**Deploy the latest commercial ERP from Git branch `production` (not `main`).**  
GitHub `main` is an older ERP lineage; Dokploy must use:

| Setting | Value |
|---------|--------|
| Repository | `ribdigi-erp` |
| **Branch** | **`production`** |
| Compose file | `docker-compose.dokploy.yml` |

After switching branch, **Redeploy with image rebuild (no cache)**. Confirm the live API:

`GET /api/v1/health` → `release_channel: "production"` and a current `build_id`.

Step-by-step (buy VPS → install Dokploy → GitHub → domains → Platform Owner):

- **`ops/vps/DOKPLOY_FIRST_TIME.md`**
- Compose file: **`docker-compose.dokploy.yml`** (Traefik handles HTTPS — no Caddy)

### Option B — Manual Docker Compose + Caddy

- **`ops/vps/README.md`** — full A–L operator guide
- **`docker-compose.prod.yml`** — production stack with Caddy
- **`ops/vps/env.production.example`** — copy to `.env` and replace all `REPLACE_ME_*` values

```bash
cp ops/vps/env.production.example .env
# edit .env and ops/vps/Caddyfile for your domain
docker compose -f docker-compose.prod.yml up -d --build
```

Do not run Option A and Option B on the same VPS (both need ports 80/443).  
Do not use development Docker credentials in production. Never set `ALLOW_DEVELOPMENT_SEED=true` on a public host.
