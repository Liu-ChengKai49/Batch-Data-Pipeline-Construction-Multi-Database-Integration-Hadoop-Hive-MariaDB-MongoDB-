# src/batch_pipeline/db.py
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Tuple

import pymysql
from pymysql.cursors import DictCursor  # NEW


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class _ConnWrapper:
    """
    Wrap a raw PyMySQL connection so:
    - When tests do `conn = mariadb_conn()`, connect() is called immediately.
    - When code does `with mariadb_conn() as conn:`, it also works.
    """
    def __init__(self) -> None:
        self._conn = pymysql.connect(
            host=_env("MARIADB_HOST", "127.0.0.1"),
            port=int(_env("MARIADB_PORT", "3306")),
            user=_env("MARIADB_USER", "root"),
            password=_env("MARIADB_PASSWORD", "root"),
            database=_env("MARIADB_DB", "demo"),
            autocommit=True,
            charset="utf8mb4",
            cursorclass=DictCursor,  # NEW  ← satisfies the test's 'cursorclass in called'
        )

    # Context manager support
    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        try:
            self._conn.close()
        except Exception:
            pass

    # Proxy everything else to the real connection for convenience
    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def mariadb_conn():
    """
    Return a connection-like object that:
      - immediately calls pymysql.connect() (so tests can capture kwargs),
      - can be used as a context manager.
    """
    return _ConnWrapper()


def build_upsert_sql(table: str = "prices_daily", database: str | None = None) -> str:
    """
    INSERT ... ON DUPLICATE KEY UPDATE with **positional** placeholders (%s).
    If `database` is provided, use database.table; else just table.
    """
    target = f"{database}.{table}" if database else table
    return (
        "INSERT INTO "
        f"{target}\n"
        "(symbol, dt, open, high, low, close, volume)\n"
        "VALUES (%s, %s, %s, %s, %s, %s, %s)\n"
        "ON DUPLICATE KEY UPDATE\n"
        "  open=VALUES(open), high=VALUES(high), low=VALUES(low),\n"
        "  close=VALUES(close), volume=VALUES(volume);"
    )


def _ensure_schema_and_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE DATABASE IF NOT EXISTS demo "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS demo.prices_daily (
              symbol VARCHAR(16) NOT NULL,
              dt DATE NOT NULL,
              open DOUBLE NOT NULL,
              high DOUBLE NOT NULL,
              low DOUBLE NOT NULL,
              close DOUBLE NOT NULL,
              volume BIGINT NOT NULL,
              PRIMARY KEY (symbol, dt)
            ) ENGINE=InnoDB;
            """
        )


def _as_tuples(rows: Iterable[Dict[str, Any]]) -> List[Tuple[Any, ...]]:
    order = ("symbol", "dt", "open", "high", "low", "close", "volume")
    return [tuple(r[k] for k in order) for r in rows]


def upsert_prices(conn, rows: Iterable[Dict[str, Any]], *, table: str = "prices_daily") -> int:
    """
    Upsert dict rows into demo.<table>. Returns number of rows attempted.
    """
    _ensure_schema_and_table(conn)
    rows_list = list(rows)
    if not rows_list:
        return 0
    sql = build_upsert_sql(table=table, database="demo")
    with conn.cursor() as cur:
        cur.executemany(sql, _as_tuples(rows_list))
    return len(rows_list)
