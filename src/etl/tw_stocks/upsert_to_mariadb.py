# src/etl/tw_stocks/upsert_to_mariadb.py
import os
import pandas as pd
import sqlalchemy as sa

def _build_engine() -> sa.Engine:
    url = os.getenv("MARIA_URL")
    if not url:
        host = os.getenv("MARIA_HOST", "mariadb")
        port = os.getenv("MARIA_PORT", "3306")
        db   = os.getenv("MARIA_DB",   "market")
        user = os.getenv("MARIA_USER", "user")
        pw   = os.getenv("MARIA_PASS", "password")
        url  = f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}?charset=utf8mb4"

    if os.getenv("DEBUG") == "1":
        try:
            left, _ = url.split("@", 1)
            if ":" in left:
                left = left.rsplit(":", 1)[0] + ":***"
            print("MARIA_URL_EFFECTIVE:", left + "@…")
        except Exception:
            pass

    return sa.create_engine(url, pool_pre_ping=True, future=True)

_ENGINE = None
def get_engine() -> sa.Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _build_engine()
    return _ENGINE

def upsert_prices(df: pd.DataFrame) -> int:
    required = ["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    df = df.copy()
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce").dt.date
    df["symbol"] = df["symbol"].astype(str).str.strip().str.lower()

    eng = get_engine()
    with eng.begin() as cxn:
        cxn.exec_driver_sql("""
            CREATE DATABASE IF NOT EXISTS market
            CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)

        cxn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS market.prices_daily (
              dt DATE NOT NULL,
              symbol VARCHAR(32) NOT NULL,
              open  DECIMAL(18,4) NOT NULL,
              high  DECIMAL(18,4) NOT NULL,
              low   DECIMAL(18,4) NOT NULL,
              close DECIMAL(18,4) NOT NULL,
              volume BIGINT NOT NULL,
              vwap DECIMAL(18,6) NOT NULL,
              is_trading_day TINYINT NOT NULL,
              PRIMARY KEY (symbol, dt)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        insert_sql = sa.text("""
            INSERT INTO market.prices_daily
              (dt, symbol, open, high, low, close, volume, vwap, is_trading_day)
            VALUES
              (:dt, :symbol, :open, :high, :low, :close, :volume, :vwap, :is_trading_day)
            ON DUPLICATE KEY UPDATE
              open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close),
              volume=VALUES(volume), vwap=VALUES(vwap), is_trading_day=VALUES(is_trading_day)
        """)

        data = df[required].to_dict(orient="records")
        if data:
            cxn.execute(insert_sql, data)
        return len(data)
