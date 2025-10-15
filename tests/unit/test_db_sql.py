from unittest.mock import MagicMock

from batch_pipeline.db import build_upsert_sql, upsert_prices


def test_build_upsert_sql_shape():
    sql = build_upsert_sql("prices_daily")
    assert "INSERT INTO prices_daily" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    # exactly 9 placeholders
    assert sql.count("%s") == 9

def test_upsert_prices_calls_executemany():
    # Fake connection + cursor (context-managed)
    fake_conn = MagicMock()
    fake_cur = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cur

    # _current_db() runs: SELECT DATABASE() AS db -> need a dict row back
    fake_cur.fetchone.return_value = {"db": "market"}

    rows = [
        {"symbol": "2330", "dt": "2025-09-26", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 5},
        {"symbol": "2303", "dt": "2025-09-26", "open": 20, "high": 22, "low": 19, "close": 20, "volume": 7},
    ]

    n = upsert_prices(fake_conn, rows, table="prices_daily")

    # returns number of rows attempted
    assert n == 2

    # executemany called once with 2 param tuples
    assert fake_cur.executemany.call_count == 1
    sql, param_list = fake_cur.executemany.call_args[0]
    assert len(param_list) == 2

    # Each tuple now has 9 values: (symbol, dt, open, high, low, close, volume, vwap, is_trading_day)
    assert len(param_list[0]) == 9
    assert len(param_list[1]) == 9

    # Defaults: vwap defaults to close; is_trading_day defaults to 1
    # Indexes: 0:symbol,1:dt,2:open,3:high,4:low,5:close,6:volume,7:vwap,8:is_trading_day
    assert param_list[0][7] == param_list[0][5]
    assert param_list[1][7] == param_list[1][5]
    assert param_list[0][8] == 1
    assert param_list[1][8] == 1

    # Commit is called (explicit commit in upsert)
    assert fake_conn.commit.called