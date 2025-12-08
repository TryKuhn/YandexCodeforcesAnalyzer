build:
	pip3 install --upgrade pip
	pip3 install -r requirements.txt
	docker build -t yandexcodeforcesanalyzer .

lint:
	docker-compose run --rm backend ruff check .
	docker-compose run --rm backend mypy . --ignore-missing-imports

lint.fix:
	docker-compose run --rm backend black .
	docker-compose run --rm backend isort .
	docker-compose run --rm backend ruff check . --fix

test:
	docker-compose run --rm backend pytest backend/tests --cov=backend

run:
	docker-compose -f docker-compose.yml up

clean:
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -af --volumes
