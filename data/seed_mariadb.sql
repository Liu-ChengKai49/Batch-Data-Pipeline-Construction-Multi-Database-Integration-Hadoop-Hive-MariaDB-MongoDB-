-- data/seed_mariadb.sql
CREATE DATABASE IF NOT EXISTS market;
USE market;

CREATE TABLE IF NOT EXISTS prices_daily (
  dt DATE NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  open DECIMAL(18,6) NOT NULL,
  high DECIMAL(18,6) NOT NULL,
  low  DECIMAL(18,6) NOT NULL,
  close DECIMAL(18,6) NOT NULL,
  volume BIGINT NOT NULL,
  vwap DECIMAL(18,6) NOT NULL,
  is_trading_day TINYINT NOT NULL,
  PRIMARY KEY (dt, symbol)
) ENGINE=InnoDB;

-- make the mart a passthrough of base table for now
CREATE OR REPLACE VIEW prices_daily_mart AS
SELECT dt, symbol, open, high, low, close, volume, vwap, is_trading_day
FROM prices_daily;

-- idempotent seed
INSERT INTO prices_daily
  (dt, symbol, open, high, low, close, volume, vwap, is_trading_day)
VALUES
  ('2024-01-02','2330.TW',1,1,1,1,10,1,1),
  ('2024-01-03','2330.TW',1,1,1,1,11,1,1),
  ('2024-01-04','2330.TW',1,1,1,1,12,1,1)
ON DUPLICATE KEY UPDATE
  close=VALUES(close), volume=VALUES(volume), vwap=VALUES(vwap);
