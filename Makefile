.PHONY: dev test test-backend test-frontend typecheck build migrate migrations superuser

dev:
	docker compose up --build

test: test-backend test-frontend

test-backend:
	docker compose run --rm backend pytest

test-frontend:
	docker compose run --rm frontend npm test

typecheck:
	docker compose run --rm frontend npm run typecheck

build:
	docker compose build
	docker compose run --rm frontend npm run build

migrations:
	docker compose run --rm backend python manage.py makemigrations --check --dry-run

migrate:
	docker compose run --rm backend python manage.py migrate

superuser:
	docker compose exec backend python manage.py createsuperuser
