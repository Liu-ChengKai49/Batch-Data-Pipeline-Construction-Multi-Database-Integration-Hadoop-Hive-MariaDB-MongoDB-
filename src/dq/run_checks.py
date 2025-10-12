# src/dq/run_checks.py
from __future__ import annotations

import os
import sys
import pandas as pd

from sqlalchemy import create_engine, text
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # editor/type-checker hints only; no runtime import
    from prometheus_client import CollectorRegistry as _CollectorRegistry, Gauge as _Gauge
    from prometheus_client import push_to_gateway as _push_to_gateway

# Env config (your docker compose exports will override these defaults)
REQ_ENV = {
    "MARIADB_HOST": os.getenv("MARIADB_HOST", "mariadb"),
    "MARIADB_PORT": int(os.getenv("MARIADB_PORT", "3306")),
    "MARIADB_USER": os.getenv("MARIADB_USER", "root"),
    "MARIADB_PASSWORD": os.getenv("MARIADB_PASSWORD", os.getenv("MARIADB_ROOT_PASSWORD", "")),
    "MARIADB_DB": os.getenv("MARIADB_DB", "market"),
    "TABLE": os.getenv("DQ_TABLE", "market.prices_daily"),
}

# Optional freshness gate: set DQ_FRESHNESS_DAYS (e.g., "7")
FRESHNESS_DAYS = os.getenv("DQ_FRESHNESS_DAYS")

# NEW: Pushgateway URL (inside compose: http://pushgateway:9091; from host: http://localhost:9091)
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091")
INSTANCE = os.getenv("HOSTNAME", "jupyterlab")
JOB_NAME = os.getenv("DQ_JOB_NAME", "dq_pipeline")

def _engine():
    uri = (
        f"mariadb+pymysql://{REQ_ENV['MARIADB_USER']}:{REQ_ENV['MARIADB_PASSWORD']}"
        f"@{REQ_ENV['MARIADB_HOST']}:{REQ_ENV['MARIADB_PORT']}/{REQ_ENV['MARIADB_DB']}"
    )
    return create_engine(uri, pool_pre_ping=True)

def _q(sql: str) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(text(sql), conn)

def check_rowcount_positive(violations: list[str]):
    df = _q(f"SELECT COUNT(*) AS cnt FROM {REQ_ENV['TABLE']}")
    cnt = int(df.iloc[0, 0] or 0)
    if cnt <= 0:
        violations.append("ROWCOUNT: expected > 0")

def check_no_nulls(violations: list[str]):
    cols = ["dt","symbol","open","high","low","close","volume","vwap","is_trading_day"]
    exprs = [f"COALESCE(SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END),0)" for c in cols]
    df = _q(f"SELECT ({' + '.join(exprs)}) AS nulls FROM {REQ_ENV['TABLE']}")
    nulls = int(df.iloc[0, 0] or 0)
    if nulls != 0:
        violations.append(f"NULLS: found {nulls} nulls across {cols}")

def check_domains_and_ranges(violations: list[str]):
    df = _q(f"""
        SELECT COALESCE(SUM(CASE
                 WHEN is_trading_day NOT IN (0,1) OR is_trading_day IS NULL
                 THEN 1 ELSE 0 END), 0) AS bad
        FROM {REQ_ENV['TABLE']}
    """)
    bad = int(df.iloc[0, 0] or 0)
    if bad != 0:
        violations.append("DOMAIN: is_trading_day must be 0/1 only")

    df = _q(f"""
        SELECT
          COALESCE(SUM(CASE
            WHEN open  < 0 OR high < 0 OR low < 0 OR close < 0 OR volume < 0 OR vwap < 0
          THEN 1 ELSE 0 END),0) AS negs,
          COALESCE(SUM(CASE WHEN high < low THEN 1 ELSE 0 END),0) AS high_lt_low,
          COALESCE(SUM(CASE WHEN open  < low OR open  > high THEN 1 ELSE 0 END),0) AS open_outside_range,
          COALESCE(SUM(CASE WHEN close < low OR close > high THEN 1 ELSE 0 END),0) AS close_outside_range
        FROM {REQ_ENV['TABLE']}
    """)
    negs, high_lt_low, open_o, close_o = map(int, df.iloc[0].tolist())
    if negs:        violations.append(f"RANGE: negative values present ({negs})")
    if high_lt_low: violations.append(f"LOGIC: high < low rows ({high_lt_low})")
    if open_o:      violations.append(f"LOGIC: open outside [low,high] rows ({open_o})")
    if close_o:     violations.append(f"LOGIC: close outside [low,high] rows ({close_o})")

def check_no_dupes_by_key(violations: list[str]):
    df = _q(f"""
        SELECT
          (SELECT COALESCE(COUNT(*),0) FROM {REQ_ENV['TABLE']}) AS total_rows,
          (SELECT COALESCE(COUNT(*),0)
             FROM (SELECT dt, symbol FROM {REQ_ENV['TABLE']} GROUP BY dt, symbol) t) AS distinct_rows
    """)
    total_rows, distinct_rows = map(int, df.iloc[0].tolist())
    if distinct_rows != total_rows:
        violations.append(f"DUPES: duplicate (dt,symbol) rows ({total_rows - distinct_rows})")

def check_freshness_if_enabled(violations: list[str]):
    if not FRESHNESS_DAYS:
        return
    try:
        days = int(FRESHNESS_DAYS)
    except ValueError:
        violations.append("CONFIG: DQ_FRESHNESS_DAYS must be integer")
        return
    df = _q(f"""
        SELECT COALESCE(DATEDIFF(CURRENT_DATE(), MAX(dt)), 999999) AS days_since_max
        FROM {REQ_ENV['TABLE']}
    """)
    gap = int(df.iloc[0, 0] or 999999)
    if gap > days:
        violations.append(f"FRESHNESS: last dt is {gap} days old (> {days})")

def run_all_checks() -> list[str]:
    violations: list[str] = []
    check_rowcount_positive(violations)
    check_no_nulls(violations)
    check_domains_and_ranges(violations)
    check_no_dupes_by_key(violations)
    check_freshness_if_enabled(violations)
    return violations

# NEW: push to Pushgateway (gracefully no-op if prometheus_client missing)
def push_dq_metric(n_fails: int) -> None:
    """
    Push dq_failures_total to Pushgateway.
    If prometheus_client is not installed, skip gracefully.
    """
    try:
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
    except Exception:
        print("WARN: prometheus_client not installed; skip Pushgateway", file=sys.stderr)
        return

    try:
        reg = CollectorRegistry()
        g = Gauge("dq_failures_total", "Number of last DQ failures", registry=reg)
        g.set(float(n_fails))
        push_to_gateway(
            PUSHGATEWAY_URL,
            job=JOB_NAME,
            grouping_key={"instance": INSTANCE, "table": REQ_ENV["TABLE"]},
            registry=reg,
        )
        print(f"PUSHED dq_failures_total={n_fails} to {PUSHGATEWAY_URL} (job={JOB_NAME})")
    except Exception as e:
        print(f"WARN: pushgateway push failed: {e}", file=sys.stderr)


def main():
    violations = run_all_checks()
    n_fails = len(violations)
    # Push regardless of status so Grafana always shows the latest value
    push_dq_metric(n_fails)

    if violations:
        print("DQ_FAIL")
        for v in violations:
            print("-", v)
        sys.exit(1)
    else:
        print("DQ_OK")
        sys.exit(0)

if __name__ == "__main__":
    main()
