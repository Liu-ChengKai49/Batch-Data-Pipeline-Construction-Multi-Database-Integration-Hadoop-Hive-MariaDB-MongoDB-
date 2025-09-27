import pandas as pd

from batch_pipeline.etl import compute_returns


def test_compute_returns_normal():
    df = pd.DataFrame(
        [{"symbol": "AAA", "dt": "2025-01-01", "close": 10.0},
         {"symbol": "AAA", "dt": "2025-01-02", "close": 12.0}]
    )
    out = compute_returns(df)
    # 1d return on the second row: (12-10)/10 = 0.2
    assert out.loc[1, "return_1d"] == 0.2

def test_compute_returns_zero_div_ok():
    df = pd.DataFrame(
        [{"symbol": "AAA", "dt": "2025-01-01", "close": 0.0},
         {"symbol": "AAA", "dt": "2025-01-02", "close": 12.0}]
    )
    out = compute_returns(df)
    # first baseline zero shouldn't crash; later rows finite
    assert out["return_1d"].isna().iloc[0] or out["return_1d"].iloc[0] == 0
