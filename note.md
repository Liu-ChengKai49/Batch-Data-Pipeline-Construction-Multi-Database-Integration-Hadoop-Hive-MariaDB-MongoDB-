docker restart hive-server

docker exec -it jupyterlab bash

docker exec -it hive-server bash
beeline -u jdbc:hive2://hive-server:10000

DROP VIEW IF EXISTS yellow_taxi;

CREATE VIEW yellow_taxi AS
SELECT
  VendorID,
  CAST(from_unixtime(CAST(tpep_pickup_datetime  / 1000000 AS BIGINT)) AS TIMESTAMP) AS tpep_pickup_datetime,
  CAST(from_unixtime(CAST(tpep_dropoff_datetime / 1000000 AS BIGINT)) AS TIMESTAMP) AS tpep_dropoff_datetime,
  passenger_count,
  trip_distance,
  RatecodeID,
  store_and_fwd_flag,
  PULocationID,
  DOLocationID,
  payment_type,
  fare_amount,
  extra,
  mta_tax,
  tip_amount,
  tolls_amount,
  improvement_surcharge,
  total_amount,
  congestion_surcharge,
  year,
  month
FROM yellow_taxi_raw;

SELECT
  CAST(tpep_pickup_datetime  AS STRING) AS pickup,
  CAST(tpep_dropoff_datetime AS STRING) AS dropoff
FROM yellow_taxi
WHERE year='2019' AND month='01'
LIMIT 10;


WITH base AS (
  SELECT *
  FROM yellow_taxi
  WHERE year='2019' AND month='01'
),
bounds AS (
  SELECT
    CAST('2019-01-01 00:00:00' AS TIMESTAMP) AS ts_start,
    CAST('2019-02-01 00:00:00' AS TIMESTAMP) AS ts_end
),
flagged AS (
  SELECT
    b.*,
    (b.tpep_pickup_datetime  < bo.ts_start OR b.tpep_pickup_datetime  >= bo.ts_end) AS bad_pickup,
    (b.tpep_dropoff_datetime < bo.ts_start OR b.tpep_dropoff_datetime >= bo.ts_end) AS bad_dropoff
  FROM base b CROSS JOIN bounds bo
)
SELECT
  COUNT(*)                                                   AS total_rows,
  SUM(CASE WHEN bad_pickup THEN 1 ELSE 0 END)               AS pickup_outside,
  SUM(CASE WHEN bad_dropoff THEN 1 ELSE 0 END)              AS dropoff_outside,
  SUM(CASE WHEN bad_pickup OR bad_dropoff THEN 1 ELSE 0 END) AS either_outside,
  SUM(CASE WHEN bad_pickup AND bad_dropoff THEN 1 ELSE 0 END) AS both_outside
FROM flagged;

SELECT passenger_count, AVG(total_amount) AS avg_total_amount
FROM yellow_taxi
WHERE year = '2019'
GROUP BY passenger_count
ORDER BY passenger_count;



