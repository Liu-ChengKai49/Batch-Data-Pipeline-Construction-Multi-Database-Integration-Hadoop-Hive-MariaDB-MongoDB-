import pytest

from batch_pipeline.etl import compute_returns, make_partition_path


def test_partition_path_ok():
    assert make_partition_path("2019-01-15") == "dt=2019-01-15/"

def test_partition_path_bad():
    with pytest.raises(ValueError):
        make_partition_path("bad-date")

def test_compute_returns_normal():
    row = {"open": 10.0, "close": 12.0}
    assert compute_returns(row) == 0.2

def test_compute_returns_zero_open():
    row = {"open": 0.0, "close": 12.0}
    assert compute_returns(row) == 0.0
