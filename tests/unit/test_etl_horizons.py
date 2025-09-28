import pandas as pd
import pytest

from batch_pipeline.etl import compute_returns


def test_compute_returns_horizons_and_sorting():
    # 31 days so 1d, 7d, and 30d are all defined.
    rows = [{"symbol": "AAA", "dt": f"2025-01-{i:02d}", "close": 99 + i} for i in range(1, 32)]
    df = pd.DataFrame(rows)

    out = compute_returns(df)

    # Columns exist
    assert {"return_1d", "return_7d", "return_30d"} <= set(out.columns)

    # exact rows (use approx to avoid tiny float flakes)
    r1 = out.loc[out["dt"] == "2025-01-02", "return_1d"].iloc[0]      # (101-100)/100
    r7 = out.loc[out["dt"] == "2025-01-08", "return_7d"].iloc[0]      # (107-100)/100
    r30 = out.loc[out["dt"] == "2025-01-31", "return_30d"].iloc[0]    # (130-100)/100

    assert r1  == pytest.approx(0.01)
    assert r7  == pytest.approx(0.07)
    assert r30 == pytest.approx(0.30)


def test_compute_returns_type_error():
    # exercise the bad-type branch
    with pytest.raises(TypeError):
        compute_returns(123)  # not a DataFrame or dict
