from batch_pipeline.db import build_upsert_sql


def test_build_upsert_sql_with_database():
    sql = build_upsert_sql(table="prices_daily", database="demo")
    # qualified target and positional placeholders
    assert "INSERT INTO demo.prices_daily" in sql
    assert sql.count("%s") == 9
