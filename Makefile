build:
	pip3 install --upgrade pip
	pip3 install -r requirements.txt
	docker build -t yandexcodeforcesanalyzer .

lint:
	docker-compose run backend ruff check .
	docker-compose run backend mypy . --ignore-missing-imports

lint.fix:
	docker-compose run backend black .
	docker-compose run backend isort .
	docker-compose run backend ruff check . --fix

test:
	docker-compose run backend pytest backend/tests --cov=backend

run:
	docker-compose -f docker-compose.yml up

build-run:
	docker-compose -f docker-compose.yml up --build
