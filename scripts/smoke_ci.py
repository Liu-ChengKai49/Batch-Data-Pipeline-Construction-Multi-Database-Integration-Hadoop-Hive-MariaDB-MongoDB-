import time, pandas as pd
from batch_pipeline.db import mariadb_conn, upsert_prices
from batch_pipeline.etl import clean_prices

for _ in range(60):
    try:
        with mariadb_conn(): break
    except Exception: time.sleep(1)
else:
    raise SystemExit("MariaDB not ready")

raw = pd.DataFrame([
    {"symbol":"TEST1","dt":"2025-01-01","open":10,"high":12,"low":9,"close":15,"volume":1000},
    {"symbol":"TEST1","dt":"2025-01-02","open":12,"high":12.5,"low":11,"close":12.4,"volume":800},
    {"symbol":"TEST2","dt":"2025-01-01","open":20,"high":21,"low":19.5,"close":19,"volume":500},
])
df = clean_prices(raw)
upsert_prices(df.to_dict("records"))
with mariadb_conn() as c, c.cursor() as cur:
    cur.execute("SELECT COUNT(*) AS c FROM prices_daily_mart")
    total = cur.fetchone()["c"]
    assert total == 3
print("SMOKE OK: rows=", total)
