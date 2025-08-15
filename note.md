docker restart hive-server

docker exec -it jupyterlab bash

docker exec -it hive-server bash
beeline -u jdbc:hive2://hive-server:10000

CREATE DATABASE IF NOT EXISTS taxi_db;
USE taxi_db;

DROP TABLE IF EXISTS yellow_taxi;

SET hive.mapred.supports.subdirectories=true;
SET mapred.input.dir.recursive=true;

CREATE EXTERNAL TABLE yellow_taxi (
  VendorID INT,
  tpep_pickup_datetime TIMESTAMP,
  tpep_dropoff_datetime TIMESTAMP,
  passenger_count INT,
  trip_distance DOUBLE,
  RatecodeID INT,
  store_and_fwd_flag STRING,
  PULocationID INT,
  DOLocationID INT,
  payment_type INT,
  fare_amount DOUBLE,
  extra DOUBLE,
  mta_tax DOUBLE,
  tip_amount DOUBLE,
  tolls_amount DOUBLE,
  improvement_surcharge DOUBLE,
  total_amount DOUBLE,
  congestion_surcharge DOUBLE
)
PARTITIONED BY (year INT, month INT)
STORED AS PARQUET
LOCATION '/data/taxi';



SELECT COUNT(*) FROM yellow_taxi WHERE year = 2019;

SELECT passenger_count, AVG(total_amount)
FROM yellow_taxi
WHERE year = 2019
GROUP BY passenger_count
ORDER BY passenger_count;

