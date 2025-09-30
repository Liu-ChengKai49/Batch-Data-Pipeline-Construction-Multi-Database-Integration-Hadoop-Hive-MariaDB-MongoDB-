# etl/tw_stocks/write_parquet_hdfs.py
import os, pathlib as pl
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from etl.tw_stocks.fetch_normalize import fetch_ohlcv
import requests
from urllib.parse import quote
import shutil

ROOT = pl.Path("local_parquet")
HDFS_NN = os.environ.get("WEBHDFS", "http://namenode:9870")  # NameNode HTTP
HDFS_PATH = os.environ.get("HDFS_PATH", "/data/stocks")      # target root on HDFS

DATA_COLS = ["open","high","low","close","volume","vwap","is_trading_day"]
# top of file
HDFS_USER = os.environ.get("HDFS_USER", "root")   # <<— add this

def _wurl(path: str, op: str, extra: str = "") -> str:
    # helper to build WebHDFS URL with user.name everywhere
    return f"{HDFS_NN}/webhdfs/v1{quote(path)}?op={op}&user.name={HDFS_USER}{extra}"

def webhdfs_mkdirs(hdfs_dir: str) -> None:
    url = _wurl(hdfs_dir, "MKDIRS")
    r = requests.put(url, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"MKDIRS {hdfs_dir} -> {r.status_code} {r.text[:200]}")

