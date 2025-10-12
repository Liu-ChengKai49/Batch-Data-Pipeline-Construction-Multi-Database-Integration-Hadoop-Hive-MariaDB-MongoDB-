from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def fetch_prices(
    conn: Connection,
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    where = ["symbol = :symbol"]
    params: dict[str, Any] = {"symbol": symbol}  # <-- widen value type

    if start is not None:
        where.append("dt >= :start")
        params["start"] = start
    if end is not None:
        where.append("dt <= :end")
        params["end"] = end

    sql = (
        "SELECT dt, symbol, open, high, low, close, volume, vwap, is_trading_day "
        "FROM prices_daily "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY dt"
    )
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = int(limit)

    rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]
