.PHONY: help up down logs backend-dev frontend-dev worker-dev migrate test-backend test-frontend lint-backend typecheck-frontend generate-api-types

help:
	@echo "PolamRaksha Development Commands"
	@echo "  make up                  Start all services via Docker Compose"
	@echo "  make down                Stop Docker Compose services"
	@echo "  make logs                Follow Docker Compose logs"
	@echo "  make backend-dev         Run FastAPI backend natively (requires local Postgres)"
	@echo "  make worker-dev          Run background worker natively"
	@echo "  make frontend-dev        Run Vite frontend dev server natively"
	@echo "  make migrate             Run Alembic migrations"
	@echo "  make test-backend        Run Pytest suite"
	@echo "  make test-frontend       Run Vitest suite"
	@echo "  make typecheck-frontend  Run TypeScript compiler check"
	@echo "  make generate-api-types  Generate frontend OpenAPI TypeScript types"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

backend-dev:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker-dev:
	cd backend && uv run python -m app.workers.runner

frontend-dev:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

migrate:
	cd backend && uv run alembic upgrade head

seed-demo:
	cd backend && uv run python scripts/seed_demo.py --confirm-demo

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm run test

lint-backend:
	cd backend && uv run ruff check app tests

typecheck-frontend:
	cd frontend && npm run typecheck

generate-api-types:
	cd backend && uv run python scripts/export_openapi.py ../frontend/openapi.json
	cd frontend && npm run generate:api

