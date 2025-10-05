import pandas as pd
def moving_average(df: pd.DataFrame, windows=(5,20,60)):
    out = df.sort_values("dt").copy()
    for w in windows:
        out[f"ma_{w}"] = out["close"].rolling(w, min_periods=w).mean()
    return out