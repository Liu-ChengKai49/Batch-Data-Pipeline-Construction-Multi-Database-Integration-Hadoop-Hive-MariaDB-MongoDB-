SET hive.cli.print.header=false;
USE default;

WITH
acc AS (
  SELECT COALESCE(COUNT(*),0) AS bad_time_order
  FROM yellow_taxi
  WHERE year='2019' AND tpep_pickup_datetime >= tpep_dropoff_datetime
),
val AS (
  SELECT
    COALESCE(SUM(CASE WHEN trip_distance < 0 OR trip_distance > 300  THEN 1 ELSE 0 END),0) AS bad_trip_distance,
    COALESCE(SUM(CASE WHEN fare_amount   < 0 OR fare_amount   > 1000 THEN 1 ELSE 0 END),0) AS bad_fare_amount
  FROM yellow_taxi
  WHERE year='2019'
),
comp AS (
  SELECT
    COALESCE(COUNT(*) - COUNT(tpep_pickup_datetime),0)  AS missing_pickup_ts,
    COALESCE(COUNT(*) - COUNT(tpep_dropoff_datetime),0) AS missing_dropoff_ts,
    COALESCE(COUNT(*) - COUNT(passenger_count),0)       AS missing_pax
  FROM yellow_taxi
  WHERE year='2019'
)
SELECT 1 AS ord, "accuracy.bad_time_order",               CAST(bad_time_order AS BIGINT)      FROM acc
UNION ALL SELECT 2, "validity.bad_trip_distance",         CAST(bad_trip_distance AS BIGINT)    FROM val
UNION ALL SELECT 3, "validity.bad_fare_amount",           CAST(bad_fare_amount AS BIGINT)      FROM val
UNION ALL SELECT 4, "completeness.missing_pickup_ts",     CAST(missing_pickup_ts AS BIGINT)    FROM comp
UNION ALL SELECT 5, "completeness.missing_dropoff_ts",    CAST(missing_dropoff_ts AS BIGINT)   FROM comp
UNION ALL SELECT 6, "completeness.missing_pax",           CAST(missing_pax AS BIGINT)          FROM comp
UNION ALL SELECT 7, "violations_total",
  CAST(bad_time_order + bad_trip_distance + bad_fare_amount
       + missing_pickup_ts + missing_dropoff_ts + missing_pax AS BIGINT)
FROM acc CROSS JOIN val CROSS JOIN comp
ORDER BY ord;
