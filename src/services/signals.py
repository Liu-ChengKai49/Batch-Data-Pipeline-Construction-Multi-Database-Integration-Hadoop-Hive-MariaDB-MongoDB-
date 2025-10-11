# src/services/signals.py
import pandas as pd


def moving_average(df: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    """
    Compute simple moving averages on the 'close' column.
    Returns the original rows plus ma_<w> columns.
    """
    if df.empty:
        # Return an empty DF but include the MA columns so downstream JSON is stable
        return df.assign(**{f"ma_{w}": [] for w in windows})

    out = df.sort_values("dt").copy()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")

    for w in windows:
        # min_periods=w so early rows become NaN (will be converted to null by to_json)
        out[f"ma_{w}"] = out["close"].rolling(w, min_periods=w).mean()

    return out
