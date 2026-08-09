# AGENTS.md

## Cursor Cloud specific instructions

This repo (RIBDIGI BUSINESS ERP) is normally run via `docker compose up` (see `README.md`), but the
Cursor Cloud VM has **no Docker**. Instead it runs **natively**: PostgreSQL, Redis, and RabbitMQ are
installed as system packages, the FastAPI backend runs from a Python venv, and the Next.js frontend
runs via `npm`. The startup update script only refreshes dependencies (`backend/.venv` via
`pip install -r backend/requirements.txt`, and `npm install` in `frontend/`); everything below must be
done by the agent for each session.

### Services

| Service | Command (run from the given dir) | Port | Notes |
|---|---|---|---|
| PostgreSQL 16 | `sudo pg_ctlcluster 16 main start` | 5432 | role/db `ribdigi`/`ribdigi_erp` (password `ribdigi`) already created |
| Redis 7 | `sudo redis-server --daemonize yes` | 6379 | rate limiting + Celery result backend |
| RabbitMQ 3.12 | `sudo rabbitmq-server -detached` (then `sudo rabbitmqctl await_startup`) | 5672 / 15672 | user `ribdigi`/`ribdigi` (administrator) already created |
| Backend (FastAPI) | `cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | 8000 | `/docs` Swagger, `/api/v1/health`. Run `PYTHONPATH=. .venv/bin/python scripts/bootstrap.py` first to apply Alembic migrations |
| Celery worker | `cd backend && PYTHONPATH=. .venv/bin/celery -A app.celery_app.celery worker --loglevel=info --concurrency=2` | — | broker=RabbitMQ, results=Redis |
| Celery beat (optional) | `cd backend && PYTHONPATH=. .venv/bin/celery -A app.celery_app.celery beat --loglevel=info` | — | periodic jobs only; not needed for most testing |
| Frontend (Next.js) | `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev` | 3000 | web UI |

Start long-running services in tmux so they survive between commands. There is no systemd on this VM
(`systemctl` does not work), so start the datastores with the direct commands above, not `service`/`systemctl`.

### Environment file (`.env`)

The backend reads `../.env` (i.e. `/workspace/.env`) via pydantic-settings. `.env` is gitignored and is
kept in the VM snapshot. If it is ever missing, recreate it from `.env.example` but rewrite the Docker
hostnames to `localhost` (the defaults point at Docker network names `postgres`/`redis`/`rabbitmq`/`minio`):
`DATABASE_URL=...@localhost:5432/...`, `REDIS_URL=redis://localhost:6379/0`,
`RABBITMQ_URL=amqp://ribdigi:ribdigi@localhost:5672/`. Also set a `JWT_SECRET_KEY`, point
`MEDIA_DIR`/`BACKUP_DIR` at a writable path (this VM uses `/workspace/.devdata/...`), and `SMS_ENABLED=false`
(Twilio is not configured). `STORAGE_BACKEND=local` avoids needing MinIO/S3.

### Lint / test / build / run

- Backend lint: `cd backend && .venv/bin/ruff check app tests` (a few pre-existing unused-import warnings in `tests/` are unrelated to setup).
- Backend tests: `cd backend && PYTHONPATH=. .venv/bin/pytest -q` (uses in-memory SQLite; does not need Postgres running).
- Frontend build: `cd frontend && npm run build`. Dev server: `npm run dev` (use this for development, per project guidance).
- The canonical commands in `Makefile` assume Docker (`docker compose exec ...`) and do **not** work on this VM — use the native commands above instead.

### Non-obvious gotchas

- **Admin accounts are forced into 2FA.** Roles in `TOTP_ENFORCED_ROLES` (default `company_admin,super_admin`)
  get `must_enroll_2fa: true` and the backend blocks all non-enrollment endpoints until TOTP is enrolled
  (see `app/totp.py` `ENROLLMENT_ALLOWED_SUFFIXES`). To test protected flows as an admin, enroll TOTP first
  (`POST /auth/2fa/setup` returns the plaintext `secret`; generate a code with `pyotp` and `POST /auth/2fa/confirm`).
  Backup codes from `POST /auth/2fa/confirm` / `POST /auth/2fa/backup-codes` do **not** expire and are handy for
  UI logins (the 2FA field accepts an authenticator code *or* a backup code). To avoid 2FA entirely for a test
  user, create a user whose role is not in `TOTP_ENFORCED_ROLES`.
- **Email validator rejects reserved TLDs.** Registering a tenant with an `@…​.test`/`@…​.example` local address
  fails validation; use a normal-looking domain (e.g. `@acme-erp.example.com` works, `@acme.test` does not).
- **No demo/seed data by default** (by design). Create a tenant via `POST /api/v1/tenants` (fields:
  `company_name`, `slug`, `industry`, `currency`, `admin_email`, `admin_password`). In non-production, the
  response includes `email_verification_token`. Optional dev seed requires `APP_ENV=development` +
  `ALLOW_DEVELOPMENT_SEED=true` then `python scripts/seed.py`.
- **Celery beat** writes a `celerybeat-schedule` file in its working dir; it is gitignored.
- Reinstalling backend deps does not require restarting uvicorn for app-code edits (it runs with `--reload`),
  but a dependency change does require restarting the uvicorn/celery processes.
