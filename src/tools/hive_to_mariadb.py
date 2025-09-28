# tools/hive_to_mariadb.py
import os, pandas as pd
from pyhive import hive
from etl.tw_stocks.upsert_to_mariadb import upsert_prices

HIVE_HOST = os.environ.get("HIVE_HOST","hive-server")
HIVE_PORT = int(os.environ.get("HIVE_PORT","10000"))
HIVE_DB   = os.environ.get("HIVE_DB","default")

def read_from_hive(sql: str) -> pd.DataFrame:
    conn = hive.Connection(host=HIVE_HOST, port=HIVE_PORT, username="hadoop", database=HIVE_DB)
    return pd.read_sql(sql, conn)

if __name__ == "__main__":
    q = """
      SELECT
        CAST(dt AS DATE) AS dt,
        symbol,
        CAST(open AS DECIMAL(18,4))  AS open,
        CAST(high AS DECIMAL(18,4))  AS high,
        CAST(low  AS DECIMAL(18,4))  AS low,
        CAST(close AS DECIMAL(18,4)) AS close,
        CAST(volume AS BIGINT)       AS volume,
        CAST(vwap AS DECIMAL(18,6))  AS vwap,
        CAST(is_trading_day AS TINYINT) AS is_trading_day
      FROM stocks_prices_raw
      WHERE dt >= DATE '2024-01-01'
    """
    df = read_from_hive(q)
    n = upsert_prices(df)
    print(f"UPSERT_FROM_HIVE rows={n}")