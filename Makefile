.PHONY: up migrate revision seed test lint recalc

up:
	docker compose up -d

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

seed:
	@echo "not implemented yet: stage 1"

test:
	uv run pytest

lint:
	uv run ruff check
	uv run ruff format --check
	uv run mypy src

recalc:
	@echo "not implemented yet: stage 1"
