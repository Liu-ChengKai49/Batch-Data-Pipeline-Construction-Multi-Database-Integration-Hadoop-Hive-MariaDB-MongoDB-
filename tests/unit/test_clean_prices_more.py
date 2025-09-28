import pandas as pd

from batch_pipeline.etl import clean_prices


def test_clean_prices_clamp_and_types():
    df = pd.DataFrame([
        # close above high → gets clamped to high; negative volume → clipped to 0
        {"symbol": 123, "dt": "2025-01-01", "open": "10", "high": "12", "low": "9", "close": "20", "volume": -5},
        # normal row passes through
        {"symbol": "AAA", "dt": "2025-01-02", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 7},
    ])
    out = clean_prices(df)

    # types and column selection
    assert list(out.columns) == ["symbol", "dt", "open", "high", "low", "close", "volume"]
    assert out.dtypes.to_dict()["symbol"].name == "object"  # coerced to str
    assert out.loc[0, "dt"] == "2025-01-01"

    # clamp & clip
    assert out.loc[0, "close"] == 12.0  # clamped to high
    assert out.loc[0, "volume"] == 0    # clipped at lower bound

    # second row unchanged
    assert out.loc[1, "close"] == 11.0
    assert out.loc[1, "volume"] == 7
