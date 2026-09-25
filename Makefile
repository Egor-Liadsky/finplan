.PHONY: up migrate revision seed test lint recalc brief

up:
	docker compose up -d

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

seed:
	@echo "not implemented yet: stage 2"

test:
	uv run pytest

brief:
	python3 docs/build-brief.py

lint:
	python3 docs/build-brief.py --check
	uv run ruff check
	uv run ruff format --check
	uv run mypy src

recalc:
	@echo "not implemented yet: stage 3"
