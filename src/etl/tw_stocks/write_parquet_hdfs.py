# etl/tw_stocks/write_parquet_hdfs.py
import os, pathlib as pl, pandas as pd, pyarrow as pa, pyarrow.parquet as pq
from etl.tw_stocks.fetch_normalize import fetch_ohlcv
import subprocess

ROOT = pl.Path("local_parquet")

def write_local_partitions(df: pd.DataFrame) -> None:
    if df.empty:
        print("NO_DATA"); return
    for (sym, day), g in df.groupby(["symbol","dt"]):
        out = ROOT / f"symbol={sym}" / f"dt={day}"
        out.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(g), out / "part-0.parquet")

def hdfs_put(local_root: pl.Path, hdfs_path: str) -> None:
    subprocess.check_call(["docker","compose","exec","namenode","hdfs","dfs","-mkdir","-p", hdfs_path])
    for p in local_root.iterdir():
        subprocess.check_call(["docker","compose","exec","namenode","hdfs","dfs","-put","-f", f"/work/{local_root}/{p.name}", hdfs_path])

if __name__ == "__main__":
    symbols = os.environ["TW_SYMBOLS"].split(",")
    start = os.environ.get("START_DATE","2024-01-01")
    end   = os.environ.get("END_DATE","auto")
    df = fetch_ohlcv(symbols, start, end)  # or TWSE provider if you set TW_SOURCE=twse
    write_local_partitions(df)
    hdfs_put(ROOT, os.environ.get("HDFS_PATH","/data/stocks"))
    print("HDFS_PUT_OK")