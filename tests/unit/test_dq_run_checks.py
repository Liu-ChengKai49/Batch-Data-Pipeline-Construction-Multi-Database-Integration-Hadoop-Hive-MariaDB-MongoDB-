import builtins
import pandas as pd
import dq.run_checks as rc
import pytest


def test_run_all_checks_ok(monkeypatch):
    # disable freshness for this test
    rc.FRESHNESS_DAYS = None

    # _q() is called 5 times when freshness is disabled:
    # 1) rowcount  2) nulls  3) domain  4) ranges  5) dupes
    seq = iter([
        pd.DataFrame([[1]]),              # COUNT(*) -> 1 (ok)
        pd.DataFrame([[0]]),              # nulls -> 0 (ok)
        pd.DataFrame([[0]]),              # domain bad -> 0 (ok)
        pd.DataFrame([[0, 0, 0, 0]]),     # ranges -> all zeros (ok)
        pd.DataFrame([[10, 10]]),         # total_rows=10, distinct_rows=10 (ok)
    ])

    monkeypatch.setattr(rc, "_q", lambda _: next(seq))
    assert rc.run_all_checks() == []


def test_run_all_checks_freshness_violation(monkeypatch):
    # enable freshness gate to 7 days
    rc.FRESHNESS_DAYS = "7"

    # Now _q() is called 6 times: the 5 above + 1 freshness query
    seq = iter([
        pd.DataFrame([[1]]),              # rowcount ok
        pd.DataFrame([[0]]),              # nulls ok
        pd.DataFrame([[0]]),              # domain ok
        pd.DataFrame([[0, 0, 0, 0]]),     # ranges ok
        pd.DataFrame([[10, 10]]),         # dupes ok
        pd.DataFrame([[15]]),             # freshness -> days_since_max = 15 (>7)
    ])
    monkeypatch.setattr(rc, "_q", lambda _: next(seq))
    violations = rc.run_all_checks()
    assert any(v.startswith("FRESHNESS:") for v in violations)


def test_main_ok_exit_code(monkeypatch):
    rc.FRESHNESS_DAYS = None
    monkeypatch.setattr(rc, "run_all_checks", lambda: [])
    monkeypatch.setattr(rc, "push_dq_metric", lambda n: None)

    with pytest.raises(SystemExit) as ex:
        rc.main()
    assert ex.value.code == 0


def test_main_fail_exit_code(monkeypatch):
    rc.FRESHNESS_DAYS = None
    monkeypatch.setattr(rc, "run_all_checks", lambda: ["something bad"])
    monkeypatch.setattr(rc, "push_dq_metric", lambda n: None)

    with pytest.raises(SystemExit) as ex:
        rc.main()
    assert ex.value.code == 1


def test_push_dq_metric_uses_prometheus(monkeypatch):
    # Provide a tiny fake prometheus_client so we don't need the real package.
    pushed = {}
    class FakeGauge:
        def __init__(self, *_a, **_k): pass
        def set(self, v): pushed["gauge"] = float(v)

    class FakeReg: pass

    def fake_push(url, job, grouping_key, registry):
        pushed["url"] = url
        pushed["job"] = job
        pushed["grouping_key"] = grouping_key

    class FakeMod:
        CollectorRegistry = FakeReg
        Gauge = FakeGauge
        push_to_gateway = staticmethod(fake_push)

    import sys
    monkeypatch.setitem(sys.modules, "prometheus_client", FakeMod)

    # run
    rc.push_dq_metric(3)

    assert pushed["gauge"] == 3.0
    assert "url" in pushed and "job" in pushed and "grouping_key" in pushed


def test_run_all_checks_all_fail(monkeypatch):
    # Enable freshness check and make every gate fail once
    rc.FRESHNESS_DAYS = "7"

    # Calls in order:
    # 1) rowcount -> 0  (fail)
    # 2) nulls    -> 5  (fail)
    # 3) domain   -> 1  (fail)
    # 4) ranges   -> negs=1, high<low=1, open_o=1, close_o=1 (all fail)
    # 5) dupes    -> total=10, distinct=8 (fail)
    # 6) freshness-> days_since_max=15 (>7) (fail)
    seq = iter([
        pd.DataFrame([[0]]),
        pd.DataFrame([[5]]),
        pd.DataFrame([[1]]),
        pd.DataFrame([[1, 1, 1, 1]]),
        pd.DataFrame([[10, 8]]),
        pd.DataFrame([[15]]),
    ])

    monkeypatch.setattr(rc, "_q", lambda _sql: next(seq))
    v = rc.run_all_checks()

    # We expect at least one message per gate fired above
    assert any(s.startswith("ROWCOUNT:") for s in v)
    assert any(s.startswith("NULLS:") for s in v)
    assert any(s.startswith("DOMAIN:") for s in v)
    assert any("RANGE: negative values" in s for s in v)
    assert any("LOGIC: high < low" in s for s in v)
    assert any("open outside" in s for s in v)
    assert any("close outside" in s for s in v)
    assert any(s.startswith("DUPES:") for s in v)
    assert any(s.startswith("FRESHNESS:") for s in v)


def test_push_dq_metric_import_error(monkeypatch, capsys):
    # Simulate ImportError when importing prometheus_client
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "prometheus_client":
            raise ImportError("not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    rc.push_dq_metric(2)
    out = capsys.readouterr().err
    assert "prometheus_client not installed" in out