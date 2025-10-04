# etl/tw_stocks/write_parquet_hdfs.py
import os
import pathlib as pl
import shutil
from urllib.parse import quote

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

from etl.tw_stocks.fetch_normalize import fetch_ohlcv

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


def to_long(df: pd.DataFrame, require_full_ohlcv: bool = False) -> pd.DataFrame:
    import re
    want = {"open", "high", "low", "close", "volume"}

    # --- Helper: try to parse wide-but-flat columns into a MultiIndex ---
    def _maybe_split_flat_to_mi(_df: pd.DataFrame) -> pd.DataFrame:
        cols = [str(c) for c in _df.columns]
        # patterns we accept:
        #   1) metric.separator.symbol  e.g., "open.2330.TW" / "open__2330.tw"
        #   2) symbol.separator.metric  e.g., "2330.TW_open"
        # separators: dot, double underscore, single underscore
        sep = r"(?:\.|__|_)"
        metric_first = all(re.match(rf"^([a-z]+){sep}(.+)$", c, flags=re.I) for c in cols)
        symbol_first = all(re.match(rf"^(.+){sep}([a-z]+)$", c, flags=re.I) for c in cols)
        if metric_first:
            pairs = []
            for c in cols:
                m = re.match(rf"^([a-z]+){sep}(.+)$", c, flags=re.I)
                metric, sym = m.group(1).lower(), m.group(2).lower()
                pairs.append((metric, sym))
            if all(m in want or m == "vwap" for m, _ in pairs):
                new_df = _df.copy()
                new_df.columns = pd.MultiIndex.from_tuples(pairs, names=["metric", "symbol"])
                return new_df
        elif symbol_first:
            pairs = []
            for c in cols:
                m = re.match(rf"^(.+){sep}([a-z]+)$", c, flags=re.I)
                sym, metric = m.group(1).lower(), m.group(2).lower()
                pairs.append((metric, sym))
            if all(m in want or m == "vwap" for m, _ in pairs):
                new_df = _df.copy()
                new_df.columns = pd.MultiIndex.from_tuples(pairs, names=["metric", "symbol"])
                return new_df
        return _df

    df_in = df  # keep for debug message
    df = df.copy()
    # Normalize obvious 'Date' index to a column early
    if df.index.name and str(df.index.name).lower() in ("date", "dt"):
        df = df.reset_index()

    # If not MI but looks like wide-flat, convert to MI
    if not isinstance(df.columns, pd.MultiIndex):
        df = _maybe_split_flat_to_mi(df)

    if isinstance(df.columns, pd.MultiIndex):
        # --- Your original MI logic, with small robustness tweaks ---
        df.columns = pd.MultiIndex.from_tuples(
            [(str(a).strip().lower(), str(b).strip().lower()) for a, b in df.columns],
            names=df.columns.names
        )

        lvl0 = set(df.columns.get_level_values(0))
        lvl1 = set(df.columns.get_level_values(1))
        if want.issubset(lvl0):
            metric_level, symbol_level = 0, 1
        elif want.issubset(lvl1):
            metric_level, symbol_level = 1, 0
        else:
            raise ValueError(
                f"Could not find expected OHLCV metrics in MultiIndex levels.\n"
                f"lvl0 sample={list(lvl0)[:6]}\n"
                f"lvl1 sample={list(lvl1)[:6]}"
            )

        def _is_flat(col):
            if not isinstance(col, tuple):
                return True
            return (col[1] is None) or (str(col[1]).strip() == "")

        flat_cols = [c for c in df.columns if _is_flat(c)]
        two_cols  = [c for c in df.columns if not _is_flat(c)]

        flat = df[flat_cols].copy() if flat_cols else pd.DataFrame(index=df.index)
        two_level = df[two_cols].copy()

        long = two_level.stack(level=symbol_level, future_stack=True).reset_index()

        # Name the symbol column consistently (robust fallback)
        sym_col_name = two_level.columns.names[symbol_level] or "symbol"
        if sym_col_name not in long.columns:
            # robust fallback: search for common auto names
            candidates = []
            for c in long.columns:
                cl = str(c).lower()
                if cl in ("ticker", "symbol", "level_0", "level_1", "level_2"):
                    candidates.append(c)
            if candidates:
                sym_col_name = candidates[-1]  # pick the last (often the stacked level)
            else:
                # last resort: if multiple 'level_*' present, the last one is often the stacked level
                level_like = [c for c in long.columns if str(c).lower().startswith("level_")]
                if level_like:
                    sym_col_name = level_like[-1]
                else:
                    raise ValueError(
                        f"Stacked frame has no obvious symbol column. Columns={list(long.columns)}"
                    )
        long = long.rename(columns={sym_col_name: "symbol"})

        if not flat.empty:
            flat = flat.copy()
            # flatten ('metric','') -> 'metric'
            flat.columns = [(c[0] if isinstance(c, tuple) else c) for c in flat.columns]

            # ✅ NEW: prevent flat 'symbol' from entering the merge
            flat = flat.drop(columns=["symbol"], errors="ignore")

            # find the level_* column produced by stack().reset_index()
            idx_col = None
            for c in long.columns:
                if str(c).startswith("level_"):
                    idx_col = c
                    break
            if idx_col is not None:
                right = flat.reset_index()
                long = long.merge(right, left_on=idx_col, right_on="index", how="left")
                long = long.drop(columns=[idx_col, "index"], errors="ignore")

        # ✅ NEW: if a duplicate slipped through, normalize it
        if "symbol_x" in long.columns or "symbol_y" in long.columns:
            if "symbol_x" in long.columns:
                long = (
                    long.drop(columns=["symbol_y"], errors="ignore")
                        .rename(columns={"symbol_x": "symbol"})
                )
            else:
                long = long.rename(columns={"symbol_y": "symbol"})


        long = long.loc[:, ~long.columns.duplicated()].copy()
        if isinstance(long.get("symbol"), pd.DataFrame):
            long["symbol"] = long["symbol"].iloc[:, 0]

        # numerics
        for c in ["open", "high", "low", "close"]:
            if c in long.columns:
                long[c] = pd.to_numeric(long[c], errors="coerce")
        if "vwap" not in long.columns or long["vwap"].isna().all():
            if all(c in long.columns for c in ("high", "low", "close")):
                long["vwap"] = ((long["high"] + long["low"] + long["close"]) / 3).round(6)

        if "is_trading_day" not in long.columns:
            long["is_trading_day"] = 1

        # date → dt
        if "dt" not in long.columns:
            if "date" in long.columns:
                long = long.rename(columns={"date": "dt"})
            else:
                picked = None
                for c in long.columns:
                    if c == "symbol":
                        continue
                    t = pd.to_datetime(long[c], errors="coerce")
                    if t.notna().mean() > 0.8:
                        long["dt"] = t
                        picked = c
                        break
                if picked is None:
                    raise ValueError("Could not infer a valid date column for 'dt'.")
        long["dt"] = pd.to_datetime(long["dt"], errors="coerce").dt.date

    else:
        # --- Non-MI path (already long) ---
        long = df.copy()
        long.columns = [str(c).strip().lower() for c in long.columns]
        # allow common synonyms for symbol
        for alt in ("ticker", "code"):
            if alt in long.columns and "symbol" not in long.columns:
                long = long.rename(columns={alt: "symbol"})
        if "symbol" not in long.columns:
            # Not actually long → tell the user what we saw
            raise ValueError(
                "Non-MultiIndex input without a 'symbol' column.\n"
                f"Columns seen: {list(long.columns)[:12]} ...\n"
                "If your columns are wide like 'open.2330.TW' or '2330.TW_open', "
                "please ensure they match the accepted patterns or set MultiIndex upstream."
            )
        if "date" in long.columns and "dt" not in long.columns:
            long = long.rename(columns={"date": "dt"})
        if "dt" not in long.columns:
            raise ValueError("Missing 'dt' column.")
        long["dt"] = pd.to_datetime(long["dt"], errors="coerce").dt.date
        if "vwap" not in long.columns and all(c in long.columns for c in ("high", "low", "close")):
            for c in ["open", "high", "low", "close"]:
                if c in long.columns:
                    long[c] = pd.to_numeric(long.get(c), errors="coerce")
            long["vwap"] = ((long["high"] + long["low"] + long["close"]) / 3).round(6)
        if "is_trading_day" not in long.columns:
            long["is_trading_day"] = 1

    # --- unify schema ---
    if "symbol" not in long.columns:
        # one last explicit fail with context
        raise ValueError(f"'symbol' column still missing. Current columns: {list(long.columns)}")

    long["symbol"] = long["symbol"].astype("string").str.strip().str.lower()

    keep = ["dt", "symbol", "open", "high", "low", "close", "volume", "vwap", "is_trading_day"]
    for k in keep:
        if k not in long.columns:
            long[k] = pd.NA

    for c in ["open", "high", "low", "close", "vwap"]:
        long[c] = pd.to_numeric(long[c], errors="coerce")
    long["volume"] = pd.to_numeric(long["volume"], errors="coerce")

    # drop rows where ALL OHLCV are missing
    long = long.dropna(subset=["open", "high", "low", "close", "volume"], how="all")

    if require_full_ohlcv:
        probs = [c for c in ["open", "high", "low", "close", "volume"] if long[c].isna().all()]
        if probs:
            raise RuntimeError(f"Upstream missing required OHLCV: {probs}")

    long = long[keep]
    long = long.loc[:, ~long.columns.duplicated()]
    return long

