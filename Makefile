OS_NAME := $(shell uname -s | tr A-Z a-z)
DOCKER_COMPOSE := $(shell command -v docker-compose 2> /dev/null || echo "docker compose")

ifeq ($(OS_NAME),linux)
	VENV_ACTIVATE = . .venv/bin/activate
	VENV_PIP = .venv/bin/pip
	PYTHON = python3
else ifeq ($(OS_NAME),darwin)
	VENV_ACTIVATE = . .venv/bin/activate
	VENV_PIP = .venv/bin/pip
	PYTHON = python3
else
	# Windows (Git Bash, WSL)
	VENV_ACTIVATE = . .venv/Scripts/activate
	VENV_PIP = .venv/Scripts/pip
	PYTHON = python
endif

build:
ifeq ($(OS_NAME),linux)
	# Только Linux нуждается в установке системных пакетов
	sudo apt update
	sudo apt install python3-full -y
endif
	# Общие для всех ОС действия
	$(PYTHON) -m venv .venv
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt
	docker build -t yandexcodeforcesanalyzer .

lint:
	$(DOCKER_COMPOSE) run --rm backend ruff check .
	$(DOCKER_COMPOSE) run --rm backend mypy . --ignore-missing-imports --explicit-package-bases

lint.fix:
	$(DOCKER_COMPOSE) run --rm backend black .
	$(DOCKER_COMPOSE) run --rm backend isort .
	$(DOCKER_COMPOSE) run --rm backend ruff check . --fix

test:
	$(DOCKER_COMPOSE) run --rm backend pytest backend/tests --cov=backend

migrate:
	$(DOCKER_COMPOSE) exec -T backend sh -c "alembic revision --autogenerate -m '$(msg)'"

migrate.upgrade:
	$(DOCKER_COMPOSE) exec -T backend sh -c "alembic upgrade head"

migrate.downgrade:
	$(DOCKER_COMPOSE) exec -T backend sh -c "alembic downgrade -1"

check.migrations:
	$(DOCKER_COMPOSE) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "\\dt"'

migrate.status:
	$(DOCKER_COMPOSE) exec -T backend sh -c "alembic current"

migrate.history:
	$(DOCKER_COMPOSE) exec -T backend sh -c "alembic history"

migrate.check:
	$(DOCKER_COMPOSE) exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "\\dt"'
	$(DOCKER_COMPOSE) exec -T backend sh -c "alembic current"

migrate.list:
	$(DOCKER_COMPOSE) exec -T backend sh -c "ls -la backend/alembic/versions/"

run:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d
	$(DOCKER_COMPOSE) logs -f backend

clean:
	$(DOCKER_COMPOSE) down --rmi all --volumes --remove-orphans
	docker system prune -af --volumes
