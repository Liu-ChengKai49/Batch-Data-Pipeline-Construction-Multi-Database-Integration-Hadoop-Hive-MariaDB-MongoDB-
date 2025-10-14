import os


import mysql.connector as mysql
import pymongo


def mdb():
    return mysql.connect(
        host=os.getenv("MARIADB_HOST","127.0.0.1"),
        port=int(os.getenv("MARIADB_PORT","3306")),
        user=os.getenv("MARIADB_USER","root"),
        password=os.getenv("MARIADB_PASSWORD","root"),
        database=os.getenv("MARIADB_DB","market"),
    )

def mgdb():
    return pymongo.MongoClient(os.getenv("MONGODB_URI","mongodb://127.0.0.1:27017/market")).get_database()

def test_rowcount_pk_nulls():
    conn = mdb() 
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM prices_daily") 
    assert cur.fetchone()[0] >= 3
    cur.execute("SELECT COUNT(*) = COUNT(DISTINCT dt, symbol) FROM prices_daily") 
    assert cur.fetchone()[0] == 1
    cur.execute("""
      SELECT COALESCE(SUM(
        (dt IS NULL) + (symbol IS NULL) + (open IS NULL) + (close IS NULL) +
        (high IS NULL) + (low IS NULL) + (volume IS NULL) + (vwap IS NULL) +
        (is_trading_day IS NULL)
      ),0) FROM prices_daily
    """) 
    assert cur.fetchone()[0] == 0
    conn.close()

def test_schema_drift():
    conn = mdb() 
    cur = conn.cursor()
    cur.execute("""
      SELECT COLUMN_NAME, DATA_TYPE
      FROM information_schema.columns
      WHERE table_schema=%s AND table_name=%s
    """, (os.getenv("MARIADB_DB","market"), "prices_daily"))
    got = dict(cur.fetchall())
    expected = {
      "dt":"date","symbol":"varchar","open":"decimal","high":"decimal","low":"decimal",
      "close":"decimal","volume":"bigint","vwap":"decimal","is_trading_day":"tinyint"
    }
    for k,v in expected.items(): 
        assert got.get(k) == v
    conn.close()

def test_mongo_loaded():
    db = mgdb()
    assert db.get_collection("raw").count_documents({}) >= 2
