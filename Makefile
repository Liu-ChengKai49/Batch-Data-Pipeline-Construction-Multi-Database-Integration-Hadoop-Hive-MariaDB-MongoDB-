PYTHONPATH := src
export PYTHONPATH

.PHONY: install lint type unit integ test up-ci down-ci smoke-ci

install:
	python -m pip install -U pip
	pip install ".[dev]"

lint:
	ruff check .

type:
	mypy src

unit:
	pytest -q tests/unit --cov=src --cov-fail-under=85

integ:
	pytest -q tests/integration

test: unit integ

up-ci:
	docker compose -f compose.ci.yaml up -d 

down-ci:
	docker compose -f compose.ci.yaml down -v

smoke-ci: up-ci
	python scripts/smoke_ci.py
	$(MAKE) down-ci
