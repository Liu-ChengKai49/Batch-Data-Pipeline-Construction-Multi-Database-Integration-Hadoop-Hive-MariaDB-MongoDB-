import pandas as pd, sqlalchemy as sa
from .db import engine

def fetch_prices(symbol: str, start: str|None=None, end: str|None=None, limit:int=500):
    where = ["symbol = :symbol"]
    params = {"symbol": symbol}
    if start: where.append("dt >= :start"); params["start"] = start
    if end:   where.append("dt <= :end");   params["end"] = end
    sql = f"""
      SELECT dt, symbol, open, high, low, close, volume, vwap, is_trading_day
      FROM prices_daily
      WHERE {' AND '.join(where)}
      ORDER BY dt DESC
      LIMIT :limit
    """
    params["limit"] = limit
    with engine.connect() as conn:
        df = pd.read_sql(sa.text(sql), conn, params=params)
    return df