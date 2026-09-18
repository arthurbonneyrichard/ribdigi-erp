.PHONY: up down logs test lint seed migrate ensure-env loadtest-smoke \
	prod-config prod-up prod-down prod-logs prod-migrate prod-ps prod-backup

ensure-env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example — set JWT_SECRET_KEY before production")
up: ensure-env
	docker compose up --build
down:
	docker compose down
logs:
	docker compose logs -f
seed:
	docker compose exec backend python scripts/seed.py
migrate:
	docker compose exec backend python -m alembic upgrade head
test:
	docker compose exec -e PYTHONPATH=/app backend pytest -q
lint:
	docker compose exec backend ruff check app tests
# Stage 5 L1 — CI-style health baseline (live API). See docs/LOAD_TEST_BASELINE.md
loadtest-smoke:
	docker compose exec -e PYTHONPATH=/app backend python -m loadtest.run_baseline --smoke --base-url http://localhost:8000

# --- production / Dokploy helpers (manual Compose; Dokploy uses UI Deploy) ---
prod-config:
	docker compose -f docker-compose.dokploy.yml config >/dev/null && echo "docker-compose.dokploy.yml OK"
prod-up:
	docker compose -f docker-compose.dokploy.yml up -d --build
prod-down:
	docker compose -f docker-compose.dokploy.yml down
prod-logs:
	docker compose -f docker-compose.dokploy.yml logs -f --tail=200
prod-migrate:
	docker compose -f docker-compose.dokploy.yml run --rm migrate
prod-ps:
	docker compose -f docker-compose.dokploy.yml ps
prod-backup:
	./ops/vps/backup-postgres.sh
