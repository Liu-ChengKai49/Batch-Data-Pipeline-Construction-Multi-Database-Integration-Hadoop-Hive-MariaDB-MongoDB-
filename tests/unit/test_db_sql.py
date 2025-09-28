from unittest.mock import MagicMock

from batch_pipeline.db import build_upsert_sql, upsert_prices


def test_build_upsert_sql_shape():
    sql = build_upsert_sql("prices_daily")
    assert "INSERT INTO prices_daily" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    # exactly 7 placeholders
    assert sql.count("%s") == 7

def test_upsert_prices_calls_executemany():
    fake_conn = MagicMock()
    fake_cur = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cur

    rows = [
        {"symbol": "2330", "dt": "2025-09-26", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 5},
        {"symbol": "2303", "dt": "2025-09-26", "open": 20, "high": 22, "low": 19, "close": 20, "volume": 7},
    ]
    n = upsert_prices(fake_conn, rows, table="prices_daily")

    assert n == 2
    # ensure executemany called once with 2 rows
    assert fake_cur.executemany.call_count == 1
    args, kwargs = fake_cur.executemany.call_args
    assert len(args[1]) == 2
