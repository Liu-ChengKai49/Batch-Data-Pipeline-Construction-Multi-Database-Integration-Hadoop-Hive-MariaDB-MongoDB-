# src/tools/hive_to_mariadb.py
import os
import pandas as pd
from pyhive import hive
from etl.tw_stocks.upsert_to_mariadb import upsert_prices

HIVE_HOST = os.environ.get("HIVE_HOST", "hive-server")
HIVE_PORT = int(os.environ.get("HIVE_PORT", "10000"))
HIVE_DB   = os.environ.get("HIVE_DB", "default")

START_DATE = os.environ.get("START_DATE", "2024-01-01")
END_DATE   = os.environ.get("END_DATE")
SYMS_ENV   = os.environ.get("TW_SYMBOLS", "").strip()
SYMBOLS    = [s.strip().lower() for s in SYMS_ENV.split(",") if s.strip()] if SYMS_ENV else []
DEBUG      = os.environ.get("DEBUG", "0") == "1"

def read_from_hive(sql: str) -> pd.DataFrame:
    conn = hive.Connection(host=HIVE_HOST, port=HIVE_PORT, username="hadoop", database=HIVE_DB)
    try:
        return pd.read_sql(sql, conn)
    finally:
        try: conn.close()
        except: pass

def _build_sql() -> str:
    where_lines = [f"dt >= DATE '{START_DATE}'"]
    if END_DATE:
        where_lines.append(f"dt <= DATE '{END_DATE}'")
    base_where = " AND ".join(where_lines)

    sym_filter = ""
    if SYMBOLS:
        syms = [s.replace("'", "''") for s in SYMBOLS]
        sym_list = ",".join(f"'{s}'" for s in syms)
        sym_filter = f" AND LOWER(symbol) IN ({sym_list})"

    return f"""
    WITH raw AS (
      SELECT
        CAST(dt AS DATE)                             AS dt,
        TRIM(LOWER(symbol))                          AS symbol,
        TRIM(CAST(open  AS STRING))                  AS open_s,
        TRIM(CAST(high  AS STRING))                  AS high_s,
        TRIM(CAST(low   AS STRING))                  AS low_s,
        TRIM(CAST(close AS STRING))                  AS close_s,
        TRIM(CAST(volume AS STRING))                 AS volume_s,
        TRIM(CAST(vwap   AS STRING))                 AS vwap_s,
        TRIM(CAST(is_trading_day AS STRING))         AS flag_s
      FROM {HIVE_DB}.stocks_prices_raw
      WHERE {base_where}{sym_filter}
    ),
    norm AS (
      SELECT
        dt, symbol,
        NULLIF(open_s,   '')  AS open_s,
        NULLIF(high_s,   '')  AS high_s,
        NULLIF(low_s,    '')  AS low_s,
        NULLIF(close_s,  '')  AS close_s,
        NULLIF(volume_s, '')  AS volume_s,
        NULLIF(vwap_s,   '')  AS vwap_s,
        NULLIF(flag_s,   '')  AS flag_s
      FROM raw
    ),
    num AS (
      SELECT
        dt,
        symbol,
        CAST(regexp_replace(open_s,   ',', '') AS DECIMAL(18,4))  AS open,
        CAST(regexp_replace(high_s,   ',', '') AS DECIMAL(18,4))  AS high,
        CAST(regexp_replace(low_s,    ',', '') AS DECIMAL(18,4))  AS low,
        CAST(regexp_replace(close_s,  ',', '') AS DECIMAL(18,4))  AS close,
        CAST(regexp_replace(volume_s, ',', '') AS BIGINT)         AS volume,
        CAST(regexp_replace(vwap_s,   ',', '') AS DECIMAL(18,6))  AS vwap,
        CASE
          WHEN flag_s IN ('0','1') THEN CAST(flag_s AS TINYINT)
          WHEN CAST(regexp_replace(volume_s, ',', '') AS BIGINT) > 0 THEN CAST(1 AS TINYINT)
          ELSE CAST(0 AS TINYINT)
        END AS is_trading_day
      FROM norm
    )
    SELECT
      dt, symbol, open, high, low, close, volume, vwap, is_trading_day
    FROM num
    WHERE dt IS NOT NULL
      AND symbol IS NOT NULL
      AND open  IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
      AND volume IS NOT NULL
      AND open  >= 0 AND high >= 0 AND low >= 0 AND close >= 0 AND volume >= 0
      AND high >= low
    """

def main() -> None:
    sql = _build_sql()
    df = read_from_hive(sql)
    df.columns = [c.split(".")[-1] for c in df.columns]
    df["symbol"] = df["symbol"].astype("string").str.strip().str.lower()
    if DEBUG:
        print("rows:", len(df))
        print("head:\n", df.head(3).to_string(index=False))
    n = upsert_prices(df)
    print(f"UPSERT_FROM_HIVE rows={n}")

if __name__ == "__main__":
    main()
