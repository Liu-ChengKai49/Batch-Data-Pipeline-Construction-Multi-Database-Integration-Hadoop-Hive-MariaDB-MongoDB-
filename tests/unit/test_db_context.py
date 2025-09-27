from types import SimpleNamespace

import batch_pipeline.db as db


def test_mariadb_conn_context_manager(monkeypatch):
    closed = {"n": 0}

    class _FakeConn:
        def close(self): closed["n"] += 1
        def cursor(self):  # not used here, but keep the shape
            return SimpleNamespace(__enter__=lambda s: s, __exit__=lambda *a, **k: None)

    def fake_connect(**kwargs):
        return _FakeConn()

    monkeypatch.setattr(db.pymysql, "connect", fake_connect)

    # Exercise __enter__/__exit__
    with db.mariadb_conn() as conn:
        assert conn is not None

    assert closed["n"] == 1  # __exit__ closed it
