SET hivevar:hive_db=default;
SET hivevar:hdfs_path=/data/stocks;

CREATE DATABASE IF NOT EXISTS ${hivevar:hive_db};
USE ${hivevar:hive_db};

CREATE EXTERNAL TABLE IF NOT EXISTS stocks_prices_raw (
  open DECIMAL(18,4),
  high DECIMAL(18,4),
  low  DECIMAL(18,4),
  close DECIMAL(18,4),
  volume BIGINT,
  vwap DECIMAL(18,6),
  is_trading_day TINYINT
)
PARTITIONED BY (symbol STRING, dt DATE)
STORED AS PARQUET
LOCATION '${hivevar:hdfs_path}';

MSCK REPAIR TABLE stocks_prices_raw;
