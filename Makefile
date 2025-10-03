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

# ---------------- Week 2 (HDFS → Hive → MariaDB) ----------------
# Default goal
.DEFAULT_GOAL := help

# Load .env into Make env (safe: ignores comments/empty lines)
ifneq (,$(wildcard .env))
  include .env
  export $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env)
endif

# Overridable knobs (can also come from your .env)
DC       ?= docker compose
JLAB     ?= jupyterlab
HIVE     ?= hive-server
MARIADB  ?= mariadb

WORKDIR      ?= /work

# Ingest
TW_SYMBOLS   ?= 2330.tw,2317.tw
START_DATE   ?= 2024-01-01
END_DATE     ?= auto
HDFS_PATH    ?= /data/stocks
HDFS_USER    ?= root

# Hive
HIVE_DB      ?= default
HIVE_HOST    ?= hive-server
HIVE_PORT    ?= 10000

# SQLAlchemy URL used by exporters (Hive→MariaDB and BI CSV)
MARIA_URL    ?= mysql+pymysql://user:password@mariadb:3306/market?charset=utf8mb4

# MariaDB CLI (for sourcing BI views)
MARIADB_HOST     ?= mariadb
MARIADB_PORT     ?= 3306
MARIADB_USER     ?= user
MARIADB_PASSWORD ?= password
MARIADB_DB       ?= market

# Optional DQ freshness gate (unset = no gate)
# DQ_FRESHNESS_DAYS ?= 7

# ---------------- Quality of life flags ----------------
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.ONESHELL:
.SILENT:

.PHONY: help hdfs-ingest hive-setup hive-export dq bi-views bi-export week2-all check compose-ps

help:
	echo ""
	echo "Week 2 pipeline targets:"
	echo "  hdfs-ingest   : Fetch TW stocks and write partitioned Parquet to HDFS"
	echo "  hive-setup    : Create/repair Hive external table over HDFS data"
	echo "  hive-export   : Export Hive data → MariaDB (idempotent on PK)"
	echo "  dq            : Run data quality checks (optional freshness gate)"
	echo "  bi-views      : Create BI views in MariaDB (idempotent CREATE/REPLACE)"
	echo "  bi-export     : Export BI CSVs under bi/exports/"
	echo "  week2-all     : Run full pipeline (ingest→hive→export→DQ→views→CSVs)"
	echo "  check         : Quick connectivity sanity checks"
	echo "  compose-ps    : Show running containers"
	echo ""

compose-ps:
	$(DC) ps

check:
	$(DC) exec $(HIVE) bash -lc '
	  set -euo pipefail
	  (echo > /dev/tcp/localhost/$(HIVE_PORT)) && echo HIVE_PORT_OK
	'
	$(DC) exec $(MARIADB) bash -lc '
	  set -euo pipefail
	  mariadb -u"$(MARIADB_USER)" -p"$(MARIADB_PASSWORD)" -e "SELECT 1" >/dev/null && echo MARIADB_OK
	'
	echo "CHECK_OK"


# ---------------- 1) HDFS ingest ----------------
hdfs-ingest:
	$(DC) exec $(JLAB) bash -lc '
	  cd $(WORKDIR)
	  export PYTHONPATH=$(PYTHONPATH)
	  export TW_SYMBOLS="$(TW_SYMBOLS)"
	  export START_DATE="$(START_DATE)"
	  export END_DATE="$(END_DATE)"
	  export HDFS_PATH="$(HDFS_PATH)"
	  export HDFS_USER="$(HDFS_USER)"
	  python -m etl.tw_stocks.write_parquet_hdfs
	'
	echo "INGEST_OK: wrote Parquet to $(HDFS_PATH)"

# ---------------- 2) Hive setup (idempotent DDL) ----------------
hive-setup:
	$(DC) exec $(HIVE) bash -lc '
	  /opt/hive/bin/beeline \
	    -u "jdbc:hive2://localhost:$(HIVE_PORT)/$(HIVE_DB)" -n hadoop -p "" \
	    --hivevar hive_db=$(HIVE_DB) \
	    --hivevar hdfs_path=$(HDFS_PATH) \
	    -f $(WORKDIR)/hive/create_ext_stocks.sql
	'
	echo "HIVE_OK: $(HIVE_DB).stocks_prices_raw available (MSCK repaired)"

# ---------------- 3) Export Hive → MariaDB ----------------
hive-export:
	$(DC) exec $(JLAB) bash -lc '
	  cd $(WORKDIR)
	  export PYTHONPATH=$(PYTHONPATH)
	  export MARIA_URL="$(MARIA_URL)"
	  export HIVE_HOST=$(HIVE_HOST)
	  export HIVE_PORT=$(HIVE_PORT)
	  export DEBUG=1
	  python -m tools.hive_to_mariadb
	'
	echo "EXPORT_OK: Hive → MariaDB"

# ---------------- 4) Data Quality checks ----------------
dq:
	$(DC) exec $(JLAB) bash -lc '
	  cd $(WORKDIR)
	  export PYTHONPATH=$(PYTHONPATH)
	  export MARIADB_HOST=$(MARIADB_HOST)
	  export MARIADB_PORT=$(MARIADB_PORT)
	  export MARIADB_USER=$(MARIADB_USER)
	  export MARIADB_PASSWORD=$(MARIADB_PASSWORD)
	  export MARIADB_DB=$(MARIADB_DB)
	  if [ -n "$${DQ_FRESHNESS_DAYS-}" ]; then export DQ_FRESHNESS_DAYS="$(DQ_FRESHNESS_DAYS)"; fi
	  python -m dq.run_checks
	'
	echo "DQ_OK"

# ---------------- 5) BI views in MariaDB (idempotent SQL) ----------------
# Run inside MariaDB container so host mysql client isn't required.
bi-views:
	$(DC) exec $(MARIADB) bash -lc '
	  mariadb -u"$(MARIADB_USER)" -p"$(MARIADB_PASSWORD)" -P"$(MARIADB_PORT)" -D"$(MARIADB_DB)" -e "\
	    SOURCE $(WORKDIR)/bi/sql/create_vw_symbols_dim.sql; \
	    SOURCE $(WORKDIR)/bi/sql/create_vw_prices_daily.sql; \
	  "
	'
	echo "BI_VIEWS_OK: vw_symbols_dim, vw_prices_daily"

# ---------------- 6) Export BI CSVs ----------------
bi-export:
	$(DC) exec $(JLAB) bash -lc '
	  cd $(WORKDIR)
	  export PYTHONPATH=$(PYTHONPATH)
	  export MARIA_URL="$(MARIA_URL)"
	  python -m bi.exports.export_csv
	'
	test -s "bi/exports/prices_daily.csv"
	test -s "bi/exports/symbols_dim.csv"
	echo "BI_EXPORT_OK: CSVs in bi/exports/"


# ---------------- One-shot pipeline ----------------
week2-all: hdfs-ingest hive-setup hive-export dq bi-views bi-export
	echo "WEEK2_OK"

