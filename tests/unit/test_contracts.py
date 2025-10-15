# tests/unit/test_contracts.py
import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings

from batch_pipeline.utils import PriceRow, clamp_close


@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=50)
@given(
    symbol=st.text(min_size=1, max_size=8),          # optional: bound to speed up
    dt=st.dates().map(lambda d: d.isoformat()),
    low=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    high=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    close=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    volume=st.integers(min_value=0, max_value=10_000_000),
)
def test_price_contract_and_clamp(symbol, dt, low, high, close, volume):
    if low > high: 
        low, high = high, low
    row = PriceRow(symbol=symbol, dt=dt, open=low, high=high, low=low, close=close, volume=volume)
    clamped = clamp_close(row)
    assert row.low <= clamped <= row.high
