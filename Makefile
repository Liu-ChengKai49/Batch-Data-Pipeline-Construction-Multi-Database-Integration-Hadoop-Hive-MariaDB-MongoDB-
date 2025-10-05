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
	docker compose -f compose.ci.yaml up -d --remove-orphans
	docker compose -f compose.ci.yaml ps

down-ci:
	docker compose -f compose.ci.yaml down -v

smoke-ci:
	set -euo pipefail
	docker compose -f compose.ci.yaml up -d --remove-orphans
	echo "[wait] checking MariaDB..."
	cid=$$(docker compose -f compose.ci.yaml ps -q mariadb)
	for i in $$(seq 1 60); do
	  if docker exec $$cid mariadb-admin ping -h 127.0.0.1 -uroot -proot >/dev/null 2>&1; then
	    echo "[wait] MariaDB is alive after $$i tries"
	    break
	  fi
	  echo "[wait] ... still waiting ($$i/60)"
	  sleep 2
	done
	echo "[smoke] running scripts/smoke_ci.py ..."
	MARIADB_HOST=127.0.0.1 MARIADB_PORT=3306 \
	MARIADB_USER=demo MARIADB_PASSWORD=demo MARIADB_DB=demo \
	python -u scripts/smoke_ci.py
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

.PHONY: help hdfs-ingest hive-setup hive-export dq bi-views bi-export week2-all check compose-ps \
        deps-jlab deps-jlab-check sheets-sync-jlab
help:
	@echo ""
	@echo "Week 2 pipeline targets:"
	@echo "  hdfs-ingest   : Fetch TW stocks and write partitioned Parquet to HDFS"
	@echo "  hive-setup    : Create/repair Hive external table over HDFS data"
	@echo "  hive-export   : Export Hive data → MariaDB (idempotent on PK)"
	@echo "  dq            : Run data quality checks (optional freshness gate)"
	@echo "  bi-base      : Create base tables in MariaDB (idempotent CREATE)"
	@echo "  bi-views      : Create BI views in MariaDB (idempotent CREATE/REPLACE)"
	@echo "  bi-export     : Export BI CSVs under bi/exports/"
	@echo "  week2-all     : Run full pipeline (ingest→hive→export→DQ→views→CSVs)"
	@echo "  check         : Quick connectivity sanity checks"
	@echo "  compose-ps    : Show running containers"
	@echo ""
	@echo "Week 3 setup:"
	@echo "  deps-jlab     : Install all Python deps inside jupyterlab (editable + extras)"
	@echo "  deps-jlab-check : Verify core libs import correctly"
	@echo "  sheets-sync-jlabSync BI CSVs to Google Sheets from inside jupyterlab"
	@echo ""


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

deps-jlab:
	@echo "[deps-jlab] installing project dependencies in jupyterlab..."
	@docker compose exec jupyterlab bash -lc 'set -euo pipefail
	echo "[deps] python=$$(python -V)  pip=$$(pip -V)"
	# remove conflicting pkgs you don’t use
	pip uninstall -y numba llvmlite >/dev/null 2>&1 || true
	pip uninstall -y backports       >/dev/null 2>&1 || true
	# build tooling
	python -m pip install -U pip setuptools wheel packaging
	python -m pip install -U backports.tarfile
	cd /work
	# install your project
	pip install -e .
	pip install -e ".[dev,hive,bi]" || true
	echo "[deps] done."
	'


deps-jlab-check:
	@docker compose exec jupyterlab bash -lc '\
	  set -euo pipefail; \
	  python -c "import pandas,sqlalchemy,fastapi; print(\"ok:pandas=%s sqlalchemy=%s\"%(pandas.__version__, sqlalchemy.__version__))"; \
	  python -c "import prometheus_client; print(\"ok:prometheus\")"; \
	  python -c "import pymysql; print(\"ok:pymysql\")"; \
	  python -c "import gspread,oauth2client; print(gspread.__version__)"; \
	'
# ---------------- 1) HDFS ingest ----------------
hdfs-ingest:
	@set -euo pipefail; \
	echo "[hdfs-ingest] deriving NEXT_START from HDFS under $(HDFS_PATH)"; \
	# 1) get LAST=latest dt=YYYY-MM-DD seen in HDFS (sed avoids awk '$$2' quoting fights)
	set +e; \
	LAST=$$( docker compose exec -T namenode bash -c '\
	  set -euo pipefail; \
	  hdfs dfs -ls -R $(HDFS_PATH) 2>/dev/null \
	    | sed -n '\''s/.*dt=\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\).*/\1/p'\'' \
	    | sort | tail -1' | tr -d "\r" ); \
	rc=$$?; set -e; \
	if [ $$rc -ne 0 ]; then \
	  echo "[hdfs-ingest] WARN: could not scan HDFS; falling back to 2024-01-01"; \
	  LAST=""; \
	fi; \
	# 2) compute NEXT_START = LAST + 1 day, but never beyond (today - 1)
	if [ -n "$$LAST" ]; then \
	  CAND=$$(date -d "$$LAST +1 day" +%F); \
	else \
	  CAND=2024-01-01; \
	fi; \
	YEST=$$(date -d "yesterday" +%F); \
	# clamp CAND to YEST if it overshoots
	if [[ "$$CAND" > "$$YEST" ]]; then NEXT_START="$$YEST"; else NEXT_START="$$CAND"; fi; \
	echo "[hdfs-ingest] LAST=$${LAST:-none}  ->  NEXT_START=$$NEXT_START  (YEST=$$YEST)"; \
	# 3) run ETL for missing tail only
	echo "[hdfs-ingest] launching ETL in $(JLAB)"; \
	docker compose exec $(JLAB) bash -lc '\
	  set -euo pipefail; \
	  cd $(WORKDIR); \
	  export PYTHONPATH=$(PYTHONPATH); \
	  export TW_SYMBOLS="$(TW_SYMBOLS)"; \
	  export START_DATE="'"$$NEXT_START"'"; \
	  export END_DATE="$(END_DATE)"; \
	  export HDFS_PATH="$(HDFS_PATH)"; \
	  export HDFS_USER="$(HDFS_USER)"; \
	  python -m etl.tw_stocks.write_parquet_hdfs \
	'; \
	echo "[hdfs-ingest] OK: wrote Parquet to $(HDFS_PATH)"	
	
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

bi-base:
	$(DC) exec $(MARIADB) bash -lc '\
	  mariadb -u"$(MARIADB_USER)" -p"$(MARIADB_PASSWORD)" -P"$(MARIADB_PORT)" -D"$(MARIADB_DB)" -e "\
	    SOURCE $(WORKDIR)/bi/sql/create_base_tables.sql; \
	  " \
	'
	echo "BI_BASE_OK: symbols_dim, prices_daily"

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

# ---------------- 7) Google Sheets sync ----------------
sheets-sync-jlab:
	@echo "[sheets] exporting to Google Sheets from inside jupyterlab..."
	@docker compose exec -T \
		-e SHEETS_DOC_ID="$(SHEETS_DOC_ID)" \
		-e MARIA_URL="$(MARIA_URL)" \
		-e GOOGLE_SA_JSON="$(GOOGLE_SA_JSON)" \
		jupyterlab bash -lc 'set -euo pipefail; cd /work; \
			python bi/sheets_sync/export_to_sheets.py'



# ---------------- One-shot pipeline ----------------
week2-all: deps-jlab hdfs-ingest hive-setup hive-export dq bi-base bi-views bi-export
	echo "WEEK2_OK"

