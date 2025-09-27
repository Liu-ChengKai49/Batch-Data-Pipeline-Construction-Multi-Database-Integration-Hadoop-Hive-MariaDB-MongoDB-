def partition_path(dt: str) -> str:
    return f"dt={dt}/"

def test_partition_path():
    assert partition_path("2025-09-01") == "dt=2025-09-01/"


