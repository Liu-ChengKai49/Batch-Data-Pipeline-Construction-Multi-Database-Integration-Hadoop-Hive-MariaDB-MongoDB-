from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from api.deps import get_conn
from services.anomaly import mad_outliers
from services.prices import fetch_prices

router = APIRouter(prefix="/anomaly", tags=["anomaly"])

@router.get("")
def anomaly_endpoint(
    symbol: str = Query(...),
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int | None = Query(None, ge=1, le=10000),
    z: float = Query(3.5, ge=0.0),
    conn: Connection = Depends(get_conn),
) -> list[dict[str, Any]]:
    rows = fetch_prices(conn=conn, symbol=symbol, start=start, end=end, limit=limit)
    return mad_outliers(rows=rows, key="close", z=z)
