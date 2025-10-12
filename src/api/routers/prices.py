from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from api.deps import get_conn
from services.prices import fetch_prices

router = APIRouter(prefix="/prices", tags=["prices"])

@router.get("", name="list_prices")
def list_prices(
    symbol: str = Query(..., description="e.g. 2330.TW"),
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int | None = Query(None, ge=1, le=10000),
    conn: Connection = Depends(get_conn),
) -> list[dict[str, Any]]:
    return fetch_prices(conn=conn, symbol=symbol, start=start, end=end, limit=limit)
