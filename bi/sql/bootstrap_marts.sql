-- bi/sql/bootstrap_marts.sql
CREATE DATABASE IF NOT EXISTS market;
USE market;

CREATE TABLE IF NOT EXISTS prices_daily (
  dt DATE NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  open  DECIMAL(18,4),
  high  DECIMAL(18,4),
  low   DECIMAL(18,4),
  close DECIMAL(18,4),
  volume BIGINT,
  vwap   DECIMAL(18,6),
  is_trading_day TINYINT,
  PRIMARY KEY (dt, symbol)
) ENGINE=InnoDB;
