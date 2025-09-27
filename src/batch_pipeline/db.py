import os, typing as t, pymysql

def mariadb_conn():
    return pymysql.connect(
        host=os.getenv("MARIADB_HOST","127.0.0.1"),
        user=os.getenv("MARIADB_USER","root"),
        password=os.getenv("MARIADB_PASSWORD","root"),
        database=os.getenv("MARIADB_DB","demo"),
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )

def upsert_prices(rows: t.Iterable[dict]) -> int:
    sql = """
    CREATE TABLE IF NOT EXISTS prices_daily_mart (
        symbol VARCHAR(16), dt DATE,
        open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT,
        PRIMARY KEY(symbol, dt)
    ) ENGINE=InnoDB;
    """
    with mariadb_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        stmt = """
        INSERT INTO prices_daily_mart (symbol, dt, open, high, low, close, volume)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
          open=VALUES(open), high=VALUES(high), low=VALUES(low),
          close=VALUES(close), volume=VALUES(volume);
        """
        data = [(r["symbol"], r["dt"], r["open"], r["high"], r["low"], r["close"], r["volume"]) for r in rows]
        if not data: return 0
        cur.executemany(stmt, data)
        return cur.rowcount
