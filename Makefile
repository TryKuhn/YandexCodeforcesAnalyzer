build:
	pip3 install --upgrade pip
	pip3 install -r requirements.txt
	docker build -t yandexcodeforcesanalyzer .

lint:
	docker-compose run --rm backend ruff check .
	docker-compose run --rm backend mypy . --ignore-missing-imports --explicit-package-bases

lint.fix:
	docker-compose run --rm backend black .
	docker-compose run --rm backend isort .
	docker-compose run --rm backend ruff check . --fix

test:
	docker-compose run --rm backend pytest backend/tests --cov=backend

migrate:
	docker-compose exec -T backend sh -c "alembic revision --autogenerate -m '$(msg)'"

migrate.upgrade:
	docker-compose exec -T backend sh -c "alembic upgrade head"

migrate.downgrade:
	docker-compose exec -T backend sh -c "alembic downgrade -1"

check.migrations:
	docker-compose exec postgres sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "\\dt"'

run:
	docker-compose -f docker-compose.yml up -d
	docker-compose logs -f backend

clean:
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -af --volumes
