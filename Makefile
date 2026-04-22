ifeq ($(OS),Windows_NT)
	DC_KIND := $(shell docker-compose version >nul 2>nul && echo v1 || echo v2)
	VENV_ACTIVATE = . .venv/Scripts/activate
	VENV_PIP = .venv/Scripts/pip
	PYTHON = python
else
	DC_KIND := $(shell command -v docker-compose >/dev/null 2>&1 && echo v1 || echo v2)
	VENV_ACTIVATE = . .venv/bin/activate
	VENV_PIP = .venv/bin/pip
	PYTHON = python3
endif

ifeq ($(DC_KIND),v1)
	DOCKER_COMPOSE := docker-compose
else
	DOCKER_COMPOSE := docker compose
endif

up:
	$(DOCKER_COMPOSE) up -d --build

down:
	$(DOCKER_COMPOSE) down

logs.be:
	$(DOCKER_COMPOSE) logs -f backend

logs.fe:
	$(DOCKER_COMPOSE) logs -f frontend

lint:
	$(DOCKER_COMPOSE) exec backend ruff check .
	$(DOCKER_COMPOSE) exec backend mypy . --ignore-missing-imports --explicit-package-bases

lint.fix:
	$(DOCKER_COMPOSE) exec backend black .
	$(DOCKER_COMPOSE) exec backend isort .
	$(DOCKER_COMPOSE) exec backend ruff check . --fix

test:
	$(DOCKER_COMPOSE) exec backend pytest backend/tests --cov=backend

migrate:
	$(DOCKER_COMPOSE) exec -T backend alembic revision --autogenerate -m "$(msg)"

migrate.upgrade:
	$(DOCKER_COMPOSE) exec -T backend alembic upgrade head

migrate.downgrade:
	$(DOCKER_COMPOSE) exec -T backend alembic downgrade -1

check.migrations:
	$(DOCKER_COMPOSE) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "\\dt"'

migrate.status:
	$(DOCKER_COMPOSE) exec -T backend alembic current

migrate.check:
	$(MAKE) check.migrations
	$(MAKE) migrate.status

db.shell:
	$(DOCKER_COMPOSE) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

clean:
	$(DOCKER_COMPOSE) down --rmi all --volumes --remove-orphans
	docker system prune -af --volumes
