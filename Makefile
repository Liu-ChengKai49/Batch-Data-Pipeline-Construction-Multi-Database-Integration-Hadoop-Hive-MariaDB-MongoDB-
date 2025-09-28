# Use both so tests can also import from repo root if needed
PYTHONPATH := src:.
export PYTHONPATH

.PHONY: install lint type unit integ test up-ci down-ci smoke-ci \
        hdfs-ingest hive-setup hive-export dq bi-views bi-export week2-all

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

# ---------- Week 2 (HDFS → Hive → MariaDB) ----------

hdfs-ingest:
	python -m etl.tw_stocks.write_parquet_hdfs

hive-setup:
	HDFS_PATH=/data/stocks HIVE_DB=default \
	docker compose exec hive-server bash -lc "\
	  beeline -u 'jdbc:hive2://localhost:10000/$${HIVE_DB}' -n hadoop -p '' \
	  --hivevar hive_db=$${HIVE_DB} --hivevar hdfs_path=$${HDFS_PATH} \
	  -f /work/hive/create_ext_stocks.sql"

hive-export:
	python -m tools.hive_to_mariadb

dq:
	python -m dq.run_checks

bi-views:
	mysql -h 127.0.0.1 -u user -p -e "SOURCE bi/sql/create_vw_symbols_dim.sql; SOURCE bi/sql/create_vw_prices_daily.sql;"

bi-export:
	python -m bi.exports.export_csv

# one-shot pipeline for Week 2
week2-all: hdfs-ingest hive-setup hive-export dq bi-views bi-export
	@echo "WEEK2_OK"
