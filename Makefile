.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: init
init: ## Create .env from the template (first-time setup)
	@test -f .env || (cp .env.example .env && echo "✓ .env created from .env.example")
	@test -f .env && echo "✓ .env ready"

.PHONY: up
up: init ## Build and start the full stack (dev, hot reload)
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  web      → http://localhost:3000"
	@echo "  api docs → http://localhost:8000/docs"
	@echo "  minio    → http://localhost:9001"
	@echo ""
	@echo "  Seeded logins (password for all: Passw0rd!)"
	@echo "    manager   → manager@matchify.dev"
	@echo "    candidate → nikos@example.com"
	@echo ""

.PHONY: down
down: ## Stop all containers
	$(COMPOSE) down

.PHONY: clean
clean: ## Stop containers AND delete all data volumes
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail logs from every service
	$(COMPOSE) logs -f

.PHONY: logs-api
logs-api: ## Tail API logs only
	$(COMPOSE) logs -f api

.PHONY: logs-web
logs-web: ## Tail web logs only
	$(COMPOSE) logs -f web

.PHONY: seed
seed: ## Fill the database with demo data (wipes existing demo data first)
	$(COMPOSE) exec api python -m app.db.seed --reset

.PHONY: unseed
unseed: ## Remove all demo data, leaving the app empty (keeps the company)
	$(COMPOSE) exec api python -m app.db.seed --clear

.PHONY: test
test: ## Run the backend test suite
	$(COMPOSE) exec api pytest -q

.PHONY: shell-api
shell-api: ## Shell into the API container
	$(COMPOSE) exec api bash

.PHONY: shell-db
shell-db: ## Open a mongosh shell
	$(COMPOSE) exec mongo mongosh matchify

.PHONY: types
types: ## Regenerate TypeScript types from the FastAPI OpenAPI schema
	@curl -s http://localhost:8000/openapi.json -o packages/api-types/openapi.json
	@cd apps/web && pnpm exec openapi-typescript ../../packages/api-types/openapi.json \
		-o ../../packages/api-types/index.ts
	@echo "✓ packages/api-types/index.ts regenerated"

.PHONY: prod
prod: ## Run the production-shaped stack (no bind mounts, no hot reload)
	$(COMPOSE) -f docker-compose.yml up --build -d
