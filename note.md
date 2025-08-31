docker compose down
docker compose build
docker compose up -d
<!-- docker compose --profile control up -d -->


docker restart hive-server

docker exec -it jupyterlab bash

docker exec -it hive-server bash
beeline -u jdbc:hive2://hive-server:10000

CREATE EXTERNAL TABLE IF NOT EXISTS yellow_taxi_raw (
  VendorID                 INT,
  tpep_pickup_datetime     BIGINT,     -- epoch µs (per your view); change to TIMESTAMP if already timestamp
  tpep_dropoff_datetime    BIGINT,     -- epoch µs
  passenger_count          INT,
  trip_distance            DOUBLE,
  RatecodeID               INT,
  store_and_fwd_flag       STRING,
  PULocationID             INT,
  DOLocationID             INT,
  payment_type             INT,
  fare_amount              DOUBLE,
  extra                    DOUBLE,
  mta_tax                  DOUBLE,
  tip_amount               DOUBLE,
  tolls_amount             DOUBLE,
  improvement_surcharge    DOUBLE,
  total_amount             DOUBLE,
  congestion_surcharge     DOUBLE
)
PARTITIONED BY (year STRING, month STRING)
STORED AS PARQUET
LOCATION "/data/taxi";

-- Discover partitions on HDFS
MSCK REPAIR TABLE yellow_taxi_raw;

-- Optional: peek
SHOW PARTITIONS yellow_taxi_raw;

<!-- -- Create the view exactly as you want
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

DROP VIEW IF EXISTS yellow_taxi; -->

<!-- CREATE VIEW yellow_taxi AS
SELECT
  VendorID,
  -- microseconds → seconds via integer division (no floating point)
  FROM_UNIXTIME( CAST(tpep_pickup_datetime  DIV 1000000 AS BIGINT) ) AS tpep_pickup_datetime,
  FROM_UNIXTIME( CAST(tpep_dropoff_datetime DIV 1000000 AS BIGINT) ) AS tpep_dropoff_datetime,
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
FROM default.yellow_taxi_raw; -->

DROP VIEW IF EXISTS yellow_taxi;

CREATE VIEW yellow_taxi AS
SELECT
  vendorid AS VendorID,

  -- microseconds -> seconds (integer), clamp 2000..2030, cast to TIMESTAMP
  CASE
    WHEN (tpep_pickup_datetime  DIV 1000000) BETWEEN 946684800 AND 1893456000
      THEN CAST(FROM_UNIXTIME(CAST(tpep_pickup_datetime  DIV 1000000 AS BIGINT)) AS TIMESTAMP)
    ELSE NULL
  END AS tpep_pickup_datetime,

  CASE
    WHEN (tpep_dropoff_datetime DIV 1000000) BETWEEN 946684800 AND 1893456000
      THEN CAST(FROM_UNIXTIME(CAST(tpep_dropoff_datetime DIV 1000000 AS BIGINT)) AS TIMESTAMP)
    ELSE NULL
  END AS tpep_dropoff_datetime,

  passenger_count,
  trip_distance,
  ratecodeid      AS RatecodeID,
  store_and_fwd_flag,
  pulocationid    AS PULocationID,
  dolocationid    AS DOLocationID,
  payment_type,
  fare_amount,
  extra,
  mta_tax,
  tip_amount,
  tolls_amount,
  improvement_surcharge,
  total_amount,
  congestion_surcharge,
  year, month
FROM default.yellow_taxi_raw;


-- Quick smoke test
SELECT COUNT(*) AS n FROM yellow_taxi LIMIT 1;

SELECT
  CAST(tpep_pickup_datetime  AS STRING) AS pickup,
  CAST(tpep_dropoff_datetime AS STRING) AS dropoff
FROM yellow_taxi
WHERE year='2019' AND month='01'
LIMIT 10;

SELECT COUNT(*)   
FROM yellow_taxi
WHERE year='2019';

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




# If your container is named "mongodb"
docker exec -it mongodb mongosh -u mongouser -p mongopassword --authenticationDatabase admin

use taxi_logs


