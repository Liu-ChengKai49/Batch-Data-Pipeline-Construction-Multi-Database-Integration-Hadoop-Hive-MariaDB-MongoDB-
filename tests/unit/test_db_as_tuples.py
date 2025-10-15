from batch_pipeline.db import _as_tuples


def test_as_tuples_ordering():
    rows = [{
        "symbol": "S", "dt": "2025-01-01",
        "open": 1, "high": 3, "low": 0.5, "close": 2, "volume": 10,
        # vwap, is_trading_day omitted on purpose: defaults kick in (vwap=close, is_trading_day=1)
    }]
    tup = _as_tuples(rows)[0]
    # exact order: symbol, dt, open, high, low, close, volume, vwap, is_trading_day
    assert tup == ("S", "2025-01-01", 1, 3, 0.5, 2, 10, 2, 1)
