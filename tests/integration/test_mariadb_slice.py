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

def test_upsert_slice():
    _wait_db()
    raw = pd.DataFrame([
        {"symbol":"2330","dt":"2025-09-01","open":100,"high":110,"low":90,"close":120,"volume":5},
        {"symbol":"2330","dt":"2025-09-01","open":100,"high":110,"low":90,"close":105,"volume":6},
    ])
    df = clean_prices(raw)
    n = upsert_prices(df.to_dict("records"))
    assert n >= 1
    with mariadb_conn() as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM prices_daily_mart WHERE symbol='2330'")
        assert cur.fetchone()["c"] == 1
