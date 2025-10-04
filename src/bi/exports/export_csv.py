# src/bi/exports/export_csv.py
import os
import sys
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

OUT_DIR = Path(os.environ.get("EXPORT_DIR", "bi/exports"))

# Preferred: single URL. Else use MARIA_* pieces.
def _build_engine() -> sa.Engine:
    url = os.getenv("MARIA_URL")
    if not url:
        host = os.getenv("MARIA_HOST", "mariadb")
        port = os.getenv("MARIA_PORT", "3306")
        db   = os.getenv("MARIA_DB",   "market")
        user = os.getenv("MARIA_USER", "user")
        pw   = os.getenv("MARIA_PASS", "password")
        url  = f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}?charset=utf8mb4"
    return sa.create_engine(url, pool_pre_ping=True, future=True)

def _mkout():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

def _maybe_strip_prefix(cols):
    # defensive: strip accidental table prefixes like "p.dt"
    return [c.split(".")[-1] for c in cols]

def export_prices_daily(start_date: str | None, end_date: str | None, symbols: list[str] | None, eng: sa.Engine) -> Path:
    """
    Export market.prices_daily -> bi/exports/prices_daily.csv (chunked).
    Filters: optional START_DATE / END_DATE / TW_SYMBOLS (comma-separated).
    """
    where = ["1=1"]
    params: dict[str, object] = {}

    if start_date:
        where.append("dt >= :start_date")
        params["start_date"] = start_date
    if end_date:
        where.append("dt <= :end_date")
        params["end_date"] = end_date
    if symbols:
        # normalize to lower; pass as a tuple to IN
        syms = tuple(s.strip().lower() for s in symbols if s.strip())
        if syms:
            where.append("LOWER(symbol) IN :syms")
            params["syms"] = syms

    sql = f"""
    SELECT
      dt, symbol, open, high, low, close, volume, vwap, is_trading_day
    FROM market.prices_daily
    WHERE {' AND '.join(where)}
    ORDER BY symbol, dt
    """

    out_path = OUT_DIR / "prices_daily.csv"
    # stream in chunks to avoid memory blowups
    chunksize = int(os.getenv("EXPORT_CHUNKSIZE", "100000"))
    header_written = False
    total_rows = 0

    with eng.connect() as cxn:
        for chunk in pd.read_sql_query(sa.text(sql), cxn, params=params, chunksize=chunksize):
            # sanitize columns once
            chunk.columns = _maybe_strip_prefix(list(chunk.columns))
            # ensure types are reasonable for CSV
            chunk["symbol"] = chunk["symbol"].astype(str).str.strip().str.lower()
            # write/append
            mode = "w" if not header_written else "a"
            chunk.to_csv(out_path, index=False, header=not header_written, mode=mode)
            header_written = True
            total_rows += len(chunk)

    if total_rows == 0:
        # create empty file with header for predictability
        cols = ["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"]
        pd.DataFrame(columns=cols).to_csv(out_path, index=False)
    return out_path

def _table_exists(eng: sa.Engine, fqname: str) -> bool:
    # fqname: "schema.table"
    schema, table = fqname.split(".", 1) if "." in fqname else (None, fqname)
    insp = sa.inspect(eng)
    try:
        return table in insp.get_table_names(schema=schema)
    except Exception:
        return False

def export_symbols_dim(eng: sa.Engine) -> Path:
    """
    Export market.symbols_dim if present; otherwise derive minimal dim from prices_daily.
    """
    out_path = OUT_DIR / "symbols_dim.csv"
    with eng.connect() as cxn:
        if _table_exists(eng, "market.symbols_dim"):
            df = pd.read_sql_query(sa.text("""
                SELECT *
                FROM market.symbols_dim
                ORDER BY symbol
            """), cxn)
            # normalize symbol casing
            if "symbol" in df.columns:
                df["symbol"] = df["symbol"].astype(str).str.strip().str.lower()
            df.to_csv(out_path, index=False)
            return out_path

        # Fallback: derive minimal dim
        df = pd.read_sql_query(sa.text("""
            SELECT DISTINCT LOWER(symbol) AS symbol
            FROM market.prices_daily
            WHERE symbol IS NOT NULL
            ORDER BY symbol
        """), cxn)
        df.to_csv(out_path, index=False)
        return out_path

def main() -> int:
    _mkout()
    eng = _build_engine()

    start = os.getenv("START_DATE")      # e.g., "2024-01-01"
    end   = os.getenv("END_DATE")        # optional
    syms_env = os.getenv("TW_SYMBOLS", "")
    symbols = [s for s in (syms_env.split(",") if syms_env else []) if s.strip()]

    prices_csv = export_prices_daily(start, end, symbols, eng)
    symbols_csv = export_symbols_dim(eng)

    # Minimal, useful output
    def _lines(p: Path) -> int:
        try:
            return sum(1 for _ in open(p, "r", encoding="utf-8"))
        except Exception:
            return 0

    print(f"EXPORTED: {prices_csv} (lines={_lines(prices_csv)})")
    print(f"EXPORTED: {symbols_csv} (lines={_lines(symbols_csv)})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
