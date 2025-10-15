# tests/integration/test_mariadb_slice.py
import time

import pandas as pd

from batch_pipeline.db import mariadb_conn, upsert_prices
from batch_pipeline.etl import clean_prices


def _wait_db():
    for _ in range(60):
        try:
            with mariadb_conn():
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError("MariaDB not ready")

def _ensure_mart_view():
    # Make the mart mirror the base table for the test
    with mariadb_conn() as c, c.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE VIEW prices_daily_mart AS
            SELECT dt, symbol, open, high, low, close, volume, vwap, is_trading_day
            FROM prices_daily
        """)

def test_upsert_slice():
    _wait_db()
    _ensure_mart_view()

    raw = pd.DataFrame([
    {"symbol": "2330", "dt": "2025-09-01", "open": 100, "high": 110, "low": 90,
     "close": 120, "volume": 5, "vwap": 120, "is_trading_day": 1},
    {"symbol": "2330", "dt": "2025-09-01", "open": 100, "high": 110, "low": 90,
     "close": 105, "volume": 6, "vwap": 105, "is_trading_day": 1},
    ])
    df = clean_prices(raw)

    # Use whatever symbol/date clean_prices actually outputs (avoid hardcoding)
    sym = str(df.loc[0, "symbol"])          # e.g., "2330.TW"
    dt  = str(df.loc[0, "dt"])[:10]         # ensure "YYYY-MM-DD"

    n = upsert_prices(df.to_dict("records"))
    assert n >= 1

    # Query with parameters (and ensure we see the committed result)
    with mariadb_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS c
            FROM prices_daily_mart
            WHERE symbol=%s AND dt=%s
        """, (sym, dt))
        assert cur.fetchone()["c"] == 1
