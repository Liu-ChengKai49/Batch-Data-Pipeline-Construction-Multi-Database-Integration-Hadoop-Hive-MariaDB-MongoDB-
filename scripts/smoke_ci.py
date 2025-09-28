import os
import time

import pandas as pd

from batch_pipeline.db import mariadb_conn, upsert_prices
from batch_pipeline.etl import clean_prices

# ← Must match compose.ci.yaml
os.environ.setdefault("MARIADB_HOST", "127.0.0.1")
os.environ.setdefault("MARIADB_PORT", "3306")
os.environ.setdefault("MARIADB_USER", "root")
os.environ.setdefault("MARIADB_PASSWORD", "root")
os.environ.setdefault("MARIADB_DB", "demo")

def wait_for_mariadb(timeout_sec: int = 60) -> None:
    start = time.time()
    for _ in range(timeout_sec):
        try:
            with mariadb_conn():
                return
        except Exception as e:
            elapsed = int(time.time() - start)
            print(f"⏳ waiting for MariaDB… ({elapsed}s) reason={e.__class__.__name__}", flush=True)
            time.sleep(1)
    raise SystemExit("MariaDB not ready")

def fetch_count(cur) -> int:
    row = cur.fetchone()
    if row is None:
        return 0
    return row["cnt"] if isinstance(row, dict) else row[0]

wait_for_mariadb()

df = pd.DataFrame(
    [
        {"symbol": "2330", "dt": "2024-01-01", "open": 100, "high": 110, "low": 90, "close": 95, "volume": 10},
        {"symbol": "2330", "dt": "2024-01-02", "open": 95,  "high": 105, "low": 92, "close": 101, "volume": 12},
        {"symbol": "2454", "dt": "2024-01-02", "open": 50,  "high": 55,  "low": 49, "close": 54,  "volume": 5},
    ]
)

df = clean_prices(df)

with mariadb_conn() as conn:
    upsert_prices(conn, df.to_dict("records"))
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM demo.prices_daily;")
        rows = fetch_count(cur)

print("SMOKE OK: rows=", rows)
