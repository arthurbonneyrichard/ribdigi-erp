# First-time VPS + Dokploy setup for Ribdigi ERP

This guide is for a **first VPS** and **Dokploy**.  
Dokploy is a control panel that installs Docker + Traefik and deploys your Git repo with a UI.

| Deploy style | Compose file | Who handles HTTPS |
|--------------|--------------|-------------------|
| **Dokploy (this guide)** | `docker-compose.dokploy.yml` | Dokploy Traefik |
| Manual Compose | `docker-compose.prod.yml` | Caddy in compose |

**Do not run both** on the same VPS — both want ports 80 and 443.

Official Dokploy install docs: https://docs.dokploy.com/docs/core/installation

---

## 0. What you need before starting

| Item | Recommendation |
|------|----------------|
| VPS | Ubuntu **24.04** LTS |
| RAM | **4 GB minimum**, **8 GB better** (Postgres + RabbitMQ + MinIO + app) |
| Disk | **40 GB+** SSD |
| Domain | e.g. `erp.ribdigihouse.com` (A record → VPS IP) |
| GitHub | Access to `ribdigi-erp` (or your fork) |
| SSH | Terminal app (Mac/Linux) or PuTTY / Windows Terminal |

Suggested providers: Hetzner, DigitalOcean, Linode, Vultr, Contabo, etc.

---

## 1. Create the VPS

1. Create a droplet/server: **Ubuntu 24.04**, 4–8 GB RAM.
2. Add your **SSH key** (safer than password).
3. Note the **public IP** (example: `203.0.113.10`).
4. In your DNS provider, create:

| Type | Name | Value |
|------|------|--------|
| A | `erp` (or `@` / your host) | VPS public IP |
| A | `panel` (optional, for Dokploy UI) | same IP |

Wait until DNS resolves:

```bash
dig +short erp.ribdigihouse.com
dig +short panel.ribdigihouse.com
```

---

## 2. First SSH login + firewall

```bash
ssh root@YOUR_VPS_IP
# or: ssh ubuntu@YOUR_VPS_IP
```

Update the OS and enable a basic firewall:

```bash
apt update && apt upgrade -y
apt install -y ufw curl git ca-certificates
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 3000/tcp    # Dokploy UI (temporary until you put it on HTTPS domain)
ufw enable
ufw status
```

---

## 3. Install Dokploy (one command)

Dokploy installs Docker for you if needed.

```bash
curl -sSL https://dokploy.com/install.sh | sh
```

When it finishes, open in your browser:

```text
http://YOUR_VPS_IP:3000
```

1. Create the **admin account** (email + strong password).
2. Save those credentials somewhere safe.

### Secure the Dokploy panel with HTTPS (strongly recommended)

In Dokploy → settings / domains for the **Dokploy panel itself**, attach something like `panel.ribdigihouse.com` with Let's Encrypt.

Only after HTTPS panel works, you may remove public `:3000` access (optional):

```bash
docker service update --publish-rm "published=3000,target=3000,mode=host" dokploy
```

Details: https://docs.dokploy.com/docs/core/installation

---

## 4. Connect GitHub to Dokploy

1. Dokploy → **Settings** → **Git** (GitHub).
2. Install / authorize the Dokploy GitHub App on the `ribdigi-erp` repo (or your fork).
3. Confirm the repo appears when creating a service.

---

## 5. Create a Compose service for Ribdigi

1. Dokploy → **Projects** → **Create Project** → name it `ribdigi`.
2. Inside the project → **Create Service** → **Docker Compose**.
3. **General** tab:
   - **Source:** GitHub
   - **Repository:** your `ribdigi-erp`
   - **Branch:** `cursor/production-docker-compose-vps` (or your release branch)
   - **Compose path:** `docker-compose.dokploy.yml`
   - **Compose type:** Docker Compose (not Stack)

---

## 6. Paste environment variables

1. Open repo-root **`.env.production.example`** (canonical Dokploy env template).
2. Dokploy Compose service → **Environment** tab.
3. Paste **all** variables, then replace every `REPLACE_ME_*` value.
   Domain defaults already target `https://erp.ribdigihouse.com`.

```env
APP_ENV=production
DEBUG=false
ALLOW_DEVELOPMENT_SEED=false

JWT_SECRET_KEY=   # openssl rand -hex 32
BACKUP_ENCRYPTION_KEY=
TOTP_ENCRYPTION_KEY=

POSTGRES_PASSWORD=
DATABASE_URL=postgresql+asyncpg://ribdigi:SAME_PASSWORD@postgres:5432/ribdigi_erp

RABBITMQ_DEFAULT_PASS=
RABBITMQ_URL=amqp://ribdigi:SAME_PASSWORD@rabbitmq:5672/
CELERY_BROKER_URL=amqp://ribdigi:SAME_PASSWORD@rabbitmq:5672//

MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
S3_ACCESS_KEY=   # same as MINIO_ROOT_USER
S3_SECRET_KEY=   # same as MINIO_ROOT_PASSWORD

CORS_ORIGINS=https://erp.ribdigihouse.com
FRONTEND_URL=https://erp.ribdigihouse.com
NEXT_PUBLIC_API_URL=https://erp.ribdigihouse.com/api/v1
TRUSTED_HOSTS=erp.ribdigihouse.com,localhost,127.0.0.1
WEBAUTHN_RP_ID=erp.ribdigihouse.com
WEBAUTHN_ORIGIN=https://erp.ribdigihouse.com

EMAIL_ENABLED=false
SMS_ENABLED=false
AI_ENABLED=false
```

