import pandas as pd

def clean_prices(df: pd.DataFrame) -> pd.DataFrame:
    df["close"] = df[["close","low","high"]].apply(
        lambda r: max(r["low"], min(r["close"], r["high"])), axis=1
    )
    df["dt"] = pd.to_datetime(df["dt"]).dt.date.astype(str)
    df["volume"] = df["volume"].fillna(0).astype(int)
    return df[["symbol","dt","open","high","low","close","volume"]]
