.PHONY: help install backend-install frontend-install dev backend frontend \
        migrate makemigrations superuser shell test test-backend lint format \
        clean

BACKEND_PY := backend/venv/bin/python
BACKEND_PIP := backend/venv/bin/pip

help:
	@echo "Available targets:"
	@echo "  install              Install backend + frontend deps"
	@echo "  dev                  Run backend (8000) and frontend (5173) — use two terminals"
	@echo "  backend              Run Django dev server on :8000"
	@echo "  frontend             Run Vite dev server on :5173"
	@echo "  migrate              Apply Django migrations"
	@echo "  makemigrations       Create new migrations from model changes"
	@echo "  superuser            Create a Django superuser"
	@echo "  shell                Open Django shell"
	@echo "  test                 Run backend pytest suite"
	@echo "  lint                 Run ruff over backend"
	@echo "  format               Auto-format backend with ruff"
	@echo "  clean                Remove caches and build artifacts"

install: backend-install frontend-install

backend-install:
	cd backend && python -m venv venv && ./venv/bin/pip install -U pip && ./venv/bin/pip install -r requirements.txt

frontend-install:
	cd frontend && npm install

backend:
	cd backend && ./venv/bin/python manage.py runserver 0.0.0.0:8000

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && ./venv/bin/python manage.py migrate

makemigrations:
	cd backend && ./venv/bin/python manage.py makemigrations

superuser:
	cd backend && ./venv/bin/python manage.py createsuperuser

shell:
	cd backend && ./venv/bin/python manage.py shell

test test-backend:
	cd backend && ./venv/bin/pytest

lint:
	cd backend && ./venv/bin/python -m ruff check .

format:
	cd backend && ./venv/bin/python -m ruff format .

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
