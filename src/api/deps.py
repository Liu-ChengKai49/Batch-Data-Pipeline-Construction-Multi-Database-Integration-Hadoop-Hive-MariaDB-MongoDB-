import pandas as pd
def to_json(df: pd.DataFrame):
    # isoformat dates for clean JSON
    if "dt" in df.columns: df["dt"] = pd.to_datetime(df["dt"]).dt.date.astype(str)
    return {"rows": len(df), "data": df.to_dict(orient="records")}