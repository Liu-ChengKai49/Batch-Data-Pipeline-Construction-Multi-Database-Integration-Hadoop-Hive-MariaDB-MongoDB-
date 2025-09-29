# src/etl/tw_stocks/fetch_normalize.py
import os
import datetime as dt
import pandas as pd

# ---- Provider A: Yahoo Finance (default) ----
def _yahoo_symbol(sym: str) -> str:
    # If user didn't add suffix, assume TWSE (.TW)
    return sym if ("." in sym) else f"{sym}.TW"

def fetch_ohlcv(symbols: list[str], start: str, end: str):
    """
    Return normalized OHLCV DataFrame with columns:
      dt (date), symbol, open, high, low, close, volume, vwap, is_trading_day
    """
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError(
            "yfinance not installed. Run: pip install yfinance"
        ) from e

    s = pd.Timestamp(start).normalize()
    e = (pd.Timestamp.today().normalize() if end == "auto"
         else pd.Timestamp(end).normalize())

    frames = []
    for sym in symbols:
        ys = _yahoo_symbol(sym)
        df = yf.download(ys, start=s.to_pydatetime(), end=e.to_pydatetime(),
                         auto_adjust=False, progress=False)
        if df is None or df.empty:
            continue
        df = df.reset_index().rename(columns=str.lower)
        df["symbol"] = sym  # keep user-facing symbol
        df = df.rename(columns={"date": "dt"})
        df["dt"] = pd.to_datetime(df["dt"]).dt.date
        df["vwap"] = ((df["high"] + df["low"] + df["close"]) / 3).round(6)
        df["is_trading_day"] = 1
        frames.append(df[["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"]])

    if not frames:
        return pd.DataFrame(columns=["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"])

    out = pd.concat(frames, ignore_index=True).sort_values(["symbol","dt"]).reset_index(drop=True)
    return out

# ---- Provider B: Official TWSE/TPEX (optional) ----
# Flip by TW_SOURCE=twse if you already added that logic elsewhere.
def fetch_tw_official(symbols: list[str], start: str, end: str):
    import requests
    s = pd.Timestamp(start).normalize()
    e = (pd.Timestamp.today().normalize() if end == "auto"
         else pd.Timestamp(end).normalize())

    def _to_yyyymmdd(ts: pd.Timestamp) -> str:
        return ts.strftime("%Y%m%d")

    def _twse_month_json(stock_no: str, month: pd.Timestamp) -> pd.DataFrame:
        url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
        params = {"response": "json", "date": _to_yyyymmdd(month), "stockNo": stock_no}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        js = r.json()
        if js.get("stat") != "OK" or not js.get("data"):
            return pd.DataFrame()
        cols = ["date","open","high","low","close","volume","turnover"]
        df = pd.DataFrame(js["data"], columns=cols)
        for c in ["open","high","low","close"]:
            df[c] = pd.to_numeric(df[c].str.replace(",","",regex=False), errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"].str.replace(",","",regex=False), errors="coerce")
        def roc_to_ad(s):
            y,m,d = s.split("/")
            y = int(y) + 1911
            return dt.date(y, int(m), int(d))
        df["dt"] = df["date"].map(roc_to_ad)
        df["vwap"] = ((df["high"] + df["low"] + df["close"]) / 3).round(6)
        df["is_trading_day"] = 1
        return df[["dt","open","high","low","close","volume","vwap","is_trading_day"]]

    def _tpex_month_csv(stock_no: str, month: pd.Timestamp) -> pd.DataFrame:
        url = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
        params = {"l": "zh-tw", "d": month.strftime("%Y/%m"), "stkno": stock_no}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        js = r.json()
        data = js.get("aaData") or []
        rows = []
        if not data:
            return pd.DataFrame()
        idx = {"date":0, "open":2, "high":3, "low":4, "close":5, "volume":8}
        for row in data:
            try:
                d = str(row[idx["date"]]).replace("\u200b","").strip()
                dt_ad = pd.to_datetime(d).date()
                def num(x): return pd.to_numeric(str(x).replace(",",""), errors="coerce")
                rows.append({
                    "dt": dt_ad,
                    "open": num(row[idx["open"]]),
                    "high": num(row[idx["high"]]),
                    "low":  num(row[idx["low"]]),
                    "close":num(row[idx["close"]]),
                    "volume": int(num(row[idx["volume"]]) or 0),
                    "vwap": None,
                    "is_trading_day": 1
                })
            except Exception:
                continue
        df = pd.DataFrame(rows)
        if not df.empty:
            df["vwap"] = ((df["high"] + df["low"] + df["close"]) / 3).round(6)
        return df

    months = pd.period_range(s, e, freq="M").to_timestamp()
    frames = []
    for sym in symbols:
        stock_no = sym.split(".")[0]
        is_otc = sym.endswith(".TWO")
        for m in months:
            dfm = _tpex_month_csv(stock_no, m) if is_otc else _twse_month_json(stock_no, m)
            if dfm.empty:
                continue
            dfm = dfm.assign(symbol=sym)
            frames.append(dfm)
    if not frames:
        return pd.DataFrame(columns=["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"])
    df = pd.concat(frames, ignore_index=True)
    df = df[(df["dt"] >= s.date()) & (df["dt"] <= e.date())]
    return df.sort_values(["symbol","dt"]).reset_index(drop=True)