Generate secrets on the VPS:

```bash
openssl rand -hex 32
openssl rand -hex 16
```

Dokploy writes these into a `.env` next to the compose file. Our compose already uses `env_file: .env` for backend/celery.

**Important:** `NEXT_PUBLIC_API_URL` is baked into the frontend **at build time**. If you change it later, Redeploy / rebuild.

---

## 7. Add domains (Traefik) — then Redeploy

Dokploy → your Compose service → **Domains**.

Add **two** routes on the **same host** (path-based, like our Caddy setup):

### Domain A — API
| Field | Value |
|-------|--------|
| Host | `erp.ribdigihouse.com` |
| Path | `/api` |
| Service name | `backend` |
| Container port | `8000` |
| HTTPS | On |
| Certificate | Let's Encrypt |
| Strip Path | **Off** |

### Domain B — UI
| Field | Value |
|-------|--------|
| Host | `erp.ribdigihouse.com` |
| Path | `/` |
| Service name | `frontend` |
| Container port | `3000` |
| HTTPS | On |
| Certificate | Let's Encrypt |

**Compose domains require a redeploy** after every domain change.

Click **Deploy**. First build can take several minutes (backend image + Next.js build).

---

## 8. Watch logs and health

In Dokploy:

- **Deployments** — build output  
- **Logs** — pick `backend`, `frontend`, `postgres`, `celery_worker`  
- **Monitoring** — container status  

From your laptop:

```bash
curl -fsS https://erp.ribdigihouse.com/api/v1/health
curl -fsS https://erp.ribdigihouse.com/api/v1/health/ready
```

Open `https://erp.ribdigihouse.com` in the browser.

---

## 9. Create the Platform Owner (one time)

Dokploy → Compose → open a terminal / exec into **`backend`**, or SSH to the VPS:

```bash
# Find the backend container name
docker ps --format '{{.Names}}' | grep -i backend

docker exec -it CONTAINER_NAME \
  env ALLOW_PLATFORM_OWNER_BOOTSTRAP=true \
      PLATFORM_OWNER_EMAIL='you@ribdigihouse.com' \
      PLATFORM_OWNER_PASSWORD='YourStrongPass1!' \
      PLATFORM_OWNER_FULL_NAME='Platform Owner' \
  python scripts/create_platform_owner.py
```

Then log in at `https://erp.ribdigihouse.com` and change the password.  
Do **not** leave `ALLOW_PLATFORM_OWNER_BOOTSTRAP=true` in Dokploy env.

---

## 10. Day-2 operations (Dokploy)

| Task | How |
|------|-----|
| Update app | Push to GitHub → Dokploy auto-deploy (if enabled) or click **Deploy** |
| View logs | Compose → Logs |
| Restart | Compose → Redeploy / Restart |
| Migrations | Handled by `migrate` service on deploy; or exec `python -m alembic upgrade head` in backend |
| Backup Postgres | SSH + `./ops/vps/backup-postgres.sh` (adjust compose file name / project) or Dokploy Volume Backups on `postgres_data` |

---

## Common first-time mistakes

1. **Port 80/443 already used** — stop nginx/Caddy/`docker-compose.prod.yml` before installing Dokploy.  
2. **Using `docker-compose.prod.yml` in Dokploy** — that file includes Caddy and will fight Traefik. Use **`docker-compose.dokploy.yml`**.  
3. **Forgot Redeploy after Domains** — Compose domains only apply after redeploy.  
4. **Wrong `NEXT_PUBLIC_API_URL`** — must be `https://your-host/api/v1` and rebuild frontend.  
5. **`EMAIL_ENABLED=true` without SMTP** — app will refuse to start in production. Keep `false` until SMTP is ready.  
6. **2 GB RAM VPS** — often OOMs during Next.js / image builds. Use 4–8 GB.  
7. **DNS not pointing yet** — Let's Encrypt will fail until the A record is correct.

---

## Quick decision: Dokploy vs plain Compose

- **Choose Dokploy** if you want a UI, GitHub auto-deploy, Traefik domains, and less SSH day-to-day.  
- **Choose `docker-compose.prod.yml`** if you prefer only SSH + Caddy and no Dokploy panel.

Both paths share the same app Dockerfiles, env template, migrations, and Platform Owner script.
