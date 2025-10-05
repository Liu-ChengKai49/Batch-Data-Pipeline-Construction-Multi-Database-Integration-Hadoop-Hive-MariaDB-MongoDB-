-- Enriched prices view with returns and simple moving averages for BI/Tableau
-- Requires MariaDB 10.2+ for window functions (you’re on 11.x so it’s fine)

CREATE OR REPLACE VIEW vw_prices_daily AS
SELECT
  p.dt,
  LOWER(TRIM(p.symbol)) AS symbol,
  p.open,
  p.high,
  p.low,
  p.close,
  p.volume,
  p.vwap,
  p.is_trading_day,

  -- Daily / 7d / 30d simple returns (safe-divide; NULL if no lag)
  CASE
    WHEN LAG(p.close) OVER w IS NULL OR LAG(p.close) OVER w = 0 THEN NULL
    ELSE (p.close / LAG(p.close) OVER w) - 1
  END AS return_1d,

  CASE
    WHEN LAG(p.close, 7) OVER w IS NULL OR LAG(p.close, 7) OVER w = 0 THEN NULL
    ELSE (p.close / LAG(p.close, 7) OVER w) - 1
  END AS return_7d,

  CASE
    WHEN LAG(p.close, 30) OVER w IS NULL OR LAG(p.close, 30) OVER w = 0 THEN NULL
    ELSE (p.close / LAG(p.close, 30) OVER w) - 1
  END AS return_30d,

  -- MA(5/20/60) over close (rows-based)
  AVG(p.close) OVER (PARTITION BY p.symbol ORDER BY p.dt ROWS BETWEEN 4 PRECEDING  AND CURRENT ROW) AS ma_5,
  AVG(p.close) OVER (PARTITION BY p.symbol ORDER BY p.dt ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma_20,
  AVG(p.close) OVER (PARTITION BY p.symbol ORDER BY p.dt ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS ma_60

FROM prices_daily p
WINDOW w AS (PARTITION BY p.symbol ORDER BY p.dt);
