# Ribdigi ERP — Ubuntu 24.04 VPS production deploy (Docker Compose)

**Status:** Production-oriented packaging for a single VPS. Complete the
[security checklist](#l-production-security-checklist) and a smoke test before
calling a host commercially go-live ready.

**First time + Dokploy?** Start here instead → **[`DOKPLOY_FIRST_TIME.md`](./DOKPLOY_FIRST_TIME.md)**  
(uses `docker-compose.dokploy.yml` + Traefik; do not mix with this Caddy stack).

Authoritative **manual** compose file: **`docker-compose.prod.yml`** (repo root).  
Env template: **`ops/vps/env.production.example`**.  
TLS proxy: **Caddy** service in compose + **`ops/vps/Caddyfile`**.

---

## Architecture (production)

| Service | Role | Published ports |
|---------|------|-----------------|
| `caddy` | TLS termination + reverse proxy | `80`, `443` |
| `frontend` | Next.js (`node server.js`, standalone) | none (edge network) |
| `backend` | FastAPI via uvicorn workers | none (edge + internal) |
| `migrate` | one-shot Alembic upgrade | none |
| `celery_worker` | Celery worker (RabbitMQ broker, Redis results) | none |
| `celery_beat` | Celery beat scheduler | none |
| `postgres` | PostgreSQL 16 | **none** |
| `redis` | Cache / rate-limit / Celery results | **none** |
| `rabbitmq` | Celery broker (+ management, internal) | **none** |
| `minio` | S3-compatible object storage | **none** |

Networks:

- `ribdigi_edge` — Caddy ↔ frontend ↔ backend  
- `ribdigi_internal` — backend/celery ↔ postgres/redis/rabbitmq/minio  

PostgreSQL data: Docker volume `postgres_data`.

---

## A–L operator guide

### A. Files created

| Path | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production Compose stack |
| `backend/.dockerignore` | Slimmer backend image |
| `frontend/.dockerignore` | Slimmer frontend image |
| `backend/scripts/bootstrap_platform_admin.py (on main)` | Initial Platform Owner bootstrap |
| `ops/vps/env.production.example` | Production `.env` template |
| `ops/vps/Caddyfile` | TLS reverse proxy config |
| `ops/vps/backup-postgres.sh` | `pg_dump` → gzip on host |
| `ops/vps/restore-postgres.sh` | Restore gzip dump into Postgres |
| `ops/vps/README.md` | This guide |

### B. Files modified

| Path | Change |
|------|--------|
| `backend/Dockerfile` | Production image (non-root, healthcheck, uvicorn workers) |
| `frontend/Dockerfile` | Multi-stage Next.js standalone production build |
| `backend/scripts/bootstrap.py` | Refuse `create_all` fallback when `APP_ENV=production` |
| `.env.production.example` | Aligned with Compose secrets model |
| `.gitignore` | Ignore `/backups/` and `*.sql.gz` |
| `ops/vps/docker-compose.prod.example.yml` | Deprecated pointer → root compose |
| `Makefile` | `prod-*` targets |

### C. Exact VPS commands (Ubuntu 24.04)

```bash
# 1) Base packages + Docker
sudo apt update
sudo apt install -y ca-certificates curl git openssl ufw
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"
# log out and back in so docker group applies

# 2) Firewall (SSH + HTTP/HTTPS only)
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status

# 3) DNS: point your hostname A/AAAA record at this VPS public IP
dig +short erp.example.com

# 4) Clone
sudo mkdir -p /opt && sudo chown "$USER":"$USER" /opt
cd /opt
git clone https://github.com/arthurbonneyrichard/ribdigi-erp.git
cd ribdigi-erp
git checkout <release-branch-or-tag>

# 5) Env + Caddy hostname
cp ops/vps/env.production.example .env
nano .env   # replace ALL REPLACE_ME_* values; set PUBLIC_HOST / CORS / URLs
nano ops/vps/Caddyfile   # replace erp.example.com + Let's Encrypt email

# Generate secrets
openssl rand -hex 32   # JWT_SECRET_KEY
openssl rand -hex 32   # BACKUP_ENCRYPTION_KEY
openssl rand -hex 32   # TOTP_ENCRYPTION_KEY
openssl rand -hex 16   # POSTGRES_PASSWORD / RABBITMQ / MINIO

# 6) Build & start
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

### D. Environment variables you must configure

| Variable | Notes |
|----------|--------|
| `JWT_SECRET_KEY` | ≥32 chars, random |
| `BACKUP_ENCRYPTION_KEY` | random; required for `.ribbak` crypto |
| `TOTP_ENCRYPTION_KEY` | random |
| `POSTGRES_PASSWORD` | strong; must match `DATABASE_URL` |
| `DATABASE_URL` | `postgresql+asyncpg://…@postgres:5432/…` |
| `RABBITMQ_DEFAULT_PASS` | strong; must match `RABBITMQ_URL` / `CELERY_BROKER_URL` |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | strong; match `S3_ACCESS_KEY` / `S3_SECRET_KEY` |
| `CORS_ORIGINS` | exact HTTPS origin(s), no `*` |
| `FRONTEND_URL` / `NEXT_PUBLIC_API_URL` | public HTTPS URLs |
| `WEBAUTHN_RP_ID` / `WEBAUTHN_ORIGIN` | match public host |
| `APP_ENV=production` | required |
| `DEBUG=false` | required |
| `EMAIL_ENABLED=false` | until SMTP is configured |
| `SMS_ENABLED=false` | until Twilio is configured |
| `ALLOW_DEVELOPMENT_SEED=false` | never true in prod |

Full template: `ops/vps/env.production.example`.

### E. Database migration command

Migrations run automatically via the `migrate` service on `up`. To run manually:

```bash
docker compose -f docker-compose.prod.yml run --rm migrate
# equivalent:
docker compose -f docker-compose.prod.yml run --rm backend python -m alembic upgrade head
```

### F. Platform Admin creation command

```bash
docker compose -f docker-compose.dokploy.yml exec \
  -e PLATFORM_ADMIN_EMAIL='owner@ribdigihouse.com' \
  -e PLATFORM_ADMIN_PASSWORD='YourStrongPass1!' \
  -e PLATFORM_ADMIN_FULL_NAME='Platform Super Admin' \
  -e PLATFORM_ADMIN_ROLE=platform_super_admin \
  backend python scripts/bootstrap_platform_admin.py
```

Password rules: ≥8 chars with upper, lower, number, and symbol.  
Do not leave `PLATFORM_ADMIN_PASSWORD` in long-lived env after bootstrap.

### G. Docker deployment command

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### H. How to check logs

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=200
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f celery_worker
docker compose -f docker-compose.prod.yml logs -f caddy
```

### I. How to restart the system

```bash
docker compose -f docker-compose.prod.yml restart
# or rolling:
docker compose -f docker-compose.prod.yml up -d --force-recreate backend frontend
```

### J. How to update after pushing new code to GitHub

```bash
cd /opt/ribdigi-erp
git fetch --prune
git checkout <release-branch-or-tag>
git pull

# Rebuild images (frontend rebuild required when NEXT_PUBLIC_API_URL or UI changes)
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
# migrate service re-applies Alembic to head on each up
docker compose -f docker-compose.prod.yml ps
curl -fsS https://erp.example.com/api/v1/health/ready
```

### K. Backup and restore procedure

**Backup (Postgres logical dump):**

```bash
mkdir -p backups && chmod 700 backups
./ops/vps/backup-postgres.sh
# copy backups/*.sql.gz off the VPS immediately
```

**Restore:**

```bash
docker compose -f docker-compose.prod.yml stop backend celery_worker celery_beat frontend
./ops/vps/restore-postgres.sh ./backups/ribdigi_erp_YYYYMMDDTHHMMSSZ.sql.gz
docker compose -f docker-compose.prod.yml start backend celery_worker celery_beat frontend
docker compose -f docker-compose.prod.yml run --rm migrate
```

Tenant-level encrypted `.ribbak` backups remain available in-app (`docs/DR_LOGICAL_BACKUP_RUNBOOK.md`).

### L. Production security checklist

- [ ] `APP_ENV=production`, `DEBUG=false`, `ALLOW_DEVELOPMENT_SEED=false`
- [ ] Strong unique secrets for JWT / backup / TOTP / DB / Rabbit / MinIO
- [ ] `CORS_ORIGINS` is exact HTTPS origin(s), never `*`
- [ ] UFW allows only 22/80/443; Postgres/Redis/Rabbit/MinIO ports closed
- [ ] Compose publishes only Caddy `80`/`443` (verify: `docker compose -f docker-compose.prod.yml ps`)
- [ ] TLS works (`https://` and HSTS header present)
- [ ] `/docs` and `/openapi.json` disabled (production FastAPI settings)
- [ ] Platform admin created once; PLATFORM_ADMIN_PASSWORD not left in env
- [ ] `EMAIL_ENABLED`/`SMS_ENABLED`/`AI_ENABLED` only when credentials are real
- [ ] `LOGIN_2FA_ENABLED=true` for production
- [ ] Off-box copy of Postgres dumps tested with restore drill
- [ ] Host packages patched; Docker engine current
- [ ] Smoke: health ready, login, one POS cash sale

---

## Remaining issues (do not claim go-live until addressed)

1. **Hostname placeholders** — `ops/vps/Caddyfile` and env template use `erp.example.com`; must match your DNS before TLS works.
2. **Next.js bake-time env** — changing `NEXT_PUBLIC_API_URL` requires `docker compose build frontend` (not just restart).
3. **Redis has no password** — acceptable only because it is unpublished on an internal Docker network; harden further (ACL/password) if the host is multi-tenant.
4. **Single-node Compose** — no HA Postgres/Rabbit; commercial SLA needs managed DB or replicas.
5. **WAL/PITR** — logical `pg_dump` scripts are provided; continuous WAL archiving is documented under `ops/postgres/` but not enabled by default.
6. **Commercial go-live** — still requires owner sign-off on physical ops, monitoring alerts, and `docs/GO_LIVE_CHECKLIST.md`.
7. **Dev compose unchanged** — `docker-compose.yml` remains for local development (public ports, reload); never point production DNS at it.

## Quick smoke test

```bash
curl -fsS https://erp.example.com/api/v1/health
curl -fsS https://erp.example.com/api/v1/health/ready
# expect HTTP 200 JSON with success/ready signals
```
