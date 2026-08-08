.PHONY: up down logs test lint seed migrate ensure-env
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
