# src/api/deps.py
from __future__ import annotations

import math
import os
from typing import Any, Iterator

import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

# -------------------------------
# Database engine / connection
# -------------------------------

_ENGINE: Engine | None = None


def _dsn() -> str:
    """Build MariaDB DSN from env vars."""
    user = os.getenv("MARIADB_USER", "root")
    pwd = os.getenv("MARIADB_PASSWORD", os.getenv("MARIADB_ROOT_PASSWORD", ""))
    host = os.getenv("MARIADB_HOST", "mariadb")
    port = int(os.getenv("MARIADB_PORT", "3306"))
    db = os.getenv("MARIADB_DB", "market")
    return f"mariadb+pymysql://{user}:{pwd}@{host}:{port}/{db}"


def get_engine() -> Engine:
    """Return a cached SQLAlchemy Engine (with pre-ping)."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(_dsn(), pool_pre_ping=True)
    return _ENGINE


def get_conn() -> Iterator[Connection]:
    """
    FastAPI dependency that yields a DB Connection.

    Usage in routers:
        from fastapi import Depends
        from sqlalchemy.engine import Connection
        from api.deps import get_conn

        def handler(conn: Connection = Depends(get_conn)):
            ...
    """
    engine = get_engine()
    with engine.connect() as conn:
        yield conn


# -------------------------------
# DataFrame → JSON helpers
# -------------------------------

def _safe_scalar(v: Any) -> Any:
    """Normalize scalars for JSON: convert numpy types, drop NaN/Inf to None."""
    if hasattr(v, "item"):
        v = v.item()

    if v is None:
        return None

    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    if isinstance(v, (int, np.integer)):
        return int(v)

    # str, bool, etc.
    return v


def to_json(df: pd.DataFrame) -> dict[str, Any]:
    """
    Convert a DataFrame to a JSON-safe payload:
    - cast 'dt' to 'YYYY-MM-DD' strings
    - convert numpy scalars; replace NaN/Inf with None
    """
    df = df.copy()

    if "dt" in df.columns:
        df["dt"] = pd.to_datetime(df["dt"]).dt.date.astype(str)

    records = df.to_dict(orient="records")
    cleaned = [{k: _safe_scalar(v) for k, v in rec.items()} for rec in records]

    return {"rows": int(len(cleaned)), "data": cleaned}


__all__ = ["get_engine", "get_conn", "to_json", "_safe_scalar"]
