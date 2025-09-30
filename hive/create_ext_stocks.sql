-- create_ext_stocks.sql  (final)

SET hivevar:hive_db = default;
-- If you wrote the repaired data under a new root (e.g. /data/stocks_long), change this:
SET hivevar:hdfs_path = /data/stocks;

-- Read Parquet by column name (safer than by position)
-- SET hive.parquet.use-column-names = true;

CREATE DATABASE IF NOT EXISTS ${hivevar:hive_db};
USE ${hivevar:hive_db};

-- Recreate to avoid lingering wrong schema
DROP TABLE IF EXISTS stocks_prices_raw;

CREATE EXTERNAL TABLE stocks_prices_raw (
  -- Only the columns actually stored inside each Parquet file
  open            DOUBLE,
  high            DOUBLE,
  low             DOUBLE,
  close           DOUBLE,
  volume          BIGINT,
  vwap            DOUBLE,
  is_trading_day  TINYINT
)
-- Folder partitions (must match your directory layout)
PARTITIONED BY (symbol STRING, dt DATE)
STORED AS PARQUET
LOCATION '${hivevar:hdfs_path}';

-- Discover partitions from directory names symbol=.../dt=...
MSCK REPAIR TABLE stocks_prices_raw;
