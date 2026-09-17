# VPS deploy — erp.ribdigihouse.com

Single-host Docker Compose + Caddy TLS for **https://erp.ribdigihouse.com**.

This is a **staging / release-candidate** recipe. It is not commercial go-live sign-off.

## 1. DNS

Point an A/AAAA record:

| Host | Type | Value |
|------|------|--------|
| `erp.ribdigihouse.com` | A | your VPS public IP |

Wait until `dig +short erp.ribdigihouse.com` returns that IP.

## 2. Install Docker + Caddy (Ubuntu)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git debian-keyring debian-archive-keyring curl
sudo usermod -aG docker $USER
# log out and back in

# Caddy
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

## 3. Clone release branch

```bash
sudo mkdir -p /opt && sudo chown "$USER":"$USER" /opt
cd /opt
git clone https://github.com/arthurbonneyrichard/ribdigi-erp.git
cd ribdigi-erp
git checkout cursor/ai-expense-store-filters-7aae
```

## 4. Env file

```bash
cp ops/vps/env.erp.ribdigihouse.com.example .env
nano .env   # replace every REPLACE_ME_* value
```

Required domain values are already set for `erp.ribdigihouse.com`.

Generate secrets:

```bash
openssl rand -hex 32   # JWT_SECRET_KEY
openssl rand -hex 32   # BACKUP_ENCRYPTION_KEY
openssl rand -hex 32   # TOTP_ENCRYPTION_KEY
openssl rand -hex 16   # DB / Rabbit / MinIO passwords
```

**Never** set `ALLOW_DEVELOPMENT_SEED=true` on this host.

## 5. Start app stack

```bash
cd /opt/ribdigi-erp
docker compose -f docker-compose.yml -f ops/vps/docker-compose.prod.example.yml up --build -d
docker compose -f docker-compose.yml -f ops/vps/docker-compose.prod.example.yml ps
docker compose -f docker-compose.yml -f ops/vps/docker-compose.prod.example.yml logs -f backend
```

Wait until you see Alembic migrations applied (through `20260917_0107`).

## 6. Caddy TLS reverse proxy

```bash
sudo cp ops/vps/Caddyfile.erp.ribdigihouse.com.example /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy
```

Caddy will obtain a Let’s Encrypt cert for `erp.ribdigihouse.com`.

## 7. Smoke test

```bash
curl -sS https://erp.ribdigihouse.com/api/v1/health/ready
```

Expect HTTP 200. Then in a browser:

1. Open https://erp.ribdigihouse.com  
2. Register a tenant (no demo user is auto-created)  
3. Login → POS → one online cash sale  

## 8. Firewall (recommended)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Do **not** expose 3000/8000/5432/6379/5672 publicly if Caddy is on the same machine (prod compose example binds app ports to localhost only).

## URL map

| Public URL | Upstream |
|------------|----------|
| `https://erp.ribdigihouse.com/api/*` | `127.0.0.1:8000` |
| `https://erp.ribdigihouse.com/*` | `127.0.0.1:3000` |

Browser API base: `https://erp.ribdigihouse.com/api/v1`
