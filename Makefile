DOCKER_COMPOSE := docker compose

DEV := docker-compose.dev.yml
PROD := docker-compose.prod.yml

# Startup and shutdown

dev.up:
	$(DOCKER_COMPOSE) -f $(DEV) up -d --build

prod.up:
	$(DOCKER_COMPOSE) -f $(PROD) up -d --build

dev.down:
	$(DOCKER_COMPOSE) -f $(DEV) down

prod.down:
	$(DOCKER_COMPOSE) -f $(PROD) down

prod.restart:
	$(DOCKER_COMPOSE) -f $(PROD) restart

# Logs

dev.logs:
	$(DOCKER_COMPOSE) -f $(DEV) logs -f

prod.logs:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f

dev.logs.be:
	$(DOCKER_COMPOSE) -f $(DEV) logs -f backend

prod.logs.be:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f backend

dev.logs.fe:
	$(DOCKER_COMPOSE) -f $(DEV) logs -f frontend

prod.logs.fe:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f frontend

prod.logs.caddy:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f caddy

# Testing and linting

dev.test:
	$(DOCKER_COMPOSE) -f $(DEV) exec backend pytest tests --cov=backend

dev.lint:
	$(DOCKER_COMPOSE) -f $(DEV) exec backend ruff check .
	$(DOCKER_COMPOSE) -f $(DEV) exec backend mypy . --ignore-missing-imports --explicit-package-bases

dev.lint.fix:
	$(DOCKER_COMPOSE) -f $(DEV) exec backend black .
	$(DOCKER_COMPOSE) -f $(DEV) exec backend isort .
	$(DOCKER_COMPOSE) -f $(DEV) exec backend ruff check . --fix

# Migrations

dev.migrate:
	$(DOCKER_COMPOSE) -f $(DEV) exec -T backend alembic revision --autogenerate -m "$(msg)"

dev.migrate.upgrade:
	$(DOCKER_COMPOSE) -f $(DEV) exec -T backend alembic upgrade head

dev.migrate.downgrade:
	$(DOCKER_COMPOSE) -f $(DEV) exec -T backend alembic downgrade -1

prod.migrate.downgrade:
	$(DOCKER_COMPOSE) -f $(PROD) exec -T backend alembic downgrade -1

dev.migrate.check:
	$(DOCKER_COMPOSE) -f $(DEV) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "\\dt"'
	$(DOCKER_COMPOSE) -f $(DEV) exec -T backend alembic current

prod.migrate.check:
	$(DOCKER_COMPOSE) -f $(PROD) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "\\dt"'
	$(DOCKER_COMPOSE) -f $(PROD) exec -T backend alembic current

# Database shell

dev.db.shell:
	$(DOCKER_COMPOSE) -f $(DEV) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

prod.db.shell:
	$(DOCKER_COMPOSE) -f $(PROD) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

# Cleanup
dev.clean:
	$(DOCKER_COMPOSE) -f $(DEV) down --rmi all --volumes --remove-orphans
	docker system prune -af --volumes

prod.clean:
	$(DOCKER_COMPOSE) -f $(PROD) down --rmi all --volumes --remove-orphans
