.PHONY: dev dev-backend dev-frontend db migrate lint install install-hooks generate-client stop restart verify-promotion

# Start everything
dev:
	$(MAKE) -j3 db dev-backend dev-frontend

db:
	docker compose up -d postgres

dev-backend:
	cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8001

dev-frontend:
	cd frontend && npm run dev -- --port 3001

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

install-hooks:
	pre-commit install

# Regenerate frontend TypeScript types from the FastAPI OpenAPI spec.
# Run after changes to backend Pydantic schemas. The output file is
# committed so LLMs and tests can rely on it without running the
# generator. CI doesn't run this — drift gets caught at next manual
# regen + the resulting tsc errors.
generate-client:
	cd backend && DEBUG=true PYTHONPATH=. python scripts/dump_openapi.py > /tmp/baseplate-openapi.json
	cd frontend && npx openapi-typescript /tmp/baseplate-openapi.json -o src/lib/api-types.ts
	rm -f /tmp/baseplate-openapi.json

migrate:
	cd backend && PYTHONPATH=. alembic upgrade head

migrate-new:
	cd backend && PYTHONPATH=. alembic revision --autogenerate -m "$(msg)"

lint:
	cd backend && ruff check app/ tests/
	cd frontend && npx tsc --noEmit
	cd frontend && npm run lint

test-backend:
	cd backend && PYTHONPATH=. pytest -v

test-frontend:
	cd frontend && npx vitest run

# Stop all services
stop:
	-pkill -f "uvicorn app.main:app" 2>/dev/null
	-pkill -f "next dev.*--port 3001" 2>/dev/null
	docker compose down

# Restart everything
restart: stop
	sleep 1
	$(MAKE) dev

hash-password:
	@python -c "import bcrypt, getpass; print(bcrypt.hashpw(getpass.getpass('Password: ').encode(), bcrypt.gensalt()).decode())"

# Verify this project honours the Flatpack it was promoted from.
# Expects reference/original-flatpack.html in the project root.
# See docs/promoting-a-flatpack.md.
verify-promotion:
	cd backend && DEBUG=true PYTHONPATH=. python scripts/verify_promotion.py ../reference/original-flatpack.html
