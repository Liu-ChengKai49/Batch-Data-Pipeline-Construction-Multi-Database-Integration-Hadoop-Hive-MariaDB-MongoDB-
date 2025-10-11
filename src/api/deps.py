# src/api/deps.py
import math

import numpy as np
import pandas as pd


def _safe_scalar(v):
    # normalize numpy scalars to Python types
    if hasattr(v, "item"):
        v = v.item()

    # allow None straight through
    if v is None:
        return None

    # numbers: remove NaN/±Inf
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, (int, np.integer)):
        return int(v)

    # everything else (str, bool, etc.)
    return v

def to_json(df: pd.DataFrame):
    df = df.copy()

    # make dt string-y (safe for JSON)
    if "dt" in df.columns:
        df["dt"] = pd.to_datetime(df["dt"]).dt.date.astype(str)

    # IMPORTANT: convert to dict first, then sanitize each value,
    # because pandas may coerce None -> NaN for float dtypes.
    records = df.to_dict(orient="records")
    cleaned = [{k: _safe_scalar(v) for k, v in rec.items()} for rec in records]

    return {"rows": int(len(cleaned)), "data": cleaned}