def write_local_partitions(df: pd.DataFrame) -> None:
    if df.empty:
        print("NO_DATA"); return

    # clean local cache
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True, exist_ok=True)

    # ensure 1D columns & stable dtypes
    df = df.loc[:, ~df.columns.duplicated()]
    df["symbol"] = df["symbol"].astype("string").str.strip().str.lower()

    dt_coerced = pd.to_datetime(df["dt"], errors="coerce")
    df = df.loc[dt_coerced.notna() & df["symbol"].notna()].copy()
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce").dt.date

    for c in ["open","high","low","close","vwap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    # If volume is truly missing, set to 0; otherwise keep original numeric
    df["volume"] = df["volume"].fillna(0).astype("Int64")

    for (sym, day), g in df.groupby(["symbol","dt"], sort=True):
        out = ROOT / f"symbol={sym}" / f"dt={day}"
        out.mkdir(parents=True, exist_ok=True)

        # --- Tripwire: show what will be written
        # print(f"WRITING PARTITION: symbol={sym} dt={day}")
        # print(g[DATA_COLS].head().to_string(index=False))

        tbl = pa.Table.from_pandas(g[DATA_COLS], preserve_index=False)
        pq.write_table(tbl, out / "part-0.parquet")

        # --- Tripwire: immediate readback to confirm schema/values
        test_read = pq.read_table(out / "part-0.parquet").to_pandas()
        # print(f"READBACK PARTITION: symbol={sym} dt={day}")
        # print(test_read.head().to_string(index=False))

        # Optional: assert readback equals what we wrote (for first row)
        for k in ["open","high","low","close","vwap"]:
            a = float(g.iloc[0][k]) if pd.notna(g.iloc[0][k]) else None
            b = float(test_read.iloc[0][k]) if pd.notna(test_read.iloc[0][k]) else None
            if a != b:
                raise AssertionError(f"Mismatch after Parquet write: {k} wrote={a} read={b}")



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
    import os

    import pandas as pd
    from src.etl.tw_stocks.fetch_normalize import fetch_ohlcv
    from src.etl.tw_stocks.write_parquet_hdfs import to_long
    # assuming these are already imported/defined somewhere in your module:
    # from src.etl.tw_stocks.write_parquet_hdfs import write_local_partitions, hdfs_put_tree, ROOT, HDFS_PATH, HDFS_USER

    symbols = os.environ["TW_SYMBOLS"].split(",")
    start = os.environ.get("START_DATE", "2024-01-01")
    end   = os.environ.get("END_DATE", "auto")
    VERBOSE = os.environ.get("VERBOSE", "0") == "1"

    # 1) Fetch
    raw = fetch_ohlcv(symbols, start, end)
    # 👇 add this guard
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        print("NO_NEW_DATA: fetch_ohlcv returned empty for the requested range")
        import sys; sys.exit(0)
        
    # 2) Normalize (strict during pipeline)
    df = to_long(raw, require_full_ohlcv=True)
    if df is None or df.empty:
        print("NO_NEW_DATA: nothing to write after normalization")
        import sys; sys.exit(0)

    # 3) Sanitize minimal fields
    df["symbol"] = df["symbol"].astype("string").str.strip().str.lower()
    df = df[df["symbol"].notna()].copy()
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce")
    df = df[df["dt"].notna()].copy()

    # 4) Light sanity checks
    metric_cols = ["open", "high", "low", "close", "volume", "vwap"]
    missing = [c for c in metric_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing metric columns after to_long(): {missing}")

    ohlc_nulls = df[["open", "high", "low", "close"]].isna().sum().sum()
    if ohlc_nulls >= 10:
        raise ValueError(f"Too many OHLC nulls ({ohlc_nulls}) – investigate upstream.")

    zero_vol_ratio = (df["volume"].fillna(0) == 0).mean()
    if zero_vol_ratio >= 0.5:
        raise ValueError(f"Suspicious share of zero volumes ({zero_vol_ratio:.2%}).")

    # 5) Optional verbose info (off by default)
    if VERBOSE:
        non_nulls = df[["open","high","low","close","volume","vwap"]].notna().sum().to_dict()
        print("NON-NULL COUNTS:", non_nulls)
        print("EFFECTIVE SYMBOLS:", sorted(df["symbol"].unique().tolist())[:10])
        print("DT RANGE:", df["dt"].min().date(), "->", df["dt"].max().date())

    # 6) Write & upload
    write_local_partitions(df)      # converts dt to .date and enforces dtypes
    hdfs_put_tree(ROOT, HDFS_PATH)  # WebHDFS with user.name

    # 7) Minimal success line
    print("OK: wrote partitions and uploaded to HDFS:",
          HDFS_PATH,
          "symbols=", len(df["symbol"].unique()),
          "rows=", len(df),
          flush=True)

