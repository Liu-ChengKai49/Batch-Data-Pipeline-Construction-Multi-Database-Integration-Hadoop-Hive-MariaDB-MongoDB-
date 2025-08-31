-- -- HDFS scratch guaranteed
-- -- dfs -mkdir -p /tmp /tmp/hive /user/hive/warehouse;
-- -- dfs -chmod 1777 /tmp /tmp/hive /user/hive/warehouse;

-- !set force true
-- !sh mkdir -p /tmp/hive-local/querylog /tmp/hive-downloaded /tmp/mapred/local /tmp/mapred/tmp /tmp/.beeline
-- !sh chmod -R 777 /tmp/hive-local /tmp/hive-downloaded /tmp/mapred /tmp/.beeline
-- -- keep MR consistent across all queries (no fetch-only bypass)
-- SET hive.fetch.task.conversion=none;
-- SET hive.input.format=org.apache.hadoop.hive.ql.io.CombineHiveInputFormat;


-- -- Stable engine + paths
-- SET hive.execution.engine=mr;
-- SET mapreduce.framework.name=local;
-- SET mapreduce.jobtracker.address=local;
-- SET fs.defaultFS=hdfs://namenode:9000;
-- USE default;

-- -- Point Hive to real, writable local dirs
-- SET hive.exec.local.scratchdir=/tmp/hive-local;
-- SET hive.exec.scratchdir=/tmp/hive;                          -- HDFS
-- SET hive.querylog.location=/tmp/hive-local/querylog;
-- SET hive.downloaded.resources.dir=/tmp/hive-downloaded;

-- -- Extra safety for the MR local runner
-- SET mapreduce.cluster.local.dir=/tmp/mapred/local;
-- SET mapreduce.job.tmp.dir=/tmp/mapred/tmp;

-- -- De-risk Hive quirks
-- SET hive.vectorized.execution.enabled=false;
-- SET hive.vectorized.execution.reduce.enabled=false;
-- SET hive.cbo.enable=false;
-- -- SET hive.input.format=org.apache.hadoop.hive.ql.io.HiveInputFormat;
-- SET hive.input.format=org.apache.hadoop.hive.ql.io.CombineHiveInputFormat;


-- Accuracy
SELECT COUNT(*) AS bad_time_order
FROM yellow_taxi
WHERE year='2019'
  AND tpep_pickup_datetime >= tpep_dropoff_datetime;

-- Validity
SELECT
  SUM(CASE WHEN trip_distance < 0 OR trip_distance > 300  THEN 1 ELSE 0 END) AS bad_trip_distance,
  SUM(CASE WHEN fare_amount   < 0 OR fare_amount   > 1000 THEN 1 ELSE 0 END) AS bad_fare_amount
FROM yellow_taxi
WHERE year='2019';

-- Completeness (view already normalizes types)
SELECT
  COUNT(*) - COUNT(tpep_pickup_datetime)   AS missing_pickup_ts,
  COUNT(*) - COUNT(tpep_dropoff_datetime)  AS missing_dropoff_ts,
  COUNT(*) - COUNT(passenger_count)        AS missing_pax
FROM yellow_taxi
WHERE year='2019';


