.PHONY: up down logs test lint seed migrate ensure-env \
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

# --- production (Ubuntu VPS) ---
prod-config:
	docker compose -f docker-compose.prod.yml config >/dev/null && echo "docker-compose.prod.yml OK"
prod-up:
	docker compose -f docker-compose.prod.yml up -d --build
prod-down:
	docker compose -f docker-compose.prod.yml down
prod-logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=200
prod-migrate:
	docker compose -f docker-compose.prod.yml run --rm migrate
prod-ps:
	docker compose -f docker-compose.prod.yml ps
prod-backup:
	./ops/vps/backup-postgres.sh
