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

INSERT INTO prices_daily
(dt, symbol, open, high, low, close, volume, vwap, is_trading_day)
VALUES
('2024-01-02','2330.TW',1,1,1,1,10,1,1),
('2024-01-03','2330.TW',1,1,1,1,11,1,1),
('2024-01-04','2330.TW',1,1,1,1,12,1,1);
