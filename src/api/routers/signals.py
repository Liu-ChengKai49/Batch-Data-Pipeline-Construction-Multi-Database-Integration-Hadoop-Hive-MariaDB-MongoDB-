from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from api.deps import get_conn
from services.prices import fetch_prices
from services.signals import moving_average

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("/moving_average")
def moving_average_endpoint(
    symbol: str = Query(...),
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int | None = Query(None, ge=1, le=10000),
    window: int = Query(5, ge=1, le=365),
    conn: Connection = Depends(get_conn),
) -> list[dict[str, Any]]:
    rows = fetch_prices(conn=conn, symbol=symbol, start=start, end=end, limit=limit)
    return moving_average(rows=rows, key="close", window=window)  # <-- window (not "windows")
