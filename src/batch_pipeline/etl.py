from __future__ import annotations

from datetime import datetime
from typing import Dict, Union

import numpy as np
import pandas as pd

RetType = Union[pd.DataFrame, float]

__all__ = ["make_partition_path", "clean_prices", "compute_returns"]

# ---------- small helper expected by tests ----------
def make_partition_path(dt_str: str) -> str:
    """
    Validate 'YYYY-MM-DD' and return partition path like 'dt=YYYY-MM-DD/'.
    Raises ValueError on bad format (test_partition_path_err.py expects this).
    """
    try:
        datetime.strptime(dt_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"bad date: {dt_str}") from e
    return f"dt={dt_str}/"


# ---------- cleaning used by smoke & later ETL ----------
def _clamp(row: pd.Series) -> float:
    """Clamp close into [low, high]."""
    c = float(row["close"])
    lo = float(row["low"])
    hi = float(row["high"])
    return max(lo, min(c, hi))

def clean_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure required columns exist and are typed:
      symbol(str), dt(YYYY-MM-DD), open(float), high(float), low(float),
      close(float clamped to [low,high]), volume(int >=0)

    Returns only these 7 columns, ready for upsert.
    """
    cols = ["symbol", "dt", "open", "high", "low", "close", "volume"]
    out = df[cols].copy()

    # types
    out["symbol"] = out["symbol"].astype(str)
    out["dt"] = pd.to_datetime(out["dt"]).dt.strftime("%Y-%m-%d")

    for c in ["open", "high", "low", "close"]:
        out[c] = out[c].astype(float)

    out["volume"] = out["volume"].astype(int).clip(lower=0)

    # clamp close
    out["close"] = out.apply(_clamp, axis=1)

    return out


# ---------- returns logic (keeps your recent refactor) ----------
def _compute_returns_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add simple returns from close: 1d, 7d, 30d by symbol, sorted by dt.
    Required columns: symbol, dt (YYYY-MM-DD), close.
    """
    out = df.copy()
    out["dt"] = pd.to_datetime(out["dt"])
    # 1) sort and 2) reset index so groupby.shift uses this exact order
    out = out.sort_values(["symbol", "dt"]).reset_index(drop=True)

    close = out["close"].astype(float)
    labels = out["symbol"]

    prev1  = close.groupby(labels).shift(1)
    prev7  = close.groupby(labels).shift(7)
    prev30 = close.groupby(labels).shift(30)

    # (current / previous) - 1
    out["return_1d"]  = close.div(prev1).sub(1.0)
    out["return_7d"]  = close.div(prev7).sub(1.0)
    out["return_30d"] = close.div(prev30).sub(1.0)

    returns_cols = ["return_1d", "return_7d", "return_30d"]
    out[returns_cols] = (
        out[returns_cols]
        .replace([np.inf, -np.inf], np.nan)
        .round(6)
    )
    return out



def _compute_return_scalar(row: Dict[str, float]) -> float:
    """
    Back-compat: if a single row dict with open/close is provided, return a scalar.
    Rounded to avoid float-equality flakes in tests.
    """
    open_ = float(row.get("open", 0.0))
    close = float(row["close"])
    if open_ == 0.0:
        return 0.0
    return round((close - open_) / open_, 6)

def compute_returns(obj: Union[pd.DataFrame, Dict[str, float]]) -> RetType:
    """
    Overloaded-style API:
      - DataFrame -> DataFrame with return_1d/7d/30d (from close).
      - dict(open, close) -> scalar return.
    """
    if isinstance(obj, pd.DataFrame):
        return _compute_returns_df(obj)
    if isinstance(obj, dict):
        return _compute_return_scalar(obj)
    raise TypeError("compute_returns expects a pandas DataFrame or a dict row")
