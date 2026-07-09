.PHONY: install dev test lint format run docker-build docker-up

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt -r requirements-dev.txt
	pre-commit install

test:
	pytest -v

lint:
	ruff check src tests
	mypy src

format:
	ruff format src tests

run:
	uvicorn src.api.main:app --reload

docker-build:
	docker compose build

docker-up:
	docker compose up
