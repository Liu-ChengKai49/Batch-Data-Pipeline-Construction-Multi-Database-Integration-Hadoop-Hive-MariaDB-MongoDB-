import pytest

from batch_pipeline.etl import make_partition_path


def test_partition_path_bad_format():
    with pytest.raises(ValueError):
        make_partition_path("2025/01/01")  # should be YYYY-MM-DD