def webhdfs_put(local_path: pl.Path, hdfs_dest: str) -> None:
    # Step 1: CREATE (NameNode) — include user.name & overwrite
    url1 = _wurl(hdfs_dest, "CREATE", "&overwrite=true")
    r1 = requests.put(url1, allow_redirects=False, timeout=30)
    if r1.status_code not in (307, 201):
        raise RuntimeError(f"CREATE {hdfs_dest} -> {r1.status_code} {r1.text[:200]}")
    loc = r1.headers.get("Location") or url1  # some stacks return 201 without redirect
    # Step 2: upload to DataNode (Location already carries delegation; user not required)
    with open(local_path, "rb") as f:
        r2 = requests.put(loc, data=f, timeout=300)
    if r2.status_code not in (200, 201):
        raise RuntimeError(f"UPLOAD {hdfs_dest} -> {r2.status_code} {r2.text[:200]}")


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize OHLCV data to tidy rows with columns:
      dt, symbol, open, high, low, close, volume, vwap, is_trading_day
    """
    want_metrics = {"open", "high", "low", "close", "volume", "vwap"}

    # Case 1: MultiIndex columns (wide table)
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = {str(x).lower() for x in df.columns.get_level_values(0)}
        lvl1 = {str(x).lower() for x in df.columns.get_level_values(1)}

        if want_metrics.issubset(lvl0):
            metric_level, symbol_level = 0, 1
        elif want_metrics.issubset(lvl1):
            metric_level, symbol_level = 1, 0
        else:
            raise ValueError("Could not find expected metrics in MultiIndex levels")

        # Stack by the symbol level -> long format (use new impl to avoid future warning)
        long = df.stack(level=symbol_level, future_stack=True).reset_index()

        # Figure out the name pandas gave to the stacked column
        sym_col_name = df.columns.names[symbol_level] or "level_1"
        if sym_col_name in long.columns and "symbol" not in long.columns:
            long = long.rename(columns={sym_col_name: "symbol"})

        # Normalize date column to 'dt'
        for cand in ("dt", "date", "Date"):
            if cand in long.columns:
                long = long.rename(columns={cand: "dt"})
                break
        else:
            # heuristic fallback
            for c in long.columns:
                if c != "symbol":
                    try:
                        tmp = pd.to_datetime(long[c], errors="coerce")
                        if tmp.notna().any():
                            long[c] = tmp
                            long = long.rename(columns={c: "dt"})
                            break
                    except Exception:
                        pass
            if "dt" not in long.columns:
                raise ValueError("Could not infer date column (dt).")

        # Ensure expected columns exist
        keep = ["dt", "symbol", "open", "high", "low", "close", "volume", "vwap", "is_trading_day"]
        for k in keep:
            if k not in long.columns:
                long[k] = pd.NA

        # Lowercase names, select only needed, then DROP DUPLICATE COLUMN NAMES
        long.columns = [str(c).lower() for c in long.columns]
        long = long[keep]
        long = long.loc[:, ~long.columns.duplicated()]   # <- critical fix
        return long

    # Case 2: Already tidy (simple Index)
    cols_lower = {str(c).lower() for c in df.columns}
    need = {"dt", "symbol"} | want_metrics
    if need.issubset(cols_lower):
        out = df.copy()
        out.columns = [str(c).lower() for c in out.columns]
        if "is_trading_day" not in out.columns:
            out["is_trading_day"] = 1
        out = out[["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"]]
        out = out.loc[:, ~out.columns.duplicated()]       # <- guard here too
        return out

    raise ValueError("fetch_ohlcv returned an unexpected shape; inspect upstream normalization.")


def write_local_partitions(df: pd.DataFrame) -> None:
    if df.empty:
        print("NO_DATA"); return
        # clean local cache from previous runs
    if ROOT.exists():
        shutil.rmtree(ROOT)          # <- wipe old timestamped folders
    ROOT.mkdir(parents=True, exist_ok=True)
    # enforce dtypes you want in Hive
    # enforce schema
    df = df.loc[:, ~df.columns.duplicated()]          # <- ensure 1D columns
    df["symbol"] = df["symbol"].astype("string").str.strip().str.lower()
    dt_coerced = pd.to_datetime(df["dt"], errors="coerce")
    df = df.loc[dt_coerced.notna() & df["symbol"].notna()].copy()
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce").dt.date   # <-- make it a date

    for c in ["open","high","low","close","vwap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")
    df["is_trading_day"] = pd.to_numeric(df["is_trading_day"], errors="coerce").fillna(1).astype("Int8")

    for (sym, day), g in df.groupby(["symbol","dt"], sort=True):
        out = ROOT / f"symbol={sym}" / f"dt={day}"
        out.mkdir(parents=True, exist_ok=True)
        # write ONLY the data columns; exclude dt/symbol from the file
        tbl = pa.Table.from_pandas(g[DATA_COLS], preserve_index=False)
        pq.write_table(tbl, out / "part-0.parquet")



def hdfs_put_tree(local_root: pl.Path, hdfs_root: str) -> None:
    for p in local_root.rglob("part-0.parquet"):
        rel = p.relative_to(local_root)   # e.g. symbol=2317.tw/dt=2024-01-02/part-0.parquet
        parts = list(rel.parent.parts)
        fixed = []
        for seg in parts:
            if seg.startswith("dt="):
                # keep only the date part (split off ' 00:00:00' if present)
                val = seg[3:].split()[0]
                fixed.append(f"dt={val}")
            elif seg.startswith("symbol="):
                fixed.append("symbol=" + seg.split("=",1)[1].strip().lower())
            else:
                fixed.append(seg)
        target_dir = f"{hdfs_root}/" + "/".join(fixed)
        webhdfs_mkdirs(target_dir)
        webhdfs_put(p, f"{target_dir}/part-0.parquet")


if __name__ == "__main__":
    symbols = os.environ["TW_SYMBOLS"].split(",")
    start = os.environ.get("START_DATE","2024-01-01")
    end   = os.environ.get("END_DATE","auto")

    raw = fetch_ohlcv(symbols, start, end)   # may be wide MultiIndex
    df  = to_long(raw)                       # normalize to tidy rows

    # --- sanitize BEFORE any prints ---
    # uniform symbol strings; keep or strip ".tw" as you prefer (here: keep)
    df["symbol"] = df["symbol"].astype("string").str.strip().str.lower()
    df = df[df["symbol"].notna()].copy()

    # coerce dt to datetime and drop invalids
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce")
    df = df[df["dt"].notna()].copy()

    # (optional) drop rows where all metrics are NaN
    metric_cols = ["open","high","low","close","volume","vwap"]
    if any(c not in df.columns for c in metric_cols):
        missing = [c for c in metric_cols if c not in df.columns]
        raise ValueError(f"Missing metric columns after to_long(): {missing}")
    df = df.dropna(subset=metric_cols, how="all")

    # safe debug prints
    syms = sorted(df["symbol"].unique().tolist())
    print("EFFECTIVE SYMBOLS:", syms[:10])
    print("DT RANGE:", df["dt"].min().date(), "->", df["dt"].max().date())
    print("HDFS_PATH:", HDFS_PATH, "HDFS_USER:", HDFS_USER)
    # ----------------------------------

    write_local_partitions(df)      # converts dt to .date and enforces dtypes
    hdfs_put_tree(ROOT, HDFS_PATH)  # WebHDFS with user.name
    print("HDFS_PUT_OK")

