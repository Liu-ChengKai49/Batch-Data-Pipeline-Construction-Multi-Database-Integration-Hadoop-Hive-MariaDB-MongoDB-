-- -- === analytics.taxi_monthly_summary DQ (your schema: year, month, passenger_count, avg_total_amount, n_trips) ===
-- USE analytics;
-- -- 1) Uniqueness at your summary grain (year, month, passenger_count)
-- SELECT COUNT(*) AS dup_summary_rows FROM (
--   SELECT year, month, passenger_count, COUNT(*) c
--   FROM taxi_monthly_summary
--   GROUP BY year, month, passenger_count
--   HAVING COUNT(*) > 1
-- ) t;

-- -- 2) Validity: month in [1,12], n_trips non-negative
-- SELECT
--   SUM(CASE WHEN month < 1 OR month > 12 THEN 1 ELSE 0 END) AS invalid_month,
--   SUM(CASE WHEN n_trips < 0 THEN 1 ELSE 0 END)              AS invalid_n_trips
-- FROM taxi_monthly_summary;

-- -- 3) Validity: passenger_count rules
-- --    - allow -1 as your "unknown" sentinel (since you mapped NULL-> -1.0 in Hive)
-- --    - require integer-like values (no fractional passenger counts)
-- SELECT
--   SUM(CASE WHEN passenger_count IS NULL THEN 1 ELSE 0 END)                              AS missing_passenger_count,
--   SUM(CASE WHEN passenger_count <> TRUNCATE(passenger_count,0) THEN 1 ELSE 0 END)      AS non_integer_passenger_count,
--   SUM(CASE WHEN passenger_count < -1 THEN 1 ELSE 0 END)                                 AS invalid_passenger_lt_minus1
-- FROM taxi_monthly_summary;

-- -- 4) Validity: average fare within a reasonable range (tune 0..1000 as you like)
-- SELECT
--   SUM(CASE WHEN avg_total_amount < 0 OR avg_total_amount > 1000 THEN 1 ELSE 0 END) AS invalid_avg_total_amount
-- FROM taxi_monthly_summary;

USE analytics;

-- duplicates by business key (example)
WITH dups AS (
  SELECT COUNT(*) AS c
  FROM taxi_monthly_summary
  GROUP BY year, month, passenger_count
  HAVING COUNT(*) > 1
)
SELECT
    -- range checks
    COALESCE(SUM(CASE WHEN month NOT BETWEEN 1 AND 12 THEN 1 ELSE 0 END),0)
  + COALESCE(SUM(CASE WHEN n_trips < 0 THEN 1 ELSE 0 END),0)
  + COALESCE(SUM(CASE WHEN avg_total_amount < 0 OR avg_total_amount > 1000 THEN 1 ELSE 0 END),0)
  + COALESCE(SUM(CASE WHEN passenger_count IS NULL THEN 1 ELSE 0 END),0)
  + COALESCE(SUM(CASE WHEN passenger_count <> TRUNCATE(passenger_count,0) THEN 1 ELSE 0 END),0)
  + COALESCE(SUM(CASE WHEN passenger_count < -1 THEN 1 ELSE 0 END),0)
  + COALESCE((SELECT SUM(c-1) FROM dups),0)  -- count “extra” dup rows
  AS violations_total
FROM taxi_monthly_summary;
