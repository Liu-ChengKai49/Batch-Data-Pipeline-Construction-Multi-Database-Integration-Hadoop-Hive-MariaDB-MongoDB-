from types import SimpleNamespace


def test_mariadb_conn_uses_env(monkeypatch):
    # Arrange env
    monkeypatch.setenv("MARIADB_HOST", "10.0.0.9")
    monkeypatch.setenv("MARIADB_PORT", "4406")
    monkeypatch.setenv("MARIADB_USER", "u")
    monkeypatch.setenv("MARIADB_PASSWORD", "p")
    monkeypatch.setenv("MARIADB_DB", "d")

    # Capture args passed to pymysql.connect
    called = {}

    def fake_connect(**kwargs):
        called.update(kwargs)
        # return a minimal fake connection with context-managed cursor
        class _Cur:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def executemany(self, *a, **k): pass
        return SimpleNamespace(cursor=lambda: _Cur())

    import batch_pipeline.db as db
    monkeypatch.setattr(db.pymysql, "connect", fake_connect)

    # Act
    conn = db.mariadb_conn()

    # Assert: function executed and forwarded env into connect()
    assert conn is not None
    assert called["host"] == "10.0.0.9"
    assert called["port"] == 4406  # string env should be cast to int
    assert called["user"] == "u"
    assert called["password"] == "p"
    assert called["database"] == "d"
    assert called["autocommit"] is True
    assert "cursorclass" in called  # we don’t care about exact class here
