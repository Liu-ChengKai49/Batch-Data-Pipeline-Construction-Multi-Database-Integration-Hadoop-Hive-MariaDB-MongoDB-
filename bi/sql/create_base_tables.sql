-- Schema: use current DB (set by -D in the Makefile)
-- Base dimension: symbols
CREATE TABLE IF NOT EXISTS symbols_dim (
  symbol      VARCHAR(32)  NOT NULL PRIMARY KEY,
  name        VARCHAR(255) NULL,
  sector      VARCHAR(128) NULL,
  industry    VARCHAR(128) NULL,
  exchange    VARCHAR(64)  NULL,
  is_active   TINYINT(1)   NOT NULL DEFAULT 1,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Base fact: daily prices (idempotent)
CREATE TABLE IF NOT EXISTS prices_daily (
  dt            DATE        NOT NULL,
  symbol        VARCHAR(32) NOT NULL,
  open          DECIMAL(18,6) NULL,
  high          DECIMAL(18,6) NULL,
  low           DECIMAL(18,6) NULL,
  close         DECIMAL(18,6) NULL,
  volume        BIGINT       NULL,
  vwap          DECIMAL(18,6) NULL,
  is_trading_day TINYINT(1)  NULL DEFAULT 1,
  updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (symbol, dt),
  KEY idx_dt (dt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
