.PHONY: up down logs test lint seed migrate
up:
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
