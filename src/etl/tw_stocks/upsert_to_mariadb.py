# # src/etl/tw_stocks/upsert_to_mariadb.py
# import os, pandas as pd, sqlalchemy as sa
# from dotenv import load_dotenv; load_dotenv()

# ENGINE = sa.create_engine(os.environ["MARIADB_URL"], pool_pre_ping=True)

# def upsert_prices(df: pd.DataFrame) -> int:
#     if df is None or df.empty:
#         return 0
#     cols = ["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"]
#     rows = df[cols].to_dict(orient="records")
#     sql = """
#     INSERT INTO market.prices_daily
#       (dt, symbol, open, high, low, close, volume, vwap, is_trading_day)
#     VALUES
#       (:dt, :symbol, :open, :high, :low, :close, :volume, :vwap, :is_trading_day)
#     ON DUPLICATE KEY UPDATE
#       open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close),
#       volume=VALUES(volume), vwap=VALUES(vwap), is_trading_day=VALUES(is_trading_day)
#     """
#     with ENGINE.begin() as cxn:
#         cxn.execute(sa.text(sql), rows)
#     return len(rows)

# upsert_to_mariadb.py
from __future__ import annotations
import os
import pandas as pd
import sqlalchemy as sa

def _engine():
    uri = (
        f"mariadb+pymysql://{os.getenv('MARIADB_USER','user')}:{os.getenv('MARIADB_PASSWORD','password')}"
        f"@{os.getenv('MARIADB_HOST','mariadb')}:{int(os.getenv('MARIADB_PORT','3306'))}"
        f"/{os.getenv('MARIADB_DB','market')}"
    )
    return sa.create_engine(uri, pool_pre_ping=True)

def upsert_prices(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0

    cols = ["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    # --- Strong dtype hygiene ---
    df = df.loc[:, cols].copy()
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce").dt.date
    df["symbol"] = df["symbol"].astype(str)

    # cast numerics; if something can’t parse -> NaN -> becomes NULL in DB
    for c in ["open","high","low","close","vwap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce", downcast="integer")
    df["is_trading_day"] = (
        pd.to_numeric(df["is_trading_day"], errors="coerce", downcast="integer")
        .fillna(0).astype(int)
    )

    # Optional safety: ensure we’re not about to write rows with *all* numeric NULLs
    numerics = ["open","high","low","close","volume","vwap"]
    if int(df[numerics].notna().any(axis=1).sum()) == 0:
        raise ValueError("All numeric fields are NULL for all rows — check upstream transform.")

    rows = df.to_dict(orient="records")
    if not rows:
        return 0

    # MySQL 8.0.20+: prefer alias ‘new’ instead of VALUES()
    sql = sa.text("""
        INSERT INTO market.prices_daily
          (dt, symbol, open, high, low, close, volume, vwap, is_trading_day)
        VALUES
          (:dt, :symbol, :open, :high, :low, :close, :volume, :vwap, :is_trading_day)
        AS new
        ON DUPLICATE KEY UPDATE
          open = new.open,
          high = new.high,
          low  = new.low,
          close= new.close,
          volume = new.volume,
          vwap   = new.vwap,
          is_trading_day = new.is_trading_day
    """)

    eng = _engine()
    with eng.begin() as cxn:
        cxn.execute(sql, rows)

    return len(rows)
