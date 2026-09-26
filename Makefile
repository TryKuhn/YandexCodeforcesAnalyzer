DOCKER_COMPOSE := docker compose

DEV := docker-compose.dev.yml
PROD := docker-compose.prod.yml

IMAGE_TAG ?= latest

# our own images (worker runs on the backend image); postgres/redis/minio/caddy
# are left alone so a pull can't silently upgrade them
APP_SERVICES := backend worker judge frontend frontend-participant

# Startup and shutdown

dev.up:
	$(DOCKER_COMPOSE) -f $(DEV) up -d --build

prod.up:
	IMAGE_TAG=$(IMAGE_TAG) $(DOCKER_COMPOSE) -f $(PROD) up -d --remove-orphans

prod.pull:
	IMAGE_TAG=$(IMAGE_TAG) $(DOCKER_COMPOSE) -f $(PROD) pull --quiet $(APP_SERVICES)

dev.down:
	$(DOCKER_COMPOSE) -f $(DEV) down

prod.down:
	$(DOCKER_COMPOSE) -f $(PROD) down

prod.restart:
	$(DOCKER_COMPOSE) -f $(PROD) restart

# the worker has no auto-reload, even in dev
dev.restart.worker:
	$(DOCKER_COMPOSE) -f $(DEV) restart worker

# the Caddyfile is bind-mounted, `up` does not pick up edits to it
prod.caddy.reload:
	$(DOCKER_COMPOSE) -f $(PROD) exec -T caddy caddy reload --config /etc/caddy/Caddyfile

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

dev.logs.fe.participant:
	$(DOCKER_COMPOSE) -f $(DEV) logs -f frontend-participant

prod.logs.fe.participant:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f frontend-participant

dev.logs.worker:
	$(DOCKER_COMPOSE) -f $(DEV) logs -f worker

prod.logs.worker:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f worker

dev.logs.judge:
	$(DOCKER_COMPOSE) -f $(DEV) logs -f judge

prod.logs.judge:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f judge

prod.logs.caddy:
	$(DOCKER_COMPOSE) -f $(PROD) logs -f caddy

# Testing and linting

dev.test:
	$(DOCKER_COMPOSE) -f $(DEV) exec backend pytest -q --tb=short

dev.lint:
	$(DOCKER_COMPOSE) -f $(DEV) exec backend ruff check .
	$(DOCKER_COMPOSE) -f $(DEV) exec backend mypy . --ignore-missing-imports --explicit-package-bases

dev.lint.fix:
	$(DOCKER_COMPOSE) -f $(DEV) exec backend black .
	$(DOCKER_COMPOSE) -f $(DEV) exec backend isort .
	$(DOCKER_COMPOSE) -f $(DEV) exec backend ruff check . --fix

# judge has no runtime deps, so its checks run locally, without Docker
judge.test:
	cd backend/judge && pytest -q --tb=short

judge.lint:
	cd backend/judge && ruff check . && mypy app --ignore-missing-imports

# Migrations

dev.migrate:
	$(DOCKER_COMPOSE) -f $(DEV) exec -T backend alembic revision --autogenerate -m "$(msg)"

dev.migrate.upgrade:
	$(DOCKER_COMPOSE) -f $(DEV) exec -T backend alembic upgrade head

dev.migrate.downgrade:
	$(DOCKER_COMPOSE) -f $(DEV) exec -T backend alembic downgrade -1

prod.migrate.upgrade:
	$(DOCKER_COMPOSE) -f $(PROD) exec -T backend alembic upgrade head

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
