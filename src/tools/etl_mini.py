# tools/etl_mini.py
from batch_pipeline import etl  # import your ETL entry points here

if __name__ == "__main__":
    # call whatever small subset loads ~a week / ≤200 rows
    etl.run(start="2024-01-01", end="2024-01-07", limit=200)
