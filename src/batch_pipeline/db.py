# src/batch_pipeline/db.py
from __future__ import annotations

import os
from typing import Any, Dict, Iterable

import pymysql
from pymysql.cursors import DictCursor


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class _ConnWrapper:
    def __init__(self) -> None:
        self._conn = pymysql.connect(
            host=_env("MARIADB_HOST", "127.0.0.1"),
            port=int(_env("MARIADB_PORT", "3306")),
            user=_env("MARIADB_USER", "root"),
            password=_env("MARIADB_PASSWORD", "root"),
            database=_env("MARIADB_DB", "market"),  # default to "market" to match CI
            autocommit=True,                        # let us control commits explicitly
            charset="utf8mb4",
            cursorclass=DictCursor,
        )

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        try:
            # rollback uncommitted changes on exception; else close cleanly
            if exc_type:
                self._conn.rollback()
            self._conn.close()
        except Exception:
            pass

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def mariadb_conn():
    return _ConnWrapper()


def _current_db(conn) -> str:
    """Return the active database name for this connection."""
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS db")
        row = cur.fetchone()
    return row["db"] or _env("MARIADB_DB", "market")


def build_upsert_sql(table: str = "prices_daily", database: str | None = None) -> str:
    target = f"{database}.{table}" if database else table
    return (
        "INSERT INTO "
        f"{target}\n"
        "(symbol, dt, open, high, low, close, volume, vwap, is_trading_day)\n"
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)\n"
        "ON DUPLICATE KEY UPDATE\n"
        "  open=VALUES(open), high=VALUES(high), low=VALUES(low),\n"
        "  close=VALUES(close), volume=VALUES(volume),\n"
        "  vwap=VALUES(vwap), is_trading_day=VALUES(is_trading_day);"
    )



def _ensure_schema_and_table(conn) -> None:
    db = _current_db(conn)
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{db}`.`prices_daily` (
              symbol VARCHAR(16) NOT NULL,
              dt DATE NOT NULL,
              open DOUBLE NOT NULL,
              high DOUBLE NOT NULL,
              low  DOUBLE NOT NULL,
              close DOUBLE NOT NULL,
              volume BIGINT NOT NULL,
              vwap DOUBLE NOT NULL,
              is_trading_day TINYINT NOT NULL,
              PRIMARY KEY (symbol, dt)
            ) ENGINE=InnoDB;
            """
        )
        # In case the table existed from an older schema, add missing columns:
        cur.execute(f"ALTER TABLE `{db}`.`prices_daily` ADD COLUMN IF NOT EXISTS vwap DOUBLE NOT NULL")
        cur.execute(f"ALTER TABLE `{db}`.`prices_daily` ADD COLUMN IF NOT EXISTS is_trading_day TINYINT NOT NULL")

        cur.execute(
            f"""
            CREATE OR REPLACE VIEW `{db}`.`prices_daily_mart` AS
            SELECT symbol, dt, open, high, low, close, volume, vwap, is_trading_day
            FROM `{db}`.`prices_daily`;
            """
        )



def _as_tuples(rows):
    out = []
    for r in rows:
        vwap = r.get("vwap", r.get("close"))          # default vwap to close
        is_td = int(r.get("is_trading_day", 1))       # default to trading day
        out.append((
            r["symbol"],
            r["dt"],
            r["open"], r["high"], r["low"], r["close"],
            r["volume"],
            vwap,
            is_td,
        ))
    return out


def upsert_prices_conn(conn, rows: Iterable[Dict[str, Any]], *, table: str = "prices_daily") -> int:
    """
    Upsert dict rows into <current_db>.<table> using an existing connection.
    Returns number of rows attempted. Commits on success; rolls back on error.
    """
    _ensure_schema_and_table(conn)

    rows_list = list(rows)
    if not rows_list:
        return 0

    db = _current_db(conn)
    sql = build_upsert_sql(table=table, database=db)

    try:
        with conn.cursor() as cur:
            cur.executemany(sql, _as_tuples(rows_list))
        conn.commit()                   # <<< IMPORTANT: make write visible
        return len(rows_list)
    except Exception:
        conn.rollback()                 # keep state clean for the test
        raise


def upsert_prices(*args, table: str = "prices_daily") -> int:
    """
    Backward-compatible API:
      - upsert_prices(conn, rows, *, table=...)  # explicit connection
      - upsert_prices(rows, *, table=...)        # wrapper (opens/closes conn)
    """
    if len(args) == 1:
        rows = args[0]
        with mariadb_conn() as conn:
            return upsert_prices_conn(conn, rows, table=table)
    elif len(args) == 2:
        conn, rows = args
        return upsert_prices_conn(conn, rows, table=table)
    else:
        raise TypeError("upsert_prices expects (rows) or (conn, rows)")


__all__ = [
    "mariadb_conn",
    "build_upsert_sql",
    "upsert_prices",
    "upsert_prices_conn",
]
