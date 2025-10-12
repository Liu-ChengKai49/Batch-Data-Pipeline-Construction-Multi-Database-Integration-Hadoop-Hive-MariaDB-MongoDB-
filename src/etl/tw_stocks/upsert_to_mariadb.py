# src/etl/tw_stocks/upsert_to_mariadb.py
import os
from typing import Optional

import pandas as pd
import sqlalchemy as sa


def _effective_url() -> str:
    # Prefer a single URL if provided (MARIADB_URL). Back-compat: MARIA_URL.
    url = os.getenv("MARIADB_URL") or os.getenv("MARIA_URL")
    if url:
        return url

    host = os.getenv("MARIADB_HOST", os.getenv("MARIA_HOST", "mariadb"))
    port = os.getenv("MARIADB_PORT", os.getenv("MARIA_PORT", "3306"))
    db   = os.getenv("MARIADB_DB",   os.getenv("MARIA_DB",   "market"))
    user = os.getenv("MARIADB_USER", os.getenv("MARIA_USER", "user"))
    pw   = os.getenv("MARIADB_PASSWORD", os.getenv("MARIA_PASSWORD", "password"))
    return f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}?charset=utf8mb4"


def _build_engine() -> sa.Engine:
    url = _effective_url()

    if os.getenv("DEBUG") == "1":
        try:
            left, _ = url.split("@", 1)
            if ":" in left:
                left = left.rsplit(":", 1)[0] + ":***"
            print("MARIADB_URL_EFFECTIVE:", left + "@…")
        except Exception:
            pass

    return sa.create_engine(url, pool_pre_ping=True, future=True)


_ENGINE: Optional[sa.Engine] = None
def get_engine() -> sa.Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _build_engine()
    return _ENGINE


DDL_SYMBOLS = """
CREATE TABLE IF NOT EXISTS symbols_dim (
  symbol      VARCHAR(32)  NOT NULL PRIMARY KEY,
  name        VARCHAR(255) NULL,
  sector      VARCHAR(128) NULL,
  industry    VARCHAR(128) NULL,
  exchange    VARCHAR(64)  NULL,
  is_active   TINYINT(1)   NOT NULL DEFAULT 1,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

DDL_PRICES = """
CREATE TABLE IF NOT EXISTS prices_daily (
  dt             DATE         NOT NULL,
  symbol         VARCHAR(32)  NOT NULL,
  open           DECIMAL(18,6) NULL,
  high           DECIMAL(18,6) NULL,
  low            DECIMAL(18,6) NULL,
  close          DECIMAL(18,6) NULL,
  volume         BIGINT        NULL,
  vwap           DECIMAL(18,6) NULL,
  is_trading_day TINYINT(1)    NULL DEFAULT 1,
  updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                 ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (symbol, dt),
  KEY idx_dt (dt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def _normalize_symbol_series(s: pd.Series) -> pd.Series:
    # Keep a consistent case; UPPER is common for tickers and avoids tableau join gotchas.
    return s.astype(str).str.strip().str.upper()


def upsert_symbols(df: pd.DataFrame) -> int:
    """
    Upsert into symbols_dim. You can pass a wide DF with columns:
      symbol (required), name, sector, industry, exchange, is_active
    Non-existing columns are treated as NULLs.
    """
    if "symbol" not in df.columns:
        raise ValueError("symbols upsert requires 'symbol' column")

    cols = ["symbol", "name", "sector", "industry", "exchange", "is_active"]
    payload = df.copy()[[c for c in cols if c in df.columns]].copy()
    payload["symbol"] = _normalize_symbol_series(payload["symbol"])

    # Ensure all columns exist (as nullable) for the parameterized insert
    for c in cols:
        if c not in payload.columns:
            payload[c] = None

    eng = get_engine()
    with eng.begin() as cxn:
        # DB name comes from URL; just ensure table exists in current DB.
        cxn.exec_driver_sql(DDL_SYMBOLS)

        # ON DUPLICATE: do not clobber non-null with NULL.
        insert_sql = sa.text("""
            INSERT INTO symbols_dim
              (symbol, name, sector, industry, exchange, is_active)
            VALUES
              (:symbol, :name, :sector, :industry, :exchange, :is_active)
            ON DUPLICATE KEY UPDATE
              name     = COALESCE(VALUES(name), name),
              sector   = COALESCE(VALUES(sector), sector),
              industry = COALESCE(VALUES(industry), industry),
              exchange = COALESCE(VALUES(exchange), exchange),
              is_active= COALESCE(VALUES(is_active), is_active)
        """)
        rows = payload.to_dict(orient="records")
        if rows:
            cxn.execute(insert_sql, rows)
        return len(rows)


def upsert_prices(df: pd.DataFrame) -> int:
    """
    Upsert daily prices into prices_daily. If symbols_dim is empty, we seed it
    using the distinct symbols from this batch (no names/sectors yet).
    Required columns: dt, symbol, open, high, low, close, volume, vwap, is_trading_day
    """
    required = ["dt", "symbol", "open", "high", "low", "close", "volume", "vwap", "is_trading_day"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    data = df.copy()
    data["dt"] = pd.to_datetime(data["dt"], errors="coerce").dt.date
    data["symbol"] = _normalize_symbol_series(data["symbol"])

    eng = get_engine()
    with eng.begin() as cxn:
        # Ensure dimension & fact tables exist
        cxn.exec_driver_sql(DDL_SYMBOLS)
        cxn.exec_driver_sql(DDL_PRICES)

        # Seed symbols_dim with distinct symbols from this batch if needed
        distinct_syms = pd.DataFrame({"symbol": data["symbol"].dropna().unique()})
        if not distinct_syms.empty:
            insert_syms = sa.text("""
                INSERT INTO symbols_dim (symbol)
                VALUES (:symbol)
                ON DUPLICATE KEY UPDATE symbol = symbol
            """)
            cxn.execute(insert_syms, distinct_syms.to_dict(orient="records"))

        # Upsert prices
        insert_prices = sa.text("""
            INSERT INTO prices_daily
              (dt, symbol, open, high, low, close, volume, vwap, is_trading_day)
            VALUES
              (:dt, :symbol, :open, :high, :low, :close, :volume, :vwap, :is_trading_day)
            ON DUPLICATE KEY UPDATE
              open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close),
              volume=VALUES(volume), vwap=VALUES(vwap), is_trading_day=VALUES(is_trading_day)
        """)
        rows = data[required].to_dict(orient="records")
        if rows:
            cxn.execute(insert_prices, rows)
        return len(rows)
